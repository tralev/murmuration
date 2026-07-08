"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 10c — WANDER BEHAVIOUR                                     ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  companion TypeScript project `flockWander.ts`.

 When no attractor or threat is active, the flock explores space by
 drifting toward a shared *wander centre* — a single moving attractor
 that ALL birds are pulled toward.  This produces coordinated,
 organic-looking exploration ("swarm around a moving target") rather
 than independent per-bird jitter.

 The wander centre follows composite trigonometric noise on each axis,
 so it never repeats exactly, and its radius "breathes" via a radial
 pulse.  Both are deterministic functions of time — no RNG — so a
 given (time, config) always yields the same centre.

   t          = time × attractor_speed × wander_speed
   centre_dir = boundedUnitTravel(trig-noise per axis)
   radius     = attractor_radius × wander_radius × radial_pulse(t)
   centre     = domain_centre + centre_dir × radius

   bird wander force = unit(centre − bird.position) × wander_speed

 Pure functions (no pygame dependency for the maths) so the behaviour
 can be unit-tested in isolation.

 Usage:
   from extensions.wander import WanderConfig, flock_wander_center
──────────────────────────────────────────────────────────────────────
"""

import math

from flock_core import WIDTH, HEIGHT


class WanderConfig:
    """Tunable parameters for the flock-level wander behaviour.

    Defaults reproduce the companion project's `flockWander.ts` feel at
    the 1000 × 700 simulation scale.
    """

    __slots__ = ("wander_speed", "wander_radius", "attractor_speed",
                 "attractor_radius")

    def __init__(self, wander_speed=1.0, wander_radius=1.0,
                 attractor_speed=0.35, attractor_radius=280.0):
        self.wander_speed = wander_speed          # bird pull strength
        self.wander_radius = wander_radius        # radius multiplier
        self.attractor_speed = attractor_speed    # how fast centre moves
        self.attractor_radius = attractor_radius  # base excursion (px)


def radial_pulse(t: float) -> float:
    """Breathing radius multiplier in the range [0.72, 1.00].

    The nested sin(·+cos(·)) composition produces asymmetric, organic
    pulses rather than a plain sinusoid.
    """
    return 0.72 + 0.28 * (0.5 + 0.5 * math.sin(t * 0.41 + math.cos(t * 0.17)))


def _bounded_unit_travel(x: float, y: float):
    """Normalise a 2D vector to unit length, mapping the zero vector to
    (0, 0) so the wander centre collapses to the domain centre rather
    than dividing by zero."""
    mag = math.hypot(x, y)
    if mag < 1e-9:
        return 0.0, 0.0
    return x / mag, y / mag


def flock_wander_center(time: float, config: WanderConfig = None):
    """Compute the shared wander centre at *time* (seconds).

    Returns an (x, y) tuple in simulation coordinates.  Deterministic:
    the same (time, config) always yields the same centre, so callers
    should compute it once per frame and reuse it for every bird.
    """
    if config is None:
        config = WanderConfig()

    t = time * config.attractor_speed * config.wander_speed

    # ── Composite trig noise per axis (companion coefficients) ──
    dx = (math.cos(t * 0.53 + math.cos(t * 0.37)) * 0.84
          + math.sin(t * 0.71) * 0.32
          + math.cos(t * 1.13) * 0.18)
    dy = (math.sin(t * 0.47 + math.sin(t * 0.41)) * 0.72
          + math.cos(t * 0.59) * 0.28
          + math.sin(t * 0.83) * 0.22)

    ux, uy = _bounded_unit_travel(dx, dy)
    radius = config.attractor_radius * config.wander_radius * radial_pulse(t)

    cx = WIDTH / 2.0 + ux * radius
    cy = HEIGHT / 2.0 + uy * radius
    return cx, cy


def wander_force(bird_pos, wander_center, config: WanderConfig = None):
    """Per-bird steering force toward the shared wander centre.

    Parameters
    ----------
    bird_pos      : object with .x / .y (e.g. pygame.Vector2) or (x, y)
    wander_center : (x, y) from flock_wander_center()
    config        : WanderConfig (defaults if None)

    Returns
    -------
    (fx, fy) tuple — unit vector toward the centre scaled by wander_speed.
    """
    if config is None:
        config = WanderConfig()

    px = getattr(bird_pos, "x", None)
    if px is None:
        px, py = bird_pos[0], bird_pos[1]
    else:
        py = bird_pos.y

    dx = wander_center[0] - px
    dy = wander_center[1] - py
    ux, uy = _bounded_unit_travel(dx, dy)
    return ux * config.wander_speed, uy * config.wander_speed
