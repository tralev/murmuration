"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 7 — THREAT AGENT & ESCAPE-WAVE PROPAGATION                 ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  companion TypeScript project threat system.

 A threat agent (distinct from the Goodenough hunting predator in
 extensions/predator.py) drives an attack with a two-phase state
 machine:

   APPROACH — steer toward the swarm centre, accelerating.
   EGRESS   — once it reaches the flock, exit at high speed.

 Threat dynamics each frame (dt in seconds):
   toSwarm  = unit(swarmCenter − threat.pos)
   APPROACH:  v += rotateToward(attackDir, toSwarm) × accel × dt
   EGRESS:    v += −toSwarm × accel × dt × 2
   v        *= (1 − momentum × dt)           # damping
   |v|      clamped to threatSpeed
   pos      += v × dt

 Bird escape response (per bird within threat_radius):
   flee_i = threat_strength × (1 − d_i / threat_radius) × r̂_(bird→threat, away)

 Escape-wave propagation (Priority 7b): a bird amplifies its neighbours'
 flee response, so a chain reaction travels through the flock:
   wave_i = flee_i + wave_gain × Σ_{j∈neighbours} wave_j
 Solved by relaxation (a few sweeps) over the neighbour graph.

 Pure-maths core (uses (x, y) tuples), so it can be unit-tested without
 pygame; a draw() helper is provided for the interactive sim.

 Usage:
   from extensions.threat import ThreatAgent, escape_wave
──────────────────────────────────────────────────────────────────────
"""

import math

from flock_core import WIDTH, HEIGHT, V0


# ── Threat constants (companion defaults, scaled to this sim) ───────

THREAT_SPEED        = V0 * 2.0     # ~2× bird cruising speed
THREAT_ACCEL        = 0.30         # approach/egress acceleration
THREAT_MOMENTUM     = 0.04         # per-frame velocity damping (light: the
                                   #   companion's 0.85 is per-second — at
                                   #   dt=1 frame that would kill all motion)
THREAT_RADIUS       = 140.0        # danger zone radius (px)
THREAT_STRENGTH     = 1.8          # peak flight-response magnitude
THREAT_TURN_RATE    = 2.5          # rad/s steering toward swarm (approach)
WAVE_GAIN           = 0.15         # escape-wave amplification per neighbour
EGRESS_TRIGGER      = 60.0         # switch to egress within this of centre

THREAT_COLOR        = (255, 70, 90)
THREAT_SIZE         = 7


def _unit(x, y):
    m = math.hypot(x, y)
    if m < 1e-9:
        return 0.0, 0.0
    return x / m, y / m


class ThreatAgent:
    """A two-phase attacking threat with approach → egress state machine."""

    __slots__ = ("x", "y", "vx", "vy", "phase")

    def __init__(self, x=None, y=None):
        # Spawn at a domain edge, aimed inward, unless placed explicitly.
        self.x = WIDTH * 0.05 if x is None else x
        self.y = HEIGHT * 0.5 if y is None else y
        self.vx = THREAT_SPEED * 0.5
        self.vy = 0.0
        self.phase = "approach"

    def update(self, swarm_center, dt=1.0):
        """Advance the threat one step toward (approach) or away from
        (egress) the swarm centre.

        Parameters
        ----------
        swarm_center : (x, y) mean flock position
        dt           : timestep (frame-normalised; 1.0 = one frame)
        """
        to_x, to_y = _unit(swarm_center[0] - self.x, swarm_center[1] - self.y)
        dist = math.hypot(swarm_center[0] - self.x, swarm_center[1] - self.y)

        # ── Phase transition: reach the flock → egress ──────────
        if self.phase == "approach" and dist < EGRESS_TRIGGER:
            self.phase = "egress"

        if self.phase == "approach":
            # Steer current heading toward the swarm (rotate-toward).
            hx, hy = _unit(self.vx, self.vy)
            steer_x = hx + (to_x - hx) * min(1.0, THREAT_TURN_RATE * dt)
            steer_y = hy + (to_y - hy) * min(1.0, THREAT_TURN_RATE * dt)
            ax, ay = _unit(steer_x, steer_y)
            self.vx += ax * THREAT_ACCEL * dt
            self.vy += ay * THREAT_ACCEL * dt
        else:  # egress — accelerate away from the flock
            self.vx += -to_x * THREAT_ACCEL * dt * 2.0
            self.vy += -to_y * THREAT_ACCEL * dt * 2.0

        # ── Momentum damping ───────────────────────────────────
        damp = 1.0 - THREAT_MOMENTUM * dt
        if damp < 0.0:
            damp = 0.0
        self.vx *= damp
        self.vy *= damp

        # ── Speed clamp ────────────────────────────────────────
        speed = math.hypot(self.vx, self.vy)
        if speed > THREAT_SPEED:
            self.vx = self.vx / speed * THREAT_SPEED
            self.vy = self.vy / speed * THREAT_SPEED

        self.x += self.vx * dt
        self.y += self.vy * dt

    def position(self):
        return self.x, self.y

    def draw(self, screen, config=None):
        """Render the threat as a distinct marker with its danger ring."""
        import pygame
        heading = math.atan2(self.vy, self.vx) if (self.vx or self.vy) else 0.0
        p = pygame.Vector2(self.x, self.y)
        tip = p + pygame.Vector2(math.cos(heading), math.sin(heading)) * THREAT_SIZE * 3
        bl = p + pygame.Vector2(math.cos(heading + 2.4), math.sin(heading + 2.4)) * THREAT_SIZE * 2
        br = p + pygame.Vector2(math.cos(heading - 2.4), math.sin(heading - 2.4)) * THREAT_SIZE * 2
        ring = (90, 30, 40) if self.phase == "egress" else (150, 40, 55)
        pygame.draw.circle(screen, ring, (int(self.x), int(self.y)),
                           int(THREAT_RADIUS), 1)
        pygame.draw.polygon(screen, THREAT_COLOR, [tip, bl, br])


def flee_force(bird_pos, threat_pos):
    """Raw escape force for one bird — points *away* from the threat,
    scaled by threat_strength × (1 − d/threat_radius) inside the danger
    zone, zero outside it.

    Returns (fx, fy).
    """
    px = getattr(bird_pos, "x", None)
    if px is None:
        px, py = bird_pos[0], bird_pos[1]
    else:
        py = bird_pos.y
    dx, dy = px - threat_pos[0], py - threat_pos[1]
    d = math.hypot(dx, dy)
    if d >= THREAT_RADIUS or d < 1e-9:
        return 0.0, 0.0
    ux, uy = dx / d, dy / d
    mag = THREAT_STRENGTH * (1.0 - d / THREAT_RADIUS)
    return ux * mag, uy * mag


def escape_wave(positions, threat_pos, neighbours, sweeps=4,
                wave_gain=WAVE_GAIN):
    """Propagate the escape response through the flock.

    Each bird's response starts at its direct flee force and is then
    amplified by its neighbours' responses over a few relaxation sweeps,
    modelling the chain-reaction wave:

        wave_i = flee_i + wave_gain × Σ_{j∈neighbours(i)} wave_j

    Parameters
    ----------
    positions  : list of (x, y) or objects with .x/.y — bird positions
    threat_pos : (x, y) threat position
    neighbours : list[list[int]] — neighbour index lists per bird
    sweeps     : relaxation iterations (wave travel distance)
    wave_gain  : amplification per neighbour (companion default 0.15)

    Returns
    -------
    list of (fx, fy) — the propagated escape force per bird.
    """
    n = len(positions)
    base = [flee_force(positions[i], threat_pos) for i in range(n)]
    wave = list(base)

    for _ in range(sweeps):
        new_wave = []
        for i in range(n):
            sx = sy = 0.0
            for j in neighbours[i]:
                sx += wave[j][0]
                sy += wave[j][1]
            new_wave.append((base[i][0] + wave_gain * sx,
                             base[i][1] + wave_gain * sy))
        wave = new_wave
    return wave
