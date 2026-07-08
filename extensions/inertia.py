"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 8 — INERTIA SMOOTHING                                      ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  companion TypeScript project (inertia default 0.84);
             classic Reynolds "steer = desired − velocity" smoothing.

 Real birds cannot change heading instantaneously — momentum carries
 them.  Inertia smoothing blends each bird's current velocity toward
 its newly-desired velocity instead of snapping to it:

   v(t+1) = inertia · v(t) + (1 − inertia) · v_desired

 inertia = 0    → no smoothing (instant turns, twitchy)
 inertia = 0.84 → companion default (smooth, momentum-like)
 inertia → 1    → frozen heading (ignores desired)

 The blended vector is then re-scaled to the bird's cruising speed so
 smoothing changes *direction response*, not speed.

 Pure functions on (x, y) tuples or pygame.Vector2 — unit-testable
 without a running simulation.

 Usage:
   from extensions.inertia import blend_inertia, INERTIA_DEFAULT
──────────────────────────────────────────────────────────────────────
"""

import math

from flock_core import V0


INERTIA_DEFAULT = 0.84   # companion default — smooth, momentum-like turns


def _xy(v):
    x = getattr(v, "x", None)
    if x is not None:
        return v.x, v.y
    return v[0], v[1]


def blend_inertia(velocity, desired, inertia=INERTIA_DEFAULT, speed=V0):
    """Blend *velocity* toward *desired* under an inertia coefficient.

        out = inertia · velocity + (1 − inertia) · desired
        out re-scaled to *speed* (so only heading is smoothed)

    Parameters
    ----------
    velocity : current velocity (x, y) / Vector2
    desired  : target velocity (x, y) / Vector2
    inertia  : blend weight in [0, 1] (0 = snap, 1 = frozen)
    speed    : cruising speed to renormalise to (0 → keep blended length)

    Returns
    -------
    (x, y) tuple — the smoothed velocity.
    """
    inertia = max(0.0, min(1.0, inertia))
    vx, vy = _xy(velocity)
    dx, dy = _xy(desired)

    bx = inertia * vx + (1.0 - inertia) * dx
    by = inertia * vy + (1.0 - inertia) * dy

    if speed <= 0.0:
        return bx, by
    mag = math.hypot(bx, by)
    if mag < 1e-9:
        return vx, vy   # degenerate — keep prior heading
    return bx / mag * speed, by / mag * speed


def turn_rate(velocity, desired, inertia=INERTIA_DEFAULT):
    """Angle (radians) between the current and blended heading — how far
    the bird actually turns this frame under the given inertia.  Useful
    for verifying that higher inertia yields smaller per-frame turns.
    """
    vx, vy = _xy(velocity)
    bx, by = blend_inertia(velocity, desired, inertia, speed=0.0)
    a0 = math.atan2(vy, vx)
    a1 = math.atan2(by, bx)
    d = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    return abs(d)
