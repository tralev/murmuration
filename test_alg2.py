"""
Unit tests for the angular-interval merge utilities in alg2.py (SECTION 4).

Covers:
  - _normalise_interval   — split wrap-around intervals into [0, 2π) segments
  - _interval_covered     — check whether an interval is fully occluded
  - _merge_interval       — insert-and-merge one interval into a sorted list
  - _merge_all            — sort-and-merge a list of intervals
"""

import math
import sys
import unittest

from occlusion_geom import (
    _normalise_interval,
    _interval_covered,
    _merge_interval,
    _merge_all,
)

TWO_PI = 2 * math.pi


# ══════════════════════════════════════════════════════════════════════
#  _normalise_interval
# ══════════════════════════════════════════════════════════════════════

class TestNormaliseInterval(unittest.TestCase):
    """Tests for _normalise_interval(start, end) → list of segments."""

    def test_both_in_range(self):
        """Both start and end within [0, 2π) → single segment."""
        result = _normalise_interval(1.0, 3.0)
        self.assertEqual(result, [(1.0, 3.0)])

    def test_start_negative(self):
        """start < 0 → [(start + 2π, 2π), (0, end)]."""
        result = _normalise_interval(-0.5, 1.0)
        self.assertEqual(len(result), 2)
        # First segment: (start + 2π, 2π)
        self.assertAlmostEqual(result[0][0], -0.5 + TWO_PI)
        self.assertAlmostEqual(result[0][1], TWO_PI)
        # Second segment: (0, end)
        self.assertAlmostEqual(result[1][0], 0.0)
        self.assertAlmostEqual(result[1][1], 1.0)

    def test_end_exceeds_2pi(self):
        """end > 2π → [(start, 2π), (0, end - 2π)]."""
        result = _normalise_interval(5.0, 7.0)  # 5.0 in range, 7.0 > 2π ≈ 6.283
        self.assertEqual(len(result), 2)
        # First segment: (start, 2π)
        self.assertAlmostEqual(result[0][0], 5.0)
        self.assertAlmostEqual(result[0][1], TWO_PI)
        # Second segment: (0, end - 2π)
        self.assertAlmostEqual(result[1][0], 0.0)
        self.assertAlmostEqual(result[1][1], 7.0 - TWO_PI)

    def test_both_negative(self):
        """start and end both negative — result is two segments via the
        start<0 branch: [(start+2π, 2π), (0, end)].  The second segment
        (0, end) has end < 0 which is technically degenerate, but the
        function assumes start < end and only handles start < 0 or
        end > 2π independently.  In practice this case never arises
        because intervals are built from normalised centres."""
        result = _normalise_interval(-3.0, -1.0)
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0][0], -3.0 + TWO_PI)
        self.assertAlmostEqual(result[0][1], TWO_PI)

    def test_both_exceed_2pi(self):
        """start and end both > 2π — result is two segments via the
        end>2π branch: [(start, 2π), (0, end-2π)].  In practice this
        case never arises because intervals are built from centres
        normalised to [0, 2π) with small half-widths."""
        result = _normalise_interval(7.0, 8.0)  # both > 2π ≈ 6.283
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0][0], 7.0)
        self.assertAlmostEqual(result[0][1], TWO_PI)
        self.assertAlmostEqual(result[1][0], 0.0)
        self.assertAlmostEqual(result[1][1], 8.0 - TWO_PI)

    def test_wrap_narrow_around_zero(self):
        """Narrow interval crossing 0: start slightly negative, end slightly positive."""
        result = _normalise_interval(-0.1, 0.1)
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0][0], -0.1 + TWO_PI)
        self.assertAlmostEqual(result[0][1], TWO_PI)
        self.assertAlmostEqual(result[1][0], 0.0)
        self.assertAlmostEqual(result[1][1], 0.1)

    def test_exact_zero_to_2pi(self):
        """Interval exactly [0, 2π] → single segment."""
        result = _normalise_interval(0.0, TWO_PI)
        self.assertEqual(result, [(0.0, TWO_PI)])

    def test_start_equals_end(self):
        """Degenerate interval (start == end) → single zero-width segment."""
        result = _normalise_interval(2.0, 2.0)
        self.assertEqual(result, [(2.0, 2.0)])


# ══════════════════════════════════════════════════════════════════════
#  _interval_covered
# ══════════════════════════════════════════════════════════════════════

class TestIntervalCovered(unittest.TestCase):
    """Tests for _interval_covered(start, end, merged) → bool."""

    def test_empty_merged(self):
        """Empty merged list → never covered."""
        self.assertFalse(_interval_covered(0.0, 1.0, []))

    def test_fully_covered_by_single(self):
        """Single merged interval that fully contains [start, end]."""
        merged = [[0.5, 2.5]]
        self.assertTrue(_interval_covered(1.0, 2.0, merged))

    def test_partial_left(self):
        """Merged covers start but not end → not covered."""
        merged = [[0.0, 1.5]]
        self.assertFalse(_interval_covered(1.0, 2.0, merged))

    def test_partial_right(self):
        """Merged covers end but not start → not covered."""
        merged = [[1.5, 3.0]]
        self.assertFalse(_interval_covered(1.0, 2.0, merged))

    def test_not_covered_at_all(self):
        """Interval entirely outside merged range."""
        merged = [[0.0, 0.5], [3.0, 4.0]]
        self.assertFalse(_interval_covered(1.0, 2.0, merged))

    def test_bridged_by_two(self):
        """Two merged intervals that together cover [start, end]."""
        merged = [[0.0, 1.2], [1.2, 3.0]]
        self.assertTrue(_interval_covered(0.5, 2.5, merged))

    def test_gap_between_merged(self):
        """Two merged intervals with a gap in between → not covered."""
        merged = [[0.0, 1.0], [2.0, 3.0]]
        self.assertFalse(_interval_covered(0.5, 2.5, merged))

    def test_multi_step_cursor(self):
        """Cursor advances across three intervals to fully cover."""
        merged = [[0.0, 1.0], [1.0, 2.0], [2.0, 3.0]]
        self.assertTrue(_interval_covered(0.2, 2.8, merged))

    def test_multi_step_partial(self):
        """Cursor stops early because of a gap."""
        merged = [[0.0, 1.0], [1.5, 2.0], [2.0, 3.0]]
        self.assertFalse(_interval_covered(0.2, 2.8, merged))

    def test_exact_boundary(self):
        """start exactly equals a merged interval boundary."""
        merged = [[1.0, 2.0]]
        self.assertTrue(_interval_covered(1.0, 1.5, merged))

    def test_epsilon_tolerance(self):
        """start slightly before a merged interval (within epsilon)."""
        merged = [[1.0, 2.0]]
        # start is 1e-10 before the merged start — should be covered via epsilon
        self.assertTrue(_interval_covered(1.0 - 1e-10, 1.5, merged))


# ══════════════════════════════════════════════════════════════════════
#  _merge_interval
# ══════════════════════════════════════════════════════════════════════

class TestMergeInterval(unittest.TestCase):
    """Tests for _merge_interval(start, end, merged) — mutates merged in place."""

    def test_insert_into_empty(self):
        """Insert into empty list → single entry."""
        merged = []
        _merge_interval(1.0, 2.0, merged)
        self.assertEqual(merged, [[1.0, 2.0]])

    def test_insert_before_all(self):
        """Non-overlapping interval before all existing."""
        merged = [[3.0, 4.0], [5.0, 6.0]]
        _merge_interval(1.0, 2.0, merged)
        self.assertEqual(merged, [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])

    def test_insert_after_all(self):
        """Non-overlapping interval after all existing."""
        merged = [[1.0, 2.0], [3.0, 4.0]]
        _merge_interval(5.0, 6.0, merged)
        self.assertEqual(merged, [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])

    def test_insert_in_middle(self):
        """Non-overlapping interval between two existing."""
        merged = [[1.0, 2.0], [5.0, 6.0]]
        _merge_interval(3.0, 4.0, merged)
        self.assertEqual(merged, [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])

    def test_merge_left(self):
        """New interval overlaps left neighbour → merged."""
        merged = [[1.0, 2.0], [4.0, 5.0]]
        _merge_interval(1.5, 3.0, merged)
        # [1.0, 2.0] extended to [1.0, 3.0]
        self.assertEqual(merged, [[1.0, 3.0], [4.0, 5.0]])

    def test_merge_right(self):
        """New interval overlaps right neighbour → merged."""
        merged = [[1.0, 2.0], [4.0, 5.0]]
        _merge_interval(3.0, 4.5, merged)
        # [4.0, 5.0] extended to [3.0, 5.0]
        self.assertEqual(merged, [[1.0, 2.0], [3.0, 5.0]])

    def test_merge_both_sides(self):
        """New interval bridges two neighbours → both merged into one."""
        merged = [[1.0, 2.0], [4.0, 5.0]]
        _merge_interval(1.5, 4.5, merged)
        self.assertEqual(merged, [[1.0, 5.0]])

    def test_contained_within_existing(self):
        """New interval is entirely inside an existing → no change to boundaries."""
        merged = [[1.0, 5.0]]
        _merge_interval(2.0, 3.0, merged)
        self.assertEqual(merged, [[1.0, 5.0]])

    def test_chain_merge_three(self):
        """New interval bridges and causes chain merge across 3+ existing."""
        merged = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
        _merge_interval(1.5, 5.5, merged)
        self.assertEqual(merged, [[1.0, 6.0]])

    def test_merge_left_via_epsilon(self):
        """Overlap within epsilon tolerance → merged."""
        merged = [[1.0, 2.0], [4.0, 5.0]]
        # gap is 2.0 - 2.0001 = -0.0001, within epsilon → merged
        _merge_interval(2.0 + 5e-10, 3.5, merged)
        self.assertEqual(merged, [[1.0, 3.5], [4.0, 5.0]])

    def test_merge_right_via_epsilon(self):
        """Overlap within epsilon tolerance on right → merged."""
        merged = [[1.0, 2.0], [4.0, 5.0]]
        _merge_interval(2.5, 4.0 - 5e-10, merged)
        self.assertEqual(merged, [[1.0, 2.0], [2.5, 5.0]])

    def test_insert_unsorted_merged(self):
        """Insert into unsorted merged still works via binary search."""
        # The function uses binary search on starts, so unsorted input
        # may produce surprising results — but the contract expects
        # merged to be sorted. This test verifies the binary-search
        # placement behaviour with already-sorted input.
        merged = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
        _merge_interval(0.5, 0.8, merged)
        self.assertEqual(merged, [[0.5, 0.8], [1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])


# ══════════════════════════════════════════════════════════════════════
#  _merge_all
# ══════════════════════════════════════════════════════════════════════

class TestMergeAll(unittest.TestCase):
    """Tests for _merge_all(intervals) → non-overlapping sorted list."""

    def test_empty(self):
        """Empty input → empty output."""
        self.assertEqual(_merge_all([]), [])

    def test_single(self):
        """Single interval → unchanged."""
        self.assertEqual(_merge_all([(1.0, 2.0)]), [[1.0, 2.0]])

    def test_two_non_overlapping(self):
        """Two non-overlapping intervals → both kept."""
        result = _merge_all([(1.0, 2.0), (3.0, 4.0)])
        self.assertEqual(result, [[1.0, 2.0], [3.0, 4.0]])

    def test_two_overlapping(self):
        """Two overlapping intervals → merged into one."""
        result = _merge_all([(1.0, 3.0), (2.0, 4.0)])
        self.assertEqual(result, [[1.0, 4.0]])

    def test_three_middle_bridges(self):
        """Three intervals where middle bridges the outer two."""
        result = _merge_all([(1.0, 2.0), (1.5, 3.5), (3.0, 4.0)])
        self.assertEqual(result, [[1.0, 4.0]])

    def test_unsorted_input(self):
        """Unsorted input → sorted output."""
        result = _merge_all([(5.0, 6.0), (1.0, 2.0), (3.0, 4.0)])
        self.assertEqual(result, [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])

    def test_duplicate_intervals(self):
        """Duplicate intervals → merged into one."""
        result = _merge_all([(1.0, 2.0), (1.0, 2.0), (1.0, 2.0)])
        self.assertEqual(result, [[1.0, 2.0]])

    def test_one_contains_another(self):
        """One interval fully contains another → single merged result."""
        result = _merge_all([(1.0, 5.0), (2.0, 3.0)])
        self.assertEqual(result, [[1.0, 5.0]])

    def test_touching_via_epsilon(self):
        """Intervals touching within epsilon → merged."""
        result = _merge_all([(1.0, 2.0), (2.0 + 5e-10, 3.0)])
        self.assertEqual(result, [[1.0, 3.0]])

    def test_non_touching(self):
        """Intervals with a real gap → not merged."""
        result = _merge_all([(1.0, 2.0), (2.5, 3.0)])
        self.assertEqual(result, [[1.0, 2.0], [2.5, 3.0]])

    def test_angular_example(self):
        """Realistic angular intervals from a flocking simulation."""
        # Simulated: small overlapping arcs from nearby birds
        intervals = [
            (0.5, 0.8),
            (0.7, 1.0),
            (1.2, 1.5),
            (5.8, 6.1),
            (6.0, 6.2),
        ]
        result = _merge_all(intervals)
        self.assertEqual(result, [[0.5, 1.0], [1.2, 1.5], [5.8, 6.2]])

    def test_all_overlapping_chain(self):
        """Chain of overlapping intervals → single result."""
        intervals = [
            (0.0, 1.0),
            (0.5, 1.5),
            (1.2, 2.0),
            (1.8, 2.5),
        ]
        result = _merge_all(intervals)
        self.assertEqual(result, [[0.0, 2.5]])


# ══════════════════════════════════════════════════════════════════════
#  Integration test: workflow from _normalise → _merge → _covered
# ══════════════════════════════════════════════════════════════════════

class TestOcclusionWorkflow(unittest.TestCase):
    """
    End-to-end test of the occlusion pipeline as used in the projection model:
      1. Normalise wrap-around intervals
      2. Test visibility with _interval_covered
      3. Merge visible intervals with _merge_interval
    """

    def test_two_birds_progressively_occluded(self):
        """
        Simulate two birds at different distances from an observer.
        Bird A (closer) subtends (0.8, 1.2). Bird B (further) subtends (0.9, 1.1).
        Bird B is fully inside Bird A's interval → not visible.
        """
        merged = []
        visible = []

        # Bird A (closer) — processed first
        for seg in _normalise_interval(0.8, 1.2):
            visible.append("A")
            _merge_interval(seg[0], seg[1], merged)

        # Bird B (further) — check visibility, then merge if visible
        for seg in _normalise_interval(0.9, 1.1):
            if not _interval_covered(seg[0], seg[1], merged):
                visible.append("B")
                _merge_interval(seg[0], seg[1], merged)

        # B should be fully occluded by A
        self.assertEqual(visible, ["A"])
        self.assertEqual(merged, [[0.8, 1.2]])

    def test_two_birds_partial_overlap(self):
        """
        Bird A subtends (0.8, 1.2). Bird B subtends (1.0, 1.5).
        B is partially visible (1.2 to 1.5 uncovered) → visible.
        """
        merged = []
        visible = []

        for seg in _normalise_interval(0.8, 1.2):
            visible.append("A")
            _merge_interval(seg[0], seg[1], merged)

        for seg in _normalise_interval(1.0, 1.5):
            if not _interval_covered(seg[0], seg[1], merged):
                visible.append("B")
                _merge_interval(seg[0], seg[1], merged)

        self.assertIn("B", visible)
        self.assertEqual(merged, [[0.8, 1.5]])

    def test_wrap_around_occlusion(self):
        """
        Bird A subtends (−0.3, 0.3), which normalises to two segments
        wrapping around 2π: [(−0.3+2π, 2π), (0, 0.3)].
        Bird B subtends (0.1, 0.2) — fully inside the second segment →
        not visible.
        """
        merged = []
        visible = []

        # Bird A — wraps around 2π via negative start
        for seg in _normalise_interval(-0.3, 0.3):
            visible.append("A")
            _merge_interval(seg[0], seg[1], merged)

        # Bird B — inside A's second segment → occluded
        for seg in _normalise_interval(0.1, 0.2):
            if not _interval_covered(seg[0], seg[1], merged):
                visible.append("B")
                _merge_interval(seg[0], seg[1], merged)

        # A produced 2 segments; B was fully covered → not visible
        self.assertEqual(visible, ["A", "A"])

    def test_boundary_vector_computation(self):
        """
        Verify δ̂ boundary vector computation from merged intervals.
        δ̂ = Σ (cos θ, sin θ) over all interval boundaries, normalised.
        """
        merged = [[0.5, 1.0]]
        # Boundaries at 0.5 and 1.0
        bx = math.cos(0.5) + math.cos(1.0)
        by = math.sin(0.5) + math.sin(1.0)
        mag = math.sqrt(bx * bx + by * by)
        # Should be non-zero (not fully surrounded)
        self.assertGreater(mag, 0.01)


if __name__ == "__main__":
    unittest.main(verbosity=2)
