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
                metrics     (FlockMetrics — only when ENABLE_METRICS)
                features    (ENABLE_GRID_OVERLAY, ENABLE_METRICS,
                             ENABLE_CSV_LOGGING)
──────────────────────────────────────────────────────────────────────
"""

import features
import pygame
from statistics import mean
from flock_core import (
    VISUAL_RANGE, MODE_SPATIAL, LOG_EVERY, SpatialGrid,
)
from boid import Boid

# metrics.py (and its external_opacity dependency) never load when
# metrics are disabled — update_frame() then expects metrics=None.
if features.ENABLE_METRICS:
    from metrics import FlockMetrics
if features.ENABLE_WANDER:
    from extensions.wander import flock_wander_center, wander_force
if features.ENABLE_THREAT:
    from extensions.threat import flee_force
if features.ENABLE_MEDIUM_PRESETS:
    import random
if features.ENABLE_FLOCK_SHAPE:
    from extensions.flock_shape import analyze_shape
if features.ENABLE_LEADER:
    from extensions.leader import leader_force
if features.ENABLE_VACUOLE:
    from extensions.vacuole import vacuole_force
if features.ENABLE_SHELL:
    from extensions.shell_formation import shell_force
from extensions.flow_field import flow_force


def update_frame(config, flock, metrics, grid, frame, clock,
                 pending_remove, pending_add, pending_reset,
                 focal_index, log_fid, ext_state=None):
    """
    Execute one frame of simulation update: boid counts, reset, grid rebuild,
    flocking, physics, metrics, and CSV logging.

    Parameters
    ----------
    config         : Config — mutable; num_boids updated during add/remove
    flock          : list[Boid] — may be reassigned during reset
    metrics        : FlockMetrics | None — None when ENABLE_METRICS is
                     False; may be reassigned during reset;
                     .update() called each frame when present
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

    Parameters
    ----------
    ext_state       : dict | None — extension state (threat, wander, aq, medium, etc.)

    Returns
    -------
    tuple of (flock, grid, metrics, frame, pending_remove, pending_add,
              pending_reset, focal_index, ext_state)
    — updated values for reassigned objects and immutable types.
    """
    if ext_state is None:
        ext_state = {}
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
        metrics = FlockMetrics() if features.ENABLE_METRICS else None
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

    # ╔══════════════════════════════════════════════════════════╗
    # ║  EXTENSION: leader / attractor  (O key)                 ║
    # ╚══════════════════════════════════════════════════════════╝
    if features.ENABLE_LEADER and ext_state.get('leader_active'):
        cfg = ext_state.get('leader_cfg')
        ext_state['leader_time'] = ext_state.get('leader_time', 0.0) + 1.0 / max(clock.get_fps(), 1.0)
        for anchor in ext_state.get('leader_anchors', []):
            anchor.update(ext_state['leader_time'])
        for boid in flock:
            fx, fy = leader_force(boid.position, ext_state.get('leader_anchors', []), cfg)
            if fx != 0.0 or fy != 0.0:
                boid.apply_force(pygame.Vector2(fx, fy))

    # ╔══════════════════════════════════════════════════════════╗
    # ║  EXTENSION: flow field  (D key)                          ║
    # ╚══════════════════════════════════════════════════════════╝
    if features.ENABLE_FLOW_FIELD and ext_state.get('flow_active'):
        cfg = ext_state.get('flow_cfg')
        ext_state['flow_time'] = ext_state.get('flow_time', 0.0) + 1.0 / max(clock.get_fps(), 1.0)
        # Gust management
        if ext_state.get('flow_gust'):
            ext_state['flow_gust_time'] = ext_state.get('flow_gust_time', 0.0) + 1.0 / max(clock.get_fps(), 1.0)
            if ext_state['flow_gust_time'] >= cfg.gust_duration:
                ext_state['flow_gust'] = False
                ext_state['flow_gust_time'] = 0.0
        elif random.random() < cfg.gust_chance / max(clock.get_fps(), 1.0):
            ext_state['flow_gust'] = True
            ext_state['flow_gust_time'] = 0.0
        fx, fy = flow_force(cfg, ext_state['flow_time'],
                            ext_state.get('flow_gust', False),
                            ext_state.get('flow_gust_time', 0.0))
        for boid in flock:
            if fx != 0.0 or fy != 0.0:
                boid.apply_force(pygame.Vector2(fx, fy))

    # ╔══════════════════════════════════════════════════════════╗
    # ║  EXTENSION: vacuole formation  (E key)                 ║
    # ╚══════════════════════════════════════════════════════════╝
    if features.ENABLE_VACUOLE and ext_state.get('vacuole') is not None:
        vacuole = ext_state['vacuole']
        swarm_x = mean(b.position.x for b in flock)
        swarm_y = mean(b.position.y for b in flock)
        ext_state['vacuole_time'] = ext_state.get('vacuole_time', 0.0) + 1.0 / max(clock.get_fps(), 1.0)
        vacuole.update((swarm_x, swarm_y), ext_state['vacuole_time'])
        cfg = ext_state.get('vacuole_cfg')
        for boid in flock:
            fx, fy = vacuole_force(boid.position, vacuole.position(), cfg)
            if fx != 0.0 or fy != 0.0:
                boid.apply_force(pygame.Vector2(fx, fy))

    # ╔══════════════════════════════════════════════════════════╗
    # ║  EXTENSION: shell formation  (P key)                    ║
    # ╚══════════════════════════════════════════════════════════╝
    if features.ENABLE_SHELL and ext_state.get('shell_active'):
        cfg = ext_state.get('shell_cfg')
        ext_state['shell_time'] = ext_state.get('shell_time', 0.0) + 1.0 / max(clock.get_fps(), 1.0)
        swarm_x = mean(b.position.x for b in flock)
        swarm_y = mean(b.position.y for b in flock)
        assignments = ext_state.get('shell_assignments', [])
        t = ext_state['shell_time']
        for i, boid in enumerate(flock):
            if i < len(assignments):
                sidx, phase, direction = assignments[i]
                fx, fy = shell_force(
                    boid.position, (swarm_x, swarm_y),
                    sidx, phase, direction, t, cfg)
                if fx != 0.0 or fy != 0.0:
                    boid.apply_force(pygame.Vector2(fx, fy))

    # ║  EXTENSION: wander behaviour  (W key)                   ║
    # ╚══════════════════════════════════════════════════════════╝
    if features.ENABLE_WANDER and ext_state.get('wander_active'):
        ext_state['wander_time'] = ext_state.get('wander_time', 0.0) + 1.0 / max(clock.get_fps(), 1.0)
        centre = flock_wander_center(
            ext_state['wander_time'], ext_state.get('wander_cfg'))
        for boid in flock:
            fx, fy = wander_force(boid.position, centre, ext_state.get('wander_cfg'))
            boid.apply_force(pygame.Vector2(fx, fy))

    # ╔══════════════════════════════════════════════════════════╗
    # ║  EXTENSION: threat agent  (T key)                       ║
    # ╚══════════════════════════════════════════════════════════╝
    if features.ENABLE_THREAT and ext_state.get('threat') is not None:
        threat = ext_state['threat']
        swarm_x = mean(b.position.x for b in flock)
        swarm_y = mean(b.position.y for b in flock)
        threat.update((swarm_x, swarm_y))
        for boid in flock:
            fx, fy = flee_force(boid.position, threat.position())
            if fx != 0.0 or fy != 0.0:
                boid.apply_force(pygame.Vector2(fx, fy))

    # ╔══════════════════════════════════════════════════════════╗
    # ║  EXTENSION: medium presets  (N key)                     ║
    # ╚══════════════════════════════════════════════════════════╝
    if features.ENABLE_MEDIUM_PRESETS:
        medium = ext_state.get('medium')
        if medium is not None and medium.name != 'grid':
            dvx, dvy = medium.drift_velocity()
            for boid in flock:
                tax, tay = medium.turbulence_accel()
                boid.apply_force(pygame.Vector2(tax + dvx, tay + dvy))

    # ── Per-bird physics: Euler integration ───────────────────
    for boid in flock:
        boid.update()

    # ── Metrics: Θ, Θ', α, FPS (EMA-smoothed) ─────────────────
    if metrics is not None:
        metrics.update(flock, clock, config)

    # ── CSV logging  (every LOG_EVERY frames; rows contain
    #    metrics values, so a metrics object is required) ──────
    if (features.ENABLE_CSV_LOGGING and metrics is not None
            and log_fid is not None and frame % LOG_EVERY == 0):
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

    # ╔══════════════════════════════════════════════════════════╗
    # ║  EXTENSION: adaptive quality  (A key)                   ║
    # ╚══════════════════════════════════════════════════════════╝
    if features.ENABLE_ADAPTIVE_QUALITY:
        aq = ext_state.get('aq')
        if aq is not None and aq.enabled:
            fps_val = max(clock.get_fps(), 1.0)
            now_ms = pygame.time.get_ticks()
            aq.update(fps_val, now_ms, len(flock))
            ext_state['aq_label'] = f"AQ tier {aq.tier}"

    # ╔══════════════════════════════════════════════════════════╗
    # ║  EXTENSION: flock shape analysis  (Y key — per frame)   ║
    # ╚══════════════════════════════════════════════════════════╝
    if features.ENABLE_FLOCK_SHAPE:
        ext_state['flock_shape'] = analyze_shape(flock)

    return (flock, grid, metrics, frame, pending_remove, pending_add,
            pending_reset, focal_index, ext_state)
