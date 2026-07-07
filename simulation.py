"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 9 — SIMULATION UPDATE  (per-frame flocking + physics)      ║
╚══════════════════════════════════════════════════════════════════════╝

 Per-frame simulation step extracted from alg2.py's main loop.
 Called by main() each frame when not paused.  Handles:

   1. Boid count changes (add/remove pending)
   2. Flock reset
   3. Spatial grid rebuild
   4. Per-bird flocking (steering forces via projection or spatial mode)
   5. Per-bird physics (Euler integration)
   6. Metrics computation (Θ, Θ', α, FPS)
   7. CSV logging

 Dependencies:  flock_core  (constants, Config, SpatialGrid)
                boid        (Boid class)
                metrics     (FlockMetrics)
                features    (ENABLE_GRID_OVERLAY)
──────────────────────────────────────────────────────────────────────
"""

import features
from flock_core import (
    VISUAL_RANGE, MODE_SPATIAL, LOG_EVERY, SpatialGrid,
)
from boid import Boid
from metrics import FlockMetrics


def update_frame(config, flock, metrics, grid, frame, clock,
                 pending_remove, pending_add, pending_reset,
                 focal_index, log_fid):
    """
    Execute one frame of simulation update: boid counts, reset, grid rebuild,
    flocking, physics, metrics, and CSV logging.

    Parameters
    ----------
    config         : Config — mutable; num_boids updated during add/remove
    flock          : list[Boid] — may be reassigned during reset
    metrics        : FlockMetrics — may be reassigned during reset;
                     .update() called each frame
    grid           : SpatialGrid — may be reassigned during reset;
                     .rebuild() called each frame
    frame          : int — current frame counter; may be reset to 0
    clock          : pygame.time.Clock — passed to metrics.update() and
                     used for CSV FPS logging
    pending_remove : int — birds to remove this frame
    pending_add    : int — birds to add this frame
    pending_reset  : bool — whether a reset was requested
    focal_index    : int | None — cleared if bird count changes affect it
    log_fid        : file | None — CSV log file handle

    Returns
    -------
    tuple of (flock, grid, metrics, frame, pending_remove, pending_add,
              pending_reset, focal_index)
    — updated values for reassigned objects and immutable types.
    """
    # ╔══════════════════════════════════════════════════════════╗
    # ║  BOID COUNT CHANGES  (+/- keys)                         ║
    # ╚══════════════════════════════════════════════════════════╝
    if pending_remove > 0:
        n_remove = min(pending_remove, len(flock) - 1)
        if n_remove > 0:
            for _ in range(n_remove):
                flock.pop()
            config.num_boids = len(flock)
            pending_remove -= n_remove
            print(f"Removed {n_remove} birds, now {config.num_boids}")
            if focal_index is not None and focal_index >= len(flock):
                focal_index = None
    if pending_add > 0:
        n_add = pending_add
        for _ in range(n_add):
            flock.append(Boid())
        config.num_boids = len(flock)
        pending_add = 0
        print(f"Added {n_add} birds, now {config.num_boids}")

    # ╔══════════════════════════════════════════════════════════╗
    # ║  RESET LOGIC  (triggered by 'r' key)                    ║
    # ╚══════════════════════════════════════════════════════════╝
    if pending_reset:
        flock = [Boid() for _ in range(config.num_boids)]
        metrics = FlockMetrics()
        grid = SpatialGrid(cell_size=VISUAL_RANGE)
        frame = 0
        pending_reset = False
        focal_index = None
        print(f"Flock reset — {config.num_boids} birds")

    # ╔══════════════════════════════════════════════════════════╗
    # ║  GRID REBUILD  (spatial hash grid)                      ║
    # ╚══════════════════════════════════════════════════════════╝
    if features.ENABLE_GRID_OVERLAY and (config.mode == MODE_SPATIAL or config.show_grid):
        grid.rebuild(flock)

    # ── Per-bird flocking: compute steering forces ────────────
    for boid in flock:
        boid.flock(flock, config, grid)

    # ── Per-bird physics: Euler integration ───────────────────
    for boid in flock:
        boid.update()

    # ── Metrics: Θ, Θ', α, FPS (EMA-smoothed) ─────────────────
    metrics.update(flock, clock, config)

    # ── CSV logging  (every LOG_EVERY frames) ─────────────────
    if features.ENABLE_CSV_LOGGING and log_fid is not None and frame % LOG_EVERY == 0:
        fps_val = clock.get_fps()
        n = len(flock)
        log_fid.write(
            f"{frame},{config.mode},{n},"
            f"{config.phi_p:.4f},{config.phi_a:.4f},"
            f"{config.phi_n:.4f},{config.sigma},"
            f"{metrics.internal_opacity:.4f},"
            f"{metrics.external_opacity:.4f},"
            f"{metrics.order_param:.4f},{fps_val:.1f}\n"
        )
        log_fid.flush()

    return (flock, grid, metrics, frame, pending_remove, pending_add,
            pending_reset, focal_index)
