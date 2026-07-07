"""
╔══════════════════════════════════════════════════════════════════════╗
║  FEATURE TOGGLES — enable/disable modules at import time            ║
╚══════════════════════════════════════════════════════════════════════╝

Set flags to True/False BEFORE importing simulation modules.
Used by boid.py, alg2.py, and extensions to conditionally load features.

Example:
    import features
    features.ENABLE_TRAILS = False
    features.ENABLE_FOCAL_DEBUG = True
    from boid import Boid  # now runs without trails

See USER_GUIDE.md for full list of features and their dependencies.
──────────────────────────────────────────────────────────────────────
"""

# ── Core features  (affect boid.py and alg2.py) ────────────────────────

ENABLE_TRAILS        = False   # position-history trail behind each boid
ENABLE_FOCAL_DEBUG   = False   # focal bird debug overlay (F key)
ENABLE_GRID_OVERLAY  = False   # spatial grid overlay (G key)

# ── Behavioural features  (affect boid.py and extensions) ─────────────

ENABLE_STERIC        = True    # steric repulsion between nearby boids
ENABLE_BLIND_ANGLES  = True    # blind-angle occlusion filtering (rear 60°)
ENABLE_ANISOTROPIC   = True    # elliptical bird body projection

# ── Performance features  (affect extensions) ──────────────────────────

ENABLE_SPATIAL_OPT   = True    # spatial chunking optimisation (Priority 3b)
ENABLE_PREDATOR      = False   # predator agent (Priority 7)
ENABLE_3D            = False   # 3D simulation mode (Priority 2c)

# ── Cross-language flags  (affect alg2.m / alg2.sce equivalents) ──────

ENABLE_CSV_LOGGING   = True    # write metrics to CSV every N frames
