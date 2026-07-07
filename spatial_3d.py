"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D SPATIAL GRID & FLOCKING MODES                                   ║
╚══════════════════════════════════════════════════════════════════════╝

 3D spatial hash grid (27-cell queries) and both flocking mode functions
 for the 3D simulation. Reuses occlusion_geom.py for PROJECTION mode
 (XY-plane projection of angular intervals).

 Dependencies:  numpy, occlusion_geom, flock_core
──────────────────────────────────────────────────────────────────────
"""

import math
import random
from collections import defaultdict

import numpy as np

from occlusion_geom import (
    _normalise_interval,
    _interval_covered,
    _merge_interval,
)
from flock_core import (
    WIDTH, HEIGHT, V0, BOID_SIZE, MAX_FORCE,
    MODE_PROJECTION, MODE_SPATIAL,
    VISUAL_RANGE, MARGIN_BOUNDARY, BOUNDARY_MARGIN, BOUNDARY_TURN_FACTOR,
    Config,
)

# ── 3D-specific constants ──────────────────────────────────────────
DEPTH = 400                           # Z-axis extent
BOUNDARY_MARGIN_Z = 120               # Z margin for boundary nudge
MAX_VISIBILITY_RANGE = 200            # Max distance for projection occlusion (performance)
_CELL_SIZE_3D = 80                    # 3D grid cell size


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
#  PROJECTION MODE (MODE 0) — 3D Extension
# ══════════════════════════════════════════════════════════════════════
#
#  Strategy for 3D:
#   1. Project all birds onto the horizontal (XY) plane.
#   2. Use the existing 2D angular-interval occlusion code to compute
#      δ̂_xy (delta vector on horizontal plane).
#   3. Add an altitude cohesion term for the Z-axis:
#      dz = mean_z_of_visible - self.pos[2], scaled to nudge toward
#      the flock's altitude.
#   4. The 3D noise vector has both XY and Z components.
#
#  Performance: limited by MAX_VISIBILITY_RANGE to keep O(K) per bird
#  rather than O(N²). At 5000 birds with range 200, each bird sees
#  only ~100-200 others in the visibility range.


def flock_projection_3d(boid, all_boids, config, grid):
    """
    3D hybrid projection model update for one bird.

    XY-plane occlusion (Pearce et al. 2014) + Z-axis altitude cohesion.

    Parameters
    ----------
    boid       : Boid3D — the observer bird
    all_boids  : list[Boid3D] — all birds in the flock
    config     : Config — simulation parameters
    grid       : SpatialGrid3D — for candidate filtering
    """
    # ── 1. Gather visible neighbours via spatial grid filtering ──
    candidates = grid.get_nearby(boid.pos, MAX_VISIBILITY_RANGE)

    # Build angular intervals on XY plane
    entries = []  # (boid, dist_xy, centre_angle, half_width)
    for other in candidates:
        if other is boid:
            continue
        dx = other.pos[0] - boid.pos[0]
        dy = other.pos[1] - boid.pos[1]
        dist_xy = math.sqrt(dx * dx + dy * dy)
        if dist_xy < 0.001:
            continue
        centre = math.atan2(dy, dx)
        if centre < 0:
            centre += 2 * math.pi
        half = math.asin(min(BOID_SIZE / dist_xy, 1.0))
        entries.append((other, dist_xy, centre, half))

    if not entries:
        # No visible birds → no projection or alignment force
        return

    # Closest-first processing for correct occlusion
    entries.sort(key=lambda x: x[1])

    merged = []
    visible = []  # [(boid, dist_xy), ...]

    for other, dist_xy, centre, half in entries:
        start = centre - half
        end = centre + half
        segments = _normalise_interval(start, end)
        is_visible = any(
            not _interval_covered(s, e, merged) for s, e in segments
        )
        if is_visible:
            visible.append((other, dist_xy))
            for s, e in segments:
                _merge_interval(s, e, merged)

    # ── 2. δ̂ on XY plane from domain boundaries ──────────────
    delta_xy = np.zeros(3, dtype=np.float32)
    for s, e in merged:
        delta_xy[0] += math.cos(s)
        delta_xy[1] += math.sin(s)
        delta_xy[0] += math.cos(e)
        delta_xy[1] += math.sin(e)

    # Fully surrounded → no projection information
    if (len(merged) == 1 and
            merged[0][0] < 1e-9 and
            merged[0][1] > 2 * math.pi - 1e-9):
        delta_xy[0] = 0.0
        delta_xy[1] = 0.0

    delta_len = math.sqrt(delta_xy[0]**2 + delta_xy[1]**2)
    if delta_len > 0:
        delta_xy[0] /= delta_len
        delta_xy[1] /= delta_len

    # ── 3. Internal opacity Θ (cached on boid) ──────────────
    occluded = sum(e - s for s, e in merged)
    boid.last_theta = min(occluded / (2 * math.pi), 1.0)

    # ── 4. Alignment with σ nearest visible neighbours ──────
    align = np.zeros(3, dtype=np.float32)
    if visible:
        # Take σ nearest (already sorted closest-first in entries, but
        # visible list may be in a different order — re-sort by distance)
        visible.sort(key=lambda x: x[1])
        nearest = visible[:config.sigma]
        for nb, _ in nearest:
            align += nb.vel
        align /= len(nearest)

    # ── 5. Altitude cohesion: nudge toward mean Z of visible ─
    altitude_cohesion = 0.0
    if visible:
        mean_z = sum(nb.pos[2] for nb, _ in visible[:config.sigma]) / min(config.sigma, len(visible))
        altitude_cohesion = (mean_z - boid.pos[2]) * 0.01

    # ── 6. Noise (3D) ──────────────────────────────────────
    theta = random.uniform(0, 2 * math.pi)
    phi = random.uniform(0, math.pi)
    noise = np.array([
        math.cos(theta) * math.sin(phi),
        math.sin(theta) * math.sin(phi),
        math.cos(phi),
    ], dtype=np.float32)

    # ── 7. Desired direction (Eq. 3 from Pearce, 3D extended) ──
    desired = delta_xy * config.phi_p
    align_len = np.linalg.norm(align)
    if align_len > 0.001:
        desired += (align / align_len) * config.phi_a
    elif np.linalg.norm(boid.vel) > 0.001:
        desired += (boid.vel / np.linalg.norm(boid.vel)) * config.phi_a
    desired[2] += altitude_cohesion * config.phi_n
    desired += noise * config.phi_n

    desired_len = np.linalg.norm(desired)
    if desired_len < 0.001:
        theta = random.uniform(0, 2 * math.pi)
        phi = random.uniform(0, math.pi)
        desired = np.array([
            math.cos(theta) * math.sin(phi),
            math.sin(theta) * math.sin(phi),
            math.cos(phi),
        ], dtype=np.float32)

    # Normalise to V0
    desired = (desired / desired_len) * V0

    # ── 8. Reynolds steering ────────────────────────────────
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
