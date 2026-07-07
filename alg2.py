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
   metrics.py         — FlockMetrics, external opacity, help overlay
   scenario_presets.py — educational preset configurations
   input_handler.py   — keyboard/mouse event processing
   simulation.py      — per-frame update (flocking, physics, metrics)

  See the companion files alg2.m (GNU Octave) and alg2.sce (Scilab)
  for ports to other computing environments.

  Runtime controls:  press 'h' for help overlay, 'esc' to quit.
"""

import pygame
import sys
import math
import os

import features

import flock_core
from flock_core import (
    WIDTH, HEIGHT, FPS, NUM_BOIDS, VISUAL_RANGE,
    LOG_FILE, LOG_EVERY, MODE_PROJECTION, MODE_SPATIAL,
    Config, SpatialGrid,
)
from boid import Boid
from metrics import FlockMetrics
from help_overlay import draw as _draw_help
import input_handler
import simulation


# ── Focal bird debug rendering ──────────────────────────────────────

def _draw_focal_bird_debug(screen, boid, font):
    """
    Render debug vectors and occlusion arcs for the focal bird.
    Shows: δ̂ (red), velocity (green), occlusion arcs (shaded wedges).
    """
    pos = boid.position
    r = 80  # radius of debug circle

    # ── Occlusion arcs (filled wedges for merged intervals) ─────
    if boid._debug_merged:
        for s, e in boid._debug_merged:
            points = [pos]
            steps = max(4, int((e - s) / 0.1))
            for i in range(steps + 1):
                a = s + (e - s) * i / steps
                points.append(pygame.Vector2(
                    pos.x + math.cos(a) * r,
                    pos.y + math.sin(a) * r,
                ))
            if len(points) > 2:
                surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                pygame.draw.polygon(surf, (255, 40, 40, 60), points)
                screen.blit(surf, (0, 0))

    # ── Debug circle ────────────────────────────────────────────
    pygame.draw.circle(screen, (60, 60, 80), (int(pos.x), int(pos.y)), r, 1)

    # ── δ̂ vector (red) ──────────────────────────────────────────
    if boid._debug_delta.length() > 0.001:
        end = pos + boid._debug_delta * r
        pygame.draw.line(screen, (255, 60, 60), pos, end, 2)
        perp = pygame.Vector2(-boid._debug_delta.y, boid._debug_delta.x) * 6
        tip = end
        pygame.draw.polygon(screen, (255, 60, 60), [
            tip,
            tip - boid._debug_delta * 12 + perp,
            tip - boid._debug_delta * 12 - perp,
        ])

    # ── Velocity vector (green) ──────────────────────────────────
    if boid.velocity.length() > 0.001:
        vdir = boid.velocity.normalize()
        vend = pos + vdir * r * 0.7
        pygame.draw.line(screen, (60, 255, 60), pos, vend, 2)

    # ── Highlight circle around focal bird ───────────────────────
    pygame.draw.circle(screen, (255, 255, 100),
                       (int(pos.x), int(pos.y)), 12, 2)

    # ── Label ───────────────────────────────────────────────────
    label = font.render("FOCAL BIRD  (click to change, F to clear)",
                        True, (255, 255, 100))
    screen.blit(label, (pos.x + 18, pos.y - 6))


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

    # ── CSV log file ─────────────────────────────────────────────
    log_fid = None
    if LOG_FILE is not None:
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
    metrics = FlockMetrics()
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

        # ── 3. RENDER ───────────────────────────────────────────
        screen.fill((20, 22, 30))

        if features.ENABLE_GRID_OVERLAY and config.mode == MODE_SPATIAL and config.show_grid:
            grid.draw(screen, font_help)

        for boid in flock:
            boid.draw(screen, config)

        if features.ENABLE_FOCAL_DEBUG and focal_index is not None and 0 <= focal_index < len(flock):
            _draw_focal_bird_debug(screen, flock[focal_index], font_debug)

        metrics.draw(screen, font_small, config, len(flock), preset_label)

        if config.show_help:
            _draw_help(screen, font_help)

        badge_text = "PROJECTION" if config.mode == MODE_PROJECTION else "SPATIAL"
        badge_color = (120, 180, 220) if config.mode == MODE_PROJECTION else (220, 180, 120)
        badge = font_small.render(badge_text, True, badge_color)
        screen.blit(badge, (WIDTH - badge.get_width() - 10, 10))

        boundary_text = "MARGIN" if flock_core.MARGIN_BOUNDARY else "TOROIDAL"
        boundary_color = (220, 140, 100) if flock_core.MARGIN_BOUNDARY else (100, 200, 140)
        boundary_badge = font_small.render(boundary_text, True, boundary_color)
        screen.blit(boundary_badge, (WIDTH - boundary_badge.get_width() - 10, 30))

        if paused:
            ptext = font_small.render(
                "PAUSED  (SPACE to resume, R to reset, ESC to quit)",
                True, (255, 200, 100))
            screen.blit(ptext, (WIDTH // 2 - 220, HEIGHT - 30))

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
