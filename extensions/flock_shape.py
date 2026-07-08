"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 6 — FLOCK SHAPE ANALYSIS                                   ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  Young et al. (2013); Ballerini et al. (2008).

 The optimal topological interaction range depends on flock *shape*:
 Young et al. report m* ≈ 6.05 for longitudinal (thin) flocks and
 m* ≈ 9.78 for transverse (thick) flocks — thinner flocks need fewer
 neighbours to stay robust.  To connect that to a live simulation we
 need to measure the flock's shape each frame.

 This module extracts shape descriptors from the flock's positions via
 principal component analysis of the position covariance:

   • principal axes & their variances (eigenvalues of the 2×2 covariance)
   • aspect ratio   = √(λ_major / λ_minor)         (elongation)
   • orientation    = angle of the major axis
   • area           = convex-hull area (reused from correlation_time)
   • suggested m*   = interpolated between the thin/thick endpoints

 The covariance and its eigen-decomposition use `numpy` (`np.cov`,
 `np.linalg.eigh`); the hull area comes from `correlation_time`
 (which delegates to `scipy.spatial.ConvexHull`).

 Usage:
   from extensions.flock_shape import analyze_shape, ShapeReport
──────────────────────────────────────────────────────────────────────
"""

import math

import numpy as np

from extensions.correlation_time import convex_hull_area


# ── Young et al. optimal-m endpoints (by flock shape) ───────────────

M_STAR_LONGITUDINAL = 6.05   # thin / elongated flocks
M_STAR_TRANSVERSE   = 9.78   # thick / round flocks
# Aspect ratios these endpoints are anchored to (elongated vs round).
_ASPECT_THIN  = 3.0
_ASPECT_ROUND = 1.0


class ShapeReport:
    """Immutable-ish bundle of flock shape descriptors."""

    __slots__ = ("count", "aspect_ratio", "orientation", "major_var",
                 "minor_var", "area", "suggested_m")

    def __init__(self, count, aspect_ratio, orientation, major_var,
                 minor_var, area, suggested_m):
        self.count = count
        self.aspect_ratio = aspect_ratio      # ≥ 1.0 (major/minor)
        self.orientation = orientation        # radians, major-axis angle
        self.major_var = major_var
        self.minor_var = minor_var
        self.area = area                      # convex-hull area
        self.suggested_m = suggested_m        # interpolated m*

    def __repr__(self):
        return (f"ShapeReport(count={self.count}, "
                f"aspect={self.aspect_ratio:.2f}, "
                f"orient={math.degrees(self.orientation):.0f}°, "
                f"area={self.area:.0f}, m*={self.suggested_m:.1f})")


def suggested_m_star(aspect_ratio: float) -> float:
    """Interpolate Young et al.'s optimal m* from the aspect ratio.

    Round flocks (aspect ≈ 1) → ~9.78; thin flocks (aspect ≥ 3) →
    ~6.05; clamped outside that range.
    """
    t = (aspect_ratio - _ASPECT_ROUND) / (_ASPECT_THIN - _ASPECT_ROUND)
    t = max(0.0, min(1.0, t))
    return M_STAR_TRANSVERSE + t * (M_STAR_LONGITUDINAL - M_STAR_TRANSVERSE)


def analyze_shape(positions) -> ShapeReport:
    """Compute shape descriptors for a set of flock positions.

    Parameters
    ----------
    positions : list of (x, y) or objects with .x/.y

    Returns
    -------
    ShapeReport — degenerate (aspect 1.0, area 0) for < 3 points.
    """
    pts = np.array([_as_xy(p) for p in positions], dtype=float)
    n = len(pts)
    if n < 3:
        return ShapeReport(n, 1.0, 0.0, 0.0, 0.0, 0.0,
                           M_STAR_TRANSVERSE)

    # Population covariance (bias=1 → divide by N, matching the previous
    # hand-rolled version) and its symmetric eigen-decomposition.
    cov = np.cov(pts, rowvar=False, bias=True)
    evals, evecs = np.linalg.eigh(cov)     # ascending eigenvalues
    lam_minor, lam_major = float(evals[0]), float(evals[1])
    major_axis = evecs[:, 1]               # eigenvector for λ_major
    angle = math.atan2(major_axis[1], major_axis[0])
    # Fold orientation into (−π/2, π/2] — axes are undirected.
    if angle > math.pi / 2:
        angle -= math.pi
    elif angle <= -math.pi / 2:
        angle += math.pi

    if lam_minor < 1e-9:
        aspect = float("inf") if lam_major > 1e-9 else 1.0
    else:
        aspect = math.sqrt(lam_major / lam_minor)

    area = convex_hull_area(pts.tolist())
    # For m* interpolation an infinite aspect just pins to the thin end.
    aspect_for_m = aspect if math.isfinite(aspect) else _ASPECT_THIN
    return ShapeReport(n, aspect, angle, lam_major, lam_minor, area,
                       suggested_m_star(aspect_for_m))


# ── helpers ─────────────────────────────────────────────────────────

def _as_xy(p):
    x = getattr(p, "x", None)
    if x is not None:
        return (x, p.y)
    return (p[0], p[1])
