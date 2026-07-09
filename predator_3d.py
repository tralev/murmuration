"""
╔══════════════════════════════════════════════════════════════════════╗
║  PREDATOR AGENT (3D) — anti-predator flocking dynamics              ║
╚══════════════════════════════════════════════════════════════════════╝

 Source (see sci.md §3 for the ecology and §4.8 for the 3D dynamics):
 Goodenough et al. (2017). Birds of prey attended
 29.6% of murmurations and were positively correlated with display size
 and duration; the paper concludes murmurations are primarily an
 anti-predator adaptation (dilution / detection / confusion — "safer
 together"). This module adds a real predator that hunts the flock and the
 flock's flight response, so that anti-predator behaviour (a fleeing wave,
 a carved void, tighter clustering) actually emerges in the 3D simulation.

 ── Predator dynamics ───────────────────────────────────────────────
   A Peregrine-like raptor flies ~2× the birds' cruising speed and steers
   toward the swarm centre of mass:

     â = unit(r_com − r_pred)
     v_pred ← v_pred + PREDATOR_ACCEL · â ,   |v_pred| clamped to PREDATOR_SPEED
     r_pred ← r_pred + v_pred

 ── Flight response (per bird) ──────────────────────────────────────
   A bird within the danger radius R_d flees directly away from the
   predator, more strongly the closer it is:

     F_flee = φ_flee · (1 − d/R_d) · unit(r_bird − r_pred)     for d < R_d

 Pure numpy Vec3. The predator is a lightweight agent; the flight force is
 a steering force accumulated via boid.apply_force.

 Dependencies:  numpy, flock_core (V0, WIDTH/HEIGHT/DEPTH, MAX_FORCE)
──────────────────────────────────────────────────────────────────────
"""

import numpy as np

from flock_core import V0, WIDTH, HEIGHT, DEPTH, MAX_FORCE


PREDATOR_SPEED  = V0 * 2.0      # raptor cruises ~2× the flock speed
PREDATOR_ACCEL  = 0.4          # hunting turn/accel per frame
DANGER_RADIUS   = 160.0        # birds within this flee
FLIGHT_STRENGTH = 2.5          # φ_flee — flight-response magnitude


class Predator3D:
    """A 3D predator that pursues the flock's centre of mass."""

    __slots__ = ("pos", "vel")

    def __init__(self, pos=None, vel=None):
        # Spawn at a corner of the volume, aimed inward, unless placed.
        self.pos = (np.array(pos, dtype=float) if pos is not None
                    else np.array([0.0, 0.0, DEPTH * 0.5]))
        self.vel = (np.array(vel, dtype=float) if vel is not None
                    else np.array([PREDATOR_SPEED, PREDATOR_SPEED, 0.0]))

    def update(self, swarm_center):
        """Steer toward *swarm_center* and advance one frame (toroidal wrap)."""
        to = np.asarray(swarm_center, dtype=float) - self.pos
        n = np.linalg.norm(to)
        if n > 1e-9:
            self.vel += (to / n) * PREDATOR_ACCEL
        speed = np.linalg.norm(self.vel)
        if speed > PREDATOR_SPEED:
            self.vel = self.vel / speed * PREDATOR_SPEED
        self.pos += self.vel
        # Toroidal wrap so the predator re-enters rather than flying away.
        self.pos[0] %= WIDTH
        self.pos[1] %= HEIGHT
        self.pos[2] %= DEPTH


# ── Flight response — per-bird flee force + per-frame driver ────────

def flee_force(boid, predator, danger=DANGER_RADIUS, strength=FLIGHT_STRENGTH):
    """Flight-response steering force for one bird — away from the predator,
    scaled by (1 − d/R_d) inside the danger radius, zero outside.

    Returns a numpy (3,) force clamped to MAX_FORCE.
    """
    diff = np.asarray(boid.pos, dtype=float) - np.asarray(predator.pos, dtype=float)
    d = float(np.linalg.norm(diff))
    if d >= danger or d < 1e-9:
        return np.zeros(3)
    force = (diff / d) * strength * (1.0 - d / danger)
    mag = float(np.linalg.norm(force))
    if mag > MAX_FORCE:
        force = force / mag * MAX_FORCE
    return force


def apply_predator(flock, predator):
    """Advance the predator toward the flock and apply the flight response to
    every threatened bird. Call once per frame between flock() and update()."""
    if not flock:
        return
    com = np.mean([b.pos for b in flock], axis=0)
    predator.update(com)
    for b in flock:
        f = flee_force(b, predator)
        if f.any():
            b.apply_force(f)
