"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 5 — ROOSTING / THERMOREGULATION                           ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  Goodenough et al. (2017); the roosting / thermoregulation
             hypothesis for why starlings gather at dusk.

 Murmurations are a pre-roost phenomenon: as dusk falls, birds are
 increasingly drawn to a fixed roost site (a reed bed, pier, or
 building), and the display collapses into a descending funnel at the
 roost.  Thermoregulation is one proposed driver — clustering at the
 roost conserves heat on cold winter nights.

 We model this as a time-of-day-gated attractor toward a roost point:

   pull(t) = roost_strength · dusk_factor(t)
   dusk_factor(t) rises from 0 (daytime) to 1 (nightfall) around dusk
   force = unit(roost − bird) · pull(t)

 dusk_factor is a smooth ramp centred on the dusk hour, so the flock
 wanders freely by day and is reeled into the roost as night falls —
 reproducing the characteristic end-of-display roosting descent.

 Pure functions — unit-testable without a simulation.

 Usage:
   from extensions.roosting import dusk_factor, roost_force
──────────────────────────────────────────────────────────────────────
"""

import math

from flock_core import WIDTH, HEIGHT


ROOST_STRENGTH_DEFAULT = 0.9    # peak attraction at full nightfall
DUSK_HOUR = 17.0                # centre of the dusk transition (24h clock)
DUSK_WIDTH = 1.5                # hours over which the ramp rises
DEFAULT_ROOST = (WIDTH * 0.5, HEIGHT * 0.85)   # roost near the bottom edge


def dusk_factor(hour: float, dusk_hour: float = DUSK_HOUR,
                width: float = DUSK_WIDTH) -> float:
    """Smooth 0→1 ramp modelling the onset of dusk.

    Returns ~0 well before *dusk_hour*, 0.5 at dusk_hour, and ~1 after
    nightfall.  A logistic ramp of the given *width* (hours).

    Parameters
    ----------
    hour      : time of day, 0..24
    dusk_hour : centre of the transition
    width     : hours over which it rises (smaller = sharper)

    Returns
    -------
    float in [0, 1].
    """
    # Logistic: 1 / (1 + e^{-(hour-dusk)/scale}); scale from width.
    scale = max(1e-6, width / 4.0)   # width ≈ the 10–90% span
    z = (hour - dusk_hour) / scale
    # Clamp to avoid overflow on extreme z.
    if z < -60:
        return 0.0
    if z > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def roost_force(bird_pos, hour, roost=DEFAULT_ROOST,
                strength=ROOST_STRENGTH_DEFAULT):
    """Attraction force toward the roost, scaled by how close it is to
    nightfall.

    Parameters
    ----------
    bird_pos : (x, y) / Vector2
    hour     : time of day, 0..24
    roost    : (x, y) roost site
    strength : peak pull magnitude at full nightfall

    Returns
    -------
    (fx, fy) tuple — zero by day, strongest after dusk.
    """
    px = getattr(bird_pos, "x", None)
    if px is None:
        px, py = bird_pos[0], bird_pos[1]
    else:
        py = bird_pos.y

    dx, dy = roost[0] - px, roost[1] - py
    d = math.hypot(dx, dy)
    if d < 1e-9:
        return 0.0, 0.0
    pull = strength * dusk_factor(hour)
    return dx / d * pull, dy / d * pull


def is_roosting_time(hour: float, threshold: float = 0.5) -> bool:
    """True once dusk_factor crosses *threshold* — the flock is being
    pulled to roost rather than freely displaying."""
    return dusk_factor(hour) >= threshold
