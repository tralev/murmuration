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
    NUM_BOIDS, MODE_PROJECTION, MODE_NAMES,
)

from renderer_3d import Renderer3D
from input_handler_3d import handle_input
from simulation_3d import World


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

    # ── Simulation state (headless model, see simulation_3d.py) ──
    world = World(num_boids=NUM_BOIDS, verbose=True)
    config = world.config
    ext = world.ext
    renderer = Renderer3D(WINDOW_WIDTH, WINDOW_HEIGHT)
    clock = pygame.time.Clock()

    running = True
    paused = False
    pending_remove = 0
    pending_add = 0
    pending_reset = False
    show_grid = False

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
            config, world.flock, running, paused, renderer.camera,
            pending_remove, pending_add, pending_reset, show_grid, ext)

        # ── Auto-rotate the camera for unattended demos (O key) ──
        renderer.camera.step_auto_rotate(dt)

        # ── 2. UPDATE (headless model — see simulation_3d.World) ──
        if not paused:
            pending_remove, pending_add, pending_reset = world.advance(
                dt, pending_remove, pending_add, pending_reset)

        # ── 3. RENDER ────────────────────────────────────────
        renderer.begin_frame()
        renderer.draw_birds(world.flock)
        if show_grid:
            renderer.draw_grid()
        renderer.end_frame()

        # Swap buffers
        pygame.display.flip()

        # ── Window title with metrics ────────────────────────
        fps_val = clock.get_fps()
        mode_name = "PROJECTION" if config.mode == MODE_PROJECTION else "SPATIAL"
        n = len(world.flock)
        pygame.display.set_caption(
            f"Murmuration 3D | {mode_name} | {n} birds | "
            f"φp={config.phi_p:.2f} φa={config.phi_a:.2f} "
            f"σ={config.sigma} | {world.metrics.summary()} τρ={world.corr.tau:.0f} | "
            f"{fps_val:.0f} FPS"
            + (" | PAUSED" if paused else "")
        )

    # ── Shutdown ─────────────────────────────────────────────
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
