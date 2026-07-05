"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 2 — CONFIGURATION CONSTANTS                                ║
║  SECTION 3 — RUNTIME STATE  (Config + SpatialGrid)                  ║
╚══════════════════════════════════════════════════════════════════════╝

 Core data structures and constants shared across all modules.
 Imported by boid.py, metrics.py, and alg2.py.
──────────────────────────────────────────────────────────────────────
"""

import math
import random
from collections import defaultdict


# ══════════════════════════════════════════════════════════════════════
#  Display
# ══════════════════════════════════════════════════════════════════════

WIDTH, HEIGHT = 1000, 700               # simulation area (pixels)
FPS           = 60                      # target frame rate

# ══════════════════════════════════════════════════════════════════════
#  Flock parameters
# ══════════════════════════════════════════════════════════════════════

NUM_BOIDS      = 150                    # number of birds
BOID_SIZE      = 3                      # bird radius b (paper: b = 1)
V0             = 4                      # constant cruising speed v₀
MAX_FORCE      = 0.15                   # max steering force (smooth turning)
VISUAL_RANGE   = 70                     # neighbour search radius (spatial mode)

# ══════════════════════════════════════════════════════════════════════
#  Default model weights  (φp + φa + φn ≡ 1)
# ══════════════════════════════════════════════════════════════════════

DEFAULT_PHI_P  = 0.03                   # projection / separation weight
DEFAULT_PHI_A  = 0.80                   # alignment weight
DEFAULT_SIGMA  = 4                      # number of nearest visible neighbours

# ══════════════════════════════════════════════════════════════════════
#  Mode identifiers
# ══════════════════════════════════════════════════════════════════════

MODE_PROJECTION = 0
MODE_SPATIAL    = 1

MODE_NAMES = {
    MODE_PROJECTION: "PROJECTION  (Pearce et al. 2014)",
    MODE_SPATIAL:    "SPATIAL     (topological Reynolds + grid)",
}


# ══════════════════════════════════════════════════════════════════════
#  Trail rendering  (position-history polyline behind each boid)
# ══════════════════════════════════════════════════════════════════════

DRAW_TRAIL   = False                   # draw position history trail behind each boid
TRAIL_LENGTH = 50                      # max trail positions to keep

# ══════════════════════════════════════════════════════════════════════
#  Boundary mode  (toroidal wrap or margin-based keepWithinBounds)
# ══════════════════════════════════════════════════════════════════════

MARGIN_BOUNDARY     = False            # use margin-based keepWithinBounds instead of toroidal wrap
BOUNDARY_MARGIN     = 200              # distance from edge to start turning (margin mode)
BOUNDARY_TURN_FACTOR = 1               # velocity nudge strength toward center (margin mode)

# ══════════════════════════════════════════════════════════════════════
#  CSV logging
# ══════════════════════════════════════════════════════════════════════

LOG_FILE  = "output/murmuration_metrics.csv"   # set to None to disable CSV
LOG_EVERY = 10                          # write a row every N frames


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECTION 3 — RUNTIME STATE                                          ║
# ╚══════════════════════════════════════════════════════════════════════╝
#  Config holds mutable simulation parameters mutated by keyboard
#  handlers.  SpatialGrid provides O(1)-per-query neighbour lookups
#  in SPATIAL mode, avoiding the O(N²) pairwise distance computation.
# ──────────────────────────────────────────────────────────────────────


class Config:
    """
    Mutable runtime parameters shared across the simulation.
    Modified directly by keyboard handlers in the main loop;
    passed by reference into Boid.flock() — changes are frame-immediate.

    φn is auto-computed from the invariant  φp + φa + φn = 1.
    """
    __slots__ = (
        "mode", "phi_p", "phi_a", "sigma",
        "num_boids", "show_grid", "show_help",
    )

    def __init__(self):
        self.mode       = MODE_PROJECTION
        self.phi_p      = DEFAULT_PHI_P
        self.phi_a      = DEFAULT_PHI_A
        self.sigma      = DEFAULT_SIGMA
        self.num_boids  = NUM_BOIDS
        self.show_grid  = False
        self.show_help  = True

    @property
    def phi_n(self) -> float:
        """φn = max(0, 1 − φp − φa) — guarantees weights sum to 1."""
        return max(0.0, 1.0 - self.phi_p - self.phi_a)


class SpatialGrid:
    """
    Toroidal spatial hash grid for O(1)-per-query neighbour lookups.

    Divides the simulation area into cells of size *cell_size* (default
    VISUAL_RANGE).  Wrap-around (toroidal) indexing means birds near
    opposite screen edges can still interact.

    Complexity:
      rebuild()    → O(N)  — clear & repopulate all cells
      get_nearby() → O(K)  — where K = birds in queried cells (not N)
    """
    def __init__(self, cell_size: int = VISUAL_RANGE):
        self.cell_size = cell_size
        self.cols = max(1, int(math.ceil(WIDTH  / cell_size)))
        self.rows = max(1, int(math.ceil(HEIGHT / cell_size)))
        self.cells: dict = defaultdict(list)

    def rebuild(self, boids: list):
        """
        Repopulate the grid from *boids*.  Complexity: O(N).
        Each bird is placed into the cell containing its position,
        modulo wrap-around.
        """
        self.cells.clear()
        for boid in boids:
            cx = int(boid.position.x // self.cell_size) % self.cols
            cy = int(boid.position.y // self.cell_size) % self.rows
            self.cells[(cx, cy)].append(boid)

    def get_nearby(self, position, radius: float) -> list:
        """
        Return all boids in cells overlapping the AABB of *radius*
        around *position*.  The caller must still filter by exact
        Euclidean distance.

        Complexity: O(K) where K is the number of birds in the
        overlapping cells (typically ≪ N).
        """
        cell_r = int(radius // self.cell_size) + 1
        cx0 = int((position.x - radius) // self.cell_size)
        cx1 = int((position.x + radius) // self.cell_size)
        cy0 = int((position.y - radius) // self.cell_size)
        cy1 = int((position.y + radius) // self.cell_size)

        nearby = []
        for cx in range(cx0, cx1 + 1):
            wcx = cx % self.cols
            for cy in range(cy0, cy1 + 1):
                wcy = cy % self.rows
                nearby.extend(self.cells.get((wcx, wcy), ()))
        return nearby

    def draw(self, screen, font):
        """
        Render grid cell boundaries and occupancy counts.
        Only called when show_grid is True (SPATIAL mode).
        """
        import pygame
        color = (50, 55, 50)
        for x in range(0, WIDTH, self.cell_size):
            pygame.draw.line(screen, color, (x, 0), (x, HEIGHT), 1)
        for y in range(0, HEIGHT, self.cell_size):
            pygame.draw.line(screen, color, (0, y), (WIDTH, y), 1)
        for (cx, cy), occupants in self.cells.items():
            px = cx * self.cell_size + 2
            py = cy * self.cell_size + 2
            txt = font.render(str(len(occupants)), True, (80, 90, 80))
            screen.blit(txt, (px, py))
