"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 1b — EXTERNAL OPACITY FROM MULTIPLE VIEWPOINTS             ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  Pearce et al. (2014).
 Θ' — fraction of the sky obscured from a distant external observer.

 The original implementation uses a single fixed viewpoint at
 (-2000, HEIGHT/2).  The paper defines Θ' implicitly as an average
 over many observer positions.  This extension samples K viewpoints
 evenly spaced on a circle of radius R_ext:

   Θ'  =  ⟨ Θ'(viewpoint_k) ⟩    for k = 0..K-1

   viewpoint_k = (R_ext · cos(θ_k),  R_ext · sin(θ_k))
   θ_k = 2π · k / K

 Default: K = 12 viewpoints, R_ext = 2000.

 Usage:
   from extensions.multi_viewpoint_opacity import (
       external_opacity_multi_viewpoint,
       FlockMetricsExtended,
   )

⇔ Octave: alg2_extended.m §SECTION 8  ⇔ Scilab: alg2_extended.sce §SECTION 8
──────────────────────────────────────────────────────────────────────
"""

import math
import random
import pygame

from occlusion_geom import _normalise_interval, _merge_all
from flock_core import V0, BOID_SIZE, MODE_PROJECTION
from metrics import FlockMetrics


# ── Tunable constants ──────────────────────────────────────────────

K_VIEWPOINTS = 12       # number of observer viewpoints on the circle
R_EXT = 2000            # radius of the observer circle


def external_opacity_multi_viewpoint(flock: list,
                                      k: int = K_VIEWPOINTS,
                                      r_ext: float = R_EXT) -> float:
    """
    Compute Θ' as the average over K viewpoints on a circle.

    ── WHY MULTIPLE VIEWPOINTS? ──

    The original metrics.py computes Θ' from a SINGLE fixed viewpoint
    at (−2000, HEIGHT/2).  This is sensitive to the flock's position
    — if the flock moves, the opacity changes even if the internal
    structure is identical.

    The paper defines Θ' implicitly as the fraction of sky obscured
    from ANY distant observer.  Averaging over K viewpoints on a
    circle gives a rotationally-invariant measure:

      Θ' = (1/K) · Σ_{k=0}^{K-1} Θ'(viewpoint_k)

      where viewpoint_k = (R_ext·cos(2πk/K),  R_ext·sin(2πk/K))

    ── ALGORITHM (per viewpoint) ──

    1. Place observer at angle θ_k on a circle of radius r_ext.
    2. For each bird, compute the angular interval [centre−half,
       centre+half] it subtends from this observer.
    3. Merge all intervals (sort-and-merge, O(N log N)).
    4. Θ'_k = Σ(merged widths) / 2π  — fraction of sky obscured.
    5. Θ' = mean(Θ'_k) across all K viewpoints.

    Complexity: O(K · N log N) where K = viewpoints, N = |flock|.

    Parameters
    ----------
    flock : list[Boid]
    k : int — number of viewpoints (default 12)
    r_ext : float — radius of the viewpoint circle (default 2000)

    Returns
    -------
    float — mean Θ' across all viewpoints (0 = transparent, 1 = opaque)
    """
    if not flock:
        return 0.0

    total = 0.0

    # ── Main loop: iterate over K viewpoints ─────────────────────
    #  Each viewpoint is at angle θ_k = 2π·k/K on a circle of radius
    #  r_ext, centred at the origin.
    for i in range(k):
        theta = 2 * math.pi * i / k
        viewpoint = pygame.Vector2(r_ext * math.cos(theta),
                                    r_ext * math.sin(theta))

        # ── Build angular intervals from this viewpoint ──────────
        #  For each bird at 2D position b.position, compute the
        #  direction and angular width as seen from the observer.
        intervals = []
        for b in flock:
            diff = b.position - viewpoint
            dist = diff.length()
            if dist < 0.001:
                continue  # bird at observer — degenerate
            centre = math.atan2(diff.y, diff.x)
            if centre < 0:
                centre += 2 * math.pi
            half = math.asin(min(BOID_SIZE / dist, 1.0))
            # Normalise the interval [centre−half, centre+half] into
            # [0, 2π) segments (handles wrap-around across 0/2π).
            intervals.extend(_normalise_interval(centre - half, centre + half))

        # ── Merge and compute opacity for this viewpoint ─────────
        if intervals:
            merged = _merge_all(intervals)
            occluded = sum(e - s for s, e in merged)
            theta_k = min(occluded / (2 * math.pi), 1.0)
        else:
            theta_k = 0.0

        total += theta_k

    return total / k


class FlockMetricsExtended(FlockMetrics):
    """
    Extended FlockMetrics that uses multi-viewpoint Θ' instead of
    single-viewpoint.

    Inherits all behaviour from FlockMetrics and overrides update()
    to compute Θ' from K viewpoints around the flock instead of a
    single fixed point at (-2000, HEIGHT/2).

    The internal opacity Θ and order parameter α are unchanged.
    """

    def update(self, flock: list, clock: pygame.time.Clock, config):
        """
        Update all metrics with multi-viewpoint Θ'.

        Same as FlockMetrics.update() but replaces the single-viewpoint
        external opacity with the K-viewpoint average.
        """
        s = self.SMOOTH
        n = len(flock)
        if n == 0:
            return

        # ── FPS (EMA-smoothed) ────────────────────────────────────
        self._fps += (clock.get_fps() - self._fps) * s

        # ── Θ — internal opacity (unchanged) ──────────────────────
        if config.mode == MODE_PROJECTION:
            theta = sum(b._last_theta for b in flock) / n
        else:
            sample_n = min(self.SAMPLES, n)
            sampled = random.sample(flock, sample_n)
            theta = sum(b.compute_internal_opacity(flock) for b in sampled) / sample_n
        self._theta += (theta - self._theta) * s

        # ── α — order parameter (unchanged) ──────────────────────
        total_v = pygame.Vector2(0, 0)
        for b in flock:
            total_v += b.velocity
        alpha = total_v.length() / (n * V0)
        self._alpha += (alpha - self._alpha) * s

        # ── Θ' — MULTI-VIEWPOINT external opacity ────────────────
        #  This is the only line changed from FlockMetrics.update():
        #    from:  theta_ext = _external_opacity(flock)
        #    to:    theta_ext = external_opacity_multi_viewpoint(flock)
        theta_ext = external_opacity_multi_viewpoint(
            flock, k=K_VIEWPOINTS, r_ext=R_EXT
        )
        self._theta_ext += (theta_ext - self._theta_ext) * s
