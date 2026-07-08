"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 16 — RICH PILOT STATE                                      ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  companion TypeScript project `types.ts` (SimulationPilot).

 The companion tracks more per-flock state than a bare centre + heading.
 A SimulationPilot carries the extra channels a richer leader/pilot
 behaviour needs:

   heading      — current travel direction (radians)
   radius       — characteristic flock radius (spread)
   roll         — bank angle, driven by how sharply the heading turns
                  (birds bank into turns, like aircraft)
   medium_pulse — slow breathing scalar in [0, 1], for ambient effects

 This module provides the dataclass and its per-frame update so the
 derived channels (roll from turn rate, medium_pulse from a clock) stay
 consistent.  Pure — no pygame — so it unit-tests headlessly.

 Usage:
   from extensions.pilot_state import SimulationPilot
──────────────────────────────────────────────────────────────────────
"""

import math
from dataclasses import dataclass, field


# Bank response: how strongly heading change maps to roll, and how fast
# roll relaxes back toward level flight.
_ROLL_GAIN = 3.0
_ROLL_MAX = math.radians(60)      # birds don't bank past ~60°
_ROLL_DECAY = 0.85                # per-update relaxation toward level
_MEDIUM_PULSE_RATE = 0.35         # radians/sec of the breathing oscillator


@dataclass
class SimulationPilot:
    """Rich per-flock pilot state (companion SimulationPilot)."""

    heading: float = 0.0          # radians
    radius: float = 100.0         # flock spread
    roll: float = 0.0             # bank angle, radians
    medium_pulse: float = 0.0     # breathing scalar [0, 1]
    _t: float = field(default=0.0, repr=False)

    def update(self, new_heading: float, radius: float, dt: float = 1.0):
        """Advance the pilot one step.

        roll is driven by the heading *change* (banking into the turn),
        clamped and relaxed toward level; medium_pulse is a slow sine.

        Parameters
        ----------
        new_heading : freshly computed travel direction (radians)
        radius      : current flock radius/spread
        dt          : timestep in seconds
        """
        # Signed shortest heading delta.
        delta = (new_heading - self.heading + math.pi) % (2 * math.pi) - math.pi

        # Bank into the turn, decay toward level, clamp.
        target_roll = max(-_ROLL_MAX, min(_ROLL_MAX, _ROLL_GAIN * delta))
        self.roll = self.roll * _ROLL_DECAY + target_roll * (1.0 - _ROLL_DECAY)

        self.heading = new_heading
        self.radius = radius

        self._t += dt
        self.medium_pulse = 0.5 + 0.5 * math.sin(self._t * _MEDIUM_PULSE_RATE)

    @classmethod
    def from_flock(cls, flock):
        """Seed a pilot from a flock's current mean heading and spread."""
        n = len(flock)
        if n == 0:
            return cls()
        vx = sum(getattr(b.velocity, "x", b.velocity[0]) for b in flock) / n
        vy = sum(getattr(b.velocity, "y", b.velocity[1]) for b in flock) / n
        heading = math.atan2(vy, vx) if (vx or vy) else 0.0

        cx = sum(getattr(b.position, "x", b.position[0]) for b in flock) / n
        cy = sum(getattr(b.position, "y", b.position[1]) for b in flock) / n
        spread = 0.0
        for b in flock:
            px = getattr(b.position, "x", b.position[0])
            py = getattr(b.position, "y", b.position[1])
            spread += math.hypot(px - cx, py - cy)
        radius = spread / n
        return cls(heading=heading, radius=radius)
