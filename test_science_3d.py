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
