"""
╔══════════════════════════════════════════════════════════════════════╗
║  STERIC REPULSION (3D) — Pearce SI Appendix generalisation          ║
╚══════════════════════════════════════════════════════════════════════╝

 Source (see sci.md §1.4 and §4.7): Pearce et al. (2014) SI Appendix. The base
 hybrid-projection model treats birds as "phantoms" with no direct
 interaction. The SI adds an optional **steric / repulsive** term: a
 short-range force that keeps birds from overlapping, felt only within a
 few body radii.

   F_steric,i = φ_s · Σ_{j : d_ij < r_s}  r̂_{i←j} / d_ij²

 i.e. a `1/d²` push *away* from every neighbour closer than the steric
 radius `r_s` (≈ a small multiple of the body size `b`). It is the 3D
 form: the direction `r̂_{i←j}` is a genuine 3-vector.

 Pure function on numpy Vec3 birds; returned as a steering force to be
 accumulated via `boid.apply_force`.

 Dependencies:  numpy, flock_core (BOID_SIZE, MAX_FORCE)
──────────────────────────────────────────────────────────────────────
"""

import numpy as np

from flock_core import BOID_SIZE, MAX_FORCE


STERIC_RADIUS = BOID_SIZE * 4.0     # interaction range (a few body radii)


def steric_force(boid, neighbours, strength=1.0, radius=STERIC_RADIUS):
    """Short-range `1/d²` repulsion away from neighbours inside *radius*.

    Parameters
    ----------
    boid       : the bird being pushed (numpy length-3 ``.pos``)
    neighbours : iterable of (other, dist) pairs, or bare birds (distance is
                 then computed). The bird itself is skipped.
    strength   : scale on the accumulated repulsion (φ_s)
    radius     : interaction range r_s

    Returns
    -------
    numpy (3,) — the repulsive steering force, clamped to MAX_FORCE.
    """
    pos = np.asarray(boid.pos, dtype=float)
    force = np.zeros(3)
    for item in neighbours:
        other, d = item if isinstance(item, tuple) else (item, None)
        if other is boid:
            continue
        diff = pos - np.asarray(other.pos, dtype=float)   # points away from j
        if d is None:
            d = float(np.linalg.norm(diff))
        if d < 1e-6 or d >= radius:
            continue
        force += (diff / d) / (d * d)                     # r̂ / d²

    force *= strength
    mag = float(np.linalg.norm(force))
    if mag > MAX_FORCE:
        force = force / mag * MAX_FORCE
    return force
