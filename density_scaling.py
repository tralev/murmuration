"""
╔══════════════════════════════════════════════════════════════════════╗
║  DENSITY SCALING — does marginal opacity hold across flock size N?    ║
╚══════════════════════════════════════════════════════════════════════╝

 Pearce et al. (2014) report that marginal opacity is **N-independent**: a
 bird need not know the flock size. The mechanism is a density that self-
 regulates as

     ρ(N) ~ N^(−1/(d−1))        (3D: ρ ~ N^(−1/2),  linear size L ~ N^(+1/2))

 so the optical depth through the flock, ρ·L, and hence the external opacity
 Θ′, stay constant as N grows.

 This module measures how the *simulated* flock's density actually scales with
 N and fits the exponent, so the claim can be checked rather than asserted.

 Two things matter for an honest measurement:

   1. **Open boundary.** On the toroidal domain every bird is interior — there
      is no light–dark silhouette edge — so the flock is forced to the fixed
      domain volume and ρ ∝ N trivially. We flip ``boid_3d.OPEN_BOUNDARY`` on
      (via :func:`open_boundary`) so the flock floats in free space and can
      self-size.
   2. **Straggler-robust statistics.** A free flock sheds a few birds that fly
      off forever; a raw convex hull is dominated by them. We use the median
      k-nearest-neighbour spacing (a purely local length scale) and a gyration
      radius computed after trimming the farthest tail.

 What the current model shows (see ``sci.md`` §4.9): `δ̂` now carries Pearce's
 density-regulation signal — it is the boundary-length-weighted mean direction
 `Σ sinα·d̂ / Σ sinα`, whose magnitude vanishes for a bird deep inside a dark
 flock and approaches 1 at the silhouette edge (`occlusion_3d`). This improves
 the measured open-boundary density exponent (from `≈ +0.5` under the earlier
 unit-normalised `δ̂` toward `≈ +0.4`, i.e. less over-condensation) but does not
 yet reach `ρ ~ N^(−1/2)`; on the bounded toroidal viewer the flock cannot
 resize at all (`ρ ∝ N`), and in free flight it sheds stragglers at the
 canonical `φp`. This tool quantifies exactly that remaining gap.

 CLI:  ``python density_scaling.py``  (runs the default sweep, prints a table).

 Dependencies:  numpy, scipy, boid_3d, spatial_grid_3d, metrics_3d, flock_core
──────────────────────────────────────────────────────────────────────
"""

import os
import math
import random
from contextlib import contextmanager

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
from scipy.spatial import cKDTree

import boid_3d
from boid_3d import Boid3D
from spatial_grid_3d import SpatialGrid3D
from metrics_3d import external_opacity
from flock_core import Config, WIDTH, HEIGHT, DEPTH

# Pearce's ideal 3D scaling exponents (d = 3 → 1/(d−1) = 1/2).
IDEAL_DENSITY_EXPONENT = -0.5      # ρ ~ N^(−1/2)
IDEAL_SIZE_EXPONENT = +0.5         # L ~ N^(+1/2)


@contextmanager
def open_boundary(enabled=True):
    """Temporarily switch the boids to free-flight (no toroidal wrap) so the
    flock can self-size, restoring the previous setting afterwards."""
    prev = boid_3d.OPEN_BOUNDARY
    boid_3d.OPEN_BOUNDARY = enabled
    try:
        yield
    finally:
        boid_3d.OPEN_BOUNDARY = prev


# ── Robust geometric estimators ────────────────────────────────────────────

def local_spacing(positions, k=7):
    """Median distance from a bird to its *k*-th nearest neighbour — a local
    length scale that ignores far-flung stragglers. Returns 0.0 for < k+1
    birds."""
    pts = np.asarray(positions, dtype=float)
    n = len(pts)
    if n < k + 1:
        return 0.0
    tree = cKDTree(pts)
    dist, _ = tree.query(pts, k=k + 1)      # column 0 is the bird itself
    return float(np.median(dist[:, k]))


def gyration_radius(positions, keep=0.85):
    """RMS distance of birds from a robust centre, after dropping the farthest
    ``1 − keep`` fraction (stragglers). A robust linear flock size.

    The centre is the per-axis *median*, not the mean: a single bird that has
    flown far off would drag the mean (and hence every distance) with it, so a
    mean centre plus distance-trim still measures the outlier. The median centre
    is unmoved by such a bird, so trimming then genuinely removes it."""
    pts = np.asarray(positions, dtype=float)
    if len(pts) < 2:
        return 0.0
    centre = np.median(pts, axis=0)
    r = np.linalg.norm(pts - centre, axis=1)
    if 0.0 < keep < 1.0:
        thr = np.quantile(r, keep)
        r = r[r <= thr]
    return float(np.sqrt(np.mean(r ** 2))) if len(r) else 0.0


def number_density(positions, keep=0.85):
    """Bird count per unit volume of the (trimmed) gyration sphere."""
    pts = np.asarray(positions, dtype=float)
    n = len(pts)
    rg = gyration_radius(pts, keep)
    if rg <= 0.0:
        return 0.0
    kept = max(1, int(round(n * keep)))
    vol = (4.0 / 3.0) * math.pi * rg ** 3
    return kept / vol if vol > 0 else 0.0


# ── Simulation driver ───────────────────────────────────────────────────────

def settle_flock(n, phi_p=None, phi_a=None, frames=700, seed=0,
                 init_std=120.0):
    """Run *n* birds from a compact blob to (near) steady state and return the
    settled positions. Runs in free flight so the flock self-sizes; the caller
    is responsible for the :func:`open_boundary` context if that is desired."""
    random.seed(seed)
    np.random.seed(seed)
    rng = np.random.default_rng(seed)
    cfg = Config()
    cfg.num_boids = n
    if phi_p is not None:
        cfg.phi_p = phi_p
    if phi_a is not None:
        cfg.phi_a = phi_a
    grid = SpatialGrid3D()
    flock = [Boid3D() for _ in range(n)]
    centre = np.array([WIDTH / 2, HEIGHT / 2, DEPTH / 2])
    for b in flock:
        b.pos = (centre + rng.normal(0, init_std, 3)).astype(np.float32)
    for _ in range(frames):
        grid.rebuild(flock)
        for b in flock:
            b.flock(flock, cfg, grid)
        for b in flock:
            b.update()
    return np.array([b.pos for b in flock], dtype=float)


def measure_point(n, phi_p=None, frames=700, seeds=(0,), tail=40):
    """Average the geometric observables for one flock size *n* over the last
    *tail* frames and over *seeds*. Returns a dict."""
    spacing, density, size, theta_ext = [], [], [], []
    for seed in seeds:
        random.seed(seed)
        np.random.seed(seed)
        rng = np.random.default_rng(seed)
        cfg = Config()
        cfg.num_boids = n
        if phi_p is not None:
            cfg.phi_p = phi_p
        grid = SpatialGrid3D()
        flock = [Boid3D() for _ in range(n)]
        centre = np.array([WIDTH / 2, HEIGHT / 2, DEPTH / 2])
        for b in flock:
            b.pos = (centre + rng.normal(0, 120.0, 3)).astype(np.float32)
        for f in range(frames):
            grid.rebuild(flock)
            for b in flock:
                b.flock(flock, cfg, grid)
            for b in flock:
                b.update()
            if f >= frames - tail:
                pts = np.array([b.pos for b in flock], dtype=float)
                spacing.append(local_spacing(pts))
                density.append(number_density(pts))
                size.append(gyration_radius(pts))
                theta_ext.append(external_opacity(flock))
    return {
        "n": n,
        "spacing": float(np.median(spacing)),
        "density": float(np.median(density)),
        "size": float(np.median(size)),
        "theta_ext": float(np.median(theta_ext)),
    }


def _fit_exponent(ns, ys):
    """Slope of log(y) vs log(N); NaN if not enough positive points."""
    ns = np.asarray(ns, dtype=float)
    ys = np.asarray(ys, dtype=float)
    ok = (ns > 0) & (ys > 0)
    if ok.sum() < 2:
        return float("nan")
    return float(np.polyfit(np.log(ns[ok]), np.log(ys[ok]), 1)[0])


def measure_scaling(n_values=(60, 120, 240, 360), phi_p=None, frames=700,
                    seeds=(0,), open_flight=True):
    """Sweep flock size and fit the density/size scaling exponents.

    Returns a dict with per-N ``points`` and the fitted ``density_exponent``
    and ``size_exponent`` (compare against :data:`IDEAL_DENSITY_EXPONENT` and
    :data:`IDEAL_SIZE_EXPONENT`)."""
    with open_boundary(open_flight):
        points = [measure_point(n, phi_p=phi_p, frames=frames, seeds=seeds)
                  for n in n_values]
    ns = [p["n"] for p in points]
    return {
        "points": points,
        "density_exponent": _fit_exponent(ns, [p["density"] for p in points]),
        "size_exponent": _fit_exponent(ns, [p["size"] for p in points]),
        "ideal_density_exponent": IDEAL_DENSITY_EXPONENT,
        "ideal_size_exponent": IDEAL_SIZE_EXPONENT,
    }


def format_report(result):
    """Render a :func:`measure_scaling` result as a readable table."""
    lines = [
        "Density scaling (open boundary, free-flight self-sizing)",
        f"{'N':>5} {'spacing':>9} {'density(1e6)':>13} {'size Rg':>9} "
        f"{'Theta_ext':>10}",
    ]
    for p in result["points"]:
        lines.append(
            f"{p['n']:>5} {p['spacing']:>9.1f} {p['density'] * 1e6:>13.3f} "
            f"{p['size']:>9.1f} {p['theta_ext']:>10.3f}")
    de, se = result["density_exponent"], result["size_exponent"]
    lines += [
        "",
        f"fit  density ~ N^{de:+.3f}   (Pearce marginal target "
        f"{result['ideal_density_exponent']:+.3f})",
        f"fit  size Rg ~ N^{se:+.3f}   (Pearce marginal target "
        f"{result['ideal_size_exponent']:+.3f})",
        "",
        "N-independent marginal opacity needs density ~ N^(-1/2); a fixed-",
        "spacing (constant-density) flock instead gives density ~ N^0. See",
        "sci.md §4.9 for why the current cohesion+steric δ̂ lands near the",
        "latter and what a density-regulating δ̂ would change.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_report(measure_scaling()))
