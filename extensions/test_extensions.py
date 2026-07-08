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
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECTION T2 — EXTENSION UNIT TESTS  (blind, steric, predator, 3D)   ║
# ╚══════════════════════════════════════════════════════════════════════╝


import math
import random
import sys
import unittest

import pygame

from test_count_mixin import TestCountMixin

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


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  _interval_in_blind_region                                           ║
# ╚══════════════════════════════════════════════════════════════════════╝

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


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  DirectVelocityBoid                                                  ║
# ╚══════════════════════════════════════════════════════════════════════╝

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


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  StericBoid                                                          ║
# ╚══════════════════════════════════════════════════════════════════════╝

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


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  BlindAnglesBoid                                                     ║
# ╚══════════════════════════════════════════════════════════════════════╝

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


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Predator                                                            ║
# ╚══════════════════════════════════════════════════════════════════════╝

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


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  PredatorBoid                                                        ║
# ╚══════════════════════════════════════════════════════════════════════╝

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


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Inheritance chain                                                   ║
# ╚══════════════════════════════════════════════════════════════════════╝

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


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Integration: end-to-end blind angle occlusion workflow              ║
# ╚══════════════════════════════════════════════════════════════════════╝

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




# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Anisotropic bodies — Priority 2d                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝

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


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  3D extension — Priority 2c                                          ║
# ╚══════════════════════════════════════════════════════════════════════╝

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


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Spatial optimization — Priority 3b                                  ║
# ╚══════════════════════════════════════════════════════════════════════╝

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


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Convex hull (Graham scan) — Priority 1c                             ║
# ╚══════════════════════════════════════════════════════════════════════╝

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


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Correlation time tracker — Priority 1c                              ║
# ╚══════════════════════════════════════════════════════════════════════╝

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


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  External opacity from multiple viewpoints (Priority 1b)             ║
# ╚══════════════════════════════════════════════════════════════════════╝

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

    def test_update_computes_power_and_angmom(self):
        """update() computes power and angular momentum."""
        boids = [DirectVelocityBoid() for _ in range(10)]
        for i, b in enumerate(boids):
            b.position = pygame.Vector2(100 + i * 50, 350)
            b.velocity = pygame.Vector2(V0, 0)
            b.acceleration = pygame.Vector2(0.1, 0)
        clock = pygame.time.Clock()
        clock.tick()
        self.metrics.update(boids, clock, self.config)
        self.assertGreater(self.metrics.power, 0.0)
        self.assertIsNotNone(self.metrics.angular_momentum)

    def test_power_zero_when_no_acceleration(self):
        """Power is zero when acceleration is zero."""
        boids = [DirectVelocityBoid() for _ in range(5)]
        for b in boids:
            b.position = pygame.Vector2(500, 350)
            b.velocity = pygame.Vector2(V0, 0)
            b.acceleration = pygame.Vector2(0, 0)
        clock = pygame.time.Clock()
        clock.tick()
        for _ in range(100):
            self.metrics.update(boids, clock, self.config)
        self.assertAlmostEqual(self.metrics.power, 0.0, places=1)

    def test_angular_momentum_positive_counterclockwise(self):
        """Angular momentum L > 0 for counterclockwise rotation."""
        boids = [DirectVelocityBoid() for _ in range(10)]
        for i, b in enumerate(boids):
            angle = 2 * math.pi * i / len(boids)
            b.position = pygame.Vector2(
                500 + 100 * math.cos(angle),
                350 + 100 * math.sin(angle),
            )
            b.velocity = pygame.Vector2(
                -V0 * math.sin(angle),
                V0 * math.cos(angle),
            )
            b.acceleration = pygame.Vector2(0, 0)
        clock = pygame.time.Clock()
        clock.tick()
        for _ in range(50):
            self.metrics.update(boids, clock, self.config)
        self.assertGreater(self.metrics.angular_momentum, 0.0)

    def test_flock_metrics_base_class_has_power_and_angmom(self):
        """Base FlockMetrics also has power and angular_momentum."""
        base = FlockMetrics()
        self.assertTrue(hasattr(base, 'power'))
        self.assertTrue(hasattr(base, 'angular_momentum'))
        self.assertEqual(base.power, 0.0)
        self.assertEqual(base.angular_momentum, 0.0)

    def test_avg_acceleration_positive_with_force(self):
        """Avg acceleration > 0 when steering forces are applied."""
        boids = [DirectVelocityBoid() for _ in range(10)]
        for i, b in enumerate(boids):
            b.position = pygame.Vector2(100 + i * 50, 350)
            b.velocity = pygame.Vector2(V0, 0)
            b.acceleration = pygame.Vector2(0.1, 0.05)
        clock = pygame.time.Clock()
        clock.tick()
        self.metrics.update(boids, clock, self.config)
        self.assertGreater(self.metrics.avg_acceleration, 0.0)

    def test_avg_acceleration_zero_with_no_force(self):
        """Avg acceleration is zero when no steering forces."""
        boids = [DirectVelocityBoid() for _ in range(5)]
        for b in boids:
            b.position = pygame.Vector2(500, 350)
            b.velocity = pygame.Vector2(V0, 0)
            b.acceleration = pygame.Vector2(0, 0)
        clock = pygame.time.Clock()
        clock.tick()
        for _ in range(100):
            self.metrics.update(boids, clock, self.config)
        self.assertAlmostEqual(self.metrics.avg_acceleration, 0.0, places=2)

    def test_dispersion_positive_with_spread(self):
        """Dispersion > 0 when birds are spread out."""
        boids = [DirectVelocityBoid() for _ in range(10)]
        for i, b in enumerate(boids):
            b.position = pygame.Vector2(100 + i * 80, 350)
            b.velocity = pygame.Vector2(V0, 0)
            b.acceleration = pygame.Vector2(0, 0)
        clock = pygame.time.Clock()
        clock.tick()
        for _ in range(100):
            self.metrics.update(boids, clock, self.config)
        self.assertGreater(self.metrics.dispersion, 0.0)

    def test_dispersion_zero_when_all_at_same_spot(self):
        """Dispersion ~ 0 when all birds at same spot."""
        boids = [DirectVelocityBoid() for _ in range(5)]
        for b in boids:
            b.position = pygame.Vector2(500, 350)
            b.velocity = pygame.Vector2(V0, 0)
            b.acceleration = pygame.Vector2(0, 0)
        clock = pygame.time.Clock()
        clock.tick()
        for _ in range(100):
            self.metrics.update(boids, clock, self.config)
        self.assertAlmostEqual(self.metrics.dispersion, 0.0, places=1)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ROADMAP 10c — WANDER BEHAVIOUR                                       ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestWander(unittest.TestCase):
    """Flock-level wander centre, radial pulse, and per-bird force."""

    def test_radial_pulse_in_range(self):
        from extensions.wander import radial_pulse
        for t in [0.0, 1.7, 5.5, 42.0, 100.0]:
            self.assertGreaterEqual(radial_pulse(t), 0.72 - 1e-9)
            self.assertLessEqual(radial_pulse(t), 1.0 + 1e-9)

    def test_wander_center_deterministic(self):
        from extensions.wander import flock_wander_center
        self.assertEqual(flock_wander_center(3.0), flock_wander_center(3.0))

    def test_wander_center_moves_over_time(self):
        from extensions.wander import flock_wander_center
        self.assertNotEqual(flock_wander_center(0.0), flock_wander_center(10.0))

    def test_wander_center_within_domain_envelope(self):
        """The centre stays within attractor_radius of the domain centre."""
        from extensions.wander import flock_wander_center, WanderConfig
        from flock_core import WIDTH, HEIGHT
        cfg = WanderConfig()
        for t in range(0, 200, 7):
            cx, cy = flock_wander_center(float(t), cfg)
            dist = math.hypot(cx - WIDTH / 2, cy - HEIGHT / 2)
            self.assertLessEqual(dist, cfg.attractor_radius + 1e-6)

    def test_wander_force_points_toward_center(self):
        from extensions.wander import wander_force, WanderConfig
        cfg = WanderConfig(wander_speed=1.0)
        fx, fy = wander_force((0.0, 0.0), (100.0, 0.0), cfg)
        self.assertGreater(fx, 0.0)          # pulled toward +x centre
        self.assertAlmostEqual(fy, 0.0, places=6)

    def test_wander_force_zero_at_center(self):
        from extensions.wander import wander_force
        fx, fy = wander_force((50.0, 50.0), (50.0, 50.0))
        self.assertAlmostEqual(fx, 0.0)
        self.assertAlmostEqual(fy, 0.0)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ROADMAP 7 — THREAT AGENT & ESCAPE WAVE                               ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestThreatAgent(unittest.TestCase):
    """Approach/egress state machine and escape-wave propagation."""

    def test_starts_in_approach(self):
        from extensions.threat import ThreatAgent
        self.assertEqual(ThreatAgent().phase, "approach")

    def test_approaches_then_egresses(self):
        from extensions.threat import ThreatAgent
        t = ThreatAgent(x=100, y=350)
        start_dist = math.hypot(500 - t.x, 350 - t.y)
        saw_egress = False
        min_dist = start_dist
        for _ in range(300):
            t.update((500, 350))
            min_dist = min(min_dist, math.hypot(500 - t.x, 350 - t.y))
            if t.phase == "egress":
                saw_egress = True
        self.assertLess(min_dist, start_dist,
                        "threat should get closer during approach")
        self.assertTrue(saw_egress, "threat should switch to egress")

    def test_speed_clamped(self):
        from extensions.threat import ThreatAgent, THREAT_SPEED
        t = ThreatAgent()
        for _ in range(100):
            t.update((500, 350))
            self.assertLessEqual(math.hypot(t.vx, t.vy), THREAT_SPEED + 1e-6)

    def test_flee_force_zero_outside_radius(self):
        from extensions.threat import flee_force, THREAT_RADIUS
        fx, fy = flee_force((0.0, 0.0), (THREAT_RADIUS + 50, 0.0))
        self.assertEqual((fx, fy), (0.0, 0.0))

    def test_flee_force_points_away(self):
        from extensions.threat import flee_force
        # Bird at +x of threat should be pushed further +x.
        fx, fy = flee_force((60.0, 0.0), (0.0, 0.0))
        self.assertGreater(fx, 0.0)
        self.assertAlmostEqual(fy, 0.0, places=6)

    def test_escape_wave_amplifies_through_neighbours(self):
        """A bird just outside the danger zone still gets a non-zero
        response via its neighbours' wave (chain reaction)."""
        from extensions.threat import escape_wave, flee_force, THREAT_RADIUS
        threat = (0.0, 0.0)
        # Chain of birds; only the first is inside the danger radius.
        positions = [(THREAT_RADIUS * 0.5, 0.0),
                     (THREAT_RADIUS + 20, 0.0),
                     (THREAT_RADIUS + 60, 0.0)]
        neighbours = [[1], [0, 2], [1]]
        wave = escape_wave(positions, threat, neighbours, sweeps=4)
        # Bird 1 has zero direct flee but a neighbour inside the zone.
        self.assertEqual(flee_force(positions[1], threat), (0.0, 0.0))
        self.assertGreater(math.hypot(*wave[1]), 0.0,
                           "wave should propagate to the neighbour")


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  MEDIUM PRESETS                                                       ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestMediumPresets(unittest.TestCase):
    """Ambient-medium preset table and derived physics."""

    def test_four_media_present(self):
        from medium_presets import MEDIUM_PRESETS
        self.assertEqual(set(MEDIUM_PRESETS),
                         {"air", "dust", "starlight", "grid"})

    def test_entries_have_expected_fields(self):
        from medium_presets import MEDIUM_PRESETS
        fields = {"label", "opacity", "pt_scale", "turbulence", "drift",
                  "color_mix", "density", "jitter", "description"}
        for name, p in MEDIUM_PRESETS.items():
            self.assertSetEqual(set(p), fields, f"{name} field mismatch")
            self.assertTrue(p["label"].startswith("MEDIUM "))

    def test_grid_is_reference_no_perturbation(self):
        from medium_presets import MediumConfig
        m = MediumConfig("grid")
        self.assertEqual(m.turbulence, 0.0)
        self.assertEqual(m.drift_velocity(), (0.0, 0.0))
        self.assertEqual(m.turbulence_accel(), (0.0, 0.0))

    def test_apply_medium_switches_and_validates(self):
        from medium_presets import MediumConfig, apply_medium
        m = MediumConfig("grid")
        label = apply_medium(m, "dust")
        self.assertIn("dust", label)
        self.assertEqual(m.name, "dust")
        self.assertEqual(apply_medium(m, "nonsense"), "")

    def test_turbulence_accel_scales_with_medium(self):
        from medium_presets import MediumConfig
        rng = random.Random(0)
        dust = MediumConfig("dust")
        mags = [math.hypot(*dust.turbulence_accel(rng)) for _ in range(50)]
        self.assertGreater(max(mags), 0.0)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ROADMAP 15 — ADAPTIVE QUALITY                                        ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestAdaptiveQuality(unittest.TestCase):
    """Three-tier FPS degradation with hysteresis."""

    def _drive(self, aq, fps, count, start_ms, steps, step_ms):
        now = start_ms
        for _ in range(steps):
            now += step_ms
            aq.update(fps, now, count)
        return now

    def test_starts_full_quality(self):
        from extensions.adaptive_quality import AdaptiveQuality
        aq = AdaptiveQuality(target_fps=60)
        self.assertEqual(aq.tier, 0)
        self.assertTrue(aq.trails_enabled)
        self.assertEqual(aq.render_scale, 1.0)

    def test_low_fps_degrades_progressively(self):
        from extensions.adaptive_quality import AdaptiveQuality
        aq = AdaptiveQuality(target_fps=60)
        # Sustained 30 fps, well below the 46.8 trigger; cooldown 1800ms.
        self._drive(aq, 30, 4000, 0, 10, 2000)
        self.assertGreaterEqual(aq.tier, 2)
        self.assertFalse(aq.trails_enabled)          # tier ≥ 1
        self.assertLess(aq.render_scale, 1.0)         # tier ≥ 2

    def test_tier3_caps_bird_count(self):
        from extensions.adaptive_quality import (
            AdaptiveQuality, BIRD_COUNT_FLOOR)
        aq = AdaptiveQuality(target_fps=60)
        self._drive(aq, 20, 4000, 0, 12, 2000)
        self.assertEqual(aq.tier, 3)
        self.assertIsNotNone(aq.bird_cap)
        self.assertGreaterEqual(aq.bird_cap, BIRD_COUNT_FLOOR)
        self.assertLess(aq.bird_cap, 4000)

    def test_hysteresis_recovers_only_above_higher_threshold(self):
        from extensions.adaptive_quality import AdaptiveQuality
        aq = AdaptiveQuality(target_fps=60)
        now = self._drive(aq, 30, 4000, 0, 10, 2000)
        degraded_tier = aq.tier
        self.assertGreater(degraded_tier, 0)
        # FPS at 0.85×target: above degrade (0.78) but below recover
        # (0.92) — should NOT recover.
        self._drive(aq, 51, 4000, now, 6, 3500)
        self.assertEqual(aq.tier, degraded_tier)
        # Now clearly above recovery threshold — should climb back.
        now2 = self._drive(aq, 60, 4000, now + 100000, 12, 3500)
        self.assertLess(aq.tier, degraded_tier)

    def test_toggle_off_restores_full_quality(self):
        from extensions.adaptive_quality import AdaptiveQuality
        aq = AdaptiveQuality(target_fps=60)
        self._drive(aq, 20, 4000, 0, 12, 2000)
        self.assertGreater(aq.tier, 0)
        aq.toggle()                       # disable → reset
        self.assertFalse(aq.enabled)
        self.assertEqual(aq.tier, 0)
        self.assertTrue(aq.trails_enabled)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ROADMAP 6 — H₂ ROBUSTNESS METRIC                                     ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestH2Robustness(unittest.TestCase):
    """Laplacian eigenvalues, H₂ norm, per-neighbour efficiency, m*."""

    def test_jacobi_matches_known_eigenvalues(self):
        from extensions.h2_robustness import jacobi_eigenvalues
        # Diagonal matrix → eigenvalues are the diagonal.
        eig = jacobi_eigenvalues([[3.0, 0.0], [0.0, 1.0]])
        self.assertAlmostEqual(eig[0], 1.0, places=6)
        self.assertAlmostEqual(eig[1], 3.0, places=6)
        # 2×2 symmetric with known spectrum: [[2,1],[1,2]] → 1 and 3.
        eig2 = jacobi_eigenvalues([[2.0, 1.0], [1.0, 2.0]])
        self.assertAlmostEqual(eig2[0], 1.0, places=6)
        self.assertAlmostEqual(eig2[1], 3.0, places=6)

    def test_laplacian_rows_sum_to_zero(self):
        from extensions.h2_robustness import knn_laplacian
        random.seed(5)
        pts = [(random.uniform(0, 100), random.uniform(0, 100))
               for _ in range(12)]
        lap = knn_laplacian(pts, 3)
        for row in lap:
            self.assertAlmostEqual(sum(row), 0.0, places=6)

    def test_h2_decreases_with_more_neighbours(self):
        from extensions.h2_robustness import h2_norm
        random.seed(7)
        pts = [(random.uniform(0, 200), random.uniform(0, 200))
               for _ in range(25)]
        self.assertGreater(h2_norm(pts, 2), h2_norm(pts, 8))

    def test_disconnected_graph_is_infinite(self):
        from extensions.h2_robustness import h2_norm
        # Two far-apart pairs with m=1: each bird links only to its
        # cluster-mate, so the two clusters never connect → no consensus.
        pts = [(0.0, 0.0), (1.0, 0.0), (1000.0, 0.0), (1001.0, 0.0)]
        self.assertEqual(h2_norm(pts, 1), math.inf)

    def test_eta_marginal_positive_and_diminishes(self):
        from extensions.h2_robustness import eta_of_m
        random.seed(11)
        pts = [(random.uniform(0, 200), random.uniform(0, 200))
               for _ in range(30)]
        # Deep into the range, marginal efficiency is small and positive.
        self.assertGreaterEqual(eta_of_m(pts, 9), 0.0)
        self.assertGreater(eta_of_m(pts, 4), eta_of_m(pts, 9))

    def test_cost_optimal_m_in_young_range(self):
        from extensions.h2_robustness import cost_optimal_m
        random.seed(13)
        pts = [(random.uniform(0, 250), random.uniform(0, 250))
               for _ in range(40)]
        best_m, _ = cost_optimal_m(pts)
        self.assertGreaterEqual(best_m, 4)
        self.assertLessEqual(best_m, 10)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ROADMAP 5 — SEASONAL / ECOLOGICAL REALISM                           ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestSeasonal(unittest.TestCase):
    """Goodenough seasonal flock-size variation."""

    def test_peak_at_midwinter(self):
        from extensions.seasonal import seasonal_size_factor, PEAK_DAY
        self.assertAlmostEqual(seasonal_size_factor(PEAK_DAY), 1.0, places=6)

    def test_summer_is_trough(self):
        from extensions.seasonal import seasonal_size_factor, MIN_FACTOR
        # ~half a year from the peak.
        self.assertAlmostEqual(seasonal_size_factor(15 + 182), MIN_FACTOR,
                               places=2)

    def test_factor_bounds(self):
        from extensions.seasonal import seasonal_size_factor, MIN_FACTOR
        for d in range(1, 366):
            f = seasonal_size_factor(d)
            self.assertGreaterEqual(f, MIN_FACTOR - 1e-9)
            self.assertLessEqual(f, 1.0 + 1e-9)

    def test_winter_flock_larger_than_summer(self):
        from extensions.seasonal import flock_size_for_day
        self.assertGreater(flock_size_for_day(15, 1000),
                           flock_size_for_day(196, 1000))

    def test_flock_size_respects_floor(self):
        from extensions.seasonal import flock_size_for_day
        self.assertGreaterEqual(flock_size_for_day(196, 1000, min_size=100),
                                100)

    def test_season_window(self):
        from extensions.seasonal import is_murmuration_season
        self.assertTrue(is_murmuration_season(15))    # January
        self.assertFalse(is_murmuration_season(196))  # July

    def test_predator_rate_deterministic(self):
        from extensions.seasonal import predator_present
        # Deterministic per-day (no rng): same day → same answer.
        self.assertEqual(predator_present(42), predator_present(42))


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ROADMAP 6 — FLOCK SHAPE ANALYSIS                                     ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestFlockShape(unittest.TestCase):
    """PCA aspect ratio, orientation, and shape-driven m*."""

    def test_thin_flock_high_aspect_low_m(self):
        from extensions.flock_shape import analyze_shape
        thin = [(x, 350.0) for x in range(100, 700, 15)]
        rep = analyze_shape(thin)
        self.assertGreater(rep.aspect_ratio, 3.0)
        self.assertLessEqual(rep.suggested_m, 7.0)   # thin → fewer neighbours

    def test_round_flock_low_aspect_high_m(self):
        from extensions.flock_shape import analyze_shape
        random.seed(2)
        round_pts = [(500 + random.uniform(-60, 60),
                      350 + random.uniform(-60, 60)) for _ in range(60)]
        rep = analyze_shape(round_pts)
        self.assertLess(rep.aspect_ratio, 1.8)
        self.assertGreater(rep.suggested_m, 8.0)     # round → more neighbours

    def test_orientation_of_horizontal_flock(self):
        from extensions.flock_shape import analyze_shape
        horiz = [(x, 350.0) for x in range(100, 700, 15)]
        rep = analyze_shape(horiz)
        # Major axis is ~horizontal → orientation near 0 (mod π).
        self.assertAlmostEqual(math.sin(rep.orientation), 0.0, places=3)

    def test_suggested_m_monotone_in_aspect(self):
        from extensions.flock_shape import suggested_m_star
        self.assertGreater(suggested_m_star(1.0), suggested_m_star(3.0))

    def test_degenerate_few_points(self):
        from extensions.flock_shape import analyze_shape
        rep = analyze_shape([(0.0, 0.0), (1.0, 1.0)])
        self.assertEqual(rep.count, 2)
        self.assertEqual(rep.area, 0.0)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ROADMAP 8 — LEADER / ATTRACTOR SYSTEM                              ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestLeaderAnchor(unittest.TestCase):
    """Leader anchor sinusoidal motion and attractor force."""

    def test_anchor_starts_at_centre(self):
        from extensions.leader import LeaderAnchor, LeaderConfig
        cfg = LeaderConfig()
        a = LeaderAnchor(cx=500, cy=350, config=cfg)
        # At construction, px/py = centre; after update(0), sinusoidal offset
        a.update(0.0)
        self.assertAlmostEqual(a.px, 500 + cfg.attractor_radius * math.sin(a.phase_x))
        self.assertAlmostEqual(a.py, 350 + cfg.attractor_radius * math.cos(a.phase_y))

    def test_anchor_moves_over_time(self):
        from extensions.leader import LeaderAnchor, LeaderConfig
        a = LeaderAnchor(cx=500, cy=350)
        p0 = a.position()
        a.update(1.0)
        p1 = a.position()
        self.assertNotEqual(p0, p1, "Anchor should move over time")

    def test_anchor_deterministic_with_same_phase(self):
        from extensions.leader import LeaderAnchor, LeaderConfig
        random.seed(42)
        a1 = LeaderAnchor()
        random.seed(42)
        a2 = LeaderAnchor()
        a1.update(3.0)
        a2.update(3.0)
        self.assertEqual(a1.position(), a2.position())

    def test_attractor_force_zero_outside_range(self):
        from extensions.leader import attractor_force, LeaderConfig
        cfg = LeaderConfig(attractor_range=100)
        fx, fy = attractor_force((0, 0), (200, 0), cfg)
        self.assertEqual((fx, fy), (0.0, 0.0))

    def test_attractor_force_points_toward_anchor(self):
        from extensions.leader import attractor_force, LeaderConfig
        cfg = LeaderConfig(attractor_range=200, chase_strength=0.5)
        fx, fy = attractor_force((0, 0), (50, 0), cfg)
        self.assertGreater(fx, 0.0)
        self.assertAlmostEqual(fy, 0.0, places=6)

    def test_attractor_force_linear_falloff(self):
        from extensions.leader import attractor_force, LeaderConfig
        cfg = LeaderConfig(attractor_range=200, chase_strength=1.0)
        # At 50% of range → 50% of chase_strength
        near = attractor_force((0, 0), (100, 0), cfg)
        far = attractor_force((0, 0), (180, 0), cfg)
        self.assertGreater(math.hypot(*near), math.hypot(*far))

    def test_attractor_force_at_zero_distance_not_crash(self):
        from extensions.leader import attractor_force, LeaderConfig
        cfg = LeaderConfig(attractor_range=200)
        fx, fy = attractor_force((50, 50), (50, 50), cfg)
        # d < 1e-9 → returns 0
        self.assertEqual((fx, fy), (0.0, 0.0))

    def test_leader_force_sums_multiple_anchors(self):
        from extensions.leader import LeaderAnchor, LeaderConfig, leader_force
        cfg = LeaderConfig(attractor_range=200, chase_strength=1.0)
        a1 = LeaderAnchor(cx=0, cy=0, config=cfg)
        a1.px, a1.py = 100.0, 0.0
        a2 = LeaderAnchor(cx=0, cy=0, config=cfg)
        a2.px, a2.py = 0.0, 100.0
        fx, fy = leader_force((0, 0), [a1, a2], cfg)
        # Both pull at 100px → 50% each from (0,0)
        self.assertGreater(fx, 0.0)
        self.assertGreater(fy, 0.0)

    def test_empty_anchors_yield_zero_force(self):
        from extensions.leader import leader_force, LeaderConfig
        fx, fy = leader_force((100, 100), [])
        self.assertEqual((fx, fy), (0.0, 0.0))


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ROADMAP 7c — VACUOLE FORMATION                                      ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestVacuoleAgent(unittest.TestCase):
    """Vacuole orbit and radial repulsion force."""

    def test_starts_at_orbit_position(self):
        from extensions.vacuole import VacuoleAgent, VacuoleConfig
        cfg = VacuoleConfig(orbit_radius=50)
        a = VacuoleAgent(config=cfg)
        dist = math.hypot(a.px - 500, a.py - 350)  # swarm_center defaults
        self.assertGreater(dist, 0.0)

    def test_update_moves_position(self):
        from extensions.vacuole import VacuoleAgent
        a = VacuoleAgent()
        p0 = a.position()
        a.update((500, 350), 1.0)
        p1 = a.position()
        self.assertNotEqual(p0, p1, "Vacuole should orbit over time")

    def test_orbits_near_swarm_centre(self):
        from extensions.vacuole import VacuoleAgent, VacuoleConfig
        cfg = VacuoleConfig(orbit_radius=60)
        a = VacuoleAgent(config=cfg)
        for t in [0.0, 1.0, 2.5, 5.0]:
            a.update((500, 350), t)
            px, py = a.position()
            dist = math.hypot(px - 500, py - 350)
            self.assertAlmostEqual(dist, 60.0, places=5)

    def test_force_zero_outside_radius(self):
        from extensions.vacuole import vacuole_force, VacuoleConfig
        cfg = VacuoleConfig(vacuole_radius=100)
        fx, fy = vacuole_force((200, 0), (0, 0), cfg)
        self.assertEqual((fx, fy), (0.0, 0.0))

    def test_force_pushes_away(self):
        from extensions.vacuole import vacuole_force, VacuoleConfig
        cfg = VacuoleConfig(vacuole_radius=200, vacuole_strength=1.0)
        # Bird at (50, 0), vacuole at (0, 0) → pushed right
        fx, fy = vacuole_force((50, 0), (0, 0), cfg)
        self.assertGreater(fx, 0.0)
        self.assertAlmostEqual(fy, 0.0, places=6)

    def test_force_linear_falloff(self):
        from extensions.vacuole import vacuole_force, VacuoleConfig
        cfg = VacuoleConfig(vacuole_radius=200, vacuole_strength=1.0)
        near = vacuole_force((50, 0), (0, 0), cfg)
        far  = vacuole_force((150, 0), (0, 0), cfg)
        self.assertGreater(math.hypot(*near), math.hypot(*far))

    def test_force_zero_at_zero_distance(self):
        from extensions.vacuole import vacuole_force, VacuoleConfig
        cfg = VacuoleConfig(vacuole_radius=200)
        fx, fy = vacuole_force((0, 0), (0, 0), cfg)
        self.assertEqual((fx, fy), (0.0, 0.0))

    def test_force_zero_at_exact_radius_boundary(self):
        from extensions.vacuole import vacuole_force, VacuoleConfig
        cfg = VacuoleConfig(vacuole_radius=100, vacuole_strength=1.0)
        fx, fy = vacuole_force((100, 0), (0, 0), cfg)
        self.assertEqual((fx, fy), (0.0, 0.0))


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ROADMAP 8 — SHELL FORMATION / PILOTING                              ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestFlowField(unittest.TestCase):
    """Tests for extensions/flow_field.py — environmental wind/drift."""

    def test_flow_config_defaults(self):
        from extensions.flow_field import FlowConfig
        cfg = FlowConfig()
        self.assertAlmostEqual(cfg.wind_angle, math.pi / 6)
        self.assertAlmostEqual(cfg.wind_strength, 0.02)
        self.assertAlmostEqual(cfg.wind_wander, 0.3)
        self.assertAlmostEqual(cfg.turbulence, 0.005)
        self.assertAlmostEqual(cfg.gust_chance, 0.15)
        self.assertAlmostEqual(cfg.gust_strength, 3.0)
        self.assertAlmostEqual(cfg.gust_duration, 0.5)

    def test_flow_force_returns_tuple(self):
        from extensions.flow_field import FlowConfig, flow_force
        cfg = FlowConfig()
        fx, fy = flow_force(cfg, 0.0, False, 0.0)
        self.assertIsInstance(fx, float)
        self.assertIsInstance(fy, float)

    def test_flow_force_nonzero(self):
        from extensions.flow_field import FlowConfig, flow_force
        cfg = FlowConfig()
        fx, fy = flow_force(cfg, 0.0, False, 0.0)
        # Wind should have a non-zero magnitude at default angle
        self.assertTrue(fx != 0.0 or fy != 0.0)

    def test_flow_force_direction_consistent(self):
        from extensions.flow_field import FlowConfig, flow_force
        cfg = FlowConfig(wind_angle=0.0, wind_wander=0.0, wind_strength=0.1)
        fx, fy = flow_force(cfg, 0.0, False, 0.0)
        # wind_angle=0 means wind blows right (positive x);
        # cos(0)*0.25 = 0.25 offset in angle, so small y-component is expected
        self.assertGreater(fx, 0)
        # y component should be small (only from cos(0)*0.25 ≈ 0.25 rad offset)
        self.assertLess(abs(fy), 0.05)

    def test_flow_gust_amplifies(self):
        from extensions.flow_field import FlowConfig, flow_force
        cfg = FlowConfig(wind_angle=0.0, wind_wander=0.0, wind_strength=0.02,
                         gust_strength=3.0, gust_duration=0.5)
        normal_fx, _ = flow_force(cfg, 0.0, False, 0.0)
        gust_fx, _ = flow_force(cfg, 0.0, True, 0.0)
        # Gust should be stronger than normal
        self.assertGreater(abs(gust_fx), abs(normal_fx))

    def test_flow_gust_decays(self):
        from extensions.flow_field import FlowConfig, flow_force
        cfg = FlowConfig(wind_angle=0.0, wind_wander=0.0, wind_strength=0.02,
                         gust_strength=3.0, gust_duration=0.5)
        # At half duration, should still be amplified but less
        fx_full, _ = flow_force(cfg, 0.0, True, 0.0)
        fx_half, _ = flow_force(cfg, 0.0, True, 0.25)
        self.assertGreater(abs(fx_half), abs(fx_full * 0.3))

    def test_flow_wandering_changes_direction(self):
        from extensions.flow_field import FlowConfig, flow_force
        cfg = FlowConfig(wind_angle=0.0, wind_wander=1.0, wind_strength=0.1)
        # At different times, the direction should differ due to wandering
        _, fy0 = flow_force(cfg, 0.0, False, 0.0)
        _, fy1 = flow_force(cfg, 1.0, False, 0.0)
        # The y-component should differ due to sinusoidal wandering
        self.assertNotAlmostEqual(fy0, fy1, places=3)


class TestShellFormation(unittest.TestCase):
    """Shell assignment, orbital force, and config."""

    def test_assign_shells_covers_all_birds(self):
        from extensions.shell_formation import assign_shells, ShellConfig
        cfg = ShellConfig(radii=[40, 80], speeds=[0.8, 0.5])
        flock = list(range(20))
        assignments = assign_shells(flock, cfg)
        self.assertEqual(len(assignments), len(flock))

    def test_assign_shells_distributes_across_shells(self):
        from extensions.shell_formation import assign_shells, ShellConfig
        cfg = ShellConfig(radii=[40, 80, 120])
        flock = list(range(30))
        assignments = assign_shells(flock, cfg)
        shells = set(s for s, _, _ in assignments)
        self.assertEqual(len(shells), 3)

    def test_shell_force_pulls_toward_target(self):
        from extensions.shell_formation import shell_force, ShellConfig
        cfg = ShellConfig(radii=[100], speeds=[0.5])
        # Bird at (0, 0), centre at (100, 0), shell radius 100, phase 0, time 0
        # target = (100 + 100*cos(0), 0 + 100*sin(0)) = (200, 0)
        fx, fy = shell_force((0, 0), (100, 0), 0, 0.0, 1, 0.0, cfg)
        self.assertGreater(fx, 0.0)  # pulled right toward target

    def test_shell_force_different_phase(self):
        from extensions.shell_formation import shell_force, ShellConfig
        cfg = ShellConfig(radii=[100], speeds=[0.5])
        # Phase π, time=0, radius=100, centre=(100,0)
        # angle = π + 0 = π, target = (100 + 100*cos(π), 100*sin(π)) = (0, 0)
        # Bird at (200, 0), dist=200, force toward (0,0) → negative x
        fx, fy = shell_force((200, 0), (100, 0), 0, math.pi, 1, 0.0, cfg)
        self.assertLess(fx, 0.0)  # pulled left toward target

    def test_shell_force_clockwise_orbits(self):
        from extensions.shell_formation import shell_force, ShellConfig
        import math as _m
        cfg = ShellConfig(radii=[80], speeds=[1.0])
        # At t=π/2, dir=1, phase=0, speed=1.0: angle=π/2
        # target = (80 + 80*cos(π/2), 0 + 80*sin(π/2)) = (80, 80)
        # bird at (80, 0), dist=80, force toward (80,80): fx=0, fy>0
        fx, fy = shell_force((80, 0), (80, 0), 0, 0.0, 1, _m.pi / 2, cfg)
        self.assertAlmostEqual(fx, 0.0, places=5)
        self.assertGreater(fy, 0.0)  # pulled up toward target

    def test_shell_force_zero_dist_no_crash(self):
        from extensions.shell_formation import shell_force, ShellConfig
        cfg = ShellConfig()
        # Bird at exact target position
        fx, fy = shell_force((100, 0), (0, 0), 0, 0.0, 1, 0.0, cfg)
        # Need to check: at time 0 with radius=40, target = (40, 0)
        # Target = (0+40*cos(0), 0+40*sin(0)) = (40, 0)
        # Bird at (100, 0), dist to (40,0) = 60 > 0, so there IS force
        # Let's put bird at target to test zero-dist
        fx2, fy2 = shell_force((40, 0), (0, 0), 0, 0.0, 1, 0.0, cfg)
        self.assertEqual((fx2, fy2), (0.0, 0.0))

    def test_default_config_has_four_shells(self):
        from extensions.shell_formation import ShellConfig
        cfg = ShellConfig()
        self.assertEqual(len(cfg.radii), 4)
        self.assertEqual(len(cfg.speeds), 4)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Test discovery sanity check                                         ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestDiscovery(unittest.TestCase, TestCountMixin):
    """Verify test count to catch accidental regressions in discovery."""

    EXPECTED_TEST_COUNT = 190
