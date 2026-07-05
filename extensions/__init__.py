"""
extensions/ — Roadmap implementations from Pearce et al. (2014) SI Appendix.

Each module implements one roadmap priority without modifying the original
source files.  Classes chain via inheritance:

    Boid  →  DirectVelocityBoid  →  StericBoid  →  BlindAnglesBoid  →  PredatorBoid
    (original)   (1a)                (2a)            (2b)                (3a)

Run:  python -m extensions.extended_simulation
"""

from extensions.direct_velocity import DirectVelocityBoid
from extensions.steric_repulsion import StericBoid
from extensions.blind_angles import BlindAnglesBoid
from extensions.anisotropic_bodies import AnisotropicBoid
from extensions.spatial_optimization import OptimizedBoid, SpatialChunker
from extensions.predator import Predator, PredatorBoid

__all__ = [
    "DirectVelocityBoid",
    "StericBoid",
    "BlindAnglesBoid",
    "AnisotropicBoid",
    "OptimizedBoid",
    "SpatialChunker",
    "Predator",
    "PredatorBoid",
]
