"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D SIMULATION STATE — the headless update loop                      ║
╚══════════════════════════════════════════════════════════════════════╝

 The simulation's per-frame logic, factored out of main_3d.py so it can run
 (and be unit-tested) with no Pygame window and no GL context. `main_3d`
 owns input + rendering; `World` owns the model: the flock, the spatial
 grid, the scientific metrics, the behavioural-dynamics state (predator +
 roosting), and the one-frame `advance()` that steps them all.

 Nothing here imports pygame, moderngl or the renderer — it is pure
 numpy/scipy, so `test_simulation_3d.py` drives it directly.

 Dependencies:  flock_core, boid_3d, spatial_grid_3d, metrics_3d,
                correlation_time, predator_3d, ecology
──────────────────────────────────────────────────────────────────────
"""

from flock_core import WIDTH, HEIGHT, DEPTH, NUM_BOIDS, MAX_FORCE, Config
from boid_3d import Boid3D
from spatial_grid_3d import SpatialGrid3D
from metrics_3d import FlockMetrics3D
from correlation_time import CorrelationTimeTracker
from predator_3d import apply_predator
from ecology import roost_force


def _default_ext():
    """Behavioural-dynamics state (Goodenough): predator + roosting. A ground
    roost near the bottom of the volume; a fast 24h clock so the dusk cycle is
    visible in seconds when roosting is toggled on."""
    return {
        "predator": None,          # Predator3D when spawned (T key)
        "roosting": False,         # day/night roost cycle (K key)
        "hour": 12.0,              # time of day, 0–24
        "day": 15,                 # day-of-year (mid-January)
        "roost": (WIDTH * 0.5, HEIGHT * 0.5, DEPTH * 0.1),
    }


class World:
    """Everything the simulation needs to step one frame, minus I/O.

    Construct it, mutate ``config`` / ``ext`` as the input handler would, and
    call :meth:`advance` once per frame. ``flock``, ``metrics`` and ``corr``
    are read by the renderer / HUD.
    """

    def __init__(self, num_boids=NUM_BOIDS, config=None, verbose=False):
        self.config = config if config is not None else Config()
        self.config.num_boids = num_boids
        self.grid = SpatialGrid3D()
        self.flock = [Boid3D() for _ in range(num_boids)]
        self.metrics = FlockMetrics3D()          # Pearce-grounded observables
        self.corr = CorrelationTimeTracker()     # density autocorrelation τρ
        self.ext = _default_ext()
        self.frame = 0
        self.verbose = verbose

    # ── Flock-size edits (the +/-/R keys) ──────────────────────────────
    def apply_flock_edits(self, pending_remove, pending_add, pending_reset):
        """Grow, shrink or reset the flock. Removal always leaves at least one
        bird. Returns the leftover ``pending_remove`` (removal is capped to the
        flock size, so a large request is spread across frames); ``pending_add``
        and ``pending_reset`` are always consumed.
        """
        if pending_remove > 0:
            n = min(pending_remove, len(self.flock) - 1)
            if n > 0:
                del self.flock[len(self.flock) - n:]
                self.config.num_boids = len(self.flock)
                pending_remove -= n
                self._say(f"Removed {n} birds, now {self.config.num_boids}")

        if pending_add > 0:
            self.flock.extend(Boid3D() for _ in range(pending_add))
            self.config.num_boids = len(self.flock)
            self._say(f"Added {pending_add} birds, now {self.config.num_boids}")

        if pending_reset:
            self.config.num_boids = NUM_BOIDS
            self.flock = [Boid3D() for _ in range(self.config.num_boids)]
            self.grid = SpatialGrid3D()
            self.frame = 0
            self._say(f"Flock reset — {self.config.num_boids} birds")

        return pending_remove

    # ── One physics/metrics frame ──────────────────────────────────────
    def step(self, dt):
        """Advance the flock one frame: grid rebuild → flocking → behavioural
        dynamics (predator, roosting) → integration → metrics. Assumes any
        flock-size edits for this frame were already applied."""
        self.grid.rebuild(self.flock)
        for boid in self.flock:
            boid.flock(self.flock, self.config, self.grid)

        # Behavioural dynamics (Goodenough) — extra steering before integration.
        if self.ext["predator"] is not None:
            apply_predator(self.flock, self.ext["predator"])
        if self.ext["roosting"]:
            self.ext["hour"] = (self.ext["hour"] + dt) % 24.0   # fast day clock
            for boid in self.flock:
                boid.apply_force(roost_force(
                    boid.pos, self.ext["hour"], self.ext["roost"],
                    self.ext["day"], strength=MAX_FORCE))

        for boid in self.flock:
            boid.update()

        self.metrics.update(self.flock, self.config)
        self.corr.sample(self.flock)
        self.frame += 1

    def advance(self, dt, pending_remove=0, pending_add=0, pending_reset=False):
        """Apply this frame's flock-size edits, then step the physics. Returns
        the leftover ``(pending_remove, pending_add, pending_reset)`` — the
        exact tuple main_3d threads back into its loop state."""
        pending_remove = self.apply_flock_edits(
            pending_remove, pending_add, pending_reset)
        self.step(dt)
        return pending_remove, 0, False

    def _say(self, msg):
        if self.verbose:
            print(msg)
