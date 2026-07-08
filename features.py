"""
╔══════════════════════════════════════════════════════════════════════╗
║  FEATURE TOGGLES — enable/disable modules at import time            ║
╚══════════════════════════════════════════════════════════════════════╝

Set flags to True/False BEFORE importing any simulation modules.
Flags are read at module load time by the relevant modules to
enable or disable features without code changes.  Disabled features
are not merely skipped — the modules that implement them are never
imported, so any subset of features can run on its own.

Example usage:
    import features
    features.ENABLE_TRAILS = False
    features.ENABLE_3D = True
    from boid import Boid          # runs without trails
    from main_3d import main       # 3D simulation is enabled

    # Minimal build: just the Pearce projection model, nothing else
    features.ENABLE_SPATIAL_MODE = False
    features.ENABLE_METRICS      = False
    features.ENABLE_PRESETS      = False
    features.ENABLE_HELP_OVERLAY = False
    features.ENABLE_CSV_LOGGING  = False

Flag summary:
    ENABLE_PROJECTION_MODE — Pearce et al. (2014) projection model (mode 0)
    ENABLE_SPATIAL_MODE    — Reynolds (1987) topological boids (mode 1)
    ENABLE_TRAILS          — position-history trail behind each boid
    ENABLE_FOCAL_DEBUG     — focal bird debug overlay (F key)
    ENABLE_GRID_OVERLAY    — spatial grid overlay (G key)
    ENABLE_METRICS         — Θ/Θ'/α metrics computation + HUD panel
    ENABLE_PRESETS         — scenario preset keys (1-0, s,l,i,v,k,q)
    ENABLE_HELP_OVERLAY    — help overlay (H key)
    ENABLE_3D              — 3D simulation (requires moderngl, PyGLM)
    ENABLE_CSV_LOGGING     — write metrics to CSV every N frames

For the full module dependency graph and educational learning path,
see USER_GUIDE.md and README.md (Step-by-Step Build Guide).
──────────────────────────────────────────────────────────────────────
"""

# ── Flocking models  (affect boid.py — at least one must be True) ────
#  With only one model enabled, its module is the only one imported and
#  the M-key mode toggle is disabled; config.mode falls back to the
#  enabled model automatically.

ENABLE_PROJECTION_MODE = True  # Pearce et al. (2014) hybrid projection model
ENABLE_SPATIAL_MODE    = True  # Reynolds (1987) boids, topological neighbours

# ── Visual features  (affect boid_render.py and alg2.py) ─────────────

ENABLE_TRAILS        = False   # position-history trail behind each boid
ENABLE_FOCAL_DEBUG   = False   # focal bird debug overlay (F key)
ENABLE_GRID_OVERLAY  = False   # spatial grid overlay (G key)

# ── Analysis & UI  (affect alg2.py, simulation.py, input_handler.py) ─

ENABLE_METRICS       = True    # FlockMetrics: Θ, Θ', α + HUD panel
                               #   (metrics.py / external_opacity.py are
                               #    never imported when False)
ENABLE_PRESETS       = True    # scenario preset keys (1-0, s,l,i,v,k,q)
                               #   (scenario_presets.py never imported
                               #    when False)
ENABLE_HELP_OVERLAY  = True    # H-key help overlay (help_overlay.py
                               #   never imported when False)

# ── Simulation mode  (affects which entry point modules are loaded) ──

ENABLE_3D            = True    # 3D simulation (main_3d.py, renderer_3d.py,
                               #   spatial_3d.py, boid_3d.py)
                               #   Requires: moderngl, PyGLM, numpy

# ── Data output  (affects alg2.py, alg2.m, alg2.sce) ─────────────────

ENABLE_CSV_LOGGING   = True    # write metrics to CSV every N frames
                               #   (rows contain metrics values, so this
                               #    also requires ENABLE_METRICS)

# ── Extension modules  (affect alg2.py, input_handler.py, simulation.py)
#  Each extension is gated — disabled modules are never imported and
#  their keyboard toggles are ignored.

ENABLE_THREAT            = False   # T-key threat agent (approach/egress +
                               #   escape-wave propagation)
ENABLE_WANDER            = False   # W-key flock wander behaviour
ENABLE_ADAPTIVE_QUALITY   = False   # A-key three-tier FPS degradation
ENABLE_MEDIUM_PRESETS     = False   # N-key ambient medium presets
                               #   (air/dust/starlight/grid)
ENABLE_H2_ROBUSTNESS      = False   # H₂ consensus robustness metric
ENABLE_SEASONAL           = False   # seasonal flock size variation
ENABLE_FLOCK_SHAPE        = False   # PCA flock shape analysis
ENABLE_LEADER             = False   # O-key leader / attractor system
ENABLE_VACUOLE            = False   # E-key vacuole formation (orbiting cavity)
