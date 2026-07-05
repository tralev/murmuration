"""
Unit tests for roadmap extensions in extensions/.

Covers:
  - _interval_in_blind_region   — blind sector containment check
  - DirectVelocityBoid          — mode stashing, direct velocity, update
  - StericBoid                  — steric repulsion between nearby boids
  - BlindAnglesBoid             — blind-angle filtering in occlusion
  - Predator                    — init, update, speed clamp, wrap, pursuit
  - PredatorBoid                — predator flight response
  - Inheritance chain           — MRO correctness
"""

import math
import random
import sys
import unittest

import pygame

from extensions.blind_angles import (
    _interval_in_blind_region,
    BlindAnglesBoid,
    BLIND_ANGLE,
)
from extensions.direct_velocity import DirectVelocityBoid
from extensions.steric_repulsion import StericBoid, STERIC_RADIUS, PHI_STERIC
from extensions.predator import (
    Predator,
    PredatorBoid,
    DANGER_RADIUS,
    PREDATOR_SPEED,
    FLIGHT_FORCE,
)
from flock_core import (
    WIDTH, HEIGHT, V0, BOID_SIZE,
    MODE_PROJECTION, MODE_SPATIAL,
    Config,
)

TWO_PI = 2 * math.pi


# ══════════════════════════════════════════════════════════════════════
#  _interval_in_blind_region
# ══════════════════════════════════════════════════════════════════════

class TestIntervalInBlindRegion(unittest.TestCase):
    """Tests for _interval_in_blind_region(start, end, blind_start, blind_end)."""

    # ── Non-wrapping blind region (blind_start ≤ blind_end) ────────

    def test_fully_inside_non_wrapping(self):
        """Interval entirely inside a non-wrapping blind region."""
        self.assertTrue(_interval_in_blind_region(1.5, 2.0, 1.0, 3.0))

    def test_fully_outside_before_non_wrapping(self):
        """Interval entirely before the blind region."""
        self.assertFalse(_interval_in_blind_region(0.0, 0.5, 1.0, 3.0))

    def test_fully_outside_after_non_wrapping(self):
        """Interval entirely after the blind region."""
        self.assertFalse(_interval_in_blind_region(3.5, 4.0, 1.0, 3.0))

    def test_partially_overlapping_start_non_wrapping(self):
        """Interval starts inside but extends past the blind region."""
        self.assertFalse(_interval_in_blind_region(2.0, 3.5, 1.0, 3.0))

    def test_partially_overlapping_end_non_wrapping(self):
        """Interval starts before but ends inside the blind region."""
        self.assertFalse(_interval_in_blind_region(0.5, 2.0, 1.0, 3.0))

    def test_exact_boundaries_non_wrapping(self):
        """Interval exactly matches blind region boundaries."""
        self.assertTrue(_interval_in_blind_region(1.0, 3.0, 1.0, 3.0))

    def test_epsilon_tolerance_non_wrapping(self):
        """Interval slightly inside blind region boundaries (within epsilon)."""
        self.assertTrue(_interval_in_blind_region(1.0 + 1e-10, 3.0 - 1e-10, 1.0, 3.0))

    # ── Wrapping blind region (blind_start > blind_end) ────────────
    #  e.g., blind_start = 5.5, blind_end = 0.8 (wraps around 2π)

    def test_fully_inside_segment1_wrapping(self):
        """Interval fully inside first segment: [blind_start, 2π)."""
        self.assertTrue(_interval_in_blind_region(5.8, 6.2, 5.5, 0.8))

    def test_fully_inside_segment2_wrapping(self):
        """Interval fully inside second segment: [0, blind_end]."""
        self.assertTrue(_interval_in_blind_region(0.1, 0.5, 5.5, 0.8))

    def test_fully_outside_wrapping(self):
        """Interval in the gap between the two segments."""
        self.assertFalse(_interval_in_blind_region(2.0, 3.0, 5.5, 0.8))

    def test_crosses_segment_gap_wrapping(self):
        """Interval spans from first segment into the gap — not fully inside."""
        self.assertFalse(_interval_in_blind_region(5.0, 6.0, 5.5, 0.8))

    def test_exact_boundaries_segment1_wrapping(self):
        """Interval exactly matches first segment boundaries."""
        self.assertTrue(_interval_in_blind_region(5.5, TWO_PI, 5.5, 0.8))
        # Note: end == 2π exactly is the boundary

    def test_exact_boundaries_segment2_wrapping(self):
        """Interval exactly matches second segment boundaries."""
        self.assertTrue(_interval_in_blind_region(0.0, 0.8, 5.5, 0.8))

    # ── Edge cases ─────────────────────────────────────────────────

    def test_degenerate_zero_width_interval(self):
        """Zero-width interval (start == end) inside blind region."""
        self.assertTrue(_interval_in_blind_region(1.5, 1.5, 1.0, 3.0))

    def test_degenerate_zero_width_outside(self):
        """Zero-width interval outside blind region."""
        self.assertFalse(_interval_in_blind_region(0.5, 0.5, 1.0, 3.0))

    def test_full_circle_blind_region(self):
        """Blind region covers entire [0, 2π) — everything is in blind."""
        self.assertTrue(_interval_in_blind_region(1.0, 2.0, 0.0, TWO_PI))

    def test_full_circle_wrapping(self):
        """Blind region covers the full circle via wrap [0.01, 0.0]."""
        self.assertTrue(_interval_in_blind_region(3.0, 4.0, 0.01, 0.0))

    def test_half_circle_blind_each_side(self):
        """Interval in the middle, blind regions on both sides."""
        self.assertFalse(_interval_in_blind_region(2.0, 4.0, 1.0, 1.5))


# ══════════════════════════════════════════════════════════════════════
#  DirectVelocityBoid
# ══════════════════════════════════════════════════════════════════════

class TestDirectVelocityBoid(unittest.TestCase):
    """Tests for DirectVelocityBoid — mode stashing, direct velocity setting."""

    def setUp(self):
        self.config = Config()
        self.boid = DirectVelocityBoid()

    def test_mode_stashed_in_projection(self):
        """flock() stashes _current_mode == MODE_PROJECTION."""
        self.config.mode = MODE_PROJECTION
        self.boid.flock([self.boid], self.config)
        self.assertEqual(self.boid._current_mode, MODE_PROJECTION)

    def test_mode_stashed_in_spatial(self):
        """flock() stashes _current_mode == MODE_SPATIAL."""
        self.config.mode = MODE_SPATIAL
        other = DirectVelocityBoid()
        from flock_core import SpatialGrid, VISUAL_RANGE
        grid = SpatialGrid(cell_size=VISUAL_RANGE)
        grid.rebuild([self.boid, other])
        self.boid.flock([self.boid, other], self.config, grid)
        self.assertEqual(self.boid._current_mode, MODE_SPATIAL)

    def test_update_projection_moves_position(self):
        """update() in projection mode adds velocity to position."""
        self.boid._current_mode = MODE_PROJECTION
        self.boid.velocity = pygame.Vector2(V0, 0)
        old_pos = self.boid.position.copy()
        self.boid.update()
        self.assertAlmostEqual(self.boid.position.x, old_pos.x + V0)
        self.assertAlmostEqual(self.boid.position.y, old_pos.y)

    def test_update_projection_no_speed_clamp(self):
        """update() in projection mode does NOT clamp speed."""
        self.boid._current_mode = MODE_PROJECTION
        # Set velocity above V0 — should stay above V0 (no clamping)
        self.boid.velocity = pygame.Vector2(V0 * 100, 0)
        self.boid.update()
        self.assertGreater(self.boid.velocity.length(), V0)

    def test_update_projection_clears_acceleration(self):
        """update() in projection mode zeros acceleration."""
        self.boid._current_mode = MODE_PROJECTION
        self.boid.acceleration = pygame.Vector2(5, 5)
        self.boid.update()
        self.assertEqual(self.boid.acceleration.length(), 0.0)

    def test_update_ignores_acceleration(self):
        """update() in projection mode does NOT add acceleration to velocity."""
        self.boid._current_mode = MODE_PROJECTION
        self.boid.velocity = pygame.Vector2(V0, 0)
        self.boid.acceleration = pygame.Vector2(-100, 0)  # large opposing force
        self.boid.update()
        # Velocity should still be (V0, 0) — acceleration was NOT applied
        self.assertAlmostEqual(self.boid.velocity.x, V0)
        self.assertAlmostEqual(self.boid.velocity.y, 0.0)

    def test_update_projection_toroidal_wrap_left(self):
        """Position wraps from left edge to right."""
        self.boid._current_mode = MODE_PROJECTION
        self.boid.position = pygame.Vector2(-10, HEIGHT // 2)
        self.boid.velocity = pygame.Vector2(-V0, 0)
        self.boid.update()
        self.assertAlmostEqual(self.boid.position.x, WIDTH)

    def test_update_projection_toroidal_wrap_right(self):
        """Position wraps from right edge to left."""
        self.boid._current_mode = MODE_PROJECTION
        self.boid.position = pygame.Vector2(WIDTH + 10, HEIGHT // 2)
        self.boid.velocity = pygame.Vector2(V0, 0)
        self.boid.update()
        self.assertAlmostEqual(self.boid.position.x, 0)

    def test_update_spatial_falls_back(self):
        """update() in spatial mode uses parent Euler integration."""
        self.boid._current_mode = MODE_SPATIAL
        self.boid.velocity = pygame.Vector2(V0, 0)
        self.boid.acceleration = pygame.Vector2(0, 0)
        self.boid.update()
        # In spatial mode, parent.update() does speed clamping
        # Velocity should still be at V0 (already at V0)
        self.assertAlmostEqual(self.boid.velocity.length(), V0, places=1)

    def test_no_current_mode_falls_back(self):
        """If _current_mode is not set, update() falls back to parent."""
        # Don't call flock() — _current_mode is not set
        # Set speed well below 0.3*V0 so parent clamping kicks in
        self.boid.velocity = pygame.Vector2(V0 * 0.1, 0)
        self.boid.acceleration = pygame.Vector2(0, 0)
        self.boid.update()
        # Falls back to parent: parent clamps speed to 0.3*V0
        self.assertAlmostEqual(self.boid.velocity.length(), V0 * 0.3, places=1)


# ══════════════════════════════════════════════════════════════════════
#  StericBoid
# ══════════════════════════════════════════════════════════════════════

class TestStericBoid(unittest.TestCase):
    """Tests for StericBoid — steric repulsion between nearby boids."""

    def setUp(self):
        self.config = Config()
        self.config.mode = MODE_PROJECTION
        random.seed(42)  # fixed seed to avoid non-deterministic noise

    def test_no_repulsion_when_alone(self):
        """Single boid: no steric repulsion applied (no neighbours)."""
        boid = StericBoid()
        old_vel = boid.velocity.copy()
        boid.flock([boid], self.config)
        # flock() calls _flock_projection which runs steric check
        # Velocity should still be set to V0 after projection
        self.assertAlmostEqual(boid.velocity.length(), V0, places=1)

    def test_repulsion_when_very_close(self):
        """Two boids at distance < STERIC_RADIUS: velocities diverge."""
        boid_a = StericBoid()
        boid_b = StericBoid()
        # Place them very close together
        boid_a.position = pygame.Vector2(500, 350)
        boid_b.position = pygame.Vector2(500 + STERIC_RADIUS * 0.5, 350)
        boid_a.velocity = pygame.Vector2(V0, 0)
        boid_b.velocity = pygame.Vector2(-V0, 0)

        boid_a.flock([boid_a, boid_b], self.config)
        boid_a._current_mode = MODE_PROJECTION
        boid_a.update()

        # After steric repulsion + update, boid_a and boid_b should
        # no longer be at distance < STERIC_RADIUS (they were pushed apart)
        new_dist = boid_a.position.distance_to(boid_b.position)
        initial_dist = STERIC_RADIUS * 0.5
        self.assertGreater(new_dist, initial_dist,
                           "Steric repulsion should increase distance between boids")

    def test_no_repulsion_when_distant(self):
        """Two boids at distance > STERIC_RADIUS: position unchanged by steric."""
        boid_a = StericBoid()
        boid_b = StericBoid()
        boid_a.position = pygame.Vector2(500, 350)
        boid_b.position = pygame.Vector2(500 + STERIC_RADIUS * 2, 350)
        boid_a.velocity = pygame.Vector2(V0, 0)
        boid_b.velocity = pygame.Vector2(-V0, 0)

        boid_a.flock([boid_a, boid_b], self.config)
        boid_a._current_mode = MODE_PROJECTION
        boid_a.update()

        # After update, distance between boids should not have decreased
        # (no steric pull, only movement from flocking)
        new_dist = boid_a.position.distance_to(boid_b.position)
        self.assertGreater(new_dist, STERIC_RADIUS,
                           "Distant boids should not be pulled together by steric")


# ══════════════════════════════════════════════════════════════════════
#  BlindAnglesBoid
# ══════════════════════════════════════════════════════════════════════

class TestBlindAnglesBoid(unittest.TestCase):
    """Tests for BlindAnglesBoid — blind-angle filtering in occlusion."""

    def setUp(self):
        self.config = Config()
        self.config.mode = MODE_PROJECTION

    def test_bird_behind_not_visible(self):
        """Bird directly behind (in blind sector) → not visible."""
        boid_a = BlindAnglesBoid()
        boid_b = BlindAnglesBoid()
        # boid_a faces right (velocity →)
        boid_a.position = pygame.Vector2(500, 350)
        boid_a.velocity = pygame.Vector2(V0, 0)
        # boid_b is behind boid_a (to the left) — in blind sector
        boid_b.position = pygame.Vector2(450, 350)
        boid_b.velocity = pygame.Vector2(V0, 0)

        # Compute visibility: boid_b should be filtered out
        delta, visible, theta, merged = boid_a._compute_projection_and_visibility(
            [boid_a, boid_b]
        )
        self.assertEqual(len(visible), 0,
                         "Bird directly behind should be in blind sector")

    def test_bird_in_front_visible(self):
        """Bird directly in front → visible (not in blind sector)."""
        boid_a = BlindAnglesBoid()
        boid_b = BlindAnglesBoid()
        boid_a.position = pygame.Vector2(500, 350)
        boid_a.velocity = pygame.Vector2(V0, 0)
        # boid_b is in front of boid_a (to the right)
        boid_b.position = pygame.Vector2(550, 350)
        boid_b.velocity = pygame.Vector2(V0, 0)

        delta, visible, theta, merged = boid_a._compute_projection_and_visibility(
            [boid_a, boid_b]
        )
        self.assertEqual(len(visible), 1,
                         "Bird directly in front should be visible")

    def test_bird_to_side_visible(self):
        """Bird at 90° (side) → visible (outside 60° blind sector)."""
        boid_a = BlindAnglesBoid()
        boid_b = BlindAnglesBoid()
        boid_a.position = pygame.Vector2(500, 350)
        boid_a.velocity = pygame.Vector2(V0, 0)
        # boid_b is directly above (90° from heading)
        boid_b.position = pygame.Vector2(500, 300)
        boid_b.velocity = pygame.Vector2(V0, 0)

        delta, visible, theta, merged = boid_a._compute_projection_and_visibility(
            [boid_a, boid_b]
        )
        self.assertEqual(len(visible), 1,
                         "Bird at 90° (side) should be visible")

    def test_no_boids_no_crash(self):
        """Empty boids list (only self) → returns zero vectors."""
        boid = BlindAnglesBoid()
        delta, visible, theta, merged = boid._compute_projection_and_visibility([boid])
        self.assertEqual(len(visible), 0)
        self.assertEqual(delta, pygame.Vector2(0, 0))
        self.assertAlmostEqual(theta, 0.0)
        self.assertEqual(merged, [])


# ══════════════════════════════════════════════════════════════════════
#  Predator
# ══════════════════════════════════════════════════════════════════════

class TestPredator(unittest.TestCase):
    """Tests for Predator — init, update, speed clamp, toroidal wrap."""

    def test_init_spawns_at_edge(self):
        """Predator spawns outside the main simulation area."""
        predator = Predator()
        # Position should be outside [0, WIDTH] x [0, HEIGHT]
        outside_x = predator.position.x < 0 or predator.position.x > WIDTH
        outside_y = predator.position.y < 0 or predator.position.y > HEIGHT
        self.assertTrue(outside_x or outside_y,
                        f"Predator should spawn at edge, got {predator.position}")

    def test_init_has_velocity(self):
        """Predator starts with non-zero velocity."""
        predator = Predator()
        self.assertGreater(predator.velocity.length(), 0)

    def test_update_empty_flock_no_crash(self):
        """update() with empty flock does not crash."""
        predator = Predator()
        old_pos = predator.position.copy()
        predator.update([])
        # Position should not change (no target to pursue)
        self.assertEqual(predator.position, old_pos)

    def test_update_pursues_nearest_bird(self):
        """Predator accelerates toward the nearest bird."""
        predator = Predator()
        predator.position = pygame.Vector2(500, 350)
        predator.velocity = pygame.Vector2(0, 0)
        predator.acceleration = pygame.Vector2(0, 0)

        # Create a mock boid at (600, 350) — to the right
        mock_boid = DirectVelocityBoid()
        mock_boid.position = pygame.Vector2(600, 350)

        predator.update([mock_boid])

        # Predator should have accelerated toward the boid (positive x)
        self.assertGreater(predator.velocity.x, 0,
                           "Predator should accelerate toward nearest bird")

    def test_update_pursues_nearest_of_two(self):
        """Predator pursues the nearest of two birds."""
        predator = Predator()
        predator.position = pygame.Vector2(500, 350)
        predator.velocity = pygame.Vector2(0, 0)
        predator.acceleration = pygame.Vector2(0, 0)

        near_boid = DirectVelocityBoid()
        near_boid.position = pygame.Vector2(510, 350)  # 10px away — nearest
        far_boid = DirectVelocityBoid()
        far_boid.position = pygame.Vector2(900, 350)    # 400px away

        predator.update([near_boid, far_boid])

        # Predator should accelerate toward nearest (positive x toward 510)
        self.assertGreater(predator.velocity.x, 0)

    def test_speed_clamped_to_max(self):
        """Predator speed is clamped to PREDATOR_SPEED."""
        predator = Predator()
        predator.position = pygame.Vector2(500, 350)
        # Set velocity above max
        predator.velocity = pygame.Vector2(PREDATOR_SPEED * 3, 0)
        predator.acceleration = pygame.Vector2(0, 0)

        mock_boid = DirectVelocityBoid()
        mock_boid.position = pygame.Vector2(600, 350)
        predator.update([mock_boid])

        self.assertLessEqual(predator.velocity.length(), PREDATOR_SPEED + 1e-6)

    def test_speed_has_minimum_floor(self):
        """Predator speed does not drop below 0.3 * PREDATOR_SPEED."""
        predator = Predator()
        predator.position = pygame.Vector2(500, 350)
        predator.velocity = pygame.Vector2(0.01, 0)  # nearly zero
        predator.acceleration = pygame.Vector2(0, 0)

        mock_boid = DirectVelocityBoid()
        mock_boid.position = pygame.Vector2(500, 350)  # at same position
        predator.update([mock_boid])

        self.assertGreaterEqual(predator.velocity.length(),
                                PREDATOR_SPEED * 0.3 - 1e-6)

    def test_toroidal_wrap_right(self):
        """Predator wraps from right edge to left."""
        predator = Predator()
        predator.position = pygame.Vector2(WIDTH + 20, 350)
        predator.velocity = pygame.Vector2(V0, 0)
        predator.acceleration = pygame.Vector2(0, 0)

        mock_boid = DirectVelocityBoid()
        mock_boid.position = pygame.Vector2(500, 350)

        predator.update([mock_boid])
        self.assertLess(predator.position.x, WIDTH)

    def test_toroidal_wrap_left(self):
        """Predator wraps from left edge to right."""
        predator = Predator()
        predator.position = pygame.Vector2(-20, 350)
        predator.velocity = pygame.Vector2(-V0, 0)
        predator.acceleration = pygame.Vector2(0, 0)

        mock_boid = DirectVelocityBoid()
        mock_boid.position = pygame.Vector2(500, 350)

        predator.update([mock_boid])
        self.assertGreaterEqual(predator.position.x, 0)


# ══════════════════════════════════════════════════════════════════════
#  PredatorBoid
# ══════════════════════════════════════════════════════════════════════

class TestPredatorBoid(unittest.TestCase):
    """Tests for PredatorBoid — predator flight response."""

    def setUp(self):
        self.boid = PredatorBoid()
        self.predator = Predator()
        self.boid.velocity = pygame.Vector2(V0, 0)

    def test_no_response_when_predator_far(self):
        """Predator beyond DANGER_RADIUS → no flight response."""
        self.boid.position = pygame.Vector2(500, 350)
        self.predator.position = pygame.Vector2(
            500 + DANGER_RADIUS + 100, 350
        )
        old_vel = self.boid.velocity.copy()
        self.boid.apply_predator_response(self.predator)
        self.assertEqual(self.boid.velocity, old_vel)

    def test_flight_when_predator_nearby(self):
        """Predator within DANGER_RADIUS → bird flees away."""
        self.boid.position = pygame.Vector2(500, 350)
        # Place predator ABOVE the bird so flight force has a perpendicular
        # component — avoids collinear cancellation with re-normalization.
        self.predator.position = pygame.Vector2(
            500, 350 - DANGER_RADIUS * 0.5  # predator above
        )
        self.boid.apply_predator_response(self.predator)
        # Bird should flee downward (away from predator above) — velocity.y > 0
        self.assertGreater(self.boid.velocity.y, 0,
                           "Bird should flee away from predator (downward)")

    def test_flight_stronger_when_closer(self):
        """Closer predator → larger directional change."""
        self.boid.position = pygame.Vector2(500, 350)

        # Predator above at 80% of danger radius — weaker flight
        self.predator.position = pygame.Vector2(
            500, 350 - DANGER_RADIUS * 0.8  # predator above, farther
        )
        self.boid.velocity = pygame.Vector2(V0, 0)
        self.boid.apply_predator_response(self.predator)
        # Measure how much the direction changed from original (0°)
        angle_far = abs(math.atan2(self.boid.velocity.y, self.boid.velocity.x))

        # Predator above at 20% of danger radius — stronger flight
        self.boid.position = pygame.Vector2(500, 350)
        self.predator.position = pygame.Vector2(
            500, 350 - DANGER_RADIUS * 0.2  # predator above, closer
        )
        self.boid.velocity = pygame.Vector2(V0, 0)
        self.boid.apply_predator_response(self.predator)
        angle_near = abs(math.atan2(self.boid.velocity.y, self.boid.velocity.x))

        self.assertGreater(angle_near, angle_far,
                           "Closer predator should cause larger directional change")

    def test_velocity_re_normalized_to_v0(self):
        """After flight response, velocity magnitude is V0."""
        self.boid.position = pygame.Vector2(500, 350)
        self.predator.position = pygame.Vector2(
            500 + DANGER_RADIUS * 0.5, 350
        )
        self.boid.velocity = pygame.Vector2(V0, 0)
        self.boid.apply_predator_response(self.predator)
        self.assertAlmostEqual(self.boid.velocity.length(), V0, places=1)

    def test_no_response_with_none_predator(self):
        """None predator → no flight response, no crash."""
        old_vel = self.boid.velocity.copy()
        self.boid.apply_predator_response(None)
        self.assertEqual(self.boid.velocity, old_vel)

    def test_no_response_when_predator_at_same_spot(self):
        """Predator at exact same position (d=0) → no crash."""
        self.boid.position = pygame.Vector2(500, 350)
        self.predator.position = pygame.Vector2(500, 350)
        old_vel = self.boid.velocity.copy()
        self.boid.apply_predator_response(self.predator)
        # d < 0.001 → no flight applied
        self.assertEqual(self.boid.velocity, old_vel)


# ══════════════════════════════════════════════════════════════════════
#  Inheritance chain
# ══════════════════════════════════════════════════════════════════════

class TestInheritanceChain(unittest.TestCase):
    """Verify that the extension class hierarchy is correct."""

    def test_predator_boid_is_direct_velocity(self):
        """PredatorBoid is an instance of DirectVelocityBoid."""
        boid = PredatorBoid()
        self.assertIsInstance(boid, DirectVelocityBoid)

    def test_predator_boid_is_steric(self):
        """PredatorBoid is an instance of StericBoid."""
        boid = PredatorBoid()
        self.assertIsInstance(boid, StericBoid)

    def test_predator_boid_is_blind_angles(self):
        """PredatorBoid is an instance of BlindAnglesBoid."""
        boid = PredatorBoid()
        self.assertIsInstance(boid, BlindAnglesBoid)

    def test_predator_boid_is_boid(self):
        """PredatorBoid is an instance of the base Boid."""
        from boid import Boid
        boid = PredatorBoid()
        self.assertIsInstance(boid, Boid)

    def test_steric_is_direct_velocity(self):
        """StericBoid is an instance of DirectVelocityBoid."""
        boid = StericBoid()
        self.assertIsInstance(boid, DirectVelocityBoid)

    def test_blind_angles_is_steric(self):
        """BlindAnglesBoid is an instance of StericBoid."""
        boid = BlindAnglesBoid()
        self.assertIsInstance(boid, StericBoid)

    def test_mro_linear(self):
        """Method resolution order follows the expected chain."""
        mro = [c.__name__ for c in PredatorBoid.__mro__
               if c.__name__ not in ('object',)]
        expected = [
            'PredatorBoid', 'BlindAnglesBoid', 'StericBoid',
            'DirectVelocityBoid', 'Boid',
        ]
        for cls_name in expected:
            self.assertIn(cls_name, mro)


# ══════════════════════════════════════════════════════════════════════
#  Integration: end-to-end blind angle occlusion workflow
# ══════════════════════════════════════════════════════════════════════

class TestBlindOcclusionWorkflow(unittest.TestCase):
    """
    Integration test: verify that the blind-angle filtering + occlusion
    pipeline works as expected end-to-end.
    """

    def test_visible_bird_not_filtered(self):
        """
        Bird at 0° (ahead) with blind sector at 180° (behind):
        the bird ahead should be visible.
        """
        boid_a = BlindAnglesBoid()
        boid_b = BlindAnglesBoid()
        boid_a.position = pygame.Vector2(500, 350)
        boid_a.velocity = pygame.Vector2(V0, 0)  # heading right (0°)
        boid_b.position = pygame.Vector2(560, 350)  # 60px ahead
        boid_b.velocity = pygame.Vector2(V0, 0)

        delta, visible, theta, merged = boid_a._compute_projection_and_visibility(
            [boid_a, boid_b]
        )
        self.assertEqual(len(visible), 1)

    def test_two_birds_one_behind_one_ahead(self):
        """
        Bird behind is filtered by blind sector; bird ahead is visible.
        """
        boid_a = BlindAnglesBoid()
        boid_b = BlindAnglesBoid()  # behind (in blind)
        boid_c = BlindAnglesBoid()  # ahead (visible)

        boid_a.position = pygame.Vector2(500, 350)
        boid_a.velocity = pygame.Vector2(V0, 0)
        boid_b.position = pygame.Vector2(440, 350)  # 60px behind
        boid_b.velocity = pygame.Vector2(V0, 0)
        boid_c.position = pygame.Vector2(560, 350)  # 60px ahead
        boid_c.velocity = pygame.Vector2(V0, 0)

        delta, visible, theta, merged = boid_a._compute_projection_and_visibility(
            [boid_a, boid_b, boid_c]
        )
        self.assertEqual(len(visible), 1, "Only the bird ahead should be visible")
        self.assertIs(visible[0][0], boid_c, "The visible bird should be boid_c")


if __name__ == "__main__":
    unittest.main(verbosity=2)
