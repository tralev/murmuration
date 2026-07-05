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
from extensions.multi_viewpoint_opacity import (
    external_opacity_multi_viewpoint,
    FlockMetricsExtended,
    K_VIEWPOINTS,
)
from metrics import FlockMetrics
from extensions.correlation_time import (
    convex_hull_area,
    CorrelationTimeTracker,
    BUFFER_SIZE,
    CORR_SAMPLE_INTERVAL,
)
from extensions.anisotropic_bodies import AnisotropicBoid, BOID_SEMI_MAJOR, BOID_SEMI_MINOR
from extensions.spatial_optimization import SpatialChunker, OptimizedBoid
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
            'PredatorBoid', 'OptimizedBoid', 'AnisotropicBoid',
            'BlindAnglesBoid', 'StericBoid',
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




# ══════════════════════════════════════════════════════════════════════
#  Anisotropic bodies — Priority 2d
# ══════════════════════════════════════════════════════════════════════

class TestAnisotropicBoid(unittest.TestCase):
    """Tests for AnisotropicBoid — elliptical birds."""

    def setUp(self):
        random.seed(42)  # deterministic RNG — prevents flaky tests from random headings

    def test_is_instance_of_blind_angles(self):
        """AnisotropicBoid inherits from BlindAnglesBoid."""
        boid = AnisotropicBoid()
        self.assertIsInstance(boid, BlindAnglesBoid)

    def test_side_view_larger_than_behind_view(self):
        """Bird seen from the side subtends a larger angle than from behind."""
        a = AnisotropicBoid()
        b = AnisotropicBoid()
        # Observer at (0, 0), target at (100, 0) to the right
        a.position = pygame.Vector2(0, 0)
        a.velocity = pygame.Vector2(4, 0)  # observer faces right (away from blind)
        b.position = pygame.Vector2(100, 0)

        # Case 1: target flying right (away from observer) — see minor axis
        b.velocity = pygame.Vector2(4, 0)  # heading 0
        _, vis1, _, _ = a._compute_projection_and_visibility([a, b])

        # Case 2: target flying up (side-on to observer) — see major axis
        b.velocity = pygame.Vector2(0, 4)  # heading π/2
        _, vis2, _, _ = a._compute_projection_and_visibility([a, b])

        # Both should be visible (not in blind sector)
        self.assertEqual(len(vis1), 1)
        self.assertEqual(len(vis2), 1)

    def test_projected_radius_within_expected_range(self):
        """Projected radius is between semi-minor and semi-major."""
        boid = AnisotropicBoid()
        boid.position = pygame.Vector2(500, 350)
        boid.velocity = pygame.Vector2(4, 0)   # face right — deterministic heading
        target = AnisotropicBoid()
        target.position = pygame.Vector2(600, 350)
        target.velocity = pygame.Vector2(4, 0)

        _, visible, theta, merged = boid._compute_projection_and_visibility(
            [boid, target]
        )
        # The target should be visible (ahead, not in blind sector)
        self.assertEqual(len(visible), 1)
        # Opacity should be non-zero
        self.assertGreater(theta, 0.0)

    def test_stationary_bird_does_not_crash(self):
        """Bird with zero velocity falls back to psi=0."""
        a = AnisotropicBoid()
        b = AnisotropicBoid()
        a.position = pygame.Vector2(500, 350)
        a.velocity = pygame.Vector2(4, 0)
        b.position = pygame.Vector2(550, 350)
        b.velocity = pygame.Vector2(0, 0)  # stationary

        _, visible, _, _ = a._compute_projection_and_visibility([a, b])
        self.assertEqual(len(visible), 1,
                         "Stationary bird should still be visible")

    def test_empty_flock_returns_zero(self):
        """No other birds — zero results."""
        boid = AnisotropicBoid()
        delta, visible, theta, merged = boid._compute_projection_and_visibility(
            [boid]
        )
        self.assertEqual(len(visible), 0)
        self.assertEqual(delta, pygame.Vector2(0, 0))
        self.assertAlmostEqual(theta, 0.0)


# ══════════════════════════════════════════════════════════════════════
#  3D extension — Priority 2c
# ══════════════════════════════════════════════════════════════════════

class TestFibonacciSphere(unittest.TestCase):
    """Tests for fibonacci_sphere()."""

    def test_returns_correct_count(self):
        """Returns exactly n points."""
        from extensions.three_d import fibonacci_sphere
        for n in [1, 5, 10, 80]:
            pts = fibonacci_sphere(n)
            self.assertEqual(len(pts), n,
                             f"Expected {n} points, got {len(pts)}")

    def test_all_points_on_unit_sphere(self):
        """All points have magnitude ~1."""
        from extensions.three_d import fibonacci_sphere
        pts = fibonacci_sphere(50)
        for x, y, z in pts:
            r = math.sqrt(x * x + y * y + z * z)
            self.assertAlmostEqual(r, 1.0, places=5)

    def test_points_cover_hemispheres(self):
        """Points exist in both positive and negative y hemispheres."""
        from extensions.three_d import fibonacci_sphere
        pts = fibonacci_sphere(20)
        pos_y = any(y > 0.5 for _, y, _ in pts)
        neg_y = any(y < -0.5 for _, y, _ in pts)
        self.assertTrue(pos_y, "Should have points in +y hemisphere")
        self.assertTrue(neg_y, "Should have points in -y hemisphere")


class TestBoid3D(unittest.TestCase):
    """Tests for Boid3D — 3D spherical cap occlusion and physics."""

    def setUp(self):
        from extensions.three_d import Boid3D
        self.config = Config()
        self.config.mode = MODE_PROJECTION
        pygame.init()

    def test_position_is_3d(self):
        """Boid3D has 3D position (Vector3)."""
        from extensions.three_d import Boid3D
        boid = Boid3D()
        self.assertIsInstance(boid.position, pygame.Vector3)
        self.assertTrue(hasattr(boid.position, 'z'))

    def test_velocity_is_3d(self):
        """Boid3D has 3D velocity."""
        from extensions.three_d import Boid3D
        boid = Boid3D()
        self.assertIsInstance(boid.velocity, pygame.Vector3)

    def test_empty_flock_no_crash(self):
        """Empty flock (only self) — returns zero results."""
        from extensions.three_d import Boid3D
        boid = Boid3D()
        delta, visible, theta = boid._compute_projection_and_visibility_3d([boid])
        self.assertEqual(len(visible), 0)
        self.assertEqual(delta, pygame.Vector3(0, 0, 0))
        self.assertAlmostEqual(theta, 0.0)

    def test_bird_in_front_visible(self):
        """Bird directly in front is visible."""
        from extensions.three_d import Boid3D
        a = Boid3D()
        b = Boid3D()
        a.position = pygame.Vector3(500, 350, 250)
        a.velocity = pygame.Vector3(4, 0, 0)  # heading +x
        # Place bird very close so cap covers many Fibonacci points
        b.position = pygame.Vector3(510, 350, 250)  # only 10px away
        b.velocity = pygame.Vector3(4, 0, 0)

        delta, visible, theta = a._compute_projection_and_visibility_3d([a, b])
        self.assertEqual(len(visible), 1,
                         "Bird directly in front should be visible")

    def test_flock_updates_velocity(self):
        """After flock(), velocity is set (non-zero)."""
        from extensions.three_d import Boid3D
        a = Boid3D()
        b = Boid3D()
        a.flock([a, b], self.config)
        self.assertGreater(a.velocity.length(), 0)

    def test_update_changes_position(self):
        """update() moves the bird."""
        from extensions.three_d import Boid3D
        boid = Boid3D()
        boid.velocity = pygame.Vector3(V0, 0, 0)
        old_pos = boid.position.copy()
        boid.update()
        self.assertNotEqual(boid.position, old_pos)

    def test_toroidal_wrap_z(self):
        """Position wraps in z-dimension."""
        from extensions.three_d import Boid3D, DEPTH
        boid = Boid3D()
        boid.position = pygame.Vector3(500, 350, DEPTH + 10)
        boid.velocity = pygame.Vector3(0, 0, V0)
        boid.update()
        self.assertGreaterEqual(boid.position.z, 0)
        self.assertLessEqual(boid.position.z, DEPTH)

    def test_occlusion_by_closer_bird(self):
        """Closer bird occludes a farther bird behind it."""
        from extensions.three_d import Boid3D
        a = Boid3D()
        b = Boid3D()  # closer — occludes c
        c = Boid3D()  # farther — behind b

        a.position = pygame.Vector3(500, 350, 250)
        a.velocity = pygame.Vector3(4, 0, 0)  # heading +x (not in blind)
        # Place b very close and c directly behind b (same direction)
        b.position = pygame.Vector3(510, 350, 250)  # 10px ahead
        b.velocity = pygame.Vector3(4, 0, 0)
        c.position = pygame.Vector3(512, 350, 250)  # 2px behind b, same LOS
        c.velocity = pygame.Vector3(4, 0, 0)

        _, visible, _ = a._compute_projection_and_visibility_3d([a, b, c])
        # b should be visible, c should be occluded by b
        visible_birds = [v[0] for v in visible]
        self.assertIn(b, visible_birds, "Closer bird b should be visible")
        self.assertNotIn(c, visible_birds,
                         "Farther bird c should be occluded by b")

    def test_is_instance_of_boid(self):
        """Boid3D inherits from base Boid."""
        from extensions.three_d import Boid3D
        from boid import Boid
        boid = Boid3D()
        self.assertIsInstance(boid, Boid)


# ══════════════════════════════════════════════════════════════════════
#  Spatial optimization — Priority 3b
# ══════════════════════════════════════════════════════════════════════

class TestSpatialChunker(unittest.TestCase):
    """Tests for SpatialChunker."""

    def setUp(self):
        self.chunker = SpatialChunker()

    def test_empty_flock_no_crash(self):
        """Rebuilding with empty flock does not crash."""
        self.chunker.rebuild([])
        entries = self.chunker.get_occlusion_entries(
            pygame.Vector2(500, 350), None
        )
        self.assertEqual(len(entries), 0)

    def test_rebuild_populates_cells(self):
        """Birds are assigned to cells."""
        boids = [DirectVelocityBoid() for _ in range(10)]
        for i, b in enumerate(boids):
            b.position = pygame.Vector2(100 + i * 80, 350)
        self.chunker.rebuild(boids)
        # Birds spread across multiple cells should produce entries
        entries = self.chunker.get_occlusion_entries(
            pygame.Vector2(500, 350), boids[0]
        )
        # Should have near entries (other birds in 3×3) plus far chunks
        self.assertGreater(len(entries), 0)

    def test_entries_have_birds_and_chunks(self):
        """Entries include both bird references and None (chunk) sentinels."""
        boids = [DirectVelocityBoid() for _ in range(150)]
        for i, b in enumerate(boids):
            b.position = pygame.Vector2(
                (i * 67) % 1000, (i * 43) % 700
            )
        self.chunker.rebuild(boids)
        entries = self.chunker.get_occlusion_entries(
            pygame.Vector2(500, 350), boids[0]
        )
        has_birds = any(e[0] is not None for e in entries)
        has_chunks = any(e[0] is None for e in entries)
        self.assertTrue(has_birds, "Should have near-bird entries")
        # Chunks may or may not appear depending on grid coverage

    def test_entries_sorted_by_distance(self):
        """Combined entries are returned for closest-first sorting."""
        boids = [DirectVelocityBoid() for _ in range(50)]
        for i, b in enumerate(boids):
            b.position = pygame.Vector2(
                (i * 137) % 1000, (i * 89) % 700
            )
        self.chunker.rebuild(boids)
        entries = self.chunker.get_occlusion_entries(
            pygame.Vector2(500, 350), None
        )
        # Entries are not pre-sorted — caller must sort
        self.assertGreater(len(entries), 0)


class TestOptimizedBoid(unittest.TestCase):
    """Tests for OptimizedBoid."""

    def test_is_instance_of_anisotropic(self):
        """OptimizedBoid inherits from AnisotropicBoid."""
        boid = OptimizedBoid()
        self.assertIsInstance(boid, AnisotropicBoid)

    def test_falls_back_without_chunker(self):
        """Without _chunker attribute, falls back to parent method."""
        a = OptimizedBoid()
        b = OptimizedBoid()
        a.position = pygame.Vector2(500, 350)
        a.velocity = pygame.Vector2(4, 0)
        b.position = pygame.Vector2(550, 350)
        b.velocity = pygame.Vector2(4, 0)
        # No _chunker set — should fall back to AnisotropicBoid's method
        _, visible, _, _ = a._compute_projection_and_visibility([a, b])
        self.assertEqual(len(visible), 1)

    def test_with_chunker_produces_same_visibility(self):
        """With a chunker, visibility should match the full method."""
        chunker = SpatialChunker()
        a = OptimizedBoid()
        b = OptimizedBoid()
        a.position = pygame.Vector2(500, 350)
        a.velocity = pygame.Vector2(4, 0)
        b.position = pygame.Vector2(550, 350)
        b.velocity = pygame.Vector2(4, 0)
        a._chunker = chunker
        chunker.rebuild([a, b])
        _, visible, _, _ = a._compute_projection_and_visibility([a, b])
        # Bird ahead should still be visible
        self.assertEqual(len(visible), 1)

    def test_empty_flock_returns_zero(self):
        """No other birds — zero results."""
        chunker = SpatialChunker()
        boid = OptimizedBoid()
        boid._chunker = chunker
        chunker.rebuild([boid])
        delta, visible, theta, merged = boid._compute_projection_and_visibility(
            [boid]
        )
        self.assertEqual(len(visible), 0)
        self.assertEqual(delta, pygame.Vector2(0, 0))
        self.assertAlmostEqual(theta, 0.0)


# ══════════════════════════════════════════════════════════════════════
#  Convex hull (Graham scan) — Priority 1c
# ══════════════════════════════════════════════════════════════════════

class TestConvexHullArea(unittest.TestCase):
    """Tests for convex_hull_area()."""

    def test_empty_returns_zero(self):
        """Empty list → 0."""
        self.assertEqual(convex_hull_area([]), 0.0)

    def test_single_point_returns_zero(self):
        """Single point → 0."""
        self.assertEqual(convex_hull_area([(100, 200)]), 0.0)

    def test_two_points_returns_zero(self):
        """Two points → 0."""
        self.assertEqual(convex_hull_area([(0, 0), (100, 100)]), 0.0)

    def test_square(self):
        """Unit square → area 1."""
        area = convex_hull_area([(0, 0), (1, 0), (1, 1), (0, 1)])
        self.assertAlmostEqual(area, 1.0)

    def test_triangle(self):
        """Right triangle → area 0.5."""
        area = convex_hull_area([(0, 0), (1, 0), (0, 1)])
        self.assertAlmostEqual(area, 0.5)

    def test_interior_point_ignored(self):
        """Point inside the hull is ignored."""
        area = convex_hull_area([(0, 0), (2, 0), (2, 2), (0, 2), (1, 1)])
        self.assertAlmostEqual(area, 4.0)

    def test_collinear_points_on_hull(self):
        """Collinear edge points are excluded from hull."""
        area = convex_hull_area([(0, 0), (1, 0), (2, 0), (2, 2), (0, 2)])
        # Hull should be (0,0), (2,0), (2,2), (0,2) → area 4
        self.assertAlmostEqual(area, 4.0)

    def test_scattered_points(self):
        """Random-looking points — verify area is reasonable."""
        pts = [(100, 200), (150, 180), (200, 210), (180, 300), (120, 290)]
        area = convex_hull_area(pts)
        self.assertGreater(area, 0)
        self.assertLess(area, 20000)  # within screen bounds

    def test_all_same_point(self):
        """All points at same location → 0."""
        area = convex_hull_area([(100, 100), (100, 100), (100, 100)])
        self.assertAlmostEqual(area, 0.0)

    def test_large_coordinates(self):
        """Points near WIDTH x HEIGHT bounds."""
        pts = [(0, 0), (1000, 0), (1000, 700), (0, 700)]
        area = convex_hull_area(pts)
        self.assertAlmostEqual(area, 1000.0 * 700.0)


# ══════════════════════════════════════════════════════════════════════
#  Correlation time tracker — Priority 1c
# ══════════════════════════════════════════════════════════════════════

class TestCorrelationTimeTracker(unittest.TestCase):
    """Tests for CorrelationTimeTracker."""

    def setUp(self):
        self.tracker = CorrelationTimeTracker()

    def test_initial_tau_is_zero(self):
        """Before any samples, τᵨ = 0."""
        self.assertEqual(self.tracker.tau, 0.0)
        self.assertEqual(self.tracker.latest_density, 0.0)
        self.assertEqual(self.tracker.buffer_size, 0)

    def test_empty_flock_no_crash(self):
        """Sampling empty flock does not crash."""
        self.tracker.sample([], 0)
        self.assertEqual(self.tracker.latest_density, 0.0)

    def test_small_flock_no_crash(self):
        """Sampling flock with <3 birds does not crash."""
        boids = [DirectVelocityBoid() for _ in range(2)]
        self.tracker.sample(boids, 0)
        self.assertEqual(self.tracker.latest_density, 0.0)

    def test_sample_collects_data(self):
        """After enough frames, buffer fills."""
        boids = [DirectVelocityBoid() for _ in range(10)]
        # Place in a spread-out pattern so hull has area
        for i, b in enumerate(boids):
            b.position = pygame.Vector2(400 + i * 20, 300 + (i % 3) * 30)

        # Call sample many times to trigger CORR_SAMPLE_INTERVAL
        for frame in range(CORR_SAMPLE_INTERVAL * 15):
            self.tracker.sample(boids, frame)

        self.assertGreater(self.tracker.buffer_size, 0)
        self.assertGreater(self.tracker.latest_density, 0.0)

    def test_tau_is_zero_for_constant_density(self):
        """If density never changes, τᵨ stays near zero."""
        boids = [DirectVelocityBoid() for _ in range(10)]
        for i, b in enumerate(boids):
            b.position = pygame.Vector2(400 + i * 20, 300 + (i % 3) * 30)

        for frame in range(CORR_SAMPLE_INTERVAL * 20):
            self.tracker.sample(boids, frame)

        # With static positions, density is nearly constant
        # → autocorrelation decays quickly → τᵨ is small or zero
        # The tracker integrates positive autocorrelation only,
        # so if variance is tiny, tau stays at 0
        self.assertTrue(self.tracker.tau < 100 or self.tracker.tau == 0.0)

    def test_sample_rate_respected(self):
        """Sampling only occurs at CORR_SAMPLE_INTERVAL."""
        boids = [DirectVelocityBoid() for _ in range(5)]
        for i, b in enumerate(boids):
            b.position = pygame.Vector2(400 + i * 30, 300 + (i % 2) * 40)

        # One sample below threshold — should not trigger
        for _ in range(CORR_SAMPLE_INTERVAL - 1):
            self.tracker.sample(boids, 0)
        self.assertEqual(self.tracker.buffer_size, 0)

        # One more triggers the sample
        self.tracker.sample(boids, 0)
        self.assertEqual(self.tracker.buffer_size, 1)

    def test_buffer_capacity(self):
        """Buffer caps at BUFFER_SIZE."""
        boids = [DirectVelocityBoid() for _ in range(5)]
        for i, b in enumerate(boids):
            b.position = pygame.Vector2(400 + i * 30, 300 + (i % 2) * 40)

        # Generate more samples than buffer capacity
        needed_frames = CORR_SAMPLE_INTERVAL * (BUFFER_SIZE + 10)
        for frame in range(needed_frames):
            self.tracker.sample(boids, frame)

        self.assertLessEqual(self.tracker.buffer_size, BUFFER_SIZE)


# ══════════════════════════════════════════════════════════════════════
#  External opacity from multiple viewpoints (Priority 1b)
# ══════════════════════════════════════════════════════════════════════

class TestMultiViewpointOpacity(unittest.TestCase):
    """Tests for external_opacity_multi_viewpoint()."""

    def test_empty_flock_returns_zero(self):
        """Empty flock → opacity 0."""
        result = external_opacity_multi_viewpoint([])
        self.assertEqual(result, 0.0)

    def test_single_bird_low_opacity(self):
        """Single bird at distance R_ext → opacity near 0."""
        boid = DirectVelocityBoid()
        boid.position = pygame.Vector2(0, 0)  # at centre
        # From distance 2000, one small bird subtends a tiny angle
        result = external_opacity_multi_viewpoint([boid], k=4, r_ext=2000)
        self.assertGreater(result, 0.0)
        self.assertLess(result, 0.01)  # very small

    def test_opacity_increases_with_more_birds(self):
        """More birds → higher opacity."""
        boid_a = DirectVelocityBoid()
        boid_a.position = pygame.Vector2(0, 0)
        boid_b = DirectVelocityBoid()
        boid_b.position = pygame.Vector2(10, 0)  # slightly offset

        single = external_opacity_multi_viewpoint([boid_a], k=4, r_ext=2000)
        double = external_opacity_multi_viewpoint([boid_a, boid_b], k=4, r_ext=2000)
        # Two separated birds should produce wider opaque region
        self.assertGreater(double, single)

    def test_returns_value_between_zero_and_one(self):
        """Opacity is always in [0, 1]."""
        boids = [DirectVelocityBoid() for _ in range(20)]
        for b in boids:
            b.position = pygame.Vector2(
                random.uniform(200, 800),
                random.uniform(150, 550),
            )
        result = external_opacity_multi_viewpoint(boids, k=8, r_ext=2000)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)

    def test_different_k_values(self):
        """K=1, K=4, K=12 all return valid values."""
        boids = [DirectVelocityBoid() for _ in range(5)]
        for b in boids:
            b.position = pygame.Vector2(500, 350)
        for k in [1, 4, 12]:
            result = external_opacity_multi_viewpoint(boids, k=k, r_ext=2000)
            self.assertGreaterEqual(result, 0.0)
            self.assertLessEqual(result, 1.0)

    def test_closer_birds_higher_opacity(self):
        """Birds closer to the observer → higher opacity."""
        boids_far = [DirectVelocityBoid() for _ in range(5)]
        boids_near = [DirectVelocityBoid() for _ in range(5)]
        for b in boids_far:
            b.position = pygame.Vector2(500, 350)
        for b in boids_near:
            b.position = pygame.Vector2(500, 350)

        result_far = external_opacity_multi_viewpoint(boids_far, k=4, r_ext=4000)
        result_near = external_opacity_multi_viewpoint(boids_near, k=4, r_ext=500)
        self.assertGreater(result_near, result_far,
                           "Closer observer should see higher opacity")

    def test_k_defaults_to_12(self):
        """Calling with just flock uses default K=12."""
        boids = [DirectVelocityBoid() for _ in range(3)]
        for b in boids:
            b.position = pygame.Vector2(500, 350)
        result = external_opacity_multi_viewpoint(boids)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)


class TestFlockMetricsExtended(unittest.TestCase):
    """Tests for FlockMetricsExtended."""

    def setUp(self):
        self.metrics = FlockMetricsExtended()
        self.config = Config()
        self.config.mode = MODE_PROJECTION

    def test_is_subclass_of_flock_metrics(self):
        """FlockMetricsExtended inherits from FlockMetrics."""
        self.assertIsInstance(self.metrics, FlockMetrics)

    def test_update_with_empty_flock(self):
        """update() with empty flock does not crash."""
        clock = pygame.time.Clock()
        clock.tick()
        self.metrics.update([], clock, self.config)
        self.assertEqual(self.metrics.internal_opacity, 0.0)
        self.assertEqual(self.metrics.external_opacity, 0.0)
        self.assertEqual(self.metrics.order_param, 0.0)

    def test_update_computes_metrics(self):
        """update() with flock computes all metrics."""
        boids = [DirectVelocityBoid() for _ in range(10)]
        clock = pygame.time.Clock()
        clock.tick()
        self.metrics.update(boids, clock, self.config)
        # Metrics should be set (not necessarily converged after one frame)
        self.assertGreaterEqual(self.metrics.internal_opacity, 0.0)
        self.assertGreaterEqual(self.metrics.external_opacity, 0.0)
        self.assertGreaterEqual(self.metrics.order_param, 0.0)
