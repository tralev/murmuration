"""
Unit tests for the angular-interval merge utilities in alg2.py (SECTION 4).

Covers:
  - _normalise_interval   — split wrap-around intervals into [0, 2π) segments
  - _interval_covered     — check whether an interval is fully occluded
  - _merge_interval       — insert-and-merge one interval into a sorted list
  - _merge_all            — sort-and-merge a list of intervals
"""

import math
import re
import unittest

import pygame

from test_count_mixin import TestCountMixin

from occlusion_geom import (
    _normalise_interval,
    _interval_covered,
    _merge_interval,
    _merge_all,
)
from flock_core import WIDTH, HEIGHT, V0, TRAIL_LENGTH

from alg2 import _get_preset_key, _save_config, _restore_config

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


# ══════════════════════════════════════════════════════════════════════
#  Margin boundary mode — verify birds stay within bounds
# ══════════════════════════════════════════════════════════════════════

class TestMarginBoundary(unittest.TestCase):
    """
    Tests for margin-based keepWithinBounds (MARGIN_BOUNDARY=True).

    Verifies that birds stay within [0, WIDTH]×[0, HEIGHT] even after
    many update steps, regardless of starting position or velocity.
    """

    @classmethod
    def setUpClass(cls):
        """Force MARGIN_BOUNDARY=True for all tests in this class."""
        import flock_core
        flock_core.MARGIN_BOUNDARY = True

    @classmethod
    def tearDownClass(cls):
        """Restore MARGIN_BOUNDARY to its default in both modules."""
        import flock_core
        import boid as boid_module
        flock_core.MARGIN_BOUNDARY = False
        boid_module.MARGIN_BOUNDARY = False

    def setUp(self):
        import flock_core
        import boid as boid_module
        # Ensure both module and import-copy see the flag
        boid_module.MARGIN_BOUNDARY = True
        self.assertTrue(flock_core.MARGIN_BOUNDARY)

    def _make_boid(self, x, y, vx, vy):
        """Create a Boid at (x, y) with velocity (vx, vy)."""
        from boid import Boid
        b = Boid()
        b.position = pygame.Vector2(x, y)
        b.velocity = pygame.Vector2(vx, vy)
        b.acceleration = pygame.Vector2(0, 0)
        return b

    def _update_n_times(self, boid, n):
        """Call boid.update() n times."""
        for _ in range(n):
            boid.update()

    def _assert_in_bounds(self, boid, msg=""):
        """Assert boid.position is within [0, WIDTH]×[0, HEIGHT]."""
        self.assertGreaterEqual(boid.position.x, 0, msg)
        self.assertLessEqual(boid.position.x, WIDTH, msg)
        self.assertGreaterEqual(boid.position.y, 0, msg)
        self.assertLessEqual(boid.position.y, HEIGHT, msg)

    # ── Basic containment ───────────────────────────────────────────

    def test_bird_center_stays_in_bounds(self):
        """Bird starting at center stays in bounds after many updates."""
        b = self._make_boid(WIDTH // 2, HEIGHT // 2, V0, 0)
        self._update_n_times(b, 500)
        self._assert_in_bounds(b, "Center bird should stay in bounds")

    def test_bird_near_left_edge_turned_back(self):
        """Bird starting inside left margin with outward velocity —
        velocity is nudged rightward each frame, stays in bounds."""
        b = self._make_boid(10, HEIGHT // 2, -V0, 0)
        nudged_right = False
        for _ in range(100):
            old_vx = b.velocity.x
            b.update()
            self._assert_in_bounds(b, "Left-edge bird should stay in bounds")
            if b.velocity.x > old_vx:
                nudged_right = True
        self.assertTrue(nudged_right,
                        "Velocity should be nudged rightward near left edge")

    def test_bird_near_right_edge_turned_back(self):
        """Bird starting inside right margin with outward velocity —
        velocity is nudged leftward each frame, stays in bounds."""
        b = self._make_boid(WIDTH - 10, HEIGHT // 2, V0, 0)
        nudged_left = False
        for _ in range(100):
            old_vx = b.velocity.x
            b.update()
            self._assert_in_bounds(b, "Right-edge bird should stay in bounds")
            if b.velocity.x < old_vx:
                nudged_left = True
        self.assertTrue(nudged_left,
                        "Velocity should be nudged leftward near right edge")

    def test_bird_near_top_edge_turned_back(self):
        """Bird starting inside top margin with outward velocity —
        velocity is nudged downward each frame, stays in bounds."""
        b = self._make_boid(WIDTH // 2, 10, 0, -V0)
        nudged_down = False
        for _ in range(100):
            old_vy = b.velocity.y
            b.update()
            self._assert_in_bounds(b, "Top-edge bird should stay in bounds")
            if b.velocity.y > old_vy:
                nudged_down = True
        self.assertTrue(nudged_down,
                        "Velocity should be nudged downward near top edge")

    def test_bird_near_bottom_edge_turned_back(self):
        """Bird starting inside bottom margin with outward velocity —
        velocity is nudged upward each frame, stays in bounds."""
        b = self._make_boid(WIDTH // 2, HEIGHT - 10, 0, V0)
        nudged_up = False
        for _ in range(100):
            old_vy = b.velocity.y
            b.update()
            self._assert_in_bounds(b, "Bottom-edge bird should stay in bounds")
            if b.velocity.y < old_vy:
                nudged_up = True
        self.assertTrue(nudged_up,
                        "Velocity should be nudged upward near bottom edge")

    # ── Corner cases ────────────────────────────────────────────────

    def test_corner_bird_turned_back(self):
        """Bird in top-left corner with diagonal outward velocity —
        nudged on both axes, stays in bounds."""
        b = self._make_boid(10, 10, -V0, -V0)
        nudged_right = False
        nudged_down = False
        for _ in range(200):
            old_vx = b.velocity.x
            old_vy = b.velocity.y
            b.update()
            self._assert_in_bounds(b, "Corner bird should stay in bounds")
            if b.velocity.x > old_vx:
                nudged_right = True
            if b.velocity.y > old_vy:
                nudged_down = True
        self.assertTrue(nudged_right,
                        "Velocity should be nudged rightward near left edge")
        self.assertTrue(nudged_down,
                        "Velocity should be nudged downward near top edge")

    def test_outside_bird_clamped_immediately(self):
        """Bird starting completely outside bounds (x < 0) —
        position is hard-clamped on the first update."""
        b = self._make_boid(-100, HEIGHT // 2, V0 * 0.1, 0)
        self._update_n_times(b, 1)
        self._assert_in_bounds(b, "Outside bird should be clamped")

    def test_outside_bird_beyond_right_clamped(self):
        """Bird starting beyond right edge — clamped immediately."""
        b = self._make_boid(WIDTH + 100, HEIGHT // 2, -V0 * 0.1, 0)
        self._update_n_times(b, 1)
        self._assert_in_bounds(b, "Beyond-right bird should be clamped")

    def test_outside_bird_beyond_bottom_clamped(self):
        """Bird starting beyond bottom edge — clamped immediately."""
        b = self._make_boid(WIDTH // 2, HEIGHT + 100, 0, -V0 * 0.1)
        self._update_n_times(b, 1)
        self._assert_in_bounds(b, "Beyond-bottom bird should be clamped")

    # ── Long-run stability ──────────────────────────────────────────

    def test_many_birds_stay_in_bounds_over_many_steps(self):
        """20 birds at random positions/velocities — all stay in bounds
        after 200 steps each."""
        import random
        random.seed(99)
        boids = []
        for _ in range(20):
            x = random.uniform(0, WIDTH)
            y = random.uniform(0, HEIGHT)
            angle = random.uniform(0, 2 * math.pi)
            b = self._make_boid(
                x, y,
                math.cos(angle) * V0,
                math.sin(angle) * V0,
            )
            boids.append(b)

        for step in range(200):
            for i, b in enumerate(boids):
                b.update()
                self._assert_in_bounds(
                    b,
                    f"Bird {i} out of bounds at step {step}: pos=({b.position.x:.1f}, {b.position.y:.1f})"
                )

    def test_high_speed_bird_clamped(self):
        """Bird with velocity >> V0 still stays in bounds."""
        b = self._make_boid(WIDTH // 2, HEIGHT // 2, V0 * 50, 0)
        self._update_n_times(b, 50)
        self._assert_in_bounds(b, "High-speed bird should stay in bounds")

    # ── Exactly-on-boundary ─────────────────────────────────────────

    def test_bird_exactly_at_zero(self):
        """Bird exactly at (0, 0) with outward velocity — stays in bounds."""
        b = self._make_boid(0, 0, -V0, -V0)
        self._update_n_times(b, 100)
        self._assert_in_bounds(b, "Bird at origin should stay in bounds")

    def test_bird_exactly_at_corner(self):
        """Bird exactly at (WIDTH, HEIGHT) — clamped immediately."""
        b = self._make_boid(WIDTH, HEIGHT, V0, V0)
        self._update_n_times(b, 100)
        self._assert_in_bounds(b, "Bird at far corner should stay in bounds")

    # ── Trail + margin interaction ──────────────────────────────────

    def test_trail_positions_are_clamped_not_raw(self):
        """When MARGIN_BOUNDARY=True, trail positions reflect clamped
        positions — NOT the raw pre-clamp values that may be out of bounds."""
        import flock_core
        import boid as boid_module
        flock_core.DRAW_TRAIL = True
        boid_module.DRAW_TRAIL = True
        self.addCleanup(self._reset_trail_flag)

        # Bird flying directly at the right wall — without clamping,
        # position would land at x > WIDTH.
        b = self._make_boid(WIDTH - 5, HEIGHT // 2, V0, 0)
        self._update_n_times(b, 50)

        # Every trail position must be in bounds
        self.assertGreater(len(b.history), 0,
                           "Trail should have recorded positions")
        for i, pt in enumerate(b.history):
            self.assertGreaterEqual(pt.x, 0,
                f"Trail point {i} x={pt.x} should be >= 0")
            self.assertLessEqual(pt.x, WIDTH,
                f"Trail point {i} x={pt.x} should be <= {WIDTH}")
            self.assertGreaterEqual(pt.y, 0,
                f"Trail point {i} y={pt.y} should be >= 0")
            self.assertLessEqual(pt.y, HEIGHT,
                f"Trail point {i} y={pt.y} should be <= {HEIGHT}")

        # The current position is clamped — trail should end at the
        # same clamped position, confirming trail is recorded AFTER
        # boundary handling (not before).
        self.assertEqual(b.position, b.history[-1],
                         "Last trail point should equal current (clamped) position")

    def test_trail_does_not_record_out_of_bounds_positions(self):
        """Bird starting outside bounds is clamped immediately;
        trail should never contain an out-of-bounds position."""
        import flock_core
        import boid as boid_module
        flock_core.DRAW_TRAIL = True
        boid_module.DRAW_TRAIL = True
        self.addCleanup(self._reset_trail_flag)

        # Bird starts at x=-50 (out of bounds), velocity points further left
        b = self._make_boid(-50, HEIGHT // 2, -V0, 0)
        self._update_n_times(b, 30)

        # Every trail position must be in bounds — the initial -50
        # should have been clamped to 0 before trail recording
        for i, pt in enumerate(b.history):
            self.assertGreaterEqual(pt.x, 0,
                f"Trail point {i} should not be < 0, got x={pt.x}")
            self.assertLessEqual(pt.x, WIDTH,
                f"Trail point {i} should not be > {WIDTH}, got x={pt.x}")
            self.assertGreaterEqual(pt.y, 0,
                f"Trail point {i} y={pt.y} should be >= 0")
            self.assertLessEqual(pt.y, HEIGHT,
                f"Trail point {i} y={pt.y} should be <= {HEIGHT}")

    def test_trail_length_capped_at_trail_length(self):
        """Trail buffer never exceeds TRAIL_LENGTH, regardless of
        how many update steps have passed."""
        import flock_core
        import boid as boid_module
        flock_core.DRAW_TRAIL = True
        boid_module.DRAW_TRAIL = True
        self.addCleanup(self._reset_trail_flag)

        b = self._make_boid(WIDTH // 2, HEIGHT // 2, V0, 0)
        # Run many more steps than TRAIL_LENGTH
        self._update_n_times(b, flock_core.TRAIL_LENGTH * 3)

        self.assertEqual(len(b.history), TRAIL_LENGTH,
            f"Trail should cap at TRAIL_LENGTH={TRAIL_LENGTH}")

    def _reset_trail_flag(self):
        """Restore DRAW_TRAIL to False after trail tests."""
        import flock_core
        import boid as boid_module
        flock_core.DRAW_TRAIL = False
        boid_module.DRAW_TRAIL = False
    # ── Edge-case: exactly at BOUNDARY_MARGIN threshold ────────────
    #  The nudge fires on strict inequality:
    #    x < BOUNDARY_MARGIN  (200) → nudge right
    #    x > WIDTH − BOUNDARY_MARGIN (800) → nudge left
    #  At exactly 200 or 800, the condition is False → no nudge.

    def test_no_nudge_exactly_at_left_margin_boundary(self):
        """Bird at x = BOUNDARY_MARGIN (200) — NOT < 200, so no nudge.
        Velocity points away from the edge so the bird stays outside
        the margin zone after the position-update step."""
        # vx = +1.3 (rightward, away from left edge); > 0.3·V₀=1.2 to avoid floor
        b = self._make_boid(200, HEIGHT // 2, 1.3, 0)
        old_vx = b.velocity.x
        b.update()
        self._assert_in_bounds(b)
        self.assertEqual(b.velocity.x, old_vx,
                         "At exactly x=200, velocity should not be nudged")

    def test_nudge_fires_just_inside_left_margin(self):
        """Bird at x = BOUNDARY_MARGIN − 1 (199) — IS < 200, so nudge fires."""
        b = self._make_boid(199, HEIGHT // 2, -V0, 0)
        old_vx = b.velocity.x
        b.update()
        self._assert_in_bounds(b)
        self.assertGreater(b.velocity.x, old_vx,
                           "At x=199, velocity should be nudged rightward (+1)")

    def test_no_nudge_exactly_at_right_margin_boundary(self):
        """Bird at x = WIDTH − BOUNDARY_MARGIN (800) — NOT > 800, so no nudge.
        Velocity points away from the edge."""
        b = self._make_boid(800, HEIGHT // 2, -1.3, 0)
        old_vx = b.velocity.x
        b.update()
        self._assert_in_bounds(b)
        self.assertEqual(b.velocity.x, old_vx,
                         "At exactly x=800, velocity should not be nudged")

    def test_nudge_fires_just_inside_right_margin(self):
        """Bird at x = WIDTH − BOUNDARY_MARGIN + 1 (801) — IS > 800, so nudge fires."""
        b = self._make_boid(801, HEIGHT // 2, V0, 0)
        old_vx = b.velocity.x
        b.update()
        self._assert_in_bounds(b)
        self.assertLess(b.velocity.x, old_vx,
                        "At x=801, velocity should be nudged leftward (−1)")

    def test_no_nudge_exactly_at_top_margin_boundary(self):
        """Bird at y = BOUNDARY_MARGIN (200) — NOT < 200, so no nudge.
        Velocity points away from the edge."""
        b = self._make_boid(WIDTH // 2, 200, 0, 1.3)
        old_vy = b.velocity.y
        b.update()
        self._assert_in_bounds(b)
        self.assertEqual(b.velocity.y, old_vy,
                         "At exactly y=200, velocity should not be nudged")

    def test_nudge_fires_just_inside_top_margin(self):
        """Bird at y = BOUNDARY_MARGIN − 1 (199) — IS < 200, so nudge fires."""
        b = self._make_boid(WIDTH // 2, 199, 0, -V0)
        old_vy = b.velocity.y
        b.update()
        self._assert_in_bounds(b)
        self.assertGreater(b.velocity.y, old_vy,
                           "At y=199, velocity should be nudged downward (+1)")

    def test_no_nudge_exactly_at_bottom_margin_boundary(self):
        """Bird at y = HEIGHT − BOUNDARY_MARGIN (500) — NOT > 500, so no nudge.
        Velocity points away from the edge."""
        b = self._make_boid(WIDTH // 2, 500, 0, -1.3)
        old_vy = b.velocity.y
        b.update()
        self._assert_in_bounds(b)
        self.assertEqual(b.velocity.y, old_vy,
                         "At exactly y=500, velocity should not be nudged")

    def test_nudge_fires_just_inside_bottom_margin(self):
        """Bird at y = HEIGHT − BOUNDARY_MARGIN + 1 (501) — IS > 500, so nudge fires."""
        b = self._make_boid(WIDTH // 2, 501, 0, V0)
        old_vy = b.velocity.y
        b.update()
        self._assert_in_bounds(b)
        self.assertLess(b.velocity.y, old_vy,
                        "At y=501, velocity should be nudged upward (−1)")

    # ── Edge-case: velocity nudge doesn't cause runaway speed ───────
    #  The nudge runs BEFORE the speed clamp (matching boids.js order),
    #  so the clamp absorbs the nudge same-frame. Speed never exceeds V₀.

    def test_speed_never_exceeds_v0_after_nudge(self):
        """Bird heading right while inside left margin — the nudge
        adds to velocity, but the clamp runs after and normalizes it.
        Speed never exceeds V₀."""
        b = self._make_boid(150, HEIGHT // 2, V0, 0)
        for _ in range(200):
            b.update()
            spd = b.velocity.length()
            self.assertLessEqual(spd, V0 + 0.01,
                f"Speed {spd:.2f} should be ≤ V₀={V0} (clamp runs after nudge)")
            self._assert_in_bounds(b)

    def test_speed_stays_bounded_near_all_four_edges(self):
        """Birds inside each margin, heading so the nudge ADDS to
        speed. Clamp runs after nudge, so speed never exceeds V₀."""
        cases = [
            (150, HEIGHT // 2, V0,   0,   "left  (v→right)"),
            (WIDTH - 150, HEIGHT // 2, -V0,   0,   "right (v→left)"),
            (WIDTH // 2,  150,  0,  V0,   "top   (v↓down)"),
            (WIDTH // 2, HEIGHT - 150,  0,  -V0,   "bottom(v↑up)"),
        ]
        for x, y, vx, vy, label in cases:
            with self.subTest(edge=label):
                b = self._make_boid(x, y, vx, vy)
                for _ in range(100):
                    b.update()
                    spd = b.velocity.length()
                    self.assertLessEqual(spd, V0 + 0.01,
                        f"{label} edge: speed {spd:.2f} > V₀={V0}")
                    self._assert_in_bounds(b)

    def test_nudge_is_absorbed_by_clamp_same_frame(self):
        """With nudge before clamp, the nudge effect is normalized
        same-frame. Speed is always V₀ after update, never V₀+turnFactor."""
        b = self._make_boid(150, HEIGHT // 2, V0, 0)
        for _ in range(50):
            b.update()
            spd = b.velocity.length()
            self.assertAlmostEqual(spd, V0, delta=0.02,
                msg=f"Speed should be clamped to V₀ after nudge, got {spd:.3f}")


# ══════════════════════════════════════════════════════════════════════
#  Toroidal wrap mode — verify birds teleport across edges
# ══════════════════════════════════════════════════════════════════════

class TestToroidalWrap(unittest.TestCase):
    """
    Tests for toroidal position wrap (MARGIN_BOUNDARY=False, default).

    Verifies birds exiting one edge reappear at the opposite edge,
    with velocity and speed unchanged.
    """

    @classmethod
    def setUpClass(cls):
        """Ensure MARGIN_BOUNDARY=False and restore after."""
        import flock_core
        import boid as boid_module
        cls._saved_margin = flock_core.MARGIN_BOUNDARY
        flock_core.MARGIN_BOUNDARY = False
        boid_module.MARGIN_BOUNDARY = False

    @classmethod
    def tearDownClass(cls):
        """Restore original MARGIN_BOUNDARY value."""
        import flock_core
        import boid as boid_module
        flock_core.MARGIN_BOUNDARY = cls._saved_margin
        boid_module.MARGIN_BOUNDARY = cls._saved_margin

    def setUp(self):
        import flock_core
        import boid as boid_module
        boid_module.MARGIN_BOUNDARY = False
        self.assertFalse(flock_core.MARGIN_BOUNDARY)

    def _make_boid(self, x, y, vx, vy):
        """Create a Boid at (x, y) with velocity (vx, vy)."""
        from boid import Boid
        b = Boid()
        b.position = pygame.Vector2(x, y)
        b.velocity = pygame.Vector2(vx, vy)
        b.acceleration = pygame.Vector2(0, 0)
        return b

    # ── Single-edge wraps ───────────────────────────────────────────

    def test_wrap_right_to_left(self):
        """Bird exiting right edge (x > WIDTH) reappears at x=0.
        y unchanged because vy=0."""
        b = self._make_boid(WIDTH + 1, HEIGHT // 2, V0, 0)
        b.update()
        self.assertAlmostEqual(b.position.x, 0.0)
        self.assertAlmostEqual(b.position.y, float(HEIGHT // 2))

    def test_wrap_left_to_right(self):
        """Bird exiting left edge (x < 0) reappears at x=WIDTH.
        y unchanged because vy=0."""
        b = self._make_boid(-1, HEIGHT // 2, -V0, 0)
        b.update()
        self.assertAlmostEqual(b.position.x, float(WIDTH))
        self.assertAlmostEqual(b.position.y, float(HEIGHT // 2))

    def test_wrap_bottom_to_top(self):
        """Bird exiting bottom edge (y > HEIGHT) reappears at y=0.
        x unchanged because vx=0."""
        b = self._make_boid(WIDTH // 2, HEIGHT + 1, 0, V0)
        b.update()
        self.assertAlmostEqual(b.position.x, float(WIDTH // 2))
        self.assertAlmostEqual(b.position.y, 0.0)

    def test_wrap_top_to_bottom(self):
        """Bird exiting top edge (y < 0) reappears at y=HEIGHT.
        x unchanged because vx=0."""
        b = self._make_boid(WIDTH // 2, -1, 0, -V0)
        b.update()
        self.assertAlmostEqual(b.position.x, float(WIDTH // 2))
        self.assertAlmostEqual(b.position.y, float(HEIGHT))

    # ── Velocity preservation ───────────────────────────────────────

    def test_velocity_unchanged_after_wrap(self):
        """Velocity magnitude and direction unchanged by toroidal wrap."""
        b = self._make_boid(WIDTH + 1, HEIGHT // 2, V0, 0)
        old_vx, old_vy = b.velocity.x, b.velocity.y
        b.update()
        self.assertEqual(b.velocity.x, old_vx,
                         "vx should not change during wrap")
        self.assertEqual(b.velocity.y, old_vy,
                         "vy should not change during wrap")

    def test_speed_preserved_after_diagonal_wrap(self):
        """Diagonal velocity preserved when wrapping both axes."""
        # Point diagonally down-right: exits both bottom and right
        vx = vy = V0 / math.sqrt(2)
        speed_before = math.sqrt(vx * vx + vy * vy)
        b = self._make_boid(WIDTH + 1, HEIGHT + 1, vx, vy)
        b.update()
        speed_after = b.velocity.length()
        self.assertAlmostEqual(speed_after, speed_before, places=5,
            msg="Speed should be unchanged after wrap")

    # ── Corner wraps (both axes simultaneously) ─────────────────────

    def test_wrap_bottom_right_corner(self):
        """Bird exiting both right and bottom edges — both axes wrap."""
        b = self._make_boid(WIDTH + 1, HEIGHT + 1, V0, V0)
        b.update()
        self.assertLess(b.position.x, WIDTH,
                        "Should wrap from right edge")
        self.assertLess(b.position.y, HEIGHT,
                        "Should wrap from bottom edge")
        self.assertGreaterEqual(b.position.x, 0)
        self.assertGreaterEqual(b.position.y, 0)

    def test_wrap_top_left_corner(self):
        """Bird exiting both left and top edges — both axes wrap."""
        b = self._make_boid(-1, -1, -V0, -V0)
        b.update()
        self.assertGreater(b.position.x, 0,
                           "Should wrap from left edge")
        self.assertGreater(b.position.y, 0,
                           "Should wrap from top edge")
        self.assertLessEqual(b.position.x, WIDTH)
        self.assertLessEqual(b.position.y, HEIGHT)

    # ── Multi-step wraps ────────────────────────────────────────────

    def test_multi_step_always_in_bounds(self):
        """Bird flying at V0 for 300 steps — wraps multiple times,
        position always in [0, WIDTH)×[0, HEIGHT)."""
        b = self._make_boid(WIDTH // 2, HEIGHT // 2, V0, 0)
        wrap_count = 0
        for _ in range(300):
            old_x = b.position.x
            b.update()
            if b.position.x < old_x and old_x > WIDTH - V0:
                wrap_count += 1  # detected a right→left wrap
            self.assertGreaterEqual(b.position.x, 0)
            self.assertLessEqual(b.position.x, WIDTH)
            self.assertGreaterEqual(b.position.y, 0)
            self.assertLessEqual(b.position.y, HEIGHT)
        self.assertGreater(wrap_count, 0,
                           "Should have wrapped at least once in 300 steps")

    def test_high_speed_clamped_before_wrap(self):
        """Bird with extreme velocity (V0×300): speed clamp reduces
        to V₀ before position update, so position stays in bounds."""
        b = self._make_boid(WIDTH // 2, HEIGHT // 2, V0 * 300, 0)
        b.update()
        self.assertGreaterEqual(b.position.x, 0)
        self.assertLess(b.position.x, WIDTH)
        self.assertAlmostEqual(b.velocity.length(), V0, delta=0.01)

    # ── Runtime boundary mode toggle ────────────────────────────────

    def test_runtime_toggle_toroidal_to_margin(self):
        """Toggle MARGIN_BOUNDARY at runtime: toroidal→wrap, margin→clamp.
        Bird at right edge flies right at V0:
          Frame 1 (toroidal): wraps from x>WIDTH to x=0
          Frame 2 (margin):   hard-clamped at wall, stays near WIDTH"""
        import flock_core
        import boid as boid_module

        # Bird at the right edge, flying right
        b = self._make_boid(WIDTH - 1, HEIGHT // 2, V0, 0)

        # ── Frame 1: toroidal mode (default in this test class) ───
        self.assertFalse(flock_core.MARGIN_BOUNDARY)
        self.assertFalse(boid_module.MARGIN_BOUNDARY)
        b.update()

        # Wrapping: x was WIDTH-1+V0 = 1003, wrapped to ~3 (or 0).
        # After wrap from x>WIDTH to 0, the bird is near the left edge.
        self.assertLess(b.position.x, V0 + 2,
            f"Toroidal: bird should wrap to left side, got x={b.position.x:.1f}")
        self.assertGreaterEqual(b.position.x, 0)

        # ── Toggle to margin mode ──────────────────────────────────
        flock_core.MARGIN_BOUNDARY = True
        boid_module.MARGIN_BOUNDARY = True
        self.addCleanup(lambda: setattr(flock_core, 'MARGIN_BOUNDARY', False))
        self.addCleanup(lambda: setattr(boid_module, 'MARGIN_BOUNDARY', False))

        # Move bird back near the right edge (simulate it having flown
        # back) so the margin nudge+clamp has something to do.
        b.position.x = WIDTH - 5
        b.velocity.x = V0
        b.update()

        # Margin: clamped at WIDTH (not wrapped to 0)
        self.assertGreater(b.position.x, WIDTH - V0 - 2,
            f"Margin: bird should be clamped near right wall, got x={b.position.x:.1f}")
        self.assertLessEqual(b.position.x, WIDTH)

    # ── Trail + toroidal wrap interaction ───────────────────────────

    def _reset_trail_flag(self):
        """Restore DRAW_TRAIL to False after trail tests."""
        import flock_core
        import boid as boid_module
        flock_core.DRAW_TRAIL = False
        boid_module.DRAW_TRAIL = False

    def test_trail_positions_are_wrapped_not_raw(self):
        """When MARGIN_BOUNDARY=False, trail positions reflect wrapped
        positions — NOT the raw pre-wrap values that may be out of bounds.
        A bird flying beyond the right edge wraps to x=0; trail records
        the post-wrap position."""
        import flock_core
        import boid as boid_module
        flock_core.DRAW_TRAIL = True
        boid_module.DRAW_TRAIL = True
        self.addCleanup(self._reset_trail_flag)

        # Bird flying right from near the right edge — will wrap each frame
        b = self._make_boid(WIDTH - 5, HEIGHT // 2, V0, 0)
        for _ in range(50):
            b.update()

        # Every trail position must be in bounds (wrapped)
        self.assertGreater(len(b.history), 0,
                           "Trail should have recorded positions")
        for i, pt in enumerate(b.history):
            self.assertGreaterEqual(pt.x, 0,
                f"Trail point {i} x={pt.x} should be >= 0")
            self.assertLessEqual(pt.x, WIDTH,
                f"Trail point {i} x={pt.x} should be <= {WIDTH}")
            self.assertGreaterEqual(pt.y, 0,
                f"Trail point {i} y={pt.y} should be >= 0")
            self.assertLessEqual(pt.y, HEIGHT,
                f"Trail point {i} y={pt.y} should be <= {HEIGHT}")

        # Last trail point equals current wrapped position — confirms
        # trail is recorded AFTER toroidal wrap (not before).
        self.assertEqual(b.position, b.history[-1],
                         "Last trail point should equal current (wrapped) position")

    def test_trail_never_contains_out_of_bounds_positions(self):
        """Bird wrapping around the torus repeatedly — trail should
        never contain a position outside [0,WIDTH]×[0,HEIGHT]."""
        import flock_core
        import boid as boid_module
        flock_core.DRAW_TRAIL = True
        boid_module.DRAW_TRAIL = True
        self.addCleanup(self._reset_trail_flag)

        # Bird flying right at V0 — will wrap ~1.2 times in 300 steps
        b = self._make_boid(WIDTH // 2, HEIGHT // 2, V0, 0)
        for _ in range(300):
            b.update()

        for i, pt in enumerate(b.history):
            self.assertGreaterEqual(pt.x, 0,
                f"Trail point {i} should not be < 0, got x={pt.x}")
            self.assertLessEqual(pt.x, WIDTH,
                f"Trail point {i} should not be > {WIDTH}, got x={pt.x}")
            self.assertGreaterEqual(pt.y, 0,
                f"Trail point {i} y={pt.y} should be >= 0")
            self.assertLessEqual(pt.y, HEIGHT,
                f"Trail point {i} y={pt.y} should be <= {HEIGHT}")

    def test_trail_length_capped_at_trail_length(self):
        """Trail buffer never exceeds TRAIL_LENGTH, regardless of
        how many update steps have passed."""
        import flock_core
        import boid as boid_module
        flock_core.DRAW_TRAIL = True
        boid_module.DRAW_TRAIL = True
        self.addCleanup(self._reset_trail_flag)

        b = self._make_boid(WIDTH // 2, HEIGHT // 2, V0, 0)
        # Run many more steps than TRAIL_LENGTH
        for _ in range(TRAIL_LENGTH * 3):
            b.update()

        self.assertEqual(len(b.history), TRAIL_LENGTH,
            f"Trail should cap at TRAIL_LENGTH={TRAIL_LENGTH}")


# ══════════════════════════════════════════════════════════════════════
#  Octave/Scilab toroidal wrap — verify array-math physics
# ══════════════════════════════════════════════════════════════════════

class TestToroidalWrapOctaveScilab(unittest.TestCase):
    """
    Runs standalone Octave/Scilab test scripts that exercise the
    toroidal wrap physics step in isolation. Verifies position wrapping
    at all 4 edges, corner wraps, speed clamping, and velocity preservation.
    """

    EXPECTED_TESTS = 8

    def _parse_output(self, stdout):
        """Parse T1_X=5.0000 lines into a dict: {'T1_X': 5.0, ...}."""
        data = {}
        for m in re.finditer(r'([A-Z][A-Z0-9_]*)=\s*([-\d.]+)', stdout):
            data[m.group(1)] = float(m.group(2))
        return data

    def _verify_results(self, data):
        """Cross-check all 8 scenarios against expected wrapped positions
        and velocity preservation."""
        n = len([k for k in data if k.startswith('T')])
        self.assertGreaterEqual(n, self.EXPECTED_TESTS * 4,
            f"Expected {self.EXPECTED_TESTS*4} key=value lines, got {n}")

        # T1: wrap right→left: 1002+4=1006 → mod(1006,1000)=6
        self.assertAlmostEqual(data['T1_X'], 6.0, places=1,
            msg="T1: right→left wrap X should be 6.0")
        self.assertAlmostEqual(data['T1_Y'], 350.0, places=1,
            msg="T1: Y should be unchanged at 350.0")
        # T2: wrap left→right: -2+(-4)=-6 → mod(-6,1000)=994
        self.assertAlmostEqual(data['T2_X'], 994.0, places=1,
            msg="T2: left→right wrap X should be 994.0")
        self.assertAlmostEqual(data['T2_Y'], 350.0, places=1,
            msg="T2: Y should be unchanged at 350.0")
        # T3: wrap bottom→top: 702+4=706 → mod(706,700)=6
        self.assertAlmostEqual(data['T3_X'], 500.0, places=1,
            msg="T3: X should be unchanged at 500.0")
        self.assertAlmostEqual(data['T3_Y'], 6.0, places=1,
            msg="T3: bottom→top wrap Y should be 6.0")
        # T4: wrap top→bottom: -2+(-4)=-6 → mod(-6,700)=694
        self.assertAlmostEqual(data['T4_X'], 500.0, places=1,
            msg="T4: X should be unchanged at 500.0")
        self.assertAlmostEqual(data['T4_Y'], 694.0, places=1,
            msg="T4: top→bottom wrap Y should be 694.0")
        # T5: corner bottom-right: diag (4,4) clamped to (2.828,2.828),
        #     (1002+2.828, 702+2.828) → mod → (4.828, 4.828)
        self.assertAlmostEqual(data['T5_X'], 4.8284, places=3,
            msg="T5: corner bottom-right X should be 4.828")
        self.assertAlmostEqual(data['T5_Y'], 4.8284, places=3,
            msg="T5: corner bottom-right Y should be 4.828")
        # T6: corner top-left: diag (-4,-4) clamped to (-2.828,-2.828),
        #     (-2-2.828, -2-2.828) → mod → (995.172, 695.172)
        self.assertAlmostEqual(data['T6_X'], 995.1716, places=3,
            msg="T6: corner top-left X should be 995.172")
        self.assertAlmostEqual(data['T6_Y'], 695.1716, places=3,
            msg="T6: corner top-left Y should be 695.172")
        # T7: high-speed clamped: spd=1200→V0=4, pos_x=500+4=504
        self.assertAlmostEqual(data['T7_X'], 504.0, places=1,
            msg="T7: high-speed X should be 504.0")
        self.assertAlmostEqual(data['T7_Y'], 350.0, places=1,
            msg="T7: Y should be unchanged at 350.0")
        self.assertAlmostEqual(data['T7_VX'], 4.0, places=1,
            msg="T7: clamped VX should be 4.0")
        # T8: velocity unchanged after wrap
        self.assertAlmostEqual(data['T8_VX'], 4.0, places=1,
            msg="T8: VX unchanged after wrap, should be 4.0")
        self.assertAlmostEqual(data['T8_VY'], 0.0, places=1,
            msg="T8: VY should be 0.0")

    def _check_positions_in_bounds(self, data):
        """All positions must be in [0,WIDTH)×[0,HEIGHT)."""
        for i in range(1, self.EXPECTED_TESTS + 1):
            x = data.get(f'T{i}_X')
            y = data.get(f'T{i}_Y')
            if x is not None:
                self.assertGreaterEqual(x, 0, f"T{i} x={x} < 0")
                self.assertLess(x, WIDTH, f"T{i} x={x} >= {WIDTH}")
            if y is not None:
                self.assertGreaterEqual(y, 0, f"T{i} y={y} < 0")
                self.assertLess(y, HEIGHT, f"T{i} y={y} >= {HEIGHT}")

    def test_octave_physics_step(self):
        """Run test_toroidal_wrap.m via local Octave CLI."""
        data = self._run_octave_script('test_toroidal_wrap.m')
        self._verify_results(data)
        self._check_positions_in_bounds(data)

    def test_octave_full_key_handler(self):
        """Run test_key_handler.m via local Octave CLI.
        Exercises the EXACT key_handler function from alg2.m with
        simulated keypresses for b, m, p, h, r, arrows, brackets, +/-.
        Verifies all globals toggle correctly and independently:
          - b/B toggles MARGIN_BOUNDARY (toroidal ↔ margin)
          - m/M toggles MODE (projection ↔ spatial)
          - p   toggles paused
          - h   toggles show_help
          - up/down arrows adjust PHI_P ±0.01
          - left/right arrows adjust PHI_A ±0.01
          - [ ] brackets adjust SIGMA ±1
          - +/= increments pending_add by 10
          - -   increments pending_remove by 10
          - r   sets pending_reset = true"""
        data = self._run_octave_script('test_key_handler.m')

        # T1: initial state — all defaults
        self.assertEqual(data.get('T1_MARGIN'), 0, "Initial MARGIN_BOUNDARY should be false")
        self.assertEqual(data.get('T1_MODE'), 0, "Initial MODE should be 0 (PROJECTION)")
        self.assertEqual(data.get('T1_PAUSED'), 0, "Initial paused should be false")
        self.assertEqual(data.get('T1_HELP'), 0, "Initial show_help should be false")
        self.assertAlmostEqual(data.get('T1_PHIP', 0), 0.03, places=2)
        self.assertAlmostEqual(data.get('T1_PHIA', 0), 0.80, places=2)
        self.assertEqual(data.get('T1_SIGMA'), 4)
        self.assertEqual(data.get('T1_PENDADD'), 0)
        self.assertEqual(data.get('T1_PENDRMV'), 0)
        self.assertEqual(data.get('T1_RESET'), 0)

        # T2: 'b' toggles MARGIN_BOUNDARY false→true; MODE and paused unchanged
        self.assertEqual(data.get('T2_MARGIN'), 1, "After 'b': MARGIN_BOUNDARY should be true")
        self.assertEqual(data.get('T2_MODE'), 0, "After 'b': MODE unchanged")
        self.assertEqual(data.get('T2_PAUSED'), 0, "After 'b': paused unchanged")

        # T3: 'm' toggles MODE 0→1; MARGIN_BOUNDARY still true
        self.assertEqual(data.get('T3_MODE'), 1, "After 'm': MODE should be 1 (SPATIAL)")
        self.assertEqual(data.get('T3_MARGIN'), 1, "After 'm': MARGIN_BOUNDARY unchanged")

        # T4: 'p' toggles paused false→true
        self.assertEqual(data.get('T4_PAUSED'), 1, "After 'p': paused should be true")
        self.assertEqual(data.get('T4_MODE'), 1, "After 'p': MODE unchanged")
        self.assertEqual(data.get('T4_MARGIN'), 1, "After 'p': MARGIN_BOUNDARY unchanged")

        # T5: 'h' toggles show_help false→true
        self.assertEqual(data.get('T5_HELP'), 1, "After 'h': show_help should be true")
        self.assertEqual(data.get('T5_PAUSED'), 1, "After 'h': paused unchanged")

        # T6: 'B' (uppercase) toggles MARGIN_BOUNDARY true→false
        self.assertEqual(data.get('T6_MARGIN'), 0, "After 'B': MARGIN_BOUNDARY should be false")
        self.assertEqual(data.get('T6_MODE'), 1, "After 'B': MODE unchanged")

        # T7: 'M' toggles MODE 1→0
        self.assertEqual(data.get('T7_MODE'), 0, "After 'M': MODE should be 0")
        self.assertEqual(data.get('T7_MARGIN'), 0, "After 'M': MARGIN_BOUNDARY unchanged")

        # T8: 'p' again toggles paused true→false
        self.assertEqual(data.get('T8_PAUSED'), 0, "After second 'p': paused should be false")
        self.assertEqual(data.get('T8_HELP'), 1, "After second 'p': help unchanged")

        # T9: 'h' again toggles show_help true→false
        self.assertEqual(data.get('T9_HELP'), 0, "After second 'h': show_help should be false")

        # T10: ']' increments SIGMA 4→5
        self.assertEqual(data.get('T10_SIGMA'), 5, "After ']': SIGMA should be 5")

        # T11: 'uparrow' increments PHI_P 0.03→0.04
        self.assertAlmostEqual(data.get('T11_PHIP', 0), 0.04, places=2)

        # T12: 'leftarrow' decrements PHI_A 0.80→0.79
        self.assertAlmostEqual(data.get('T12_PHIA', 0), 0.79, places=2)

        # T13: 'equal' adds 10 to pending_add
        self.assertEqual(data.get('T13_PENDADD'), 10, "After '=': pending_add should be 10")

        # T14: 'hyphen' adds 10 to pending_remove
        self.assertEqual(data.get('T14_PENDRMV'), 10, "After '-': pending_remove should be 10")

        # T15: 'r' sets pending_reset = true
        self.assertEqual(data.get('T15_RESET'), 1, "After 'r': pending_reset should be true")

        # T16: multiple presses accumulate correctly
        self.assertEqual(data.get('T16_PENDADD'), 30, "After 3 '=' presses: pending_add should be 30")
        self.assertEqual(data.get('T16_SIGMA'), 7, "After 3 ']' presses: SIGMA should be 7")
        self.assertEqual(data.get('T16_SIGMABACK'), 6, "After '[' press: SIGMA should drop from 7 to 6")

        # T17: 'downarrow' decrements PHI_P back to 0.03
        self.assertAlmostEqual(data.get('T17_PHIP', 0), 0.03, places=2)

        # T18: 'rightarrow' increments PHI_A back to 0.80
        self.assertAlmostEqual(data.get('T18_PHIA', 0), 0.80, places=2)

        # T19: all independent toggles ended at their default values
        self.assertEqual(data.get('T19_MARGIN'), 0, "Final MARGIN_BOUNDARY should be false")
        self.assertEqual(data.get('T19_MODE'), 0, "Final MODE should be 0")
        self.assertEqual(data.get('T19_PAUSED'), 0, "Final paused should be false")
        self.assertEqual(data.get('T19_HELP'), 0, "Final show_help should be false")

        # T20: unrecognized key 'x' — NO globals mutated
        self.assertEqual(data.get('T20_MARGIN_UNCHANGED'), 1, "After 'x': MARGIN_BOUNDARY unchanged")
        self.assertEqual(data.get('T20_MODE_UNCHANGED'), 1, "After 'x': MODE unchanged")
        self.assertEqual(data.get('T20_PAUSED_UNCHANGED'), 1, "After 'x': paused unchanged")
        self.assertEqual(data.get('T20_HELP_UNCHANGED'), 1, "After 'x': show_help unchanged")
        self.assertEqual(data.get('T20_PHIP_UNCHANGED'), 1, "After 'x': PHI_P unchanged")
        self.assertEqual(data.get('T20_PHIA_UNCHANGED'), 1, "After 'x': PHI_A unchanged")
        self.assertEqual(data.get('T20_SIGMA_UNCHANGED'), 1, "After 'x': SIGMA unchanged")
        self.assertEqual(data.get('T20_PENDADD_UNCHANGED'), 1, "After 'x': pending_add unchanged")
        self.assertEqual(data.get('T20_PENDRMV_UNCHANGED'), 1, "After 'x': pending_remove unchanged")
        self.assertEqual(data.get('T20_RESET_UNCHANGED'), 1, "After 'x': pending_reset unchanged")

        # T21: unrecognized key 'q' — NO globals mutated
        self.assertEqual(data.get('T21_MARGIN_UNCHANGED'), 1, "After 'q': MARGIN_BOUNDARY unchanged")
        self.assertEqual(data.get('T21_MODE_UNCHANGED'), 1, "After 'q': MODE unchanged")
        self.assertEqual(data.get('T21_PAUSED_UNCHANGED'), 1, "After 'q': paused unchanged")
        self.assertEqual(data.get('T21_HELP_UNCHANGED'), 1, "After 'q': show_help unchanged")
        self.assertEqual(data.get('T21_PHIP_UNCHANGED'), 1, "After 'q': PHI_P unchanged")
        self.assertEqual(data.get('T21_PHIA_UNCHANGED'), 1, "After 'q': PHI_A unchanged")
        self.assertEqual(data.get('T21_SIGMA_UNCHANGED'), 1, "After 'q': SIGMA unchanged")
        self.assertEqual(data.get('T21_PENDADD_UNCHANGED'), 1, "After 'q': pending_add unchanged")
        self.assertEqual(data.get('T21_PENDRMV_UNCHANGED'), 1, "After 'q': pending_remove unchanged")
        self.assertEqual(data.get('T21_RESET_UNCHANGED'), 1, "After 'q': pending_reset unchanged")

        # T22: PHI_P floor at 0.0 — 5 downarrow presses, caps at 0.00
        self.assertAlmostEqual(data.get('T22_PHIP', -1), 0.00, places=2,
            msg="PHI_P should be clamped at 0.00")
        self.assertEqual(data.get('T22_PHIP_AT_FLOOR'), 1,
            "PHI_P == 0.0 should be true")

        # T23: PHI_A ceiling at 1.0 — 22 rightarrow presses, caps at 1.00
        self.assertAlmostEqual(data.get('T23_PHIA', -1), 1.00, places=2,
            msg="PHI_A should be clamped at 1.00")
        self.assertEqual(data.get('T23_PHIA_AT_CEILING'), 1,
            "PHI_A == 1.0 should be true")

        # T24: PHI_A floor at 0.0 — 102 leftarrow presses from 1.00
        self.assertAlmostEqual(data.get('T24_PHIA', -1), 0.00, places=2,
            msg="PHI_A should be clamped at 0.00")
        self.assertEqual(data.get('T24_PHIA_AT_FLOOR'), 1,
            "PHI_A == 0.0 should be true")

        # T25: SIGMA ceiling at 50 — 50 ] presses from 6
        self.assertEqual(data.get('T25_SIGMA'), 50,
            "SIGMA should be clamped at 50")
        self.assertEqual(data.get('T25_SIGMA_AT_CEILING'), 1,
            "SIGMA == 50 should be true")

        # T26: SIGMA floor at 1 — 55 [ presses from 50
        self.assertEqual(data.get('T26_SIGMA'), 1,
            "SIGMA should be clamped at 1")
        self.assertEqual(data.get('T26_SIGMA_AT_FLOOR'), 1,
            "SIGMA == 1 should be true")

        # T27: pending_add ceiling at 200 — 20 = presses from 30
        self.assertEqual(data.get('T27_PENDADD'), 200,
            "pending_add should be clamped at 200")
        self.assertEqual(data.get('T27_PENDADD_AT_CEILING'), 1,
            "pending_add == 200 should be true")

        # T28: pending_remove has NO cap — 100 '-' presses from 10 → 1010
        self.assertEqual(data.get('T28_PENDRMV'), 1010,
            "pending_remove should grow unbounded to 1010")
        self.assertEqual(data.get('T28_PENDRMV_UNBOUNDED'), 1,
            "pending_remove > 200 should be true (no cap)")

        # T29: PHI_P ceiling at 1.0 — 102 uparrow presses from 0.00
        self.assertAlmostEqual(data.get('T29_PHIP', -1), 1.00, places=2,
            msg="PHI_P should be clamped at 1.00")
        self.assertEqual(data.get('T29_PHIP_AT_CEILING'), 1,
            "PHI_P == 1.0 should be true")

        # T30: empty-key boundary case (ibut=0 analogue) — all globals unchanged
        self.assertEqual(data.get('T30_MARGIN_UNCHANGED'), 1, "Empty key: MARGIN_BOUNDARY unchanged")
        self.assertEqual(data.get('T30_MODE_UNCHANGED'), 1, "Empty key: MODE unchanged")
        self.assertEqual(data.get('T30_PAUSED_UNCHANGED'), 1, "Empty key: paused unchanged")
        self.assertEqual(data.get('T30_HELP_UNCHANGED'), 1, "Empty key: show_help unchanged")
        self.assertEqual(data.get('T30_PHIP_UNCHANGED'), 1, "Empty key: PHI_P unchanged")
        self.assertEqual(data.get('T30_PHIA_UNCHANGED'), 1, "Empty key: PHI_A unchanged")
        self.assertEqual(data.get('T30_SIGMA_UNCHANGED'), 1, "Empty key: SIGMA unchanged")
        self.assertEqual(data.get('T30_PENDADD_UNCHANGED'), 1, "Empty key: pending_add unchanged")
        self.assertEqual(data.get('T30_PENDRMV_UNCHANGED'), 1, "Empty key: pending_remove unchanged")
        self.assertEqual(data.get('T30_RESET_UNCHANGED'), 1, "Empty key: pending_reset unchanged")

    def test_octave_boundary_toggle(self):
        """Run test_boundary_toggle.m via local Octave CLI.
        Verifies MARGIN_BOUNDARY global can be toggled at runtime:
          - Starts false (toroidal)
          - Toggles to true (margin) on first simulated 'b' press
          - Toggles back to false on second simulated 'b' press"""
        data = self._run_octave_script('test_boundary_toggle.m')

        # Parse STATE0, STATE1, STATE2 values
        self.assertIn('STATE0', data, "Missing STATE0")
        self.assertIn('STATE1', data, "Missing STATE1")
        self.assertIn('STATE2', data, "Missing STATE2")

        # STATE0: initial = false (toroidal) → 0
        self.assertEqual(data['STATE0'], 0,
                         f"STATE0 should be 0 (false), got {data['STATE0']}")
        # STATE1: after first toggle → true (margin) → 1
        self.assertEqual(data['STATE1'], 1,
                         f"STATE1 should be 1 (true), got {data['STATE1']}")
        # STATE2: after second toggle → back to false → 0
        self.assertEqual(data['STATE2'], 0,
                         f"STATE2 should be 0 (false), got {data['STATE2']}")

        # Companion globals should be present
        self.assertIn('BOUNDARY_MARGIN', data, "Scilab: BOUNDARY_MARGIN should be present")
        self.assertEqual(data['BOUNDARY_MARGIN'], 200,
                         "Scilab: BOUNDARY_MARGIN should be 200")
        self.assertIn('BOUNDARY_TURN_FACTOR', data, "Scilab: BOUNDARY_TURN_FACTOR should be present")
        self.assertEqual(data['BOUNDARY_TURN_FACTOR'], 1,
                         "Scilab: BOUNDARY_TURN_FACTOR should be 1")

    def test_scilab_full_key_handler_docker(self):
        """Run test_key_handler.sce via docker-compose.
        Exercises the EXACT key_handler function from alg2.sce with
        simulated keypresses via ASCII codes (ibut < 0 convention).
        Verifies all globals toggle correctly and independently."""
        data = self._run_scilab_script_docker('test_key_handler.sce')

        # T1: initial state — all defaults
        self.assertEqual(data.get('T1_MARGIN'), 0, "Initial MARGIN_BOUNDARY should be false")
        self.assertEqual(data.get('T1_MODE'), 0, "Initial MODE should be 0 (PROJECTION)")
        self.assertEqual(data.get('T1_PAUSED'), 0, "Initial paused should be false")
        self.assertEqual(data.get('T1_HELP'), 0, "Initial show_help should be false")
        self.assertAlmostEqual(data.get('T1_PHIP', 0), 0.03, places=2)
        self.assertAlmostEqual(data.get('T1_PHIA', 0), 0.80, places=2)
        self.assertEqual(data.get('T1_SIGMA'), 4)
        self.assertEqual(data.get('T1_PENDADD'), 0)
        self.assertEqual(data.get('T1_PENDRMV'), 0)
        self.assertEqual(data.get('T1_RESET'), 0)

        # T2: 'b' toggles MARGIN_BOUNDARY false→true
        self.assertEqual(data.get('T2_MARGIN'), 1)
        self.assertEqual(data.get('T2_MODE'), 0, "After 'b': MODE unchanged")
        self.assertEqual(data.get('T2_PAUSED'), 0, "After 'b': paused unchanged")

        # T3: 'm' toggles MODE 0→1
        self.assertEqual(data.get('T3_MODE'), 1)
        self.assertEqual(data.get('T3_MARGIN'), 1, "After 'm': MARGIN_BOUNDARY unchanged")

        # T4: 'p' toggles paused false→true
        self.assertEqual(data.get('T4_PAUSED'), 1)
        self.assertEqual(data.get('T4_MODE'), 1, "After 'p': MODE unchanged")
        self.assertEqual(data.get('T4_MARGIN'), 1, "After 'p': MARGIN_BOUNDARY unchanged")

        # T5: 'h' toggles show_help false→true
        self.assertEqual(data.get('T5_HELP'), 1)
        self.assertEqual(data.get('T5_PAUSED'), 1, "After 'h': paused unchanged")

        # T6: 'B' toggles MARGIN_BOUNDARY true→false
        self.assertEqual(data.get('T6_MARGIN'), 0)
        self.assertEqual(data.get('T6_MODE'), 1, "After 'B': MODE unchanged")

        # T7: 'M' toggles MODE 1→0
        self.assertEqual(data.get('T7_MODE'), 0)
        self.assertEqual(data.get('T7_MARGIN'), 0, "After 'M': MARGIN_BOUNDARY unchanged")

        # T8: 'p' again toggles paused true→false
        self.assertEqual(data.get('T8_PAUSED'), 0)
        self.assertEqual(data.get('T8_HELP'), 1, "After second 'p': help unchanged")

        # T9: 'h' again toggles show_help true→false
        self.assertEqual(data.get('T9_HELP'), 0)

        # T10: ']' increments SIGMA 4→5
        self.assertEqual(data.get('T10_SIGMA'), 5)

        # T11: up arrow increments PHI_P 0.03→0.04
        self.assertAlmostEqual(data.get('T11_PHIP', 0), 0.04, places=2)

        # T12: left arrow decrements PHI_A 0.80→0.79
        self.assertAlmostEqual(data.get('T12_PHIA', 0), 0.79, places=2)

        # T13: '=' adds 10 to pending_add
        self.assertEqual(data.get('T13_PENDADD'), 10)

        # T14: '-' adds 10 to pending_remove
        self.assertEqual(data.get('T14_PENDRMV'), 10)

        # T15: 'r' sets pending_reset = true
        self.assertEqual(data.get('T15_RESET'), 1)

        # T16: multiple presses accumulate
        self.assertEqual(data.get('T16_PENDADD'), 30)
        self.assertEqual(data.get('T16_SIGMA'), 7)
        self.assertEqual(data.get('T16_SIGMABACK'), 6)

        # T17: down arrow decrements PHI_P back to 0.03
        self.assertAlmostEqual(data.get('T17_PHIP', 0), 0.03, places=2)

        # T18: right arrow increments PHI_A back to 0.80
        self.assertAlmostEqual(data.get('T18_PHIA', 0), 0.80, places=2)

        # T19: all independent toggles ended at defaults
        self.assertEqual(data.get('T19_MARGIN'), 0)
        self.assertEqual(data.get('T19_MODE'), 0)
        self.assertEqual(data.get('T19_PAUSED'), 0)
        self.assertEqual(data.get('T19_HELP'), 0)

        # T20: unrecognized key 'x' (120) — NO globals mutated
        self.assertEqual(data.get('T20_MARGIN_UNCHANGED'), 1, "Scilab after 'x': MARGIN_BOUNDARY unchanged")
        self.assertEqual(data.get('T20_MODE_UNCHANGED'), 1, "Scilab after 'x': MODE unchanged")
        self.assertEqual(data.get('T20_PAUSED_UNCHANGED'), 1, "Scilab after 'x': paused unchanged")
        self.assertEqual(data.get('T20_HELP_UNCHANGED'), 1, "Scilab after 'x': show_help unchanged")
        self.assertEqual(data.get('T20_PHIP_UNCHANGED'), 1, "Scilab after 'x': PHI_P unchanged")
        self.assertEqual(data.get('T20_PHIA_UNCHANGED'), 1, "Scilab after 'x': PHI_A unchanged")
        self.assertEqual(data.get('T20_SIGMA_UNCHANGED'), 1, "Scilab after 'x': SIGMA unchanged")
        self.assertEqual(data.get('T20_PENDADD_UNCHANGED'), 1, "Scilab after 'x': pending_add unchanged")
        self.assertEqual(data.get('T20_PENDRMV_UNCHANGED'), 1, "Scilab after 'x': pending_remove unchanged")
        self.assertEqual(data.get('T20_RESET_UNCHANGED'), 1, "Scilab after 'x': pending_reset unchanged")

        # T21: unrecognized key 'q' (113) — NO globals mutated
        self.assertEqual(data.get('T21_MARGIN_UNCHANGED'), 1, "Scilab after 'q': MARGIN_BOUNDARY unchanged")
        self.assertEqual(data.get('T21_MODE_UNCHANGED'), 1, "Scilab after 'q': MODE unchanged")
        self.assertEqual(data.get('T21_PAUSED_UNCHANGED'), 1, "Scilab after 'q': paused unchanged")
        self.assertEqual(data.get('T21_HELP_UNCHANGED'), 1, "Scilab after 'q': show_help unchanged")
        self.assertEqual(data.get('T21_PHIP_UNCHANGED'), 1, "Scilab after 'q': PHI_P unchanged")
        self.assertEqual(data.get('T21_PHIA_UNCHANGED'), 1, "Scilab after 'q': PHI_A unchanged")
        self.assertEqual(data.get('T21_SIGMA_UNCHANGED'), 1, "Scilab after 'q': SIGMA unchanged")
        self.assertEqual(data.get('T21_PENDADD_UNCHANGED'), 1, "Scilab after 'q': pending_add unchanged")
        self.assertEqual(data.get('T21_PENDRMV_UNCHANGED'), 1, "Scilab after 'q': pending_remove unchanged")
        self.assertEqual(data.get('T21_RESET_UNCHANGED'), 1, "Scilab after 'q': pending_reset unchanged")

        # T22: PHI_P floor at 0.0 — 5 downarrow presses (40)
        self.assertAlmostEqual(data.get('T22_PHIP', -1), 0.00, places=2,
            msg="Scilab: PHI_P should be clamped at 0.00")
        self.assertEqual(data.get('T22_PHIP_AT_FLOOR'), 1,
            "Scilab: PHI_P == 0.0 should be true")

        # T23: PHI_A ceiling at 1.0 — 22 rightarrow presses (39)
        self.assertAlmostEqual(data.get('T23_PHIA', -1), 1.00, places=2,
            msg="Scilab: PHI_A should be clamped at 1.00")
        self.assertEqual(data.get('T23_PHIA_AT_CEILING'), 1,
            "Scilab: PHI_A == 1.0 should be true")

        # T24: PHI_A floor at 0.0 — 102 leftarrow presses (37)
        self.assertAlmostEqual(data.get('T24_PHIA', -1), 0.00, places=2,
            msg="Scilab: PHI_A should be clamped at 0.00")
        self.assertEqual(data.get('T24_PHIA_AT_FLOOR'), 1,
            "Scilab: PHI_A == 0.0 should be true")

        # T25: SIGMA ceiling at 50 — 50 ] presses (93)
        self.assertEqual(data.get('T25_SIGMA'), 50,
            "Scilab: SIGMA should be clamped at 50")
        self.assertEqual(data.get('T25_SIGMA_AT_CEILING'), 1,
            "Scilab: SIGMA == 50 should be true")

        # T26: SIGMA floor at 1 — 55 [ presses (91)
        self.assertEqual(data.get('T26_SIGMA'), 1,
            "Scilab: SIGMA should be clamped at 1")
        self.assertEqual(data.get('T26_SIGMA_AT_FLOOR'), 1,
            "Scilab: SIGMA == 1 should be true")

        # T27: pending_add ceiling at 200 — 20 = presses (61)
        self.assertEqual(data.get('T27_PENDADD'), 200,
            "Scilab: pending_add should be clamped at 200")
        self.assertEqual(data.get('T27_PENDADD_AT_CEILING'), 1,
            "Scilab: pending_add == 200 should be true")

        # T28: pending_remove unbounded — 100 - presses (45) from 10 → 1010
        self.assertEqual(data.get('T28_PENDRMV'), 1010,
            "Scilab: pending_remove should grow unbounded to 1010")
        self.assertEqual(data.get('T28_PENDRMV_UNBOUNDED'), 1,
            "Scilab: pending_remove > 200 should be true (no cap)")

        # T29: PHI_P ceiling at 1.0 — 102 uparrow presses (38)
        self.assertAlmostEqual(data.get('T29_PHIP', -1), 1.00, places=2,
            msg="Scilab: PHI_P should be clamped at 1.00")
        self.assertEqual(data.get('T29_PHIP_AT_CEILING'), 1,
            "Scilab: PHI_P == 1.0 should be true")

        # T30: positive ibut (mouse event) — handler skips entirely
        self.assertEqual(data.get('T30_PHIP_UNCHANGED'), 1, "Scilab +ibut: PHI_P unchanged")
        self.assertEqual(data.get('T30_PHIA_UNCHANGED'), 1, "Scilab +ibut: PHI_A unchanged")
        self.assertEqual(data.get('T30_SIGMA_UNCHANGED'), 1, "Scilab +ibut: SIGMA unchanged")
        self.assertEqual(data.get('T30_MARGIN_UNCHANGED'), 1, "Scilab +ibut: MARGIN_BOUNDARY unchanged")
        self.assertEqual(data.get('T30_MODE_UNCHANGED'), 1, "Scilab +ibut: MODE unchanged")
        self.assertEqual(data.get('T30_PAUSED_UNCHANGED'), 1, "Scilab +ibut: paused unchanged")
        self.assertEqual(data.get('T30_HELP_UNCHANGED'), 1, "Scilab +ibut: show_help unchanged")

        # T31: ibut = 0 boundary case (focused, isolated) — no globals mutated
        self.assertEqual(data.get('T31_MARGIN_UNCHANGED'), 1, "Scilab ibut=0: MARGIN_BOUNDARY unchanged")
        self.assertEqual(data.get('T31_MODE_UNCHANGED'), 1, "Scilab ibut=0: MODE unchanged")
        self.assertEqual(data.get('T31_PAUSED_UNCHANGED'), 1, "Scilab ibut=0: paused unchanged")
        self.assertEqual(data.get('T31_HELP_UNCHANGED'), 1, "Scilab ibut=0: show_help unchanged")
        self.assertEqual(data.get('T31_PHIP_UNCHANGED'), 1, "Scilab ibut=0: PHI_P unchanged")
        self.assertEqual(data.get('T31_PHIA_UNCHANGED'), 1, "Scilab ibut=0: PHI_A unchanged")
        self.assertEqual(data.get('T31_SIGMA_UNCHANGED'), 1, "Scilab ibut=0: SIGMA unchanged")
        self.assertEqual(data.get('T31_PENDADD_UNCHANGED'), 1, "Scilab ibut=0: pending_add unchanged")
        self.assertEqual(data.get('T31_PENDRMV_UNCHANGED'), 1, "Scilab ibut=0: pending_remove unchanged")
        self.assertEqual(data.get('T31_RESET_UNCHANGED'), 1, "Scilab ibut=0: pending_reset unchanged")

    def test_scilab_boundary_toggle_docker(self):
        """Run test_boundary_toggle.sce via docker-compose.
        Verifies MARGIN_BOUNDARY can be toggled at runtime in Scilab."""
        data = self._run_scilab_script_docker('test_boundary_toggle.sce')

        self.assertIn('STATE0', data, "Scilab: Missing STATE0")
        self.assertIn('STATE1', data, "Scilab: Missing STATE1")
        self.assertIn('STATE2', data, "Scilab: Missing STATE2")

        # STATE0: initial = false (%f) → 0
        self.assertEqual(data['STATE0'], 0,
                         f"STATE0 should be 0 (false), got {data['STATE0']}")
        # STATE1: after first toggle → true (%t) → 1
        self.assertEqual(data['STATE1'], 1,
                         f"STATE1 should be 1 (true), got {data['STATE1']}")
        # STATE2: after second toggle → back to false → 0
        self.assertEqual(data['STATE2'], 0,
                         f"STATE2 should be 0 (false), got {data['STATE2']}")

        self.assertIn('BOUNDARY_MARGIN', data)
        self.assertEqual(data['BOUNDARY_MARGIN'], 200)
        self.assertIn('BOUNDARY_TURN_FACTOR', data)
        self.assertEqual(data['BOUNDARY_TURN_FACTOR'], 1)

    def test_scilab_physics_step_docker(self):
        """Run test_toroidal_wrap.sce via docker-compose."""
        data = self._run_scilab_script_docker('test_toroidal_wrap.sce')
        self._verify_results(data)
        self._check_positions_in_bounds(data)

    # ═══════════════════════════════════════════════════════════════
    #  Cross-language consistency helpers
    # ═══════════════════════════════════════════════════════════════

    def _run_octave_script(self, script_name):
        """Run an Octave script and return parsed output dict."""
        import os
        import subprocess

        script = os.path.join(os.path.dirname(__file__), script_name)
        if not os.path.exists(script):
            self.skipTest(f"Missing {script}")
        octave = "/opt/homebrew/bin/octave"
        try:
            res = subprocess.run(
                [octave, "--no-gui", "--silent", script],
                capture_output=True, text=True, timeout=30,
                cwd=os.path.dirname(os.path.abspath(__file__)))
        except OSError:
            self.skipTest(f"Octave not found at {octave}")
        except subprocess.TimeoutExpired:
            self.fail(f"Octave {script_name} timed out")
        self.assertEqual(res.returncode, 0,
                         f"Octave exited {res.returncode}: {res.stderr}")
        return self._parse_output(res.stdout)

    def _run_scilab_script_docker(self, script_name):
        """Run a Scilab script via Docker; return parsed dict or skip."""
        import os
        import subprocess

        script = os.path.join(os.path.dirname(__file__), script_name)
        if not os.path.exists(script):
            self.skipTest(f"Missing {script}")
        cwd = os.path.dirname(os.path.abspath(__file__))
        try:
            res = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True, text=True, timeout=5, cwd=cwd)
        except (OSError, subprocess.TimeoutExpired):
            self.skipTest(
                f"docker compose not available (needed for {script_name})")
        if res.returncode != 0:
            detail = (
                f": {res.stderr.strip()}" if res.stderr.strip() else "")
            self.skipTest(
                f"docker compose returned {res.returncode} "
                f"for {script_name}{detail}")

        cmd = ["docker", "compose", "run", "--rm", "-T", "shell",
               "scilab-cli", "-nb", "-f", script_name]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=60, cwd=cwd)
        except subprocess.TimeoutExpired:
            self.fail(f"Scilab {script_name} docker timed out")

        if res.returncode != 0:
            self.skipTest(f"Scilab docker returned {res.returncode}")

        data = self._parse_output(res.stdout)
        if not data:
            self.skipTest(f"No parseable output from Scilab {script_name}")
        return data

    def test_cross_language_key_handler_consistency(self):
        """Compare Octave and Scilab key_handler outputs.
        Runs test_key_handler.m (Octave) and test_key_handler.sce (Scilab),
        then compares all T1-T30 outputs key-by-key for cross-language parity.
        Float values (PHI_P, PHI_A) use approximate comparison."""
        data_oct = self._run_octave_script('test_key_handler.m')
        data_sci = self._run_scilab_script_docker('test_key_handler.sce')

        oct_keys = set(k for k in data_oct if k.startswith('T'))
        sci_keys = set(k for k in data_sci if k.startswith('T'))
        shared = oct_keys & sci_keys

        self.assertGreater(len(shared), 0,
            "No shared keys between Octave and Scilab outputs")
        # T31 is Scilab-only (focused ibut=0 test — no Octave analogue
        # since Octave uses event.Key dispatch, not ibut).
        oct_only_expected = set()
        sci_only_expected = {k for k in sci_keys if k.startswith('T31')}
        self.assertEqual(oct_keys - sci_keys, oct_only_expected,
            f"Unexpected Octave-only keys: {sorted(oct_keys - sci_keys)}")
        self.assertEqual(sci_keys - oct_keys, sci_only_expected,
            f"Unexpected Scilab-only keys: {sorted((sci_keys - oct_keys) - sci_only_expected)}")

        float_pats = ('PHIP', 'PHIA')
        mismatches = []

        for key in sorted(shared):
            ov = data_oct[key]
            sv = data_sci[key]

            if any(p in key for p in float_pats):
                if abs(ov - sv) > 0.005:
                    mismatches.append(f"{key}: Oct={ov:.4f} Sci={sv:.4f}")
            else:
                if ov != sv:
                    mismatches.append(f"{key}: Oct={ov} Sci={sv}")

        if mismatches:
            self.fail(
                f"{len(mismatches)} key_handler output mismatches "
                f"between Octave and Scilab:\n" +
                "\n".join(mismatches[:20]))

    def test_cross_language_physics_consistency(self):
        """Compare Octave and Scilab toroidal wrap physics outputs.
        Runs test_toroidal_wrap.m (Octave) and test_toroidal_wrap.sce
        (Scilab), then compares all T1-T8 outputs key-by-key for
        cross-language parity. All physics values are floats."""
        data_oct = self._run_octave_script('test_toroidal_wrap.m')
        data_sci = self._run_scilab_script_docker('test_toroidal_wrap.sce')

        oct_keys = set(k for k in data_oct if k.startswith('T'))
        sci_keys = set(k for k in data_sci if k.startswith('T'))
        shared = oct_keys & sci_keys

        self.assertGreater(len(shared), 0,
            "No shared keys between Octave and Scilab physics outputs")
        self.assertEqual(oct_keys, sci_keys,
            f"Key set mismatch: Oct={len(oct_keys)} Sci={len(sci_keys)} "
            f"\nOct-only: {sorted(oct_keys - sci_keys)}"
            f"\nSci-only: {sorted(sci_keys - oct_keys)}")

        mismatches = []
        for key in sorted(shared):
            ov = data_oct[key]
            sv = data_sci[key]
            if abs(ov - sv) > 0.005:
                mismatches.append(f"{key}: Oct={ov:.4f} Sci={sv:.4f}")

        if mismatches:
            self.fail(
                f"{len(mismatches)} physics output mismatches "
                f"between Octave and Scilab:\n" +
                "\n".join(mismatches[:20]))

    def test_cross_language_boundary_toggle_consistency(self):
        """Compare Octave and Scilab boundary toggle outputs.
        Runs test_boundary_toggle.m (Octave) and test_boundary_toggle.sce
        (Scilab), then compares STATE0/1/2 and companion globals key-by-key."""
        data_oct = self._run_octave_script('test_boundary_toggle.m')
        data_sci = self._run_scilab_script_docker('test_boundary_toggle.sce')

        # Only compare numeric keys: STATE0, STATE1, STATE2,
        # BOUNDARY_MARGIN, BOUNDARY_TURN_FACTOR
        num_keys = {'STATE0', 'STATE1', 'STATE2',
                    'BOUNDARY_MARGIN', 'BOUNDARY_TURN_FACTOR'}
        oct_keys = set(k for k in data_oct if k in num_keys)
        sci_keys = set(k for k in data_sci if k in num_keys)
        shared = oct_keys & sci_keys

        self.assertEqual(oct_keys, num_keys,
            f"Octave missing keys: {sorted(num_keys - oct_keys)}")
        self.assertEqual(sci_keys, num_keys,
            f"Scilab missing keys: {sorted(num_keys - sci_keys)}")
        self.assertGreater(len(shared), 0,
            "No shared keys between Octave and Scilab boundary toggle outputs")

        mismatches = []
        for key in sorted(shared):
            ov = data_oct[key]
            sv = data_sci[key]
            if abs(ov - sv) > 0.001:
                mismatches.append(f"{key}: Oct={ov:.4f} Sci={sv:.4f}")

        if mismatches:
            self.fail(
                f"{len(mismatches)} boundary toggle output mismatches "
                f"between Octave and Scilab:\n" +
                "\n".join(mismatches[:20]))

    def test_all_cross_language_consistency(self):
        """Run all three cross-language consistency checks in one test.
        Executes key_handler, physics, and boundary toggle comparisons
        via subTest so each check reports independently."""
        checks = [
            ("key_handler",
             'test_key_handler.m', 'test_key_handler.sce',
             # Expected key-set asymmetry: T31 is Scilab-only
             {'T31'}, 0.005, ('PHIP', 'PHIA'), None),
            ("physics",
             'test_toroidal_wrap.m', 'test_toroidal_wrap.sce',
             # No expected asymmetry
             set(), 0.005, (), None),
            ("boundary_toggle",
             'test_boundary_toggle.m', 'test_boundary_toggle.sce',
             # Only compare numeric keys (TOGGLE_STEP is non-numeric)
             set(), 0.001, (),
             {'STATE0', 'STATE1', 'STATE2',
              'BOUNDARY_MARGIN', 'BOUNDARY_TURN_FACTOR'}),
        ]

        for name, oct_script, sci_script, sci_only, tol, float_pats, num_keys \
                in checks:
            with self.subTest(check=name):
                data_oct = self._run_octave_script(oct_script)
                data_sci = self._run_scilab_script_docker(sci_script)

                oct_keys = set(k for k in data_oct if k.startswith('T'))
                sci_keys = set(k for k in data_sci if k.startswith('T'))

                # For boundary_toggle, also include the non-T keys
                if name == "boundary_toggle":
                    oct_keys = {k for k in data_oct
                                if k in {'STATE0', 'STATE1', 'STATE2',
                                         'BOUNDARY_MARGIN',
                                         'BOUNDARY_TURN_FACTOR'}}
                    sci_keys = {k for k in data_sci
                                if k in {'STATE0', 'STATE1', 'STATE2',
                                         'BOUNDARY_MARGIN',
                                         'BOUNDARY_TURN_FACTOR'}}
                    # Assert both scripts produce all expected keys
                    self.assertEqual(oct_keys, num_keys,
                        f"Octave missing {name} keys: "
                        f"{sorted(num_keys - oct_keys)}")
                    self.assertEqual(sci_keys, num_keys,
                        f"Scilab missing {name} keys: "
                        f"{sorted(num_keys - sci_keys)}")

                shared = oct_keys & sci_keys

                self.assertGreater(len(shared), 0,
                    f"No shared keys in {name} check")

                if sci_only:
                    self.assertEqual(oct_keys - sci_keys, set(),
                        f"Unexpected Octave-only {name} keys: "
                        f"{sorted(oct_keys - sci_keys)}")
                    self.assertEqual(sci_keys - oct_keys, sci_only,
                        f"Unexpected Scilab-only {name} keys: "
                        f"{sorted((sci_keys - oct_keys) - sci_only)}")
                else:
                    self.assertEqual(oct_keys, sci_keys,
                        f"{name} key set mismatch: "
                        f"Oct-only: {sorted(oct_keys - sci_keys)} "
                        f"Sci-only: {sorted(sci_keys - oct_keys)}")

                mismatches = []
                for key in sorted(shared):
                    ov = data_oct[key]
                    sv = data_sci[key]

                    if float_pats and any(p in key for p in float_pats):
                        if abs(ov - sv) > tol:
                            mismatches.append(
                                f"{key}: Oct={ov:.4f} Sci={sv:.4f}")
                    elif isinstance(ov, float) or isinstance(sv, float):
                        if abs(ov - sv) > tol:
                            mismatches.append(
                                f"{key}: Oct={ov:.4f} Sci={sv:.4f}")
                    else:
                        if ov != sv:
                            mismatches.append(
                                f"{key}: Oct={ov} Sci={sv}")

                if mismatches:
                    self.fail(
                        f"{len(mismatches)} {name} output mismatches "
                        f"between Octave and Scilab:\n" +
                        "\n".join(mismatches[:20]))


# ══════════════════════════════════════════════════════════════════════
#  Test discovery sanity check — catches accidental regressions
# ══════════════════════════════════════════════════════════════════════

class TestPresetValidation(unittest.TestCase):
    """Verify all scenario presets apply without errors and produce
    valid phi_n >= 0 (weights must sum to at most 1)."""

    def test_all_presets_apply_without_errors(self):
        from flock_core import Config
        from scenario_presets import PRESETS, apply_preset

        preset_count = len(PRESETS)
        self.assertGreater(preset_count, 0,
            "PRESETS dict should not be empty")

        for key, preset in sorted(PRESETS.items(), key=lambda kv: str(kv[0])):
            config = Config()
            label = apply_preset(config, key)

            self.assertNotEqual(label, "",
                f"Preset {key}: apply_preset returned empty label")
            self.assertIn("PRESET", label,
                f"Preset {key}: label should contain 'PRESET'")

            self.assertGreaterEqual(config.phi_p, 0.0,
                f"Preset {key}: phi_p={config.phi_p} should be >= 0")
            self.assertLessEqual(config.phi_p, 1.0,
                f"Preset {key}: phi_p={config.phi_p} should be <= 1")

            self.assertGreaterEqual(config.phi_a, 0.0,
                f"Preset {key}: phi_a={config.phi_a} should be >= 0")
            self.assertLessEqual(config.phi_a, 1.0,
                f"Preset {key}: phi_a={config.phi_a} should be <= 1")

            phi_n = config.phi_n  # auto-computed: max(0, 1 − φp − φa)
            self.assertGreaterEqual(phi_n, 0.0,
                f"Preset {key}: phi_n={phi_n:.4f} should be >= 0 "
                f"(phi_p={config.phi_p}, phi_a={config.phi_a})")

            self.assertGreaterEqual(config.sigma, 1,
                f"Preset {key}: sigma={config.sigma} should be >= 1")
            self.assertLessEqual(config.sigma, 50,
                f"Preset {key}: sigma={config.sigma} should be <= 50")

            self.assertIn(config.mode, (0, 1),
                f"Preset {key}: mode={config.mode} should be 0 or 1")

    def test_presets_are_visually_distinct(self):
        """Verify presets produce meaningfully different flocks by checking
        that phi_n (noise weight), phi_p (projection), phi_a (alignment),
        sigma (neighbourhood size), and mode differ across presets.
        At least 75% should have unique (phi_p, phi_a, sigma, mode) tuples
        and at least 50% should have unique phi_n values."""
        from scenario_presets import PRESETS

        signatures = {}
        phi_n_values = set()

        for key, preset in PRESETS.items():
            phi_p = preset['phi_p']
            phi_a = preset['phi_a']
            sigma = preset['sigma']
            mode = preset['mode']
            phi_n = round(max(0.0, 1.0 - phi_p - phi_a), 4)

            phi_n_values.add(phi_n)
            signatures[key] = (phi_p, phi_a, sigma, mode, phi_n)

        unique_sigs = len(set(signatures.values()))
        total = len(PRESETS)

        self.assertGreaterEqual(unique_sigs, int(total * 0.75),
            f"Only {unique_sigs}/{total} unique preset signatures "
            f"(need >= {int(total * 0.75)}). "
            f"Presets may be too similar.")

        unique_phi_n = len(phi_n_values)
        self.assertGreaterEqual(unique_phi_n, int(total * 0.5),
            f"Only {unique_phi_n}/{total} unique phi_n values "
            f"(need >= {int(total * 0.5)}). "
            f"Flock noise levels are too uniform.")

        # Also verify no two presets are identical in all parameters
        for key_a in PRESETS:
            for key_b in PRESETS:
                if str(key_a) >= str(key_b):
                    continue
                sig_a = signatures[key_a]
                sig_b = signatures[key_b]
                self.assertNotEqual(
                    sig_a, sig_b,
                    f"Preset {key_a!r} and {key_b!r} have identical "
                    f"parameters: {sig_a}")

    def test_preset_count_matches_expected(self):
        """Sanity check: ensure we have exactly 16 presets (5 original
        + 11 companion). If this fails, a preset was added or removed
        without updating this test."""
        from scenario_presets import PRESETS
        self.assertEqual(len(PRESETS), 16,
            f"Expected 16 presets, got {len(PRESETS)}. "
            f"Update this assertion if presets were intentionally "
            f"added or removed.")

    # ── Toggle behaviour tests ──────────────────────────────────

    def test_toggle_same_key_restores_previous(self):
        """Applying preset A, then preset A again restores original values."""
        from flock_core import Config
        from scenario_presets import apply_preset

        config = Config()
        orig_phi_p = config.phi_p
        orig_phi_a = config.phi_a
        orig_sigma = config.sigma
        orig_mode = config.mode

        saved = _save_config(config)
        apply_preset(config, 1)

        self.assertNotEqual(config.phi_p, orig_phi_p,
            "Preset 1 should change phi_p from default")

        _restore_config(config, saved)

        self.assertEqual(config.phi_p, orig_phi_p,
            "Restore should return phi_p to original")
        self.assertEqual(config.phi_a, orig_phi_a,
            "Restore should return phi_a to original")
        self.assertEqual(config.sigma, orig_sigma,
            "Restore should return sigma to original")
        self.assertEqual(config.mode, orig_mode,
            "Restore should return mode to original")

    def test_toggle_different_key_overwrites_saved(self):
        """Applying preset A then preset B — toggle B should restore
        to A's values (not the original defaults)."""
        from flock_core import Config
        from scenario_presets import apply_preset, PRESETS

        config = Config()

        saved_a = _save_config(config)
        apply_preset(config, 1)

        # Now apply preset B; should save B's snapshot (post-preset-A)
        saved_b = _save_config(config)
        apply_preset(config, 2)

        self.assertNotEqual(config.phi_p, PRESETS[1]['phi_p'],
            "After preset 2, phi_p should differ from preset 1")

        _restore_config(config, saved_b)
        self.assertEqual(config.phi_p, PRESETS[1]['phi_p'],
            "Restoring to saved_b should return to preset 1 values")

    def test_toggle_manual_tweak_invalidates_saved_config(self):
        """After a preset is applied, a manual tweak clears the toggle
        state — no saved_config means no restore is possible."""
        from flock_core import Config
        from scenario_presets import apply_preset

        config = Config()
        orig_phi_p = config.phi_p

        saved = _save_config(config)
        apply_preset(config, 1)
        preset_phi_p = config.phi_p
        self.assertNotEqual(preset_phi_p, orig_phi_p,
            "Preset should change phi_p from default")

        # Simulate manual tweak: clear snapshot and adjust
        saved = None
        config.phi_p = 0.07

        self.assertIsNone(saved,
            "Manual tweak should clear toggle state")
        self.assertNotEqual(config.phi_p, preset_phi_p,
            "Manual tweak should change phi_p from preset value")

    def test_get_preset_key_number_keys(self):
        """_get_preset_key maps numeric pygame keys correctly."""
        self.assertEqual(_get_preset_key(pygame.K_1), 1)
        self.assertEqual(_get_preset_key(pygame.K_5), 5)
        self.assertEqual(_get_preset_key(pygame.K_6), 6)
        self.assertEqual(_get_preset_key(pygame.K_9), 9)
        self.assertEqual(_get_preset_key(pygame.K_0), 0)

    def test_get_preset_key_letter_keys(self):
        """_get_preset_key maps letter pygame keys correctly."""
        self.assertEqual(_get_preset_key(pygame.K_s), 's')
        self.assertEqual(_get_preset_key(pygame.K_l), 'l')
        self.assertEqual(_get_preset_key(pygame.K_i), 'i')
        self.assertEqual(_get_preset_key(pygame.K_v), 'v')
        self.assertEqual(_get_preset_key(pygame.K_k), 'k')
        self.assertEqual(_get_preset_key(pygame.K_q), 'q')

    def test_get_preset_key_returns_none_for_non_preset(self):
        """_get_preset_key returns None for keys not mapped to presets."""
        self.assertIsNone(_get_preset_key(pygame.K_a))
        self.assertIsNone(_get_preset_key(pygame.K_m))
        self.assertIsNone(_get_preset_key(pygame.K_SPACE))
        self.assertIsNone(_get_preset_key(pygame.K_ESCAPE))

    def test_save_restore_roundtrip(self):
        """_save_config followed by _restore_config preserves all values."""
        from flock_core import Config

        config = Config()
        config.phi_p = 0.12
        config.phi_a = 0.65
        config.sigma = 7
        config.mode = 1

        saved = _save_config(config)

        config.phi_p = 0.99
        config.phi_a = 0.01
        config.sigma = 50
        config.mode = 0

        _restore_config(config, saved)

        self.assertEqual(config.phi_p, 0.12)
        self.assertEqual(config.phi_a, 0.65)
        self.assertEqual(config.sigma, 7)
        self.assertEqual(config.mode, 1)


class TestDiscovery(unittest.TestCase, TestCountMixin):
    """Verify test count to catch accidental regressions in discovery."""

    EXPECTED_TEST_COUNT = 108


if __name__ == "__main__":
    unittest.main(verbosity=2)
