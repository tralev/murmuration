"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION T5 — PROJECTION MODEL UNIT TESTS                           ║
╚══════════════════════════════════════════════════════════════════════╝

 Standalone tests for projection_model.py — verify that the extracted
 compute_projection_and_visibility() function works correctly using
 minimal mock boids (no Boid class dependency).

 The mock boid only needs .position (pygame.Vector2) — the function
 uses identity checks (other is boid) and position arithmetic; it does
 not call any Boid methods.
──────────────────────────────────────────────────────────────────────
"""

import math
import unittest

import pygame

from test_count_mixin import TestCountMixin

from projection_model import compute_projection_and_visibility
from flock_core import BOID_SIZE


class MockBoid:
    """Minimal boid with just the attributes needed by the projection model."""
    __slots__ = ("position",)

    def __init__(self, x: float, y: float):
        self.position = pygame.Vector2(x, y)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  compute_projection_and_visibility                                   ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestComputeProjectionAndVisibility(unittest.TestCase):
    """Standalone tests for projection_model.compute_projection_and_visibility()."""

    # ── Edge cases ──────────────────────────────────────────────────

    def test_empty_boids_list(self):
        """Empty list → zero delta, no visible neighbours, zero theta."""
        observer = MockBoid(0, 0)
        delta, visible, theta, merged = compute_projection_and_visibility(observer, [])
        self.assertEqual(delta, pygame.Vector2(0, 0))
        self.assertEqual(visible, [])
        self.assertAlmostEqual(theta, 0.0)
        self.assertEqual(merged, [])

    def test_observer_is_only_boid(self):
        """Observer is the only boid in the list → same as empty."""
        observer = MockBoid(0, 0)
        delta, visible, theta, merged = compute_projection_and_visibility(
            observer, [observer]
        )
        self.assertEqual(delta, pygame.Vector2(0, 0))
        self.assertEqual(visible, [])
        self.assertAlmostEqual(theta, 0.0)

    def test_same_position_skipped(self):
        """Other boid at same position → dist < 0.001 → skipped."""
        observer = MockBoid(100, 200)
        other = MockBoid(100, 200)  # identical position
        delta, visible, theta, merged = compute_projection_and_visibility(
            observer, [observer, other]
        )
        self.assertEqual(len(visible), 0)
        self.assertAlmostEqual(theta, 0.0)

    # ── Single visible neighbour ────────────────────────────────────

    def test_single_bird_to_the_right(self):
        """One bird to the right → δ̂ points right (toward the bird).

        δ̂ sums unit vectors TO the merged interval boundaries.
        For a bird at angle 0: boundaries at −α and +α.
        Sum = (cos(−α)+cos(α), sin(−α)+sin(α)) ≈ (2, 0) → right.
        """
        observer = MockBoid(500, 350)
        other = MockBoid(600, 350)   # due east

        delta, visible, theta, merged = compute_projection_and_visibility(
            observer, [observer, other]
        )

        self.assertEqual(len(visible), 1)
        self.assertIs(visible[0][0], other)

        # δ̂ points toward the bird (right / positive x)
        self.assertGreater(delta.length(), 0.9)
        self.assertAlmostEqual(delta.x, 1.0, delta=0.02)
        self.assertAlmostEqual(delta.y, 0.0, delta=0.02)

        # Theta: single interval width / 2π
        dist = 100.0
        half = math.asin(min(BOID_SIZE / dist, 1.0))
        expected_theta = (2 * half) / (2 * math.pi)
        self.assertAlmostEqual(theta, expected_theta, places=4)

    def test_single_bird_above(self):
        """One bird directly above → δ̂ points up (toward the bird).

        Bird at angle 3π/2 (screen up): boundaries at 3π/2±α.
        Sum ≈ (0, −2) → points up (negative y in screen coords).
        """
        observer = MockBoid(500, 350)
        other = MockBoid(500, 250)   # due north (screen up)

        delta, visible, theta, merged = compute_projection_and_visibility(
            observer, [observer, other]
        )

        self.assertEqual(len(visible), 1)
        # δ̂ points toward the bird (up / negative y in Pygame screen coords)
        self.assertAlmostEqual(delta.x, 0.0, delta=0.02)
        self.assertAlmostEqual(delta.y, -1.0, delta=0.02)

    def test_theta_scales_with_distance(self):
        """Closer bird → larger angular width → higher theta."""
        observer = MockBoid(0, 0)
        near = MockBoid(20, 0)
        far = MockBoid(100, 0)

        _, _, theta_near, _ = compute_projection_and_visibility(
            observer, [observer, near]
        )
        _, _, theta_far, _ = compute_projection_and_visibility(
            observer, [observer, far]
        )

        self.assertGreater(theta_near, theta_far)

    # ── Occlusion (closest-first ordering) ──────────────────────────

    def test_closer_bird_occludes_further(self):
        """Closer bird completely blocks further bird → only closer visible.

        observer at (0,0), near at (50,0), far at (200,0).
        near's interval [−asin(3/50), +asin(3/50)] ≈ [−0.06, +0.06]
        fully covers far's interval [−0.015, +0.015].
        """
        observer = MockBoid(0, 0)
        near = MockBoid(50, 0)
        far = MockBoid(200, 0)
        delta, visible, theta, merged = compute_projection_and_visibility(
            observer, [observer, far, near]
        )

        self.assertEqual(len(visible), 1)
        self.assertIs(visible[0][0], near)

    def test_partial_occlusion_both_visible(self):
        """Far bird is partially occluded but has uncovered angular range
        → both birds are visible.

        observer at (0,0), near at (50,0) on x-axis,
        far at (200,30) — offset vertically so some angle extends beyond near.
        """
        observer = MockBoid(0, 0)
        near = MockBoid(50, 0)
        far = MockBoid(200, 30)

        delta, visible, theta, merged = compute_projection_and_visibility(
            observer, [observer, near, far]
        )

        visible_boids = [b for b, _ in visible]
        self.assertIn(near, visible_boids, "Near bird should be visible")
        self.assertIn(far, visible_boids, "Far bird should be visible (partial overlap)")
        self.assertIs(visible[0][0], near)  # closer first

    def test_three_birds_stacked(self):
        """Three birds on same ray — only the closest is visible."""
        observer = MockBoid(0, 0)
        a = MockBoid(20, 0)
        b = MockBoid(60, 0)
        c = MockBoid(120, 0)

        delta, visible, theta, merged = compute_projection_and_visibility(
            observer, [observer, c, b, a]
        )

        self.assertEqual(len(visible), 1)
        self.assertIs(visible[0][0], a)

    # ── δ̂ (delta) vector direction — points toward occlusion ────────

    def test_delta_points_toward_occlusion(self):
        """δ̂ points toward the occluded region (toward other birds).

        One bird at angle 0 → boundaries at −α and +α.
        Sum of unit vectors ≈ (2, 0) → points right (toward bird).
        This is the projection term: steer toward birds → cohesion.
        """
        observer = MockBoid(0, 0)
        other = MockBoid(100, 0)
        delta, _, _, _ = compute_projection_and_visibility(
            observer, [observer, other]
        )

        self.assertGreater(delta.length(), 0.9)
        self.assertGreater(delta.x, 0.9)   # points right toward the bird

    def test_delta_zero_when_fully_surrounded(self):
        """When occluded intervals cover the full circle, δ̂ = 0.

        The function explicitly checks: if merged is a single interval
        spanning the full [0, 2π) range, delta is set to (0, 0).
        Need enough close birds to trigger this — 24 birds at dist=12
        with BOID_SIZE=3 gives half=asin(0.25)≈0.253, each covering
        ~0.506 rad; with 24 birds the intervals overlap into a full ring.
        """
        observer = MockBoid(0, 0)
        ring = [observer]
        for i in range(24):
            angle = i * 2 * math.pi / 24
            ring.append(MockBoid(
                12 * math.cos(angle),
                12 * math.sin(angle),
            ))

        delta, visible, theta, merged = compute_projection_and_visibility(observer, ring)

        self.assertAlmostEqual(delta.length(), 0.0, delta=0.01,
            msg=f"Fully surrounded: delta should be ~0, got length={delta.length():.4f}")

    def test_delta_points_toward_birds_in_partial_ring(self):
        """Birds on the right half only → δ̂ points right (toward them).

        Birds at angles −π/2 to π/2 (east side). The merged interval
        spans the right half; boundaries at −π/2 and π/2.
        Sum ≈ (0, −1) + (0, 1) = (0, 0). But individual bird intervals
        create additional interior boundaries that contribute.
        The net direction should have a positive x component.
        """
        observer = MockBoid(0, 0)
        ring = [observer]
        for i in range(6):
            angle = -math.pi / 2 + i * math.pi / 5
            ring.append(MockBoid(
                20 * math.cos(angle),
                20 * math.sin(angle),
            ))

        delta, _, _, _ = compute_projection_and_visibility(observer, ring)

        # δ̂ should point right (toward the birds' side)
        self.assertGreater(delta.length(), 0.3)
        self.assertGreater(delta.x, 0.0,
            f"Delta should point right (toward birds), got x={delta.x:.3f}")

    # ── Theta (internal opacity) ────────────────────────────────────

    def test_theta_zero_for_empty(self):
        """No other birds → theta = 0."""
        observer = MockBoid(0, 0)
        _, _, theta, _ = compute_projection_and_visibility(observer, [observer])
        self.assertAlmostEqual(theta, 0.0)

    def test_theta_increases_with_more_birds(self):
        """More birds → more occlusion → higher theta."""
        observer = MockBoid(0, 0)
        one_bird = [observer, MockBoid(40, 0)]
        two_birds = [observer, MockBoid(40, 0), MockBoid(40, 25)]
        three_birds = [observer, MockBoid(40, 0), MockBoid(30, 20), MockBoid(30, -20)]

        _, _, t1, _ = compute_projection_and_visibility(observer, one_bird)
        _, _, t2, _ = compute_projection_and_visibility(observer, two_birds)
        _, _, t3, _ = compute_projection_and_visibility(observer, three_birds)

        self.assertLess(t1, t2, "Two birds should have more occlusion than one")
        self.assertLess(t2, t3, "Three birds should have more occlusion than two")

    def test_theta_clamped_to_one(self):
        """Theta should never exceed 1.0 even with many birds."""
        observer = MockBoid(0, 0)
        many = [observer]
        for i in range(50):
            angle = i * 2 * math.pi / 50
            many.append(MockBoid(30 * math.cos(angle), 30 * math.sin(angle)))

        _, _, theta, _ = compute_projection_and_visibility(observer, many)
        self.assertLessEqual(theta, 1.0)

    # ── Angular wrap-around ─────────────────────────────────────────

    def test_bird_at_angular_wrap(self):
        """Birds near the 0/2π angular boundary — intervals normalise
        across wrap and merge correctly."""
        observer = MockBoid(0, 0)
        # Bird A at angle ~0 (positive x)
        a = MockBoid(50, 0)
        # Bird B at angle ~350° (just below 2π)
        angle_b = 2 * math.pi - 0.1
        b = MockBoid(50 * math.cos(angle_b), 50 * math.sin(angle_b))

        delta, visible, theta, merged = compute_projection_and_visibility(
            observer, [observer, a, b]
        )

        # Both should be visible (narrow wrap intervals don't fully cover each other)
        self.assertEqual(len(visible), 2)

    # ── Visibility ordering ─────────────────────────────────────────

    def test_visible_sorted_by_distance(self):
        """Visible neighbours should be returned in distance order."""
        observer = MockBoid(0, 0)
        far = MockBoid(200, 0)
        mid = MockBoid(100, 20)   # offset so not occluded by far
        near = MockBoid(40, 40)   # offset so not occluded

        _, visible, _, _ = compute_projection_and_visibility(
            observer, [observer, far, mid, near]
        )

        self.assertEqual(len(visible), 3)
        distances = [d for _, d in visible]
        self.assertEqual(distances, sorted(distances),
                         "Visible neighbours should be sorted by distance")

    # ── Determinism ─────────────────────────────────────────────────

    def test_deterministic_given_same_positions(self):
        """Identical inputs produce identical outputs."""
        observer = MockBoid(250, 350)
        others = [observer]
        for i in range(10):
            angle = i * 2 * math.pi / 10
            others.append(MockBoid(
                250 + 80 * math.cos(angle),
                350 + 80 * math.sin(angle),
            ))

        d1, v1, t1, m1 = compute_projection_and_visibility(observer, others)
        d2, v2, t2, m2 = compute_projection_and_visibility(observer, others)

        self.assertEqual(d1, d2)
        self.assertEqual(len(v1), len(v2))
        self.assertAlmostEqual(t1, t2)
        self.assertEqual(m1, m2)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Test count guardian                                                 ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestDiscovery(unittest.TestCase, TestCountMixin):
    """Verify test count for projection_model module."""

    EXPECTED_TEST_COUNT = 18


if __name__ == '__main__':
    unittest.main(verbosity=2)
