"""
╔══════════════════════════════════════════════════════════════════════╗
║  EXTENDED SIMULATION — Roadmap Extensions Entry Point               ║
╚══════════════════════════════════════════════════════════════════════╝

 extended_simulation.py — Full murmuration simulation with all
 roadmap extensions enabled.

 Implements:
   1a — Direct velocity setting (Pearce et al. Eq. 2–3, no steering)
   1b — Multi-viewpoint external opacity (K=12 viewpoints)
   1c — Correlation time τᵨ (Graham scan convex hull + autocorrelation)
   2a — Steric repulsion (short-range 1/r² repulsive force)
   2b — Blind angles (blind sector behind each bird, default β=60°)
   2d — Anisotropic bodies (elliptical birds, a:b=2:1)
   3a — Predator agent (peregrine falcon / sparrowhawk)
   3b — Spatial optimization (chunk-based far-field approximation)

 Run:  python -m extensions.extended_simulation
       python extensions/extended_simulation.py

 Based on alg2.py but uses PredatorBoid (the full extension chain)
 instead of the base Boid class. Original source files are unchanged.
──────────────────────────────────────────────────────────────────────
"""

import pygame
import sys
import math
import os

from flock_core import (
    WIDTH, HEIGHT, FPS, NUM_BOIDS, VISUAL_RANGE,
    LOG_FILE, LOG_EVERY, MODE_PROJECTION, MODE_SPATIAL,
    Config, SpatialGrid,
)
from extensions.predator import Predator, PredatorBoid
from extensions.spatial_optimization import SpatialChunker
from extensions.blind_angles import BLIND_ANGLE
from extensions.steric_repulsion import PHI_STERIC
from extensions.multi_viewpoint_opacity import FlockMetricsExtended, K_VIEWPOINTS
from extensions.correlation_time import CorrelationTimeTracker
from scenario_presets import apply_preset


# ══════════════════════════════════════════════════════════════════════
#  Draw predator danger radius around focal bird
# ══════════════════════════════════════════════════════════════════════

def _draw_focal_bird_debug(screen, boid, font, predator=None):
    """
    Render debug vectors and occlusion arcs for the focal bird.
    Also shows predator danger information if present.
    """
    pos = boid.position
    r = 80

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

    # ── Blind sector (grey wedge behind bird) ────────────────────
    if boid.velocity.length_squared() > 0.001:
        heading = math.atan2(boid.velocity.y, boid.velocity.x)
        blind_centre = heading + math.pi
        b_start = blind_centre - BLIND_ANGLE / 2
        b_end = blind_centre + BLIND_ANGLE / 2
        b_points = [pos]
        b_steps = max(4, int(BLIND_ANGLE / 0.1))
        for i in range(b_steps + 1):
            a = b_start + BLIND_ANGLE * i / b_steps
            b_points.append(pygame.Vector2(
                pos.x + math.cos(a) * r * 0.5,
                pos.y + math.sin(a) * r * 0.5,
            ))
        if len(b_points) > 2:
            surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(surf, (100, 100, 100, 80), b_points)
            screen.blit(surf, (0, 0))

    # ── Highlight circle around focal bird ───────────────────────
    pygame.draw.circle(screen, (255, 255, 100),
                       (int(pos.x), int(pos.y)), 12, 2)

    # ── Label ───────────────────────────────────────────────────
    label = font.render("FOCAL BIRD  (click to change, F to clear)",
                        True, (255, 255, 100))
    screen.blit(label, (pos.x + 18, pos.y - 6))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(
        "Murmuration EXTENDED — M:toggle 1-5:presets P:predator H:help ESC:quit"
    )

    clock = pygame.time.Clock()
    font_small = pygame.font.Font(None, 18)
    font_help  = pygame.font.Font(None, 16)
    font_debug = pygame.font.Font(None, 14)

    config = Config()
    grid = SpatialGrid(cell_size=VISUAL_RANGE)

    # ── Open CSV log file ────────────────────────────────────────
    log_fid = None
    if LOG_FILE is not None:
        ext_log = LOG_FILE.replace(".csv", "_extended.csv")
        try:
            os.makedirs(os.path.dirname(ext_log) or ".", exist_ok=True)
            log_fid = open(ext_log, "w")
            log_fid.write(
                "frame,mode,num_boids,phi_p,phi_a,phi_n,"
                "sigma,theta,theta_ext,alpha,fps,"
                "phi_steric,blind_angle,tau,density,predator_active,"
                "power,ang_mom\n"
            )
            print(f"Logging metrics to {ext_log} every {LOG_EVERY} frames")
        except OSError as e:
            print(f"WARNING: could not open {ext_log}: {e}")
            log_fid = None

    # ── Initialize extended flock ─────────────────────────────────
    flock = [PredatorBoid() for _ in range(config.num_boids)]
    predator = None   # predator starts inactive — press 'p' to spawn
    metrics = FlockMetricsExtended()
    corr_tracker = CorrelationTimeTracker()
    chunker = SpatialChunker()
    frame = 0
    running = True
    paused = False
    pending_reset = False
    pending_add = 0
    pending_remove = 0
    preset_label = ""
    focal_index = None
    predator_active = False

    ext_info_line = ""   # cached extension info string for display

    while running:
        dt = clock.tick(FPS)

        # ═══════════════════════════════════════════════════════════
        #  INPUT HANDLING
        # ═══════════════════════════════════════════════════════════
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                key = event.key

                # ── Scenario presets (1–5) ──────────────────────
                if pygame.K_1 <= key <= pygame.K_5:
                    preset_label = apply_preset(config, key - pygame.K_1 + 1)

                # ── Mode toggle (m) ─────────────────────────────
                elif key == pygame.K_m:
                    config.mode = 1 - config.mode
                    mode_name = "PROJECTION" if config.mode == MODE_PROJECTION else "SPATIAL"
                    print(f"[MODE] Switched to {mode_name}")

                # ── φp (up/down arrows) ─────────────────────────
                elif key == pygame.K_UP:
                    config.phi_p = min(1.0, config.phi_p + 0.01)
                    preset_label = ""
                elif key == pygame.K_DOWN:
                    config.phi_p = max(0.0, config.phi_p - 0.01)
                    preset_label = ""

                # ── φa (left/right arrows) ──────────────────────
                elif key == pygame.K_RIGHT:
                    config.phi_a = min(1.0, config.phi_a + 0.01)
                    preset_label = ""
                elif key == pygame.K_LEFT:
                    config.phi_a = max(0.0, config.phi_a - 0.01)
                    preset_label = ""

                # ── σ ([ / ]) ───────────────────────────────────
                elif key == pygame.K_RIGHTBRACKET:
                    config.sigma = min(50, config.sigma + 1)
                    preset_label = ""
                elif key == pygame.K_LEFTBRACKET:
                    config.sigma = max(1, config.sigma - 1)
                    preset_label = ""

                # ── Boid count (+ / -) ──────────────────────────
                elif key == pygame.K_EQUALS or key == pygame.K_PLUS:
                    pending_add = min(pending_add + 10, 200)
                elif key == pygame.K_MINUS:
                    pending_remove += 10

                # ── Focal bird (f) ──────────────────────────────
                elif key == pygame.K_f:
                    if focal_index is not None:
                        focal_index = None
                        print("Focal bird: OFF")
                    elif flock:
                        focal_index = 0
                        print(f"Focal bird: #{focal_index}")

                # ── Predator toggle (p) ─────────────────────────
                elif key == pygame.K_p:
                    if predator is None:
                        predator = Predator()
                        predator_active = True
                        print("Predator SPAWNED — birds will flee!")
                    else:
                        predator = None
                        predator_active = False
                        print("Predator REMOVED")

                # ── Visual toggles (g, h) ────────────────────────
                elif key == pygame.K_g:
                    config.show_grid = not config.show_grid
                elif key == pygame.K_h:
                    config.show_help = not config.show_help

                # ── Simulation control (space, r, esc) ───────────
                elif key == pygame.K_SPACE:
                    paused = not paused
                elif key == pygame.K_r:
                    pending_reset = True
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
                if best_dist < 30 * 30:
                    focal_index = best_idx
                    print(f"Focal bird: #{focal_index}")

        # ═══════════════════════════════════════════════════════════
        #  UPDATE
        # ═══════════════════════════════════════════════════════════
        if not paused:
            # ── Boid count changes ───────────────────────────────
            if pending_remove > 0:
                n_remove = min(pending_remove, len(flock) - 1)
                if n_remove > 0:
                    for _ in range(n_remove):
                        flock.pop()
                    config.num_boids = len(flock)
                    pending_remove -= n_remove
                    if focal_index is not None and focal_index >= len(flock):
                        focal_index = None
            if pending_add > 0:
                for _ in range(pending_add):
                    flock.append(PredatorBoid())
                config.num_boids = len(flock)
                pending_add = 0

            # ── Reset logic ──────────────────────────────────────
            if pending_reset:
                flock = [PredatorBoid() for _ in range(config.num_boids)]
                predator = None
                predator_active = False
                metrics = FlockMetricsExtended()
                corr_tracker = CorrelationTimeTracker()
                chunker = SpatialChunker()
                grid = SpatialGrid(cell_size=VISUAL_RANGE)
                frame = 0
                pending_reset = False
                focal_index = None

            # ── Grid rebuild ─────────────────────────────────────
            if config.mode == MODE_SPATIAL or config.show_grid:
                grid.rebuild(flock)

            # ── Spatial chunker rebuild (for optimized occlusion) ──
            if config.mode == MODE_PROJECTION:
                chunker.rebuild(flock)
                for boid in flock:
                    boid._chunker = chunker

            # ── Per-bird flocking: compute steering forces ────────
            for boid in flock:
                boid.flock(flock, config, grid)

            # ── Predator response (flight from danger) ────────────
            if predator_active and predator is not None:
                for boid in flock:
                    boid.apply_predator_response(predator)

            # ── Predator update ───────────────────────────────────
            if predator_active and predator is not None:
                predator.update(flock)

            # ── Metrics (must run BEFORE physics — reads acceleration
            #     before boid.update() zeros it) ────────────────────
            metrics.update(flock, clock, config)

            # ── Per-bird physics ─────────────────────────────────
            for boid in flock:
                boid.update()

            # ── Correlation time τᵨ ─────────────────────────────
            corr_tracker.sample(flock, frame)

            # ── Extension info line (updated each frame) ─────────
            tau_str = f"τᵨ={corr_tracker.tau:.0f}f" if corr_tracker.tau > 0 else "τᵨ=…"
            ext_info_line = (
                f"EXT: DirVel  φ_s={PHI_STERIC:.2f}  β={math.degrees(BLIND_ANGLE):.0f}°  "
                f"Pred={'ON' if predator_active else 'OFF'}  {tau_str}  ρ={corr_tracker.latest_density:.4f}  "
                f"P={metrics.power:.1f}  L={metrics.angular_momentum:.0f}"
            )

            # ── CSV logging ───────────────────────────────────────
            if log_fid is not None and frame % LOG_EVERY == 0:
                fps_val = clock.get_fps()
                n = len(flock)
                log_fid.write(
                    f"{frame},{config.mode},{n},"
                    f"{config.phi_p:.4f},{config.phi_a:.4f},"
                    f"{config.phi_n:.4f},{config.sigma},"
                    f"{metrics.internal_opacity:.4f},"
                    f"{metrics.external_opacity:.4f},"
                    f"{metrics.order_param:.4f},{fps_val:.1f},"
                    f"{PHI_STERIC:.4f},{BLIND_ANGLE:.4f},"
                    f"{corr_tracker.tau:.4f},{corr_tracker.latest_density:.6f},"
                    f"{1 if predator_active else 0},"
                    f"{metrics.power:.4f},{metrics.angular_momentum:.4f}\n"
                )
                log_fid.flush()

        # ═══════════════════════════════════════════════════════════
        #  RENDER
        # ═══════════════════════════════════════════════════════════
        screen.fill((20, 22, 30))

        if config.mode == MODE_SPATIAL and config.show_grid:
            grid.draw(screen, font_help)

        for boid in flock:
            boid.draw(screen, config)

        # ── Predator ──────────────────────────────────────────────
        if predator_active and predator is not None:
            predator.draw(screen)

        # ── Focal bird debug view ─────────────────────────────────
        if focal_index is not None and 0 <= focal_index < len(flock):
            _draw_focal_bird_debug(screen, flock[focal_index], font_debug,
                                   predator if predator_active else None)

        metrics.draw(screen, font_small, config, len(flock), preset_label)

        # ── Extension info line ───────────────────────────────────
        ext_surf = font_small.render(ext_info_line, True, (180, 160, 220))
        screen.blit(ext_surf, (WIDTH // 2 - ext_surf.get_width() // 2, HEIGHT - 18))

        if config.show_help:
            _draw_help_extended(screen, font_help)

        # ── Mode badge ───────────────────────────────────────────
        badge_text = "PROJECTION" if config.mode == MODE_PROJECTION else "SPATIAL"
        badge_color = (120, 180, 220) if config.mode == MODE_PROJECTION else (220, 180, 120)
        badge = font_small.render(badge_text, True, badge_color)
        screen.blit(badge, (WIDTH - badge.get_width() - 10, 10))

        # ── Extension badge ───────────────────────────────────────
        ext_badge = font_small.render(
            "EXTENDED", True, (180, 160, 220)
        )
        screen.blit(ext_badge, (WIDTH - ext_badge.get_width() - 10, 28))

        if paused:
            ptext = font_small.render(
                "PAUSED  (SPACE to resume, R to reset, ESC to quit)",
                True, (255, 200, 100))
            screen.blit(ptext, (WIDTH // 2 - 220, HEIGHT - 40))

        frame += 1
        pygame.display.flip()

    # ═══════════════════════════════════════════════════════════════
    #  SHUTDOWN
    # ═══════════════════════════════════════════════════════════════
    if log_fid is not None:
        log_fid.close()
        ext_log = LOG_FILE.replace(".csv", "_extended.csv")
        print(f"Metrics saved to {ext_log}")
    pygame.quit()
    sys.exit()


# ── Extended help overlay ───────────────────────────────────────────

_EXT_HELP_LINES = [
    "CONTROLS (Extended)",
    "─────────────────────────────────────────",
    "M         toggle PROJECTION / SPATIAL mode",
    "1–5       scenario presets",
    "↑ / ↓     φp  ±0.01",
    "← / →     φa  ±0.01   (φn = 1 − φp − φa)",
    "[ / ]     σ   ±1",
    "+ / -     add / remove 10 birds",
    "P         spawn / remove predator",
    "F         toggle focal bird debug view",
    "G         toggle grid overlay",
    "H         hide this help",
    "SPACE     pause / resume",
    "R         reset flock",
    "ESC       quit",
    "",
    "Extensions active:",
    "  1a — Direct velocity (no steering)",
    "  1b — Multi-viewpoint Θ'  (K=12)",
    "  1c — Correlation time τᵨ",
    "  2a — Steric repulsion  (φ_s=0.03)",
    f"  2b — Blind angles  (β={math.degrees(BLIND_ANGLE):.0f}°)",
    "  2d — Anisotropic bodies  (a:b=2:1)",
    "  3a — Predator agent  (P to spawn)",
    "  3b — Spatial optimization",
]


def _draw_help_extended(screen: pygame.Surface, font: pygame.font.Font):
    """Extended help panel with extension info."""
    x, y = WIDTH - 380, 10
    n_lines = len(_EXT_HELP_LINES)
    bg = pygame.Surface((370, n_lines * 18 + 12), pygame.SRCALPHA)
    bg.fill((10, 12, 18, 200))
    screen.blit(bg, (x - 4, y - 4))
    for line in _EXT_HELP_LINES:
        surf = font.render(line, True, (200, 200, 160))
        screen.blit(surf, (x, y))
        y += 18


if __name__ == "__main__":
    main()
