"""
╔══════════════════════════════════════════════════════════════════════╗
║  ECOLOGY — seasonal, critical-mass & predator realism (3D)          ║
╚══════════════════════════════════════════════════════════════════════╝

 Source (see sci/): Goodenough, Little, Carpenter & Hart (2017), "Birds of
 a feather flock together: Insights into starling murmuration behaviour
 revealed using citizen science" (PLoS ONE 12(6): e0179277).

 Citizen-science observations of UK starling murmurations give the
 ecological envelope this module reproduces:

   • Seasonal flock size — grows through autumn/winter, peaks in
     mid-winter, falls toward spring; no habitat association.
   • Critical mass — a coherent murmuration needs roughly 500 birds to
     get going; below that, birds mill without large coordinated waves.
   • Predators present at ~29.6% of murmurations, associated with larger
     and longer-lasting displays.

 Pure, dimension-agnostic functions (they operate on flock *size* and
 *date*, not geometry), so they apply unchanged to the 3D simulation.

 Usage:
   from ecology import seasonal_size_factor, coherence_factor, predator_present
──────────────────────────────────────────────────────────────────────
"""

import math


# ── Seasonal model (fit to the Goodenough seasonal description) ─────
PEAK_DAY   = 15       # day-of-year of maximum size (~mid-January)
MIN_FACTOR = 0.25     # summer trough as a fraction of the winter peak
_DAYS = 365.0
_SEASON_MONTHS = {10, 11, 12, 1, 2, 3}   # Oct–Mar observation window
_MONTH_STARTS = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]

# ── Critical mass (Goodenough ~500-bird onset threshold) ────────────
CRITICAL_MASS = 500
_LO, _HI = 0.4, 1.2   # coherence ramps over [0.4·N_crit, 1.2·N_crit]

# ── Predator presence rate (Goodenough: 29.6% of murmurations) ──────
PREDATOR_RATE = 0.296


# ══════════════════════════════════════════════════════════════════════
#  Seasonal flock-size variation
# ══════════════════════════════════════════════════════════════════════

def seasonal_size_factor(day_of_year: int) -> float:
    """Relative flock-size factor in [MIN_FACTOR, 1.0] for a day-of-year.

    A raised cosine peaking at PEAK_DAY (mid-winter) and troughing half a
    year later (mid-summer). Wrap-around is handled so late-December and
    early-January are both near the peak.
    """
    delta = (day_of_year - PEAK_DAY) % _DAYS
    if delta > _DAYS / 2:
        delta -= _DAYS
    cos_phase = math.cos(2 * math.pi * delta / _DAYS)
    return MIN_FACTOR + (1.0 - MIN_FACTOR) * (0.5 + 0.5 * cos_phase)


def flock_size_for_day(day_of_year: int, peak_size: int,
                       min_size: int = 0) -> int:
    """Scale a peak (mid-winter) flock size down to a given day."""
    return max(min_size, int(round(peak_size * seasonal_size_factor(day_of_year))))


def is_murmuration_season(day_of_year: int) -> bool:
    """True if the day falls in the Oct–Mar observation window."""
    return _day_to_month(day_of_year) in _SEASON_MONTHS


# ══════════════════════════════════════════════════════════════════════
#  Critical-mass onset gate
# ══════════════════════════════════════════════════════════════════════

def _smoothstep(t: float) -> float:
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3.0 - 2.0 * t)


def coherence_factor(n: int, critical_mass: int = CRITICAL_MASS) -> float:
    """Fraction of full coordinated behaviour a flock of *n* birds shows —
    0 well below the critical mass, rising smoothly through it, 1 above.
    Intended as a multiplier on the alignment/projection weights so the
    murmuration "switches on" with size."""
    lo, hi = critical_mass * _LO, critical_mass * _HI
    if hi <= lo:
        return 1.0 if n >= hi else 0.0
    return _smoothstep((n - lo) / (hi - lo))


def has_critical_mass(n: int, critical_mass: int = CRITICAL_MASS) -> bool:
    """True once the flock is large enough to be (mostly) coherent."""
    return coherence_factor(n, critical_mass) >= 0.5


def gated_weight(weight: float, n: int,
                 critical_mass: int = CRITICAL_MASS) -> float:
    """Scale a flocking weight (φa or φp) by the coherence factor."""
    return weight * coherence_factor(n, critical_mass)


# ══════════════════════════════════════════════════════════════════════
#  Predator presence
# ══════════════════════════════════════════════════════════════════════

def predator_present(day_of_year: int, rng=None) -> bool:
    """Whether a predator attends this display (~29.6% base rate).
    Deterministic per-day when *rng* is None; drawn from *rng* otherwise."""
    if rng is not None:
        return rng.random() < PREDATOR_RATE
    frac = ((day_of_year * 2654435761) % 1000) / 1000.0
    return frac < PREDATOR_RATE


# ── helpers ─────────────────────────────────────────────────────────

def _day_to_month(day_of_year: int) -> int:
    d = (day_of_year - 1) % 365
    month = 1
    for i, start in enumerate(_MONTH_STARTS):
        if d >= start:
            month = i + 1
    return month
