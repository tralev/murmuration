"""
Unit tests for the 3D science modules ported from the founding papers:

  metrics_3d          — Pearce et al. (2014): order parameter, opacity
                        Θ/Θ', angular momentum, dispersion
  h2_robustness       — Young et al. (2013): consensus H₂, cost-optimal m*
  ecology             — Goodenough et al. (2017): seasonal size, critical
                        mass, predator presence
  scenario_presets_3d — the eight restored 3D scenario presets

No display or GPU is required — a tiny stub boid carries only .pos/.vel.
"""

import math
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np


class _StubBoid:
    """Minimal duck-typed boid: numpy Vec3 pos/vel + cached opacity."""
    def __init__(self, pos, vel, last_theta=0.0):
        self.pos = np.array(pos, dtype=float)
        self.vel = np.array(vel, dtype=float)
        self.last_theta = last_theta


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  occlusion_3d — true 3D spherical-cap projection (Pearce)             ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestSphericalCapOcclusion(unittest.TestCase):
    """Analytic 3D spherical-cap occlusion: δ̂ from domain boundaries, Θ,
    closest-first visibility."""

    def test_fibonacci_sphere_is_unit_vectors(self):
        from occlusion_3d import fibonacci_sphere
        pts = fibonacci_sphere(200)
        self.assertEqual(pts.shape, (200, 3))
        self.assertTrue(np.allclose(np.linalg.norm(pts, axis=1), 1.0))

    def test_fibonacci_sphere_degenerate_n(self):
        from occlusion_3d import fibonacci_sphere
        self.assertEqual(fibonacci_sphere(0).shape, (0, 3))
        one = fibonacci_sphere(1)
        self.assertEqual(one.shape, (1, 3))
        self.assertTrue(np.allclose(np.linalg.norm(one[0]), 1.0))

    def test_empty_returns_zero(self):
        from occlusion_3d import spherical_cap_occlusion
        d, vis, th = spherical_cap_occlusion(_StubBoid((0, 0, 0), (1, 0, 0)), [])
        self.assertEqual(list(d), [0, 0, 0])
        self.assertEqual(vis, [])

    def test_raw_point_neighbour_default_heading(self):
        """A neighbour given as a bare (x, y, z) point has no velocity —
        its heading defaults to +X and it is still projected."""
        from occlusion_3d import spherical_cap_occlusion
        obs = _StubBoid((0, 0, 0), (1, 0, 0))
        d, vis, th = spherical_cap_occlusion(obs, [(60.0, 0.0, 0.0)],
                                             anisotropy=2.0)
        self.assertEqual(len(vis), 1)
        self.assertGreater(th, 0.0)

    def test_coincident_neighbour_skipped(self):
        """A neighbour at the observer's exact position (d ≈ 0) is skipped
        rather than dividing by zero."""
        from occlusion_3d import spherical_cap_occlusion
        obs = _StubBoid((0, 0, 0), (1, 0, 0))
        d, vis, th = spherical_cap_occlusion(obs, [_StubBoid((0, 0, 0), (1, 0, 0))])
        self.assertEqual(vis, [])
        self.assertEqual(th, 0.0)
        self.assertEqual(th, 0.0)

    def test_delta_points_toward_single_neighbour(self):
        """δ̂ resolves toward a lone neighbour's silhouette (cohesion),
        even at a distance the old lattice method could not resolve."""
        from occlusion_3d import spherical_cap_occlusion
        obs = _StubBoid((0, 0, 0), (0, 1, 0))
        d, vis, th = spherical_cap_occlusion(obs, [_StubBoid((100, 0, 0), (1, 0, 0))])
        self.assertGreater(d[0], 0.9)          # toward +X (the bird)
        self.assertGreater(th, 0.0)            # non-zero opacity
        self.assertEqual(len(vis), 1)

    def test_delta_is_genuinely_3d(self):
        """A neighbour purely above → δ̂ has the Z component the old
        XY-plane approximation could never produce."""
        from occlusion_3d import spherical_cap_occlusion
        d, _, _ = spherical_cap_occlusion(_StubBoid((0, 0, 0), (1, 0, 0)),
                                          [_StubBoid((0, 0, 80), (1, 0, 0))])
        self.assertGreater(d[2], 0.9)

    def test_closest_first_occlusion(self):
        """A nearer bird hides a farther one directly behind it."""
        from occlusion_3d import spherical_cap_occlusion
        obs = _StubBoid((0, 0, 0), (1, 0, 0))
        d, vis, th = spherical_cap_occlusion(
            obs, [_StubBoid((30, 0, 0), (1, 0, 0)),
                  _StubBoid((60, 0, 0), (1, 0, 0))])  # same +X ray, behind
        self.assertEqual(len(vis), 1)

    def test_angularly_separated_both_visible(self):
        from occlusion_3d import spherical_cap_occlusion
        obs = _StubBoid((0, 0, 0), (1, 0, 0))
        _, vis, _ = spherical_cap_occlusion(
            obs, [_StubBoid((50, 0, 0), (1, 0, 0)),
                  _StubBoid((0, 50, 0), (1, 0, 0))])   # +X and +Y
        self.assertEqual(len(vis), 2)

    def test_theta_rises_with_more_neighbours(self):
        from occlusion_3d import spherical_cap_occlusion
        obs = _StubBoid((0, 0, 0), (1, 0, 0))
        _, _, th1 = spherical_cap_occlusion(obs, [_StubBoid((40, 0, 0), (1, 0, 0))])
        many = [_StubBoid((40 * math.cos(a), 40 * math.sin(a), 0), (1, 0, 0))
                for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)]
        _, _, th_many = spherical_cap_occlusion(obs, many)
        self.assertGreater(th_many, th1)
        self.assertLessEqual(th_many, 1.0)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Pearce SI refinements — steric, blind angles, anisotropic bodies     ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestStericRepulsion(unittest.TestCase):
    def test_pushes_away_from_close_bird(self):
        from steric_3d import steric_force
        from flock_core import BOID_SIZE
        f = steric_force(_StubBoid((0, 0, 0), (1, 0, 0)),
                         [_StubBoid((BOID_SIZE * 2, 0, 0), (1, 0, 0))])
        self.assertLess(f[0], 0.0)                 # pushed toward −X

    def test_no_push_beyond_radius(self):
        from steric_3d import steric_force, STERIC_RADIUS
        f = steric_force(_StubBoid((0, 0, 0), (1, 0, 0)),
                         [_StubBoid((STERIC_RADIUS + 50, 0, 0), (1, 0, 0))])
        self.assertTrue(np.allclose(f, 0.0))

    def test_closer_pushes_harder(self):
        from steric_3d import steric_force
        near = np.linalg.norm(steric_force(
            _StubBoid((0, 0, 0), (1, 0, 0)), [_StubBoid((6, 0, 0), (1, 0, 0))]))
        far = np.linalg.norm(steric_force(
            _StubBoid((0, 0, 0), (1, 0, 0)), [_StubBoid((11, 0, 0), (1, 0, 0))]))
        self.assertGreater(near, far)

    def test_self_is_excluded(self):
        from steric_3d import steric_force
        b = _StubBoid((0, 0, 0), (1, 0, 0))
        self.assertTrue(np.allclose(steric_force(b, [b]), 0.0))

    def test_force_clamped_to_max_force(self):
        from steric_3d import steric_force
        from flock_core import MAX_FORCE
        # 1/d² at d = 0.01 is huge — the clamp must cap it at MAX_FORCE.
        f = steric_force(_StubBoid((0, 0, 0), (1, 0, 0)),
                         [_StubBoid((0.01, 0, 0), (1, 0, 0))])
        self.assertAlmostEqual(np.linalg.norm(f), MAX_FORCE, places=6)


class TestBlindAngles(unittest.TestCase):
    def test_bird_behind_is_invisible(self):
        from occlusion_3d import spherical_cap_occlusion
        obs = _StubBoid((0, 0, 0), (0, 1, 0))       # heading +Y
        behind = _StubBoid((0, -40, 0), (1, 0, 0))  # directly behind
        bc = math.cos(math.radians(60) / 2)
        _, vis_no, _ = spherical_cap_occlusion(obs, [behind])
        _, vis_blind, _ = spherical_cap_occlusion(obs, [behind], blind_cos=bc)
        self.assertEqual(len(vis_no), 1)
        self.assertEqual(len(vis_blind), 0)

    def test_bird_ahead_still_visible_with_blind(self):
        from occlusion_3d import spherical_cap_occlusion
        obs = _StubBoid((0, 0, 0), (0, 1, 0))       # heading +Y
        ahead = _StubBoid((0, 40, 0), (1, 0, 0))    # in front
        bc = math.cos(math.radians(60) / 2)
        _, vis, _ = spherical_cap_occlusion(obs, [ahead], blind_cos=bc)
        self.assertEqual(len(vis), 1)


class TestAnisotropicBodies(unittest.TestCase):
    def test_broadside_bigger_than_end_on(self):
        from occlusion_3d import spherical_cap_occlusion
        obs = _StubBoid((0, 0, 0), (1, 0, 0))
        end_on = _StubBoid((60, 0, 0), (1, 0, 0))   # heading along view ray
        broad = _StubBoid((60, 0, 0), (0, 1, 0))    # heading across view ray
        _, _, th_end = spherical_cap_occlusion(obs, [end_on], anisotropy=3.0)
        _, _, th_broad = spherical_cap_occlusion(obs, [broad], anisotropy=3.0)
        self.assertGreater(th_broad, th_end)

    def test_isotropic_default_unchanged(self):
        from occlusion_3d import spherical_cap_occlusion
        obs = _StubBoid((0, 0, 0), (1, 0, 0))
        b = _StubBoid((50, 0, 0), (0, 1, 0))
        _, _, th1 = spherical_cap_occlusion(obs, [b])                 # default
        _, _, th2 = spherical_cap_occlusion(obs, [b], anisotropy=1.0)  # explicit
        self.assertAlmostEqual(th1, th2)


class TestConfigRefinements(unittest.TestCase):
    def test_blind_cos_off_when_disabled(self):
        from flock_core import Config
        c = Config()
        c.refinements = False
        self.assertIsNone(c.blind_cos)
        self.assertEqual(c.anisotropy_eff, 1.0)

    def test_blind_cos_on_by_default(self):
        from flock_core import Config
        c = Config()
        self.assertIsNotNone(c.blind_cos)
        self.assertGreater(c.anisotropy_eff, 1.0)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Goodenough dynamics — predator agent, roosting, day-length           ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestPredator3D(unittest.TestCase):
    def test_predator_chases_swarm_centre(self):
        from predator_3d import Predator3D
        pred = Predator3D(pos=(0, 0, 0), vel=(0, 0, 0))
        target = np.array([500.0, 350.0, 200.0])
        d0 = np.linalg.norm(target - pred.pos)
        for _ in range(30):
            pred.update(target)
        self.assertLess(np.linalg.norm(target - pred.pos), d0)

    def test_flee_points_away_and_scales(self):
        from predator_3d import flee_force, Predator3D, DANGER_RADIUS
        pred = Predator3D(pos=(0, 0, 0), vel=(0, 0, 0))
        near = flee_force(_StubBoid((20, 0, 0), (0, 0, 0)), pred)
        far = flee_force(_StubBoid((DANGER_RADIUS - 5, 0, 0), (0, 0, 0)), pred)
        self.assertGreater(near[0], 0.0)                # pushed +X, away
        self.assertGreater(np.linalg.norm(near), np.linalg.norm(far))

    def test_no_flee_outside_danger(self):
        from predator_3d import flee_force, Predator3D, DANGER_RADIUS
        pred = Predator3D(pos=(0, 0, 0), vel=(0, 0, 0))
        f = flee_force(_StubBoid((DANGER_RADIUS + 100, 0, 0), (0, 0, 0)), pred)
        self.assertTrue(np.allclose(f, 0.0))

    def test_apply_predator_pushes_a_near_bird(self):
        from predator_3d import Predator3D, apply_predator
        pred = Predator3D(pos=(500, 350, 200), vel=(0, 0, 0))
        b = _StubBoid((520, 350, 200), (0, 0, 0))
        b._acc = np.zeros(3)
        b.apply_force = lambda f: setattr(b, "_acc", b._acc + f)
        apply_predator([b], pred)
        self.assertTrue(np.linalg.norm(b._acc) > 0.0)

    def test_apply_predator_empty_flock_noop(self):
        """No birds → no centre of mass; the predator must not move."""
        from predator_3d import Predator3D, apply_predator
        pred = Predator3D(pos=(500, 350, 200), vel=(0, 0, 0))
        before = np.array(pred.pos, dtype=float).copy()
        apply_predator([], pred)
        self.assertTrue(np.allclose(pred.pos, before))


class TestRoostingDaylight(unittest.TestCase):
    def test_day_length_peaks_at_solstice(self):
        from ecology import day_length, SOLSTICE_DAY, DAY_LENGTH_MEAN
        self.assertGreater(day_length(SOLSTICE_DAY), DAY_LENGTH_MEAN)
        self.assertLess(day_length(SOLSTICE_DAY + 182), DAY_LENGTH_MEAN)

    def test_dusk_ramp_monotone(self):
        from ecology import dusk_factor, sunset_hour
        day = 15
        s = sunset_hour(day)
        self.assertLess(dusk_factor(s - 3, day), 0.5)
        self.assertAlmostEqual(dusk_factor(s, day), 0.5, places=2)
        self.assertGreater(dusk_factor(s + 3, day), 0.5)

    def test_roost_force_zero_by_day_pulls_at_dusk(self):
        from ecology import roost_force, sunset_hour
        day = 15
        roost = (500, 350, 40)
        pos = (500, 350, 300)                       # high above the roost
        day_f = roost_force(pos, sunset_hour(day) - 4, roost, day)
        night_f = roost_force(pos, sunset_hour(day) + 4, roost, day)
        self.assertAlmostEqual(np.linalg.norm(day_f), 0.0, places=3)
        self.assertLess(night_f[2], 0.0)            # roost is below → pulled down
        self.assertGreater(np.linalg.norm(night_f), np.linalg.norm(day_f))

    def test_dusk_factor_saturates_far_from_sunset(self):
        """The logistic ramp clamps to exactly 0/1 far from sunset instead
        of overflowing exp()."""
        from ecology import dusk_factor
        self.assertEqual(dusk_factor(0.0, 15), 0.0)     # deep pre-dawn
        self.assertEqual(dusk_factor(40.0, 15), 1.0)    # long past sunset

    def test_roost_force_zero_at_roost(self):
        """A bird already sitting on the roost feels no pull (d ≈ 0 guard)."""
        from ecology import roost_force
        roost = (500, 350, 40)
        f = roost_force(roost, 22.0, roost, 15)         # after sunset
        self.assertTrue(np.allclose(f, 0.0))

    def test_temperature_coldest_in_winter(self):
        from ecology import temperature
        self.assertLess(temperature(20), temperature(200))   # Jan < Jul

    def test_is_roosting_time(self):
        from ecology import is_roosting_time, sunset_hour
        day = 15
        self.assertFalse(is_roosting_time(sunset_hour(day) - 3, day))
        self.assertTrue(is_roosting_time(sunset_hour(day) + 3, day))


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  metrics_3d — Pearce observables                                      ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestOrderParameter(unittest.TestCase):
    def test_aligned_flock_is_one(self):
        from metrics_3d import order_parameter
        flock = [_StubBoid((i, 0, 0), (4, 0, 0)) for i in range(20)]
        self.assertAlmostEqual(order_parameter(flock), 1.0, places=6)

    def test_opposed_pairs_cancel_to_zero(self):
        from metrics_3d import order_parameter
        flock = ([_StubBoid((0, 0, 0), (4, 0, 0)) for _ in range(10)]
                 + [_StubBoid((0, 0, 0), (-4, 0, 0)) for _ in range(10)])
        self.assertAlmostEqual(order_parameter(flock), 0.0, places=6)

    def test_empty_flock(self):
        from metrics_3d import order_parameter
        self.assertEqual(order_parameter([]), 0.0)


class TestExternalOpacity(unittest.TestCase):
    def test_range(self):
        from metrics_3d import external_opacity
        random.seed(1)
        flock = [_StubBoid((random.uniform(0, 500), random.uniform(0, 500),
                            random.uniform(0, 300)), (1, 0, 0))
                 for _ in range(60)]
        theta = external_opacity(flock)
        self.assertGreaterEqual(theta, 0.0)
        self.assertLessEqual(theta, 1.0)

    def test_tight_cluster_more_opaque_than_spread(self):
        from metrics_3d import external_opacity
        tight = [_StubBoid((250 + random.uniform(-10, 10),
                            250 + random.uniform(-10, 10),
                            150 + random.uniform(-10, 10)), (1, 0, 0))
                 for _ in range(80)]
        spread = [_StubBoid((random.uniform(0, 900),
                             random.uniform(0, 600),
                             random.uniform(0, 400)), (1, 0, 0))
                  for _ in range(80)]
        random.seed(2)
        self.assertGreater(external_opacity(tight), external_opacity(spread))

    def test_degenerate(self):
        from metrics_3d import external_opacity
        self.assertEqual(external_opacity([]), 0.0)

    def test_degenerate_span_returns_zero(self):
        """Coincident zero-size birds project to a zero-area silhouette."""
        import metrics_3d as mm
        old = mm.BOID_SIZE
        mm.BOID_SIZE = 0.0
        try:
            flock = [_StubBoid((5, 5, 5), (1, 0, 0)) for _ in range(3)]
            self.assertEqual(mm.external_opacity(flock), 0.0)
        finally:
            mm.BOID_SIZE = old


class TestAngularMomentumDispersion(unittest.TestCase):
    def test_straight_stream_low_angular_momentum(self):
        from metrics_3d import angular_momentum
        flock = [_StubBoid((i * 10, 0, 0), (4, 0, 0)) for i in range(30)]
        self.assertLess(angular_momentum(flock), 1e-6)

    def test_empty_flock_zero_metrics(self):
        """Every raw metric returns 0 for an empty flock."""
        from metrics_3d import (internal_opacity, angular_momentum,
                                dispersion)
        self.assertEqual(internal_opacity([]), 0.0)
        self.assertEqual(angular_momentum([]), 0.0)
        self.assertEqual(dispersion([]), 0.0)

    def test_dispersion_matches_known_radius(self):
        from metrics_3d import dispersion
        # Four birds at ±10 on x about the origin → mean |r| = 10.
        flock = [_StubBoid((10, 0, 0), (0, 0, 0)),
                 _StubBoid((-10, 0, 0), (0, 0, 0)),
                 _StubBoid((0, 10, 0), (0, 0, 0)),
                 _StubBoid((0, -10, 0), (0, 0, 0))]
        self.assertAlmostEqual(dispersion(flock), 10.0, places=6)


class TestFlockMetrics3D(unittest.TestCase):
    def test_update_smooths_toward_raw(self):
        from metrics_3d import FlockMetrics3D, order_parameter
        flock = [_StubBoid((i, 0, 0), (4, 0, 0)) for i in range(20)]
        m = FlockMetrics3D()
        for _ in range(200):
            m.update(flock)
        self.assertAlmostEqual(m.order_param, order_parameter(flock), places=2)

    def test_summary_is_string(self):
        from metrics_3d import FlockMetrics3D
        m = FlockMetrics3D()
        m.update([_StubBoid((0, 0, 0), (4, 0, 0))])
        self.assertIn("α=", m.summary())

    def test_update_empty_flock_is_noop(self):
        from metrics_3d import FlockMetrics3D
        m = FlockMetrics3D()
        flock = [_StubBoid((i * 10, 0, 0), (4, 0, 0)) for i in range(10)]
        m.update(flock)
        before = (m.order_param, m.internal_opacity, m.external_opacity,
                  m.angular_momentum, m.dispersion)
        m.update([])                                # must not decay the EMAs
        after = (m.order_param, m.internal_opacity, m.external_opacity,
                 m.angular_momentum, m.dispersion)
        self.assertEqual(before, after)

    def test_properties_expose_all_five_emas(self):
        from metrics_3d import FlockMetrics3D
        m = FlockMetrics3D(smooth=1.0)              # no smoothing lag
        flock = [_StubBoid((i * 10, 0, 0), (4, 0, 0), last_theta=0.5)
                 for i in range(10)]
        m.update(flock)
        self.assertAlmostEqual(m.order_param, 1.0, places=6)   # aligned
        self.assertAlmostEqual(m.internal_opacity, 0.5, places=6)
        self.assertGreaterEqual(m.external_opacity, 0.0)
        self.assertGreaterEqual(m.angular_momentum, 0.0)
        self.assertGreater(m.dispersion, 0.0)                  # spread line


class TestMarginalOpacity(unittest.TestCase):
    """Pearce's emergent 'marginal opacity': a self-organised flock at the
    default density settles to internal opacity Θ≈0.30, not the ~0.04 seen
    when the body radius b is far too small for the domain (regression guard
    on BOID_SIZE, see flock_core). Full steady state (mean Θ≈0.30 across seeds)
    is reached by ~500 frames; 350 frames already lifts Θ well clear of the
    sparse-flock floor.

    Running the dynamics to condensation costs ~25s, so this is gated behind
    RUN_SLOW_TESTS (set in CI) and skipped by the fast pre-commit hook."""

    @unittest.skipUnless(os.environ.get("RUN_SLOW_TESTS"),
                         "slow integration test — set RUN_SLOW_TESTS=1")
    def test_default_flock_reaches_marginal_band(self):
        import random
        from boid_3d import Boid3D
        from spatial_grid_3d import SpatialGrid3D
        from metrics_3d import internal_opacity
        from flock_core import Config, NUM_BOIDS

        random.seed(1)
        np.random.seed(1)
        cfg = Config()
        cfg.num_boids = NUM_BOIDS
        grid = SpatialGrid3D()
        flock = [Boid3D() for _ in range(NUM_BOIDS)]
        tail = []
        for f in range(350):
            grid.rebuild(flock)
            for b in flock:
                b.flock(flock, cfg, grid)
            for b in flock:
                b.update()
            if f >= 310:
                tail.append(internal_opacity(flock))
        theta = float(np.mean(tail))
        # Comfortably above the sparse-flock collapse (~0.04) and physical.
        self.assertGreater(theta, 0.10)
        self.assertLess(theta, 0.60)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  density_scaling — is marginal opacity N-independent? (Pearce)        ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestDensityEstimators(unittest.TestCase):
    """Fast, deterministic checks of the straggler-robust geometry estimators
    that the density-scaling analysis is built on."""

    def test_local_spacing_on_a_line(self):
        from density_scaling import local_spacing
        pts = [(10.0 * i, 0.0, 0.0) for i in range(12)]   # 1-D lattice, step 10
        self.assertAlmostEqual(local_spacing(pts, k=1), 10.0, places=6)

    def test_local_spacing_too_few_points(self):
        from density_scaling import local_spacing
        self.assertEqual(local_spacing([(0, 0, 0), (1, 0, 0)], k=7), 0.0)

    def test_gyration_radius_of_a_shell(self):
        from density_scaling import gyration_radius
        rng = np.random.default_rng(0)
        v = rng.normal(size=(400, 3))
        v /= np.linalg.norm(v, axis=1, keepdims=True)     # unit sphere, R=50
        pts = v * 50.0
        self.assertAlmostEqual(gyration_radius(pts, keep=1.0), 50.0, delta=1.0)

    def test_gyration_trims_stragglers(self):
        from density_scaling import gyration_radius
        pts = [(1.0, 0, 0), (-1.0, 0, 0), (0, 1.0, 0), (0, -1.0, 0),
               (10000.0, 0, 0)]                            # one far outlier
        # Trimming the top 20% drops the outlier, so Rg stays O(1).
        self.assertLess(gyration_radius(pts, keep=0.8), 5.0)

    def test_number_density_positive_and_scales(self):
        from density_scaling import number_density
        rng = np.random.default_rng(1)
        loose = rng.normal(0, 100, (200, 3))
        tight = rng.normal(0, 30, (200, 3))
        self.assertGreater(number_density(tight), number_density(loose))

    def test_gyration_degenerate_inputs(self):
        from density_scaling import gyration_radius
        self.assertEqual(gyration_radius([(1.0, 2.0, 3.0)]), 0.0)  # 1 point
        self.assertEqual(gyration_radius(np.zeros((0, 3))), 0.0)   # empty

    def test_number_density_degenerate_flock(self):
        """Coincident birds have Rg = 0 — density is 0, not a division
        by a zero-volume sphere."""
        from density_scaling import number_density
        self.assertEqual(number_density([(5.0, 5.0, 5.0)] * 4), 0.0)

    def test_settle_and_measure_accept_phi_overrides(self):
        """settle_flock/measure_point with explicit φp/φa overrides (tiny
        flock and frame counts — this checks plumbing, not physics)."""
        from density_scaling import settle_flock, measure_point
        pts = settle_flock(4, phi_p=0.05, phi_a=0.6, frames=2, seed=0)
        self.assertEqual(pts.shape, (4, 3))
        rep = measure_point(4, phi_p=0.05, frames=3, seeds=(0,), tail=2)
        self.assertEqual(rep["n"], 4)
        for key in ("spacing", "density", "size", "theta_ext"):
            self.assertTrue(np.isfinite(rep[key]))


class TestDensityScaling(unittest.TestCase):
    """Marginal opacity is N-independent only if density ~ N^(−1/2). This runs
    the open-boundary sweep and checks the analysis pipeline is well-formed and
    honest (finite fitted exponents, positive densities). It deliberately does
    *not* assert the ideal exponent — the current cohesion+steric δ̂ does not
    reach it (see sci.md §4.9); the tool exists to measure that gap, not to
    paper over it. Gated behind RUN_SLOW_TESTS as it runs the dynamics."""

    @unittest.skipUnless(os.environ.get("RUN_SLOW_TESTS"),
                         "slow integration test — set RUN_SLOW_TESTS=1")
    def test_scaling_sweep_is_well_formed(self):
        import math
        from density_scaling import measure_scaling, IDEAL_DENSITY_EXPONENT
        res = measure_scaling(n_values=(40, 80, 160), frames=250, seeds=(0,))
        self.assertEqual([p["n"] for p in res["points"]], [40, 80, 160])
        for p in res["points"]:
            self.assertGreater(p["density"], 0.0)
            self.assertGreater(p["spacing"], 0.0)
            self.assertGreaterEqual(p["theta_ext"], 0.0)
        self.assertTrue(math.isfinite(res["density_exponent"]))
        self.assertTrue(math.isfinite(res["size_exponent"]))
        self.assertEqual(res["ideal_density_exponent"], IDEAL_DENSITY_EXPONENT)

    def test_open_boundary_context_restores(self):
        import boid_3d
        from density_scaling import open_boundary
        before = boid_3d.OPEN_BOUNDARY
        with open_boundary(True):
            self.assertTrue(boid_3d.OPEN_BOUNDARY)
        self.assertEqual(boid_3d.OPEN_BOUNDARY, before)

    # ── fast, pure-function checks (no dynamics) ────────────────────

    def test_fit_exponent_recovers_slope(self):
        from density_scaling import _fit_exponent
        ns = [10, 100, 1000]
        ys = [2.0 * n ** 0.5 for n in ns]              # y ∝ N^0.5
        self.assertAlmostEqual(_fit_exponent(ns, ys), 0.5, places=6)

    def test_fit_exponent_nan_when_too_few_points(self):
        import math
        from density_scaling import _fit_exponent
        self.assertTrue(math.isnan(_fit_exponent([10], [1.0])))

    def test_settle_flock_returns_positions(self):
        from density_scaling import settle_flock
        pts = settle_flock(n=12, frames=5, seed=0)     # tiny + short = fast
        self.assertEqual(pts.shape, (12, 3))

    def test_format_report_renders_exponents(self):
        from density_scaling import format_report, IDEAL_DENSITY_EXPONENT
        result = {
            "points": [{"n": 40, "spacing": 50.0, "density": 1e-6,
                        "size": 300.0, "theta_ext": 0.2}],
            "density_exponent": 0.4,
            "size_exponent": 0.3,
            "ideal_density_exponent": IDEAL_DENSITY_EXPONENT,
            "ideal_size_exponent": 0.5,
        }
        text = format_report(result)
        self.assertIn("density ~ N^", text)
        self.assertIn("40", text)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  h2_robustness — Young consensus robustness (3D)                      ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestH2Robustness3D(unittest.TestCase):
    def _cloud(self, n, seed):
        random.seed(seed)
        return [(random.uniform(0, 300), random.uniform(0, 300),
                 random.uniform(0, 200)) for _ in range(n)]

    def test_symmetric_eigenvalues_known(self):
        from h2_robustness import symmetric_eigenvalues
        eig = symmetric_eigenvalues([[2.0, 1.0], [1.0, 2.0]])
        self.assertAlmostEqual(eig[0], 1.0, places=6)
        self.assertAlmostEqual(eig[1], 3.0, places=6)

    def test_laplacian_rows_sum_to_zero(self):
        from h2_robustness import knn_laplacian
        lap = knn_laplacian(self._cloud(15, 3), 4)
        for row in lap:
            self.assertAlmostEqual(float(sum(row)), 0.0, places=6)

    def test_more_neighbours_more_robust(self):
        from h2_robustness import h2_norm
        pts = self._cloud(30, 5)
        self.assertGreater(h2_norm(pts, 3), h2_norm(pts, 9))

    def test_disconnected_is_infinite(self):
        from h2_robustness import h2_norm
        # Two far-apart 3D pairs; m=1 links only within each pair.
        pts = [(0, 0, 0), (1, 0, 0), (1000, 0, 0), (1001, 0, 0)]
        self.assertEqual(h2_norm(pts, 1), math.inf)

    def test_cost_optimal_m_in_young_range(self):
        from h2_robustness import cost_optimal_m
        best_m, _ = cost_optimal_m(self._cloud(50, 7))
        self.assertGreaterEqual(best_m, 4)
        self.assertLessEqual(best_m, 10)

    def test_accepts_boid_objects(self):
        from h2_robustness import h2_norm
        flock = [_StubBoid((random.uniform(0, 200), random.uniform(0, 200),
                            random.uniform(0, 200)), (0, 0, 0))
                 for _ in range(20)]
        random.seed(9)
        self.assertGreaterEqual(h2_norm(flock, 5), 0.0)

    def test_empty_and_degenerate_inputs(self):
        from h2_robustness import (symmetric_eigenvalues, knn_laplacian,
                                   h2_norm)
        self.assertEqual(symmetric_eigenvalues([]), [])
        self.assertEqual(knn_laplacian([], 3).shape, (0, 0))
        self.assertEqual(h2_norm([(0.0, 0.0, 0.0)], 1), 0.0)   # n < 2 → 0

    def test_eta_of_m_is_finite_and_nonneg(self):
        from h2_robustness import eta_of_m
        eta = eta_of_m(self._cloud(40, 8), m=6)
        self.assertTrue(eta >= 0.0 or eta == float("inf"))

    def test_accepts_attr_points(self):
        """Points exposing .x/.y (no .z) coerce with z = 0."""
        import types as _t
        from h2_robustness import h2_norm
        pts = [_t.SimpleNamespace(x=float(i % 3) * 10, y=float(i // 3) * 10)
               for i in range(9)]
        self.assertGreaterEqual(h2_norm(pts, 3), 0.0)

    def test_eta_degenerate_m_equals_m0(self):
        from h2_robustness import eta_of_m
        pts = self._cloud(20, 11)
        self.assertEqual(eta_of_m(pts, m=3, m0=3), 0.0)

    def test_eta_connectivity_transitions(self):
        """Two far-apart triads: small m leaves the graph disconnected
        (H₂ = ∞). The neighbour that first connects it is worth η = ∞;
        while both graphs are disconnected η is 0."""
        from h2_robustness import eta_of_m
        pts = [(0, 0, 0), (10, 0, 0), (0, 10, 0),
               (1000, 0, 0), (1010, 0, 0), (1000, 10, 0)]
        self.assertEqual(eta_of_m(pts, m=5, m0=1), math.inf)  # ∞ → finite
        self.assertEqual(eta_of_m(pts, m=2, m0=1), 0.0)       # ∞ → ∞


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ecology — Goodenough seasonal / critical mass / predator             ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestEcology(unittest.TestCase):
    def test_seasonal_peak_and_trough(self):
        from ecology import seasonal_size_factor, PEAK_DAY, MIN_FACTOR
        self.assertAlmostEqual(seasonal_size_factor(PEAK_DAY), 1.0, places=6)
        self.assertAlmostEqual(seasonal_size_factor(PEAK_DAY + 182),
                               MIN_FACTOR, places=2)

    def test_seasonal_bounds(self):
        from ecology import seasonal_size_factor, MIN_FACTOR
        for d in range(1, 366):
            f = seasonal_size_factor(d)
            self.assertGreaterEqual(f, MIN_FACTOR - 1e-9)
            self.assertLessEqual(f, 1.0 + 1e-9)

    def test_coherence_gate(self):
        from ecology import coherence_factor, has_critical_mass
        self.assertLess(coherence_factor(100), coherence_factor(600))
        self.assertFalse(has_critical_mass(100))
        self.assertTrue(has_critical_mass(600))

    def test_gated_weight(self):
        from ecology import gated_weight
        self.assertAlmostEqual(gated_weight(0.8, 10), 0.0, places=4)
        self.assertGreater(gated_weight(0.8, 600), 0.7)

    def test_season_window(self):
        from ecology import is_murmuration_season
        self.assertTrue(is_murmuration_season(15))     # January
        self.assertFalse(is_murmuration_season(196))   # July

    def test_predator_deterministic_per_day(self):
        from ecology import predator_present
        self.assertEqual(predator_present(42), predator_present(42))

    def test_predator_drawn_from_rng(self):
        """With an rng the presence is a draw against PREDATOR_RATE, not the
        per-day hash."""
        import types as _t
        from ecology import predator_present
        self.assertTrue(predator_present(42, rng=_t.SimpleNamespace(
            random=lambda: 0.0)))
        self.assertFalse(predator_present(42, rng=_t.SimpleNamespace(
            random=lambda: 0.999)))

    def test_flock_size_for_day(self):
        from ecology import flock_size_for_day, PEAK_DAY
        self.assertEqual(flock_size_for_day(PEAK_DAY, 500), 500)
        # Summer trough scales down but never below min_size.
        self.assertGreaterEqual(flock_size_for_day(PEAK_DAY + 182, 100,
                                                   min_size=95), 95)

    def test_coherence_midpoint_partial(self):
        """Inside the ramp [0.4·N_crit, 1.2·N_crit] the smoothstep is
        strictly between the extremes."""
        from ecology import coherence_factor, CRITICAL_MASS
        f = coherence_factor(CRITICAL_MASS)
        self.assertGreater(f, 0.0)
        self.assertLess(f, 1.0)

    def test_coherence_degenerate_critical_mass(self):
        """critical_mass = 0 collapses the ramp — every flock is coherent."""
        from ecology import coherence_factor
        self.assertEqual(coherence_factor(10, critical_mass=0), 1.0)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  flock_shape — Young shape → optimal m* (3D)                          ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestFlockShape3D(unittest.TestCase):
    def test_thin_flock_low_m(self):
        from flock_shape import analyze_shape
        thin = [_StubBoid((x, 0.0, 0.0), (0, 0, 0)) for x in range(0, 600, 15)]
        rep = analyze_shape(thin)
        self.assertGreater(rep.aspect_ratio, 3.0)
        self.assertLessEqual(rep.suggested_m, 7.0)

    def test_round_flock_high_m(self):
        from flock_shape import analyze_shape
        random.seed(3)
        rnd = [_StubBoid((random.uniform(-50, 50), random.uniform(-50, 50),
                          random.uniform(-50, 50)), (0, 0, 0)) for _ in range(80)]
        rep = analyze_shape(rnd)
        self.assertLess(rep.aspect_ratio, 1.8)
        self.assertGreater(rep.suggested_m, 8.0)

    def test_thickness_ratio_bounds(self):
        from flock_shape import analyze_shape
        random.seed(4)
        rnd = [_StubBoid((random.uniform(-40, 40), random.uniform(-40, 40),
                          random.uniform(-40, 40)), (0, 0, 0)) for _ in range(50)]
        rep = analyze_shape(rnd)
        self.assertGreater(rep.thickness_ratio, 0.0)
        self.assertLessEqual(rep.thickness_ratio, 1.0)

    def test_m_star_monotone(self):
        from flock_shape import suggested_m_star
        self.assertGreater(suggested_m_star(1.0), suggested_m_star(3.0))

    def test_degenerate_few_points(self):
        from flock_shape import analyze_shape
        rep = analyze_shape([_StubBoid((0, 0, 0), (0, 0, 0)),
                             _StubBoid((1, 1, 1), (0, 0, 0))])
        self.assertEqual(rep.count, 2)

    def test_repr_readout(self):
        from flock_shape import analyze_shape
        rep = analyze_shape([_StubBoid((x, 0.0, 0.0), (0, 0, 0))
                             for x in range(0, 100, 10)])
        s = repr(rep)
        self.assertIn("ShapeReport", s)
        self.assertIn("aspect=", s)

    def test_accepts_raw_points(self):
        """Bare (x, y, z) tuples work as well as boids (the _as_xyz
        fallback)."""
        from flock_shape import analyze_shape
        rep = analyze_shape([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
                             (0.0, 10.0, 0.0), (0.0, 0.0, 10.0)])
        self.assertEqual(rep.count, 4)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  correlation_time — Pearce τρ (3D hull volume)                        ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestCorrelationTime3D(unittest.TestCase):
    def test_cube_volume(self):
        from correlation_time import convex_hull_volume
        cube = [_StubBoid(p, (0, 0, 0)) for p in
                [(0, 0, 0), (10, 0, 0), (0, 10, 0), (0, 0, 10),
                 (10, 10, 10), (10, 10, 0), (10, 0, 10), (0, 10, 10)]]
        self.assertAlmostEqual(convex_hull_volume(cube), 1000.0, places=3)

    def test_degenerate_returns_zero(self):
        from correlation_time import convex_hull_volume
        # Fewer than 4 points, and coplanar points, have no 3D volume.
        self.assertEqual(convex_hull_volume(
            [_StubBoid((0, 0, 0), (0, 0, 0)), _StubBoid((1, 1, 1), (0, 0, 0))]),
            0.0)
        coplanar = [_StubBoid((x, y, 0), (0, 0, 0))
                    for x in (0, 1) for y in (0, 1)]
        self.assertEqual(convex_hull_volume(coplanar), 0.0)

    def test_tracker_accumulates_samples(self):
        from correlation_time import CorrelationTimeTracker, SAMPLE_INTERVAL
        random.seed(5)
        t = CorrelationTimeTracker()
        for _ in range(SAMPLE_INTERVAL * 20):
            flock = [_StubBoid((random.uniform(0, 100), random.uniform(0, 100),
                                random.uniform(0, 100)), (0, 0, 0))
                     for _ in range(20)]
            t.sample(flock)
        self.assertEqual(t.n_samples, 20)
        self.assertGreaterEqual(t.tau, 0.0)

    def test_tau_zero_before_enough_samples(self):
        from correlation_time import CorrelationTimeTracker
        t = CorrelationTimeTracker()
        t.sample([_StubBoid((0, 0, 0), (0, 0, 0))])
        self.assertEqual(t.tau, 0.0)

    def test_buffer_is_capped(self):
        """The density buffer drops its oldest sample past BUFFER_SIZE."""
        import correlation_time as ct
        random.seed(6)
        old = ct.BUFFER_SIZE
        ct.BUFFER_SIZE = 5
        try:
            t = ct.CorrelationTimeTracker()
            for _ in range(ct.SAMPLE_INTERVAL * 8):     # 8 samples → cap 5
                flock = [_StubBoid((random.uniform(0, 100),
                                    random.uniform(0, 100),
                                    random.uniform(0, 100)), (0, 0, 0))
                         for _ in range(12)]
                t.sample(flock)
            self.assertEqual(t.n_samples, 5)
        finally:
            ct.BUFFER_SIZE = old

    def test_constant_density_zero_tau(self):
        """A perfectly constant density has zero variance — τρ is 0, not
        a 0/0."""
        from correlation_time import CorrelationTimeTracker, SAMPLE_INTERVAL
        cube = [_StubBoid(p, (0, 0, 0)) for p in
                [(0, 0, 0), (10, 0, 0), (0, 10, 0), (0, 0, 10),
                 (10, 10, 10), (10, 10, 0), (10, 0, 10), (0, 10, 10)]]
        t = CorrelationTimeTracker()
        for _ in range(SAMPLE_INTERVAL * 10):           # 10 identical samples
            t.sample(cube)
        self.assertEqual(t.tau, 0.0)

    def test_hull_accepts_raw_points(self):
        """Bare (x, y, z) tuples work as well as boids (the _as_xyz
        fallback)."""
        from correlation_time import convex_hull_volume
        cube = [(0, 0, 0), (10, 0, 0), (0, 10, 0), (0, 0, 10),
                (10, 10, 10), (10, 10, 0), (10, 0, 10), (0, 10, 10)]
        self.assertAlmostEqual(convex_hull_volume(cube), 1000.0, places=3)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  scenario_presets_3d — restored 3D presets                            ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestScenarioPresets3D(unittest.TestCase):
    def test_eight_presets_with_expected_keys(self):
        from scenario_presets_3d import PRESETS_3D
        self.assertEqual(set(PRESETS_3D),
                         {'a', 'b', 'c', 'd', 'e', 'f', 'w', 'h'})

    def test_entries_well_formed(self):
        from scenario_presets_3d import PRESETS_3D
        fields = {"label", "phi_p", "phi_a", "sigma", "mode", "description"}
        for key, p in PRESETS_3D.items():
            self.assertSetEqual(set(p), fields, f"preset {key}")
            self.assertTrue(p["label"].startswith(f"PRESET {key} — "))
            # φp + φa ≤ 1 so φn = 1 − φp − φa stays non-negative.
            self.assertLessEqual(p["phi_p"] + p["phi_a"], 1.0 + 1e-9)

    def test_apply_mutates_config(self):
        from scenario_presets_3d import apply_preset_3d
        from flock_core import Config
        cfg = Config()
        label = apply_preset_3d(cfg, 'b')
        self.assertIn("Ball of Birds", label)
        self.assertAlmostEqual(cfg.phi_p, 0.18)
        self.assertEqual(cfg.sigma, 7)

    def test_bad_key_returns_empty(self):
        from scenario_presets_3d import apply_preset_3d
        from flock_core import Config
        self.assertEqual(apply_preset_3d(Config(), 'z'), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
