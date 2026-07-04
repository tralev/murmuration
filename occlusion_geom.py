"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 4 — ANGULAR-INTERVAL UTILITIES                            ║
╚══════════════════════════════════════════════════════════════════════╝

 Module-level helper functions for working with angular intervals
 on [0, 2π).  Used by both the projection model and external opacity.

 An angular interval is a pair (start, end) representing the arc
 [start, end) subtended by a bird as seen from a viewpoint.
 Intervals may wrap around 2π (e.g., start = 6.0, end = 0.5).

 These functions are pure — they depend only on the math module.
 They can be tested without Pygame or any simulation state.
──────────────────────────────────────────────────────────────────────
"""

import math


def _normalise_interval(start: float, end: float) -> list:
    """
    Split an angular interval [start, end] into one or two segments
    that each lie entirely within [0, 2π).

    Handles wrap-around:
      start < 0       → [(start + 2π, 2π), (0, end)]
      end > 2π        → [(start, 2π), (0, end − 2π)]
      both in [0, 2π) → [(start, end)]

    ┌─────────────────────────────────────────────────────────────┐
    │  EXAMPLE: Bird at angle 0 (facing right). A neighbour at   │
    │  angle 350° (just left of right) subtends an interval      │
    │  that crosses the 0°/360° boundary:                        │
    │                                                            │
    │    0°          90°         180°         270°         360°  │
    │    ├────────────┼────────────┼────────────┼────────────┤  │
    │    ██████████████████████████░░░░░░░░░░░░░███████████████  │
    │    └── segment 2 ──┘                 └─── segment 1 ───┘  │
    │                                                            │
    │  interval = [345°, 355°] → normalised to:                  │
    │    segment 1: [345° = 6.02 rad, 360° = 2π rad]            │
    │    segment 2: [0° = 0 rad,     355° = 6.20 rad - 2π]     │
    └─────────────────────────────────────────────────────────────┘
    """
    segments = []
    if start < 0:
        segments.append((start + 2 * math.pi, 2 * math.pi))
        segments.append((0, end))
    elif end > 2 * math.pi:
        segments.append((start, 2 * math.pi))
        segments.append((0, end - 2 * math.pi))
    else:
        segments.append((start, end))
    return segments


def _interval_covered(start: float, end: float, merged: list) -> bool:
    """
    Check whether the interval [start, end] is fully covered by the
    merged (occluded) interval set.

    Walks through merged intervals in order, advancing a cursor from
    start toward end.  If cursor reaches end, the interval is covered.

    Complexity: O(|merged|) per call.
    """
    cursor = start
    for ms, me in merged:
        if ms <= cursor + 1e-9 < me:
            cursor = max(cursor, me)
        if cursor >= end - 1e-9:
            return True
    return cursor >= end - 1e-9


def _merge_interval(start: float, end: float, merged: list):
    """
    Insert [start, end] into the sorted merged interval list,
    merging with at most two adjacent intervals.

    Uses binary search to find the insertion point, then merges left
    and right (chaining in case the new interval bridges multiple
    existing ones).  Complexity: O(log |merged| + merges).
    """
    n = len(merged)
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        if merged[mid][0] < start:
            lo = mid + 1
        else:
            hi = mid
    idx = lo

    merged.insert(idx, [start, end])

    # Merge with left neighbour if overlapping
    if idx > 0 and merged[idx - 1][1] >= merged[idx][0] - 1e-9:
        merged[idx - 1][1] = max(merged[idx - 1][1], merged[idx][1])
        merged.pop(idx)
        idx -= 1

    # Merge with right neighbours (chain in case of multiple overlaps)
    while idx < len(merged) - 1 and merged[idx][1] >= merged[idx + 1][0] - 1e-9:
        merged[idx][1] = max(merged[idx][1], merged[idx + 1][1])
        merged.pop(idx + 1)


def _merge_all(intervals: list) -> list:
    """
    Sort-and-merge a list of (start, end) intervals into non-overlapping
    merged intervals.  Used by compute_internal_opacity and external opacity.

    Complexity: O(N log N) where N = |intervals|.
    """
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: x[0])
    merged = [list(intervals[0])]
    for s, e in intervals[1:]:
        if s <= merged[-1][1] + 1e-9:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged
