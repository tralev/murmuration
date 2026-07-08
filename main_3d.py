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

import features

# ── Modularity guard — set features.ENABLE_3D = False to disable ──
if not features.ENABLE_3D:
    raise ImportError(
        "3D simulation is disabled. "
        "Set features.ENABLE_3D = True before importing main_3d."
    )

import pygame
from pygame.locals import *

from flock_core import (
    WIDTH, HEIGHT, V0, NUM_BOIDS,
    DEFAULT_PHI_P, DEFAULT_PHI_A, DEFAULT_SIGMA,
    MODE_PROJECTION, MODE_SPATIAL,
    MODE_NAMES, Config,
)

from boid_3d import Boid3D
from spatial_3d import SpatialGrid3D
from renderer_3d import Renderer3D
from scenario_presets import apply_preset_3d


# ── 3D-specific constants ──────────────────────────────────────────
DEPTH = 400
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


def handle_input(config, flock, running, paused, camera, pending_remove,
                 pending_add, pending_reset, show_grid):
    """
    Process Pygame events. Returns updated state.
    """
    mouse_drag_sensitivity = 0.005
    dragging = False
    prev_mouse = None

    for event in pygame.event.get():
        if event.type == QUIT:
            running = False

        elif event.type == KEYDOWN:
            key = event.key

            if key == K_ESCAPE:
                running = False
            elif key == K_SPACE:
                paused = not paused
                print("PAUSED" if paused else "RESUMED")
            elif key == K_r:
                pending_reset = True
            elif key == K_m:
                config.mode = 1 - config.mode
                print(f"MODE: {MODE_NAMES[config.mode]}")
            elif key == K_g:
                show_grid = not show_grid
            elif key == K_v:
                camera.reset()
                print("Camera reset to default view")
            elif key == K_o:
                on = camera.toggle_auto_rotate()
                print(f"Auto-rotate {'ON' if on else 'OFF'}")
            elif key == K_UP:
                config.phi_p = min(1.0, config.phi_p + 0.01)
            elif key == K_DOWN:
                config.phi_p = max(0.0, config.phi_p - 0.01)
                if config.phi_p + config.phi_a > 1.0:
                    config.phi_a = 1.0 - config.phi_p
            elif key == K_RIGHT:
                config.phi_a = min(1.0, config.phi_a + 0.01)
                if config.phi_p + config.phi_a > 1.0:
                    config.phi_p = 1.0 - config.phi_a
            elif key == K_LEFT:
                config.phi_a = max(0.0, config.phi_a - 0.01)
            elif key == K_RIGHTBRACKET:
                config.sigma = min(20, config.sigma + 1)
            elif key == K_LEFTBRACKET:
                config.sigma = max(1, config.sigma - 1)
            elif key == K_EQUALS or key == K_KP_PLUS:
                pending_add += 10
            elif key == K_MINUS:
                pending_remove += 10

            # ── 3D scenario presets (keys a–h, w) ─────
            elif (K_a <= key <= K_h and key != K_g) or key == K_w:
                preset_key = chr(key)
                label = apply_preset_3d(config, preset_key)
                if label:
                    print(label)

        elif event.type == MOUSEBUTTONDOWN:
            if event.button == 1:
                dragging = True
                prev_mouse = pygame.mouse.get_pos()
            elif event.button == 4:
                camera.zoom(1.0)
            elif event.button == 5:
                camera.zoom(-1.0)

        elif event.type == MOUSEBUTTONUP:
            if event.button == 1:
                dragging = False

        elif event.type == MOUSEMOTION:
            if event.buttons[0]:
                x, y = event.pos
                if prev_mouse is not None:
                    dx = x - prev_mouse[0]
                    dy = y - prev_mouse[1]
                    camera.rotate(
                        dx * mouse_drag_sensitivity,
                        -dy * mouse_drag_sensitivity,
                    )
                prev_mouse = (x, y)

    return (running, paused, pending_remove, pending_add,
            pending_reset, show_grid)


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

    flock = [Boid3D() for _ in range(config.num_boids)]

    running = True
    paused = False
    frame = 0
    pending_remove = 0
    pending_add = 0
    pending_reset = False
    show_grid = False

    print(f"Murmuration 3D — {config.num_boids} birds")
    print(f"Mode: {MODE_NAMES[config.mode]}")
    print("Press M to toggle mode | Space to pause | ESC to quit")
    print("Mouse drag to orbit | Scroll to zoom")
    print("Presets: a=Default b=Ball c=Cloud d=Stream e=Column f=Acro w=Vortex h=Void")

    # ── Main loop ────────────────────────────────────────────
    while running:
        dt = clock.tick(FPS) / 1000.0

        # ── 1. INPUT ─────────────────────────────────────────
        (running, paused, pending_remove, pending_add,
         pending_reset, show_grid) = handle_input(
            config, flock, running, paused, renderer.camera,
            pending_remove, pending_add, pending_reset, show_grid)

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

            # Per-bird physics
            for boid in flock:
                boid.update()

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
            f"σ={config.sigma} | {fps_val:.0f} FPS"
            + (" | PAUSED" if paused else "")
        )

    # ── Shutdown ─────────────────────────────────────────────
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
