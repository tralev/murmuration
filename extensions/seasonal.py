"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 5 — SEASONAL / ECOLOGICAL REALISM                         ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  Goodenough, Little, Carpenter & Hart (2017),
             "Birds of a feather flock together: Insights into
             starling murmuration behaviour revealed using citizen
             science", PLoS ONE 12(6): e0179277.

 Citizen-science observations of UK starling murmurations give the
 ecological envelope this module reproduces:

   • Seasonal flock size — grows through autumn/winter (Oct→Feb),
     peaks in mid-winter, falls away toward March.  No habitat
     association (urban, rural, wetland all used).
   • Predator presence at ~29.6% of murmurations, associated with
     larger and longer-lasting displays.
   • Mean display duration ≈ 26 min, positively correlated with day
     length, weakly negatively with temperature.

 We model the seasonal size curve as a smooth function of day-of-year
 peaking at mid-winter (≈ day 15, mid-January) and bottoming in summer,
 then map it onto a flock-size multiplier.  Deterministic — no RNG — so
 a given day always yields the same size.

 Usage:
   from extensions.seasonal import seasonal_size_factor, flock_size_for_day
──────────────────────────────────────────────────────────────────────
"""

import math


# ── Model parameters (fit to the Goodenough seasonal description) ───

PEAK_DAY        = 15      # day-of-year of maximum size (~mid-January)
MIN_FACTOR      = 0.25    # summer trough as a fraction of the winter peak
PREDATOR_RATE   = 0.296   # fraction of murmurations with a predator present
MEAN_DURATION_S = 26 * 60  # mean display duration (seconds)

# Months where murmurations are actually observed (Oct–Mar); outside
# this window starlings are dispersed and breeding.
_SEASON_MONTHS = {10, 11, 12, 1, 2, 3}
_DAYS_IN_YEAR = 365.0


def seasonal_size_factor(day_of_year: int) -> float:
    """Relative flock-size factor in [MIN_FACTOR, 1.0] for a day-of-year.

    A raised cosine peaking at PEAK_DAY: 1.0 at mid-winter, MIN_FACTOR
    at the opposite point of the year (mid-summer).  The wrap-around is
    handled so late-December and early-January are both near the peak.

    Parameters
    ----------
    day_of_year : int, 1..365

    Returns
    -------
    float in [MIN_FACTOR, 1.0]
    """
    # Phase measured from the peak, wrapped to [-182.5, 182.5] days.
    delta = (day_of_year - PEAK_DAY) % _DAYS_IN_YEAR
    if delta > _DAYS_IN_YEAR / 2:
        delta -= _DAYS_IN_YEAR
    # cos = +1 at the peak, −1 half a year away.
    cos_phase = math.cos(2 * math.pi * delta / _DAYS_IN_YEAR)
    # Map cos∈[-1,1] onto [MIN_FACTOR, 1.0].
    return MIN_FACTOR + (1.0 - MIN_FACTOR) * (0.5 + 0.5 * cos_phase)


def flock_size_for_day(day_of_year: int, peak_size: int,
                       min_size: int = 0) -> int:
    """Scale a peak (mid-winter) flock size down to a given day.

    Parameters
    ----------
    day_of_year : int, 1..365
    peak_size   : flock size at the mid-winter peak
    min_size    : optional floor so the simulation never empties

    Returns
    -------
    int — the flock size for that day, at least *min_size*.
    """
    size = int(round(peak_size * seasonal_size_factor(day_of_year)))
    return max(min_size, size)


def is_murmuration_season(day_of_year: int) -> bool:
    """True if the day falls in the Oct–Mar observation window."""
    return _day_to_month(day_of_year) in _SEASON_MONTHS


def predator_present(day_of_year: int, rng=None) -> bool:
    """Sample whether a predator attends this display (~29.6% base rate,
    per Goodenough).  Deterministic per-day when *rng* is None (uses the
    day as a hash), or drawn from *rng* if supplied."""
    if rng is not None:
        return rng.random() < PREDATOR_RATE
    # Deterministic pseudo-random from the day, stable across runs.
    frac = ((day_of_year * 2654435761) % 1000) / 1000.0
    return frac < PREDATOR_RATE


# ── helpers ─────────────────────────────────────────────────────────

# Cumulative days at the start of each month (non-leap year).
_MONTH_STARTS = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]


def _day_to_month(day_of_year: int) -> int:
    """Map a 1-based day-of-year to a 1-based month (non-leap)."""
    d = ((day_of_year - 1) % 365)
    month = 1
    for i, start in enumerate(_MONTH_STARTS):
        if d >= start:
            month = i + 1
    return month
