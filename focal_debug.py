"""
╔══════════════════════════════════════════════════════════════════════╗
║  FOCAL BIRD DEBUG RENDERING                                         ║
╚══════════════════════════════════════════════════════════════════════╝

 Renders the focal bird debug overlay: occlusion arcs, δ̂ vector,
 velocity vector, highlight circle, and label.  Extracted from
 alg2.py so the debug view can be toggled independently and studied
 as a standalone feature.

 Toggled by pressing 'F' (requires features.ENABLE_FOCAL_DEBUG).
 Imported by alg2.py for the main 2D simulation loop.

 Dependencies:  pygame  (drawing primitives)
                flock_core  (WIDTH, HEIGHT)
──────────────────────────────────────────────────────────────────────
"""

import math
import pygame

from flock_core import WIDTH, HEIGHT


def draw(screen: pygame.Surface, boid, font: pygame.font.Font):
    """
    Render debug vectors and occlusion arcs for the focal bird.

    Shows:
      - Occlusion arcs (shaded red wedges) for merged angular intervals
      - δ̂ vector (red arrow) — direction to nearest domain boundary
      - Velocity vector (green arrow)
      - Highlight circle around the focal bird
      - "FOCAL BIRD" label

    Parameters
    ----------
    screen : pygame.Surface
    boid   : Boid  — the focal bird (must have _debug_delta, _debug_merged)
    font   : pygame.font.Font  — for the label text
    """
    pos = boid.position
    r = 80  # radius of the debug circle

    # ── Occlusion arcs (filled wedges for merged intervals) ─────
    if boid._debug_merged:
        for s, e in boid._debug_merged:
            points = [pos]
            steps = max(4, int((e - s) / 0.1))
            for i in range(steps + 1):
                a = s + (e - s) * i / steps
                points.append(pygame.Vector2(
                    pos.x + math.cos(a) * r,
                    pos.y + math.sin(a) * r,
                ))
            if len(points) > 2:
                surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                pygame.draw.polygon(surf, (255, 40, 40, 60), points)
                screen.blit(surf, (0, 0))

    # ── Debug circle ────────────────────────────────────────────
    pygame.draw.circle(screen, (60, 60, 80),
                       (int(pos.x), int(pos.y)), r, 1)

    # ── δ̂ vector (red arrow) ────────────────────────────────────
    if boid._debug_delta.length() > 0.001:
        end = pos + boid._debug_delta * r
        pygame.draw.line(screen, (255, 60, 60), pos, end, 2)
        perp = pygame.Vector2(-boid._debug_delta.y, boid._debug_delta.x) * 6
        tip = end
        pygame.draw.polygon(screen, (255, 60, 60), [
            tip,
            tip - boid._debug_delta * 12 + perp,
            tip - boid._debug_delta * 12 - perp,
        ])

    # ── Velocity vector (green arrow) ────────────────────────────
    if boid.velocity.length() > 0.001:
        vdir = boid.velocity.normalize()
        vend = pos + vdir * r * 0.7
        pygame.draw.line(screen, (60, 255, 60), pos, vend, 2)

    # ── Highlight circle around focal bird ───────────────────────
    pygame.draw.circle(screen, (255, 255, 100),
                       (int(pos.x), int(pos.y)), 12, 2)

    # ── Label ───────────────────────────────────────────────────
    label = font.render("FOCAL BIRD  (click to change, F to clear)",
                        True, (255, 255, 100))
    screen.blit(label, (pos.x + 18, pos.y - 6))
