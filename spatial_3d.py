"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D SPATIAL GRID & FLOCKING MODES                                   ║
╚══════════════════════════════════════════════════════════════════════╝

 3D spatial hash grid (27-cell queries) and both flocking mode functions
 for the 3D simulation. PROJECTION mode uses true 3D spherical-cap
 occlusion (occlusion_3d.py) — not an XY-plane approximation.

 Dependencies:  numpy, occlusion_3d, flock_core
──────────────────────────────────────────────────────────────────────
"""

import math
import random
from collections import defaultdict

import numpy as np

from occlusion_3d import spherical_cap_occlusion
from flock_core import (
    WIDTH, HEIGHT, DEPTH, V0, BOID_SIZE, MAX_FORCE,
    MODE_PROJECTION, MODE_SPATIAL,
    VISUAL_RANGE, Config,
)

# ── 3D-specific constants ──────────────────────────────────────────
BOUNDARY_MARGIN_Z = 120               # Z margin for boundary nudge
MAX_VISIBILITY_RANGE = 200            # Max distance for projection occlusion (performance)
_CELL_SIZE_3D = 80                    # 3D grid cell size

# ── Boundary mode constants (local) ────────────────────────────────
MARGIN_BOUNDARY     = False
BOUNDARY_MARGIN     = 200
BOUNDARY_TURN_FACTOR = 1


# ══════════════════════════════════════════════════════════════════════
#  3D SPATIAL HASH GRID
# ══════════════════════════════════════════════════════════════════════

class SpatialGrid3D:
    """
    3D spatial hash grid for O(1)-per-query neighbour lookups.

    Divides the 3D simulation volume (WIDTH × HEIGHT × DEPTH) into cells
    of size cell_size. Queries check 3×3×3 = 27 adjacent cells.

    Complexity:
      rebuild()    → O(N)
      get_nearby() → O(K)  where K = birds in queried cells
    """
    def __init__(self, cell_size=_CELL_SIZE_3D):
        self.cell_size = cell_size
        self.cols = max(1, int(math.ceil(WIDTH / cell_size)))
        self.rows = max(1, int(math.ceil(HEIGHT / cell_size)))
        self.slices = max(1, int(math.ceil(DEPTH / cell_size)))
        self.cells = defaultdict(list)

    def rebuild(self, boids):
        """Repopulate the grid in O(N)."""
        self.cells.clear()
        for boid in boids:
            cx = int(boid.pos[0] // self.cell_size) % self.cols
            cy = int(boid.pos[1] // self.cell_size) % self.rows
            cz = int(boid.pos[2] // self.cell_size) % self.slices
            self.cells[(cx, cy, cz)].append(boid)

    def get_nearby(self, pos, radius):
        """
        Return all boids in cells overlapping the AABB of *radius*
        around *pos*. Checks 3×3×3 = 27 cells.
        """
        cx0 = int((pos[0] - radius) // self.cell_size)
        cx1 = int((pos[0] + radius) // self.cell_size)
        cy0 = int((pos[1] - radius) // self.cell_size)
        cy1 = int((pos[1] + radius) // self.cell_size)
        cz0 = int((pos[2] - radius) // self.cell_size)
        cz1 = int((pos[2] + radius) // self.cell_size)

        nearby = []
        for cx in range(cx0, cx1 + 1):
            wcx = cx % self.cols
            for cy in range(cy0, cy1 + 1):
                wcy = cy % self.rows
                for cz in range(cz0, cz1 + 1):
                    wcz = cz % self.slices
                    nearby.extend(self.cells.get((wcx, wcy, wcz), ()))
        return nearby


# ══════════════════════════════════════════════════════════════════════
#  PROJECTION MODE (MODE 0) — true 3D spherical-cap occlusion
# ══════════════════════════════════════════════════════════════════════
#
#  Pearce et al. (2014), extended to 3D exactly as the SI Appendix
#  describes: each neighbour is a circular cap on the observer's view
#  sphere, and the light–dark boundaries are curves on that sphere. The
#  cap geometry, occlusion, δ̂ (from the boundaries) and internal opacity
#  Θ are computed analytically in occlusion_3d.spherical_cap_occlusion —
#  no XY-plane projection, and no altitude-cohesion hack (δ̂ is a genuine
#  3-vector, so cohesion in Z falls out for free).
#
#  Performance: candidate set limited by MAX_VISIBILITY_RANGE via the
#  spatial grid, so occlusion stays roughly O(K) per bird rather than
#  O(N²) over the whole flock.


def flock_projection_3d(boid, all_boids, config, grid):
    """
    3D hybrid projection-model update for one bird, using true spherical-
    cap occlusion (Pearce et al. 2014, SI Appendix — 3D extension).

    Parameters
    ----------
    boid       : Boid3D — the observer bird
    all_boids  : list[Boid3D] — all birds in the flock (unused; kept for a
                 uniform signature with flock_spatial_3d)
    config     : Config — simulation parameters
    grid       : SpatialGrid3D — for candidate filtering
    """
    # ── 1. Candidate neighbours (grid-limited for performance) ──────
    candidates = grid.get_nearby(boid.pos, MAX_VISIBILITY_RANGE)
    if not candidates or (len(candidates) == 1 and candidates[0] is boid):
        return  # nobody in view → no projection or alignment force

    # ── 2. True 3D projection: δ̂, visible neighbours, opacity Θ ─────
    delta, visible, theta = spherical_cap_occlusion(boid, candidates)
    boid.last_theta = theta
    if not visible:
        return

    # ── 3. Alignment with the σ nearest visible neighbours ──────────
    align = np.zeros(3, dtype=np.float32)
    nearest = visible[:config.sigma]              # visible is closest-first
    for nb, _ in nearest:
        align += nb.vel
    align /= len(nearest)

    # ── 4. Noise — a uniform random unit vector on the sphere ───────
    ntheta = random.uniform(0, 2 * math.pi)
    nphi = random.uniform(0, math.pi)
    noise = np.array([
        math.cos(ntheta) * math.sin(nphi),
        math.sin(ntheta) * math.sin(nphi),
        math.cos(nphi),
    ], dtype=np.float32)

    # ── 5. Desired velocity  v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂  (Pearce Eq. 3)
    #  δ̂ is already a full 3-vector, so it drives cohesion in all axes.
    desired = delta.astype(np.float32) * config.phi_p
    align_len = np.linalg.norm(align)
    if align_len > 0.001:
        desired += (align / align_len) * config.phi_a
    elif np.linalg.norm(boid.vel) > 0.001:
        desired += (boid.vel / np.linalg.norm(boid.vel)) * config.phi_a
    desired += noise * config.phi_n

    desired_len = np.linalg.norm(desired)
    if desired_len < 0.001:
        desired = noise
        desired_len = 1.0
    desired = (desired / desired_len) * V0

    # ── 6. Reynolds steering toward the desired velocity ────────────
    steer = desired - boid.vel
    steer_len = np.linalg.norm(steer)
    if steer_len > MAX_FORCE:
        steer = (steer / steer_len) * MAX_FORCE
    boid.apply_force(steer)


# ══════════════════════════════════════════════════════════════════════
#  SPATIAL MODE (MODE 1) — 3D Extension
# ══════════════════════════════════════════════════════════════════════

def flock_spatial_3d(boid, all_boids, config, grid):
    """
    3D topological Reynolds boids update for one bird.

    Steps:
      1. Query 3D spatial grid for candidate neighbours.
      2. Filter by VISUAL_RANGE, sort by 3D distance, take σ nearest.
      3. Compute separation / alignment / cohesion steering forces in 3D.
      4. Add noise, apply weighted forces.
    """
    candidates = grid.get_nearby(boid.pos, VISUAL_RANGE)

    neighbours = []
    for other in candidates:
        if other is boid:
            continue
        d = np.linalg.norm(boid.pos - other.pos)
        if d < VISUAL_RANGE:
            neighbours.append((other, d))

    neighbours.sort(key=lambda x: x[1])
    neighbours = neighbours[:config.sigma]
    n = len(neighbours)

    separation = np.zeros(3, dtype=np.float32)
    alignment = np.zeros(3, dtype=np.float32)
    cohesion = np.zeros(3, dtype=np.float32)
    coh_dir = np.zeros(3, dtype=np.float32)  # init in case n=0

    if n > 0:
        for other, d in neighbours:
            alignment += other.vel
            cohesion += other.pos

            if d < VISUAL_RANGE * 0.3:
                diff = boid.pos - other.pos
                if d > 0.001:
                    diff = diff / d
                separation += diff

        alignment /= n
        cohesion /= n

        # Reynolds steering: desired minus current, clamped
        align_len = np.linalg.norm(alignment)
        if align_len > 0.001:
            alignment = (alignment / align_len) * V0
        alignment = alignment - boid.vel
        align_len = np.linalg.norm(alignment)
        if align_len > MAX_FORCE:
            alignment = (alignment / align_len) * MAX_FORCE

        coh_dir = cohesion - boid.pos
        coh_len = np.linalg.norm(coh_dir)
        if coh_len > 0.001:
            coh_dir = (coh_dir / coh_len) * V0
        coh_dir = coh_dir - boid.vel
        coh_len = np.linalg.norm(coh_dir)
        if coh_len > MAX_FORCE:
            coh_dir = (coh_dir / coh_len) * MAX_FORCE

        sep_len = np.linalg.norm(separation)
        if sep_len > 0.001:
            separation = (separation / sep_len) * V0
        separation = separation - boid.vel
        sep_len = np.linalg.norm(separation)
        if sep_len > MAX_FORCE:
            separation = (separation / sep_len) * MAX_FORCE

    # Noise (3D)
    theta = random.uniform(0, 2 * math.pi)
    phi = random.uniform(0, math.pi)
    noise = np.array([
        math.cos(theta) * math.sin(phi),
        math.sin(theta) * math.sin(phi),
        math.cos(phi),
    ], dtype=np.float32) * MAX_FORCE * 0.8

    boid.apply_force(separation * config.phi_p * 2.0)
    boid.apply_force(alignment * config.phi_a * 1.2)
    boid.apply_force(coh_dir * config.phi_n * 1.5)
    boid.apply_force(noise)
