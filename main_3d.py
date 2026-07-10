"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D MURMURATION — Main Entry Point                                  ║
╚══════════════════════════════════════════════════════════════════════╝

 Pygame + PyOpenGL 3D bird flocking simulation.
 Two modes, switchable at runtime:
   MODE 0 (PROJECTION) — Pearce et al. 2014 hybrid projection model
   MODE 1 (SPATIAL)    — Topological Reynolds boids with 3D spatial grid

 Controls:
   M           Toggle mode
   Space       Pause / resume
   R           Reset flock
   Up/Down     φp ±0.01
   Left/Right  φa ±0.01
   [/]         σ ±1
   +/-         Add/remove birds
   G           Toggle grid overlay
   a-h, w       3D scenario presets
   ESC         Quit

   Mouse drag  Orbit camera
   Scroll      Zoom

 Dependencies:  numpy, PyOpenGL, PyGLM, Pygame
──────────────────────────────────────────────────────────────────────
"""

import sys

import pygame
from pygame.locals import *

from flock_core import (
    WIDTH, HEIGHT, DEPTH, V0, NUM_BOIDS, MAX_FORCE,
    DEFAULT_PHI_P, DEFAULT_PHI_A, DEFAULT_SIGMA,
    MODE_PROJECTION, MODE_SPATIAL,
    MODE_NAMES, Config,
)

from boid_3d import Boid3D
from spatial_grid_3d import SpatialGrid3D
from renderer_3d import Renderer3D
from input_handler_3d import handle_input
from metrics_3d import FlockMetrics3D
from correlation_time import CorrelationTimeTracker
from predator_3d import apply_predator
from ecology import roost_force


# ── 3D-specific constants ──────────────────────────────────────────
FPS = 60
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
BG_COLOR = (8, 10, 14)


def create_window():
    """Create a Pygame window with OpenGL flags for ModernGL."""
    pygame.display.set_mode(
        (WINDOW_WIDTH, WINDOW_HEIGHT),
        DOUBLEBUF | OPENGL,
    )
    pygame.display.set_caption("Murmuration 3D — Bird Flock Simulation")


def setup_opengl():
    """ModernGL handles OpenGL state internally — nothing to set up here."""
    pass


def main():
    """3D simulation main loop."""
    # ── Pygame + OpenGL window setup ─────────────────────────
    pygame.init()
    create_window()
    setup_opengl()

    # ── Simulation state ─────────────────────────────────────
    config = Config()
    config.num_boids = NUM_BOIDS
    grid = SpatialGrid3D()
    renderer = Renderer3D(WINDOW_WIDTH, WINDOW_HEIGHT)
    clock = pygame.time.Clock()
    metrics = FlockMetrics3D()      # Pearce-grounded 3D observables
    corr = CorrelationTimeTracker()  # density autocorrelation time τρ

    flock = [Boid3D() for _ in range(config.num_boids)]

    running = True
    paused = False
    frame = 0
    pending_remove = 0
    pending_add = 0
    pending_reset = False
    show_grid = False

    # ── Behavioural-dynamics state (Goodenough): predator + roosting ──
    #  A ground roost near the bottom of the volume; a fast 24h clock so the
    #  dusk cycle is visible in seconds when roosting is toggled on.
    ext = {
        "predator": None,          # Predator3D when spawned (T key)
        "roosting": False,         # day/night roost cycle (K key)
        "hour": 12.0,              # time of day, 0–24
        "day": 15,                 # day-of-year (mid-January)
        "roost": (WIDTH * 0.5, HEIGHT * 0.5, DEPTH * 0.1),
    }

    print(f"Murmuration 3D — {config.num_boids} birds")
    print(f"Mode: {MODE_NAMES[config.mode]}")
    print("Press M to toggle mode | Space to pause | ESC to quit")
    print("Mouse drag to orbit | Scroll to zoom")
    print("O key: auto-rotate | V key: reset camera view")
    print("T: predator | K: roosting cycle | U: SI refinements (on)")

    # ── Main loop ────────────────────────────────────────────
    while running:
        dt = clock.tick(FPS) / 1000.0

        # ── 1. INPUT ─────────────────────────────────────────
        (running, paused, pending_remove, pending_add,
         pending_reset, show_grid) = handle_input(
            config, flock, running, paused, renderer.camera,
            pending_remove, pending_add, pending_reset, show_grid, ext)

        # ── Auto-rotate the camera for unattended demos (O key) ──
        renderer.camera.step_auto_rotate(dt)

        # ── 2. UPDATE ────────────────────────────────────────
        if not paused:
            # Boid count changes
            if pending_remove > 0:
                n = min(pending_remove, len(flock) - 1)
                if n > 0:
                    for _ in range(n):
                        flock.pop()
                    config.num_boids = len(flock)
                    pending_remove -= n
                    print(f"Removed {n} birds, now {config.num_boids}")
            if pending_add > 0:
                n_added = pending_add
                for _ in range(pending_add):
                    flock.append(Boid3D())
                config.num_boids = len(flock)
                pending_add = 0
                print(f"Added {n_added} birds, now {config.num_boids}")

            # Reset
            if pending_reset:
                config.num_boids = NUM_BOIDS
                flock = [Boid3D() for _ in range(config.num_boids)]
                grid = SpatialGrid3D()
                frame = 0
                pending_reset = False
                print(f"Flock reset — {config.num_boids} birds")

            # Grid rebuild
            grid.rebuild(flock)

            # Per-bird flocking
            for boid in flock:
                boid.flock(flock, config, grid)

            # ── Behavioural dynamics (Goodenough) ────────────
            #  Applied as extra steering forces before integration.
            if ext["predator"] is not None:            # anti-predator flight
                apply_predator(flock, ext["predator"])
            if ext["roosting"]:                        # dusk descent to roost
                ext["hour"] = (ext["hour"] + dt) % 24.0   # fast day clock
                for boid in flock:
                    boid.apply_force(roost_force(
                        boid.pos, ext["hour"], ext["roost"],
                        ext["day"], strength=MAX_FORCE))

            # Per-bird physics
            for boid in flock:
                boid.update()

            # Scientific metrics (order param, opacity Θ/Θ', L, dispersion)
            metrics.update(flock, config)
            corr.sample(flock)          # τρ density autocorrelation

            frame += 1

        # ── 3. RENDER ────────────────────────────────────────
        renderer.begin_frame()
        renderer.draw_birds(flock)
        if show_grid:
            renderer.draw_grid()
        renderer.end_frame()

        # Swap buffers
        pygame.display.flip()

        # ── Window title with metrics ────────────────────────
        fps_val = clock.get_fps()
        mode_name = "PROJECTION" if config.mode == MODE_PROJECTION else "SPATIAL"
        n = len(flock)
        pygame.display.set_caption(
            f"Murmuration 3D | {mode_name} | {n} birds | "
            f"φp={config.phi_p:.2f} φa={config.phi_a:.2f} "
            f"σ={config.sigma} | {metrics.summary()} τρ={corr.tau:.0f} | "
            f"{fps_val:.0f} FPS"
            + (" | PAUSED" if paused else "")
        )

    # ── Shutdown ─────────────────────────────────────────────
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
