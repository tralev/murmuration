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

⇔ Octave: alg2_extended.m §SECTION 7 PHASE 2  ⇔ Scilab: alg2_extended.sce §SECTION 7

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

        ── WHY BLIND ANGLES? ──

        Real birds have eyes on the sides of their heads — they
        cannot see directly behind them.  Pearce et al. SI Appendix
        models this as a blind sector of width β (default 60°)
        centred on the backward direction.

        Any bird whose ENTIRE angular interval falls within the blind
        sector is invisible — excluded before the occlusion merge.

        ── ALGORITHM PIPELINE ──

        1. BUILD:    Compute angular intervals for all other birds.
        2. BLIND:    Determine blind sector [θ+π−β/2, θ+π+β/2].
        3. FILTER:   Remove entries entirely within the blind sector.
        4. SORT:     Remaining entries sorted by distance (closest first).
        5. MERGE:    Incremental occlusion merge (closest-first).
        6. DELTA:    δ̂ from merged domain boundaries.
        7. THETA:    Internal opacity Θ = Σ(merged widths) / 2π.

        Blind filtering happens BEFORE the occlusion merge, so
        invisible birds don't contribute to the occluded set AND
        don't appear in visible_neighbours for alignment.
        """

        # ── Phase 1: Build angular intervals ──────────────────────
        #  For each other bird at distance d: centre = atan2(Δy, Δx),
        #  half-width = asin(BOID_SIZE / d).  The interval [centre−half,
        #  centre+half] subtends the bird's silhouette.
        entries = []
        for other in boids:
            if other is self:
                continue
            diff = other.position - self.position
            dist = diff.length()
            if dist < 0.001:
                continue  # co-located — degenerate
            centre = math.atan2(diff.y, diff.x)
            if centre < 0:
                centre += 2 * math.pi
            half = math.asin(min(BOID_SIZE / dist, 1.0))
            entries.append((other, dist, centre, half))

        if not entries:
            return pygame.Vector2(0, 0), [], 0.0, []

        # ── Phase 2: Compute blind sector ─────────────────────────
        #  Blind region = [heading + π − β/2,  heading + π + β/2]
        #  The blind centre is directly behind the bird (−heading).
        if self.velocity.length_squared() > 0.001:
            heading = math.atan2(self.velocity.y, self.velocity.x)
        else:
            heading = 0.0
        if heading < 0:
            heading += 2 * math.pi

        # Backward direction (opposite of heading), normalised to [0, 2π)
        blind_centre = heading + math.pi
        if blind_centre >= 2 * math.pi:
            blind_centre -= 2 * math.pi

        # Blind sector extends ±β/2 from the blind centre
        blind_start = blind_centre - BLIND_ANGLE / 2
        blind_end   = blind_centre + BLIND_ANGLE / 2
        if blind_start < 0:
            blind_start += 2 * math.pi
        if blind_end > 2 * math.pi:
            blind_end -= 2 * math.pi

        # ── Phase 3: Filter birds in the blind sector ─────────────
        #  A bird is invisible if its ENTIRE angular interval lies
        #  within the blind region.  We don't use partially-visible
        #  — if even a sliver peeks out, the bird is visible.
        filtered = []
        for other, dist, centre, half in entries:
            start = centre - half
            end   = centre + half
            segments = _normalise_interval(start, end)

            # Check if ALL segments fall within the blind region
            all_in_blind = all(
                _interval_in_blind_region(s, e, blind_start, blind_end)
                for s, e in segments
            )
            if not all_in_blind:
                filtered.append((other, dist, centre, half))

        if not filtered:
            return pygame.Vector2(0, 0), [], 0.0, []

        # ── Phase 4: Sort closest-first ───────────────────────────
        #  WHY CLOSEST-FIRST?  A bird closer to you blocks your view
        #  of birds behind it.  Processing in distance order ensures
        #  correct occlusion — near birds cast shadows over far birds.
        filtered.sort(key=lambda x: x[1])

        # ── Phase 5: Incremental occlusion merge ──────────────────
        #  Walk through entries (closest to farthest).  For each:
        #    a. Check if any part of the interval is uncovered.
        #    b. If yes → bird is visible.  Merge interval into
        #       the occluded set so farther birds are hidden.
        #    c. If no  → bird is fully occluded by closer birds.
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

        # ── Phase 6: δ̂ — projection direction ───────────────────
        #  δ̂ = Σ of unit vectors to each boundary of each merged
        #  interval, normalised.  This points toward the nearest
        #  gap in the occluded visual field.
        delta = pygame.Vector2(0, 0)
        two_pi = 2 * math.pi
        for s, e in merged:
            delta += pygame.Vector2(math.cos(s), math.sin(s))
            delta += pygame.Vector2(math.cos(e), math.sin(e))

        # Fully surrounded (merged = [0, 2π]) → δ̂ = 0
        if (len(merged) == 1 and
                merged[0][0] < 1e-9 and
                merged[0][1] > two_pi - 1e-9):
            delta = pygame.Vector2(0, 0)

        if delta.length() > 0:
            delta.normalize_ip()

        # ── Phase 7: Internal opacity Θ_i ─────────────────────────
        #  Θ = (total occluded angular width) / 2π
        occluded = sum(e - s for s, e in merged)
        theta = min(occluded / two_pi, 1.0)

        return delta, visible_neighbours, theta, merged
