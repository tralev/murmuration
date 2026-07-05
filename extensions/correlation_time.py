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
──────────────────────────────────────────────────────────────────────
"""

import math


# ── Tunable constants ──────────────────────────────────────────────

BUFFER_SIZE           = 500   # max number of density snapshots stored
CORR_SAMPLE_INTERVAL  = 10    # sample density every N frames
MAX_LAG_FRACTION      = 0.25  # integrate up to 25% of buffer length


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Convex Hull — Graham Scan                                          ║
# ╚══════════════════════════════════════════════════════════════════════╝

def _cross(o, a, b):
    """
    2D cross product of vectors OA and OB.

    Returns (a_x − o_x)(b_y − o_y) − (a_y − o_y)(b_x − o_x).

    Used by Graham scan to determine turn direction:
      > 0  → counter-clockwise (left turn) — keep on hull
      ≤ 0  → clockwise or collinear (right turn) — pop from hull

    This is the determinant of the matrix [[OA_x, OA_y], [OB_x, OB_y]].
    """
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _dist_sq(a, b):
    """Squared Euclidean distance between points a and b."""
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def convex_hull_area(points: list) -> float:
    """
    Compute the area of the convex hull of a set of 2D points
    using Graham scan.  Returns 0 if fewer than 3 points.

    ── GRAHAM SCAN ALGORITHM (O(N log N)) ──

    1. FIND PIVOT: the point with the lowest y-coordinate (ties
       broken by lowest x).  This point is guaranteed to be on
       the hull.

    2. SORT by polar angle from pivot.  Points with the same angle
       are sorted by distance (closest first).

    3. BUILD HULL: iterate through sorted points.  For each point,
       pop from the hull while the last three points make a
       clockwise or collinear turn (_cross ≤ 0).  Then push the
       new point.

       This "pop-and-push" loop ensures the hull stays convex!
       It works because the cross product detects when adding a
       new point would create a concave indentation.

    4. SHOELACE FORMULA: compute polygon area from hull vertices.
       area = (1/2) × |Σ (x_i·y_{i+1} − x_{i+1}·y_i)|

    Complexity: O(N log N) where N = len(points).
    The sort dominates; the hull-building loop is O(N) (each point
    is pushed and popped at most once).

    Parameters
    ----------
    points : list of (x, y) tuples

    Returns
    -------
    float — area of the convex hull polygon (0 if degenerate)
    """
    n = len(points)
    if n < 3:
        return 0.0  # need at least 3 points for a polygon

    # ═══════════════════════════════════════════════════════════
    #  STEP 1: Find pivot — lowest y, then leftmost x
    # ═══════════════════════════════════════════════════════════
    #
    #  The pivot is guaranteed to be a hull vertex.  We swap it
    #  into position [0] so the rest of the algorithm can use it
    #  as the reference point for polar angle sorting.
    #
    #  Each comparison checks against points[0] (which may have
    #  changed due to earlier swaps — this is the "current best").
    # ───────────────────────────────────────────────────────────

    for i in range(1, n):
        if (points[i][1] < points[0][1] or
            (points[i][1] == points[0][1] and points[i][0] < points[0][0])):
            points[0], points[i] = points[i], points[0]

    pivot = points[0]

    # ═══════════════════════════════════════════════════════════
    #  STEP 2: Sort by polar angle from pivot
    # ═══════════════════════════════════════════════════════════
    #
    #  polar_order returns (angle, distance_sq).  Sorting by
    #  this pair ensures:
    #    - Points are ordered counter-clockwise around pivot.
    #    - Collinear points (same angle) are ordered closest-first,
    #      allowing the hull-building loop to naturally skip
    #      interior collinear points.
    # ───────────────────────────────────────────────────────────

    def polar_order(p):
        dx, dy = p[0] - pivot[0], p[1] - pivot[1]
        return (math.atan2(dy, dx), dx * dx + dy * dy)

    sorted_pts = sorted(points[1:], key=polar_order)

    # ═══════════════════════════════════════════════════════════
    #  STEP 3: Build convex hull via Graham scan
    # ═══════════════════════════════════════════════════════════
    #
    #  Start with the pivot and the first sorted point.  For each
    #  subsequent point p, check if the last three points make a
    #  RIGHT turn (clockwise or collinear).  If so, pop the middle
    #  point — it's inside the hull.  Repeat until the turn is LEFT
    #  (counter-clockwise), then push p.
    #
    #  VISUAL TRACE (square: (0,0), (1,0), (1,1), (0,1)):
    #    pivot=(0,0), sorted=[(1,0), (1,1), (0,1)]
    #    hull=[(0,0), (1,0)]          — initial
    #    p=(1,1): cross((0,0),(1,0),(1,1)) = 1 > 0 → push → [(0,0),(1,0),(1,1)]
    #    p=(0,1): cross((1,0),(1,1),(0,1)) = 1 > 0 → push → [(0,0),(1,0),(1,1),(0,1)]
    #
    #  COLLINEAR EXAMPLE ((0,0), (1,0), (2,0), (2,2), (0,2)):
    #    sorted=[(1,0), (2,0), (2,2), (0,2)]
    #    hull=[(0,0), (1,0)]
    #    p=(2,0): cross((0,0),(1,0),(2,0)) = 0 ≤ 0 → pop (1,0) → [(0,0)] → push (2,0)
    #    → [(0,0), (2,0)]  ... collinear (1,0) excluded!
    # ───────────────────────────────────────────────────────────

    hull = [pivot, sorted_pts[0]]
    for p in sorted_pts[1:]:
        # Pop while the last two hull points + p make a right turn
        while len(hull) >= 2 and _cross(hull[-2], hull[-1], p) <= 0:
            hull.pop()
        hull.append(p)

    # ═══════════════════════════════════════════════════════════
    #  STEP 4: Shoelace formula for polygon area
    # ═══════════════════════════════════════════════════════════
    #
    #  area = (1/2) × |Σ (x_i·y_{i+1} − x_{i+1}·y_i)|
    #
    #  Each edge from vertex i to i+1 contributes a signed
    #  trapezoid area.  Summing around the closed polygon gives
    #  the total area.  The absolute value handles winding order.
    #
    #  The modulo index (i+1) % m closes the polygon back to the
    #  first vertex.
    # ───────────────────────────────────────────────────────────

    area = 0.0
    m = len(hull)
    for i in range(m):
        x1, y1 = hull[i]
        x2, y2 = hull[(i + 1) % m]  # wrap to first vertex
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


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
