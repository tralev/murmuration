"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 4 — VISUAL THEMES                                          ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  companion TypeScript project `themes.ts`.

 A small palette registry so the simulation's look can be switched
 between named colour schemes.  Each theme supplies the handful of
 colours the renderer needs: background, the two mode-tinted bird
 colours (projection / spatial), trail, HUD text, and badge accents.

 Themes (companion set):
   dark     — default: near-black field, cool birds  (the current look)
   ink      — deep indigo "ink on water"
   paper    — light background, dark birds (print-friendly)
   graphite — neutral grey, high-contrast birds
   inverse  — white field, black birds (maximum contrast)

 Pure data + a resolver — no pygame dependency, so themes can be listed
 and unit-tested headlessly.  The renderer reads the resolved Theme and
 uses its colours.

 Usage:
   from extensions.themes import THEMES, get_theme, cycle_theme
──────────────────────────────────────────────────────────────────────
"""


class Theme:
    """A resolved colour scheme.  All colours are (r, g, b) 0–255 tuples."""

    __slots__ = ("name", "background", "bird_projection", "bird_spatial",
                 "trail", "hud_text", "accent")

    def __init__(self, name, background, bird_projection, bird_spatial,
                 trail, hud_text, accent):
        self.name = name
        self.background = background
        self.bird_projection = bird_projection
        self.bird_spatial = bird_spatial
        self.trail = trail
        self.hud_text = hud_text
        self.accent = accent


# ── Theme registry (companion themes.ts palette) ────────────────────

THEMES = {
    "dark": Theme(
        "dark",
        background=(20, 22, 30),
        bird_projection=(200, 210, 230),
        bird_spatial=(230, 200, 160),
        trail=(85, 140, 244),
        hud_text=(170, 200, 170),
        accent=(120, 180, 220),
    ),
    "ink": Theme(
        "ink",
        background=(10, 14, 28),
        bird_projection=(150, 180, 235),
        bird_spatial=(210, 180, 235),
        trail=(70, 110, 210),
        hud_text=(150, 175, 210),
        accent=(110, 150, 230),
    ),
    "paper": Theme(
        "paper",
        background=(238, 236, 228),
        bird_projection=(60, 70, 110),
        bird_spatial=(140, 80, 40),
        trail=(120, 140, 200),
        hud_text=(50, 55, 60),
        accent=(70, 90, 140),
    ),
    "graphite": Theme(
        "graphite",
        background=(48, 50, 54),
        bird_projection=(220, 228, 240),
        bird_spatial=(240, 210, 170),
        trail=(120, 150, 220),
        hud_text=(210, 214, 210),
        accent=(150, 190, 230),
    ),
    "inverse": Theme(
        "inverse",
        background=(250, 250, 250),
        bird_projection=(20, 30, 60),
        bird_spatial=(90, 40, 10),
        trail=(40, 70, 150),
        hud_text=(20, 20, 20),
        accent=(30, 60, 120),
    ),
}

# Cycle order for the theme-toggle key.
THEME_ORDER = ["dark", "ink", "paper", "graphite", "inverse"]


def get_theme(name: str) -> Theme:
    """Return the named Theme, or the 'dark' default if unknown."""
    return THEMES.get(name, THEMES["dark"])


def cycle_theme(name: str) -> str:
    """Return the next theme name in THEME_ORDER, wrapping around."""
    try:
        i = THEME_ORDER.index(name)
    except ValueError:
        return THEME_ORDER[0]
    return THEME_ORDER[(i + 1) % len(THEME_ORDER)]
