"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 2d — ANISOTROPIC BODIES                                    ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  Pearce et al. (2014) SI Appendix.
 Birds are modelled as ellipses rather than circles.  The projected
 size depends on the viewing angle relative to the bird's orientation:

   projected radius = √[(a·sin(θ−ψ))² + (b·cos(θ−ψ))²]

 where:
   a = semi-major axis (length, along flight direction)
   b = semi-minor axis (width, perpendicular to flight)
   θ = viewing angle from observer to target
   ψ = target bird's orientation (velocity direction)

 Default aspect ratio a:b = 2:1 — birds are longer along their
 flight direction than across it.

 When viewed from behind (θ = ψ), the minor axis b is visible.
 When viewed from the side (θ = ψ + π/2), the major axis a is visible.

 Builds on BlindAnglesBoid (Roadmap 2b).

⇔ Octave: alg2_extended.m §SECTION 7 PHASE 1  ⇔ Scilab: alg2_extended.sce §SECTION 7

 Usage:  from extensions.anisotropic_bodies import AnisotropicBoid
──────────────────────────────────────────────────────────────────────
"""

import math
import pygame

from extensions.blind_angles import BlindAnglesBoid, BLIND_ANGLE, _interval_in_blind_region
from flock_core import BOID_SIZE
from occlusion_geom import _normalise_interval, _interval_covered, _merge_interval


# ── Tunable constants ──────────────────────────────────────────────

# Semi-axes preserving approximately the same area as the original
# circular bird (π·BOID_SIZE² ≈ π·a·b → a·b = BOID_SIZE²)
# Default: a = 1.5·BOID_SIZE, b = 0.67·BOID_SIZE gives a:b ≈ 2.25:1
BOID_SEMI_MAJOR = BOID_SIZE * 1.4   # a — length along flight direction
BOID_SEMI_MINOR = BOID_SIZE * 0.7   # b — width across flight direction


class AnisotropicBoid(BlindAnglesBoid):
    """
    Extension 2d: Elliptical birds with orientation-dependent
    projected size.

    Overrides _compute_projection_and_visibility() to use the
    projected radius formula instead of a constant BOID_SIZE.

    All other behaviour (blind angles, steric repulsion, direct
    velocity) is inherited from the parent chain.
    """

    def _compute_projection_and_visibility(self, boids: list):
        """
        Core occlusion algorithm with anisotropic projected sizes.

        Each other bird's angular half-width now depends on its
        orientation relative to the viewing direction.  Birds
        seen from the side appear larger (major axis visible);
        birds seen from behind appear smaller (minor axis visible).
        """
        a = BOID_SEMI_MAJOR
        b = BOID_SEMI_MINOR
        import pygame

        # ── Build angular intervals for all other birds ────────────
        entries = []
        for other in boids:
            if other is self:
                continue
            diff = other.position - self.position
            dist = diff.length()
            if dist < 0.001:
                continue
            centre = math.atan2(diff.y, diff.x)
            if centre < 0:
                centre += 2 * math.pi

            # ── Anisotropic projected radius ──────────────────────
            #  Compute target bird's orientation ψ from its velocity
            if other.velocity.length_squared() > 0.001:
                psi = math.atan2(other.velocity.y, other.velocity.x)
            else:
                psi = 0.0

            # Projected radius depends on viewing angle (θ) relative
            # to bird orientation (ψ).
            #   θ = ψ     → see minor axis b (behind)
            #   θ = ψ+π/2 → see major axis a (side)
            d_angle = centre - psi
            projected_radius = math.sqrt(
                (a * math.sin(d_angle)) ** 2 +
                (b * math.cos(d_angle)) ** 2
            )
            half = math.asin(min(projected_radius / dist, 1.0))
            entries.append((other, dist, centre, half))

        if not entries:
            return pygame.Vector2(0, 0), [], 0.0, []

        # ── Compute blind region from our heading ──────────────────
        if self.velocity.length_squared() > 0.001:
            heading = math.atan2(self.velocity.y, self.velocity.x)
        else:
            heading = 0.0
        if heading < 0:
            heading += 2 * math.pi

        blind_centre = heading + math.pi
        if blind_centre >= 2 * math.pi:
            blind_centre -= 2 * math.pi
        blind_start = blind_centre - BLIND_ANGLE / 2
        blind_end   = blind_centre + BLIND_ANGLE / 2
        if blind_start < 0:
            blind_start += 2 * math.pi
        if blind_end > 2 * math.pi:
            blind_end -= 2 * math.pi

        # ── Filter: remove entries entirely in the blind region ────
        filtered = []
        for other, dist, centre, half in entries:
            start = centre - half
            end   = centre + half
            segments = _normalise_interval(start, end)

            all_in_blind = all(
                _interval_in_blind_region(s, e, blind_start, blind_end)
                for s, e in segments
            )
            if not all_in_blind:
                filtered.append((other, dist, centre, half))

        if not filtered:
            return pygame.Vector2(0, 0), [], 0.0, []

        # ── Sort closest-first ─────────────────────────────────────
        filtered.sort(key=lambda x: x[1])

        # ── Incremental occlusion merge ────────────────────────────
        merged = []
        visible_neighbours = []

        for other, dist, centre, half in filtered:
            start = centre - half
            end   = centre + half
            segments = _normalise_interval(start, end)

            is_visible = any(
                not _interval_covered(s, e, merged) for s, e in segments
            )
            if is_visible:
                visible_neighbours.append((other, dist))
                for s, e in segments:
                    _merge_interval(s, e, merged)

        # ── δ̂ from domain boundaries ─────────────────────────────
        delta = pygame.Vector2(0, 0)
        two_pi = 2 * math.pi
        for s, e in merged:
            delta += pygame.Vector2(math.cos(s), math.sin(s))
            delta += pygame.Vector2(math.cos(e), math.sin(e))

        if (len(merged) == 1 and
                merged[0][0] < 1e-9 and
                merged[0][1] > two_pi - 1e-9):
            delta = pygame.Vector2(0, 0)

        if delta.length() > 0:
            delta.normalize_ip()

        # ── Internal opacity Θ_i ──────────────────────────────────
        occluded = sum(e - s for s, e in merged)
        theta = min(occluded / two_pi, 1.0)

        return delta, visible_neighbours, theta, merged
