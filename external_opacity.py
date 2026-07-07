"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 7 — EXTERNAL OPACITY  (Θ')                                 ║
╚══════════════════════════════════════════════════════════════════════╝

Θ' — fraction of the sky obscured from a distant external observer.
The observer is placed at (−2000, HEIGHT/2), far to the left of the
flock.  Angular intervals subtended by each bird are merged to find
the total occluded angular width.

Complexity: O(N log N) where N = |flock|.

Imported by metrics.py (FlockMetrics.update) and by Octave/Scilab
equivalents (alg2.m §SECTION 7, alg2.sce §SECTION 7).
──────────────────────────────────────────────────────────────────────
"""

import math
import pygame

from occlusion_geom import _normalise_interval, _merge_all
from flock_core import HEIGHT, BOID_SIZE


def compute(flock: list) -> float:
    """
    Compute Θ' — external opacity from a distant left-side observer.

    For each bird, compute the angular interval it subtends from the
    viewpoint at (−2000, HEIGHT/2).  Sort all intervals by start angle,
    merge overlaps, and sum the merged widths divided by 2π.
    """
    if not flock:
        return 0.0

    viewpoint = pygame.Vector2(-2000, HEIGHT / 2)
    intervals = []
    for b in flock:
        diff = b.position - viewpoint
        dist = diff.length()
        if dist < 0.001:
            continue
        centre = math.atan2(diff.y, diff.x)
        if centre < 0:
            centre += 2 * math.pi
        half = math.asin(min(BOID_SIZE / dist, 1.0))
        intervals.extend(_normalise_interval(centre - half, centre + half))

    merged = _merge_all(intervals)
    occluded = sum(e - s for s, e in merged)
    return min(occluded / (2 * math.pi), 1.0)
