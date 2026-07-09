"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D SPHERICAL-CAP OCCLUSION — physically-correct projection model    ║
╚══════════════════════════════════════════════════════════════════════╝

 Source (see sci.md): Pearce, Miller, Rowlands & Turner (2014), "The Role of
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
     is d̂_j, with boundary length ∝ sin α_j; so the resolved boundary is
     Σ_visible sin α_j · d̂_j. We divide by the *total* boundary length
     Σ sin α_j (not by the vector's own magnitude), so δ̂ is a boundary-
     length-weighted **mean direction** whose magnitude lives in [0, 1]:
     ≈ 1 when the boundaries all point one way (a bird at the silhouette
     edge) and → 0 when they cancel (a bird deep inside, fully dark). That
     surviving magnitude is what makes *marginal opacity* emerge and be
     N-independent: an interior bird feels almost no cohesion and spreads
     until it nears the edge, where δ̂ grows and draws it back, so the flock
     self-regulates to a light–dark balance rather than a fixed spacing.
     Occlusion gates the sum (hidden birds drop out). (Averaging the
     *unoccluded* sky instead, as three_d.py did, gives the opposite sign —
     a flee-to-open-sky separation force.)

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


def _heading(bird):
    """Unit heading of a bird from its velocity; +X if (near-)stationary."""
    v = getattr(bird, "vel", None)
    if v is None:
        return np.array([1.0, 0.0, 0.0])
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else np.array([1.0, 0.0, 0.0])


def spherical_cap_occlusion(observer, neighbours, blind_cos=None, anisotropy=1.0):
    """Compute the 3D projection quantities for one observer bird.

    Parameters
    ----------
    observer   : the viewing bird (numpy length-3 ``.pos``, ``.vel``)
    neighbours : iterable of candidate birds (each with ``.pos``/``.vel``);
                 the observer itself is ignored if present.
    blind_cos  : if not None, cos of the blind half-angle — a neighbour whose
                 direction lies within the rear cone (`d̂·(−ĥ) ≥ blind_cos`,
                 ĥ = observer heading) is invisible (Pearce SI "blind angles").
    anisotropy : axis ratio `a/b ≥ 1` of a prolate spheroid body elongated
                 along each neighbour's heading (Pearce SI "anisotropic
                 bodies"). 1.0 = isotropic (the default). The projected
                 silhouette radius then depends on the viewing angle.

    Returns
    -------
    (delta, visible, theta)
      delta   : numpy (3,) — δ̂, the boundary-length-weighted mean direction
                to the light–dark domain boundaries. |δ̂| ∈ [0, 1]: near 1 at
                the silhouette edge, → 0 when fully surrounded (boundaries
                cancel) or when there are no visible neighbours. The magnitude
                carries the density-regulation signal, so callers must use δ̂
                as-is (do not renormalise it).
      visible : list[(bird, dist)] — neighbours not hidden directly behind
                a nearer bird, closest first.
      theta   : float — internal opacity Θ ∈ [0, 1].
    """
    obs_pos = _as_pos(observer)
    neg_heading = -_heading(observer) if blind_cos is not None else None

    # ── Gather neighbour displacements (vectorised) ─────────────────
    others, diffs, headings = [], [], []
    for other in neighbours:
        if other is observer:
            continue
        diff = _as_pos(other) - obs_pos
        d = float(np.linalg.norm(diff))
        if d < 1e-6:
            continue
        # Blind-angle filter: a bird directly behind the observer is unseen.
        if blind_cos is not None and float((diff / d) @ neg_heading) >= blind_cos:
            continue
        others.append(other)
        diffs.append(diff)
        if anisotropy != 1.0:
            headings.append(_heading(other))

    if not others:
        return np.zeros(3), [], 0.0

    diffs = np.asarray(diffs)                                # (K, 3)
    dists = np.linalg.norm(diffs, axis=1)                    # (K,)
    dirs = diffs / dists[:, None]                            # unit directions

    # ── Effective body radius (anisotropic bodies) ──────────────────
    #  A prolate spheroid with semi-major a = b·anisotropy along the
    #  neighbour's heading and semi-minor b: seen broadside it spans a
    #  (large), end-on it spans b (small). b_eff = √((a·sinψ)²+(b·cosψ)²)
    #  with ψ the angle between the view direction and the neighbour axis.
    if anisotropy != 1.0:
        hd = np.asarray(headings)                           # (K, 3)
        cos_psi = np.abs(np.sum(dirs * hd, axis=1))         # |d̂·ĥ_j|
        sin_psi = np.sqrt(np.maximum(0.0, 1.0 - cos_psi ** 2))
        a = BOID_SIZE * anisotropy
        b_eff = np.sqrt((a * sin_psi) ** 2 + (BOID_SIZE * cos_psi) ** 2)
    else:
        b_eff = BOID_SIZE

    alphas = np.arcsin(np.minimum(b_eff / dists, 1.0))
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
    boundary_len = 0.0                                       # Σ sinα over visible
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
        boundary_len += float(sin_a[i])
        one_minus *= (1.0 - omega[i] / (4.0 * math.pi))

    theta = 1.0 - one_minus

    # δ̂ is normalised by the TOTAL boundary length Σ sinα, *not* by its own
    # vector magnitude — see the module header. The result lives in [0, 1]:
    # ≈ 1 when the light–dark boundaries all resolve one way (a bird at the
    # silhouette edge) and → 0 when they cancel (a bird deep inside, fully
    # dark). That magnitude is Pearce's density-regulation signal: an interior
    # bird feels almost no cohesion and drifts apart until it nears the edge,
    # where δ̂ grows and pulls it back — so the flock settles at *marginal
    # opacity* rather than a fixed spacing. Normalising to unit magnitude (the
    # earlier code) discarded this and gave every bird full cohesion, yielding
    # a constant-density flock whose opacity scaled with N.
    delta = delta / boundary_len if boundary_len > 1e-9 else np.zeros(3)

    return delta, visible, theta
