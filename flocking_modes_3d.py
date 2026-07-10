"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D FLOCKING MODES — how a bird chooses its steering                 ║
╚══════════════════════════════════════════════════════════════════════╝

 The two interchangeable steering rules the simulation toggles with `M`
 (Boid3D.flock dispatches to one of them by config.mode):

   MODE 0  PROJECTION — the Pearce et al. (2014) hybrid projection model,
                        driven by true 3D spherical-cap occlusion
                        (occlusion_3d.py). This is the paper's model.
   MODE 1  SPATIAL    — classic topological Reynolds boids (separation /
                        alignment / cohesion over the σ nearest neighbours).
                        Not paper-specific; a familiar comparison regime.

 Both take the same signature ``(boid, all_boids, config, grid)`` and
 accumulate steering onto the bird via ``boid.apply_force`` — they read the
 flock only through the spatial grid (spatial_grid_3d.py), so this module
 has no dependency on the grid's internals or on Boid3D (the bird is
 duck-typed: ``.pos`` / ``.vel`` / ``.apply_force`` / ``.last_theta``).

 Source (see sci.md §4.1 for the projection update v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂,
 §4.6 for the Reynolds-steering / speed-band implementation choices, and §4.7
 for the steric SI refinement).

 Dependencies:  numpy, occlusion_3d, steric_3d, flock_core
──────────────────────────────────────────────────────────────────────
"""

import math
import random

import numpy as np

from occlusion_3d import spherical_cap_occlusion
from steric_3d import steric_force
from flock_core import V0, MAX_FORCE, VISUAL_RANGE

# Max distance a bird considers for projection occlusion. The spatial grid
# limits candidates to this radius, so occlusion stays ~O(K) per bird rather
# than O(N²); beyond it a neighbour's cap is < 0.5° wide and negligible.
MAX_VISIBILITY_RANGE = 200


def _random_unit_vector():
    """A random direction on the unit sphere (both modes use it for noise).

    Uses the simulation's seeded ``random`` module so runs stay reproducible.
    (Sampling φ uniformly in [0, π] is the flock's existing pole-biased noise,
    kept as-is; it is only a small isotropic perturbation.)
    """
    theta = random.uniform(0, 2 * math.pi)
    phi = random.uniform(0, math.pi)
    return np.array([
        math.cos(theta) * math.sin(phi),
        math.sin(theta) * math.sin(phi),
        math.cos(phi),
    ], dtype=np.float32)


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
    #  Pearce SI refinements: blind rear cone + anisotropic bodies are
    #  applied inside the occlusion (config supplies them, or no-ops when
    #  refinements are off).
    delta, visible, theta = spherical_cap_occlusion(
        boid, candidates,
        blind_cos=config.blind_cos, anisotropy=config.anisotropy_eff)
    boid.last_theta = theta
    if not visible:
        # Still apply steric repulsion even with an empty projected view.
        if config.refinements and config.steric > 0:
            boid.apply_force(steric_force(boid, candidates, config.steric))
        return

    # ── 3. Alignment with the σ nearest visible neighbours ──────────
    align = np.zeros(3, dtype=np.float32)
    nearest = visible[:config.sigma]              # visible is closest-first
    for nb, _ in nearest:
        align += nb.vel
    align /= len(nearest)

    # ── 4. Noise — a uniform random unit vector on the sphere ───────
    noise = _random_unit_vector()

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

    # ── 7. Steric repulsion (Pearce SI) — short-range 1/d² push ─────
    if config.refinements and config.steric > 0:
        boid.apply_force(steric_force(boid, visible, config.steric))


# ══════════════════════════════════════════════════════════════════════
#  SPATIAL MODE (MODE 1) — topological Reynolds boids in 3D
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

    # Noise (3D) — scaled down so it only jitters the coordinated motion.
    noise = _random_unit_vector() * (MAX_FORCE * 0.8)

    boid.apply_force(separation * config.phi_p * 2.0)
    boid.apply_force(alignment * config.phi_a * 1.2)
    boid.apply_force(coh_dir * config.phi_n * 1.5)
    boid.apply_force(noise)

    # ── Steric repulsion (Pearce SI) — short-range 1/d² push ────────
    if config.refinements and config.steric > 0:
        boid.apply_force(steric_force(boid, neighbours, config.steric))
