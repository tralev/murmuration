"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 7c — VACUOLE FORMATION                                    ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  companion TypeScript/Three.js project.

 A vacuole is a region of empty space that forms when birds flee a
 threat from all directions, leaving a cavity behind.  The vacuole
 agent orbits near the flock centre, and birds within its danger
 radius are pushed radially outward — away from the vacuole centre.

   For each bird within vacuole_radius of the vacuole centre:
     flee = vacuole_strength × (1 − d / vacuole_radius) × r̂_away

 The vacuole persists and orbits as long as it remains active.
 Toggle via 'E' key (Empty / cavitY / vacuolE).

 Pure functions (no pygame dependency for the maths) so the behaviour
 can be unit-tested in isolation.

 Usage:
   from extensions.vacuole import VacuoleAgent, VacuoleConfig
──────────────────────────────────────────────────────────────────────
"""

import math
import random

from flock_core import WIDTH, HEIGHT


# ── Tunable constants (companion defaults, scaled to this sim) ──────

VACUOLE_RADIUS     = 120.0   # danger zone radius (px)
VACUOLE_STRENGTH   = 1.2     # peak repulsion force
VACUOLE_ORBIT_SPEED = 0.6    # angular speed of orbit (rad/s)
VACUOLE_ORBIT_RADIUS = 60.0  # distance from flock centre (px)

VACUOLE_COLOR      = (140, 100, 180)
VACUOLE_RING_COLOR = (100, 60, 140)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  VacuoleConfig                                                      ║
# ╚══════════════════════════════════════════════════════════════════════╝

class VacuoleConfig:
    """Tunable parameters for the vacuole system."""

    __slots__ = ("vacuole_radius", "vacuole_strength",
                 "orbit_speed", "orbit_radius")

    def __init__(self, vacuole_radius=VACUOLE_RADIUS,
                 vacuole_strength=VACUOLE_STRENGTH,
                 orbit_speed=VACUOLE_ORBIT_SPEED,
                 orbit_radius=VACUOLE_ORBIT_RADIUS):
        self.vacuole_radius = vacuole_radius
        self.vacuole_strength = vacuole_strength
        self.orbit_speed = orbit_speed
        self.orbit_radius = orbit_radius


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  VacuoleAgent                                                       ║
# ╚══════════════════════════════════════════════════════════════════════╝

class VacuoleAgent:
    """An autonomous vacuole that orbits the flock centre, pushing birds
    radially outward to create an empty cavity."""

    __slots__ = ("px", "py", "phase", "config")

    def __init__(self, config=None):
        if config is None:
            config = VacuoleConfig()
        self.config = config
        self.phase = random.uniform(0, 2 * math.pi)
        # Start at the orbit position for t=0
        self.px = WIDTH / 2.0 + config.orbit_radius * math.cos(self.phase)
        self.py = HEIGHT / 2.0 + config.orbit_radius * math.sin(self.phase)

    def update(self, swarm_center, time: float):
        """Advance the vacuole position along its orbit.

        Parameters
        ----------
        swarm_center : (x, y) mean flock position
        time         : elapsed time in seconds
        """
        angle = self.config.orbit_speed * time + self.phase
        self.px = swarm_center[0] + self.config.orbit_radius * math.cos(angle)
        self.py = swarm_center[1] + self.config.orbit_radius * math.sin(angle)

    def position(self):
        """Return current (x, y)."""
        return self.px, self.py


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Repulsion force                                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝

def vacuole_force(bird_pos, vacuole_center, config=None):
    """Radial repulsion force pushing a bird AWAY from the vacuole centre.

    Linear falloff: full strength at d=0, zero at d=vacuole_radius.
    Returns (0, 0) if the bird is outside the vacuole radius.

    Parameters
    ----------
    bird_pos       : object with .x/.y or (x, y)
    vacuole_center : (x, y) vacuole centre
    config         : VacuoleConfig (defaults if None)

    Returns
    -------
    (fx, fy) tuple.
    """
    if config is None:
        config = VacuoleConfig()

    px = getattr(bird_pos, "x", None)
    if px is None:
        px, py = bird_pos[0], bird_pos[1]
    else:
        py = bird_pos.y

    # Vector from vacuole to bird (repel away from vacuole)
    dx = px - vacuole_center[0]
    dy = py - vacuole_center[1]
    dist = math.hypot(dx, dy)
    if dist < 1e-9 or dist > config.vacuole_radius:
        return 0.0, 0.0
    ux, uy = dx / dist, dy / dist
    mag = config.vacuole_strength * (1.0 - dist / config.vacuole_radius)
    return ux * mag, uy * mag


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Drawing helper  (imports pygame locally for testability)           ║
# ╚══════════════════════════════════════════════════════════════════════╝

def draw_vacuole(screen, vacuole, config=None):
    """Render the vacuole as a hollow ring with a pulsating centre dot."""
    import pygame
    if config is None:
        config = vacuole.config if hasattr(vacuole, 'config') else VacuoleConfig()
    px, py = vacuole.position()
    # Danger ring
    pygame.draw.circle(screen, VACUOLE_RING_COLOR,
                       (int(px), int(py)), int(config.vacuole_radius), 2)
    # Core hollow circle (cavity)
    pygame.draw.circle(screen, VACUOLE_COLOR,
                       (int(px), int(py)), 10, 2)
    # Pulsating centre
    r = 4
    pygame.draw.circle(screen, VACUOLE_COLOR, (int(px), int(py)), r)
