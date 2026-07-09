"""
╔══════════════════════════════════════════════════════════════════════╗
║  FLOCK SHAPE ANALYSIS (3D) — shape-dependent optimal neighbours     ║
╚══════════════════════════════════════════════════════════════════════╝

 Source (see sci.md §2.3 for the result and §4.4 for the 3D port): Young,
 Scardovi, Cavagna, Giardina & Leonard (2013), "Starling Flock Networks
 Manage Uncertainty in Consensus at Low Cost" (arXiv:1302.3195). The
 paper's key structural result is that the optimal
 number of interaction neighbours does **not** depend on flock size but on
 the flock's **shape — notably its thickness**: thin (longitudinal) flocks
 need fewer neighbours (m* ≈ 6) than thick (transverse) ones (m* ≈ 9.8).

 This module measures a 3D flock's shape from the principal-component
 analysis of its position covariance (numpy.cov + numpy.linalg.eigh — a
 3×3 symmetric eigenproblem) and interpolates Young's shape-driven m*.

   • three principal-axis variances λ₁ ≥ λ₂ ≥ λ₃
   • elongation (aspect ratio) = √(λ₁ / λ₃)      (major vs. minor extent)
   • thickness ratio           = √(λ₃ / λ₁) ∈ (0, 1]
   • suggested m* interpolated between the thin/thick endpoints

 Pairs with h2_robustness.py: shape → predicted m*, H₂ → measured optimum.

 Usage:
   from flock_shape import analyze_shape, suggested_m_star, ShapeReport
──────────────────────────────────────────────────────────────────────
"""

import math

import numpy as np


# Young et al. optimal-m endpoints by flock shape.
M_STAR_LONGITUDINAL = 6.05    # thin / elongated flocks
M_STAR_TRANSVERSE   = 9.78    # thick / round flocks
_ASPECT_THIN  = 3.0           # aspect ratio anchoring the "thin" endpoint
_ASPECT_ROUND = 1.0           # aspect ratio anchoring the "round" endpoint


# ── Shape → optimal-m* mapping (Young's thin/thick endpoints) ───────

class ShapeReport:
    """Bundle of 3D flock-shape descriptors."""

    __slots__ = ("count", "variances", "aspect_ratio", "thickness_ratio",
                 "axes", "suggested_m")

    def __init__(self, count, variances, aspect_ratio, thickness_ratio,
                 axes, suggested_m):
        self.count = count
        self.variances = variances            # (λ₁, λ₂, λ₃) descending
        self.aspect_ratio = aspect_ratio      # √(λ₁/λ₃) ≥ 1
        self.thickness_ratio = thickness_ratio  # √(λ₃/λ₁) ∈ (0, 1]
        self.axes = axes                      # 3×3 principal axes (columns)
        self.suggested_m = suggested_m

    def __repr__(self):
        return (f"ShapeReport(n={self.count}, aspect={self.aspect_ratio:.2f}, "
                f"thickness={self.thickness_ratio:.2f}, "
                f"m*={self.suggested_m:.1f})")


def suggested_m_star(aspect_ratio: float) -> float:
    """Interpolate Young et al.'s optimal m* from the flock aspect ratio.

    Round flocks (aspect ≈ 1) → ~9.78; thin flocks (aspect ≥ 3) → ~6.05,
    clamped outside that range."""
    t = (aspect_ratio - _ASPECT_ROUND) / (_ASPECT_THIN - _ASPECT_ROUND)
    t = max(0.0, min(1.0, t))
    return M_STAR_TRANSVERSE + t * (M_STAR_LONGITUDINAL - M_STAR_TRANSVERSE)


def _as_xyz(p):
    pos = getattr(p, "pos", None)
    if pos is not None:
        return (float(pos[0]), float(pos[1]), float(pos[2]))
    return (p[0], p[1], p[2])


# ══════════════════════════════════════════════════════════════════════
#  PCA SHAPE ANALYSIS — 3×3 position-covariance eigendecomposition
# ══════════════════════════════════════════════════════════════════════

def analyze_shape(flock) -> ShapeReport:
    """Compute 3D shape descriptors for a flock (birds with ``.pos`` or
    (x,y,z) tuples). Degenerate (< 4 points) → round default."""
    pts = np.array([_as_xyz(p) for p in flock], dtype=float)
    n = len(pts)
    if n < 4:
        return ShapeReport(n, (0.0, 0.0, 0.0), 1.0, 1.0,
                           np.eye(3), M_STAR_TRANSVERSE)

    cov = np.cov(pts, rowvar=False, bias=True)      # 3×3 covariance
    evals, evecs = np.linalg.eigh(cov)              # ascending
    evals = np.maximum(evals, 0.0)
    lam3, lam2, lam1 = float(evals[0]), float(evals[1]), float(evals[2])

    if lam3 < 1e-9:
        aspect = float("inf") if lam1 > 1e-9 else 1.0
        thickness = 0.0 if lam1 > 1e-9 else 1.0
    else:
        aspect = math.sqrt(lam1 / lam3)
        thickness = math.sqrt(lam3 / lam1)

    aspect_for_m = aspect if math.isfinite(aspect) else _ASPECT_THIN
    # Principal axes as columns, ordered major → minor.
    axes = evecs[:, ::-1]
    return ShapeReport(n, (lam1, lam2, lam3), aspect, thickness, axes,
                       suggested_m_star(aspect_for_m))
