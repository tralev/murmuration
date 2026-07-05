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

        ── THEORY ──

        In the base model, birds are "phantoms" — they can occupy
        the same position without consequence.  This is unrealistic.

        Pearce et al. (2014) SI Appendix introduces a short-range
        repulsive force:

          F_rep = φ_s · Σ_{j: d_ij < r_s}  (r̂ⱼᵢ / d_ij²)

        where:
          φ_s = steric weight (0.03 — small, only prevents overlap)
          r_s = steric radius (2·BOID_SIZE — activates at close range)
          r̂ⱼᵢ = unit vector FROM neighbour j TO self i

        The 1/d² falloff means the force is negligible at distance
        and strong at contact — just enough to prevent birds from
        overlapping without affecting large-scale flock structure.

        ── IMPLEMENTATION ──

        1. Parent computes desired velocity via projection model.
        2. Iterate ALL boids (not just visible ones — physical
           contact is felt even if the bird is behind you).
        3. For each bird within STERIC_RADIUS:
           a. Compute direction away from the neighbour.
           b. Add repulsive contribution proportional to 1/d².
        4. Add cumulative repulsion to velocity.
        5. Re-normalise to v₀ (repulsion changes direction, not speed).

        The re-normalisation ensures the bird maintains cruising speed
        after evasive manoeuvres — it steers around neighbours, it
        doesn't slow down.
        """

        # ── Phase 1: compute projection direction (parent) ────────
        #  This sets self.velocity to the projection-model desired
        #  direction.  We then adjust it with repulsion.
        super()._flock_projection(boids, config)

        # ── Phase 2: steric repulsion loop ────────────────────────
        #  Sum repulsive forces from ALL close birds, regardless of
        #  visibility.  Physical contact doesn't require line-of-sight.
        repulsion = pygame.Vector2(0, 0)

        for other in boids:
            if other is self:
                continue

            # Displacement vector FROM neighbour TO self
            #  (we want to push self AWAY from the neighbour)
            diff = self.position - other.position
            d = diff.length()

            # Only birds within the steric radius repel
            if d < STERIC_RADIUS and d > 0.001:
                diff /= d                         # unit direction away
                repulsion += diff / (d * d)       # 1/r² weighting

        # ── Phase 3: apply repulsion to velocity ──────────────────
        if repulsion.length() > 0.001:
            repulsion.normalize_ip()

            # Scale: φ_s × BOID_SIZE gives a small, dimensionalised
            # force.  BOID_SIZE is the characteristic length scale;
            # without it the force would be dimensionless.
            repulsion *= PHI_STERIC * BOID_SIZE

            self.velocity += repulsion

            # Re-normalise to cruising speed v₀
            #  Steric repulsion steers the bird — it doesn't change
            #  its speed.  This models a bird that banks away from
            #  a collision without slowing down.
            if self.velocity.length() > 0.001:
                self.velocity.scale_to_length(V0)
