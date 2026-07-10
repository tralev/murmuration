"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D SPATIAL HASH GRID — O(1) neighbour lookups                       ║
╚══════════════════════════════════════════════════════════════════════╝

 The neighbour-finding data structure both flocking modes build on
 (flocking_modes_3d.py). It buckets birds into a uniform 3D grid so a
 query only inspects the birds in the 3×3×3 = 27 cells around a point,
 instead of scanning the whole flock (O(N²) → roughly O(N) per frame).

 This is *only* the spatial index — no flocking rules live here, so the
 grid can be read and understood on its own. See flocking_modes_3d.py for
 how PROJECTION and SPATIAL mode consume it.

 Dependencies:  flock_core (WIDTH, HEIGHT, DEPTH)
──────────────────────────────────────────────────────────────────────
"""

import math
from collections import defaultdict

from flock_core import WIDTH, HEIGHT, DEPTH

# Default cell size in world units. A cell ≈ the neighbour-interaction range,
# so the 27-cell query around a bird reliably contains its true neighbours.
CELL_SIZE_3D = 80


class SpatialGrid3D:
    """
    3D spatial hash grid for O(1)-per-query neighbour lookups.

    Divides the 3D simulation volume (WIDTH × HEIGHT × DEPTH) into cells
    of size cell_size. Queries check 3×3×3 = 27 adjacent cells.

    Complexity:
      rebuild()    → O(N)
      get_nearby() → O(K)  where K = birds in queried cells
    """
    def __init__(self, cell_size=CELL_SIZE_3D):
        self.cell_size = cell_size
        self.cols = max(1, int(math.ceil(WIDTH / cell_size)))
        self.rows = max(1, int(math.ceil(HEIGHT / cell_size)))
        self.slices = max(1, int(math.ceil(DEPTH / cell_size)))
        self.cells = defaultdict(list)

    def rebuild(self, boids):
        """Repopulate the grid in O(N). Call once per frame before querying."""
        self.cells.clear()
        for boid in boids:
            cx = int(boid.pos[0] // self.cell_size) % self.cols
            cy = int(boid.pos[1] // self.cell_size) % self.rows
            cz = int(boid.pos[2] // self.cell_size) % self.slices
            self.cells[(cx, cy, cz)].append(boid)

    def get_nearby(self, pos, radius):
        """
        Return all boids in cells overlapping the AABB of *radius* around
        *pos*. Checks 3×3×3 = 27 cells.

        Cell indices wrap (``% cols`` …) so the query still works for a
        flock that has drifted or spread past the nominal volume; the false
        positives this can add are far away and get distance-filtered by the
        caller. The returned birds are *candidates* — the caller applies the
        exact (Euclidean) distance test.
        """
        cx0 = int((pos[0] - radius) // self.cell_size)
        cx1 = int((pos[0] + radius) // self.cell_size)
        cy0 = int((pos[1] - radius) // self.cell_size)
        cy1 = int((pos[1] + radius) // self.cell_size)
        cz0 = int((pos[2] - radius) // self.cell_size)
        cz1 = int((pos[2] + radius) // self.cell_size)

        nearby = []
        for cx in range(cx0, cx1 + 1):
            wcx = cx % self.cols
            for cy in range(cy0, cy1 + 1):
                wcy = cy % self.rows
                for cz in range(cz0, cz1 + 1):
                    wcz = cz % self.slices
                    nearby.extend(self.cells.get((wcx, wcy, wcz), ()))
        return nearby
