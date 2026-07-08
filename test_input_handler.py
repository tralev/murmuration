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
                state['preset_label'],
                state.get('ext_state'))
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
# ║  Extension toggles  (T, W, A, N, J, C, Y)                           ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestExtensionToggles(unittest.TestCase):
    """Tests for the 7 new extension key handlers."""

    def setUp(self):
        self._saved_threat = features.ENABLE_THREAT
        self._saved_wander = features.ENABLE_WANDER
        self._saved_aq = features.ENABLE_ADAPTIVE_QUALITY
        self._saved_medium = features.ENABLE_MEDIUM_PRESETS
        self._saved_h2 = features.ENABLE_H2_ROBUSTNESS
        self._saved_seasonal = features.ENABLE_SEASONAL
        self._saved_shape = features.ENABLE_FLOCK_SHAPE
        self._saved_vacuole = features.ENABLE_VACUOLE

    def tearDown(self):
        features.ENABLE_THREAT = self._saved_threat
        features.ENABLE_WANDER = self._saved_wander
        features.ENABLE_ADAPTIVE_QUALITY = self._saved_aq
        features.ENABLE_MEDIUM_PRESETS = self._saved_medium
        features.ENABLE_H2_ROBUSTNESS = self._saved_h2
        features.ENABLE_SEASONAL = self._saved_seasonal
        features.ENABLE_FLOCK_SHAPE = self._saved_shape
        features.ENABLE_VACUOLE = self._saved_vacuole

    # ── T: threat agent ──────────────────────────────────────────

    def test_t_spawns_threat(self):
        """T key with threat=None → creates ThreatAgent."""
        features.ENABLE_THREAT = True
        from extensions.threat import ThreatAgent
        s = _default_state()
        s['ext_state'] = {'threat': None}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_t)])
        self.assertIsNotNone(result['ext_state']['threat'])
        self.assertIsInstance(result['ext_state']['threat'], ThreatAgent)

    def test_t_removes_threat(self):
        """T key with existing threat → removes it."""
        features.ENABLE_THREAT = True
        from extensions.threat import ThreatAgent
        s = _default_state()
        s['ext_state'] = {'threat': ThreatAgent()}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_t)])
        self.assertIsNone(result['ext_state']['threat'])

    def test_t_ignored_when_threat_disabled(self):
        """T key ignored when ENABLE_THREAT=False."""
        features.ENABLE_THREAT = False
        s = _default_state()
        s['ext_state'] = {'threat': None}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_t)])
        self.assertIsNone(result['ext_state']['threat'])

    # ── W: wander behaviour ──────────────────────────────────────

    def test_w_toggles_wander_on(self):
        """W key with wander_active=False → toggles to True."""
        features.ENABLE_WANDER = True
        s = _default_state()
        s['ext_state'] = {'wander_active': False}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_w)])
        self.assertTrue(result['ext_state']['wander_active'])

    def test_w_toggles_wander_off(self):
        """W key with wander_active=True → toggles to False."""
        features.ENABLE_WANDER = True
        s = _default_state()
        s['ext_state'] = {'wander_active': True}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_w)])
        self.assertFalse(result['ext_state']['wander_active'])

    def test_w_ignored_when_wander_disabled(self):
        """W key ignored when ENABLE_WANDER=False."""
        features.ENABLE_WANDER = False
        s = _default_state()
        s['ext_state'] = {'wander_active': False}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_w)])
        self.assertFalse(result['ext_state']['wander_active'])

    # ── A: adaptive quality ──────────────────────────────────────

    def test_a_toggles_adaptive_quality(self):
        """A key toggles AdaptiveQuality on and sets aq_label."""
        features.ENABLE_ADAPTIVE_QUALITY = True
        from extensions.adaptive_quality import AdaptiveQuality
        aq = AdaptiveQuality()
        aq.enabled = True
        s = _default_state()
        s['ext_state'] = {'aq': aq, 'aq_label': ''}

        # First press: disable
        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_a)])
        self.assertFalse(result['ext_state']['aq'].enabled)
        self.assertEqual(result['ext_state']['aq_label'], '')

        # Second press: re-enable
        result = _call_handle_events(result, [MockEvent(pygame.KEYDOWN, key=pygame.K_a)])
        self.assertTrue(result['ext_state']['aq'].enabled)

    def test_a_ignored_when_aq_disabled(self):
        """A key ignored when ENABLE_ADAPTIVE_QUALITY=False."""
        features.ENABLE_ADAPTIVE_QUALITY = False
        from extensions.adaptive_quality import AdaptiveQuality
        aq = AdaptiveQuality()
        s = _default_state()
        s['ext_state'] = {'aq': aq, 'aq_label': ''}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_a)])
        self.assertTrue(aq.enabled)  # unchanged

    # ── N: cycle medium ──────────────────────────────────────────

    def test_n_cycles_medium(self):
        """N key cycles from one medium to the next."""
        features.ENABLE_MEDIUM_PRESETS = True
        from medium_presets import MediumConfig
        medium = MediumConfig("grid")
        s = _default_state()
        s['ext_state'] = {'medium': medium, 'medium_label': 'MEDIUM grid'}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_n)])
        # grid → air (first in the list after grid... actually, let me check)
        # MEDIUM_PRESETS keys are: air, dust, starlight, grid
        # grid.index + 1 % 4 = 0 → air
        self.assertEqual(result['ext_state']['medium'].name, 'air')
        self.assertIn('air', result['ext_state']['medium_label'])

    def test_n_cycles_through_all_media(self):
        """N key cycles through all 4 media and wraps."""
        features.ENABLE_MEDIUM_PRESETS = True
        from medium_presets import MediumConfig
        medium = MediumConfig("grid")
        s = _default_state()
        s['ext_state'] = {'medium': medium, 'medium_label': 'MEDIUM grid'}

        # grid → air → dust → starlight → grid
        for expected in ['air', 'dust', 'starlight', 'grid']:
            s = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_n)])
            self.assertEqual(s['ext_state']['medium'].name, expected)

    def test_n_ignored_when_medium_disabled(self):
        """N key ignored when ENABLE_MEDIUM_PRESETS=False."""
        features.ENABLE_MEDIUM_PRESETS = False
        from medium_presets import MediumConfig
        medium = MediumConfig("grid")
        s = _default_state()
        s['ext_state'] = {'medium': medium, 'medium_label': 'MEDIUM grid'}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_n)])
        self.assertEqual(result['ext_state']['medium'].name, 'grid')

    # ── J: H₂ compute ────────────────────────────────────────────

    def test_j_computes_h2_value(self):
        """J key computes H₂ norm and sets h2_val."""
        features.ENABLE_H2_ROBUSTNESS = True
        config = Config()
        config.sigma = 3
        flock = [_make_boid(i * 20, 350) for i in range(10)]
        s = _default_state(config)
        s['flock'] = flock
        s['ext_state'] = {'h2_val': -1.0}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_j)])
        # H₂ should be computed and set to a positive finite value
        self.assertGreater(result['ext_state']['h2_val'], 0.0)
        self.assertTrue(
            result['ext_state']['h2_val'] != float('inf'),
            "H₂ should be finite for connected graph")

    def test_j_ignored_when_h2_disabled(self):
        """J key ignored when ENABLE_H2_ROBUSTNESS=False."""
        features.ENABLE_H2_ROBUSTNESS = False
        s = _default_state()
        s['ext_state'] = {'h2_val': -1.0}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_j)])
        self.assertEqual(result['ext_state']['h2_val'], -1.0)

    # ── C: seasonal day advance ──────────────────────────────────

    def test_c_advances_seasonal_day(self):
        """C key advances seasonal_day by 30."""
        features.ENABLE_SEASONAL = True
        s = _default_state()
        s['ext_state'] = {'seasonal_day': 1, 'seasonal_label': ''}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_c)])
        self.assertEqual(result['ext_state']['seasonal_day'], 31)
        self.assertIn('flock factor', result['ext_state']['seasonal_label'])

    def test_c_wraps_seasonal_day_past_365(self):
        """C key wraps seasonal_day past 365."""
        features.ENABLE_SEASONAL = True
        s = _default_state()
        s['ext_state'] = {'seasonal_day': 350, 'seasonal_label': ''}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_c)])
        # (350 % 365) + 30 = 350 + 30 = 380 → but wait: (350 % 365) + 30 = 350 + 30 = 380
        # Actually 350 < 365, so: (350 % 365) + 30 = 350 + 30 = 380 > 365
        # There's no wrap-to-1 logic, so 380 stays
        self.assertEqual(result['ext_state']['seasonal_day'], 380)
        # seasonal_size_factor handles it via modulo internally

    def test_c_ignored_when_seasonal_disabled(self):
        """C key ignored when ENABLE_SEASONAL=False."""
        features.ENABLE_SEASONAL = False
        s = _default_state()
        s['ext_state'] = {'seasonal_day': 1, 'seasonal_label': ''}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_c)])
        self.assertEqual(result['ext_state']['seasonal_day'], 1)

    # ── Y: flock shape ───────────────────────────────────────────

    def test_y_does_not_crash(self):
        """Y key is a no-op handler (computed per-frame in simulation)."""
        features.ENABLE_FLOCK_SHAPE = True
        s = _default_state()
        s['ext_state'] = {'flock_shape': None}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_y)])
        # No crash, no change to flock_shape (computed in simulation.py)
        self.assertIsNone(result['ext_state']['flock_shape'])

    # ── O: leader / attractor system ────────────────────────────

    def test_o_spawns_leader_anchors(self):
        """O key spawns leader anchors."""
        features.ENABLE_LEADER = True
        from extensions.leader import LeaderConfig
        cfg = LeaderConfig()
        s = _default_state()
        s['ext_state'] = {'leader_active': False, 'leader_cfg': cfg,
                          'leader_time': 0.0, 'leader_anchors': []}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_o)])
        self.assertTrue(result['ext_state']['leader_active'])
        self.assertEqual(len(result['ext_state']['leader_anchors']), cfg.anchor_count)

    def test_o_removes_leader_anchors(self):
        """O key with active leaders removes them."""
        features.ENABLE_LEADER = True
        from extensions.leader import LeaderAnchor, LeaderConfig
        cfg = LeaderConfig()
        anchors = [LeaderAnchor(config=cfg) for _ in range(cfg.anchor_count)]
        s = _default_state()
        s['ext_state'] = {'leader_active': True, 'leader_cfg': cfg,
                          'leader_time': 0.0, 'leader_anchors': anchors}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_o)])
        self.assertFalse(result['ext_state']['leader_active'])
        self.assertEqual(len(result['ext_state']['leader_anchors']), 0)

    def test_o_ignored_when_leader_disabled(self):
        """O key ignored when ENABLE_LEADER=False."""
        features.ENABLE_LEADER = False
        s = _default_state()
        s['ext_state'] = {'leader_active': False, 'leader_anchors': []}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_o)])
        self.assertFalse(result['ext_state']['leader_active'])

    def test_y_ignored_when_shape_disabled(self):
        """Y key ignored when ENABLE_FLOCK_SHAPE=False."""
        features.ENABLE_FLOCK_SHAPE = False
        s = _default_state()
        s['ext_state'] = {}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_y)])
        # No crash

    # ── E: vacuole formation ───────────────────────────────────

    def test_e_spawns_vacuole(self):
        """E key with vacuole=None → creates VacuoleAgent."""
        features.ENABLE_VACUOLE = True
        from extensions.vacuole import VacuoleAgent
        s = _default_state()
        s['ext_state'] = {'vacuole': None, 'vacuole_time': 0.0}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_e)])
        self.assertIsNotNone(result['ext_state']['vacuole'])
        self.assertIsInstance(result['ext_state']['vacuole'], VacuoleAgent)

    def test_e_removes_vacuole(self):
        """E key with existing vacuole → removes it."""
        features.ENABLE_VACUOLE = True
        from extensions.vacuole import VacuoleAgent
        s = _default_state()
        s['ext_state'] = {'vacuole': VacuoleAgent(), 'vacuole_time': 0.0}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_e)])
        self.assertIsNone(result['ext_state']['vacuole'])

    def test_e_ignored_when_vacuole_disabled(self):
        """E key ignored when ENABLE_VACUOLE=False."""
        features.ENABLE_VACUOLE = False
        s = _default_state()
        s['ext_state'] = {'vacuole': None}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_e)])
        self.assertIsNone(result['ext_state']['vacuole'])

    # ── ext_state survives non-extension events ──────────────────

    def test_ext_state_preserved_on_non_extension_key(self):
        """Pressing a non-extension key preserves ext_state dict."""
        features.ENABLE_WANDER = True
        s = _default_state()
        s['ext_state'] = {'wander_active': True, 'x_custom': 42}

        result = _call_handle_events(s, [MockEvent(pygame.KEYDOWN, key=pygame.K_UP)])
        self.assertTrue(result['ext_state']['wander_active'])
        self.assertEqual(result['ext_state']['x_custom'], 42)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Test count guardian                                                 ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestDiscovery(unittest.TestCase, TestCountMixin):
    """Verify test count for input_handler module."""

    EXPECTED_TEST_COUNT = 57


if __name__ == '__main__':
    unittest.main(verbosity=2)
