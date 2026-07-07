"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 6 — SPATIAL MODEL  (MODE 1)                                ║
╚══════════════════════════════════════════════════════════════════════╝

 Core computation for the topological Reynolds boids model.
 Extracted from the Boid class so the algorithm can be studied, tested,
 and reused independently of the Boid lifecycle.

 This function is called by Boid._flock_spatial() — the Boid method is a
 thin wrapper that delegates here, preserving the extension-subclassing API.

 Classic three-rule boids with topological neighbour selection:
   Separation  — steer away from neighbours that are too close
   Alignment   — steer toward the average heading of neighbours
   Cohesion    — steer toward the average position of neighbours

 Only the σ nearest neighbours within VISUAL_RANGE contribute
 (topological, not metric, range — see Ballerini et al. 2008).
 Queried via the spatial hash grid in O(1) per bird.

 Weights are repurposed from the projection model:
   φp → separation strength  (× 2.0)
   φa → alignment strength   (× 1.2)
   φn → cohesion strength    (× 1.5)
──────────────────────────────────────────────────────────────────────
"""

import math
import random

import pygame

from flock_core import (
    V0, VISUAL_RANGE, MAX_FORCE, Config, SpatialGrid,
)


def flock_spatial(boid, boids: list, config: Config, grid: SpatialGrid) -> None:
    """
    Topological Reynolds boids update for one bird.

    Steps:
      1. Query spatial grid for candidate neighbours.
      2. Filter by VISUAL_RANGE, sort by distance, take σ nearest.
      3. Compute separation / alignment / cohesion steering forces.
      4. Add noise, apply weighted forces.

    Parameters
    ----------
    boid   : Boid  — the bird to update
    boids  : list[Boid] — all birds in the flock (unused; kept for API symmetry)
    config : Config — simulation parameters (σ, φp, φa, φn)
    grid   : SpatialGrid — spatial hash for O(1) neighbour queries
    """
    # Clear projection debug state — not meaningful in spatial mode
    boid._debug_delta = pygame.Vector2(0, 0)
    boid._debug_merged = []

    candidates = grid.get_nearby(boid.position, VISUAL_RANGE)

    neighbours = []
    for other in candidates:
        if other is boid:
            continue
        d = boid.position.distance_to(other.position)
        if d < VISUAL_RANGE:
            neighbours.append((other, d))

    # 🎓 WHY TOPOLOGICAL?  Starling data shows each bird tracks
    # ~6-7 neighbours regardless of how far away they are.  If we
    # used a fixed radius (metric), dense flocks would have hundreds
    # of neighbours and dilute flocks would have none — neither
    # matches reality.  Topological interaction is scale-free.
    neighbours.sort(key=lambda x: x[1])
    neighbours = neighbours[:config.sigma]
    n = len(neighbours)

    separation = pygame.Vector2(0, 0)
    alignment  = pygame.Vector2(0, 0)
    cohesion   = pygame.Vector2(0, 0)

    if n > 0:
        for other, d in neighbours:
            alignment += other.velocity
            cohesion  += other.position

            if d < VISUAL_RANGE * 0.3:
                diff = boid.position - other.position
                if d > 0.001:
                    diff /= d
                separation += diff

        alignment /= n
        cohesion  /= n

        if alignment.length() > 0.001:
            alignment.scale_to_length(V0)
        alignment -= boid.velocity
        if alignment.length() > MAX_FORCE:
            alignment.scale_to_length(MAX_FORCE)

        cohesion -= boid.position
        if cohesion.length() > 0.001:
            cohesion.scale_to_length(V0)
        cohesion -= boid.velocity
        if cohesion.length() > MAX_FORCE:
            cohesion.scale_to_length(MAX_FORCE)

        if separation.length() > 0.001:
            separation.scale_to_length(V0)
        separation -= boid.velocity
        if separation.length() > MAX_FORCE:
            separation.scale_to_length(MAX_FORCE)

    na = random.uniform(0, 2 * math.pi)
    noise = pygame.Vector2(math.cos(na), math.sin(na)) * MAX_FORCE * 0.8

    boid.apply_force(separation * config.phi_p * 2.0)
    boid.apply_force(alignment  * config.phi_a * 1.2)
    boid.apply_force(cohesion   * config.phi_n * 1.5)
    boid.apply_force(noise)
