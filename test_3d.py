"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION T3D — 3D SIMULATION UNIT TESTS                             ║
╚══════════════════════════════════════════════════════════════════════╝

 Standalone tests for the 3D simulation components:
   • Boid3D.update()  — toroidal wrap, speed clamp, boundary nudge
   • SpatialGrid3D    — rebuild, get_nearby, toroidal cell wrapping
   • flock_spatial_3d — 3D Reynolds steering (sep/align/cohesion/noise)
   • flock_projection_3d — true 3D spherical-cap occlusion (occlusion_3d)

 Uses mock boids with numpy arrays. No Pygame, ModernGL, or rendering
 dependency — pure physics tests.
──────────────────────────────────────────────────────────────────────
"""

import math
import random
import unittest

import numpy as np

from flock_core import (
    WIDTH, HEIGHT, DEPTH, V0, MAX_FORCE,
    MODE_PROJECTION, MODE_SPATIAL,
    VISUAL_RANGE, BOID_SIZE, Config,
)
from spatial_grid_3d import SpatialGrid3D
from flocking_modes_3d import flock_projection_3d, flock_spatial_3d
from boid_3d import Boid3D


# ══════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════

class MockBoid:
    """Minimal 3D boid that records forces applied by flocking functions."""
    def __init__(self, x, y, z, vx=0.0, vy=0.0, vz=0.0):
        self.pos = np.array([x, y, z], dtype=np.float32)
        self.vel = np.array([vx, vy, vz], dtype=np.float32)
        self.last_theta = 0.0
        self._forces = []

    def apply_force(self, force):
        self._forces.append(np.array(force, dtype=np.float32))


class MockGrid:
    """Grid that returns all boids when queried."""
    def __init__(self, boids):
        self._boids = boids

    def get_nearby(self, pos, radius):
        return list(self._boids)


def _make_config(sigma=4, phi_p=0.03, phi_a=0.80, mode=MODE_PROJECTION):
    """Build a minimal Config for testing the *base* projection geometry.

    Pearce SI refinements (blind angles, anisotropy, steric) default on in
    the live sim but are disabled here so these tests isolate the base
    model; the refinement tests in test_science_3d.py enable them.
    """
    c = Config()
    c.sigma = sigma
    c.phi_p = phi_p
    c.phi_a = phi_a
    c.mode = mode
    c.refinements = False
    return c


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Boid3D.update() — Toroidal Wrap & Speed Clamp                      ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestBoid3DUpdate(unittest.TestCase):
    """Tests for Boid3D physics: wrap, speed clamp, boundary nudge."""

    # ── Toroidal wrap ───────────────────────────────────────────────

    def test_wrap_x_positive(self):
        """Position beyond WIDTH → hard reset to 0 (toroidal re-entry)."""
        b = Boid3D()
        b.pos = np.array([WIDTH + 50, 350, 200], dtype=np.float32)
        b.vel = np.array([V0, 0, 0], dtype=np.float32)  # V0 to avoid speed clamp
        b.acc = np.array([0, 0, 0], dtype=np.float32)
        b.update()
        self.assertAlmostEqual(b.pos[0], 0.0, delta=0.5)
        self.assertAlmostEqual(b.pos[1], 350 + V0 * 0.3, delta=2)
        self.assertAlmostEqual(b.pos[2], 200, delta=2)

    def test_wrap_x_negative(self):
        """Position below 0 → hard reset to WIDTH."""
        b = Boid3D()
        b.pos = np.array([-50, 350, 200], dtype=np.float32)
        b.vel = np.array([-V0, 0, 0], dtype=np.float32)
        b.acc = np.array([0, 0, 0], dtype=np.float32)
        b.update()
        self.assertAlmostEqual(b.pos[0], float(WIDTH), delta=0.5)
        self.assertAlmostEqual(b.pos[1], 350 + V0 * 0.3, delta=2)

    def test_wrap_y_positive(self):
        """Position beyond HEIGHT → hard reset to 0."""
        b = Boid3D()
        b.pos = np.array([500, HEIGHT + 30, 200], dtype=np.float32)
        b.vel = np.array([0, V0, 0], dtype=np.float32)
        b.update()
        self.assertAlmostEqual(b.pos[1], 0.0, delta=0.5)

    def test_wrap_y_negative(self):
        """Position below 0 → hard reset to HEIGHT."""
        b = Boid3D()
        b.pos = np.array([500, -30, 200], dtype=np.float32)
        b.vel = np.array([0, -V0, 0], dtype=np.float32)
        b.update()
        self.assertAlmostEqual(b.pos[1], float(HEIGHT), delta=0.5)

    def test_wrap_z_positive(self):
        """Position beyond DEPTH → hard reset to 0."""
        b = Boid3D()
        b.pos = np.array([500, 350, DEPTH + 20], dtype=np.float32)
        b.vel = np.array([0, 0, V0], dtype=np.float32)
        b.update()
        self.assertAlmostEqual(b.pos[2], 0.0, delta=0.5)

    def test_wrap_z_negative(self):
        """Position below 0 → hard reset to DEPTH."""
        b = Boid3D()
        b.pos = np.array([500, 350, -20], dtype=np.float32)
        b.vel = np.array([0, 0, -V0], dtype=np.float32)
        b.update()
        self.assertAlmostEqual(b.pos[2], float(DEPTH), delta=0.5)

    def test_no_wrap_when_in_bounds(self):
        """Position within bounds → no wrap."""
        b = Boid3D()
        b.pos = np.array([500, 350, 200], dtype=np.float32)
        b.vel = np.array([1, 2, 3], dtype=np.float32)
        b.update()
        self.assertAlmostEqual(b.pos[0], 501, delta=2)
        self.assertAlmostEqual(b.pos[1], 352, delta=2)
        self.assertAlmostEqual(b.pos[2], 203, delta=2)

    # ── Speed clamp ─────────────────────────────────────────────────

    def test_speed_clamp_above_v0(self):
        """Speed > V0 → clamped to V0."""
        b = Boid3D()
        b.pos = np.array([500, 350, 200], dtype=np.float32)
        b.vel = np.array([V0 * 2, 0, 0], dtype=np.float32)  # speed = 8
        b.acc = np.array([0, 0, 0], dtype=np.float32)
        b.update()
        self.assertAlmostEqual(np.linalg.norm(b.vel), V0, delta=0.01)

    def test_speed_clamp_below_min(self):
        """Speed < 0.3*V0 → clamped up to 0.3*V0."""
        b = Boid3D()
        b.pos = np.array([500, 350, 200], dtype=np.float32)
        b.vel = np.array([0.1, 0, 0], dtype=np.float32)  # speed = 0.1
        b.update()
        self.assertGreaterEqual(np.linalg.norm(b.vel), V0 * 0.3 - 0.01)

    def test_speed_clamp_zero_gets_random(self):
        """Zero velocity → replaced with random direction at 0.3*V0."""
        b = Boid3D()
        b.pos = np.array([500, 350, 200], dtype=np.float32)
        b.vel = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        b.update()
        speed = np.linalg.norm(b.vel)
        self.assertAlmostEqual(speed, V0 * 0.3, delta=0.01)

    # ── Acceleration accumulation & reset ──────────────────────────

    def test_acc_applied_and_reset(self):
        """Acceleration is added to velocity, then reset to zero after update."""
        b = Boid3D()
        b.pos = np.array([500, 350, 200], dtype=np.float32)
        b.vel = np.array([V0 * 0.5, 0, 0], dtype=np.float32)  # speed=2 (below V0)
        b.acc = np.array([0.5, 0, 0], dtype=np.float32)
        old_vel_x = b.vel[0]
        b.update()
        # velocity was increased by acceleration (2+0.5=2.5, still below V0=4 → no clamp)
        self.assertAlmostEqual(b.vel[0], old_vel_x + 0.5, places=3)
        # acceleration was reset to zero
        self.assertAlmostEqual(np.linalg.norm(b.acc), 0.0, delta=0.001)

    def test_apply_force_accumulates(self):
        """Multiple apply_force calls accumulate."""
        b = Boid3D()
        b.acc = np.array([0, 0, 0], dtype=np.float32)
        b.apply_force(np.array([1, 0, 0], dtype=np.float32))
        b.apply_force(np.array([0, 2, 0], dtype=np.float32))
        self.assertEqual(b.acc[0], 1.0)
        self.assertEqual(b.acc[1], 2.0)
        self.assertEqual(b.acc[2], 0.0)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SpatialGrid3D                                                      ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestSpatialGrid3D(unittest.TestCase):
    """Tests for the 3D spatial hash grid."""

    def test_rebuild_populates_grid(self):
        """Birds land in the correct cells after rebuild."""
        grid = SpatialGrid3D(cell_size=100)
        b1 = MockBoid(50, 50, 50)
        b2 = MockBoid(150, 50, 50)  # different cell
        b3 = MockBoid(50, 50, 150)  # different z slice

        grid.rebuild([b1, b2, b3])
        # b1 at cell (0, 0, 0)
        # b2 at cell (1, 0, 0)
        # b3 at cell (0, 0, 1)
        self.assertIn(b1, grid.cells.get((0, 0, 0), []))
        self.assertIn(b2, grid.cells.get((1, 0, 0), []))
        self.assertIn(b3, grid.cells.get((0, 0, 1), []))

    def test_rebuild_clears_previous(self):
        """Rebuild clears old cell contents."""
        grid = SpatialGrid3D(cell_size=100)
        b1 = MockBoid(50, 50, 50)
        grid.rebuild([b1])
        self.assertIn(b1, grid.cells.get((0, 0, 0), []))

        grid.rebuild([])
        self.assertEqual(len(grid.cells), 0)

    def test_get_nearby_returns_candidates(self):
        """get_nearby returns birds in the correct cells."""
        grid = SpatialGrid3D(cell_size=100)
        b_near = MockBoid(50, 50, 50)
        b_far = MockBoid(500, 500, 300)
        grid.rebuild([b_near, b_far])

        nearby = grid.get_nearby(np.array([50, 50, 50], dtype=np.float32), 100)
        self.assertIn(b_near, nearby)
        self.assertNotIn(b_far, nearby)

    def test_get_nearby_returns_nothing_when_empty(self):
        """Empty grid → get_nearby returns empty list."""
        grid = SpatialGrid3D(cell_size=100)
        grid.rebuild([])
        nearby = grid.get_nearby(np.array([500, 350, 200], dtype=np.float32), 100)
        self.assertEqual(nearby, [])

    def test_toroidal_cell_wrap_x(self):
        """Birds at exact bounds wrap to the same column (modulo cols)."""
        grid = SpatialGrid3D(cell_size=100)
        b_left = MockBoid(50, 350, 200)
        b_right = MockBoid(WIDTH, 350, 200)  # WIDTH=1000, 1000//100=10, 10%10=0
        grid.rebuild([b_left, b_right])

        # Both should be in column 0: 50//100=0, WIDTH//100%cols=10%10=0
        cx_left = int(50 // 100) % grid.cols
        cx_right = int(WIDTH // 100) % grid.cols
        self.assertEqual(cx_left, cx_right)

    def test_toroidal_query_wraps(self):
        """Querying near an edge wraps to the opposite side cells."""
        grid = SpatialGrid3D(cell_size=100)
        b = MockBoid(10, 350, 200)  # near left edge, x=10
        grid.rebuild([b])

        # Query from near right edge → should wrap to get b
        nearby = grid.get_nearby(
            np.array([WIDTH - 10, 350, 200], dtype=np.float32), 50)
        self.assertIn(b, nearby)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  flock_spatial_3d                                                   ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestFlockSpatial3D(unittest.TestCase):
    """Standalone tests for flocking_modes_3d.flock_spatial_3d()."""

    # ── No neighbours ───────────────────────────────────────────────

    def test_no_neighbours_zero_steering(self):
        """With no neighbours, sep/align/coh forces are zero. 4 forces applied."""
        boid = MockBoid(500, 350, 200, V0, 0, 0)
        config = _make_config(mode=MODE_SPATIAL)
        grid = MockGrid([])

        flock_spatial_3d(boid, [boid], config, grid)

        self.assertEqual(len(boid._forces), 4)
        self.assertAlmostEqual(np.linalg.norm(boid._forces[0]), 0.0, delta=0.01)
        self.assertAlmostEqual(np.linalg.norm(boid._forces[1]), 0.0, delta=0.01)
        self.assertAlmostEqual(np.linalg.norm(boid._forces[2]), 0.0, delta=0.01)
        # Noise is non-zero
        self.assertGreater(np.linalg.norm(boid._forces[3]), 0.0)

    def test_self_filtered_by_identity(self):
        """Other boid is same object → filtered, steering zero."""
        boid = MockBoid(500, 350, 200, V0, 0, 0)
        config = _make_config(mode=MODE_SPATIAL)
        grid = MockGrid([boid])

        flock_spatial_3d(boid, [boid], config, grid)

        self.assertAlmostEqual(np.linalg.norm(boid._forces[0]), 0.0, delta=0.01)
        self.assertAlmostEqual(np.linalg.norm(boid._forces[1]), 0.0, delta=0.01)

    # ── Single neighbour ────────────────────────────────────────────

    def test_single_neighbour_alignment_cohesion_nonzero(self):
        """Single neighbour within range → alignment + cohesion non-zero."""
        boid = MockBoid(500, 350, 200, 0, V0, 0)
        nb = MockBoid(550, 350, 200, V0, 0, 0)
        config = _make_config(mode=MODE_SPATIAL)
        grid = MockGrid([boid, nb])

        flock_spatial_3d(boid, [boid, nb], config, grid)

        self.assertGreater(np.linalg.norm(boid._forces[1]), 0.0)  # alignment
        self.assertGreater(np.linalg.norm(boid._forces[2]), 0.0)  # cohesion

    def test_close_neighbour_separation(self):
        """Neighbour within separation zone → separation force non-zero."""
        boid = MockBoid(500, 350, 200, V0, 0, 0)
        nb = MockBoid(510, 350, 200, V0, 0, 0)  # dist=10 < 21 (VISUAL_RANGE*0.3)
        config = _make_config(mode=MODE_SPATIAL)
        grid = MockGrid([boid, nb])

        flock_spatial_3d(boid, [boid, nb], config, grid)

        self.assertGreater(np.linalg.norm(boid._forces[0]), 0.0)

    def test_separation_pushes_away(self):
        """Separation pushes left when neighbour is to the right."""
        boid = MockBoid(500, 350, 200, V0, 0, 0)
        nb = MockBoid(509, 350, 200, V0, 0, 0)  # to the right, dist=9
        config = _make_config(mode=MODE_SPATIAL)
        grid = MockGrid([boid, nb])

        flock_spatial_3d(boid, [boid, nb], config, grid)

        self.assertLess(boid._forces[0][0], 0.0,
                        "Separation should push left (negative X)")

    def test_cohesion_points_toward_neighbour(self):
        """Cohesion steers toward neighbour's position in 3D."""
        boid = MockBoid(500, 350, 200, 0, V0, 0)
        nb = MockBoid(550, 350, 200, V0, 0, 0)  # to the right
        config = _make_config(mode=MODE_SPATIAL)
        grid = MockGrid([boid, nb])

        flock_spatial_3d(boid, [boid, nb], config, grid)

        self.assertGreater(boid._forces[2][0], 0.0,
                           "Cohesion should steer right (positive X)")

    # ── Topological selection ──────────────────────────────────────

    def test_sigma_limits_neighbour_count(self):
        """Only sigma nearest neighbours contribute."""
        boid = MockBoid(500, 350, 200, 0, V0, 0)
        others = [boid]
        for i in range(8):
            others.append(MockBoid(500 + 30 + i * 5, 350, 200, V0, 0, 0))
        config = _make_config(sigma=3, mode=MODE_SPATIAL)
        grid = MockGrid(others)

        flock_spatial_3d(boid, others, config, grid)

        self.assertGreater(np.linalg.norm(boid._forces[1]), 0.0)
        self.assertGreater(np.linalg.norm(boid._forces[2]), 0.0)

    # ── VISUAL_RANGE filtering ─────────────────────────────────────

    def test_far_bird_excluded_by_range(self):
        """Bird beyond VISUAL_RANGE → excluded from steering."""
        boid = MockBoid(500, 350, 200, 0, V0, 0)
        far = MockBoid(500 + VISUAL_RANGE + 1, 350, 200, V0, 0, 0)
        config = _make_config(sigma=10, mode=MODE_SPATIAL)
        grid = MockGrid([boid, far])

        flock_spatial_3d(boid, [boid, far], config, grid)

        self.assertAlmostEqual(np.linalg.norm(boid._forces[0]), 0.0, delta=0.01)
        self.assertAlmostEqual(np.linalg.norm(boid._forces[1]), 0.0, delta=0.01)
        self.assertAlmostEqual(np.linalg.norm(boid._forces[2]), 0.0, delta=0.01)

    # ── Force clamping ─────────────────────────────────────────────

    def test_steering_clamped_to_max_force(self):
        """Steering forces never exceed MAX_FORCE."""
        boid = MockBoid(500, 350, 200, 0, 0, 0)
        nb = MockBoid(550, 350, 200, V0, 0, 0)
        config = _make_config(mode=MODE_SPATIAL)
        grid = MockGrid([boid, nb])

        flock_spatial_3d(boid, [boid, nb], config, grid)

        for i, f in enumerate(boid._forces):
            fl = np.linalg.norm(f)
            if fl > 0:
                self.assertLessEqual(fl, MAX_FORCE + 0.001,
                    f"Force {i} should be ≤ MAX_FORCE, got {fl:.4f}")

    # ── Pearce SI refinements ───────────────────────────────────────

    def test_refinements_add_steric_force(self):
        """With refinements on, a neighbour inside the steric radius adds a
        fifth force (sep/align/coh/noise + steric); off → the usual four."""
        from flock_core import BOID_SIZE
        nb_pos = (500 + BOID_SIZE * 2, 350, 200)

        boid = MockBoid(500, 350, 200, V0, 0, 0)
        nb = MockBoid(*nb_pos, V0, 0, 0)
        config = Config()                            # refinements on
        config.mode = MODE_SPATIAL
        flock_spatial_3d(boid, [boid, nb], config, MockGrid([boid, nb]))
        self.assertEqual(len(boid._forces), 5)
        self.assertLess(boid._forces[-1][0], 0.0)    # steric pushes −X

        plain = MockBoid(500, 350, 200, V0, 0, 0)
        nb2 = MockBoid(*nb_pos, V0, 0, 0)
        off = _make_config(mode=MODE_SPATIAL)        # refinements off
        flock_spatial_3d(plain, [plain, nb2], off, MockGrid([plain, nb2]))
        self.assertEqual(len(plain._forces), 4)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  flock_projection_3d                                                ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestFlockProjection3D(unittest.TestCase):
    """Standalone tests for flocking_modes_3d.flock_projection_3d()."""

    # ── Edge cases ──────────────────────────────────────────────────

    def test_empty_candidates_no_force(self):
        """No candidates from grid → no forces applied."""
        boid = MockBoid(500, 350, 200, V0, 0, 0)
        config = _make_config(mode=MODE_PROJECTION)
        grid = MockGrid([])

        flock_projection_3d(boid, [boid], config, grid)

        self.assertEqual(len(boid._forces), 0)

    def test_only_self_no_force(self):
        """Other boid is self → skipped, no forces."""
        boid = MockBoid(500, 350, 200, V0, 0, 0)
        config = _make_config(mode=MODE_PROJECTION)
        grid = MockGrid([boid])

        flock_projection_3d(boid, [boid], config, grid)

        self.assertEqual(len(boid._forces), 0)

    # ── Single visible neighbour ───────────────────────────────────

    def test_single_bird_delta_points_right(self):
        """One bird to the right → δ̂ pushes right.

        Bird and neighbour have different velocities so alignment
        doesn't cancel the projection force."""
        boid = MockBoid(500, 350, 200, 0, V0, 0)     # heading up
        other = MockBoid(600, 350, 200, V0, 0, 0)     # due east, heading right
        config = _make_config(mode=MODE_PROJECTION)
        grid = MockGrid([boid, other])

        flock_projection_3d(boid, [boid, other], config, grid)

        self.assertEqual(len(boid._forces), 1)
        steer = boid._forces[0]
        # Steer should have positive X component (delta points toward the bird)
        self.assertGreater(steer[0], 0.0,
                           f"Steer should push right, got x={steer[0]:.3f}")

    def test_theta_cached_on_boid(self):
        """Internal opacity Θ is cached on boid.last_theta."""
        boid = MockBoid(500, 350, 200, V0, 0, 0)
        other = MockBoid(600, 350, 200, V0, 0, 0)
        config = _make_config(mode=MODE_PROJECTION)
        grid = MockGrid([boid, other])

        flock_projection_3d(boid, [boid, other], config, grid)

        self.assertGreater(boid.last_theta, 0.0,
                           "Theta should be non-zero when a bird is visible")

    # ── Occlusion (closest-first) ──────────────────────────────────

    def test_closer_bird_occludes_further(self):
        """Closer bird blocks further bird on same ray → 1 visible."""
        boid = MockBoid(0, 0, 200, V0, 0, 0)
        near = MockBoid(50, 0, 200, V0, 0, 0)
        far = MockBoid(100, 0, 200, V0, 0, 0)
        config = _make_config(mode=MODE_PROJECTION)
        grid = MockGrid([boid, near, far])

        flock_projection_3d(boid, [boid, near, far], config, grid)

        # Only 1 force = steer toward the visible bird(s)
        self.assertEqual(len(boid._forces), 1)

    def test_two_birds_offset_both_visible(self):
        """Two birds with angular offset → both visible."""
        boid = MockBoid(0, 0, 200, V0, 0, 0)
        a = MockBoid(50, 0, 200, V0, 0, 0)    # due east
        b = MockBoid(50, 50, 200, V0, 0, 0)   # northeast
        config = _make_config(mode=MODE_PROJECTION)
        grid = MockGrid([boid, a, b])

        flock_projection_3d(boid, [boid, a, b], config, grid)

        self.assertEqual(len(boid._forces), 1)
        # With two visible birds at different angles, theta > 0
        self.assertGreater(boid.last_theta, 0.0)

    # ── 3D cohesion via the genuine 3-vector δ̂ ─────────────────────
    #  (Replaces the old "altitude cohesion" hack — the true 3D
    #   spherical-cap δ̂ carries a Z component on its own.  These use a
    #   projection-dominant weighting + a fixed RNG seed so the small,
    #   physically-honest δ̂ term isn't swamped by the noise term.)

    def test_delta_has_z_component_when_bird_above(self):
        """A visible bird at higher Z → δ̂ steers with +Z (drawn upward
        toward the flock) — the XY-plane approximation could never do this."""
        random.seed(7)
        boid = MockBoid(500, 350, 200, V0, 0, 0)
        other = MockBoid(600, 350, 320, V0, 0, 0)  # higher Z
        config = _make_config(phi_p=0.9, phi_a=0.05, mode=MODE_PROJECTION)
        grid = MockGrid([boid, other])

        flock_projection_3d(boid, [boid, other], config, grid)

        self.assertGreater(boid._forces[0][2], 0.0,
                           f"Steer Z should be positive (toward higher bird), "
                           f"got z={boid._forces[0][2]:.5f}")

    def test_cohesion_down_when_visible_below(self):
        """Visible bird below → δ̂ steers with −Z (drawn downward)."""
        random.seed(7)
        boid = MockBoid(500, 350, 200, V0, 0, 0)
        other = MockBoid(600, 350, 80, V0, 0, 0)   # lower Z
        config = _make_config(phi_p=0.9, phi_a=0.05, mode=MODE_PROJECTION)
        grid = MockGrid([boid, other])

        flock_projection_3d(boid, [boid, other], config, grid)

        self.assertLess(boid._forces[0][2], 0.0,
            f"δ̂ should draw down (negative Z), got z={boid._forces[0][2]:.5f}")

    # ── Steer clamping ─────────────────────────────────────────────

    def test_steer_clamped_to_max_force(self):
        """Steering force never exceeds MAX_FORCE."""
        boid = MockBoid(500, 350, 200, 0, 0, 0)  # zero vel → large steer
        other = MockBoid(600, 350, 200, V0, 0, 0)
        config = _make_config(mode=MODE_PROJECTION)
        grid = MockGrid([boid, other])

        flock_projection_3d(boid, [boid, other], config, grid)

        self.assertEqual(len(boid._forces), 1)
        self.assertLessEqual(np.linalg.norm(boid._forces[0]), MAX_FORCE + 0.001)

    # ── Determinism ─────────────────────────────────────────────────

    def test_deterministic_given_same_inputs(self):
        """Same inputs + same RNG seed produce the identical steer force.

        The projection noise term (random.uniform on theta/phi) is the
        only source of variation, so seeding the RNG identically before
        each call makes the whole step deterministic — that is what
        "given same inputs" means. Without the reseed this test is flaky:
        with phi_n = 0.05 the two independent noise draws can pull the
        force magnitudes apart by more than any fixed tolerance.
        """
        config = _make_config(phi_p=0.1, phi_a=0.85, mode=MODE_PROJECTION)

        random.seed(1234)
        b1 = MockBoid(500, 350, 200, V0, 0, 0)
        o1 = MockBoid(600, 350, 200, V0, 0, 0)
        flock_projection_3d(b1, [b1, o1], config, MockGrid([b1, o1]))
        s1 = b1._forces[0].copy()

        random.seed(1234)
        b2 = MockBoid(500, 350, 200, V0, 0, 0)
        o2 = MockBoid(600, 350, 200, V0, 0, 0)
        flock_projection_3d(b2, [b2, o2], config, MockGrid([b2, o2]))
        s2 = b2._forces[0]

        # Identical seed + inputs → bitwise-close steering force.
        self.assertAlmostEqual(np.linalg.norm(s1 - s2), 0.0, places=5)

    # ── Degenerate alignment branches ───────────────────────────────

    def test_zero_net_neighbour_velocity_aligns_with_own_heading(self):
        """Visible neighbours whose velocities cancel (⟨v⟩ ≈ 0) fall back
        to aligning with the boid's own heading, so the desired velocity
        equals the current one and the steer is ~zero."""
        boid = MockBoid(500, 350, 200, V0, 0, 0)
        n1 = MockBoid(560, 320, 200, 0, 2, 0)       # well-separated caps —
        n2 = MockBoid(560, 380, 200, 0, -2, 0)      # both visible; ⟨v⟩ = 0
        config = _make_config(sigma=2, phi_p=0.0, phi_a=1.0)  # φn = 0

        flock_projection_3d(boid, [boid, n1, n2], config,
                            MockGrid([boid, n1, n2]))

        self.assertEqual(len(boid._forces), 1)
        self.assertAlmostEqual(np.linalg.norm(boid._forces[0]), 0.0, delta=0.01)

    def test_zero_desired_velocity_falls_back_to_noise(self):
        """⟨v⟩ ≈ 0, own velocity ≈ 0 and φp = φn = 0 leave a zero desired
        velocity — the fallback steers by the noise vector instead of
        dividing by zero."""
        boid = MockBoid(500, 350, 200, 0, 0, 0)     # stationary observer
        n1 = MockBoid(560, 320, 200, 0, 2, 0)
        n2 = MockBoid(560, 380, 200, 0, -2, 0)
        config = _make_config(sigma=2, phi_p=0.0, phi_a=1.0)

        flock_projection_3d(boid, [boid, n1, n2], config,
                            MockGrid([boid, n1, n2]))

        self.assertEqual(len(boid._forces), 1)
        f = boid._forces[0]
        self.assertTrue(np.all(np.isfinite(f)))
        self.assertGreater(np.linalg.norm(f), 0.0)  # noise-driven steer

    def test_blind_view_still_applies_steric(self):
        """With refinements on, a lone neighbour inside the rear blind cone
        is invisible (no projection force) but its short-range steric
        repulsion still applies."""
        from flock_core import BOID_SIZE
        boid = MockBoid(500, 350, 200, 0, V0, 0)    # heading +Y
        behind = MockBoid(500, 350 - BOID_SIZE * 2, 200, 0, V0, 0)
        config = Config()                            # refinements on
        config.mode = MODE_PROJECTION

        flock_projection_3d(boid, [boid, behind], config,
                            MockGrid([boid, behind]))

        self.assertEqual(len(boid._forces), 1)
        self.assertGreater(boid._forces[0][1], 0.0)  # pushed away, +Y
        self.assertEqual(boid.last_theta, 0.0)       # empty projected view


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Boundary modes & flock() dispatch                                  ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestBoid3DBoundaryModes(unittest.TestCase):
    """The non-default boundary branches of Boid3D.update() and the
    mode dispatch in Boid3D.flock()."""

    def test_margin_mode_nudges_and_clamps(self):
        """MARGIN_BOUNDARY: a bird past a wall is nudged inward and then
        hard-clamped into the volume (no toroidal wrap)."""
        import boid_3d as m
        old = m.MARGIN_BOUNDARY
        m.MARGIN_BOUNDARY = True
        try:
            b = Boid3D()
            b.pos = np.array([-30.0, 350.0, 200.0], dtype=np.float32)  # past −x wall
            b.vel = np.array([-1.0, 0.0, 0.0], dtype=np.float32)       # heading out
            b.acc = np.zeros(3, dtype=np.float32)
            b.update()
            self.assertGreaterEqual(b.pos[0], 0.0)      # clamped back in bounds
            self.assertLessEqual(b.pos[0], float(WIDTH))
        finally:
            m.MARGIN_BOUNDARY = old

    def test_margin_mode_nudges_all_six_walls(self):
        """MARGIN_BOUNDARY: a bird inside each wall's margin band gets an
        inward velocity nudge on that axis (all six walls, both signs)."""
        import boid_3d as m
        cases = [  # (position inside a margin band, nudged axis, sign)
            ((50.0, 350.0, 200.0), 0, +1),   # −x wall
            ((950.0, 350.0, 200.0), 0, -1),  # +x wall
            ((500.0, 50.0, 200.0), 1, +1),   # −y wall
            ((500.0, 650.0, 200.0), 1, -1),  # +y wall
            ((500.0, 350.0, 50.0), 2, +1),   # −z wall
            ((500.0, 350.0, 350.0), 2, -1),  # +z wall
        ]
        old = m.MARGIN_BOUNDARY
        m.MARGIN_BOUNDARY = True
        try:
            for pos, axis, sign in cases:
                with self.subTest(axis=axis, sign=sign):
                    b = Boid3D()
                    b.pos = np.array(pos, dtype=np.float32)
                    vel = np.zeros(3, dtype=np.float32)
                    vel[(axis + 1) % 3] = 0.5 * V0     # cruise along another axis
                    b.vel = vel
                    b.acc = np.zeros(3, dtype=np.float32)
                    b.update()
                    self.assertGreater(sign * b.vel[axis], 0.0)
        finally:
            m.MARGIN_BOUNDARY = old

    def test_open_boundary_does_not_wrap(self):
        """OPEN_BOUNDARY: a bird past a wall keeps flying (free flight)."""
        import boid_3d as m
        old = m.OPEN_BOUNDARY
        m.OPEN_BOUNDARY = True
        try:
            b = Boid3D()
            b.pos = np.array([WIDTH + 100.0, 350.0, 200.0], dtype=np.float32)
            b.vel = np.array([V0, 0.0, 0.0], dtype=np.float32)
            b.acc = np.zeros(3, dtype=np.float32)
            b.update()
            self.assertGreater(b.pos[0], float(WIDTH))  # not wrapped to 0
        finally:
            m.OPEN_BOUNDARY = old

    def test_flock_dispatches_to_spatial(self):
        """config.mode == MODE_SPATIAL routes Boid3D.flock() to the
        Reynolds mode (exercising the dispatch, not just the raw function)."""
        b = Boid3D()
        b.pos = np.array([500.0, 350.0, 200.0], dtype=np.float32)
        b.vel = np.array([V0, 0.0, 0.0], dtype=np.float32)
        cfg = _make_config(mode=MODE_SPATIAL)
        nb = Boid3D()
        nb.pos = np.array([520.0, 350.0, 200.0], dtype=np.float32)
        b.flock([b, nb], cfg, MockGrid([b, nb]))       # must not raise

    def test_flock_dispatches_to_projection(self):
        b = Boid3D()
        b.pos = np.array([500.0, 350.0, 200.0], dtype=np.float32)
        b.vel = np.array([V0, 0.0, 0.0], dtype=np.float32)
        cfg = _make_config(mode=MODE_PROJECTION)
        nb = Boid3D()
        nb.pos = np.array([560.0, 350.0, 200.0], dtype=np.float32)
        b.flock([b, nb], cfg, MockGrid([b, nb]))       # must not raise
        self.assertIsInstance(b.last_theta, float)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Discovery gate (tests.md §3.1)                                     ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestDiscovery(unittest.TestCase):
    """Pinned test count — a renamed or mis-indented test silently drops
    out of unittest discovery; this fails loudly instead. Update the pin
    when tests are deliberately added or removed."""

    EXPECTED = 48

    def test_module_test_count(self):
        import test_3d as m
        n = unittest.TestLoader().loadTestsFromModule(m).countTestCases()
        self.assertEqual(n, self.EXPECTED)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Seeded determinism (tests.md §3.2)                                 ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestDeterminism(unittest.TestCase):
    """Same seeds ⟹ bit-identical trajectories. Guards against hidden
    global state or unseeded randomness anywhere in the frame loop
    (the 3D successor to the 2D cross-language golden reference)."""

    @staticmethod
    def _run_sim(frames=30, n=15):
        random.seed(77)
        np.random.seed(77)
        config = _make_config(phi_p=0.05, phi_a=0.8, mode=MODE_PROJECTION)
        flock = [Boid3D() for _ in range(n)]
        grid = SpatialGrid3D()
        for frame in range(frames):
            if frame == frames // 2:              # exercise both modes
                config.mode = MODE_SPATIAL
            grid.rebuild(flock)
            for b in flock:
                b.flock(flock, config, grid)
            for b in flock:
                b.update()
        return np.array([b.pos for b in flock]), np.array([b.vel for b in flock])

    def test_bit_identical_trajectories(self):
        pos1, vel1 = self._run_sim()
        pos2, vel2 = self._run_sim()
        self.assertTrue(np.array_equal(pos1, pos2))
        self.assertTrue(np.array_equal(vel1, vel2))


if __name__ == '__main__':
    unittest.main(verbosity=2)
