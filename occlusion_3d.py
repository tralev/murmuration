"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D SPHERICAL-CAP OCCLUSION — physically-correct projection model    ║
╚══════════════════════════════════════════════════════════════════════╝

 Source (see sci/): Pearce, Miller, Rowlands & Turner (2014), "The Role of
 Projection in the Control of Bird Flocks" (arXiv:1407.2414). The SI
 Appendix states the model "easily can be extended to 3D flocks, in which
 the light–dark [boundaries] become curves on the surface of a sphere."

 This replaces the previous XY-plane *approximation* (which projected all
 neighbours onto the horizontal plane and patched the missing Z direction
 with an ad-hoc "altitude cohesion" nudge) with the genuine 3D projection:
 each neighbour subtends a circular **cap** on the observer's view sphere,
 and the dark (occluded) region is the union of those caps.

 ── Geometry ────────────────────────────────────────────────────────
   Neighbour j at distance d with body radius b subtends a cap centred on
   the unit direction d̂ = (r_j − r_i)/|r_j − r_i| with angular radius
       α = asin(b / d)                              (Pearce Eq. SI-3)
   and solid angle  Ω = 2π(1 − cos α).  A view direction v̂ is in the cap
   iff v̂ · d̂ ≥ cos α.

 ── Why analytic, not a Fibonacci-lattice z-buffer ──────────────────
   The removed three_d.py discretised the sphere with ~80 Fibonacci points
   and z-buffered. That fails at this simulation's density: with b = 3 in a
   1000×700×400 volume, a typical neighbour subtends only 1–6°, a cap that
   covers well under one lattice point, so Θ and δ̂ collapse to zero. The 2D
   model avoided this only because a 1-D angular interval is continuous.
   The cap algebra below is exact and **density-independent** — no lattice
   resolution floor — which is both more correct and cheaper.

 ── Visibility, Θ, and δ̂ (faithful Pearce) ─────────────────────────
   • Visible set: process neighbours closest-first; a neighbour is occluded
     when the direction to it falls inside a *nearer* visible bird's cap
     (v̂ · d̂_k ≥ cos α_k) — i.e. it sits directly behind a closer bird.
   • Θ (internal opacity) = 1 − Π_visible (1 − Ω_j/4π): the probabilistic
     union of the visible caps' sky-fractions. Hidden caps lie inside
     visible ones and add nothing. Saturates toward 1 when surrounded.
   • δ̂ = "resolved vector sum of all the light–dark domain boundaries"
     (Pearce). The boundary of cap j is a circle whose resolved direction
     is d̂_j, with boundary length ∝ sin α_j; so δ̂ = normalise(Σ_visible
     sin α_j · d̂_j). This is cohesive — the bird is drawn toward the
     silhouette edges — and occlusion gates it (hidden birds drop out),
     which is the mechanism behind the paper's *marginal opacity*.
     (Averaging the *unoccluded* sky instead, as three_d.py did, gives the
     opposite sign — a flee-to-open-sky separation force.)

 Dependencies:  numpy, flock_core (BOID_SIZE)
──────────────────────────────────────────────────────────────────────
"""

import math

import numpy as np

from flock_core import BOID_SIZE


def fibonacci_sphere(n: int = 256) -> np.ndarray:
    """*n* near-uniform unit vectors on the sphere via the Fibonacci
    (golden-angle) spiral. Kept as a utility (used for visualisation and
    tests); the occlusion itself is analytic, not lattice-based."""
    if n <= 0:
        return np.zeros((0, 3))
    if n == 1:
        return np.array([[0.0, 0.0, 1.0]])
    ga = math.pi * (3.0 - math.sqrt(5.0))
    i = np.arange(n)
    y = 1.0 - (i / (n - 1)) * 2.0
    r = np.sqrt(np.maximum(0.0, 1.0 - y * y))
    theta = ga * i
    return np.stack([np.cos(theta) * r, y, np.sin(theta) * r], axis=1)


def _as_pos(p):
    pos = getattr(p, "pos", None)
    return np.asarray(pos if pos is not None else p, dtype=float)


def spherical_cap_occlusion(observer, neighbours):
    """Compute the 3D projection quantities for one observer bird.

    Parameters
    ----------
    observer   : the viewing bird (needs numpy length-3 ``.pos``)
    neighbours : iterable of candidate birds (each with ``.pos``); the
                 observer itself is ignored if present.

    Returns
    -------
    (delta, visible, theta)
      delta   : numpy (3,) — δ̂, the normalised resolved vector to the
                light–dark domain boundaries (0-vector if none / fully
                surrounded — no projection information).
      visible : list[(bird, dist)] — neighbours not hidden directly behind
                a nearer bird, closest first.
      theta   : float — internal opacity Θ ∈ [0, 1].
    """
    obs_pos = _as_pos(observer)

    # ── Gather neighbour displacements (vectorised) ─────────────────
    others, diffs = [], []
    for other in neighbours:
        if other is observer:
            continue
        diff = _as_pos(other) - obs_pos
        d = float(np.linalg.norm(diff))
        if d < 1e-6:
            continue
        others.append(other)
        diffs.append(diff)

    if not others:
        return np.zeros(3), [], 0.0

    diffs = np.asarray(diffs)                                # (K, 3)
    dists = np.linalg.norm(diffs, axis=1)                    # (K,)
    dirs = diffs / dists[:, None]                            # unit directions
    alphas = np.arcsin(np.minimum(BOID_SIZE / dists, 1.0))
    cos_a = np.cos(alphas)
    sin_a = np.sin(alphas)
    omega = 2.0 * math.pi * (1.0 - cos_a)                   # cap solid angles

    order = np.argsort(dists)                                # closest first

    # ── Closest-first visibility: a bird is hidden when its direction
    #    lies inside a nearer *visible* bird's cap. The dot-product test
    #    against all visible caps at once is a single matmul. ─────────
    K = len(order)
    vis_dirs = np.empty((K, 3))
    vis_cos = np.empty(K)
    n_vis = 0
    visible = []
    delta = np.zeros(3)
    one_minus = 1.0                                          # Π(1 − Ω/4π)
    for i in order:
        di = dirs[i]
        if n_vis and np.any(vis_dirs[:n_vis] @ di >= vis_cos[:n_vis]):
            continue                                         # behind a nearer cap
        visible.append((others[i], float(dists[i])))
        vis_dirs[n_vis] = di
        vis_cos[n_vis] = cos_a[i]
        n_vis += 1
        delta += sin_a[i] * di                              # boundary weight
        one_minus *= (1.0 - omega[i] / (4.0 * math.pi))

    theta = 1.0 - one_minus

    norm = float(np.linalg.norm(delta))
    delta = delta / norm if norm > 1e-9 else np.zeros(3)

    return delta, visible, theta
