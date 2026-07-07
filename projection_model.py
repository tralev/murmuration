"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 5 — PROJECTION MODEL  (MODE 0)                             ║
╚══════════════════════════════════════════════════════════════════════╝

 Core computation for the hybrid projection model (Pearce et al. 2014).
 Extracted from the Boid class so the algorithm can be studied, tested,
 and reused independently of the Boid lifecycle.

 These functions are called by Boid._flock_projection() and
 Boid._compute_projection_and_visibility() — the Boid methods are thin
 wrappers that delegate here, preserving the extension-subclassing API.

 Reference:  Pearce et al. (2014), Eq. (3):
   v_i(t+1) = φp · δ̂_i(t) + φa · ⟨v̂_j(t)⟩_visible + φn · η̂_i(t)

──────────────────────────────────────────────────────────────────────
"""

import math
import random

import pygame

from occlusion_geom import (
    _normalise_interval,
    _interval_covered,
    _merge_interval,
)
from flock_core import (
    V0, BOID_SIZE, MAX_FORCE, Config,
)


# ╔══════════════════════════════════════════════════════════════╗
# ║  Angular-interval occlusion — the core projection algorithm  ║
# ╚══════════════════════════════════════════════════════════════╝
#
#  For each other bird j, compute the angular interval [θⱼ − αⱼ, θⱼ + αⱼ]
#  it subtends, where  αⱼ = arcsin(min(b / dⱼ, 1)).
#
#  Process birds closest-first (distance-sorted).  A bird is *visible*
#  iff any part of its interval is NOT already covered by previously
#  merged (closer) intervals.  Visible intervals are then merged into
#  the occluded set.
#
#  δ̂ is computed from the *boundaries* of the merged occluded intervals:
#    δ̂ = Σ_{boundaries} (cos θ, sin θ)   (normalised)
#
#  Complexity: O(N log N) — n·log n sort + n interval merges.
# ───────────────────────────────────────────────────────────────


def compute_projection_and_visibility(boid, boids: list):
    """
    Core of the hybrid projection model — angular-interval occlusion.

    For each other bird j, compute the angular interval [θⱼ − αⱼ, θⱼ + αⱼ]
    it subtends, where  αⱼ = arcsin(min(b / dⱼ, 1)).

    Process birds closest-first (distance-sorted).  A bird is *visible*
    iff any part of its interval is NOT already covered by previously
    merged (closer) intervals.  Visible intervals are then merged into
    the occluded set.

    δ̂ is computed from the *boundaries* of the merged occluded intervals:
      δ̂ = Σ_{boundaries} (cos θ, sin θ)   (normalised)

    Parameters
    ----------
    boid   : Boid  — the observer bird
    boids  : list[Boid] — all birds in the flock

    Returns
    -------
    delta   : pygame.Vector2  — unit vector δ̂ to nearest domain boundary
    visible : list[(Boid, float)] — visible neighbours (closest first)
    theta   : float  — internal opacity Θ_i ∈ [0, 1]
    merged  : list[(float, float)] — merged intervals (for debug view)
    """
    # ── Build angular intervals for all other birds ────────────
    entries = []  # (boid, distance, centre_angle, half_width)
    for other in boids:
        if other is boid:
            continue
        diff = other.position - boid.position
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

    # 🎓 WHY CLOSEST-FIRST?  A bird closer to you blocks your
    # view of birds behind it.  If we processed birds in random
    # order, a distant bird might be marked "visible" and then a
    # closer bird (processed later) would incorrectly extend the
    # occluded set over it.  Sorting by distance gives correct
    # occlusion: near birds cast shadows over far birds.
    entries.sort(key=lambda x: x[1])

    # ── Incremental occlusion merge ────────────────────────────
    merged = []              # [(start, end), …]  merged occluded intervals
    visible_neighbours = []  # [(boid, distance), …]

    for other, dist, centre, half in entries:
        start = centre - half
        end   = centre + half
        segments = _normalise_interval(start, end)

        # Visibility test: is ANY segment partially uncovered?
        is_visible = any(
            not _interval_covered(s, e, merged) for s, e in segments
        )
        if is_visible:
            visible_neighbours.append((other, dist))
            for s, e in segments:
                _merge_interval(s, e, merged)

    # ── δ̂ from domain boundaries ─────────────────────────────
    delta = pygame.Vector2(0, 0)
    for s, e in merged:
        delta += pygame.Vector2(math.cos(s), math.sin(s))
        delta += pygame.Vector2(math.cos(e), math.sin(e))

    if (len(merged) == 1 and
            merged[0][0] < 1e-9 and
            merged[0][1] > 2 * math.pi - 1e-9):
        delta = pygame.Vector2(0, 0)

    if delta.length() > 0:
        delta.normalize_ip()

    # ── Internal opacity Θ_i ──────────────────────────────────
    occluded = sum(e - s for s, e in merged)
    theta = min(occluded / (2 * math.pi), 1.0)

    return delta, visible_neighbours, theta, merged


# ╔══════════════════════════════════════════════════════════════╗
# ║  Projection-mode flocking step                               ║
# ╚══════════════════════════════════════════════════════════════╝
#
#  Steps:
#    1. Compute δ̂, visible neighbours, and Θ via angular occlusion.
#    2. Alignment with σ nearest visible neighbours.
#    3. Noise vector.
#    4. Desired direction: v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
#    5. Reynolds steering toward desired direction.
# ───────────────────────────────────────────────────────────────


def flock_projection(boid, boids: list, config: Config) -> None:
    """
    Hybrid projection model update for one bird.

    Steps:
      1. Compute δ̂, visible neighbours, and Θ via angular occlusion.
      2. Alignment with σ nearest visible neighbours.
      3. Noise vector.
      4. Desired direction: v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
      5. Reynolds steering toward desired direction.

    Parameters
    ----------
    boid   : Boid  — the bird to update
    boids  : list[Boid] — all birds in the flock
    config : Config — simulation parameters (φp, φa, φn, σ)
    """
    # ── Step 1: projection direction & visible neighbours ──────
    #  O(N log N) — compute angular intervals to all other birds,
    #  merge them closest-first, and determine δ̂ from domain boundaries.
    delta, visible, theta, merged = boid._compute_projection_and_visibility(boids)
    boid._last_theta = theta
    boid._debug_delta = delta
    boid._debug_merged = merged

    # ── Step 2: alignment with σ nearest visible neighbours ────
    #  ⟨v̂_j⟩_visible — mean velocity direction of σ closest visible birds.
    align = pygame.Vector2(0, 0)
    if visible:
        nearest = visible[:config.sigma]
        for nb, _ in nearest:
            align += nb.velocity
        align /= len(nearest)

    # ── Step 3: noise — random unit vector η̂ ──────────────────
    na = random.uniform(0, 2 * math.pi)
    noise = pygame.Vector2(math.cos(na), math.sin(na))

    # 🎓 TEACHING MOMENT:  Eq. 3 from Pearce et al. (2014)
    #  v_desired = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
    #  This *replaces* the classic separation + cohesion forces.
    #  The projection term δ̂ alone is enough to keep the flock
    #  together — no explicit attraction/repulsion needed.
    desired = delta * config.phi_p
    if align.length() > 0.001:
        desired += align.normalize() * config.phi_a
    else:
        if boid.velocity.length() > 0.001:
            desired += boid.velocity.normalize() * config.phi_a
    desired += noise * config.phi_n

    if desired.length() < 0.001:
        desired = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))

    # Normalise to constant speed V₀ for smooth animation
    desired.normalize_ip()
    desired *= V0

    # ── Step 5: Reynolds-style steering ────────────────────────
    #  steer = v_desired − v_current, clamped to MAX_FORCE
    steer = desired - boid.velocity
    if steer.length() > MAX_FORCE:
        steer.scale_to_length(MAX_FORCE)
    boid.apply_force(steer)
