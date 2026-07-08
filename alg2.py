"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 1 — HEADER & OVERVIEW                                      ║
╚══════════════════════════════════════════════════════════════════════╝

 alg2.py — Dual-Mode Bird Flock Simulation (Python / Pygame)
 ─────────────────────────────────────────────────────────
 Based on:  Pearce, Miller, Rowlands & Turner (2014)
            "Role of projection in the control of bird flocks"
            PNAS 111(29), 10422–10426.
            DOI: 10.1073/pnas.1402202111

 Two switchable flocking modes (press 'm' to toggle):
 ─────────────────────────────────────────────────────
   MODE 0 — PROJECTION   Hybrid projection model (Pearce et al., Eq. 3)
   MODE 1 — SPATIAL      Topological Reynolds boids (Reynolds 1987)

 Entry point — imports simulation logic from:
   occlusion_geom.py  — angular interval utilities (pure math)
   flock_core.py      — constants, Config, SpatialGrid
   boid.py            — Boid agent with flocking logic
   boid_render.py     — 2D bird/trail drawing
   hud.py             — status badges and paused banner
   metrics.py         — FlockMetrics + external opacity  (flag-gated)
   help_overlay.py    — H-key help text                  (flag-gated)
   focal_debug.py     — focal-bird debug view            (flag-gated)
   scenario_presets.py — educational preset configurations
   input_handler.py   — keyboard/mouse event processing
   simulation.py      — per-frame update (flocking, physics, metrics)

 Modules for disabled features are never imported — set flags in
 features.py to run any subset (see features.py for the full list).

  See the companion files alg2.m (GNU Octave) and alg2.sce (Scilab)
  for ports to other computing environments.

  Runtime controls:  press 'h' for help overlay, 'esc' to quit.
"""

import pygame
import sys
import os

import features

from flock_core import (
    WIDTH, HEIGHT, FPS, NUM_BOIDS, VISUAL_RANGE,
    LOG_FILE, LOG_EVERY, MODE_PROJECTION, MODE_SPATIAL,
    Config, SpatialGrid,
)
from boid import Boid
import boid_render
import hud
import input_handler
import simulation

# ── Flag-gated imports — disabled features never load their module ──
if features.ENABLE_METRICS:
    from metrics import FlockMetrics
if features.ENABLE_HELP_OVERLAY:
    from help_overlay import draw as _draw_help
if features.ENABLE_FOCAL_DEBUG:
    from focal_debug import draw as _draw_focal_debug
if features.ENABLE_PRESETS:
    from scenario_presets import PRESETS as _PRESETS


# ═══════════════════════════════════════════════════════════════════════
#  MAIN — pure orchestrator: setup → frame loop (input→update→render)
# ═══════════════════════════════════════════════════════════════════════

def main():
    # ── Setup ────────────────────────────────────────────────────
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(
        "Murmuration — M: toggle mode   B: toggle boundary   "
        "1-0,s,l,i,v,k,q: presets   H: help   ESC: quit"
    )

    clock = pygame.time.Clock()
    font_small = pygame.font.Font(None, 18)
    font_help  = pygame.font.Font(None, 16)
    font_debug = pygame.font.Font(None, 14)

    config = Config()
    grid = SpatialGrid(cell_size=VISUAL_RANGE)

    # ── Single-model build: start in the enabled mode ────────────
    if not features.ENABLE_PROJECTION_MODE:
        config.mode = MODE_SPATIAL
    elif not features.ENABLE_SPATIAL_MODE:
        config.mode = MODE_PROJECTION

    # ── CSV log file (needs ENABLE_CSV_LOGGING + ENABLE_METRICS,
    #    since every row contains metrics values) ─────────────────
    log_fid = None
    if (features.ENABLE_CSV_LOGGING and features.ENABLE_METRICS
            and LOG_FILE is not None):
        try:
            os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)
            log_fid = open(LOG_FILE, "w")
            log_fid.write(
                "frame,mode,num_boids,phi_p,phi_a,phi_n,"
                "sigma,theta,theta_ext,alpha,fps\n"
            )
            print(f"Logging metrics to {LOG_FILE} every {LOG_EVERY} frames")
        except OSError as e:
            print(f"WARNING: could not open {LOG_FILE} for writing: {e}")
            log_fid = None

    # ── Initial state ────────────────────────────────────────────
    flock = [Boid() for _ in range(config.num_boids)]
    metrics = FlockMetrics() if features.ENABLE_METRICS else None
    frame = 0
    running = True
    paused = False
    pending_reset = False
    pending_add = 0
    pending_remove = 0
    preset_label = ""
    focal_index = None
    last_preset_key = None
    saved_config = None

    # ══════════════════════════════════════════════════════════════
    #  MAIN FRAME LOOP
    # ══════════════════════════════════════════════════════════════
    while running:
        dt = clock.tick(FPS)

        # ── 1. INPUT  (→ input_handler.py) ──────────────────────
        (running, paused, pending_reset, pending_add, pending_remove,
         focal_index, last_preset_key, saved_config, preset_label) = \
            input_handler.handle_events(
                config, flock, running, paused, pending_reset,
                pending_add, pending_remove, focal_index,
                last_preset_key, saved_config, preset_label)

        # ── 2. UPDATE  (→ simulation.py) ────────────────────────
        if not paused:
            (flock, grid, metrics, frame, pending_remove, pending_add,
             pending_reset, focal_index) = \
                simulation.update_frame(
                    config, flock, metrics, grid, frame, clock,
                    pending_remove, pending_add, pending_reset,
                    focal_index, log_fid)

        # ── 3. RENDER  (→ boid_render.py, hud.py, overlays) ─────
        screen.fill((20, 22, 30))

        if features.ENABLE_GRID_OVERLAY and config.mode == MODE_SPATIAL and config.show_grid:
            grid.draw(screen, font_help)

        for boid in flock:
            boid_render.draw_boid(screen, boid, config)

        if features.ENABLE_FOCAL_DEBUG and focal_index is not None and 0 <= focal_index < len(flock):
            _draw_focal_debug(screen, flock[focal_index], font_debug)

        if metrics is not None:
            metrics.draw(screen, font_small, config, len(flock), preset_label)

        if features.ENABLE_HELP_OVERLAY and config.show_help:
            _draw_help(screen, font_help)

        # ── Preset tooltip: active preset's description ──────────
        if (features.ENABLE_PRESETS and preset_label
                and last_preset_key is not None):
            _desc = _PRESETS.get(last_preset_key, {}).get("description", "")
            hud.draw_preset_tooltip(screen, font_help, _desc)

        hud.draw_badges(screen, font_small, config)
        if paused:
            hud.draw_paused_banner(screen, font_small)

        frame += 1
        pygame.display.flip()

    # ── Shutdown ─────────────────────────────────────────────────
    if log_fid is not None:
        log_fid.close()
        print(f"Metrics saved to {LOG_FILE}")
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
