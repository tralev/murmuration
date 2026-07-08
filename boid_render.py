"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 10 — 2D BIRD RENDERING                                     ║
╚══════════════════════════════════════════════════════════════════════╝

 Drawing code for the 2D Boid agent, extracted from boid.py so that
 agent physics and rendering can be studied (and modified) separately.
 The Boid class holds state; this module turns that state into pixels.

 Feature flags:
   ENABLE_TRAILS — draws the position-history polyline behind each
   bird (the history itself is recorded by Boid.update()).

 Dependencies:  flock_core  (BOID_SIZE, mode constants)
                features    (ENABLE_TRAILS)
──────────────────────────────────────────────────────────────────────
"""

import math

import pygame

import features
from flock_core import BOID_SIZE, MODE_PROJECTION, Config


def draw_boid(screen: pygame.Surface, boid, config: Config):
    """
    Render one bird as a small triangle pointing in its heading direction.
    Colour: cool blue-white in PROJECTION mode, warm amber in SPATIAL mode.

    Duck-types the boid — only .position, .velocity, and .history are
    accessed, so no import of boid.py is needed (and no circular import
    is created).
    """
    if boid.velocity.length_squared() > 0.001:
        direction = math.atan2(boid.velocity.y, boid.velocity.x)
    else:
        direction = 0

    tip = boid.position + pygame.Vector2(
        math.cos(direction), math.sin(direction)
    ) * BOID_SIZE * 2.5
    back_left = boid.position + pygame.Vector2(
        math.cos(direction + 2.3), math.sin(direction + 2.3)
    ) * BOID_SIZE * 1.5
    back_right = boid.position + pygame.Vector2(
        math.cos(direction - 2.3), math.sin(direction - 2.3)
    ) * BOID_SIZE * 1.5

    # ── Trail (position-history polyline, drawn behind the bird) ──
    if features.ENABLE_TRAILS and len(boid.history) > 1:
        pts = [(p.x, p.y) for p in boid.history]
        pygame.draw.aalines(screen, (85, 140, 244), False, pts, 1)

    if config.mode == MODE_PROJECTION:
        color = (200, 210, 230)
    else:
        color = (230, 200, 160)

    pygame.draw.polygon(screen, color, [tip, back_left, back_right])
