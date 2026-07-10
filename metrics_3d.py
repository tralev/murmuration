"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D FLOCK METRICS — scientific observables for the 3D simulation    ║
╚══════════════════════════════════════════════════════════════════════╝

 Ports the 2D metrics core to the 3D (numpy Vec3) stack, implementing the
 observables the founding papers actually measure. Sources (see sci.md §1.3
 for the observables and §4.2 for their 3D forms):

   • Pearce, Miller, Rowlands & Turner (2014), "The Role of Projection in
     the Control of Bird Flocks" (arXiv:1407.2414):
       - internal opacity  Θ   — the fraction of a *typical bird's* view
         occluded by other birds. Real flocks are "marginally opaque":
         the paper fits Θ' ≈ N(µ = 0.30, σ² = 0.059) across 118 flocks.
       - external opacity  Θ'  — the fraction an *outside observer* sees
         occluded (their Fig. 3 quantity).
       - order parameter    α   — |Σ v̂| / N, the flock's net polarisation
         (their Fig. 2e, "mass of the swarm normalised by speed").
   • Standard collective-motion diagnostics also reported by Pearce:
       - angular momentum   L   — mean |r × v| about the centre of mass,
         distinguishing a milling vortex from a polarised stream.
       - dispersion        σ_r  — mean distance from the centre of mass.

 All metrics are exponential-moving-average smoothed so the on-screen
 readout is stable frame to frame. The flock is duck-typed: only
 ``.pos`` / ``.vel`` (numpy length-3) and ``.last_theta`` are read.

 Dependencies:  numpy, flock_core (V0, BOID_SIZE, DEPTH, MODE_PROJECTION)
──────────────────────────────────────────────────────────────────────
"""

import numpy as np

from flock_core import V0, BOID_SIZE, WIDTH, HEIGHT, DEPTH, MODE_PROJECTION


# Marginal-opacity reference from Pearce et al. Fig. 3d (µ of the fitted
# Gaussian) — used only as a documented target, not enforced.
MARGINAL_OPACITY_MEAN = 0.30


# ══════════════════════════════════════════════════════════════════════
#  OBSERVABLES — polarisation & opacity  (Pearce §1.3, §4.2)
# ══════════════════════════════════════════════════════════════════════

def order_parameter(flock) -> float:
    """Polarisation α = |mean(v̂)| ∈ [0, 1].

    1.0 when every bird points the same way (a coherent stream); ~0 for
    disordered or purely rotational (milling) motion. Pearce Fig. 2e.
    """
    n = len(flock)
    if n == 0:
        return 0.0
    acc = np.zeros(3)
    for b in flock:
        v = np.asarray(b.vel, dtype=float)
        s = np.linalg.norm(v)
        if s > 1e-9:
            acc += v / s
    return float(np.linalg.norm(acc) / n)


def internal_opacity(flock) -> float:
    """Mean internal opacity Θ = ⟨Θ_i⟩ over the flock.

    Θ_i is cached on each bird as ``last_theta`` during the projection
    step (flocking_modes_3d.flock_projection_3d). In SPATIAL mode no projection
    runs, so this reflects the last projection pass (or 0). Pearce's
    marginally-opaque flocks sit near MARGINAL_OPACITY_MEAN.
    """
    n = len(flock)
    if n == 0:
        return 0.0
    return float(sum(getattr(b, "last_theta", 0.0) for b in flock) / n)


def external_opacity(flock, observer_axis=0, grid=64) -> float:
    """External opacity Θ' — fraction of the flock's silhouette an outside
    observer sees covered by birds.

    The 3D generalisation of the 2D "fraction of sky occluded": project
    every bird onto the plane perpendicular to *observer_axis* (default X,
    matching the 2D distant-observer convention), rasterise each bird as a
    disk of radius BOID_SIZE onto a coarse grid spanning the flock's
    projected extent, and return covered_cells / total_cells. Rasterising
    the *union* avoids double-counting overlapping birds.

    Parameters
    ----------
    flock         : birds with numpy length-3 ``.pos``
    observer_axis : 0/1/2 — axis the observer looks along (projected out)
    grid          : rasterisation resolution per side

    Returns
    -------
    float in [0, 1]; 0 for an empty or degenerate flock.
    """
    n = len(flock)
    if n < 2:
        return 0.0
    # The two axes that remain after projecting out the observer axis.
    ax = [i for i in range(3) if i != observer_axis]
    pts = np.array([[b.pos[ax[0]], b.pos[ax[1]]] for b in flock], dtype=float)

    lo = pts.min(axis=0) - BOID_SIZE
    hi = pts.max(axis=0) + BOID_SIZE
    span = hi - lo
    if span[0] <= 0 or span[1] <= 0:
        return 0.0

    canvas = np.zeros((grid, grid), dtype=bool)
    # Cell size in world units; the disk radius in cells (per axis).
    cell = span / grid
    ru = max(1, int(round(BOID_SIZE / cell[0])))
    rv = max(1, int(round(BOID_SIZE / cell[1])))

    # Precompute a disk stamp in cell space.
    yy, xx = np.ogrid[-rv:rv + 1, -ru:ru + 1]
    stamp = (xx / max(ru, 1)) ** 2 + (yy / max(rv, 1)) ** 2 <= 1.0

    for p in pts:
        cu = int((p[0] - lo[0]) / span[0] * (grid - 1))
        cv = int((p[1] - lo[1]) / span[1] * (grid - 1))
        u0, u1 = cu - ru, cu + ru + 1
        v0, v1 = cv - rv, cv + rv + 1
        # Clip the stamp to the canvas bounds.
        su0, sv0 = max(0, -u0), max(0, -v0)
        u0, v0 = max(0, u0), max(0, v0)
        u1, v1 = min(grid, u1), min(grid, v1)
        if u1 <= u0 or v1 <= v0:
            continue
        canvas[v0:v1, u0:u1] |= stamp[sv0:sv0 + (v1 - v0), su0:su0 + (u1 - u0)]

    return float(canvas.sum()) / (grid * grid)


# ══════════════════════════════════════════════════════════════════════
#  KINEMATIC DIAGNOSTICS — momentum & spread
# ══════════════════════════════════════════════════════════════════════

def angular_momentum(flock) -> float:
    """Mean angular-momentum magnitude about the centre of mass,
    normalised by V0. Large for a milling vortex, ~0 for a straight
    stream — the rotational complement to the (translational) order
    parameter.
    """
    n = len(flock)
    if n == 0:
        return 0.0
    com = np.mean([b.pos for b in flock], axis=0)
    total = np.zeros(3)
    for b in flock:
        r = np.asarray(b.pos, dtype=float) - com
        total += np.cross(r, np.asarray(b.vel, dtype=float))
    # Normalise by N·V0·characteristic-radius so it stays O(1)-ish.
    scale = n * V0 * (0.5 * (WIDTH + HEIGHT))
    return float(np.linalg.norm(total) / scale) if scale else 0.0


def dispersion(flock) -> float:
    """Mean distance of birds from the centre of mass (flock spread)."""
    n = len(flock)
    if n == 0:
        return 0.0
    pos = np.array([b.pos for b in flock], dtype=float)
    com = pos.mean(axis=0)
    return float(np.linalg.norm(pos - com, axis=1).mean())


# ══════════════════════════════════════════════════════════════════════
#  REAL-TIME AGGREGATOR — EMA-smoothed readout for the HUD
# ══════════════════════════════════════════════════════════════════════

class FlockMetrics3D:
    """EMA-smoothed real-time metrics for the 3D flock.

    Read the properties after each update() for a stable readout. The
    smoothing factor (0.04) matches the 2D FlockMetrics so behaviour is
    comparable across stacks.
    """

    __slots__ = ("_alpha", "_theta", "_theta_ext", "_L", "_disp", "smooth")

    def __init__(self, smooth=0.04):
        self.smooth = smooth
        self._alpha = 0.0
        self._theta = 0.0
        self._theta_ext = 0.0
        self._L = 0.0
        self._disp = 0.0

    def update(self, flock, config=None):
        """Fold this frame's raw metrics into the running EMAs."""
        if not flock:
            return
        s = self.smooth
        self._alpha += (order_parameter(flock) - self._alpha) * s
        self._theta += (internal_opacity(flock) - self._theta) * s
        self._theta_ext += (external_opacity(flock) - self._theta_ext) * s
        self._L += (angular_momentum(flock) - self._L) * s
        self._disp += (dispersion(flock) - self._disp) * s

    @property
    def order_param(self) -> float:
        return self._alpha

    @property
    def internal_opacity(self) -> float:
        return self._theta

    @property
    def external_opacity(self) -> float:
        return self._theta_ext

    @property
    def angular_momentum(self) -> float:
        return self._L

    @property
    def dispersion(self) -> float:
        return self._disp

    def summary(self) -> str:
        """One-line readout for the window title / HUD."""
        return (f"α={self._alpha:.2f} Θ={self._theta:.2f} "
                f"Θ'={self._theta_ext:.2f} L={self._L:.3f} "
                f"σr={self._disp:.0f}")
