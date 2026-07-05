"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 2b — BLIND ANGLES BEHIND EACH BIRD                         ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  Pearce et al. (2014) SI Appendix.
 Birds have a blind sector behind them where they cannot see other
 birds.  This is modelled by masking out an angular region of width β
 centred on the opposite of the bird's heading:

   blind region = [θ_i + π − β/2,  θ_i + π + β/2]    (mod 2π)

 Any bird j whose angular interval is entirely within the blind region
 is treated as NOT visible — excluded from the occlusion merge before
 the closest-first loop.

 β = blind angle width (default: π/3 = 60°)

 Builds on StericBoid (Roadmap 2a).

 Usage:  from extensions.blind_angles import BlindAnglesBoid
──────────────────────────────────────────────────────────────────────
"""

import math
import pygame

from extensions.steric_repulsion import StericBoid
from flock_core import BOID_SIZE
from occlusion_geom import _normalise_interval, _interval_covered, _merge_interval


# ── Tunable constants ──────────────────────────────────────────────

BLIND_ANGLE = math.pi / 3   # β — blind sector width (60°)


def _interval_in_blind_region(start: float, end: float,
                               blind_start: float, blind_end: float) -> bool:
    """
    Check whether the angular interval [start, end] lies entirely
    within the blind region [blind_start, blind_end].

    All angles are in [0, 2π).  Handles wrap-around for the blind
    region (e.g., blind_start = 5.5, blind_end = 0.8 after normalisation
    of θ + π ± β/2).
    """
    if blind_start <= blind_end:
        return blind_start - 1e-9 <= start and end <= blind_end + 1e-9
    else:
        in_seg1 = blind_start - 1e-9 <= start and end <= 2 * math.pi + 1e-9
        in_seg2 = -1e-9 <= start and end <= blind_end + 1e-9
        return in_seg1 or in_seg2


class BlindAnglesBoid(StericBoid):
    """
    Extension 2b: Blind angles added to steric-repulsion projection.

    Filters out birds whose entire angular interval falls within
    the blind sector behind the viewing bird.  These birds are
    excluded from occlusion merging — they are invisible.
    """

    def _compute_projection_and_visibility(self, boids: list):
        """
        Core occlusion algorithm with blind-angle filtering.

        Before the closest-first occlusion merge loop, entries whose
        angular interval lies entirely within the blind sector are
        removed (treated as invisible).
        """
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
            half = math.asin(min(BOID_SIZE / dist, 1.0))
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

        # ── Sort closest-first (correct occlusion ordering) ────────
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
