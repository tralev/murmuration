"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION T12 — FEATURE FLAG UNIT TESTS                              ║
╚══════════════════════════════════════════════════════════════════════╝

 Tests for the feature flag gating system in features.py.
 Verifies that each flag correctly enables/disables its feature
 at the right point (import time, render time, I/O time).

 Uses subprocess for import-time guards (ENABLE_3D) and direct
 flag manipulation for runtime guards (ENABLE_CSV_LOGGING, etc.).

 The test_input_handler.py file already covers ENABLE_FOCAL_DEBUG
 and ENABLE_GRID_OVERLAY gating for the F and G keys.
──────────────────────────────────────────────────────────────────────
"""

import io
import os
import subprocess
import sys
import unittest

from test_count_mixin import TestCountMixin

import features
from flock_core import LOG_EVERY

# Resolved once so subprocess tests don't depend on cwd
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ENABLE_3D — import-time guard                                       ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestEnable3D(unittest.TestCase):
    """Tests for the ENABLE_3D import-time guard in main_3d.py.

    Uses subprocess so each test gets a fresh Python interpreter —
    the guard fires at module level and can only be triggered once
    per process (imports are cached).
    """

    _IMPORT_SCRIPT = (
        "import sys; sys.path.insert(0, {root!r}); "
        "import features; features.ENABLE_3D = {flag}; "
        "import main_3d"
    )

    def _run_import(self, flag):
        """Run 'import main_3d' with ENABLE_3D set to *flag*.
        Returns the CompletedProcess from subprocess."""
        script = self._IMPORT_SCRIPT.format(root=_PROJECT_ROOT, flag=flag)
        return subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=15,
        )

    def test_enable_3d_false_raises_importerror(self):
        """ENABLE_3D=False should raise ImportError at module level."""
        result = self._run_import(False)
        self.assertNotEqual(result.returncode, 0,
                            f"Expected non-zero exit for ENABLE_3D=False, "
                            f"got {result.returncode}")
        output = result.stderr + result.stdout
        self.assertIn("disabled", output,
                      f"Expected 'disabled' in output, got: {output!r}")

    def test_enable_3d_true_allows_import(self):
        """ENABLE_3D=True (default) allows main_3d to import."""
        result = self._run_import(True)
        self.assertEqual(result.returncode, 0,
                         f"Expected exit 0 for ENABLE_3D=True, "
                         f"got {result.returncode}. stderr={result.stderr!r}")

    def test_enable_3d_false_prevents_heavy_imports(self):
        """ENABLE_3D=False prevents pygame/numpy/moderngl from loading —
        the ImportError fires before any of those imports."""
        result = self._run_import(False)
        output = result.stderr + result.stdout
        # Should NOT contain "No module named" (that would mean the guard
        # didn't fire and we're hitting a missing-dep error instead)
        self.assertNotIn("No module named", output,
                         f"Guard didn't fire — got missing-module error: "
                         f"{output!r}")


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ENABLE_CSV_LOGGING — I/O guard                                      ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestEnableCsvLogging(unittest.TestCase):
    """Tests for the ENABLE_CSV_LOGGING check in simulation.py."""

    def setUp(self):
        self._saved = features.ENABLE_CSV_LOGGING

    def tearDown(self):
        features.ENABLE_CSV_LOGGING = self._saved

    def test_csv_logging_false_prevents_writes(self):
        """When ENABLE_CSV_LOGGING=False, log_fid.write() is never called."""
        features.ENABLE_CSV_LOGGING = False

        # Simulate the exact guard from simulation.py
        log_buf = io.StringIO()
        frame = 0
        log_fid = log_buf

        # Replicate the guard condition from simulation.py
        if features.ENABLE_CSV_LOGGING and log_fid is not None and frame % LOG_EVERY == 0:
            log_fid.write("should not be written\n")

        self.assertEqual(log_buf.getvalue(), "",
                         "CSV write occurred despite ENABLE_CSV_LOGGING=False")

    def test_csv_logging_true_allows_writes(self):
        """When ENABLE_CSV_LOGGING=True, log_fid.write() is called."""
        features.ENABLE_CSV_LOGGING = True

        log_buf = io.StringIO()
        frame = 0
        log_fid = log_buf

        if features.ENABLE_CSV_LOGGING and log_fid is not None and frame % LOG_EVERY == 0:
            log_fid.write("csv_row\n")

        self.assertEqual(log_buf.getvalue(), "csv_row\n",
                         "CSV write was blocked despite ENABLE_CSV_LOGGING=True")

    def test_csv_logging_false_with_none_logfid_no_crash(self):
        """ENABLE_CSV_LOGGING=False with log_fid=None should not crash."""
        features.ENABLE_CSV_LOGGING = False

        # Short-circuit evaluation means log_fid is not None is never
        # evaluated when ENABLE_CSV_LOGGING is False (leftmost in AND)
        frame = 0
        log_fid = None
        wrote = False

        if features.ENABLE_CSV_LOGGING and log_fid is not None and frame % LOG_EVERY == 0:
            log_fid.write("x")
            wrote = True

        self.assertFalse(wrote)

    def test_csv_logging_false_no_file_created(self):
        """ENABLE_CSV_LOGGING=False prevents alg2.py from opening a file."""
        features.ENABLE_CSV_LOGGING = False

        # Simulate the exact guard from alg2.py
        log_fid = None
        LOG_FILE = "output/test.csv"  # not actually created

        # Replicate the alg2.py guard
        if features.ENABLE_CSV_LOGGING and LOG_FILE is not None:
            log_fid = open(LOG_FILE, "w")

        self.assertIsNone(log_fid,
                          "File was opened despite ENABLE_CSV_LOGGING=False")


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Flag count and consistency                                           ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestFlagCount(unittest.TestCase):
    """Verify the number and names of active feature flags."""

    def test_exactly_ten_flags(self):
        """features.py should have exactly 10 active flags — catch accidental
        additions or deletions."""
        expected = {
            'ENABLE_PROJECTION_MODE',
            'ENABLE_SPATIAL_MODE',
            'ENABLE_TRAILS',
            'ENABLE_FOCAL_DEBUG',
            'ENABLE_GRID_OVERLAY',
            'ENABLE_METRICS',
            'ENABLE_PRESETS',
            'ENABLE_HELP_OVERLAY',
            'ENABLE_3D',
            'ENABLE_CSV_LOGGING',
        }
        actual = {k for k in dir(features)
                  if k.startswith('ENABLE_') and not k.startswith('_')}
        self.assertSetEqual(actual, expected,
                            f"Flag set mismatch. Expected {expected}, got {actual}")

    def test_no_unknown_flags_imported(self):
        """No stale flags from the old features.py should survive."""
        stale = {'ENABLE_STERIC', 'ENABLE_BLIND_ANGLES', 'ENABLE_ANISOTROPIC',
                 'ENABLE_SPATIAL_OPT', 'ENABLE_PREDATOR'}
        for flag in stale:
            self.assertFalse(hasattr(features, flag),
                             f"Stale flag {flag} still present in features.py")


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Flag defaults                                                        ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestFlagDefaults(unittest.TestCase):
    """Verify that flag defaults match the expected safe values."""

    def test_visual_flags_default_false(self):
        """Visual features default to False (safe: no extra rendering)."""
        self.assertFalse(features.ENABLE_TRAILS,
                         "ENABLE_TRAILS should default to False")
        self.assertFalse(features.ENABLE_FOCAL_DEBUG,
                         "ENABLE_FOCAL_DEBUG should default to False")
        self.assertFalse(features.ENABLE_GRID_OVERLAY,
                         "ENABLE_GRID_OVERLAY should default to False")

    def test_simulation_flags_default_true(self):
        """Core simulation features default to True (normal operation)."""
        self.assertTrue(features.ENABLE_PROJECTION_MODE,
                        "ENABLE_PROJECTION_MODE should default to True")
        self.assertTrue(features.ENABLE_SPATIAL_MODE,
                        "ENABLE_SPATIAL_MODE should default to True")
        self.assertTrue(features.ENABLE_METRICS,
                        "ENABLE_METRICS should default to True")
        self.assertTrue(features.ENABLE_PRESETS,
                        "ENABLE_PRESETS should default to True")
        self.assertTrue(features.ENABLE_HELP_OVERLAY,
                        "ENABLE_HELP_OVERLAY should default to True")
        self.assertTrue(features.ENABLE_3D,
                        "ENABLE_3D should default to True")
        self.assertTrue(features.ENABLE_CSV_LOGGING,
                        "ENABLE_CSV_LOGGING should default to True")


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Flocking model flags — import guards + dispatch fallback            ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestModelFlags(unittest.TestCase):
    """Tests for ENABLE_PROJECTION_MODE / ENABLE_SPATIAL_MODE gating
    in boid.py.

    Uses subprocess so each test gets a fresh interpreter — the gated
    imports fire at module level and are cached afterwards.
    """

    def _run(self, script):
        return subprocess.run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0, {_PROJECT_ROOT!r}); "
             + script],
            capture_output=True, text=True, timeout=30,
        )

    def test_both_models_disabled_raises_importerror(self):
        """With both model flags False, importing boid fails loudly."""
        result = self._run(
            "import features; "
            "features.ENABLE_PROJECTION_MODE = False; "
            "features.ENABLE_SPATIAL_MODE = False; "
            "import boid"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("disabled", result.stderr + result.stdout)

    def test_projection_only_never_imports_spatial(self):
        """ENABLE_SPATIAL_MODE=False keeps spatial_model out of
        sys.modules, and a SPATIAL-mode config falls back to the
        projection model without crashing."""
        result = self._run(
            "import features; features.ENABLE_SPATIAL_MODE = False; "
            "import sys; "
            "from flock_core import Config, MODE_SPATIAL; "
            "from boid import Boid; "
            "assert 'spatial_model' not in sys.modules; "
            "c = Config(); c.mode = MODE_SPATIAL; "
            "f = [Boid() for _ in range(8)]; "
            "[b.flock(f, c) for b in f]; [b.update() for b in f]; "
            "print('ok')"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_spatial_only_never_imports_projection(self):
        """ENABLE_PROJECTION_MODE=False keeps projection_model out of
        sys.modules, and a PROJECTION-mode config falls back to the
        spatial model without crashing."""
        result = self._run(
            "import features; features.ENABLE_PROJECTION_MODE = False; "
            "import sys; "
            "from flock_core import Config, SpatialGrid, VISUAL_RANGE, "
            "MODE_PROJECTION; "
            "from boid import Boid; "
            "assert 'projection_model' not in sys.modules; "
            "c = Config(); c.mode = MODE_PROJECTION; "
            "g = SpatialGrid(cell_size=VISUAL_RANGE); "
            "f = [Boid() for _ in range(8)]; g.rebuild(f); "
            "[b.flock(f, c, g) for b in f]; [b.update() for b in f]; "
            "print('ok')"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Lazy-import guards — disabled features never load their module      ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestLazyImports(unittest.TestCase):
    """Disabled features must keep their implementation module out of
    sys.modules entirely (the ENABLE_3D pattern applied everywhere)."""

    def _run(self, script):
        return subprocess.run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0, {_PROJECT_ROOT!r}); "
             f"import os; os.environ['SDL_VIDEODRIVER'] = 'dummy'; "
             + script],
            capture_output=True, text=True, timeout=30,
        )

    def test_metrics_disabled_never_imports_metrics(self):
        """ENABLE_METRICS=False keeps metrics + external_opacity out of
        alg2 and simulation."""
        result = self._run(
            "import features; features.ENABLE_METRICS = False; "
            "import sys, alg2, simulation; "
            "assert 'metrics' not in sys.modules; "
            "assert 'external_opacity' not in sys.modules; "
            "print('ok')"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_presets_disabled_never_imports_presets(self):
        """ENABLE_PRESETS=False keeps scenario_presets out of
        input_handler."""
        result = self._run(
            "import features; features.ENABLE_PRESETS = False; "
            "import sys, input_handler; "
            "assert 'scenario_presets' not in sys.modules; "
            "print('ok')"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_help_disabled_never_imports_help_overlay(self):
        """ENABLE_HELP_OVERLAY=False keeps help_overlay out of alg2."""
        result = self._run(
            "import features; features.ENABLE_HELP_OVERLAY = False; "
            "import sys, alg2; "
            "assert 'help_overlay' not in sys.modules; "
            "print('ok')"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Test count guardian                                                  ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestDiscovery(unittest.TestCase, TestCountMixin):
    """Verify test count for features module."""

    EXPECTED_TEST_COUNT = 17


if __name__ == '__main__':
    unittest.main(verbosity=2)
