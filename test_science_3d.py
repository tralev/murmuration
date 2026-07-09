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

    def test_empty_returns_zero(self):
        from occlusion_3d import spherical_cap_occlusion
        d, vis, th = spherical_cap_occlusion(_StubBoid((0, 0, 0), (1, 0, 0)), [])
        self.assertEqual(list(d), [0, 0, 0])
        self.assertEqual(vis, [])
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


class TestAngularMomentumDispersion(unittest.TestCase):
    def test_straight_stream_low_angular_momentum(self):
        from metrics_3d import angular_momentum
        flock = [_StubBoid((i * 10, 0, 0), (4, 0, 0)) for i in range(30)]
        self.assertLess(angular_momentum(flock), 1e-6)

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
