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


import re
import unittest

from test_count_mixin import TestCountMixin

from flock_core import WIDTH, HEIGHT


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  _normalise_interval                                                 ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestToroidalWrapOctaveScilab(unittest.TestCase):
    """
    Runs standalone Octave/Scilab test scripts that exercise the
    toroidal wrap physics step in isolation. Verifies position wrapping
    at all 4 edges, corner wraps, speed clamping, and velocity preservation.
    """

    EXPECTED_TESTS = 8

    def _parse_output(self, stdout):
        """Parse T1_X=5.0000 lines into a dict: {'T1_X': 5.0, ...}."""
        data = {}
        for m in re.finditer(r'([A-Z][A-Z0-9_]*)=\s*([-\d.]+)', stdout):
            data[m.group(1)] = float(m.group(2))
        return data

    def _verify_results(self, data):
        """Cross-check all 8 scenarios against expected wrapped positions
        and velocity preservation."""
        n = len([k for k in data if k.startswith('T')])
        self.assertGreaterEqual(n, self.EXPECTED_TESTS * 4,
            f"Expected {self.EXPECTED_TESTS*4} key=value lines, got {n}")

        # T1: wrap right→left: 1002+4=1006 → mod(1006,1000)=6
        self.assertAlmostEqual(data['T1_X'], 6.0, places=1,
            msg="T1: right→left wrap X should be 6.0")
        self.assertAlmostEqual(data['T1_Y'], 350.0, places=1,
            msg="T1: Y should be unchanged at 350.0")
        # T2: wrap left→right: -2+(-4)=-6 → mod(-6,1000)=994
        self.assertAlmostEqual(data['T2_X'], 994.0, places=1,
            msg="T2: left→right wrap X should be 994.0")
        self.assertAlmostEqual(data['T2_Y'], 350.0, places=1,
            msg="T2: Y should be unchanged at 350.0")
        # T3: wrap bottom→top: 702+4=706 → mod(706,700)=6
        self.assertAlmostEqual(data['T3_X'], 500.0, places=1,
            msg="T3: X should be unchanged at 500.0")
        self.assertAlmostEqual(data['T3_Y'], 6.0, places=1,
            msg="T3: bottom→top wrap Y should be 6.0")
        # T4: wrap top→bottom: -2+(-4)=-6 → mod(-6,700)=694
        self.assertAlmostEqual(data['T4_X'], 500.0, places=1,
            msg="T4: X should be unchanged at 500.0")
        self.assertAlmostEqual(data['T4_Y'], 694.0, places=1,
            msg="T4: top→bottom wrap Y should be 694.0")
        # T5: corner bottom-right: diag (4,4) clamped to (2.828,2.828),
        #     (1002+2.828, 702+2.828) → mod → (4.828, 4.828)
        self.assertAlmostEqual(data['T5_X'], 4.8284, places=3,
            msg="T5: corner bottom-right X should be 4.828")
        self.assertAlmostEqual(data['T5_Y'], 4.8284, places=3,
            msg="T5: corner bottom-right Y should be 4.828")
        # T6: corner top-left: diag (-4,-4) clamped to (-2.828,-2.828),
        #     (-2-2.828, -2-2.828) → mod → (995.172, 695.172)
        self.assertAlmostEqual(data['T6_X'], 995.1716, places=3,
            msg="T6: corner top-left X should be 995.172")
        self.assertAlmostEqual(data['T6_Y'], 695.1716, places=3,
            msg="T6: corner top-left Y should be 695.172")
        # T7: high-speed clamped: spd=1200→V0=4, pos_x=500+4=504
        self.assertAlmostEqual(data['T7_X'], 504.0, places=1,
            msg="T7: high-speed X should be 504.0")
        self.assertAlmostEqual(data['T7_Y'], 350.0, places=1,
            msg="T7: Y should be unchanged at 350.0")
        self.assertAlmostEqual(data['T7_VX'], 4.0, places=1,
            msg="T7: clamped VX should be 4.0")
        # T8: velocity unchanged after wrap
        self.assertAlmostEqual(data['T8_VX'], 4.0, places=1,
            msg="T8: VX unchanged after wrap, should be 4.0")
        self.assertAlmostEqual(data['T8_VY'], 0.0, places=1,
            msg="T8: VY should be 0.0")

    def _check_positions_in_bounds(self, data):
        """All positions must be in [0,WIDTH)×[0,HEIGHT)."""
        for i in range(1, self.EXPECTED_TESTS + 1):
            x = data.get(f'T{i}_X')
            y = data.get(f'T{i}_Y')
            if x is not None:
                self.assertGreaterEqual(x, 0, f"T{i} x={x} < 0")
                self.assertLess(x, WIDTH, f"T{i} x={x} >= {WIDTH}")
            if y is not None:
                self.assertGreaterEqual(y, 0, f"T{i} y={y} < 0")
                self.assertLess(y, HEIGHT, f"T{i} y={y} >= {HEIGHT}")

    def test_octave_physics_step(self):
        """Run test_toroidal_wrap.m via local Octave CLI."""
        data = self._run_octave_script('test_toroidal_wrap.m')
        self._verify_results(data)
        self._check_positions_in_bounds(data)

    def test_octave_full_key_handler(self):
        """Run test_key_handler.m via local Octave CLI.
        Exercises the EXACT key_handler function from alg2.m with
        simulated keypresses for b, m, p, h, r, arrows, brackets, +/-.
        Verifies all globals toggle correctly and independently:
          - b/B toggles MARGIN_BOUNDARY (toroidal ↔ margin)
          - m/M toggles MODE (projection ↔ spatial)
          - p   toggles paused
          - h   toggles show_help
          - up/down arrows adjust PHI_P ±0.01
          - left/right arrows adjust PHI_A ±0.01
          - [ ] brackets adjust SIGMA ±1
          - +/= increments pending_add by 10
          - -   increments pending_remove by 10
          - r   sets pending_reset = true"""
        data = self._run_octave_script('test_key_handler.m')

        # T1: initial state — all defaults
        self.assertEqual(data.get('T1_MARGIN'), 0, "Initial MARGIN_BOUNDARY should be false")
        self.assertEqual(data.get('T1_MODE'), 0, "Initial MODE should be 0 (PROJECTION)")
        self.assertEqual(data.get('T1_PAUSED'), 0, "Initial paused should be false")
        self.assertEqual(data.get('T1_HELP'), 0, "Initial show_help should be false")
        self.assertAlmostEqual(data.get('T1_PHIP', 0), 0.03, places=2)
        self.assertAlmostEqual(data.get('T1_PHIA', 0), 0.80, places=2)
        self.assertEqual(data.get('T1_SIGMA'), 4)
        self.assertEqual(data.get('T1_PENDADD'), 0)
        self.assertEqual(data.get('T1_PENDRMV'), 0)
        self.assertEqual(data.get('T1_RESET'), 0)

        # T2: 'b' toggles MARGIN_BOUNDARY false→true; MODE and paused unchanged
        self.assertEqual(data.get('T2_MARGIN'), 1, "After 'b': MARGIN_BOUNDARY should be true")
        self.assertEqual(data.get('T2_MODE'), 0, "After 'b': MODE unchanged")
        self.assertEqual(data.get('T2_PAUSED'), 0, "After 'b': paused unchanged")

        # T3: 'm' toggles MODE 0→1; MARGIN_BOUNDARY still true
        self.assertEqual(data.get('T3_MODE'), 1, "After 'm': MODE should be 1 (SPATIAL)")
        self.assertEqual(data.get('T3_MARGIN'), 1, "After 'm': MARGIN_BOUNDARY unchanged")

        # T4: 'p' toggles paused false→true
        self.assertEqual(data.get('T4_PAUSED'), 1, "After 'p': paused should be true")
        self.assertEqual(data.get('T4_MODE'), 1, "After 'p': MODE unchanged")
        self.assertEqual(data.get('T4_MARGIN'), 1, "After 'p': MARGIN_BOUNDARY unchanged")

        # T5: 'h' toggles show_help false→true
        self.assertEqual(data.get('T5_HELP'), 1, "After 'h': show_help should be true")
        self.assertEqual(data.get('T5_PAUSED'), 1, "After 'h': paused unchanged")

        # T6: 'B' (uppercase) toggles MARGIN_BOUNDARY true→false
        self.assertEqual(data.get('T6_MARGIN'), 0, "After 'B': MARGIN_BOUNDARY should be false")
        self.assertEqual(data.get('T6_MODE'), 1, "After 'B': MODE unchanged")

        # T7: 'M' toggles MODE 1→0
        self.assertEqual(data.get('T7_MODE'), 0, "After 'M': MODE should be 0")
        self.assertEqual(data.get('T7_MARGIN'), 0, "After 'M': MARGIN_BOUNDARY unchanged")

        # T8: 'p' again toggles paused true→false
        self.assertEqual(data.get('T8_PAUSED'), 0, "After second 'p': paused should be false")
        self.assertEqual(data.get('T8_HELP'), 1, "After second 'p': help unchanged")

        # T9: 'h' again toggles show_help true→false
        self.assertEqual(data.get('T9_HELP'), 0, "After second 'h': show_help should be false")

        # T10: ']' increments SIGMA 4→5
        self.assertEqual(data.get('T10_SIGMA'), 5, "After ']': SIGMA should be 5")

        # T11: 'uparrow' increments PHI_P 0.03→0.04
        self.assertAlmostEqual(data.get('T11_PHIP', 0), 0.04, places=2)

        # T12: 'leftarrow' decrements PHI_A 0.80→0.79
        self.assertAlmostEqual(data.get('T12_PHIA', 0), 0.79, places=2)

        # T13: 'equal' adds 10 to pending_add
        self.assertEqual(data.get('T13_PENDADD'), 10, "After '=': pending_add should be 10")

        # T14: 'hyphen' adds 10 to pending_remove
        self.assertEqual(data.get('T14_PENDRMV'), 10, "After '-': pending_remove should be 10")

        # T15: 'r' sets pending_reset = true
        self.assertEqual(data.get('T15_RESET'), 1, "After 'r': pending_reset should be true")

        # T16: multiple presses accumulate correctly
        self.assertEqual(data.get('T16_PENDADD'), 30, "After 3 '=' presses: pending_add should be 30")
        self.assertEqual(data.get('T16_SIGMA'), 7, "After 3 ']' presses: SIGMA should be 7")
        self.assertEqual(data.get('T16_SIGMABACK'), 6, "After '[' press: SIGMA should drop from 7 to 6")

        # T17: 'downarrow' decrements PHI_P back to 0.03
        self.assertAlmostEqual(data.get('T17_PHIP', 0), 0.03, places=2)

        # T18: 'rightarrow' increments PHI_A back to 0.80
        self.assertAlmostEqual(data.get('T18_PHIA', 0), 0.80, places=2)

        # T19: all independent toggles ended at their default values
        self.assertEqual(data.get('T19_MARGIN'), 0, "Final MARGIN_BOUNDARY should be false")
        self.assertEqual(data.get('T19_MODE'), 0, "Final MODE should be 0")
        self.assertEqual(data.get('T19_PAUSED'), 0, "Final paused should be false")
        self.assertEqual(data.get('T19_HELP'), 0, "Final show_help should be false")

        # T20: unrecognized key 'x' — NO globals mutated
        self.assertEqual(data.get('T20_MARGIN_UNCHANGED'), 1, "After 'x': MARGIN_BOUNDARY unchanged")
        self.assertEqual(data.get('T20_MODE_UNCHANGED'), 1, "After 'x': MODE unchanged")
        self.assertEqual(data.get('T20_PAUSED_UNCHANGED'), 1, "After 'x': paused unchanged")
        self.assertEqual(data.get('T20_HELP_UNCHANGED'), 1, "After 'x': show_help unchanged")
        self.assertEqual(data.get('T20_PHIP_UNCHANGED'), 1, "After 'x': PHI_P unchanged")
        self.assertEqual(data.get('T20_PHIA_UNCHANGED'), 1, "After 'x': PHI_A unchanged")
        self.assertEqual(data.get('T20_SIGMA_UNCHANGED'), 1, "After 'x': SIGMA unchanged")
        self.assertEqual(data.get('T20_PENDADD_UNCHANGED'), 1, "After 'x': pending_add unchanged")
        self.assertEqual(data.get('T20_PENDRMV_UNCHANGED'), 1, "After 'x': pending_remove unchanged")
        self.assertEqual(data.get('T20_RESET_UNCHANGED'), 1, "After 'x': pending_reset unchanged")

        # T21: unrecognized key 'q' — NO globals mutated
        self.assertEqual(data.get('T21_MARGIN_UNCHANGED'), 1, "After 'q': MARGIN_BOUNDARY unchanged")
        self.assertEqual(data.get('T21_MODE_UNCHANGED'), 1, "After 'q': MODE unchanged")
        self.assertEqual(data.get('T21_PAUSED_UNCHANGED'), 1, "After 'q': paused unchanged")
        self.assertEqual(data.get('T21_HELP_UNCHANGED'), 1, "After 'q': show_help unchanged")
        self.assertEqual(data.get('T21_PHIP_UNCHANGED'), 1, "After 'q': PHI_P unchanged")
        self.assertEqual(data.get('T21_PHIA_UNCHANGED'), 1, "After 'q': PHI_A unchanged")
        self.assertEqual(data.get('T21_SIGMA_UNCHANGED'), 1, "After 'q': SIGMA unchanged")
        self.assertEqual(data.get('T21_PENDADD_UNCHANGED'), 1, "After 'q': pending_add unchanged")
        self.assertEqual(data.get('T21_PENDRMV_UNCHANGED'), 1, "After 'q': pending_remove unchanged")
        self.assertEqual(data.get('T21_RESET_UNCHANGED'), 1, "After 'q': pending_reset unchanged")

        # T22: PHI_P floor at 0.0 — 5 downarrow presses, caps at 0.00
        self.assertAlmostEqual(data.get('T22_PHIP', -1), 0.00, places=2,
            msg="PHI_P should be clamped at 0.00")
        self.assertEqual(data.get('T22_PHIP_AT_FLOOR'), 1,
            "PHI_P == 0.0 should be true")

        # T23: PHI_A ceiling at 1.0 — 22 rightarrow presses, caps at 1.00
        self.assertAlmostEqual(data.get('T23_PHIA', -1), 1.00, places=2,
            msg="PHI_A should be clamped at 1.00")
        self.assertEqual(data.get('T23_PHIA_AT_CEILING'), 1,
            "PHI_A == 1.0 should be true")

        # T24: PHI_A floor at 0.0 — 102 leftarrow presses from 1.00
        self.assertAlmostEqual(data.get('T24_PHIA', -1), 0.00, places=2,
            msg="PHI_A should be clamped at 0.00")
        self.assertEqual(data.get('T24_PHIA_AT_FLOOR'), 1,
            "PHI_A == 0.0 should be true")

        # T25: SIGMA ceiling at 50 — 50 ] presses from 6
        self.assertEqual(data.get('T25_SIGMA'), 50,
            "SIGMA should be clamped at 50")
        self.assertEqual(data.get('T25_SIGMA_AT_CEILING'), 1,
            "SIGMA == 50 should be true")

        # T26: SIGMA floor at 1 — 55 [ presses from 50
        self.assertEqual(data.get('T26_SIGMA'), 1,
            "SIGMA should be clamped at 1")
        self.assertEqual(data.get('T26_SIGMA_AT_FLOOR'), 1,
            "SIGMA == 1 should be true")

        # T27: pending_add ceiling at 200 — 20 = presses from 30
        self.assertEqual(data.get('T27_PENDADD'), 200,
            "pending_add should be clamped at 200")
        self.assertEqual(data.get('T27_PENDADD_AT_CEILING'), 1,
            "pending_add == 200 should be true")

        # T28: pending_remove has NO cap — 100 '-' presses from 10 → 1010
        self.assertEqual(data.get('T28_PENDRMV'), 1010,
            "pending_remove should grow unbounded to 1010")
        self.assertEqual(data.get('T28_PENDRMV_UNBOUNDED'), 1,
            "pending_remove > 200 should be true (no cap)")

        # T29: PHI_P ceiling at 1.0 — 102 uparrow presses from 0.00
        self.assertAlmostEqual(data.get('T29_PHIP', -1), 1.00, places=2,
            msg="PHI_P should be clamped at 1.00")
        self.assertEqual(data.get('T29_PHIP_AT_CEILING'), 1,
            "PHI_P == 1.0 should be true")

        # T30: empty-key boundary case (ibut=0 analogue) — all globals unchanged
        self.assertEqual(data.get('T30_MARGIN_UNCHANGED'), 1, "Empty key: MARGIN_BOUNDARY unchanged")
        self.assertEqual(data.get('T30_MODE_UNCHANGED'), 1, "Empty key: MODE unchanged")
        self.assertEqual(data.get('T30_PAUSED_UNCHANGED'), 1, "Empty key: paused unchanged")
        self.assertEqual(data.get('T30_HELP_UNCHANGED'), 1, "Empty key: show_help unchanged")
        self.assertEqual(data.get('T30_PHIP_UNCHANGED'), 1, "Empty key: PHI_P unchanged")
        self.assertEqual(data.get('T30_PHIA_UNCHANGED'), 1, "Empty key: PHI_A unchanged")
        self.assertEqual(data.get('T30_SIGMA_UNCHANGED'), 1, "Empty key: SIGMA unchanged")
        self.assertEqual(data.get('T30_PENDADD_UNCHANGED'), 1, "Empty key: pending_add unchanged")
        self.assertEqual(data.get('T30_PENDRMV_UNCHANGED'), 1, "Empty key: pending_remove unchanged")
        self.assertEqual(data.get('T30_RESET_UNCHANGED'), 1, "Empty key: pending_reset unchanged")

    def test_octave_boundary_toggle(self):
        """Run test_boundary_toggle.m via local Octave CLI.
        Verifies MARGIN_BOUNDARY global can be toggled at runtime:
          - Starts false (toroidal)
          - Toggles to true (margin) on first simulated 'b' press
          - Toggles back to false on second simulated 'b' press"""
        data = self._run_octave_script('test_boundary_toggle.m')

        # Parse STATE0, STATE1, STATE2 values
        self.assertIn('STATE0', data, "Missing STATE0")
        self.assertIn('STATE1', data, "Missing STATE1")
        self.assertIn('STATE2', data, "Missing STATE2")

        # STATE0: initial = false (toroidal) → 0
        self.assertEqual(data['STATE0'], 0,
                         f"STATE0 should be 0 (false), got {data['STATE0']}")
        # STATE1: after first toggle → true (margin) → 1
        self.assertEqual(data['STATE1'], 1,
                         f"STATE1 should be 1 (true), got {data['STATE1']}")
        # STATE2: after second toggle → back to false → 0
        self.assertEqual(data['STATE2'], 0,
                         f"STATE2 should be 0 (false), got {data['STATE2']}")

        # Companion globals should be present
        self.assertIn('BOUNDARY_MARGIN', data, "Scilab: BOUNDARY_MARGIN should be present")
        self.assertEqual(data['BOUNDARY_MARGIN'], 200,
                         "Scilab: BOUNDARY_MARGIN should be 200")
        self.assertIn('BOUNDARY_TURN_FACTOR', data, "Scilab: BOUNDARY_TURN_FACTOR should be present")
        self.assertEqual(data['BOUNDARY_TURN_FACTOR'], 1,
                         "Scilab: BOUNDARY_TURN_FACTOR should be 1")

    def test_scilab_full_key_handler_docker(self):
        """Run test_key_handler.sce via docker-compose.
        Exercises the EXACT key_handler function from alg2.sce with
        simulated keypresses via ASCII codes (ibut < 0 convention).
        Verifies all globals toggle correctly and independently."""
        data = self._run_scilab_script_docker('test_key_handler.sce')

        # T1: initial state — all defaults
        self.assertEqual(data.get('T1_MARGIN'), 0, "Initial MARGIN_BOUNDARY should be false")
        self.assertEqual(data.get('T1_MODE'), 0, "Initial MODE should be 0 (PROJECTION)")
        self.assertEqual(data.get('T1_PAUSED'), 0, "Initial paused should be false")
        self.assertEqual(data.get('T1_HELP'), 0, "Initial show_help should be false")
        self.assertAlmostEqual(data.get('T1_PHIP', 0), 0.03, places=2)
        self.assertAlmostEqual(data.get('T1_PHIA', 0), 0.80, places=2)
        self.assertEqual(data.get('T1_SIGMA'), 4)
        self.assertEqual(data.get('T1_PENDADD'), 0)
        self.assertEqual(data.get('T1_PENDRMV'), 0)
        self.assertEqual(data.get('T1_RESET'), 0)

        # T2: 'b' toggles MARGIN_BOUNDARY false→true
        self.assertEqual(data.get('T2_MARGIN'), 1)
        self.assertEqual(data.get('T2_MODE'), 0, "After 'b': MODE unchanged")
        self.assertEqual(data.get('T2_PAUSED'), 0, "After 'b': paused unchanged")

        # T3: 'm' toggles MODE 0→1
        self.assertEqual(data.get('T3_MODE'), 1)
        self.assertEqual(data.get('T3_MARGIN'), 1, "After 'm': MARGIN_BOUNDARY unchanged")

        # T4: 'p' toggles paused false→true
        self.assertEqual(data.get('T4_PAUSED'), 1)
        self.assertEqual(data.get('T4_MODE'), 1, "After 'p': MODE unchanged")
        self.assertEqual(data.get('T4_MARGIN'), 1, "After 'p': MARGIN_BOUNDARY unchanged")

        # T5: 'h' toggles show_help false→true
        self.assertEqual(data.get('T5_HELP'), 1)
        self.assertEqual(data.get('T5_PAUSED'), 1, "After 'h': paused unchanged")

        # T6: 'B' toggles MARGIN_BOUNDARY true→false
        self.assertEqual(data.get('T6_MARGIN'), 0)
        self.assertEqual(data.get('T6_MODE'), 1, "After 'B': MODE unchanged")

        # T7: 'M' toggles MODE 1→0
        self.assertEqual(data.get('T7_MODE'), 0)
        self.assertEqual(data.get('T7_MARGIN'), 0, "After 'M': MARGIN_BOUNDARY unchanged")

        # T8: 'p' again toggles paused true→false
        self.assertEqual(data.get('T8_PAUSED'), 0)
        self.assertEqual(data.get('T8_HELP'), 1, "After second 'p': help unchanged")

        # T9: 'h' again toggles show_help true→false
        self.assertEqual(data.get('T9_HELP'), 0)

        # T10: ']' increments SIGMA 4→5
        self.assertEqual(data.get('T10_SIGMA'), 5)

        # T11: up arrow increments PHI_P 0.03→0.04
        self.assertAlmostEqual(data.get('T11_PHIP', 0), 0.04, places=2)

        # T12: left arrow decrements PHI_A 0.80→0.79
        self.assertAlmostEqual(data.get('T12_PHIA', 0), 0.79, places=2)

        # T13: '=' adds 10 to pending_add
        self.assertEqual(data.get('T13_PENDADD'), 10)

        # T14: '-' adds 10 to pending_remove
        self.assertEqual(data.get('T14_PENDRMV'), 10)

        # T15: 'r' sets pending_reset = true
        self.assertEqual(data.get('T15_RESET'), 1)

        # T16: multiple presses accumulate
        self.assertEqual(data.get('T16_PENDADD'), 30)
        self.assertEqual(data.get('T16_SIGMA'), 7)
        self.assertEqual(data.get('T16_SIGMABACK'), 6)

        # T17: down arrow decrements PHI_P back to 0.03
        self.assertAlmostEqual(data.get('T17_PHIP', 0), 0.03, places=2)

        # T18: right arrow increments PHI_A back to 0.80
        self.assertAlmostEqual(data.get('T18_PHIA', 0), 0.80, places=2)

        # T19: all independent toggles ended at defaults
        self.assertEqual(data.get('T19_MARGIN'), 0)
        self.assertEqual(data.get('T19_MODE'), 0)
        self.assertEqual(data.get('T19_PAUSED'), 0)
        self.assertEqual(data.get('T19_HELP'), 0)

        # T20: unrecognized key 'x' (120) — NO globals mutated
        self.assertEqual(data.get('T20_MARGIN_UNCHANGED'), 1, "Scilab after 'x': MARGIN_BOUNDARY unchanged")
        self.assertEqual(data.get('T20_MODE_UNCHANGED'), 1, "Scilab after 'x': MODE unchanged")
        self.assertEqual(data.get('T20_PAUSED_UNCHANGED'), 1, "Scilab after 'x': paused unchanged")
        self.assertEqual(data.get('T20_HELP_UNCHANGED'), 1, "Scilab after 'x': show_help unchanged")
        self.assertEqual(data.get('T20_PHIP_UNCHANGED'), 1, "Scilab after 'x': PHI_P unchanged")
        self.assertEqual(data.get('T20_PHIA_UNCHANGED'), 1, "Scilab after 'x': PHI_A unchanged")
        self.assertEqual(data.get('T20_SIGMA_UNCHANGED'), 1, "Scilab after 'x': SIGMA unchanged")
        self.assertEqual(data.get('T20_PENDADD_UNCHANGED'), 1, "Scilab after 'x': pending_add unchanged")
        self.assertEqual(data.get('T20_PENDRMV_UNCHANGED'), 1, "Scilab after 'x': pending_remove unchanged")
        self.assertEqual(data.get('T20_RESET_UNCHANGED'), 1, "Scilab after 'x': pending_reset unchanged")

        # T21: unrecognized key 'q' (113) — NO globals mutated
        self.assertEqual(data.get('T21_MARGIN_UNCHANGED'), 1, "Scilab after 'q': MARGIN_BOUNDARY unchanged")
        self.assertEqual(data.get('T21_MODE_UNCHANGED'), 1, "Scilab after 'q': MODE unchanged")
        self.assertEqual(data.get('T21_PAUSED_UNCHANGED'), 1, "Scilab after 'q': paused unchanged")
        self.assertEqual(data.get('T21_HELP_UNCHANGED'), 1, "Scilab after 'q': show_help unchanged")
        self.assertEqual(data.get('T21_PHIP_UNCHANGED'), 1, "Scilab after 'q': PHI_P unchanged")
        self.assertEqual(data.get('T21_PHIA_UNCHANGED'), 1, "Scilab after 'q': PHI_A unchanged")
        self.assertEqual(data.get('T21_SIGMA_UNCHANGED'), 1, "Scilab after 'q': SIGMA unchanged")
        self.assertEqual(data.get('T21_PENDADD_UNCHANGED'), 1, "Scilab after 'q': pending_add unchanged")
        self.assertEqual(data.get('T21_PENDRMV_UNCHANGED'), 1, "Scilab after 'q': pending_remove unchanged")
        self.assertEqual(data.get('T21_RESET_UNCHANGED'), 1, "Scilab after 'q': pending_reset unchanged")

        # T22: PHI_P floor at 0.0 — 5 downarrow presses (40)
        self.assertAlmostEqual(data.get('T22_PHIP', -1), 0.00, places=2,
            msg="Scilab: PHI_P should be clamped at 0.00")
        self.assertEqual(data.get('T22_PHIP_AT_FLOOR'), 1,
            "Scilab: PHI_P == 0.0 should be true")

        # T23: PHI_A ceiling at 1.0 — 22 rightarrow presses (39)
        self.assertAlmostEqual(data.get('T23_PHIA', -1), 1.00, places=2,
            msg="Scilab: PHI_A should be clamped at 1.00")
        self.assertEqual(data.get('T23_PHIA_AT_CEILING'), 1,
            "Scilab: PHI_A == 1.0 should be true")

        # T24: PHI_A floor at 0.0 — 102 leftarrow presses (37)
        self.assertAlmostEqual(data.get('T24_PHIA', -1), 0.00, places=2,
            msg="Scilab: PHI_A should be clamped at 0.00")
        self.assertEqual(data.get('T24_PHIA_AT_FLOOR'), 1,
            "Scilab: PHI_A == 0.0 should be true")

        # T25: SIGMA ceiling at 50 — 50 ] presses (93)
        self.assertEqual(data.get('T25_SIGMA'), 50,
            "Scilab: SIGMA should be clamped at 50")
        self.assertEqual(data.get('T25_SIGMA_AT_CEILING'), 1,
            "Scilab: SIGMA == 50 should be true")

        # T26: SIGMA floor at 1 — 55 [ presses (91)
        self.assertEqual(data.get('T26_SIGMA'), 1,
            "Scilab: SIGMA should be clamped at 1")
        self.assertEqual(data.get('T26_SIGMA_AT_FLOOR'), 1,
            "Scilab: SIGMA == 1 should be true")

        # T27: pending_add ceiling at 200 — 20 = presses (61)
        self.assertEqual(data.get('T27_PENDADD'), 200,
            "Scilab: pending_add should be clamped at 200")
        self.assertEqual(data.get('T27_PENDADD_AT_CEILING'), 1,
            "Scilab: pending_add == 200 should be true")

        # T28: pending_remove unbounded — 100 - presses (45) from 10 → 1010
        self.assertEqual(data.get('T28_PENDRMV'), 1010,
            "Scilab: pending_remove should grow unbounded to 1010")
        self.assertEqual(data.get('T28_PENDRMV_UNBOUNDED'), 1,
            "Scilab: pending_remove > 200 should be true (no cap)")

        # T29: PHI_P ceiling at 1.0 — 102 uparrow presses (38)
        self.assertAlmostEqual(data.get('T29_PHIP', -1), 1.00, places=2,
            msg="Scilab: PHI_P should be clamped at 1.00")
        self.assertEqual(data.get('T29_PHIP_AT_CEILING'), 1,
            "Scilab: PHI_P == 1.0 should be true")

        # T30: positive ibut (mouse event) — handler skips entirely
        self.assertEqual(data.get('T30_PHIP_UNCHANGED'), 1, "Scilab +ibut: PHI_P unchanged")
        self.assertEqual(data.get('T30_PHIA_UNCHANGED'), 1, "Scilab +ibut: PHI_A unchanged")
        self.assertEqual(data.get('T30_SIGMA_UNCHANGED'), 1, "Scilab +ibut: SIGMA unchanged")
        self.assertEqual(data.get('T30_MARGIN_UNCHANGED'), 1, "Scilab +ibut: MARGIN_BOUNDARY unchanged")
        self.assertEqual(data.get('T30_MODE_UNCHANGED'), 1, "Scilab +ibut: MODE unchanged")
        self.assertEqual(data.get('T30_PAUSED_UNCHANGED'), 1, "Scilab +ibut: paused unchanged")
        self.assertEqual(data.get('T30_HELP_UNCHANGED'), 1, "Scilab +ibut: show_help unchanged")

        # T31: ibut = 0 boundary case (focused, isolated) — no globals mutated
        self.assertEqual(data.get('T31_MARGIN_UNCHANGED'), 1, "Scilab ibut=0: MARGIN_BOUNDARY unchanged")
        self.assertEqual(data.get('T31_MODE_UNCHANGED'), 1, "Scilab ibut=0: MODE unchanged")
        self.assertEqual(data.get('T31_PAUSED_UNCHANGED'), 1, "Scilab ibut=0: paused unchanged")
        self.assertEqual(data.get('T31_HELP_UNCHANGED'), 1, "Scilab ibut=0: show_help unchanged")
        self.assertEqual(data.get('T31_PHIP_UNCHANGED'), 1, "Scilab ibut=0: PHI_P unchanged")
        self.assertEqual(data.get('T31_PHIA_UNCHANGED'), 1, "Scilab ibut=0: PHI_A unchanged")
        self.assertEqual(data.get('T31_SIGMA_UNCHANGED'), 1, "Scilab ibut=0: SIGMA unchanged")
        self.assertEqual(data.get('T31_PENDADD_UNCHANGED'), 1, "Scilab ibut=0: pending_add unchanged")
        self.assertEqual(data.get('T31_PENDRMV_UNCHANGED'), 1, "Scilab ibut=0: pending_remove unchanged")
        self.assertEqual(data.get('T31_RESET_UNCHANGED'), 1, "Scilab ibut=0: pending_reset unchanged")

    def test_scilab_boundary_toggle_docker(self):
        """Run test_boundary_toggle.sce via docker-compose.
        Verifies MARGIN_BOUNDARY can be toggled at runtime in Scilab."""
        data = self._run_scilab_script_docker('test_boundary_toggle.sce')

        self.assertIn('STATE0', data, "Scilab: Missing STATE0")
        self.assertIn('STATE1', data, "Scilab: Missing STATE1")
        self.assertIn('STATE2', data, "Scilab: Missing STATE2")

        # STATE0: initial = false (%f) → 0
        self.assertEqual(data['STATE0'], 0,
                         f"STATE0 should be 0 (false), got {data['STATE0']}")
        # STATE1: after first toggle → true (%t) → 1
        self.assertEqual(data['STATE1'], 1,
                         f"STATE1 should be 1 (true), got {data['STATE1']}")
        # STATE2: after second toggle → back to false → 0
        self.assertEqual(data['STATE2'], 0,
                         f"STATE2 should be 0 (false), got {data['STATE2']}")

        self.assertIn('BOUNDARY_MARGIN', data)
        self.assertEqual(data['BOUNDARY_MARGIN'], 200)
        self.assertIn('BOUNDARY_TURN_FACTOR', data)
        self.assertEqual(data['BOUNDARY_TURN_FACTOR'], 1)

    def test_scilab_physics_step_docker(self):
        """Run test_toroidal_wrap.sce via docker-compose."""
        data = self._run_scilab_script_docker('test_toroidal_wrap.sce')
        self._verify_results(data)
        self._check_positions_in_bounds(data)

    # ═══════════════════════════════════════════════════════════════
    #  Cross-language consistency helpers
    # ═══════════════════════════════════════════════════════════════

    def _run_octave_script(self, script_name):
        """Run an Octave script and return parsed output dict."""
        import os
        import subprocess

        script = os.path.join(os.path.dirname(__file__), script_name)
        if not os.path.exists(script):
            self.skipTest(f"Missing {script}")
        octave = "/opt/homebrew/bin/octave"
        try:
            res = subprocess.run(
                [octave, "--no-gui", "--silent", script],
                capture_output=True, text=True, timeout=30,
                cwd=os.path.dirname(os.path.abspath(__file__)))
        except OSError:
            self.skipTest(f"Octave not found at {octave}")
        except subprocess.TimeoutExpired:
            self.fail(f"Octave {script_name} timed out")
        self.assertEqual(res.returncode, 0,
                         f"Octave exited {res.returncode}: {res.stderr}")
        return self._parse_output(res.stdout)

    def _run_scilab_script_docker(self, script_name):
        """Run a Scilab script via Docker; return parsed dict or skip."""
        import os
        import subprocess

        script = os.path.join(os.path.dirname(__file__), script_name)
        if not os.path.exists(script):
            self.skipTest(f"Missing {script}")
        cwd = os.path.dirname(os.path.abspath(__file__))
        try:
            res = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True, text=True, timeout=5, cwd=cwd)
        except (OSError, subprocess.TimeoutExpired):
            self.skipTest(
                f"docker compose not available (needed for {script_name})")
        if res.returncode != 0:
            detail = (
                f": {res.stderr.strip()}" if res.stderr.strip() else "")
            self.skipTest(
                f"docker compose returned {res.returncode} "
                f"for {script_name}{detail}")

        cmd = ["docker", "compose", "run", "--rm", "-T", "shell",
               "scilab-cli", "-nb", "-f", script_name]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=60, cwd=cwd)
        except subprocess.TimeoutExpired:
            self.fail(f"Scilab {script_name} docker timed out")

        if res.returncode != 0:
            self.skipTest(f"Scilab docker returned {res.returncode}")

        data = self._parse_output(res.stdout)
        if not data:
            self.skipTest(f"No parseable output from Scilab {script_name}")
        return data

    def test_cross_language_key_handler_consistency(self):
        """Compare Octave and Scilab key_handler outputs.
        Runs test_key_handler.m (Octave) and test_key_handler.sce (Scilab),
        then compares all T1-T30 outputs key-by-key for cross-language parity.
        Float values (PHI_P, PHI_A) use approximate comparison."""
        data_oct = self._run_octave_script('test_key_handler.m')
        data_sci = self._run_scilab_script_docker('test_key_handler.sce')

        oct_keys = set(k for k in data_oct if k.startswith('T'))
        sci_keys = set(k for k in data_sci if k.startswith('T'))
        shared = oct_keys & sci_keys

        self.assertGreater(len(shared), 0,
            "No shared keys between Octave and Scilab outputs")
        # T31 is Scilab-only (focused ibut=0 test — no Octave analogue
        # since Octave uses event.Key dispatch, not ibut).
        oct_only_expected = set()
        sci_only_expected = {k for k in sci_keys if k.startswith('T31')}
        self.assertEqual(oct_keys - sci_keys, oct_only_expected,
            f"Unexpected Octave-only keys: {sorted(oct_keys - sci_keys)}")
        self.assertEqual(sci_keys - oct_keys, sci_only_expected,
            f"Unexpected Scilab-only keys: {sorted((sci_keys - oct_keys) - sci_only_expected)}")

        float_pats = ('PHIP', 'PHIA')
        mismatches = []

        for key in sorted(shared):
            ov = data_oct[key]
            sv = data_sci[key]

            if any(p in key for p in float_pats):
                if abs(ov - sv) > 0.005:
                    mismatches.append(f"{key}: Oct={ov:.4f} Sci={sv:.4f}")
            else:
                if ov != sv:
                    mismatches.append(f"{key}: Oct={ov} Sci={sv}")

        if mismatches:
            self.fail(
                f"{len(mismatches)} key_handler output mismatches "
                f"between Octave and Scilab:\n" +
                "\n".join(mismatches[:20]))

    def test_cross_language_physics_consistency(self):
        """Compare Octave and Scilab toroidal wrap physics outputs.
        Runs test_toroidal_wrap.m (Octave) and test_toroidal_wrap.sce
        (Scilab), then compares all T1-T8 outputs key-by-key for
        cross-language parity. All physics values are floats."""
        data_oct = self._run_octave_script('test_toroidal_wrap.m')
        data_sci = self._run_scilab_script_docker('test_toroidal_wrap.sce')

        oct_keys = set(k for k in data_oct if k.startswith('T'))
        sci_keys = set(k for k in data_sci if k.startswith('T'))
        shared = oct_keys & sci_keys

        self.assertGreater(len(shared), 0,
            "No shared keys between Octave and Scilab physics outputs")
        self.assertEqual(oct_keys, sci_keys,
            f"Key set mismatch: Oct={len(oct_keys)} Sci={len(sci_keys)} "
            f"\nOct-only: {sorted(oct_keys - sci_keys)}"
            f"\nSci-only: {sorted(sci_keys - oct_keys)}")

        mismatches = []
        for key in sorted(shared):
            ov = data_oct[key]
            sv = data_sci[key]
            if abs(ov - sv) > 0.005:
                mismatches.append(f"{key}: Oct={ov:.4f} Sci={sv:.4f}")

        if mismatches:
            self.fail(
                f"{len(mismatches)} physics output mismatches "
                f"between Octave and Scilab:\n" +
                "\n".join(mismatches[:20]))

    def test_cross_language_boundary_toggle_consistency(self):
        """Compare Octave and Scilab boundary toggle outputs.
        Runs test_boundary_toggle.m (Octave) and test_boundary_toggle.sce
        (Scilab), then compares STATE0/1/2 and companion globals key-by-key."""
        data_oct = self._run_octave_script('test_boundary_toggle.m')
        data_sci = self._run_scilab_script_docker('test_boundary_toggle.sce')

        # Only compare numeric keys: STATE0, STATE1, STATE2,
        # BOUNDARY_MARGIN, BOUNDARY_TURN_FACTOR
        num_keys = {'STATE0', 'STATE1', 'STATE2',
                    'BOUNDARY_MARGIN', 'BOUNDARY_TURN_FACTOR'}
        oct_keys = set(k for k in data_oct if k in num_keys)
        sci_keys = set(k for k in data_sci if k in num_keys)
        shared = oct_keys & sci_keys

        self.assertEqual(oct_keys, num_keys,
            f"Octave missing keys: {sorted(num_keys - oct_keys)}")
        self.assertEqual(sci_keys, num_keys,
            f"Scilab missing keys: {sorted(num_keys - sci_keys)}")
        self.assertGreater(len(shared), 0,
            "No shared keys between Octave and Scilab boundary toggle outputs")

        mismatches = []
        for key in sorted(shared):
            ov = data_oct[key]
            sv = data_sci[key]
            if abs(ov - sv) > 0.001:
                mismatches.append(f"{key}: Oct={ov:.4f} Sci={sv:.4f}")

        if mismatches:
            self.fail(
                f"{len(mismatches)} boundary toggle output mismatches "
                f"between Octave and Scilab:\n" +
                "\n".join(mismatches[:20]))

    def test_all_cross_language_consistency(self):
        """Run all three cross-language consistency checks in one test.
        Executes key_handler, physics, and boundary toggle comparisons
        via subTest so each check reports independently."""
        checks = [
            ("key_handler",
             'test_key_handler.m', 'test_key_handler.sce',
             # Expected key-set asymmetry: T31 is Scilab-only
             {'T31'}, 0.005, ('PHIP', 'PHIA'), None),
            ("physics",
             'test_toroidal_wrap.m', 'test_toroidal_wrap.sce',
             # No expected asymmetry
             set(), 0.005, (), None),
            ("boundary_toggle",
             'test_boundary_toggle.m', 'test_boundary_toggle.sce',
             # Only compare numeric keys (TOGGLE_STEP is non-numeric)
             set(), 0.001, (),
             {'STATE0', 'STATE1', 'STATE2',
              'BOUNDARY_MARGIN', 'BOUNDARY_TURN_FACTOR'}),
        ]

        for name, oct_script, sci_script, sci_only, tol, float_pats, num_keys \
                in checks:
            with self.subTest(check=name):
                data_oct = self._run_octave_script(oct_script)
                data_sci = self._run_scilab_script_docker(sci_script)

                oct_keys = set(k for k in data_oct if k.startswith('T'))
                sci_keys = set(k for k in data_sci if k.startswith('T'))

                # For boundary_toggle, also include the non-T keys
                if name == "boundary_toggle":
                    oct_keys = {k for k in data_oct
                                if k in {'STATE0', 'STATE1', 'STATE2',
                                         'BOUNDARY_MARGIN',
                                         'BOUNDARY_TURN_FACTOR'}}
                    sci_keys = {k for k in data_sci
                                if k in {'STATE0', 'STATE1', 'STATE2',
                                         'BOUNDARY_MARGIN',
                                         'BOUNDARY_TURN_FACTOR'}}
                    # Assert both scripts produce all expected keys
                    self.assertEqual(oct_keys, num_keys,
                        f"Octave missing {name} keys: "
                        f"{sorted(num_keys - oct_keys)}")
                    self.assertEqual(sci_keys, num_keys,
                        f"Scilab missing {name} keys: "
                        f"{sorted(num_keys - sci_keys)}")

                shared = oct_keys & sci_keys

                self.assertGreater(len(shared), 0,
                    f"No shared keys in {name} check")

                if sci_only:
                    self.assertEqual(oct_keys - sci_keys, set(),
                        f"Unexpected Octave-only {name} keys: "
                        f"{sorted(oct_keys - sci_keys)}")
                    self.assertEqual(sci_keys - oct_keys, sci_only,
                        f"Unexpected Scilab-only {name} keys: "
                        f"{sorted((sci_keys - oct_keys) - sci_only)}")
                else:
                    self.assertEqual(oct_keys, sci_keys,
                        f"{name} key set mismatch: "
                        f"Oct-only: {sorted(oct_keys - sci_keys)} "
                        f"Sci-only: {sorted(sci_keys - oct_keys)}")

                mismatches = []
                for key in sorted(shared):
                    ov = data_oct[key]
                    sv = data_sci[key]

                    if float_pats and any(p in key for p in float_pats):
                        if abs(ov - sv) > tol:
                            mismatches.append(
                                f"{key}: Oct={ov:.4f} Sci={sv:.4f}")
                    elif isinstance(ov, float) or isinstance(sv, float):
                        if abs(ov - sv) > tol:
                            mismatches.append(
                                f"{key}: Oct={ov:.4f} Sci={sv:.4f}")
                    else:
                        if ov != sv:
                            mismatches.append(
                                f"{key}: Oct={ov} Sci={sv}")

                if mismatches:
                    self.fail(
                        f"{len(mismatches)} {name} output mismatches "
                        f"between Octave and Scilab:\n" +
                        "\n".join(mismatches[:20]))


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Test discovery sanity check — catches accidental regressions        ║
# ╚══════════════════════════════════════════════════════════════════════╝


class TestDiscovery(unittest.TestCase, TestCountMixin):
    """Verify test count for cross-language module."""

    EXPECTED_TEST_COUNT = 10


if __name__ == '__main__':
    unittest.main(verbosity=2)
