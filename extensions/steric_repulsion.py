"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 2a — STERIC / REPULSIVE INTERACTIONS                       ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  Pearce et al. (2014) SI Appendix.
 Birds are \"phantoms\" without a repulsive term — they can overlap.
 This extension adds a short-range 1/r² repulsive force:

   v_i  +=  φ_s · Σ_{j: d_ij < r_s}  (r̂_ji / d_ij²)

 where:
   φ_s = steric weight (~0.01–0.05)
   r_s = steric radius (~2b = 2·BOID_SIZE)
   r̂_ji = unit vector from j to i

 The repulsion is applied to the σ nearest visible neighbours only.

 Builds on DirectVelocityBoid (Roadmap 1a).

 Usage:  from extensions.steric_repulsion import StericBoid
──────────────────────────────────────────────────────────────────────
"""

import pygame

from extensions.direct_velocity import DirectVelocityBoid
from flock_core import BOID_SIZE, V0


# ── Tunable constants ──────────────────────────────────────────────

PHI_STERIC  = 0.03     # steric weight (small — just enough to prevent overlap)
STERIC_RADIUS = 2 * BOID_SIZE   # r_s — birds within this distance repel


class StericBoid(DirectVelocityBoid):
    """
    Extension 2a: Steric repulsion added to direct-velocity projection.

    After computing the desired direction via the projection model,
    a short-range repulsive term pushes overlapping birds apart.
    """

    def _flock_projection(self, boids: list, config):
        """
        Projection model with steric repulsion.

        Inherits direct velocity setting from DirectVelocityBoid
        and adds a repulsion loop after computing the desired direction.
        """
        # ── Call parent: compute δ̂, visible neighbours, desired ──
        super()._flock_projection(boids, config)

        # ── Steric repulsion: push away from close neighbours ──────
        #  Check all boids within steric radius. Physical contact
        #  is felt regardless of visibility — a bird overlapping you
        #  pushes you even if you can't see it.
        repulsion = pygame.Vector2(0, 0)
        for other in boids:
            if other is self:
                continue
            diff = self.position - other.position
            d = diff.length()
            if d < STERIC_RADIUS and d > 0.001:
                # 1/r² falloff toward unit direction
                diff /= d
                repulsion += diff / (d * d)

        if repulsion.length() > 0.001:
            # Scale by steric weight and add directly to velocity
            # (not steering — we're in direct-velocity mode)
            repulsion.normalize_ip()
            # The steric force scales with 1/r² already; weight just
            # controls overall strength relative to V0.
            repulsion *= PHI_STERIC * BOID_SIZE
            self.velocity += repulsion
            # Re-normalise to V0 so steric changes direction but not speed
            if self.velocity.length() > 0.001:
                self.velocity.scale_to_length(V0)
