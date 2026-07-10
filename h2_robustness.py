"""
╔══════════════════════════════════════════════════════════════════════╗
║  H₂ ROBUSTNESS — consensus-network robustness (3D)                  ║
╚══════════════════════════════════════════════════════════════════════╝

 Source (see sci.md §2 for the model and §4.3 for the 3D port): Young,
 Scardovi, Cavagna, Giardina & Leonard (2013), "Starling Flock Networks
 Manage Uncertainty in Consensus at Low Cost" (arXiv:1302.3195 / PLoS
 Comput Biol 9(1): e1002894).

 The paper's central result: starlings track a *fixed* number of nearest
 neighbours, and interacting with **six or seven** optimises the trade-off
 between group cohesion and individual sensing effort. It models heading
 agreement as noisy linear consensus on the interaction graph and measures
 robustness by the **H₂ norm** — the steady-state variance of disagreement
 driven by per-bird noise. The optimal neighbour count is shown to be
 *independent of flock size* and to depend instead on flock **shape**.

   L        = graph Laplacian of the m-nearest-neighbour graph
   0 = λ₁ ≤ λ₂ ≤ … ≤ λ_N   (Laplacian eigenvalues)
   H₂²      = (1 / 2N) · Σ_{i≥2} 1/λ_i          (smaller = more robust)

 This is a straight 3D port of the 2D extension — the maths is
 dimension-agnostic: the k-NN graph is built from 3D positions with
 scipy.spatial.cKDTree and the Laplacian spectrum from numpy.linalg.eigvalsh.

 Usage:
   from h2_robustness import h2_norm, cost_optimal_m, eta_of_m
──────────────────────────────────────────────────────────────────────
"""

import math

import numpy as np
from scipy.spatial import cKDTree


# ── Linear-algebra & coercion helpers ──────────────────────────────

def symmetric_eigenvalues(matrix):
    """Ascending eigenvalues of a real symmetric matrix (LAPACK eigvalsh)."""
    a = np.asarray(matrix, dtype=float)
    if a.size == 0:
        return []
    return np.linalg.eigvalsh(a).tolist()


def _as_xyz(p):
    """Coerce a bird / point to an (x, y, z) tuple (z defaults to 0)."""
    x = getattr(p, "pos", None)
    if x is not None:                      # a Boid3D with .pos array
        return (float(p.pos[0]), float(p.pos[1]), float(p.pos[2]))
    if hasattr(p, "x"):
        return (p.x, p.y, getattr(p, "z", 0.0))
    return (p[0], p[1], p[2] if len(p) > 2 else 0.0)


# ══════════════════════════════════════════════════════════════════════
#  H₂ NORM — Laplacian spectrum of the m-nearest-neighbour graph
#  H₂² = (1/2N) Σ_{i≥2} 1/λ_i   (smaller = more robust; +inf if disconnected)
# ══════════════════════════════════════════════════════════════════════

def knn_laplacian(positions, m):
    """Symmetric graph Laplacian L = D − A of the m-nearest-neighbour
    graph over 3D positions. The directed k-NN relation is symmetrised
    (edge if *either* bird sees the other), matching the undirected
    consensus network in Young et al. Uses a k-d tree (O(N log N))."""
    pts = np.array([_as_xyz(p) for p in positions], dtype=float)
    n = len(pts)
    if n == 0:
        return np.zeros((0, 0))
    m = min(m, n - 1)
    if m < 1:
        return np.zeros((n, n))            # a lone bird has no neighbours

    tree = cKDTree(pts)
    _, idx = tree.query(pts, k=m + 1)      # col 0 is the point itself
    idx = np.atleast_2d(idx)

    adj = np.zeros((n, n), dtype=float)
    rows = np.repeat(np.arange(n), m)
    adj[rows, idx[:, 1:].reshape(-1)] = 1.0
    adj = np.maximum(adj, adj.T)           # symmetrise
    return np.diag(adj.sum(axis=1)) - adj


def h2_norm(positions, m):
    """H₂ robustness of the m-nearest-neighbour consensus network in 3D.

    Returns +inf for a disconnected graph (λ₂ ≈ 0 → the flock cannot reach
    consensus). Smaller values = more robust to sensing noise.
    """
    lap = knn_laplacian(positions, m)
    n = lap.shape[0]
    if n < 2:
        return 0.0
    eig = symmetric_eigenvalues(lap)
    acc = 0.0
    for lam in eig[1:]:                    # skip λ₁ ≈ 0 (consensus mode)
        if lam < 1e-6:
            return math.inf                # disconnected
        acc += 1.0 / lam
    return math.sqrt(acc / (2.0 * n))


# ══════════════════════════════════════════════════════════════════════
#  COST-OPTIMAL NEIGHBOUR COUNT — η(m) and m* = argmin J(m)=H₂(m)+cost·m
#  Young's headline result: the interior optimum lands at m* ≈ 6–7.
# ══════════════════════════════════════════════════════════════════════

def eta_of_m(positions, m, m0=None):
    """Marginal per-neighbour efficiency η(m) = [H₂(m−1) − H₂(m)] / 1 —
    the incremental robustness gained from the m-th neighbour. Falls
    toward zero as returns diminish (the basis for a finite optimum).
    +inf if the m-th neighbour first connects the graph."""
    if m0 is None:
        m0 = m - 1
    if m == m0:
        return 0.0
    h0, h1 = h2_norm(positions, m0), h2_norm(positions, m)
    if math.isinf(h0) and math.isfinite(h1):
        return math.inf
    if not (math.isfinite(h0) and math.isfinite(h1)):
        return 0.0
    return (h0 - h1) / (m - m0)


def cost_optimal_m(positions, sensing_cost=0.06, m_min=1, m_max=12):
    """Neighbour count minimising J(m) = H₂(m) + sensing_cost·m — Young et
    al.'s cohesion-vs-effort trade-off. For typical flocks the interior
    optimum lands at m* ≈ 6–7, reproducing the paper's headline result
    (raw H₂ alone always favours the maximum m)."""
    best_m, best_j = m_min, math.inf
    n = len(positions)
    hi = min(m_max, max(1, n - 1))
    for m in range(m_min, hi + 1):
        h = h2_norm(positions, m)
        if not math.isfinite(h):
            continue
        j = h + sensing_cost * m
        if j < best_j:
            best_j, best_m = j, m
    return best_m, best_j
