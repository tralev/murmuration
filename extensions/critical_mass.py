"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 5 — CRITICAL MASS THRESHOLD                               ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  Goodenough et al. (2017) — citizen-science observation that
             a critical mass of roughly 500 birds is needed to initiate
             coherent murmuration behaviour.  Below that, birds mill
             about without forming the large coordinated waves.

 We model this as a soft gate on the collective coupling: the effective
 alignment/projection strength scales up as the flock approaches and
 exceeds the critical mass, so a small flock behaves incoherently and a
 large one "switches on" into a murmuration.

   coherence(N) = smoothstep((N − N_crit·lo) / (N_crit·hi − N_crit·lo))

 coherence rises from 0 (well below critical mass) to 1 (comfortably
 above it), following a smoothstep so the transition is gradual rather
 than a hard cliff.  Multiply the flocking weights by this factor to
 gate the onset of coordinated behaviour.

 Pure functions — unit-testable.

 Usage:
   from extensions.critical_mass import coherence_factor, has_critical_mass
──────────────────────────────────────────────────────────────────────
"""


CRITICAL_MASS = 500        # birds needed to initiate murmuration (Goodenough)
_LO = 0.4                   # coherence starts rising at 0.4 × N_crit
_HI = 1.2                   # coherence saturates at 1.2 × N_crit


def _smoothstep(t: float) -> float:
    """Classic smoothstep on [0, 1]: 3t² − 2t³, clamped."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3.0 - 2.0 * t)


def coherence_factor(n: int, critical_mass: int = CRITICAL_MASS) -> float:
    """Fraction of full coordinated behaviour a flock of *n* birds shows.

    0 well below the critical mass, rising smoothly through it, saturating
    at 1 above it.  Intended as a multiplier on the alignment/projection
    weights so the murmuration "switches on" with size.

    Parameters
    ----------
    n             : current flock size
    critical_mass : threshold (default 500)

    Returns
    -------
    float in [0, 1].
    """
    lo = critical_mass * _LO
    hi = critical_mass * _HI
    if hi <= lo:
        return 1.0 if n >= hi else 0.0
    return _smoothstep((n - lo) / (hi - lo))


def has_critical_mass(n: int, critical_mass: int = CRITICAL_MASS) -> bool:
    """True once the flock is large enough to be (mostly) coherent —
    i.e. coherence_factor ≥ 0.5, which happens around the critical mass."""
    return coherence_factor(n, critical_mass) >= 0.5


def gated_weight(weight: float, n: int,
                 critical_mass: int = CRITICAL_MASS) -> float:
    """Scale a flocking *weight* (φa or φp) by the coherence factor, so a
    sub-critical flock couples weakly and a super-critical one fully."""
    return weight * coherence_factor(n, critical_mass)
