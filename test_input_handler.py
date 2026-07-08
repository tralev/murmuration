"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION T11 — INPUT HANDLER UNIT TESTS                             ║
╚══════════════════════════════════════════════════════════════════════╝

 Standalone tests for input_handler.py — verify handle_events() using
 mocked pygame events (no Pygame init required).

 Uses unittest.mock.patch to replace pygame.event.get() with a function
 that returns a list of mock events.  Mock events have .type, .key,
 .button, and .pos attributes as needed.
──────────────────────────────────────────────────────────────────────
"""

import unittest
from unittest.mock import patch

import pygame

from test_count_mixin import TestCountMixin

import flock_core
from flock_core import Config, MODE_PROJECTION, MODE_SPATIAL
import boid as boid_module
import features
from input_handler import handle_events, _get_preset_key, _save_config, _restore_config


class MockEvent:
    """Lightweight Pygame event stand-in with just the needed attributes."""
    def __init__(self, event_type, **kwargs):
        self.type = event_type
        for k, v in kwargs.items():
            setattr(self, k, v)


def _make_boid(x=0, y=0):
    """Create a minimal mock boid with just position for mouse-click tests."""
    class B:
        pass
    b = B()
    b.position = pygame.Vector2(x, y)
    return b


def _default_state(config=None):
    """Return the default state tuple for handle_events()."""
    return {
        'config': config or Config(),
        'flock': [],
        'running': True,
        'paused': False,
        'pending_reset': False,
        'pending_add': 0,
        'pending_remove': 0,
        'focal_index': None,
        'last_preset_key': None,
        'saved_config': None,
        'preset_label': '',
    }


def _call_handle_events(state, events):
    """Helper: mock pygame.event.get to return events, call handle_events."""
    with patch('input_handler.pygame.event.get', return_value=events):
        (running, paused, pending_reset, pending_add, pending_remove,
         focal_index, last_preset_key, saved_config, preset_label,
         ext_state) = \
            handle_events(
                state['config'], state['flock'],
                state['running'], state['paused'], state['pending_reset'],
                state['pending_add'], state['pending_remove'],
                state['focal_index'],
                state['last_preset_key'], state['saved_config'],
                state['preset_label'])
    return {
        **state,
        'running': running, 'paused': paused,
        'pending_reset': pending_reset,
        'pending_add': pending_add, 'pending_remove': pending_remove,
        'focal_index': focal_index,
        'last_preset_key': last_preset_key, 'saved_config': saved_config,
        'preset_label': preset_label,
        'ext_state': ext_state,
    }


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Simulation control                                                  ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestSimulationControl(unittest.TestCase):
    """Tests for QUIT, ESC, SPACE, R keys."""

    def test_quit_event_stops_running(self):
        """QUIT event → running = False."""
        s = _default_state()
        result = _call_handle_events(s, [MockEvent(pygame.QUIT)])
        self.assertFalse(result['running'])

    def test_escape_key_stops_running(self):
        """ESC key → running = False."""
        s = _default_state()
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        ])
        self.assertFalse(result['running'])

    def test_space_toggles_pause(self):
        """SPACE key toggles paused."""
        s = _default_state()
        # First press: pause
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        ])
        self.assertTrue(result['paused'])
        # Second press: unpause
        result = _call_handle_events(result, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        ])
        self.assertFalse(result['paused'])

    def test_r_key_sets_pending_reset(self):
        """R key → pending_reset = True, toggle state cleared."""
        s = _default_state()
        s['last_preset_key'] = 1
        s['saved_config'] = {'phi_p': 0.1, 'phi_a': 0.5, 'sigma': 4, 'mode': 0}

        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_r)
        ])
        self.assertTrue(result['pending_reset'])
        self.assertIsNone(result['last_preset_key'])
        self.assertIsNone(result['saved_config'])


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Mode toggle (m)                                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestModeToggle(unittest.TestCase):
    """Tests for M key mode switching."""

    def test_m_toggles_projection_to_spatial(self):
        """M key toggles config.mode between MODE_PROJECTION and MODE_SPATIAL."""
        config = Config()
        config.mode = MODE_PROJECTION

        s = _default_state(config)
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_m)
        ])
        self.assertEqual(result['config'].mode, MODE_SPATIAL)

        result = _call_handle_events(result, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_m)
        ])
        self.assertEqual(result['config'].mode, MODE_PROJECTION)

    def test_m_clears_preset_toggle_state(self):
        """M key clears last_preset_key and saved_config."""
        config = Config()
        s = _default_state(config)
        s['last_preset_key'] = 3
        s['saved_config'] = _save_config(config)

        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_m)
        ])
        self.assertIsNone(result['last_preset_key'])
        self.assertIsNone(result['saved_config'])


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Parameter adjustment (arrows, brackets, +/-)                       ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestParameterAdjustment(unittest.TestCase):
    """Tests for phi_p, phi_a, sigma, and boid count key handlers."""

    def test_up_arrow_increases_phi_p(self):
        """UP arrow → phi_p + 0.01, clamped to 1.0."""
        config = Config()
        config.phi_p = 0.5

        s = _default_state(config)
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_UP)
        ])
        self.assertAlmostEqual(result['config'].phi_p, 0.51)

    def test_up_arrow_clamped_to_one(self):
        """UP arrow at phi_p=1.0 → stays at 1.0."""
        config = Config()
        config.phi_p = 0.995

        s = _default_state(config)
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_UP)
        ])
        self.assertAlmostEqual(result['config'].phi_p, 1.0)

        # Second press at 1.0 → stays 1.0
        result = _call_handle_events(result, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_UP)
        ])
        self.assertAlmostEqual(result['config'].phi_p, 1.0)

    def test_down_arrow_decreases_phi_p(self):
        """DOWN arrow → phi_p - 0.01, clamped to 0.0."""
        config = Config()
        config.phi_p = 0.005

        s = _default_state(config)
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_DOWN)
        ])
        self.assertAlmostEqual(result['config'].phi_p, 0.0)

    def test_right_arrow_increases_phi_a(self):
        """RIGHT arrow → phi_a + 0.01."""
        config = Config()
        config.phi_a = 0.5

        s = _default_state(config)
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_RIGHT)
        ])
        self.assertAlmostEqual(result['config'].phi_a, 0.51)

    def test_left_arrow_decreases_phi_a(self):
        """LEFT arrow → phi_a - 0.01."""
        config = Config()
        config.phi_a = 0.5

        s = _default_state(config)
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_LEFT)
        ])
        self.assertAlmostEqual(result['config'].phi_a, 0.49)

    def test_right_bracket_increases_sigma(self):
        """] key → sigma + 1, clamped to 50."""
        config = Config()
        config.sigma = 49

        s = _default_state(config)
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_RIGHTBRACKET)
        ])
        self.assertEqual(result['config'].sigma, 50)

        # Another press at 50 → stays 50
        result = _call_handle_events(result, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_RIGHTBRACKET)
        ])
        self.assertEqual(result['config'].sigma, 50)

    def test_left_bracket_decreases_sigma(self):
        """[ key → sigma - 1, clamped to 1."""
        config = Config()
        config.sigma = 2

        s = _default_state(config)
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_LEFTBRACKET)
        ])
        self.assertEqual(result['config'].sigma, 1)

        # Another press at 1 → stays 1
        result = _call_handle_events(result, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_LEFTBRACKET)
        ])
        self.assertEqual(result['config'].sigma, 1)

    def test_equals_key_increases_pending_add(self):
        """= key → pending_add + 10, clamped to 200."""
        s = _default_state()
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_EQUALS)
        ])
        self.assertEqual(result['pending_add'], 10)

        # After reaching limit
        result['pending_add'] = 195
        result2 = _call_handle_events(result, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_EQUALS)
        ])
        self.assertEqual(result2['pending_add'], 200)

    def test_minus_key_increases_pending_remove(self):
        """- key → pending_remove + 10."""
        s = _default_state()
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_MINUS)
        ])
        self.assertEqual(result['pending_remove'], 10)

    def test_parameter_change_clears_preset_label(self):
        """Any parameter keypress clears preset_label and toggle state."""
        config = Config()
        s = _default_state(config)
        s['preset_label'] = "Preset 3"
        s['last_preset_key'] = 3
        s['saved_config'] = _save_config(config)

        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_UP)
        ])
        self.assertEqual(result['preset_label'], "")
        self.assertIsNone(result['last_preset_key'])
        self.assertIsNone(result['saved_config'])


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Visual toggles (g, h)                                              ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestVisualToggles(unittest.TestCase):
    """Tests for G (grid) and H (help) key handlers."""

    def setUp(self):
        self._saved_grid = features.ENABLE_GRID_OVERLAY
        features.ENABLE_GRID_OVERLAY = True

    def tearDown(self):
        features.ENABLE_GRID_OVERLAY = self._saved_grid

    def test_g_toggles_show_grid(self):
        """G key (with ENABLE_GRID_OVERLAY=True) toggles show_grid."""
        config = Config()
        config.show_grid = False

        s = _default_state(config)
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_g)
        ])
        self.assertTrue(result['config'].show_grid)

        result = _call_handle_events(result, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_g)
        ])
        self.assertFalse(result['config'].show_grid)

    def test_g_ignored_when_grid_disabled(self):
        """G key is ignored when features.ENABLE_GRID_OVERLAY is False."""
        features.ENABLE_GRID_OVERLAY = False
        config = Config()
        config.show_grid = False

        s = _default_state(config)
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_g)
        ])
        # G should be ignored, grid stays False
        self.assertFalse(result['config'].show_grid)

    def test_h_toggles_show_help(self):
        """H key toggles show_help."""
        config = Config()
        config.show_help = True

        s = _default_state(config)
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_h)
        ])
        self.assertFalse(result['config'].show_help)

        result = _call_handle_events(result, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_h)
        ])
        self.assertTrue(result['config'].show_help)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Boundary mode toggle (b)                                           ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestBoundaryToggle(unittest.TestCase):
    """Tests for B key boundary mode toggle."""

    def setUp(self):
        self._saved_margin = flock_core.MARGIN_BOUNDARY
        self._saved_boid_margin = boid_module.MARGIN_BOUNDARY

    def tearDown(self):
        flock_core.MARGIN_BOUNDARY = self._saved_margin
        boid_module.MARGIN_BOUNDARY = self._saved_boid_margin

    def test_b_toggles_margin_boundary(self):
        """B key toggles MARGIN_BOUNDARY in both modules."""
        flock_core.MARGIN_BOUNDARY = False
        boid_module.MARGIN_BOUNDARY = False

        s = _default_state()
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_b)
        ])
        self.assertTrue(flock_core.MARGIN_BOUNDARY)
        self.assertTrue(boid_module.MARGIN_BOUNDARY)

        result = _call_handle_events(result, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_b)
        ])
        self.assertFalse(flock_core.MARGIN_BOUNDARY)
        self.assertFalse(boid_module.MARGIN_BOUNDARY)

    def test_both_modules_synced_after_toggle(self):
        """After B toggle, both module flags are the same value."""
        flock_core.MARGIN_BOUNDARY = True
        boid_module.MARGIN_BOUNDARY = False  # deliberately desynced

        s = _default_state()
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_b)
        ])
        # After toggle: flock_core was True → now False
        # boid_module is synced to flock_core's new value
        self.assertEqual(flock_core.MARGIN_BOUNDARY,
                         boid_module.MARGIN_BOUNDARY)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Focal bird (f key + mouse click)                                   ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestFocalBird(unittest.TestCase):
    """Tests for F key and mouse click focal bird selection."""

    def setUp(self):
        self._saved_focal = features.ENABLE_FOCAL_DEBUG
        features.ENABLE_FOCAL_DEBUG = True

    def tearDown(self):
        features.ENABLE_FOCAL_DEBUG = self._saved_focal

    def test_f_sets_focal_index_when_none(self):
        """F key with non-empty flock → focal_index = 0."""
        flock = [_make_boid(100, 200), _make_boid(300, 400)]
        s = _default_state()
        s['flock'] = flock

        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_f)
        ])
        self.assertEqual(result['focal_index'], 0)

    def test_f_clears_focal_index_when_set(self):
        """F key with focal already set → focal_index = None."""
        flock = [_make_boid(100, 200)]
        s = _default_state()
        s['flock'] = flock
        s['focal_index'] = 0

        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_f)
        ])
        self.assertIsNone(result['focal_index'])

    def test_f_noop_when_flock_empty(self):
        """F key with empty flock → focal_index stays None."""
        s = _default_state()
        s['flock'] = []

        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_f)
        ])
        self.assertIsNone(result['focal_index'])

    def test_f_ignored_when_focal_debug_disabled(self):
        """F key ignored when features.ENABLE_FOCAL_DEBUG is False."""
        features.ENABLE_FOCAL_DEBUG = False
        flock = [_make_boid(100, 200)]
        s = _default_state()
        s['flock'] = flock

        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_f)
        ])
        # F should do nothing → focal stays None
        self.assertIsNone(result['focal_index'])

    def test_mouse_click_selects_nearest_bird(self):
        """Mouse click near a bird → focal_index set to that bird."""
        flock = [
            _make_boid(100, 200),  # dist from (105, 205) = sqrt(25+25) = 7.07
            _make_boid(400, 500),  # far away
        ]
        s = _default_state()
        s['flock'] = flock

        ev = MockEvent(pygame.MOUSEBUTTONDOWN, button=1, pos=(105, 205))
        result = _call_handle_events(s, [ev])
        self.assertEqual(result['focal_index'], 0)

    def test_mouse_click_too_far_no_selection(self):
        """Mouse click farther than 30px from any bird → focal_index unchanged."""
        flock = [_make_boid(100, 200)]
        s = _default_state()
        s['flock'] = flock

        # Click at (200, 300) — dist = sqrt(10000+10000) = 141 > 30
        ev = MockEvent(pygame.MOUSEBUTTONDOWN, button=1, pos=(200, 300))
        result = _call_handle_events(s, [ev])
        self.assertIsNone(result['focal_index'])


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Multiple events per frame                                           ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestMultipleEvents(unittest.TestCase):
    """Tests that multiple events in a single frame are processed correctly."""

    def test_two_keys_processed_in_order(self):
        """Two KEYDOWN events in one frame → both applied."""
        config = Config()
        config.phi_p = 0.5

        s = _default_state(config)
        result = _call_handle_events(s, [
            MockEvent(pygame.KEYDOWN, key=pygame.K_UP),
            MockEvent(pygame.KEYDOWN, key=pygame.K_UP),
        ])
        self.assertAlmostEqual(result['config'].phi_p, 0.52)

    def test_events_after_quit_still_processed(self):
        """QUIT sets running=False and continues (doesn't break, just skips
        subsequent event processing for QUIT itself). But other events after
        QUIT are still processed since QUIT uses 'continue', not 'break'.
        """
        config = Config()
        config.phi_p = 0.5

        s = _default_state(config)
        result = _call_handle_events(s, [
            MockEvent(pygame.QUIT),
            MockEvent(pygame.KEYDOWN, key=pygame.K_UP),
        ])
        # QUIT sets running=False, then continues to next event
        self.assertFalse(result['running'])
        # UP should still be processed
        self.assertAlmostEqual(result['config'].phi_p, 0.51)

    def test_empty_event_list_no_change(self):
        """Empty event list → no state changes."""
        s = _default_state()
        result = _call_handle_events(s, [])
        self.assertEqual(result['running'], s['running'])
        self.assertEqual(result['paused'], s['paused'])
        self.assertIsNone(result['focal_index'])


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Preset helpers (tested more thoroughly in test_presets.py)          ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestPresetHelpers(unittest.TestCase):
    """Quick sanity checks for _get_preset_key, _save_config, _restore_config."""

    def test_get_preset_key_returns_none_for_unknown(self):
        """Non-preset key → None."""
        self.assertIsNone(_get_preset_key(pygame.K_a))
        self.assertIsNone(_get_preset_key(pygame.K_SPACE))

    def test_save_and_restore_config(self):
        """_save_config → _restore_config round-trips correctly."""
        config = Config()
        config.phi_p = 0.123
        config.phi_a = 0.456
        config.sigma = 7
        config.mode = MODE_PROJECTION

        saved = _save_config(config)

        # Mutate config
        config.phi_p = 0.999
        config.phi_a = 0.001
        config.sigma = 1
        config.mode = MODE_SPATIAL

        _restore_config(config, saved)

        self.assertAlmostEqual(config.phi_p, 0.123)
        self.assertAlmostEqual(config.phi_a, 0.456)
        self.assertEqual(config.sigma, 7)
        self.assertEqual(config.mode, MODE_PROJECTION)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Test count guardian                                                 ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestDiscovery(unittest.TestCase, TestCountMixin):
    """Verify test count for input_handler module."""

    EXPECTED_TEST_COUNT = 32


if __name__ == '__main__':
    unittest.main(verbosity=2)
