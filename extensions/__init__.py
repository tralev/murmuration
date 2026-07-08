"""
extensions/ — Roadmap implementations from Pearce et al. (2014) SI Appendix.

Each module implements one roadmap priority without modifying the original
source files.  The flocking-agent variants chain via inheritance:

    Boid  →  DirectVelocityBoid  →  StericBoid  →  BlindAnglesBoid  →  PredatorBoid
    (original)   (1a)                (2a)            (2b)                (3a)

Standalone behaviour/analysis modules (used by any boid, pure functions
where possible so they unit-test without pygame):

    wander            (10c)  flock-level wander centre + radial pulse
    threat            (7)    approach/egress threat agent + escape wave
    adaptive_quality  (15)   three-tier FPS degradation with hysteresis
    h2_robustness     (6)    Young et al. consensus H₂ + η(m) + cost-optimal m*
    seasonal          (5)    Goodenough seasonal flock-size variation
    flock_shape       (6)    PCA aspect ratio, orientation, shape-driven m*
    correlation_time  (1c)   τᵨ via convex-hull density autocorrelation
    multi_viewpoint_opacity (1b)  K-viewpoint external opacity Θ'

⇔ Octave: extensions/alg2_extended.m   ⇔ Scilab: extensions/alg2_extended.sce
Run:  python -m extensions.extended_simulation
"""

from extensions.direct_velocity import DirectVelocityBoid
from extensions.steric_repulsion import StericBoid
from extensions.blind_angles import BlindAnglesBoid
from extensions.anisotropic_bodies import AnisotropicBoid
from extensions.spatial_optimization import OptimizedBoid, SpatialChunker
from extensions.predator import Predator, PredatorBoid
from extensions.wander import WanderConfig, flock_wander_center, wander_force
from extensions.threat import ThreatAgent, escape_wave, flee_force
from extensions.adaptive_quality import AdaptiveQuality
from extensions.h2_robustness import (
    h2_norm, knn_laplacian, eta_of_m, optimal_m, cost_optimal_m,
)
from extensions.seasonal import (
    seasonal_size_factor, flock_size_for_day, is_murmuration_season,
)
from extensions.flock_shape import analyze_shape, ShapeReport, suggested_m_star

__all__ = [
    # Boid inheritance chain
    "DirectVelocityBoid",
    "StericBoid",
    "BlindAnglesBoid",
    "AnisotropicBoid",
    "OptimizedBoid",
    "SpatialChunker",
    "Predator",
    "PredatorBoid",
    # Behaviour / analysis modules
    "WanderConfig", "flock_wander_center", "wander_force",
    "ThreatAgent", "escape_wave", "flee_force",
    "AdaptiveQuality",
    "h2_norm", "knn_laplacian", "eta_of_m", "optimal_m", "cost_optimal_m",
    "seasonal_size_factor", "flock_size_for_day", "is_murmuration_season",
    "analyze_shape", "ShapeReport", "suggested_m_star",
]
