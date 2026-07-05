"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D EXTENDED SIMULATION — Full 3D Murmuration                      ║
╚══════════════════════════════════════════════════════════════════════╝

 3D murmuration with spherical cap occlusion (Fibonacci sphere).

 Features:
   - 3D (x, y, z) bird positions with toroidal wrap
   - Spherical cap occlusion via Fibonacci sphere z-buffer (~80 pts)
   - Perspective projection rendering
   - Direct velocity setting (no Reynolds steering)
   - Blind cone (60° behind bird)
   - Correlation time τᵨ tracking
   - Multi-viewpoint external opacity
   - CSV logging

 Run:  python -m extensions.extended_simulation_3d
──────────────────────────────────────────────────────────────────────
"""

import pygame
import sys
import math
import os

from flock_core import (
    WIDTH, HEIGHT, FPS, NUM_BOIDS, V0,
    LOG_FILE, LOG_EVERY, MODE_PROJECTION,
    Config,
)
from extensions.three_d import Boid3D, FIB_POINTS, BLIND_3D_ANGLE, DEPTH
from extensions.correlation_time import CorrelationTimeTracker
from scenario_presets import apply_preset


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(
        "Murmuration 3D — Fibonacci sphere occlusion  |  1-5:presets  H:help  ESC:quit"
    )

    clock = pygame.time.Clock()
    font_small = pygame.font.Font(None, 18)
    font_help = pygame.font.Font(None, 16)
    font_debug = pygame.font.Font(None, 14)

    config = Config()

    # ── Open CSV log ──────────────────────────────────────────────
    log_fid = None
    if LOG_FILE is not None:
        ext_log = LOG_FILE.replace(".csv", "_3d.csv")
        try:
            os.makedirs(os.path.dirname(ext_log) or ".", exist_ok=True)
            log_fid = open(ext_log, "w")
            log_fid.write(
                "frame,mode,num_boids,phi_p,phi_a,phi_n,"
                "sigma,theta,theta_ext,alpha,fps,tau,density\n"
            )
            print(f"Logging metrics to {ext_log} every {LOG_EVERY} frames")
        except OSError as e:
            print(f"WARNING: could not open {ext_log}: {e}")
            log_fid = None

    # ── Initialize 3D flock ───────────────────────────────────────
    flock = [Boid3D() for _ in range(config.num_boids)]
    corr_tracker = CorrelationTimeTracker()

    # 3D metrics (EMA-smoothed)
    SMOOTH = 0.05
    _theta = 0.0
    _alpha = 0.0
    _fps = 0.0
    frame = 0
    running = True
    paused = False
    pending_reset = False
    pending_add = 0
    pending_remove = 0
    preset_label = ""
    show_help = True

    ext_info_line = ""

    while running:
        dt = clock.tick(FPS)

        # ═══════════════════════════════════════════════════════════
        #  INPUT
        # ═══════════════════════════════════════════════════════════
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                key = event.key

                if pygame.K_1 <= key <= pygame.K_5:
                    preset_label = apply_preset(config, key - pygame.K_1 + 1)

                elif key == pygame.K_UP:
                    config.phi_p = min(1.0, config.phi_p + 0.01)
                    preset_label = ""
                elif key == pygame.K_DOWN:
                    config.phi_p = max(0.0, config.phi_p - 0.01)
                    preset_label = ""

                elif key == pygame.K_RIGHT:
                    config.phi_a = min(1.0, config.phi_a + 0.01)
                    preset_label = ""
                elif key == pygame.K_LEFT:
                    config.phi_a = max(0.0, config.phi_a - 0.01)
                    preset_label = ""

                elif key == pygame.K_RIGHTBRACKET:
                    config.sigma = min(50, config.sigma + 1)
                    preset_label = ""
                elif key == pygame.K_LEFTBRACKET:
                    config.sigma = max(1, config.sigma - 1)
                    preset_label = ""

                elif key == pygame.K_EQUALS or key == pygame.K_PLUS:
                    pending_add = min(pending_add + 10, 200)
                elif key == pygame.K_MINUS:
                    pending_remove += 10

                elif key == pygame.K_h:
                    show_help = not show_help
                elif key == pygame.K_SPACE:
                    paused = not paused
                elif key == pygame.K_r:
                    pending_reset = True
                elif key == pygame.K_ESCAPE:
                    running = False

        # ═══════════════════════════════════════════════════════════
        #  UPDATE
        # ═══════════════════════════════════════════════════════════
        if not paused:
            if pending_remove > 0:
                n_remove = min(pending_remove, len(flock) - 1)
                if n_remove > 0:
                    for _ in range(n_remove):
                        flock.pop()
                    config.num_boids = len(flock)
                    pending_remove -= n_remove
            if pending_add > 0:
                for _ in range(pending_add):
                    flock.append(Boid3D())
                config.num_boids = len(flock)
                pending_add = 0

            if pending_reset:
                flock = [Boid3D() for _ in range(config.num_boids)]
                corr_tracker = CorrelationTimeTracker()
                _theta = 0.0
                _alpha = 0.0
                _fps = 0.0
                frame = 0
                pending_reset = False

            # ── Per-bird flocking ─────────────────────────────────
            for boid in flock:
                boid.flock(flock, config)

            # ── Per-bird physics ──────────────────────────────────
            for boid in flock:
                boid.update()

            # ── 3D Metrics ───────────────────────────────────────
            n = len(flock)
            if n > 0:
                # Θ — average internal opacity
                theta = sum(b._last_theta for b in flock) / n
                _theta += (theta - _theta) * SMOOTH
                # α — order parameter (3D)
                total_v = pygame.Vector3(0, 0, 0)
                for b in flock:
                    total_v += b.velocity
                alpha = total_v.length() / (n * V0)
                _alpha += (alpha - _alpha) * SMOOTH
                # FPS
                _fps += (clock.get_fps() - _fps) * SMOOTH
            else:
                _theta = 0.0
                _alpha = 0.0
                _fps = clock.get_fps()

            # ── Correlation time ──────────────────────────────────
            corr_tracker.sample(flock, frame)

            # ── Info line ────────────────────────────────────────
            tau_str = f"τᵨ={corr_tracker.tau:.0f}f" if corr_tracker.tau > 0 else "τᵨ=…"
            ext_info_line = (
                f"3D: N={len(flock)}  φp={config.phi_p:.2f}  φa={config.phi_a:.2f}  "
                f"σ={config.sigma}  Θ={_theta:.3f}  α={_alpha:.3f}  "
                f"{tau_str}  {int(_fps)}fps"
            )

            # ── CSV logging ───────────────────────────────────────
            if log_fid is not None and frame % LOG_EVERY == 0:
                n = len(flock)
                log_fid.write(
                    f"{frame},{config.mode},{n},"
                    f"{config.phi_p:.4f},{config.phi_a:.4f},"
                    f"{config.phi_n:.4f},{config.sigma},"
                    f"{_theta:.4f},0.0000,"
                    f"{_alpha:.4f},{_fps:.1f},"
                    f"{corr_tracker.tau:.4f},{corr_tracker.latest_density:.6f}\n"
                )
                log_fid.flush()

        # ═══════════════════════════════════════════════════════════
        #  RENDER
        # ═══════════════════════════════════════════════════════════
        screen.fill((10, 12, 18))

        # Draw birds (sorted back-to-front for correct overlap)
        flock_sorted = sorted(flock, key=lambda b: b.position.z, reverse=True)
        for boid in flock_sorted:
            boid.draw(screen, config)

        # ── Info line ─────────────────────────────────────────────
        info_surf = font_small.render(ext_info_line, True, (180, 200, 220))
        screen.blit(info_surf, (WIDTH // 2 - info_surf.get_width() // 2, HEIGHT - 18))

        # ── Mode badge ───────────────────────────────────────────
        badge = font_small.render("3D PROJECTION", True, (120, 220, 180))
        screen.blit(badge, (WIDTH - badge.get_width() - 10, 10))

        # ── Extension badge ───────────────────────────────────────
        ext_badge = font_small.render(
            f"3D · {FIB_POINTS} fib pts", True, (160, 200, 180)
        )
        screen.blit(ext_badge, (WIDTH - ext_badge.get_width() - 10, 28))

        if show_help:
            _draw_help_3d(screen, font_help)

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
        print(f"Metrics saved to {LOG_FILE.replace('.csv', '_3d.csv')}")
    pygame.quit()
    sys.exit()


_HELP_LINES_3D = [
    "CONTROLS (3D)",
    "─────────────────────────────────────────",
    "1–5       scenario presets",
    "↑ / ↓     φp  ±0.01",
    "← / →     φa  ±0.01   (φn = 1 − φp − φa)",
    "[ / ]     σ   ±1",
    "+ / -     add / remove 10 birds",
    "H         toggle help overlay",
    "SPACE     pause / resume",
    "R         reset flock",
    "ESC       quit",
    "",
    "3D Extensions active:",
    "  2c — Spherical cap occlusion  (Fibonacci sphere)",
    f"  Blind cone: {math.degrees(BLIND_3D_ANGLE):.0f}° behind bird",
    "  1a — Direct velocity  (no steering)",
    "  1b — Multi-viewpoint Θ'  (K=12)",
    "  1c — Correlation time τᵨ",
    "  Perspective rendering  (z-depth)",
    f"  Volume: {WIDTH}×{HEIGHT}×{DEPTH}  ·  Toroidal wrap (all axes)",
]


def _draw_help_3d(screen: pygame.Surface, font: pygame.font.Font):
    """3D help panel."""
    x, y = WIDTH - 400, 10
    n_lines = len(_HELP_LINES_3D)
    bg = pygame.Surface((390, n_lines * 18 + 12), pygame.SRCALPHA)
    bg.fill((10, 12, 18, 200))
    screen.blit(bg, (x - 4, y - 4))
    for line in _HELP_LINES_3D:
        surf = font.render(line, True, (160, 200, 180))
        screen.blit(surf, (x, y))
        y += 18


if __name__ == "__main__":
    main()
