"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 10 — HELP OVERLAY                                          ║
╚══════════════════════════════════════════════════════════════════════╝

Semi-transparent panel in the top-right corner showing all keyboard
controls.  Toggled by pressing 'H'.

The line list is built per draw from the feature flags, so a modular
build (see features.py) only advertises the keys that actually work:
disabled presets, mode toggle, focal debug, and grid overlay lines
disappear along with their features.

Imported by alg2.py for the main simulation loop (flag-gated —
never loaded when ENABLE_HELP_OVERLAY is False).
──────────────────────────────────────────────────────────────────────
"""

import pygame

import features
from flock_core import WIDTH


def _build_help_lines():
    """Assemble the help text for the currently enabled feature set."""
    lines = [
        "CONTROLS",
        "─────────────────────────────────────────",
    ]
    if features.ENABLE_PROJECTION_MODE and features.ENABLE_SPATIAL_MODE:
        lines.append("M         toggle PROJECTION / SPATIAL mode")
    lines.append("B         toggle TOROIDAL / MARGIN boundary")
    if features.ENABLE_PRESETS:
        lines.extend([
            "1–0       number-key presets (10 scenarios)",
            "s,l,i,v,k,q  letter-key presets (6 scenarios)",
            "  (press same key again to toggle off)",
        ])
    lines.extend([
        "↑ / ↓     φp  ±0.01",
        "← / →     φa  ±0.01   (φn = 1 − φp − φa)",
        "[ / ]     σ   ±1      (neighbour count)",
        "+ / -     add / remove 10 birds",
    ])
    if features.ENABLE_FOCAL_DEBUG:
        lines.append("F         toggle focal bird debug view")
    if features.ENABLE_GRID_OVERLAY:
        lines.append("G         toggle grid overlay (SPATIAL)")
    if features.ENABLE_THREAT:
        lines.append("T         spawn / remove threat agent")
    if features.ENABLE_WANDER:
        lines.append("W         toggle wander behaviour")
    if features.ENABLE_ADAPTIVE_QUALITY:
        lines.append("A         toggle adaptive quality")
    if features.ENABLE_MEDIUM_PRESETS:
        lines.append("N         cycle ambient medium")
    if features.ENABLE_H2_ROBUSTNESS:
        lines.append("J         compute H₂ robustness")
    if features.ENABLE_SEASONAL:
        lines.append("C         advance seasonal day (+30)")
    if features.ENABLE_FLOCK_SHAPE:
        lines.append("Y         flock shape analysis")
    if features.ENABLE_LEADER:
        lines.append("O         toggle leader / attractor system")
    lines.extend([
        "H         hide this help",
        "SPACE     pause / resume",
        "R         reset flock",
        "ESC       quit",
    ])
    return lines


def draw(screen: pygame.Surface, font: pygame.font.Font):
    """
    Render the help overlay as a semi-transparent panel in the top-right.
    """
    lines = _build_help_lines()
    x, y = WIDTH - 370, 10
    bg = pygame.Surface((360, len(lines) * 18 + 12), pygame.SRCALPHA)
    bg.fill((10, 12, 18, 200))
    screen.blit(bg, (x - 4, y - 4))
    for line in lines:
        surf = font.render(line, True, (200, 200, 160))
        screen.blit(surf, (x, y))
        y += 18
