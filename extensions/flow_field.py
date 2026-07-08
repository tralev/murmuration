"""
╔══════════════════════════════════════════════════════════════╗
║  EXTENSION: flow field  (D key)                             ║
║                                                              ║
║  Environmental wind / drift field — a global force that      ║
║  pushes all birds in a configurable direction, simulating    ║
║  atmospheric currents.                                       ║
║                                                              ║
║  Pure functions for testability.                             ║
╚══════════════════════════════════════════════════════════════╝
"""

import math
from dataclasses import dataclass, field


@dataclass
class FlowConfig:
    """Tunable parameters for the flow field extension."""

    # Base wind direction (radians, 0 = right, π/2 = down)
    wind_angle: float = math.pi / 6  # ~30° down-right
    # Wind strength — fraction of V0 applied per frame
    wind_strength: float = 0.02
    # How much the wind direction wanders per second (radians/s)
    wind_wander: float = 0.3
    # Turbulence — random perturbation magnitude added to each bird
    turbulence: float = 0.005
    # Gust chance per second (0.0–1.0)
    gust_chance: float = 0.15
    # Gust strength multiplier (temporary boost)
    gust_strength: float = 3.0
    # Gust duration in seconds
    gust_duration: float = 0.5


def flow_force(config: FlowConfig, flow_time: float, gust_active: bool,
               gust_time: float) -> tuple:
    """
    Pure function — compute the current flow (wind) direction and strength.

    Returns (fx, fy) — the force vector to apply to each bird.

    The wind direction wanders sinusoidally over time, and gusts
    temporarily amplify the strength.
    """
    # Wandering wind direction
    angle = config.wind_angle + math.sin(flow_time * config.wind_wander) * 0.4
    angle += math.cos(flow_time * config.wind_wander * 0.7) * 0.25

    strength = config.wind_strength

    # Gust amplification
    if gust_active:
        # Gust decays linearly over its duration
        remaining = 1.0 - (gust_time / config.gust_duration)
        if remaining > 0:
            strength *= 1.0 + (config.gust_strength - 1.0) * remaining

    fx = math.cos(angle) * strength
    fy = math.sin(angle) * strength

    return (fx, fy)


def draw_flow(screen, config: FlowConfig, flow_time: float,
              gust_active: bool):
    """
    Draw a subtle wind indicator arrow in the top-left corner.
    """
    if config is None:
        return
    try:
        import pygame
    except ImportError:
        return

    angle = config.wind_angle + math.sin(flow_time * config.wind_wander) * 0.4
    angle += math.cos(flow_time * config.wind_wander * 0.7) * 0.25

    # Arrow origin (top-left area)
    ox, oy = 30, 30
    length = 40

    # Arrow tip
    tx = ox + math.cos(angle) * length
    ty = oy + math.sin(angle) * length

    # Colour: white normally, yellow during gust
    colour = (255, 220, 80) if gust_active else (180, 200, 220)

    # Draw arrow shaft
    pygame.draw.line(screen, colour, (ox, oy), (tx, ty), 2)

    # Draw arrowhead
    head_len = 10
    head_angle = 0.5
    for sign in (-1, 1):
        hx = tx - math.cos(angle + sign * head_angle) * head_len
        hy = ty - math.sin(angle + sign * head_angle) * head_len
        pygame.draw.line(screen, colour, (tx, ty), (hx, hy), 2)

    # Label
    font = pygame.font.SysFont('monospace', 12)
    label = font.render('WIND', True, colour)
    screen.blit(label, (ox - 10, oy + 15))
