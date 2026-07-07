"""
╔══════════════════════════════════════════════════════════════════════╗
║  FEATURE TOGGLES — enable/disable modules at import time            ║
╚══════════════════════════════════════════════════════════════════════╝

Set flags to True/False BEFORE importing any simulation modules.
Flags are read at module load time by the relevant modules to
enable or disable features without code changes.

Example usage:
    import features
    features.ENABLE_TRAILS = False
    features.ENABLE_3D = True
    from boid import Boid          # runs without trails
    from main_3d import main       # 3D simulation is enabled

Flag summary:
    ENABLE_TRAILS         — position-history trail behind each boid
    ENABLE_FOCAL_DEBUG    — focal bird debug overlay (F key)
    ENABLE_GRID_OVERLAY   — spatial grid overlay (G key)
    ENABLE_3D             — 3D simulation (requires moderngl, PyGLM)
    ENABLE_CSV_LOGGING    — write metrics to CSV every N frames

For the full module dependency graph and educational learning path,
see USER_GUIDE.md and README.md (Step-by-Step Build Guide).
──────────────────────────────────────────────────────────────────────
"""

# ── Visual features  (affect boid.py and alg2.py) ────────────────────

ENABLE_TRAILS        = False   # position-history trail behind each boid
ENABLE_FOCAL_DEBUG   = False   # focal bird debug overlay (F key)
ENABLE_GRID_OVERLAY  = False   # spatial grid overlay (G key)

# ── Simulation mode  (affects which entry point modules are loaded) ──

ENABLE_3D            = True    # 3D simulation (main_3d.py, renderer_3d.py,
                               #   spatial_3d.py, boid_3d.py)
                               #   Requires: moderngl, PyGLM, numpy

# ── Data output  (affects alg2.py, alg2.m, alg2.sce) ─────────────────

ENABLE_CSV_LOGGING   = True    # write metrics to CSV every N frames
