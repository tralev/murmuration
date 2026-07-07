"""
Unit tests for the angular-interval merge utilities in alg2.py (SECTION 4).

Covers:
  - _normalise_interval   — split wrap-around intervals into [0, 2π) segments
  - _interval_covered     — check whether an interval is fully occluded
  - _merge_interval       — insert-and-merge one interval into a sorted list
  - _merge_all            — sort-and-merge a list of intervals
"""
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECTION T1 — CORE UNIT TESTS  (alg2, boid, occlusion, presets)     ║
# ╚══════════════════════════════════════════════════════════════════════╝


import math
import unittest

import pygame

import flock_core
import features

from test_count_mixin import TestCountMixin

from flock_core import WIDTH, HEIGHT, V0, TRAIL_LENGTH


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  _normalise_interval                                                 ║
# ╚══════════════════════════════════════════════════════════════════════╝

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
        import features
        features.ENABLE_TRAILS = True
        self.addCleanup(lambda: setattr(features, 'ENABLE_TRAILS', False))

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
        import features
        features.ENABLE_TRAILS = True
        self.addCleanup(lambda: setattr(features, 'ENABLE_TRAILS', False))

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
        import features
        features.ENABLE_TRAILS = True
        self.addCleanup(lambda: setattr(features, 'ENABLE_TRAILS', False))

        b = self._make_boid(WIDTH // 2, HEIGHT // 2, V0, 0)
        # Run many more steps than TRAIL_LENGTH
        self._update_n_times(b, flock_core.TRAIL_LENGTH * 3)

        self.assertEqual(len(b.history), TRAIL_LENGTH,
            f"Trail should cap at TRAIL_LENGTH={TRAIL_LENGTH}")

    def _reset_trail_flag(self):
        """Restore ENABLE_TRAILS to False after trail tests."""
        import features
        features.ENABLE_TRAILS = False
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
    #  The nudge runs BEFORE the speed clamp (see BOUNDARY_MODES.md §1),
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


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Toroidal wrap mode — verify birds teleport across edges             ║
# ╚══════════════════════════════════════════════════════════════════════╝

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
        """Restore ENABLE_TRAILS to False after trail tests."""
        import features
        features.ENABLE_TRAILS = False

    def test_trail_positions_are_wrapped_not_raw(self):
        """When MARGIN_BOUNDARY=False, trail positions reflect wrapped
        positions — NOT the raw pre-wrap values that may be out of bounds.
        A bird flying beyond the right edge wraps to x=0; trail records
        the post-wrap position."""
        import features
        features.ENABLE_TRAILS = True
        self.addCleanup(lambda: setattr(features, 'ENABLE_TRAILS', False))

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
        import features
        features.ENABLE_TRAILS = True
        self.addCleanup(lambda: setattr(features, 'ENABLE_TRAILS', False))

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
        import features
        features.ENABLE_TRAILS = True
        self.addCleanup(lambda: setattr(features, 'ENABLE_TRAILS', False))

        b = self._make_boid(WIDTH // 2, HEIGHT // 2, V0, 0)
        # Run many more steps than TRAIL_LENGTH
        for _ in range(TRAIL_LENGTH * 3):
            b.update()

        self.assertEqual(len(b.history), TRAIL_LENGTH,
            f"Trail should cap at TRAIL_LENGTH={TRAIL_LENGTH}")


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Octave/Scilab toroidal wrap — verify array-math physics             ║
# ╚══════════════════════════════════════════════════════════════════════╝


class TestDiscovery(unittest.TestCase, TestCountMixin):
    """Verify test count for boundary module."""

    EXPECTED_TEST_COUNT = 41


if __name__ == '__main__':
    unittest.main(verbosity=2)
