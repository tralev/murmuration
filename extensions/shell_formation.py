"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 8 — SHELL FORMATION / PILOTING                            ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  companion TypeScript/Three.js project.

 Birds orbit a leader anchor in concentric geometric shells.  Each
 bird is assigned to a shell with a fixed radius and angular speed,
 producing structured formations (rings, swarms-in-rings) rather than
 random wandering.

   shell_force for bird i at shell k:
     orbit_angle = phase_i + ω_k × time
     target_xy  = centre + R_k × [cos(orbit_angle), sin(orbit_angle)]
     force      = chase_strength × (target_xy − bird_pos)

 Pure functions (no pygame dependency for the maths) so the behaviour
 can be unit-tested in isolation.

 Usage:
   from extensions.shell_formation import ShellConfig, shell_force
──────────────────────────────────────────────────────────────────────
"""

import math
import random

from flock_core import WIDTH, HEIGHT


# ── Tunable constants ────────────────────────────────────────────────

DEFAULT_SHELL_RADII  = [40.0, 80.0, 120.0, 160.0]  # px
DEFAULT_SHELL_SPEEDS = [0.8, 0.5, 0.3, 0.2]        # rad/s
DEFAULT_CHASE_STRENGTH = 0.4

SHELL_COLORS = [
    (100, 200, 255),
    (140, 180, 240),
    (180, 160, 220),
    (200, 140, 200),
]


# ══════════════════════════════════════════════════════════════════════
#  ShellConfig
# ══════════════════════════════════════════════════════════════════════

class ShellConfig:
    """Tunable parameters for the shell formation system."""

    __slots__ = ("radii", "speeds", "chase_strength")

    def __init__(self, radii=None, speeds=None,
                 chase_strength=DEFAULT_CHASE_STRENGTH):
        self.radii = radii if radii is not None else list(DEFAULT_SHELL_RADII)
        self.speeds = speeds if speeds is not None else list(DEFAULT_SHELL_SPEEDS)
        self.chase_strength = chase_strength


# ══════════════════════════════════════════════════════════════════════
#  Bird shell assignment  (performed once on activation)
# ══════════════════════════════════════════════════════════════════════

def assign_shells(flock, config=None):
    """Assign each bird a shell index, orbital phase, and direction.

    Returns a list of (shell_idx, phase, direction) tuples, one per bird.
    Birds are distributed evenly across shells.
    """
    if config is None:
        config = ShellConfig()
    n_shells = len(config.radii)
    assignments = []
    for i, _ in enumerate(flock):
        shell_idx = i % n_shells
        phase = random.uniform(0, 2 * math.pi)
        direction = 1 if random.random() > 0.5 else -1
        assignments.append((shell_idx, phase, direction))
    return assignments


# ══════════════════════════════════════════════════════════════════════
#  Shell force
# ══════════════════════════════════════════════════════════════════════

def shell_force(bird_pos, centre, shell_idx, phase, direction,
                time, config=None):
    """Steering force toward a bird's assigned orbital position.

    Parameters
    ----------
    bird_pos  : object with .x/.y or (x, y)
    centre    : (cx, cy) — the anchor / leader centre
    shell_idx : int — which shell the bird belongs to
    phase     : float — initial orbital phase
    direction : int — +1 clockwise, -1 counter-clockwise
    time      : float — elapsed seconds
    config    : ShellConfig

    Returns
    -------
    (fx, fy) tuple.
    """
    if config is None:
        config = ShellConfig()

    px = getattr(bird_pos, "x", None)
    if px is None:
        px, py = bird_pos[0], bird_pos[1]
    else:
        py = bird_pos.y

    radius = config.radii[shell_idx % len(config.radii)]
    speed = config.speeds[shell_idx % len(config.speeds)]
    angle = phase + direction * speed * time

    target_x = centre[0] + radius * math.cos(angle)
    target_y = centre[1] + radius * math.sin(angle)

    dx = target_x - px
    dy = target_y - py
    dist = math.hypot(dx, dy)
    if dist < 1e-9:
        return 0.0, 0.0
    mag = min(config.chase_strength, dist * config.chase_strength)
    ux, uy = dx / dist, dy / dist
    return ux * mag, uy * mag


# ══════════════════════════════════════════════════════════════════════
#  Drawing helper
# ══════════════════════════════════════════════════════════════════════

def draw_shells(screen, centre, config=None):
    """Render concentric shell rings around the leader centre."""
    import pygame
    if config is None:
        config = ShellConfig()
    cx, cy = int(centre[0]), int(centre[1])
    for i, (r, color) in enumerate(zip(config.radii, SHELL_COLORS)):
        pygame.draw.circle(screen, color, (cx, cy), int(r), 1)
