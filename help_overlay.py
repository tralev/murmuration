"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 10 — HELP OVERLAY                                          ║
╚══════════════════════════════════════════════════════════════════════╝

Semi-transparent panel in the top-right corner showing all keyboard
controls.  Toggled by pressing 'H'.

Imported by alg2.py for the main simulation loop.
──────────────────────────────────────────────────────────────────────
"""

import pygame

from flock_core import WIDTH


_HELP_LINES = [
    "CONTROLS",
    "─────────────────────────────────────────",
    "M         toggle PROJECTION / SPATIAL mode",
    "B         toggle TOROIDAL / MARGIN boundary",
    "1–0       number-key presets (10 scenarios)",
    "s,l,i,v,k,q  letter-key presets (6 scenarios)",
    "  (press same key again to toggle off)",
    "↑ / ↓     φp  ±0.01",
    "← / →     φa  ±0.01   (φn = 1 − φp − φa)",
    "[ / ]     σ   ±1      (neighbour count)",
    "+ / -     add / remove 10 birds",
    "F         toggle focal bird debug view",
    "G         toggle grid overlay (SPATIAL)",
    "H         hide this help",
    "SPACE     pause / resume",
    "R         reset flock",
    "ESC       quit",
]


def draw(screen: pygame.Surface, font: pygame.font.Font):
    """
    Render the help overlay as a semi-transparent panel in the top-right.
    """
    x, y = WIDTH - 370, 10
    bg = pygame.Surface((360, len(_HELP_LINES) * 18 + 12), pygame.SRCALPHA)
    bg.fill((10, 12, 18, 200))
    screen.blit(bg, (x - 4, y - 4))
    for line in _HELP_LINES:
        surf = font.render(line, True, (200, 200, 160))
        screen.blit(surf, (x, y))
        y += 18
