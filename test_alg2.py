"""
╔══════════════════════════════════════════════════════════════════════╗
║  TEST RUNNER — imports all domain-specific test suites              ║
╚══════════════════════════════════════════════════════════════════════╝

Aggregates all test suites from the split test files:
  test_occlusion.py       — angular interval merge utilities (47 tests)
  test_boundary.py        — margin + toroidal wrap modes (41 tests)
  test_cross_language.py  — Octave/Scilab cross-language parity (10 tests)
  test_presets.py         — scenario preset validation (10 tests)

Run all:   python3 -m unittest test_occlusion test_boundary test_cross_language test_presets
Run this:  python3 -m unittest test_alg2
"""

import unittest

# Re-export all test classes so `python -m unittest test_alg2` discovers them
from test_occlusion import (
    TestNormaliseInterval,
    TestIntervalCovered,
    TestMergeInterval,
    TestMergeAll,
    TestOcclusionWorkflow,
)
from test_boundary import (
    TestMarginBoundary,
    TestToroidalWrap,
)
from test_cross_language import (
    TestToroidalWrapOctaveScilab,
)
from test_presets import (
    TestPresetValidation,
)

# Note: each split file has its own TestDiscovery with the correct
# EXPECTED_TEST_COUNT for that module. Run them individually for
# count verification:
#   python3 -m unittest test_occlusion.TestDiscovery
#   python3 -m unittest test_boundary.TestDiscovery
#   python3 -m unittest test_cross_language.TestDiscovery
#   python3 -m unittest test_presets.TestDiscovery

if __name__ == "__main__":
    unittest.main(verbosity=2)
