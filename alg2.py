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

 Runtime controls:  press 'h' for help overlay, 'esc' to quit.
"""

import pygame
import sys
import math
import os

import flock_core
from flock_core import (
    WIDTH, HEIGHT, FPS, NUM_BOIDS, VISUAL_RANGE,
    LOG_FILE, LOG_EVERY, MODE_PROJECTION, MODE_SPATIAL,
    Config, SpatialGrid,
)
import boid as boid_module
from boid import Boid
from metrics import FlockMetrics, _draw_help
from scenario_presets import apply_preset


def _get_preset_key(pygame_key):
    """Map a pygame key constant to a preset key (int or str).
    Returns None if the key is not a preset key."""
    import pygame
    if pygame.K_1 <= pygame_key <= pygame.K_5:
        return pygame_key - pygame.K_1 + 1
    if pygame.K_6 <= pygame_key <= pygame.K_9:
        return pygame_key - pygame.K_1 + 1
    if pygame_key == pygame.K_0:
        return 0
    key_map = {
        pygame.K_s: 's', pygame.K_l: 'l', pygame.K_i: 'i',
        pygame.K_v: 'v', pygame.K_k: 'k', pygame.K_q: 'q',
    }
    return key_map.get(pygame_key)


def _save_config(config):
    """Snapshot the mutable parts of a Config for later restoration."""
    return {
        'phi_p': config.phi_p,
        'phi_a': config.phi_a,
        'sigma': config.sigma,
        'mode': config.mode,
    }


def _restore_config(config, saved):
    """Restore a Config from a snapshot dict."""
    config.phi_p = saved['phi_p']
    config.phi_a = saved['phi_a']
    config.sigma = saved['sigma']
    config.mode = saved['mode']


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECTION 12 — MAIN LOOP                                             ║
# ╚══════════════════════════════════════════════════════════════════════╝
#  The main simulation loop runs at a target 60 FPS.  Each frame:
#
#    1. INPUT   — process Pygame events (keyboard, window close, mouse)
#    2. UPDATE  — if not paused:
#       a. Auto-compute φn
#       b. Apply pending boid count changes
#       c. Apply pending reset
#       d. Rebuild spatial grid
#       e. Per-bird flocking (steering forces)
#       f. Per-bird physics (Euler integration)
#       g. Compute metrics (Θ, Θ', α, FPS)
#       h. CSV logging (every LOG_EVERY frames)
#    3. RENDER  — clear screen, draw birds, metrics, grid, help, badge,
#                 focal bird debug view, preset label
#    4. FLIP    — present frame to display
# ──────────────────────────────────────────────────────────────────────

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
            # Draw filled arc for each occluded interval
            points = [pos]
            steps = max(4, int((e - s) / 0.1))
            for i in range(steps + 1):
                a = s + (e - s) * i / steps
                points.append(pygame.Vector2(
                    pos.x + math.cos(a) * r,
                    pos.y + math.sin(a) * r,
                ))
            if len(points) > 2:
                # Semi-transparent red fill for occluded regions
                surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                pygame.draw.polygon(surf, (255, 40, 40, 60), points)
                screen.blit(surf, (0, 0))

    # ── Debug circle ────────────────────────────────────────────
    pygame.draw.circle(screen, (60, 60, 80), (int(pos.x), int(pos.y)), r, 1)

    # ── δ̂ vector (red) ──────────────────────────────────────────
    if boid._debug_delta.length() > 0.001:
        end = pos + boid._debug_delta * r
        pygame.draw.line(screen, (255, 60, 60), pos, end, 2)
        # Arrowhead
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


def main():
    # ╔══════════════════════════════════════════════════════════════╗
    # ║  SECTION 2b — FIGURE SETUP  (Pygame window)                  ║
    # ╚══════════════════════════════════════════════════════════════╝
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(
        "Murmuration — M: toggle mode   B: toggle boundary   1-0,s,l,i,v,k,q: presets   H: help   ESC: quit"
    )

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  SECTION 2c — GRAPHICS SETUP  (clock, fonts)                 ║
    # ╚══════════════════════════════════════════════════════════════╝
    clock = pygame.time.Clock()
    font_small = pygame.font.Font(None, 18)
    font_help  = pygame.font.Font(None, 16)
    font_debug = pygame.font.Font(None, 14)

    config = Config()
    grid = SpatialGrid(cell_size=VISUAL_RANGE)

    # ── Open CSV log file ────────────────────────────────────────
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

    # ── Initialize flock ──────────────────────────────────────────
    flock = [Boid() for _ in range(config.num_boids)]
    metrics = FlockMetrics()
    frame = 0
    running = True
    paused = False
    pending_reset = False
    pending_add = 0
    pending_remove = 0
    preset_label = ""          # on-screen preset name
    focal_index = None         # index of selected focal bird (None = off)
    last_preset_key = None     # toggle: last preset key (second press restores)
    saved_config = None        # toggle: snapshot before current preset

    # ═══════════════════════════════════════════════════════════════
    #  MAIN FRAME LOOP
    # ═══════════════════════════════════════════════════════════════
    while running:
        dt = clock.tick(FPS)

        # ╔══════════════════════════════════════════════════════════╗
        # ║  SECTION 11 — INPUT HANDLING  (Pygame events)           ║
        # ╚══════════════════════════════════════════════════════════╝
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                key = event.key

                # ── Scenario presets  (toggle: same key = restore) ──
                preset_key = _get_preset_key(key)
                if preset_key is not None:
                    if (last_preset_key == preset_key
                            and saved_config is not None):
                        # Second press → restore previous settings
                        _restore_config(config, saved_config)
                        preset_label = ""
                        last_preset_key = None
                        saved_config = None
                        print(f"[PRESET {preset_key}] Toggled off "
                              f"— restored previous settings")
                    else:
                        saved_config = _save_config(config)
                        preset_label = apply_preset(config, preset_key)
                        last_preset_key = preset_key

                # ── Mode toggle  (m) ─────────────────────────────
                elif key == pygame.K_m:
                    config.mode = 1 - config.mode
                    mode_name = "PROJECTION" if config.mode == MODE_PROJECTION else "SPATIAL"
                    print(f"[MODE] Switched to {mode_name}")
                    last_preset_key = None   # invalidate preset toggle
                    saved_config = None

                # ── φp  (up/down arrows) ─────────────────────────
                elif key == pygame.K_UP:
                    config.phi_p = min(1.0, config.phi_p + 0.01)
                    preset_label = ""
                    last_preset_key = None
                    saved_config = None
                elif key == pygame.K_DOWN:
                    config.phi_p = max(0.0, config.phi_p - 0.01)
                    preset_label = ""
                    last_preset_key = None
                    saved_config = None

                # ── φa  (left/right arrows) ──────────────────────
                elif key == pygame.K_RIGHT:
                    config.phi_a = min(1.0, config.phi_a + 0.01)
                    preset_label = ""
                    last_preset_key = None
                    saved_config = None
                elif key == pygame.K_LEFT:
                    config.phi_a = max(0.0, config.phi_a - 0.01)
                    preset_label = ""
                    last_preset_key = None
                    saved_config = None

                # ── σ  ([ / ] brackets) ──────────────────────────
                elif key == pygame.K_RIGHTBRACKET:
                    config.sigma = min(50, config.sigma + 1)
                    preset_label = ""
                    last_preset_key = None
                    saved_config = None
                elif key == pygame.K_LEFTBRACKET:
                    config.sigma = max(1,  config.sigma - 1)
                    preset_label = ""
                    last_preset_key = None
                    saved_config = None

                # ── Boid count  (+ / -) ──────────────────────────
                elif key == pygame.K_EQUALS or key == pygame.K_PLUS:
                    pending_add = min(pending_add + 10, 200)
                    print("Adding 10 birds (pending)")
                elif key == pygame.K_MINUS:
                    pending_remove += 10
                    print("Removing 10 birds (pending)")

                # ── Focal bird  (f) ──────────────────────────────
                elif key == pygame.K_f:
                    if focal_index is not None:
                        focal_index = None
                        print("Focal bird: OFF")
                    elif flock:
                        focal_index = 0
                        print(f"Focal bird: #{focal_index}  (click to change, F to clear)")

                # ── Visual toggles  (g, h) ────────────────────────
                elif key == pygame.K_g:
                    config.show_grid = not config.show_grid
                elif key == pygame.K_h:
                    config.show_help = not config.show_help

                # ── Boundary mode toggle  (b) ─────────────────────
                elif key == pygame.K_b:
                    flock_core.MARGIN_BOUNDARY = not flock_core.MARGIN_BOUNDARY
                    boid_module.MARGIN_BOUNDARY = flock_core.MARGIN_BOUNDARY
                    mode_name = "MARGIN" if flock_core.MARGIN_BOUNDARY else "TOROIDAL"
                    print(f"[BOUNDARY] Switched to {mode_name} wrap")

                # ── Simulation control  (space, r, esc) ───────────
                elif key == pygame.K_SPACE:
                    paused = not paused
                elif key == pygame.K_r:
                    pending_reset = True
                    last_preset_key = None   # reset clears toggle state
                    saved_config = None
                    print("Resetting flock...")
                elif key == pygame.K_ESCAPE:
                    running = False

            # ── Mouse click: select focal bird ───────────────────
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                best_dist = float("inf")
                best_idx = None
                for i, b in enumerate(flock):
                    d = (b.position.x - mx) ** 2 + (b.position.y - my) ** 2
                    if d < best_dist:
                        best_dist = d
                        best_idx = i
                if best_dist < 30 * 30:  # within 30px
                    focal_index = best_idx
                    print(f"Focal bird: #{focal_index}")

        # ───────────────────────────────────────────────────────────
        #  UPDATE  — flocking physics + metrics
        # ───────────────────────────────────────────────────────────
        if not paused:
            # ╔══════════════════════════════════════════════════════╗
            # ║  SECTION 9a — AUTO-COMPUTE φn                        ║
            # ╚══════════════════════════════════════════════════════╝
            #  φn = max(0, 1 − φp − φa) — auto-computed by
            #  Config.phi_n @property.

            # ╔══════════════════════════════════════════════════════╗
            # ║  SECTION 9c — BOID COUNT CHANGES  (+/- keys)        ║
            # ╚══════════════════════════════════════════════════════╝
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

            # ╔══════════════════════════════════════════════════════╗
            # ║  SECTION 9b — RESET LOGIC  (triggered by 'r' key)   ║
            # ╚══════════════════════════════════════════════════════╝
            if pending_reset:
                flock = [Boid() for _ in range(config.num_boids)]
                metrics = FlockMetrics()
                grid = SpatialGrid(cell_size=VISUAL_RANGE)
                frame = 0
                pending_reset = False
                focal_index = None
                print(f"Flock reset — {config.num_boids} birds")

            # ╔══════════════════════════════════════════════════════╗
            # ║  SECTION 9d — GRID REBUILD  (spatial hash grid)     ║
            # ╚══════════════════════════════════════════════════════╝
            if config.mode == MODE_SPATIAL or config.show_grid:
                grid.rebuild(flock)

            # ── Per-bird flocking: compute steering forces ────────
            for boid in flock:
                boid.flock(flock, config, grid)

            # ── Per-bird physics: Euler integration ───────────────
            for boid in flock:
                boid.update()

            # ── Metrics: Θ, Θ', α, FPS (EMA-smoothed) ─────────────
            metrics.update(flock, clock, config)

            # ── CSV logging  (every LOG_EVERY frames) ─────────────
            if log_fid is not None and frame % LOG_EVERY == 0:
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

        # ───────────────────────────────────────────────────────────
        #  RENDER
        # ───────────────────────────────────────────────────────────
        screen.fill((20, 22, 30))

        if config.mode == MODE_SPATIAL and config.show_grid:
            grid.draw(screen, font_help)

        for boid in flock:
            boid.draw(screen, config)

        # ── Focal bird debug view ─────────────────────────────────
        if focal_index is not None and 0 <= focal_index < len(flock):
            _draw_focal_bird_debug(screen, flock[focal_index], font_debug)

        metrics.draw(screen, font_small, config, len(flock), preset_label)

        if config.show_help:
            _draw_help(screen, font_help)

        badge_text = "PROJECTION" if config.mode == MODE_PROJECTION else "SPATIAL"
        badge_color = (120, 180, 220) if config.mode == MODE_PROJECTION else (220, 180, 120)
        badge = font_small.render(badge_text, True, badge_color)
        screen.blit(badge, (WIDTH - badge.get_width() - 10, 10))

        # ── Boundary mode badge ───────────────────────────────────
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

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  SECTION 13 — SHUTDOWN                                      ║
    # ╚══════════════════════════════════════════════════════════════╝
    if log_fid is not None:
        log_fid.close()
        print(f"Metrics saved to {LOG_FILE}")
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
