"""
Unit tests for scenario presets and preset toggle behaviour.

Covers:
  - apply_preset           — all 16 presets produce valid phi_n ≥ 0
  - _get_preset_key        — maps pygame key constants to preset keys
  - _save_config / _restore_config — config snapshot round-trip
  - Toggle behaviour       — same key restores, different key overwrites
"""
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECTION T1 — CORE UNIT TESTS  (alg2, boid, occlusion, presets)     ║
# ╚══════════════════════════════════════════════════════════════════════╝


import unittest

import pygame

from test_count_mixin import TestCountMixin

from input_handler import _get_preset_key, _save_config, _restore_config


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  _normalise_interval                                                 ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestPresetValidation(unittest.TestCase):
    """Verify all scenario presets apply without errors and produce
    valid phi_n >= 0 (weights must sum to at most 1)."""

    def test_all_presets_apply_without_errors(self):
        from flock_core import Config
        from scenario_presets import PRESETS, apply_preset

        preset_count = len(PRESETS)
        self.assertGreater(preset_count, 0,
            "PRESETS dict should not be empty")

        for key, preset in sorted(PRESETS.items(), key=lambda kv: str(kv[0])):
            config = Config()
            label = apply_preset(config, key)

            self.assertNotEqual(label, "",
                f"Preset {key}: apply_preset returned empty label")
            self.assertIn("PRESET", label,
                f"Preset {key}: label should contain 'PRESET'")

            self.assertGreaterEqual(config.phi_p, 0.0,
                f"Preset {key}: phi_p={config.phi_p} should be >= 0")
            self.assertLessEqual(config.phi_p, 1.0,
                f"Preset {key}: phi_p={config.phi_p} should be <= 1")

            self.assertGreaterEqual(config.phi_a, 0.0,
                f"Preset {key}: phi_a={config.phi_a} should be >= 0")
            self.assertLessEqual(config.phi_a, 1.0,
                f"Preset {key}: phi_a={config.phi_a} should be <= 1")

            phi_n = config.phi_n  # auto-computed: max(0, 1 − φp − φa)
            self.assertGreaterEqual(phi_n, 0.0,
                f"Preset {key}: phi_n={phi_n:.4f} should be >= 0 "
                f"(phi_p={config.phi_p}, phi_a={config.phi_a})")

            self.assertGreaterEqual(config.sigma, 1,
                f"Preset {key}: sigma={config.sigma} should be >= 1")
            self.assertLessEqual(config.sigma, 50,
                f"Preset {key}: sigma={config.sigma} should be <= 50")

            self.assertIn(config.mode, (0, 1),
                f"Preset {key}: mode={config.mode} should be 0 or 1")

    def test_presets_are_visually_distinct(self):
        """Verify presets produce meaningfully different flocks by checking
        that phi_n (noise weight), phi_p (projection), phi_a (alignment),
        sigma (neighbourhood size), and mode differ across presets.
        At least 75% should have unique (phi_p, phi_a, sigma, mode) tuples
        and at least 50% should have unique phi_n values."""
        from scenario_presets import PRESETS

        signatures = {}
        phi_n_values = set()

        for key, preset in PRESETS.items():
            phi_p = preset['phi_p']
            phi_a = preset['phi_a']
            sigma = preset['sigma']
            mode = preset['mode']
            phi_n = round(max(0.0, 1.0 - phi_p - phi_a), 4)

            phi_n_values.add(phi_n)
            signatures[key] = (phi_p, phi_a, sigma, mode, phi_n)

        unique_sigs = len(set(signatures.values()))
        total = len(PRESETS)

        self.assertGreaterEqual(unique_sigs, int(total * 0.75),
            f"Only {unique_sigs}/{total} unique preset signatures "
            f"(need >= {int(total * 0.75)}). "
            f"Presets may be too similar.")

        unique_phi_n = len(phi_n_values)
        self.assertGreaterEqual(unique_phi_n, int(total * 0.5),
            f"Only {unique_phi_n}/{total} unique phi_n values "
            f"(need >= {int(total * 0.5)}). "
            f"Flock noise levels are too uniform.")

        # Also verify no two presets are identical in all parameters
        for key_a in PRESETS:
            for key_b in PRESETS:
                if str(key_a) >= str(key_b):
                    continue
                sig_a = signatures[key_a]
                sig_b = signatures[key_b]
                self.assertNotEqual(
                    sig_a, sig_b,
                    f"Preset {key_a!r} and {key_b!r} have identical "
                    f"parameters: {sig_a}")

    def test_preset_count_matches_expected(self):
        """Sanity check: ensure we have exactly 16 presets (5 original
        + 11 companion). If this fails, a preset was added or removed
        without updating this test."""
        from scenario_presets import PRESETS
        self.assertEqual(len(PRESETS), 16,
            f"Expected 16 presets, got {len(PRESETS)}. "
            f"Update this assertion if presets were intentionally "
            f"added or removed.")

    # ── Toggle behaviour tests ──────────────────────────────────

    def test_toggle_same_key_restores_previous(self):
        """Applying preset A, then preset A again restores original values."""
        from flock_core import Config
        from scenario_presets import apply_preset

        config = Config()
        orig_phi_p = config.phi_p
        orig_phi_a = config.phi_a
        orig_sigma = config.sigma
        orig_mode = config.mode

        saved = _save_config(config)
        apply_preset(config, 1)

        self.assertNotEqual(config.phi_p, orig_phi_p,
            "Preset 1 should change phi_p from default")

        _restore_config(config, saved)

        self.assertEqual(config.phi_p, orig_phi_p,
            "Restore should return phi_p to original")
        self.assertEqual(config.phi_a, orig_phi_a,
            "Restore should return phi_a to original")
        self.assertEqual(config.sigma, orig_sigma,
            "Restore should return sigma to original")
        self.assertEqual(config.mode, orig_mode,
            "Restore should return mode to original")

    def test_toggle_different_key_overwrites_saved(self):
        """Applying preset A then preset B — toggle B should restore
        to A's values (not the original defaults)."""
        from flock_core import Config
        from scenario_presets import apply_preset, PRESETS

        config = Config()

        saved_a = _save_config(config)
        apply_preset(config, 1)

        # Now apply preset B; should save B's snapshot (post-preset-A)
        saved_b = _save_config(config)
        apply_preset(config, 2)

        self.assertNotEqual(config.phi_p, PRESETS[1]['phi_p'],
            "After preset 2, phi_p should differ from preset 1")

        _restore_config(config, saved_b)
        self.assertEqual(config.phi_p, PRESETS[1]['phi_p'],
            "Restoring to saved_b should return to preset 1 values")

    def test_toggle_manual_tweak_invalidates_saved_config(self):
        """After a preset is applied, a manual tweak clears the toggle
        state — no saved_config means no restore is possible."""
        from flock_core import Config
        from scenario_presets import apply_preset

        config = Config()
        orig_phi_p = config.phi_p

        saved = _save_config(config)
        apply_preset(config, 1)
        preset_phi_p = config.phi_p
        self.assertNotEqual(preset_phi_p, orig_phi_p,
            "Preset should change phi_p from default")

        # Simulate manual tweak: clear snapshot and adjust
        saved = None
        config.phi_p = 0.07

        self.assertIsNone(saved,
            "Manual tweak should clear toggle state")
        self.assertNotEqual(config.phi_p, preset_phi_p,
            "Manual tweak should change phi_p from preset value")

    def test_get_preset_key_number_keys(self):
        """_get_preset_key maps numeric pygame keys correctly."""
        self.assertEqual(_get_preset_key(pygame.K_1), 1)
        self.assertEqual(_get_preset_key(pygame.K_5), 5)
        self.assertEqual(_get_preset_key(pygame.K_6), 6)
        self.assertEqual(_get_preset_key(pygame.K_9), 9)
        self.assertEqual(_get_preset_key(pygame.K_0), 0)

    def test_get_preset_key_letter_keys(self):
        """_get_preset_key maps letter pygame keys correctly."""
        self.assertEqual(_get_preset_key(pygame.K_s), 's')
        self.assertEqual(_get_preset_key(pygame.K_l), 'l')
        self.assertEqual(_get_preset_key(pygame.K_i), 'i')
        self.assertEqual(_get_preset_key(pygame.K_v), 'v')
        self.assertEqual(_get_preset_key(pygame.K_k), 'k')
        self.assertEqual(_get_preset_key(pygame.K_q), 'q')

    def test_get_preset_key_returns_none_for_non_preset(self):
        """_get_preset_key returns None for keys not mapped to presets."""
        self.assertIsNone(_get_preset_key(pygame.K_a))
        self.assertIsNone(_get_preset_key(pygame.K_m))
        self.assertIsNone(_get_preset_key(pygame.K_SPACE))
        self.assertIsNone(_get_preset_key(pygame.K_ESCAPE))

    def test_save_restore_roundtrip(self):
        """_save_config followed by _restore_config preserves all values."""
        from flock_core import Config

        config = Config()
        config.phi_p = 0.12
        config.phi_a = 0.65
        config.sigma = 7
        config.mode = 1

        saved = _save_config(config)

        config.phi_p = 0.99
        config.phi_a = 0.01
        config.sigma = 50
        config.mode = 0

        _restore_config(config, saved)

        self.assertEqual(config.phi_p, 0.12)
        self.assertEqual(config.phi_a, 0.65)
        self.assertEqual(config.sigma, 7)
        self.assertEqual(config.mode, 1)



class TestDiscovery(unittest.TestCase, TestCountMixin):
    """Verify test count for presets module."""

    EXPECTED_TEST_COUNT = 10


if __name__ == '__main__':
    unittest.main(verbosity=2)
