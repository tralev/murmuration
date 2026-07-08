"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 11 (3D) — INPUT HANDLING  (Pygame events, 3D simulation)   ║
╚══════════════════════════════════════════════════════════════════════╝

 Why this module exists
 ──────────────────────
 The 2D simulation keeps its event handling in `input_handler.py`, away
 from the main loop. This is the 3D counterpart: it owns all keyboard,
 mouse-drag (orbit), and scroll (zoom) handling for `main_3d.py`, so the
 3D entry point stays a lean setup-plus-loop and the input logic can be
 read and changed on its own.

 It covers the fixed 3D controls only:
   • simulation:  SPACE pause, R reset flock, M mode toggle, ESC quit
   • camera:      mouse-drag orbit, scroll zoom, O auto-rotate, V reset
   • parameters:  ↑/↓ φp, ←/→ φa, [ / ] σ, +/- flock size, G grid
   • presets:     a–h, w → 3D scenario presets

 (The 3D build does not use the 2D extension key toggles — those belong
 to the Pygame-CPU 2D stack and its `extensions/input_ext.py`.)

 Dependencies:  pygame + pygame.locals (event/key constants)
                flock_core   (MODE_NAMES)
                scenario_presets (apply_preset_3d)
──────────────────────────────────────────────────────────────────────
"""

import pygame
from pygame.locals import *

from flock_core import MODE_NAMES
from scenario_presets import apply_preset_3d


def handle_input(config, flock, running, paused, camera, pending_remove,
                 pending_add, pending_reset, show_grid):
    """
    Process Pygame events for one frame of the 3D simulation.

    Mutates *config* and the *camera* in place; returns the updated
    immutable/loop-control values as a tuple.

    Returns
    -------
    (running, paused, pending_remove, pending_add, pending_reset, show_grid)
    """
    mouse_drag_sensitivity = 0.005
    prev_mouse = None

    for event in pygame.event.get():
        if event.type == QUIT:
            running = False

        elif event.type == KEYDOWN:
            key = event.key

            # ── Simulation control ───────────────────────────────
            if key == K_ESCAPE:
                running = False
            elif key == K_SPACE:
                paused = not paused
                print("PAUSED" if paused else "RESUMED")
            elif key == K_r:                       # R — reset the flock
                pending_reset = True
            elif key == K_m:                       # M — projection ↔ spatial
                config.mode = 1 - config.mode
                print(f"MODE: {MODE_NAMES[config.mode]}")
            elif key == K_g:                       # G — reference grid
                show_grid = not show_grid

            # ── Camera controls (view-only, no simulation effect) ─
            elif key == K_v:                       # V — reset camera view
                camera.reset()
                print("Camera reset to default view")
            elif key == K_o:                       # O — auto-rotate demo mode
                on = camera.toggle_auto_rotate()
                print(f"Auto-rotate {'ON' if on else 'OFF'}")

            # ── Live parameter tuning (φp, φa, σ) ────────────────
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

            # ── Flock size ───────────────────────────────────────
            elif key == K_EQUALS or key == K_KP_PLUS:
                pending_add += 10
            elif key == K_MINUS:
                pending_remove += 10

            # ── 3D scenario presets (keys a–h, w) ────────────────
            #  Excludes G (K_g), handled above as the grid toggle.
            elif (K_a <= key <= K_h and key != K_g) or key == K_w:
                label = apply_preset_3d(config, chr(key))
                if label:
                    print(label)

        # ── Mouse: left-drag orbits the camera ───────────────────
        elif event.type == MOUSEBUTTONDOWN:
            if event.button == 1:
                prev_mouse = pygame.mouse.get_pos()
            elif event.button == 4:                # scroll up → zoom in
                camera.zoom(1.0)
            elif event.button == 5:                # scroll down → zoom out
                camera.zoom(-1.0)

        elif event.type == MOUSEMOTION:
            if event.buttons[0]:                   # left button held
                x, y = event.pos
                if prev_mouse is not None:
                    dx = x - prev_mouse[0]
                    dy = y - prev_mouse[1]
                    camera.rotate(dx * mouse_drag_sensitivity,
                                  -dy * mouse_drag_sensitivity)
                prev_mouse = (x, y)

    return (running, paused, pending_remove, pending_add,
            pending_reset, show_grid)
