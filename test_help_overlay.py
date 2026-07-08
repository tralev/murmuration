"""
Unit tests for the help overlay (help_overlay.py).

Covers:
  - _build_help_lines  — flag-aware line assembly: disabled features'
                         key bindings disappear from the overlay
  - draw               — renders onto a headless surface and actually
                         paints pixels
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from test_count_mixin import TestCountMixin

import features
import help_overlay
from help_overlay import _build_help_lines


def _lines_text(lines):
    return "\n".join(lines)


class TestBuildHelpLines(unittest.TestCase):
    """Flag-aware assembly of the overlay's line list."""

    def setUp(self):
        self._saved = {
            k: getattr(features, k) for k in dir(features)
            if k.startswith("ENABLE_")
        }

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(features, k, v)

    def test_default_build_lists_core_controls(self):
        """With default flags, the overlay lists mode toggle, presets,
        parameter keys, and simulation controls."""
        text = _lines_text(_build_help_lines())
        for fragment in ["CONTROLS", "toggle PROJECTION / SPATIAL",
                         "number-key presets", "letter-key presets",
                         "φp", "φa", "σ", "pause / resume",
                         "reset flock", "quit"]:
            self.assertIn(fragment, text,
                          f"Default overlay missing {fragment!r}")

    def test_presets_disabled_hides_preset_lines(self):
        """ENABLE_PRESETS=False removes all preset key lines."""
        features.ENABLE_PRESETS = False
        text = _lines_text(_build_help_lines())
        self.assertNotIn("presets", text)
        self.assertNotIn("toggle off", text)

    def test_single_model_hides_mode_toggle(self):
        """With only one flocking model enabled, the M-key line is
        removed (the key is inert in that build)."""
        features.ENABLE_SPATIAL_MODE = False
        text = _lines_text(_build_help_lines())
        self.assertNotIn("toggle PROJECTION / SPATIAL", text)

    def test_focal_and_grid_lines_follow_flags(self):
        """F and G lines appear only when their features are enabled
        (both default to False, so the default overlay omits them)."""
        text = _lines_text(_build_help_lines())
        self.assertNotIn("focal bird debug", text)
        self.assertNotIn("grid overlay", text)

        features.ENABLE_FOCAL_DEBUG = True
        features.ENABLE_GRID_OVERLAY = True
        text = _lines_text(_build_help_lines())
        self.assertIn("focal bird debug", text)
        self.assertIn("grid overlay", text)

    def test_always_present_controls_survive_minimal_build(self):
        """Even with every optional feature off, boundary toggle,
        parameter keys, pause, reset, help, and quit remain."""
        features.ENABLE_PRESETS = False
        features.ENABLE_SPATIAL_MODE = False
        features.ENABLE_FOCAL_DEBUG = False
        features.ENABLE_GRID_OVERLAY = False
        text = _lines_text(_build_help_lines())
        for fragment in ["TOROIDAL / MARGIN", "φp", "σ",
                         "hide this help", "pause / resume",
                         "reset flock", "quit"]:
            self.assertIn(fragment, text,
                          f"Minimal overlay missing {fragment!r}")


class TestDraw(unittest.TestCase):
    """draw() paints onto a headless surface."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1000, 700))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_draw_paints_pixels(self):
        """After draw(), the overlay region is no longer the fill
        colour (the panel background and text were blitted)."""
        screen = pygame.display.get_surface()
        fill = (20, 22, 30)
        screen.fill(fill)
        font = pygame.font.Font(None, 16)

        help_overlay.draw(screen, font)

        # Sample inside the panel (top-right corner, x = WIDTH - 370)
        sampled = screen.get_at((700, 40))[:3]
        self.assertNotEqual(sampled, fill,
                            "Overlay drew nothing — panel region "
                            "still shows the fill colour")


class TestDiscovery(unittest.TestCase, TestCountMixin):
    """Verify test count for help overlay module."""

    EXPECTED_TEST_COUNT = 6


if __name__ == '__main__':
    unittest.main(verbosity=2)
