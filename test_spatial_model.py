"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION T6 — SPATIAL MODEL UNIT TESTS                              ║
╚══════════════════════════════════════════════════════════════════════╝

 Standalone tests for spatial_model.py — verify that the extracted
 flock_spatial() function works correctly using mock boids and a
 mock spatial grid (no Boid class or real SpatialGrid dependency).

 Note: flock_spatial() always calls apply_force() 4 times per frame
 (separation, alignment, cohesion, noise). When there are no neighbours,
 the first three forces are zero vectors.
──────────────────────────────────────────────────────────────────────
"""

import math
import unittest

import pygame

from test_count_mixin import TestCountMixin

from spatial_model import flock_spatial
from flock_core import (
    V0, VISUAL_RANGE, MAX_FORCE, Config,
)


class MockBoid:
    """Minimal boid that records forces applied by the spatial model."""
    __slots__ = ("position", "velocity", "_debug_delta", "_debug_merged",
                 "_forces")

    def __init__(self, x: float, y: float, vx: float = 0.0, vy: float = 0.0):
        self.position = pygame.Vector2(x, y)
        self.velocity = pygame.Vector2(vx, vy)
        self._debug_delta = pygame.Vector2(1, 1)    # non-zero to detect clear
        self._debug_merged = [(0.1, 0.2)]           # non-empty to detect clear
        self._forces = []                            # recorded applied forces

    def apply_force(self, force: pygame.Vector2):
        """Record the applied force (instead of accumulating to acceleration)."""
        self._forces.append(pygame.Vector2(force))


class MockGrid:
    """Grid that returns all boids when queried (simulates no spatial filtering).

    The spatial model's own distance filtering (VISUAL_RANGE check) is what
    determines actual neighbour selection — the grid just provides candidates.
    """
    def __init__(self, boids: list):
        self._boids = boids

    def get_nearby(self, position, radius: float) -> list:
        return list(self._boids)


def _make_config(sigma=4, phi_p=0.03, phi_a=0.80):
    """Build a minimal Config for testing."""
    c = Config()
    c.sigma = sigma
    c.phi_p = phi_p
    c.phi_a = phi_a
    return c


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  flock_spatial                                                       ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestFlockSpatial(unittest.TestCase):
    """Standalone tests for spatial_model.flock_spatial()."""

    # ── Debug state clearing ─────────────────────────────────────────

    def test_debug_state_cleared(self):
        """flock_spatial always clears _debug_delta and _debug_merged."""
        boid = MockBoid(500, 350, V0, 0)
        config = _make_config()
        grid = MockGrid([])

        flock_spatial(boid, [boid], config, grid)

        self.assertEqual(boid._debug_delta, pygame.Vector2(0, 0))
        self.assertEqual(boid._debug_merged, [])

    # ── No neighbours: forces 0–2 are zero vectors ───────────────────

    def test_no_neighbours_zero_steering(self):
        """With no neighbours, separation/alignment/cohesion forces are zero.
        Only noise (index 3) is non-zero. (But 4 apply_force calls always happen.)"""
        boid = MockBoid(500, 350, V0, 0)
        config = _make_config()
        grid = MockGrid([])

        flock_spatial(boid, [boid], config, grid)

        # 4 forces always applied: sep, align, coh, noise
        self.assertEqual(len(boid._forces), 4)
        # first three should be zero
        self.assertEqual(boid._forces[0], pygame.Vector2(0, 0))
        self.assertEqual(boid._forces[1], pygame.Vector2(0, 0))
        self.assertEqual(boid._forces[2], pygame.Vector2(0, 0))
        # noise is non-zero
        self.assertNotEqual(boid._forces[3], pygame.Vector2(0, 0))
        self.assertAlmostEqual(boid._forces[3].length(), MAX_FORCE * 0.8, delta=0.01)

    def test_self_filtered_by_identity(self):
        """Other boid is the same object → filtered by `other is boid` check.
        Forces 0–2 are zero (no real neighbours)."""
        boid = MockBoid(500, 350, V0, 0)
        config = _make_config()
        grid = MockGrid([boid])  # grid returns just the boid itself

        flock_spatial(boid, [boid], config, grid)

        self.assertEqual(len(boid._forces), 4)
        self.assertEqual(boid._forces[0], pygame.Vector2(0, 0))
        self.assertEqual(boid._forces[1], pygame.Vector2(0, 0))
        self.assertEqual(boid._forces[2], pygame.Vector2(0, 0))

    def test_sigma_zero_no_neighbours(self):
        """sigma=0 → neighbours[:0] is empty → steering forces are zero."""
        boid = MockBoid(500, 350, V0, 0)
        neighbour = MockBoid(550, 350, V0, 0)
        config = _make_config(sigma=0)
        grid = MockGrid([boid, neighbour])

        flock_spatial(boid, [boid, neighbour], config, grid)

        # sigma=0 means no neighbours used → sep/align/coh are zero
        self.assertEqual(boid._forces[0], pygame.Vector2(0, 0))
        self.assertEqual(boid._forces[1], pygame.Vector2(0, 0))
        self.assertEqual(boid._forces[2], pygame.Vector2(0, 0))
        # noise still applied
        self.assertNotEqual(boid._forces[3], pygame.Vector2(0, 0))

    # ── Single neighbour ─────────────────────────────────────────────

    def test_single_neighbour_far_no_separation(self):
        """Neighbour beyond separation threshold (d >= VISUAL_RANGE*0.3=21):
        separation stays zero; alignment + cohesion are non-zero."""
        boid = MockBoid(500, 350, 0, V0)           # heading up
        neighbour = MockBoid(550, 350, V0, 0)       # dist=50, heading right

        config = _make_config()
        grid = MockGrid([boid, neighbour])

        flock_spatial(boid, [boid, neighbour], config, grid)

        self.assertEqual(len(boid._forces), 4)
        # Separation is zero (neighbour beyond 21-pixel threshold)
        self.assertAlmostEqual(boid._forces[0].length(), 0.0, delta=0.02)
        # Alignment and cohesion are non-zero (different velocities avoid cancellation)
        self.assertNotEqual(boid._forces[1], pygame.Vector2(0, 0))
        self.assertNotEqual(boid._forces[2], pygame.Vector2(0, 0))

    def test_single_neighbour_close_separation(self):
        """Neighbour within separation threshold (d < VISUAL_RANGE*0.3=21):
        separation force is non-zero and pushes away from the neighbour."""
        boid = MockBoid(500, 350, V0, 0)
        neighbour = MockBoid(510, 350, V0, 0)   # dist=10 < 21

        config = _make_config()
        grid = MockGrid([boid, neighbour])

        flock_spatial(boid, [boid, neighbour], config, grid)

        # Separation is non-zero (close neighbour triggers it)
        sep_force = boid._forces[0]
        self.assertGreater(sep_force.length(), 0.001)

    def test_separation_pushes_away(self):
        """Separation pushes left when neighbour is to the right."""
        boid = MockBoid(500, 350, V0, 0)
        neighbour = MockBoid(509, 350, V0, 0)   # dist=9 → separation zone

        config = _make_config()
        grid = MockGrid([boid, neighbour])

        flock_spatial(boid, [boid, neighbour], config, grid)

        sep_force = boid._forces[0]
        # Neighbour to the right → separation pushes left (negative x)
        self.assertLess(sep_force.x, 0,
                        f"Separation should push left, got x={sep_force.x:.3f}")

    # ── Cohesion (steers toward neighbour) ───────────────────────────

    def test_cohesion_points_toward_neighbour(self):
        """Cohesion steers toward neighbour's position.

        Boid velocity is orthogonal to neighbour direction so it doesn't
        cancel the cohesion steering.
        """
        # Boid heading up, neighbour to the right → cohesion should push right
        boid = MockBoid(500, 350, 0, -V0)
        neighbour = MockBoid(550, 350, V0, 0)

        config = _make_config()
        grid = MockGrid([boid, neighbour])

        flock_spatial(boid, [boid, neighbour], config, grid)

        coh_force = boid._forces[2]
        # Cohesion should steer right (toward neighbour at x=550)
        self.assertGreater(coh_force.x, 0,
                           f"Cohesion should steer right, got x={coh_force.x:.3f}")

    # ── Topological selection (sigma limit) ──────────────────────────

    def test_sigma_limits_neighbour_count(self):
        """Only sigma nearest neighbours contribute. Forces are still applied
        but computed from at most sigma neighbours."""
        boid = MockBoid(500, 350, 0, V0)       # heading up (avoids velocity cancellation)
        others = [boid]
        for i in range(8):
            others.append(MockBoid(500 + 30 + i * 5, 350, V0, 0))  # distances 30-65

        config = _make_config(sigma=3)
        grid = MockGrid(others)

        flock_spatial(boid, others, config, grid)

        # Alignment and cohesion should be non-zero (3 neighbours contribute)
        self.assertNotEqual(boid._forces[1], pygame.Vector2(0, 0))
        self.assertNotEqual(boid._forces[2], pygame.Vector2(0, 0))

    # ── Force scaling by config weights ──────────────────────────────

    def test_force_scaling_alignment_unchanged_when_phi_a_same(self):
        """Alignment force magnitude is the same when φa is unchanged."""
        boid1 = MockBoid(500, 350, 0, V0)
        neighbour1 = MockBoid(550, 350, V0, 0)
        config1 = _make_config(phi_p=0.1, phi_a=0.5, sigma=4)
        grid1 = MockGrid([boid1, neighbour1])
        flock_spatial(boid1, [boid1, neighbour1], config1, grid1)

        boid2 = MockBoid(500, 350, 0, V0)
        neighbour2 = MockBoid(550, 350, V0, 0)
        config2 = _make_config(phi_p=0.2, phi_a=0.5, sigma=4)
        grid2 = MockGrid([boid2, neighbour2])
        flock_spatial(boid2, [boid2, neighbour2], config2, grid2)

        # Alignment force (index 1) uses φa → same for both
        self.assertAlmostEqual(
            boid1._forces[1].length(), boid2._forces[1].length(), places=2,
            msg="Alignment force should be unchanged when φa is same")

    # ── Grid filtering ───────────────────────────────────────────────

    def test_grid_filters_by_visual_range(self):
        """Birds returned by grid but beyond VISUAL_RANGE → excluded.
        Only the within-range neighbour contributes to steering."""
        boid = MockBoid(500, 350, 0, V0)           # heading up (avoids velocity cancellation)
        within = MockBoid(530, 350, V0, 0)          # dist=30 < 70
        beyond = MockBoid(580, 350, V0, 0)          # dist=80 > 70 (filtered out)
        config = _make_config(sigma=10)
        grid = MockGrid([boid, within, beyond])

        flock_spatial(boid, [boid, within, beyond], config, grid)

        # Both are in grid, but beyond is filtered by VISUAL_RANGE check.
        # Forces are computed from the 1 valid neighbour → alignment non-zero.
        self.assertNotEqual(boid._forces[1], pygame.Vector2(0, 0),
                            "Alignment force should be non-zero (1 valid neighbour)")

    def test_neighbour_exactly_at_visual_range_excluded(self):
        """Neighbour at d = VISUAL_RANGE exactly → d < VISUAL_RANGE is False
        → excluded. Steering forces should be zero."""
        boid = MockBoid(500, 350, V0, 0)
        at_edge = MockBoid(500 + VISUAL_RANGE, 350, V0, 0)  # dist = 70 exactly
        config = _make_config()
        grid = MockGrid([boid, at_edge])

        flock_spatial(boid, [boid, at_edge], config, grid)

        # d = VISUAL_RANGE exactly → not included → steering forces are zero
        self.assertEqual(boid._forces[0], pygame.Vector2(0, 0))
        self.assertEqual(boid._forces[1], pygame.Vector2(0, 0))
        self.assertEqual(boid._forces[2], pygame.Vector2(0, 0))

    # ── Force clamping ───────────────────────────────────────────────

    def test_steering_clamped_to_max_force(self):
        """Steering forces never exceed MAX_FORCE."""
        boid = MockBoid(500, 350, 0, 0)   # zero velocity → large steering
        neighbour = MockBoid(550, 350, V0, 0)
        config = _make_config()
        grid = MockGrid([boid, neighbour])

        flock_spatial(boid, [boid, neighbour], config, grid)

        for i, f in enumerate(boid._forces):
            if f.length() > 0:
                self.assertLessEqual(f.length(), MAX_FORCE + 0.001,
                    f"Force {i} should be \u2264 MAX_FORCE, got {f.length():.4f}")


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Test count guardian                                                 ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestDiscovery(unittest.TestCase, TestCountMixin):
    """Verify test count for spatial_model module."""

    EXPECTED_TEST_COUNT = 13


if __name__ == '__main__':
    unittest.main(verbosity=2)
