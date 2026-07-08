"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 11 — INPUT HANDLING  (Pygame events)                       ║
╚══════════════════════════════════════════════════════════════════════╝

 Keyboard and mouse event processing for the murmuration simulation.
 Extracted from alg2.py so the input logic can be studied, tested, and
 modified independently of the main loop.

 Called once per frame by main() in alg2.py.  Mutates mutable state
 (config, flock) directly; returns updated values for immutable types.

 Dependencies:  pygame (for event constants and mouse position)
                features.py   (ENABLE_FOCAL_DEBUG, ENABLE_GRID_OVERLAY,
                               ENABLE_PRESETS, ENABLE_HELP_OVERLAY,
                               ENABLE_PROJECTION_MODE, ENABLE_SPATIAL_MODE)
                flock_core    (MARGIN_BOUNDARY, etc.)
                boid_module   (for MARGIN_BOUNDARY sync)
                scenario_presets (apply_preset — only when ENABLE_PRESETS)
──────────────────────────────────────────────────────────────────────
"""

import pygame

import features
import flock_core
from flock_core import (
    MODE_PROJECTION, MODE_SPATIAL,
)
import boid as boid_module

# scenario_presets.py never loads when presets are disabled; the
# preset keys then fall through to the remaining key handlers.
if features.ENABLE_PRESETS:
    from scenario_presets import apply_preset


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Preset helpers — key mapping and config snapshot/restore            ║
# ╚══════════════════════════════════════════════════════════════════════╝


def _get_preset_key(pygame_key):
    """Map a pygame key constant to a preset key (int or str).
    Returns None if the key is not a preset key."""
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
# ║  Event loop — per-frame Pygame event processing                     ║
# ╚══════════════════════════════════════════════════════════════════════╝


def handle_events(config, flock, running, paused, pending_reset,
                  pending_add, pending_remove, focal_index,
                  last_preset_key, saved_config, preset_label):
    """
    Process all pending Pygame events for one frame.

    Parameters
    ----------
    config          : Config — mutable; modified in place for mode, φp, φa, σ,
                      show_grid, show_help
    flock           : list[Boid] — mutable; read for mouse-click focal selection
    running         : bool — whether the simulation is running (ESC/QUIT sets False)
    paused          : bool — whether simulation is paused (SPACE toggles)
    pending_reset   : bool — R key sets True
    pending_add     : int — =/+ key increments
    pending_remove  : int — - key increments
    focal_index     : int | None — F key or mouse click sets; F clears
    last_preset_key : any | None — tracked for toggle behaviour
    saved_config    : dict | None — config snapshot for preset toggle
    preset_label    : str — label for on-screen preset name display

    Returns
    -------
    tuple of (running, paused, pending_reset, pending_add, pending_remove,
              focal_index, last_preset_key, saved_config, preset_label)
    — updated values for immutable types.
    """
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            continue

        elif event.type == pygame.KEYDOWN:
            key = event.key

            # ── Scenario presets  (toggle: same key = restore) ──
            preset_key = (_get_preset_key(key)
                          if features.ENABLE_PRESETS else None)
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

            # ── Mode toggle  (m) — needs both models enabled ──
            elif key == pygame.K_m:
                if (features.ENABLE_PROJECTION_MODE
                        and features.ENABLE_SPATIAL_MODE):
                    config.mode = 1 - config.mode
                    mode_name = "PROJECTION" if config.mode == MODE_PROJECTION else "SPATIAL"
                    print(f"[MODE] Switched to {mode_name}")
                    last_preset_key = None   # invalidate preset toggle
                    saved_config = None
                else:
                    print("[MODE] Toggle disabled — only one flocking "
                          "model is enabled in features.py")

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
                config.sigma = max(1, config.sigma - 1)
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
            elif key == pygame.K_f and features.ENABLE_FOCAL_DEBUG:
                if focal_index is not None:
                    focal_index = None
                    print("Focal bird: OFF")
                elif flock:
                    focal_index = 0
                    print(f"Focal bird: #{focal_index}"
                          f"  (click to change, F to clear)")

            # ── Visual toggles  (g, h) ────────────────────────
            elif key == pygame.K_g and features.ENABLE_GRID_OVERLAY:
                config.show_grid = not config.show_grid
            elif key == pygame.K_h and features.ENABLE_HELP_OVERLAY:
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

    return (running, paused, pending_reset, pending_add, pending_remove,
            focal_index, last_preset_key, saved_config, preset_label)
