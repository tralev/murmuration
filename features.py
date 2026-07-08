"""
╔══════════════════════════════════════════════════════════════════════╗
║  FEATURE TOGGLES — enable/disable 3D simulation components          ║
╚══════════════════════════════════════════════════════════════════════╝

Set flags BEFORE importing any simulation modules.
Flags are read at module load time to enable or disable components.

Example usage:
    import features
    features.ENABLE_SPATIAL_MODE = False
    from boid_3d import Boid3D

Flag summary:
    ENABLE_PROJECTION_MODE — Pearce et al. (2014) projection model
    ENABLE_SPATIAL_MODE    — Reynolds (1987) topological boids

For the 3D simulation architecture, see main_3d.py.
──────────────────────────────────────────────────────────────────────
"""

# ── Flocking models  ────────────────────────────────────────────────

ENABLE_PROJECTION_MODE = True
ENABLE_SPATIAL_MODE    = True
