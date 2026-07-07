"""
╔══════════════════════════════════════════════════════════════════════╗
║  ITERATION 9 — Modular Architecture                                ║
╚══════════════════════════════════════════════════════════════════════╝

 Splits the monolithic simulation into focused modules.
 Each module has a single responsibility and can be studied independently.

 What we learn:
   • features.py      — toggle flags (ENABLE_TRAILS, ENABLE_GRID, etc.)
   • flock_core.py    — constants, Config, SpatialGrid
   • occlusion_geom.py — pure math functions (no Pygame)
   • boid.py          — Boid class (both _flock_projection and _flock_spatial)
   • metrics.py       — Θ, Θ', α with EMA
   • scenario_presets.py — educational preset configurations
   • input_handler.py — Pygame event processing
   • simulation.py    — per-frame update (boid counts, grid, flocking)
   • alg2.py          — main() orchestrator (thin, ties modules together)

 Dependency graph (no circular imports):
   occlusion_geom → flock_core → boid → metrics → scenario_presets
   → input_handler → simulation → alg2
──────────────────────────────────────────────────────────────────────
"""

# ══════════════════════════════════════════════════════════════════════
#  features.py — enable/disable feature sets at import time
# ══════════════════════════════════════════════════════════════════════

# Core features
ENABLE_TRAILS = False          # draw position-history trail behind birds
ENABLE_FOCAL_DEBUG = False     # render focal bird debug vectors
ENABLE_GRID_OVERLAY = False    # show spatial grid cells (SPATIAL mode)

# Usage in boid.py:
#   import features
#   if features.ENABLE_TRAILS:
#       self.history.append(pygame.Vector2(self.position))

# ══════════════════════════════════════════════════════════════════════
#  alg2.py — thin orchestrator (the final 3-phase main loop)
# ══════════════════════════════════════════════════════════════════════

def main():
    """
    Pure orchestrator pattern:
      while running:
          1. INPUT   — input_handler.handle_events(...)
          2. UPDATE  — simulation.update_frame(...)
          3. RENDER  — local drawing
    """
    # ── Setup (Pygame, config, grid, flock, metrics, CSV, fonts)
    # ── while running:
    #       dt = clock.tick(FPS)
    #
    #       # 1. INPUT
    #       (running, paused, ...) = input_handler.handle_events(
    #           config, flock, running, paused, ...)
    #
    #       # 2. UPDATE (if not paused)
    #       (flock, grid, metrics, frame, ...) = simulation.update_frame(
    #           config, flock, metrics, grid, frame, clock, ...)
    #
    #       # 3. RENDER
    #       screen.fill(...)
    #       for boid in flock: boid.draw(screen, config)
    #       metrics.draw(screen, ...)
    #       pygame.display.flip()
    pass


# ══════════════════════════════════════════════════════════════════════
#  KEY DESIGN PATTERNS
# ══════════════════════════════════════════════════════════════════════

"""
1. THIN WRAPPERS — Boid methods delegate to extracted functions:
     def _flock_projection(self, boids, config):
         projection_model.flock_projection(self, boids, config)
   This preserves extension subclassing (blind_angles, steric_repulsion).

2. STATE RETURNS — immutable values returned from functions:
     (running, paused, ...) = input_handler.handle_events(...)
   Mutable objects (config, flock) are modified in-place.

3. FEATURE FLAGS — import-time toggles in features.py:
     if features.ENABLE_TRAILS: ...
   No runtime overhead for disabled features.

4. IMPORT ORDER — dependency DAG (no circular imports):
     occlusion_geom → flock_core → projection/spatial_model → boid
       → metrics → help_overlay → scenario_presets
       → input_handler → simulation → alg2

5. TEST STRUCTURE — domain-split test files with discovery guardians:
     test_occlusion.py (47 tests)
     test_boundary.py (41 tests)
     test_cross_language.py (10 tests)
     test_presets.py (10 tests)
     test_projection_model.py (18 tests)
     test_spatial_model.py (13 tests)
     test_input_handler.py (32 tests)
     test_alg2.py — thin runner importing all classes
"""

# For the complete, runnable modular codebase, see:
#   alg2.py           — main entry point
#   flock_core.py     — constants, Config, SpatialGrid
#   boid.py           — Boid class
#   occlusion_geom.py — angular interval math
#   projection_model.py — Pearce et al. algorithm
#   spatial_model.py  — Reynolds boids algorithm
#   metrics.py        — scientific metrics
#   features.py       — toggle flags
#   help_overlay.py   — keyboard reference
#   input_handler.py  — event processing
#   simulation.py     — per-frame update
