"""
╔══════════════════════════════════════════════════════════════════════╗
║  ITERATION 4 — Angular Occlusion Geometry                          ║
╚══════════════════════════════════════════════════════════════════════╝

Four pure functions for working with angular intervals on the unit
circle [0, 2π). These are the mathematical foundation of the
projection model (Iteration 5).

What we learn:
  • _normalise_interval — split wrap-around intervals across 0/2π
  • _interval_covered   — check if an interval is fully occluded
  • _merge_interval     — binary-search insert + merge overlapping
  • _merge_all          — sort-and-merge a list of intervals

No Pygame dependency — pure math, fully unit-testable.
──────────────────────────────────────────────────────────────────────
"""

import math

_EPS = 1e-7   # epsilon for floating-point tolerance


def _normalise_interval(start, end):
    """
    Split an angular interval into [0, 2π) segments.
    Handles wrap-around: negative start or end > 2π.
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


def _interval_covered(start, end, merged):
    """
    Check whether [start, end] is completely covered by merged intervals.
    Uses a cursor that advances through the merged list in O(K).
    """
    cursor = start
    for ms, me in merged:
        if ms - _EPS <= cursor:
            cursor = max(cursor, me)
        if cursor >= end - _EPS:
            return True
        if ms > cursor + _EPS:
            break
    return cursor >= end - _EPS


def _merge_interval(start, end, merged):
    """
    Insert [start, end] into the sorted merged list, merging with
    overlapping adjacent intervals. Uses binary search for O(log K)
    insertion point.
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

    # Merge left
    if idx > 0 and merged[idx - 1][1] >= merged[idx][0] - _EPS:
        merged[idx - 1][1] = max(merged[idx - 1][1], merged[idx][1])
        merged.pop(idx)
        idx -= 1

    # Merge right (chain in case of multiple overlaps)
    while idx < len(merged) - 1 and merged[idx][1] >= merged[idx + 1][0] - _EPS:
        merged[idx][1] = max(merged[idx][1], merged[idx + 1][1])
        merged.pop(idx + 1)


def _merge_all(intervals):
    """
    Sort intervals by start, then merge all overlapping ones.
    Returns a list of non-overlapping [start, end] pairs.
    """
    if not intervals:
        return []
    merged = [list(intervals[0])]
    for start, end in sorted(intervals):
        _merge_interval(start, end, merged)
    return merged


# ── Quick smoke test ────────────────────────────────────────────────
if __name__ == "__main__":
    # Normalise: wrap-around across 0
    segs = _normalise_interval(-0.5, 0.5)
    assert len(segs) == 2, f"Expected 2 segments, got {len(segs)}"

    # Merge: overlapping intervals become one
    merged = []
    _merge_interval(1.0, 3.0, merged)
    _merge_interval(2.0, 4.0, merged)
    assert merged == [[1.0, 4.0]], f"Expected [[1,4]], got {merged}"

    # Cover: fully covered interval
    assert _interval_covered(1.5, 2.5, [[1.0, 3.0]]), "Should be covered"

    # Merge all
    result = _merge_all([(3.0, 4.0), (1.0, 2.0), (1.5, 3.5)])
    assert result == [[1.0, 4.0]], f"Expected [[1,4]], got {result}"

    print("All occlusion geometry smoke tests passed!")
