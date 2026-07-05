"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 3b — LARGER FLOCKS VIA SPATIAL OPTIMISATION               ║
╚══════════════════════════════════════════════════════════════════════╝

 Reduces the per-bird occlusion cost from O(N) to O(N_near + C)
 where C is the number of grid chunks (typically 50–70).

 How it works:
   1. Divide screen into a 10×7 grid of chunks.
   2. Each chunk tracks its centroid and bounding radius.
   3. For each viewing bird, the 3×3 surrounding cells provide
      exact per-bird angular intervals ("near").
   4. All other chunks contribute a single conservative interval
      each based on their bounding circle ("far" approximation).
   5. Chunks act as passive occluders — they are not added to
      visible_neighbours (no alignment contribution from far birds).

 This allows the simulation to run with 500+ birds at acceptable
 frame rates while preserving the same emergent flocking behaviour.

 Usage:  from extensions.spatial_optimization import (
             SpatialChunker, OptimizedBoid
         )
──────────────────────────────────────────────────────────────────────
"""

import math
import pygame

from extensions.anisotropic_bodies import AnisotropicBoid, BOID_SEMI_MAJOR, BOID_SEMI_MINOR
from extensions.blind_angles import BLIND_ANGLE, _interval_in_blind_region
from flock_core import WIDTH, HEIGHT
from occlusion_geom import _normalise_interval, _interval_covered, _merge_interval


# ── Grid constants ─────────────────────────────────────────────────

GRID_COLS = 10
GRID_ROWS = 7
CELL_W = WIDTH / GRID_COLS
CELL_H = HEIGHT / GRID_ROWS


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SpatialChunker                                                      ║
# ╚══════════════════════════════════════════════════════════════════════╝

class SpatialChunker:
    """
    Grid-based spatial chunker for far-field occlusion approximation.

    Divides the screen into GRID_COLS × GRID_ROWS cells.  Each cell
    stores its birds, centroid, and bounding radius.  The chunker
    is rebuilt each frame (O(N)).

    Provides `get_occlusion_entries()` which returns a combined list
    of near-bird entries and far-chunk entries for the occlusion
    merge pipeline.
    """

    __slots__ = ("cols", "rows", "cell_w", "cell_h", "_cells")

    def __init__(self):
        self.cols = GRID_COLS
        self.rows = GRID_ROWS
        self.cell_w = CELL_W
        self.cell_h = CELL_H
        self._cells = {}  # (cx, cy) → {"birds": [], "cx": float, "cy": float, "r": float}

    def rebuild(self, flock: list):
        """
        Rebuild all chunk data from flock positions.  O(N).

        ALGORITHM (two-pass):

        PASS 1 — Bin assignment:
          For each bird, compute its grid cell (cx, cy) via integer
          division of its position by cell size, modulo screen
          dimensions for toroidal wrap.  Group birds by cell key.

        PASS 2 — Per-cell statistics:
          For each non-empty cell, compute:
            centroid = average position of all birds in the cell
            bounding_radius = max(distance from centroid) + semi_major

          The +BOID_SEMI_MAJOR term ensures the bounding circle
          conservatively covers all birds in the cell — the max
          distance from centroid may be to a bird's centre, but the
          bird's body extends beyond that by its semi-major axis.

        Cells with no birds are removed from _cells (cleared).
        """

        # ═══════════════════════════════════════════════════════════
        #  PASS 1: Assign each bird to its grid cell
        # ═══════════════════════════════════════════════════════════
        #
        #  Cell coordinates:
        #    cx = floor(x / cell_w) % cols
        #    cy = floor(y / cell_h) % rows
        #
        #  The modulo handles toroidal wrap — birds at x=995 in a
        #  100px-wide cell map to cx=9 (not cx=9.95).
        # ───────────────────────────────────────────────────────────

        cells = {}
        for boid in flock:
            cx = int(boid.position.x // self.cell_w)
            cy = int(boid.position.y // self.cell_h)
            cx = cx % self.cols     # toroidal wrap (x)
            cy = cy % self.rows     # toroidal wrap (y)
            key = (cx, cy)
            if key not in cells:
                cells[key] = []
            cells[key].append(boid)

        # ═══════════════════════════════════════════════════════════
        #  PASS 2: Compute per-cell centroid and bounding radius
        # ═══════════════════════════════════════════════════════════
        #
        #  Centroid = (Σx / n,  Σy / n)  — simple arithmetic mean.
        #
        #  Bounding radius:
        #    r_cell = max(||p_j − centroid||) + BOID_SEMI_MAJOR
        #
        #  This is a CONSERVATIVE over-approximation.  The chunk's
        #  bounding circle is guaranteed to contain every bird in the
        #  cell.  When used as a far-field occluder, this means we
        #  may over-occlude slightly — a small price for the O(C)
        #  speed-up over O(N_birds).
        # ───────────────────────────────────────────────────────────

        chunk_data = {}
        for key, birds in cells.items():
            if not birds:
                continue

            # ── Centroid: simple average of all bird positions ────
            sum_x = sum(b.position.x for b in birds)
            sum_y = sum(b.position.y for b in birds)
            n = len(birds)
            centroid_x = sum_x / n
            centroid_y = sum_y / n

            # ── Bounding radius: max distance + padding ───────────
            max_dist_sq = 0.0
            for b in birds:
                dx = b.position.x - centroid_x
                dy = b.position.y - centroid_y
                dist_sq = dx * dx + dy * dy
                if dist_sq > max_dist_sq:
                    max_dist_sq = dist_sq

            # Add BOID_SEMI_MAJOR to ensure the circle fully
            # encloses all birds (their bodies extend beyond
            # their centre positions)
            radius = math.sqrt(max_dist_sq) + BOID_SEMI_MAJOR

            chunk_data[key] = {
                "birds": birds,
                "cx": centroid_x,
                "cy": centroid_y,
                "r": radius,
            }

        self._cells = chunk_data

    def get_occlusion_entries(self, viewer_pos, viewer_self):
        """
        Return combined list of near-bird and far-chunk entries.

        ── TWO-PHASE APPROACH ──

        NEAR (3×3 surrounding cells):
          Exact per-bird angular intervals, each with its anisotropic
          projected radius.  These are the birds close enough to the
          viewer that their individual shapes matter for occlusion.

          Toroidal cell indexing ensures correct behaviour at screen
          edges — a viewer in cell (0, y) can see birds in cell
          (cols−1, y) if they're adjacent via wrap.

        FAR (all remaining chunks):
          Single conservative interval per chunk using the chunk's
          bounding radius.  The bounding circle is guaranteed to
          contain every bird in the chunk, so the interval is a safe
          over-approximation.

          Sentinel value None (instead of a bird reference) marks
          chunks as PASSIVE OCCLUDERS — they contribute to occlusion
          but NOT to visible_neighbours (no alignment contribution
          from distant, unresolved birds).

        ── TOROIDAL DISTANCE ──

        All distances use the SHORTEST toroidal path:
          diff = pos_target − pos_viewer
          if |diff.x| > WIDTH/2:  diff.x −= sign(diff.x) × WIDTH
          (same for y)

        This accounts for the periodic boundary — a bird at (10, y)
        and another at (990, y) have a toroidal distance of 20, not 980.

        Returns list of (bird_or_None, distance, centre_angle, half_width)
        ready for closest-first sorting and occlusion merging.
        """

        # ── Viewer's cell coordinates (toroidal-wrapped) ──────────
        vx = int(viewer_pos.x // self.cell_w) % self.cols
        vy = int(viewer_pos.y // self.cell_h) % self.rows

        entries = []

        # ═══════════════════════════════════════════════════════════
        #  PHASE 1 — NEAR: 3×3 surrounding cells
        # ═══════════════════════════════════════════════════════════
        #
        #  Iterate over the 9 cells centred on the viewer's cell.
        #  For each bird in these cells, compute its exact angular
        #  interval using its anisotropic projected radius.
        #
        #  Toroidal modulo: (vx + dx) % cols ensures cells at the
        #  screen edge wrap correctly.  If vx=0 and dx=−1, we
        #  get cx = (0−1) % 10 = 9 — the leftmost cell wraps to
        #  the right edge.
        # ───────────────────────────────────────────────────────────

        for dx in (-1, 0, 1):        # 3 columns
            for dy in (-1, 0, 1):    # 3 rows → 9 cells total
                cx = (vx + dx) % self.cols   # toroidal wrap (x)
                cy = (vy + dy) % self.rows   # toroidal wrap (y)
                cell = self._cells.get((cx, cy))
                if cell is None:
                    continue  # empty cell — skip

                # Process each bird in this near cell
                for bird in cell["birds"]:
                    if bird is viewer_self:
                        continue  # don't include the viewer

                    # ── Toroidal distance (shortest path) ────────
                    #  Compute the 2D displacement accounting for
                    #  periodic wrap.  If the direct distance is
                    #  more than half the screen width, the true
                    #  shortest path wraps around the opposite edge.
                    dx_b = bird.position.x - viewer_pos.x
                    dy_b = bird.position.y - viewer_pos.y
                    if abs(dx_b) > WIDTH / 2:
                        dx_b = dx_b - math.copysign(WIDTH, dx_b)
                    if abs(dy_b) > HEIGHT / 2:
                        dy_b = dy_b - math.copysign(HEIGHT, dy_b)

                    dist = math.sqrt(dx_b * dx_b + dy_b * dy_b)
                    if dist < 0.001:
                        continue  # co-located — degenerate

                    # ── Centre angle on [0, 2π) ───────────────────
                    centre = math.atan2(dy_b, dx_b)
                    if centre < 0:
                        centre += 2 * math.pi

                    # ── Anisotropic projected radius ─────────────
                    #  Elliptical bird: the apparent width depends
                    #  on the viewing angle relative to the bird's
                    #  orientation (velocity direction).
                    #
                    #  projected_radius = √[(a·sin(θ−ψ))² + (b·cos(θ−ψ))²]
                    #    a = BOID_SEMI_MAJOR  (length, along velocity)
                    #    b = BOID_SEMI_MINOR  (width, perpendicular)
                    #    ψ = atan2(v_y, v_x)  (bird's heading)
                    #    θ = centre angle      (viewing direction)
                    if bird.velocity.length_squared() > 0.001:
                        psi = math.atan2(bird.velocity.y, bird.velocity.x)
                    else:
                        psi = 0.0  # stationary bird — default orientation

                    d_angle = centre - psi
                    projected_radius = math.sqrt(
                        (BOID_SEMI_MAJOR * math.sin(d_angle)) ** 2 +
                        (BOID_SEMI_MINOR * math.cos(d_angle)) ** 2
                    )

                    half = math.asin(min(projected_radius / dist, 1.0))
                    entries.append((bird, dist, centre, half))

        # ═══════════════════════════════════════════════════════════
        #  PHASE 2 — FAR: all remaining chunks
        # ═══════════════════════════════════════════════════════════
        #
        #  For every cell NOT in the 3×3 near region, contribute a
        #  SINGLE conservative interval representing the entire chunk
        #  as a unified occluder.
        #
        #  The chunk is treated as a circle of radius r_cell centred
        #  at the chunk's centroid.  This is a conservative
        #  over-approximation — the angular width may be slightly
        #  larger than the true combined width of all birds in the
        #  chunk, but this only makes occlusion slightly more
        #  aggressive (safer than under-occluding).
        #
        #  Toroidal-aware cell distance check:
        #    min(|cx−vx|, cols−|cx−vx|) gives the true grid distance
        #    accounting for wrap.  If this is ≤ 1 in both x and y,
        #    the cell is in the 3×3 near region and was already
        #    processed in Phase 1.
        # ───────────────────────────────────────────────────────────

        for key, cell in self._cells.items():
            cx_cell, cy_cell = key

            # ── Toroidal-aware cell distance ──────────────────────
            #  Check if this cell is within the 3×3 near region.
            #  The minimum of (direct distance, wrap-around distance)
            #  gives the true grid distance.
            dx_wrap = min(abs(cx_cell - vx), self.cols - abs(cx_cell - vx))
            dy_wrap = min(abs(cy_cell - vy), self.rows - abs(cy_cell - vy))
            if dx_wrap <= 1 and dy_wrap <= 1:
                continue  # already processed as near — skip

            # ── Toroidal distance to chunk centroid ───────────────
            dx_c = cell["cx"] - viewer_pos.x
            dy_c = cell["cy"] - viewer_pos.y
            if abs(dx_c) > WIDTH / 2:
                dx_c = dx_c - math.copysign(WIDTH, dx_c)
            if abs(dy_c) > HEIGHT / 2:
                dy_c = dy_c - math.copysign(HEIGHT, dy_c)

            dist = math.sqrt(dx_c * dx_c + dy_c * dy_c)
            if dist < 0.001:
                continue

            centre = math.atan2(dy_c, dx_c)
            if centre < 0:
                centre += 2 * math.pi

            # ── Angular half-width from bounding circle ───────────
            #  half = asin(r_cell / d)
            #  The bounding circle may be larger than any individual
            #  bird, so this over-approximates the true occlusion.
            half = math.asin(min(cell["r"] / dist, 1.0))

            # ── Sentinel: None → passive occluder ─────────────────
            #  Chunks marked with None are merged into the occluded
            #  set but NOT added to visible_neighbours.  Distant,
            #  unresolved birds don't contribute to alignment.
            entries.append((None, dist, centre, half))

        return entries


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  OptimizedBoid                                                        ║
# ╚══════════════════════════════════════════════════════════════════════╝

class OptimizedBoid(AnisotropicBoid):
    """
    Extension 3b: Spatially optimized occlusion using chunk-based
    far-field approximation.

    Overrides _compute_projection_and_visibility() to use the
    SpatialChunker for O(N_near + C) per-bird cost instead of O(N).
    """

    def _compute_projection_and_visibility(self, boids: list):
        """
        Optimized occlusion with chunk-based far-field approximation.

        Near birds (3×3 surrounding cells) are processed exactly.
        Far chunks contribute single conservative intervals as
        passive occluders (no alignment contribution).
        """
        # ── Get combined near+far entries from chunker ────────────
        # The chunker is stored on the flock list or passed externally.
        # We require the caller to set `self._chunker` before calling.
        chunker = getattr(self, '_chunker', None)
        if chunker is None:
            # Fall back to parent if no chunker available
            return super()._compute_projection_and_visibility(boids)

        entries = chunker.get_occlusion_entries(
            self.position, self
        )

        if not entries:
            return pygame.Vector2(0, 0), [], 0.0, []

        # ── Blind region from our heading ─────────────────────────
        if self.velocity.length_squared() > 0.001:
            heading = math.atan2(self.velocity.y, self.velocity.x)
        else:
            heading = 0.0
        if heading < 0:
            heading += 2 * math.pi

        blind_centre = heading + math.pi
        if blind_centre >= 2 * math.pi:
            blind_centre -= 2 * math.pi
        blind_start = blind_centre - BLIND_ANGLE / 2
        blind_end   = blind_centre + BLIND_ANGLE / 2
        if blind_start < 0:
            blind_start += 2 * math.pi
        if blind_end > 2 * math.pi:
            blind_end -= 2 * math.pi

        # ── Filter blind region ───────────────────────────────────
        filtered = []
        for bird_or_none, dist, centre, half in entries:
            start = centre - half
            end   = centre + half
            segments = _normalise_interval(start, end)

            all_in_blind = all(
                _interval_in_blind_region(s, e, blind_start, blind_end)
                for s, e in segments
            )
            if not all_in_blind:
                filtered.append((bird_or_none, dist, centre, half))

        if not filtered:
            return pygame.Vector2(0, 0), [], 0.0, []

        # ── Sort closest-first ────────────────────────────────────
        filtered.sort(key=lambda x: x[1])

        # ── Incremental occlusion merge ───────────────────────────
        merged = []
        visible_neighbours = []

        for bird_or_none, dist, centre, half in filtered:
            start = centre - half
            end   = centre + half
            segments = _normalise_interval(start, end)

            is_visible = any(
                not _interval_covered(s, e, merged) for s, e in segments
            )
            if is_visible:
                # Chunks (bird_or_none is None) are passive occluders:
                # they merge into the occluded set but do NOT
                # contribute to visible_neighbours for alignment.
                if bird_or_none is not None:
                    visible_neighbours.append((bird_or_none, dist))
                for s, e in segments:
                    _merge_interval(s, e, merged)

        # ── δ̂ from domain boundaries ────────────────────────────
        delta = pygame.Vector2(0, 0)
        two_pi = 2 * math.pi
        for s, e in merged:
            delta += pygame.Vector2(math.cos(s), math.sin(s))
            delta += pygame.Vector2(math.cos(e), math.sin(e))

        if (len(merged) == 1 and
                merged[0][0] < 1e-9 and
                merged[0][1] > two_pi - 1e-9):
            delta = pygame.Vector2(0, 0)

        if delta.length() > 0:
            delta.normalize_ip()

        # ── Internal opacity Θ_i ─────────────────────────────────
        occluded = sum(e - s for s, e in merged)
        theta = min(occluded / two_pi, 1.0)

        return delta, visible_neighbours, theta, merged
