"""
╔══════════════════════════════════════════════════════════════════════╗
║  CONFIGURATION CONSTANTS & RUNTIME STATE    (3D simulation)         ║
╚══════════════════════════════════════════════════════════════════════╝

 Core data structures and constants shared across 3D modules.
 Imported by boid_3d.py, spatial_3d.py, and main_3d.py.
──────────────────────────────────────────────────────────────────────
"""

import math


# ══════════════════════════════════════════════════════════════════════
#  Simulation volume  (3D)
# ══════════════════════════════════════════════════════════════════════

WIDTH  = 1000
HEIGHT = 700
DEPTH  = 400

# ══════════════════════════════════════════════════════════════════════
#  Flock parameters
# ══════════════════════════════════════════════════════════════════════

NUM_BOIDS      = 150
BOID_SIZE      = 3
V0             = 4
MAX_FORCE      = 0.15
VISUAL_RANGE   = 70

# ══════════════════════════════════════════════════════════════════════
#  Default model weights  (φp + φa + φn ≡ 1)
# ══════════════════════════════════════════════════════════════════════

DEFAULT_PHI_P  = 0.03
DEFAULT_PHI_A  = 0.80
DEFAULT_SIGMA  = 4

# ══════════════════════════════════════════════════════════════════════
#  Mode identifiers
# ══════════════════════════════════════════════════════════════════════

MODE_PROJECTION = 0
MODE_SPATIAL    = 1

MODE_NAMES = {
    MODE_PROJECTION: "PROJECTION  (Pearce et al. 2014)",
    MODE_SPATIAL:    "SPATIAL     (topological Reynolds)",
}


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  RUNTIME STATE                                                      ║
# ╚══════════════════════════════════════════════════════════════════════╝


class Config:
    """
    Mutable runtime parameters shared across the simulation.
    Modified directly by keyboard handlers; passed by reference
    into Boid3D.flock() — changes are frame-immediate.

    φn is auto-computed from the invariant  φp + φa + φn = 1.
    """
    __slots__ = ("mode", "phi_p", "phi_a", "sigma", "num_boids")

    def __init__(self):
        self.mode       = MODE_PROJECTION
        self.phi_p      = DEFAULT_PHI_P
        self.phi_a      = DEFAULT_PHI_A
        self.sigma      = DEFAULT_SIGMA
        self.num_boids  = NUM_BOIDS

    @property
    def phi_n(self) -> float:
        """φn = max(0, 1 − φp − φa) — guarantees weights sum to 1."""
        return max(0.0, 1.0 - self.phi_p - self.phi_a)
