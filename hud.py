"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 12 — HUD  (status badges & banners)                        ║
╚══════════════════════════════════════════════════════════════════════╝

 Small status indicators drawn every frame, extracted from alg2.py's
 render block so the main loop stays a pure orchestrator:

   - mode badge      (top-right)   PROJECTION / SPATIAL
   - boundary badge  (top-right)   TOROIDAL / MARGIN
   - paused banner   (bottom)      shown while simulation is paused

 The larger overlays live in their own modules: metrics panel in
 metrics.py, help text in help_overlay.py, focal-bird debug view in
 focal_debug.py.

 Dependencies:  flock_core  (WIDTH, HEIGHT, mode constants,
                             MARGIN_BOUNDARY read dynamically)
──────────────────────────────────────────────────────────────────────
"""

import pygame

import flock_core
from flock_core import WIDTH, HEIGHT, MODE_PROJECTION, Config


def draw_badges(screen: pygame.Surface, font: pygame.font.Font,
                config: Config):
    """Draw the mode and boundary badges in the top-right corner.

    MARGIN_BOUNDARY is read through the flock_core module (not a
    from-import) because the B key rebinds it at runtime.
    """
    badge_text = "PROJECTION" if config.mode == MODE_PROJECTION else "SPATIAL"
    badge_color = ((120, 180, 220) if config.mode == MODE_PROJECTION
                   else (220, 180, 120))
    badge = font.render(badge_text, True, badge_color)
    screen.blit(badge, (WIDTH - badge.get_width() - 10, 10))

    boundary_text = "MARGIN" if flock_core.MARGIN_BOUNDARY else "TOROIDAL"
    boundary_color = ((220, 140, 100) if flock_core.MARGIN_BOUNDARY
                      else (100, 200, 140))
    boundary_badge = font.render(boundary_text, True, boundary_color)
    screen.blit(boundary_badge,
                (WIDTH - boundary_badge.get_width() - 10, 30))


def draw_paused_banner(screen: pygame.Surface, font: pygame.font.Font):
    """Draw the paused notice near the bottom of the window."""
    ptext = font.render(
        "PAUSED  (SPACE to resume, R to reset, ESC to quit)",
        True, (255, 200, 100))
    screen.blit(ptext, (WIDTH // 2 - 220, HEIGHT - 30))
