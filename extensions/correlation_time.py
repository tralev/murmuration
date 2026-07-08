"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 1c — CORRELATION TIME  τᵨ                                  ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  Pearce et al. (2014).
 The correlation time τᵨ measures how long density fluctuations
 persist in the flock — the characteristic timescale of structural
 changes.

   τᵨ = ∫₀^∞ C_ρρ(Δt) dΔt

   C_ρρ(Δt) = ⟨ρ(t) · ρ(t + Δt)⟩ − ⟨ρ⟩²
   ρ(t)     = N / area(convex_hull(flock))

 Density ρ is computed from the convex hull of flock positions using
 Graham scan (O(N log N)).  A ring buffer stores density snapshots
 sampled every CORR_SAMPLE_INTERVAL frames.  Autocorrelation is
 computed from the buffer and integrated to estimate τᵨ.

 Usage:
   from extensions.correlation_time import CorrelationTimeTracker

⇔ Octave: alg2_extended.m §SECTION 5+9  ⇔ Scilab: alg2_extended.sce §SECTION 5+9
──────────────────────────────────────────────────────────────────────
"""

import numpy as np
from scipy.spatial import ConvexHull, QhullError


# ── Tunable constants ──────────────────────────────────────────────

BUFFER_SIZE           = 500   # max number of density snapshots stored
CORR_SAMPLE_INTERVAL  = 10    # sample density every N frames
MAX_LAG_FRACTION      = 0.25  # integrate up to 25% of buffer length


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Convex Hull — scipy.spatial.ConvexHull (Qhull)                     ║
# ╚══════════════════════════════════════════════════════════════════════╝

def convex_hull_area(points: list) -> float:
    """
    Area of the convex hull of a set of 2D points, used to estimate the
    flock density ρ = N / area for the correlation time τᵨ.

    Delegates to `scipy.spatial.ConvexHull` (Qhull). For a 2D hull,
    Qhull's ``.volume`` attribute is the enclosed **area** (``.area`` is
    the perimeter). Qhull raises ``QhullError`` for degenerate inputs —
    fewer than 3 points, or all points collinear/coincident — which have
    no positive area; we map those to 0.0.

    Parameters
    ----------
    points : list of (x, y) tuples

    Returns
    -------
    float — area of the convex hull polygon (0.0 if degenerate)
    """
    if len(points) < 3:
        return 0.0  # need at least 3 points for a polygon
    try:
        return float(ConvexHull(np.asarray(points, dtype=float)).volume)
    except QhullError:
        # Collinear or coincident points — no 2D hull, zero area.
        return 0.0


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Correlation Time Tracker                                           ║
# ╚══════════════════════════════════════════════════════════════════════╝

class CorrelationTimeTracker:
    """
    Tracks flock density over time and estimates the correlation
    time τᵨ — the characteristic timescale of density fluctuations.

    Density ρ = N / area(convex_hull(positions)) is sampled every
    CORR_SAMPLE_INTERVAL frames and stored in a ring buffer.
    Autocorrelation of the density time series is computed from
    the buffer, and τᵨ is estimated by integrating C_ρρ over lag.
    """

    __slots__ = ("_buffer", "_frames", "_idx", "_count",
                 "_tau", "_latest_density", "_sample_timer")

    def __init__(self):
        self._buffer = [0.0] * BUFFER_SIZE   # ring buffer of densities
        self._frames = [0] * BUFFER_SIZE      # ring buffer of frame numbers
        self._idx = 0                         # write position
        self._count = 0                       # number of valid entries
        self._tau = 0.0                       # latest τᵨ estimate
        self._latest_density = 0.0             # most recent ρ
        self._sample_timer = 0                 # countdown to next sample

    def sample(self, flock: list, frame: int):
        """
        Sample flock density and store in the ring buffer.

        Should be called every frame.  Sampling only occurs when
        the internal timer reaches CORR_SAMPLE_INTERVAL.

        Parameters
        ----------
        flock : list[Boid]
        frame : int — current frame number
        """
        self._sample_timer += 1
        if self._sample_timer < CORR_SAMPLE_INTERVAL:
            return
        self._sample_timer = 0

        n = len(flock)
        if n < 3:
            self._latest_density = 0.0
            return

        # ── Compute density from convex hull ─────────────────────
        points = [(b.position.x, b.position.y) for b in flock]
        area = convex_hull_area(points)
        if area < 1.0:
            self._latest_density = 0.0
            return

        density = n / area

        # ── Store in ring buffer ─────────────────────────────────
        self._buffer[self._idx] = density
        self._frames[self._idx] = frame
        self._idx = (self._idx + 1) % BUFFER_SIZE
        if self._count < BUFFER_SIZE:
            self._count += 1

        self._latest_density = density

        # ── Recompute τᵨ from buffer ────────────────────────────
        self._compute_tau()

    def _compute_tau(self):
        """
        Compute autocorrelation of density time series and
        integrate to estimate τᵨ.

        ── AUTOCORRELATION METHOD ──

        C_ρρ(lag) = ⟨ρ(t)·ρ(t+lag)⟩ − ⟨ρ⟩²

        This is the auto-covariance: how correlated is the density
        now with the density *lag* frames ago?

        τᵨ = Σ_{lag=0}^{max_lag} C_ρρ(lag) · Δt  /  C_ρρ(0)

        The integral of the autocorrelation function gives the
        characteristic timescale of density fluctuations.  A large
        τᵨ means the flock maintains its density pattern for a long
        time; a small τᵨ means the pattern changes rapidly.

        ── STEP-BY-STEP ──

        1. Unroll the ring buffer into a linear array (oldest first).
        2. Compute mean density ⟨ρ⟩ and variance σ².
        3. For each lag from 0 to max_lag (25% of buffer):
           a. Compute ⟨ρ[i]·ρ[i+lag]⟩ over valid pairs.
           b. C(lag) = cross_product − ⟨ρ⟩²
           c. If C(lag) ≤ 0, stop (correlation has vanished).
           d. Accumulate C(lag) · Δt
        4. Normalise: τᵨ = Σ(C·Δt) / σ²

        The normalisation by variance gives τᵨ in units of Δt
        (frame intervals).  Integration stops when correlation
        drops below zero to avoid including noise.
        """
        m = self._count
        if m < 10:
            self._tau = 0.0  # insufficient data
            return

        # ═══════════════════════════════════════════════════════════
        #  STEP 1: Unroll ring buffer into linear array
        # ═══════════════════════════════════════════════════════════
        #
        #  The ring buffer wraps around (circular).  To simplify
        #  computations, we extract a linear time series where
        #  index 0 is the OLDEST sample and index m−1 is the
        #  NEWEST.  This ordering makes the autocorrelation sum
        #  over lags more natural.
        #
        #  Starting index: (self._idx − m) wraps to the oldest
        #  entry.  Then we walk forward m steps (mod BUFFER_SIZE).
        # ───────────────────────────────────────────────────────────

        dens = []
        for i in range(m):
            idx = (self._idx - m + i) % BUFFER_SIZE
            dens.append(self._buffer[idx])

        # ═══════════════════════════════════════════════════════════
        #  STEP 2: Compute mean and variance
        # ═══════════════════════════════════════════════════════════

        mean_d = sum(dens) / m

        # Variance: σ² = ⟨(ρ − ⟨ρ⟩)²⟩
        var = sum((d - mean_d) ** 2 for d in dens) / m
        if var < 1e-12:
            self._tau = 0.0
            return  # nearly constant density → zero correlation time

        # ═══════════════════════════════════════════════════════════
        #  STEP 3: Autocorrelation integration
        # ═══════════════════════════════════════════════════════════
        #
        #  max_lag = 25% of buffer length — beyond this, the
        #  autocorrelation is dominated by noise.  Using only the
        #  first quarter gives a stable estimate.
        #
        #  dt = CORR_SAMPLE_INTERVAL — the time between consecutive
        #  density samples (in frames).
        #
        #  For each lag, we compute:
        #    C(lag) = ⟨d[i]·d[i+lag]⟩ − ⟨d⟩²
        #
        #  The cross-product only uses pairs (i, i+lag) where both
        #  indices are valid (i < m − lag).
        #
        #  Integration stops when C(lag) becomes negative — the
        #  correlation has vanished and further lags would only add
        #  noise.
        # ───────────────────────────────────────────────────────────

        max_lag = max(1, int(m * MAX_LAG_FRACTION))
        dt = CORR_SAMPLE_INTERVAL
        tau_sum = 0.0

        for lag in range(max_lag):
            n_pairs = m - lag  # number of valid d[i], d[i+lag] pairs
            if n_pairs < 2:
                break

            # Cross-product: average of d[i] * d[i+lag]
            cross = sum(dens[i] * dens[i + lag] for i in range(n_pairs)) / n_pairs

            # Auto-covariance: C(lag) = ⟨d[i]·d[i+lag]⟩ − ⟨d⟩²
            c = cross - mean_d * mean_d

            if c <= 0:
                break  # autocorrelation has vanished — stop integrating

            tau_sum += c * dt

        # ═══════════════════════════════════════════════════════════
        #  STEP 4: Normalise
        # ═══════════════════════════════════════════════════════════
        #
        #  τᵨ = Σ(C·Δt) / σ²
        #
        #  Dividing by variance gives τᵨ in units of Δt (frames).
        #  At lag=0: C(0) = ⟨d²⟩ − ⟨d⟩² = σ², so the normalisation
        #  ensures τᵨ = Δt if C just drops linearly to zero at lag=1.
        # ───────────────────────────────────────────────────────────

        self._tau = tau_sum / var

    # ── Properties ───────────────────────────────────────────────────

    @property
    def tau(self) -> float:
        """Correlation time τᵨ in frames."""
        return self._tau

    @property
    def latest_density(self) -> float:
        """Most recent density ρ = N / hull_area."""
        return self._latest_density

    @property
    def buffer_size(self) -> int:
        """Number of snapshots collected so far."""
        return self._count
