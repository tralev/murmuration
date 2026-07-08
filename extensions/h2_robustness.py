"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 6 — H₂ ROBUSTNESS METRIC  (consensus dynamics)             ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  Young, Scardovi, Cavagna, Giardina & Leonard (2013),
             "Starling flock networks manage uncertainty in consensus
             at low cost", PLoS Comput. Biol. 9(1): e1002894.

 Models heading consensus as a noisy linear system on the interaction
 graph and measures its robustness by the H₂ norm — the steady-state
 variance of the disagreement, driven by per-bird sensing noise:

   L        = graph Laplacian of the k-nearest-neighbour graph
   0 = λ₁ ≤ λ₂ ≤ … ≤ λ_N   (Laplacian eigenvalues)
   H₂²      = (1 / 2N) · Σ_{i≥2} 1/λ_i

 A larger H₂ means noise accumulates more — i.e. worse robustness — so
 flocks minimise it.  Young et al. show a topological interaction range
 of m ≈ 6–7 neighbours is near-optimal: enough to keep the algebraic
 connectivity λ₂ high without paying an O(m) sensing cost per bird.

   per-neighbour efficiency  η(m) = (robustness gain) / (sensing cost)
                                   ≈ [H₂(m₀) − H₂(m)] / (m − m₀)

 The k-nearest-neighbour graph is built with `scipy.spatial.cKDTree`
 (O(N log N)) and the Laplacian's eigenvalues come from
 `numpy.linalg.eigvalsh` (LAPACK, symmetric) — the right tools for
 the nearest-neighbour query and the symmetric eigenproblem.

 Usage:
   from extensions.h2_robustness import h2_norm, knn_laplacian, eta_of_m
──────────────────────────────────────────────────────────────────────
"""

import math

import numpy as np
from scipy.spatial import cKDTree


def symmetric_eigenvalues(matrix):
    """Ascending eigenvalues of a real symmetric matrix.

    Thin wrapper over `numpy.linalg.eigvalsh` (LAPACK), which exploits
    symmetry for accuracy and speed. Returns a plain list so callers stay
    numpy-agnostic.
    """
    a = np.asarray(matrix, dtype=float)
    if a.size == 0:
        return []
    return np.linalg.eigvalsh(a).tolist()


# ══════════════════════════════════════════════════════════════════════
#  Interaction graph → Laplacian → H₂
# ══════════════════════════════════════════════════════════════════════

def knn_laplacian(positions, m):
    """Symmetric graph Laplacian of the m-nearest-neighbour graph.

    The directed k-NN relation is symmetrised (an edge exists if either
    bird sees the other), matching the undirected consensus network in
    Young et al.  L = D − A with unit edge weights.

    Neighbour queries use a `scipy.spatial.cKDTree` (k-d tree, O(N log N))
    instead of a hand-built O(N²) distance matrix.

    Parameters
    ----------
    positions : list of (x, y[, z]) or objects with .x/.y[/.z]
    m         : topological neighbour count per bird

    Returns
    -------
    numpy.ndarray — the N×N Laplacian (float64).
    """
    pts = np.array([_as_tuple(p) for p in positions], dtype=float)
    n = len(pts)
    if n == 0:
        return np.zeros((0, 0))
    m = max(1, min(m, n - 1))

    # cKDTree.query with k = m+1 returns each point plus its m nearest
    # (column 0 is the point itself). Symmetrise the directed relation.
    tree = cKDTree(pts)
    _, idx = tree.query(pts, k=m + 1)
    idx = np.atleast_2d(idx)

    adj = np.zeros((n, n), dtype=float)
    rows = np.repeat(np.arange(n), m)
    cols = idx[:, 1:].reshape(-1)          # drop self-column
    adj[rows, cols] = 1.0
    adj = np.maximum(adj, adj.T)           # edge if either sees the other

    lap = np.diag(adj.sum(axis=1)) - adj
    return lap


def h2_norm(positions, m):
    """H₂ robustness of the m-nearest-neighbour consensus network.

    Returns +inf for a disconnected graph (λ₂ ≈ 0 → infinite variance),
    which correctly flags a flock that cannot reach consensus.

    Parameters
    ----------
    positions : list of positions (see knn_laplacian)
    m         : topological neighbour count

    Returns
    -------
    float — the H₂ norm (smaller = more robust); math.inf if disconnected.
    """
    lap = knn_laplacian(positions, m)
    n = lap.shape[0]
    if n < 2:
        return 0.0
    eig = symmetric_eigenvalues(lap)
    # Skip λ₁ ≈ 0 (the consensus mode). A near-zero λ₂ ⇒ disconnected.
    acc = 0.0
    for lam in eig[1:]:
        if lam < 1e-6:
            return math.inf
        acc += 1.0 / lam
    return math.sqrt(acc / (2.0 * n))


def eta_of_m(positions, m, m0=None):
    """Per-neighbour efficiency η(m): robustness gained per extra
    neighbour.  Marginal by default (m0 = m − 1), so it is the discrete
    derivative −ΔH₂/Δm — the incremental value of the m-th neighbour:

        η(m) = [H₂(m0) − H₂(m)] / (m − m0)

    η is large while extra neighbours still help and falls toward zero
    as returns diminish.  Special case: if the m0 graph is disconnected
    (H₂ = ∞) but the m graph is connected, η is +∞ — connecting the
    consensus network is maximally valuable.  Returns 0.0 when both are
    non-finite or m == m0.
    """
    if m0 is None:
        m0 = m - 1
    if m == m0:
        return 0.0
    h_m0 = h2_norm(positions, m0)
    h_m = h2_norm(positions, m)
    if math.isinf(h_m0) and math.isfinite(h_m):
        return math.inf   # graph just became connected
    if not (math.isfinite(h_m0) and math.isfinite(h_m)):
        return 0.0
    return (h_m0 - h_m) / (m - m0)


def optimal_m(positions, m_min=1, m_max=12):
    """Scan m and return the m minimising raw H₂.

    Note: raw H₂ decreases monotonically with connectivity, so this
    almost always returns m_max — it is the most-robust range *ignoring
    sensing cost*.  For the Young et al. m* ≈ 6–7 result, which balances
    robustness against the O(m) cost of tracking neighbours, use
    cost_optimal_m().

    Returns
    -------
    (best_m, best_h2) tuple.
    """
    best_m, best_h = m_min, math.inf
    n = len(positions)
    hi = min(m_max, max(1, n - 1))
    for m in range(m_min, hi + 1):
        h = h2_norm(positions, m)
        if h < best_h:
            best_h, best_m = h, m
    return best_m, best_h


def cost_optimal_m(positions, sensing_cost=0.06, m_min=1, m_max=12):
    """Optimal neighbour count under a sensing-cost/benefit trade-off.

    Young et al. frame each tracked neighbour as an O(m) sensing cost
    weighed against the robustness benefit.  We minimise a combined
    objective

        J(m) = H₂(m) + sensing_cost × m

    whose interior minimum reproduces the empirical m* ≈ 6–7 for typical
    flocks (raw H₂ alone would always pick the maximum m).  Increase
    *sensing_cost* to model costlier sensing → smaller m*.

    Returns
    -------
    (best_m, best_J) tuple.
    """
    best_m, best_j = m_min, math.inf
    n = len(positions)
    hi = min(m_max, max(1, n - 1))
    for m in range(m_min, hi + 1):
        h = h2_norm(positions, m)
        if not math.isfinite(h):
            continue   # disconnected — skip
        j = h + sensing_cost * m
        if j < best_j:
            best_j, best_m = j, m
    return best_m, best_j


# ── helpers ─────────────────────────────────────────────────────────

def _as_tuple(p):
    x = getattr(p, "x", None)
    if x is not None:
        y = p.y
        z = getattr(p, "z", None)
        return (x, y) if z is None else (x, y, z)
    return tuple(p)
