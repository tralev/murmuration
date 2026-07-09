"""
╔══════════════════════════════════════════════════════════════════════╗
║  CORRELATION TIME τρ (3D) — density-fluctuation timescale           ║
╚══════════════════════════════════════════════════════════════════════╝

 Source (see sci.md): Pearce, Miller, Rowlands & Turner (2014), "The Role of
 Projection in the Control of Bird Flocks" (arXiv:1407.2414). Fig. 2f
 reports the "swarm density autocorrelation time τρ" — how long density
 fluctuations persist, a characteristic timescale of the flock's internal
 structural dynamics.

   ρ(t)      = N / volume(convex hull of the flock)      (3D density)
   C_ρρ(Δt)  = ⟨ρ(t)·ρ(t+Δt)⟩ − ⟨ρ⟩²                     (autocovariance)
   τρ        = ∫₀^∞ C_ρρ(Δt)/C_ρρ(0) dΔt                 (integrated time)

 The 3D density uses the convex-hull **volume** (scipy.spatial.ConvexHull
 `.volume` is the enclosed volume in 3D; `.area` is the surface area).
 Density snapshots are stored in a ring buffer; τρ is estimated as the
 area under the normalised autocorrelation out to a fraction of the buffer.

 Usage:
   from correlation_time import CorrelationTimeTracker, convex_hull_volume
──────────────────────────────────────────────────────────────────────
"""

import numpy as np
from scipy.spatial import ConvexHull, QhullError


BUFFER_SIZE          = 500    # max density snapshots stored
SAMPLE_INTERVAL      = 10     # sample density every N frames
MAX_LAG_FRACTION     = 0.25   # integrate autocorrelation to 25% of buffer


def convex_hull_volume(flock) -> float:
    """Convex-hull volume of the 3D flock (birds with ``.pos`` or (x,y,z)).

    Delegates to scipy's Qhull; ``.volume`` is the enclosed 3D volume.
    Degenerate inputs (< 4 points, or coplanar/collinear) have no volume
    and return 0.0.
    """
    pts = np.array([_as_xyz(p) for p in flock], dtype=float)
    if len(pts) < 4:
        return 0.0
    try:
        return float(ConvexHull(pts).volume)
    except QhullError:
        return 0.0                                   # coplanar / degenerate


class CorrelationTimeTracker:
    """Rolling estimator of the density autocorrelation time τρ.

    Call ``sample(flock)`` each frame; it stores density every
    SAMPLE_INTERVAL frames. Read ``tau`` for the current estimate (0 until
    enough samples accumulate).
    """

    __slots__ = ("_buf", "_frame", "_tau")

    def __init__(self):
        self._buf = []            # recent density snapshots (ring)
        self._frame = 0
        self._tau = 0.0

    def sample(self, flock):
        """Record a density snapshot every SAMPLE_INTERVAL frames and
        refresh the τρ estimate."""
        self._frame += 1
        if self._frame % SAMPLE_INTERVAL != 0:
            return self._tau
        vol = convex_hull_volume(flock)
        rho = (len(flock) / vol) if vol > 1e-9 else 0.0
        self._buf.append(rho)
        if len(self._buf) > BUFFER_SIZE:
            self._buf.pop(0)
        self._tau = self._estimate_tau()
        return self._tau

    @property
    def tau(self) -> float:
        return self._tau

    @property
    def n_samples(self) -> int:
        return len(self._buf)

    def _estimate_tau(self) -> float:
        """Integrate the normalised density autocorrelation, in units of
        SAMPLE_INTERVAL frames."""
        x = np.asarray(self._buf, dtype=float)
        n = len(x)
        if n < 8:
            return 0.0
        x = x - x.mean()
        c0 = float(np.dot(x, x) / n)
        if c0 < 1e-12:
            return 0.0                               # constant density
        max_lag = max(1, int(n * MAX_LAG_FRACTION))
        tau = 0.5                                    # lag-0 trapezoid term
        for lag in range(1, max_lag):
            c = float(np.dot(x[:-lag], x[lag:]) / (n - lag))
            r = c / c0
            if r <= 0.0:
                break                                # first zero crossing
            tau += r
        return tau * SAMPLE_INTERVAL                 # → frames


def _as_xyz(p):
    pos = getattr(p, "pos", None)
    if pos is not None:
        return (float(pos[0]), float(pos[1]), float(pos[2]))
    return (p[0], p[1], p[2])
