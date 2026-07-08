"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 8 — BLOB INITIALISATION                                    ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  companion TypeScript project `particleInitialization.ts`.

 Instead of scattering birds uniformly across the domain, the companion
 seeds them in a small number of overlapping spherical "blobs" with a
 volumetric density falloff.  This starts the flock already clustered —
 closer to how a real murmuration assembles from roosting groups — and
 gives the projection model a denser initial field to work on.

 Algorithm:
   1. Place N_CENTERS blob centres (default 5) within the domain.
   2. For each bird, pick a centre and sample a radius with a
      volumetric bias (r = R · u^(1/D)) so points fill the sphere
      evenly rather than clumping at the middle.
   3. Offset by a random direction and clamp inside the domain.

 Works in 2D (returns (x, y)) and 3D (returns (x, y, z)) via the
 *dims* argument.  Deterministic when given a seeded RNG.

 Usage:
   from extensions.blob_init import blob_positions
──────────────────────────────────────────────────────────────────────
"""

import math
import random

from flock_core import WIDTH, HEIGHT


N_CENTERS_DEFAULT = 5
BLOB_RADIUS_DEFAULT = 140.0


def _random_unit(dims, rng):
    """A random unit vector in 2 or 3 dimensions (uniform on the sphere)."""
    if dims == 2:
        a = rng.uniform(0, 2 * math.pi)
        return [math.cos(a), math.sin(a)]
    # 3D: sample a direction via normalised Gaussians (uniform on S²).
    while True:
        v = [rng.gauss(0, 1) for _ in range(3)]
        m = math.sqrt(sum(c * c for c in v))
        if m > 1e-9:
            return [c / m for c in v]


def blob_positions(count, dims=2, n_centers=N_CENTERS_DEFAULT,
                   radius=BLOB_RADIUS_DEFAULT, bounds=None, rng=None):
    """Generate *count* clustered start positions.

    Parameters
    ----------
    count     : number of birds
    dims      : 2 or 3
    n_centers : number of blob centres (default 5)
    radius    : blob radius in px
    bounds    : (w, h[, d]) domain size; defaults to (WIDTH, HEIGHT[, 400])
    rng       : optional random.Random for determinism

    Returns
    -------
    list of (x, y) or (x, y, z) tuples, all inside the domain.
    """
    if rng is None:
        rng = random
    if bounds is None:
        bounds = (WIDTH, HEIGHT) if dims == 2 else (WIDTH, HEIGHT, 400)
    n_centers = max(1, n_centers)

    # Blob centres kept a margin in from the edges so blobs stay visible.
    margin = radius * 0.5
    centers = []
    for _ in range(n_centers):
        centers.append([rng.uniform(margin, bounds[k] - margin)
                        for k in range(dims)])

    positions = []
    for i in range(count):
        c = centers[i % n_centers]           # round-robin keeps blobs even
        u = rng.random()
        r = radius * (u ** (1.0 / dims))     # volumetric radius bias
        direction = _random_unit(dims, rng)
        p = []
        for k in range(dims):
            val = c[k] + direction[k] * r
            val = max(0.0, min(bounds[k], val))  # clamp into domain
            p.append(val)
        positions.append(tuple(p))
    return positions
