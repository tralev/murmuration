"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 8 — ATTRACTOR / LEADER SYSTEM                             ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  companion TypeScript/Three.js project.

 Leader anchors are procedural waypoints that move in sinusoidal
 patterns through the simulation space.  Multiple anchors can be
 active simultaneously, each attracting nearby birds.

   anchor_i.pos(t) = centre + A × [sin(ωᵢ×t + φᵢ), cos(ωᵢ×t + φᵢ)]

   For birds within attractorRange of an anchor:
     attractForce = chaseStrength × unit(anchor.pos − bird.pos)

 Pure functions (no pygame dependency for the maths) so the behaviour
 can be unit-tested in isolation.

 Usage:
   from extensions.leader import LeaderAnchor, LeaderConfig, attractor_force
──────────────────────────────────────────────────────────────────────
"""

import math
import random

from flock_core import WIDTH, HEIGHT, V0


# ── Tunable constants (companion defaults, scaled to this sim) ──────

DEFAULT_ATTRACTOR_RADIUS  = 80.0   # amplitude of sinusoidal motion (px)
DEFAULT_ATTRACTOR_SPEED   = 0.5    # angular speed (rad/s)
DEFAULT_ATTRACTOR_RANGE   = 200.0  # birds within this range feel the pull
DEFAULT_CHASE_STRENGTH    = 0.3    # pull force magnitude

LEADER_COLOR = (100, 200, 255)
LEADER_SIZE  = 8
LEADER_RING_COLOR = (60, 140, 200)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  LeaderConfig                                                       ║
# ╚══════════════════════════════════════════════════════════════════════╝

class LeaderConfig:
    """Tunable parameters for the leader / attractor system."""

    __slots__ = ("anchor_count", "attractor_radius", "attractor_speed",
                 "attractor_range", "chase_strength")

    def __init__(self, anchor_count=1, attractor_radius=DEFAULT_ATTRACTOR_RADIUS,
                 attractor_speed=DEFAULT_ATTRACTOR_SPEED,
                 attractor_range=DEFAULT_ATTRACTOR_RANGE,
                 chase_strength=DEFAULT_CHASE_STRENGTH):
        self.anchor_count = anchor_count
        self.attractor_radius = attractor_radius
        self.attractor_speed = attractor_speed
        self.attractor_range = attractor_range
        self.chase_strength = chase_strength


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  LeaderAnchor                                                       ║
# ╚══════════════════════════════════════════════════════════════════════╝

class LeaderAnchor:
    """A single procedural waypoint moving in a sinusoidal Lissajous orbit.

    Anchors are deterministic given their random seed phase, so the
    same anchor always follows the same path.
    """

    __slots__ = ("cx", "cy", "phase_x", "phase_y", "radius", "speed",
                 "px", "py")

    def __init__(self, cx=None, cy=None, config=None):
        if config is None:
            config = LeaderConfig()
        self.cx = WIDTH / 2.0 if cx is None else cx
        self.cy = HEIGHT / 2.0 if cy is None else cy
        # Random phase per anchor for visual variety
        self.phase_x = random.uniform(0, 2 * math.pi)
        self.phase_y = random.uniform(0, 2 * math.pi)
        self.radius = config.attractor_radius
        self.speed = config.attractor_speed
        self.px = self.cx
        self.py = self.cy

    def update(self, time: float):
        """Advance the anchor position to the given *time* (seconds)."""
        self.px = self.cx + self.radius * math.sin(self.speed * time + self.phase_x)
        self.py = self.cy + self.radius * math.cos(self.speed * time + self.phase_y)

    def position(self):
        """Return current (x, y)."""
        return self.px, self.py


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Attractor / leader force                                           ║
# ╚══════════════════════════════════════════════════════════════════════╝

def attractor_force(bird_pos, anchor_pos, config=None):
    """Steering force pulling a bird toward an anchor point.

    Parameters
    ----------
    bird_pos   : object with .x / .y (e.g. pygame.Vector2) or (x, y)
    anchor_pos : (x, y) anchor position
    config     : LeaderConfig (defaults if None)

    Returns
    -------
    (fx, fy) tuple — force toward the anchor scaled by chase_strength,
    or (0, 0) if the bird is outside attractor_range.
    """
    if config is None:
        config = LeaderConfig()

    px = getattr(bird_pos, "x", None)
    if px is None:
        px, py = bird_pos[0], bird_pos[1]
    else:
        py = bird_pos.y

    dx = anchor_pos[0] - px
    dy = anchor_pos[1] - py
    dist = math.hypot(dx, dy)
    if dist < 1e-9 or dist > config.attractor_range:
        return 0.0, 0.0
    # Linear falloff: full strength at 0, zero at range
    mag = config.chase_strength * (1.0 - dist / config.attractor_range)
    ux, uy = dx / dist, dy / dist
    return ux * mag, uy * mag


def leader_force(bird_pos, anchors, config=None):
    """Sum of attractor forces from all active anchors.

    Parameters
    ----------
    bird_pos : object with .x/.y or (x, y)
    anchors  : list of LeaderAnchor
    config   : LeaderConfig (defaults if None)

    Returns
    -------
    (fx, fy) tuple.
    """
    if config is None:
        config = LeaderConfig()
    fx = fy = 0.0
    for anchor in anchors:
        ax, ay = attractor_force(bird_pos, anchor.position(), config)
        fx += ax
        fy += ay
    return fx, fy


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Drawing helper  (imports pygame locally for testability)           ║
# ╚══════════════════════════════════════════════════════════════════════╝

def draw_anchors(screen, anchors, config=None):
    """Render all leader anchors as pulsing rings with direction marker."""
    import pygame
    if config is None:
        config = LeaderConfig()
    for anchor in anchors:
        px, py = anchor.position()
        # Attractor range ring (dashed feel via thin line)
        pygame.draw.circle(screen, LEADER_RING_COLOR,
                           (int(px), int(py)), int(config.attractor_range), 1)
        # Core dot
        pygame.draw.circle(screen, LEADER_COLOR,
                           (int(px), int(py)), LEADER_SIZE)
        # Small direction indicator (tiny cross)
        r = LEADER_SIZE + 4
        pygame.draw.line(screen, LEADER_COLOR,
                         (int(px - r), int(py)), (int(px + r), int(py)), 1)
        pygame.draw.line(screen, LEADER_COLOR,
                         (int(px), int(py - r)), (int(px), int(py + r)), 1)
