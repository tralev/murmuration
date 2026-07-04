"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 1 — HEADER & OVERVIEW                                      ║
╚══════════════════════════════════════════════════════════════════════╝

 alg2.py — Dual-Mode Bird Flock Simulation (Python / Pygame)
 ─────────────────────────────────────────────────────────
 Based on:  Pearce, Miller, Rowlands & Turner (2014)
            "Role of projection in the control of bird flocks"
            PNAS 111(29), 10422–10426.
            DOI: 10.1073/pnas.1402202111

 Two switchable flocking modes (press 'm' to toggle):
 ─────────────────────────────────────────────────────
   MODE 0 — PROJECTION   Hybrid projection model (Pearce et al., Eq. 3)
            v_i = φp·δ̂_i + φa·⟨v̂_j⟩_visible + φn·η̂_i

            δ̂_i  = direction to the nearest boundary of the occluded
                   angular domain (computed via incremental angular-
                   interval merging of closer-first neighbours).
            Visibility determined by occlusion: a neighbour is visible
            iff any portion of its subtended angular interval is NOT
            already covered by birds closer to the observer.
            Internal opacity Θ_i = fraction of 2π occluded.

   MODE 1 — SPATIAL      Topological Reynolds boids (Reynolds 1987)
            Separation / Alignment / Cohesion with σ nearest neighbours
            within VISUAL_RANGE.  Weights are repurposed:
              φp → separation, φa → alignment, φn → cohesion.

 See the companion files alg2.m (GNU Octave) and alg2.sce (Scilab)
 for ports to other scientific computing environments.

 Runtime controls:  press 'h' for help overlay, 'esc' to quit.
"""

import pygame
from collections import defaultdict
import random
import math
import sys


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECTION 2 — CONFIGURATION CONSTANTS                                ║
# ╚══════════════════════════════════════════════════════════════════════╝
#  These are the physical and numerical parameters of the simulation.
#  φp, φa, φn, and σ can be adjusted at runtime via keyboard controls.
# ──────────────────────────────────────────────────────────────────────

# ── Display ───────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1000, 700               # simulation area (pixels)
FPS           = 60                      # target frame rate

# ── Flock parameters ──────────────────────────────────────────────────
NUM_BOIDS      = 150                    # number of birds
BOID_SIZE      = 3                      # bird radius b (paper: b = 1)
V0             = 4                      # constant cruising speed v₀ (paper: v₀ = 1)
MAX_FORCE      = 0.15                   # max steering force (smooth turning)
VISUAL_RANGE   = 70                     # neighbour search radius (spatial mode)

# ── Default model weights  (φp + φa + φn ≡ 1) ────────────────────────
DEFAULT_PHI_P  = 0.03                   # projection / separation weight
DEFAULT_PHI_A  = 0.80                   # alignment weight
DEFAULT_SIGMA  = 4                      # number of nearest visible neighbours

# ── Mode identifiers ──────────────────────────────────────────────────
MODE_PROJECTION = 0
MODE_SPATIAL    = 1

MODE_NAMES = {
    MODE_PROJECTION: "PROJECTION  (Pearce et al. 2014)",
    MODE_SPATIAL:    "SPATIAL     (topological Reynolds + grid)",
}


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECTION 2d — CSV LOGGING SETUP                                     ║
# ╚══════════════════════════════════════════════════════════════════════╝
#  Metrics (frame, mode, θ, θ', α, FPS) are appended to a CSV file
#  every LOG_EVERY frames.  The file is opened at startup and closed
#  on exit.  Set LOG_FILE = None to disable CSV logging.
# ──────────────────────────────────────────────────────────────────────

LOG_FILE  = "murmuration_metrics.csv"   # set to None to disable CSV
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
      rebuild()  → O(N)  — clear & repopulate all cells
      get_nearby() → O(K) — where K = birds in queried cells (not N)
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

    def get_nearby(self, position: "pygame.Vector2", radius: float) -> list:
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

    def draw(self, screen: pygame.Surface, font: pygame.font.Font):
        """
        Render grid cell boundaries and occupancy counts.
        Only called when show_grid is True (SPATIAL mode).
        """
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


class Boid:
    """
    A single bird agent.  Holds position, velocity, acceleration, and
    a cached internal opacity Θ (computed during the projection step
    and reused by the metrics system).

    Physics (shared by both modes):
      Euler integration with speed clamping to [0.3·V₀, V₀] and
      toroidal position wrap.
    """
    __slots__ = ("position", "velocity", "acceleration", "_last_theta")

    def __init__(self):
        self.position = pygame.Vector2(
            random.uniform(0, WIDTH),
            random.uniform(0, HEIGHT),
        )
        angle = random.uniform(0, 2 * math.pi)
        self.velocity = pygame.Vector2(
            math.cos(angle), math.sin(angle)
        ) * random.uniform(1, V0)
        self.acceleration = pygame.Vector2(0, 0)
        self._last_theta = 0.0          # cached internal opacity

    # ╔══════════════════════════════════════════════════════════╗
    # ║  SECTION 9 — PHYSICS UPDATE  (shared by both modes)      ║
    # ╚══════════════════════════════════════════════════════════╝
    #
    #  Euler integration with speed clamping and toroidal wrap.
    #  This is the same physics step regardless of flocking mode:
    #
    #    1. v ← v + a          apply accumulated steering force
    #    2. |v| clamped to [0.3·V₀, V₀]
    #       - cap at V₀ (max cruising speed)
    #       - floor at 0.3·V₀ (prevent stagnation)
    #    3. p ← p + v          move forward
    #    4. toroidal wrap      re-enter from opposite edge
    #    5. a ← 0              reset steering accumulator
    #
    #  Complexity: O(N) — single pass over all boids.
    # ───────────────────────────────────────────────────────────

    def update(self):
        """
        Euler integration step.
        v ← v + a               (apply accumulated steering)
        speed clamped to [0.3·V₀, V₀]
        p ← p + v               (move)
        toroidal wrap at edges
        a ← 0                   (reset steering accumulator)
        """
        self.velocity += self.acceleration
        speed = self.velocity.length()
        if speed > V0:
            self.velocity.scale_to_length(V0)
        elif speed < V0 * 0.3:
            if speed > 0.001:
                self.velocity.scale_to_length(V0 * 0.3)
            else:
                a = random.uniform(0, 2 * math.pi)
                self.velocity = pygame.Vector2(math.cos(a), math.sin(a)) * V0 * 0.3

        self.position += self.velocity
        self.acceleration *= 0

        # Toroidal wrap: birds exiting one edge re-enter from the opposite
        if   self.position.x > WIDTH:  self.position.x = 0
        elif self.position.x < 0:      self.position.x = WIDTH
        if   self.position.y > HEIGHT: self.position.y = 0
        elif self.position.y < 0:      self.position.y = HEIGHT

    def apply_force(self, force: pygame.Vector2):
        """Accumulate a steering force for the current frame."""
        self.acceleration += force

    # ── Mode dispatch ──────────────────────────────────────────────

    def flock(self, boids: list, config: Config, grid: SpatialGrid = None):
        """
        Dispatch to the active flocking logic based on config.mode.
        This is the per-frame decision rule for each bird.
        """
        if config.mode == MODE_PROJECTION:
            self._flock_projection(boids, config)
        else:
            self._flock_spatial(boids, config, grid)

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  SECTION 5 — PROJECTION MODEL  (MODE 0)                     ║
    # ╚══════════════════════════════════════════════════════════════╝
    #
    #  Reference:  Pearce et al. (2014), Eq. (3):
    #    v_i(t+1) = φp · δ̂_i(t) + φa · ⟨v̂_j(t)⟩_visible + φn · η̂_i(t)
    #
    #  δ̂_i  — unit vector pointing toward the nearest boundary of the
    #          occluded angular domain.  Computed by summing unit vectors
    #          to each boundary of each merged occluded interval.
    #
    #  ⟨v̂_j⟩_visible  — mean heading of the σ nearest *visible* neighbours
    #                     (visibility via angular-interval occlusion).
    #
    #  η̂_i  — random unit vector (intrinsic noise).
    #
    #  Θ_i  — internal opacity = (sum of merged interval widths) / 2π.
    #          Cached on the boid and reused by metrics.
    # ─────────────────────────────────────────────────────────────────

    def _flock_projection(self, boids: list, config: Config):
        """
        Hybrid projection model update for one bird.

        Steps:
          1. Compute δ̂, visible neighbours, and Θ via angular occlusion.
          2. Alignment with σ nearest visible neighbours.
          3. Noise vector.
          4. Desired direction: v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
          5. Reynolds steering toward desired direction.
        """
        # ── Step 1: projection direction & visible neighbours ──────
        #  O(N log N) — compute angular intervals to all other birds,
        #  merge them closest-first, and determine δ̂ from domain boundaries.
        delta, visible, theta = self._compute_projection_and_visibility(boids)
        self._last_theta = theta

        # ── Step 2: alignment with σ nearest visible neighbours ────
        #  ⟨v̂_j⟩_visible — mean velocity direction of σ closest visible birds.
        align = pygame.Vector2(0, 0)
        if visible:
            nearest = visible[:config.sigma]
            for nb, _ in nearest:
                align += nb.velocity
            align /= len(nearest)

        # ── Step 3: noise — random unit vector η̂ ──────────────────
        na = random.uniform(0, 2 * math.pi)
        noise = pygame.Vector2(math.cos(na), math.sin(na))

        # ── Step 4: desired direction (Eq. 3 from paper) ───────────
        #  v_desired = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
        desired = delta * config.phi_p
        if align.length() > 0.001:
            desired += align.normalize() * config.phi_a
        else:
            # fallback: use own heading when no visible neighbours
            if self.velocity.length() > 0.001:
                desired += self.velocity.normalize() * config.phi_a
        desired += noise * config.phi_n

        if desired.length() < 0.001:
            desired = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))

        # Normalise to constant speed V₀ for smooth animation.
        # (The paper lets speed vary naturally; this is an aesthetic choice.)
        desired.normalize_ip()
        desired *= V0

        # ── Step 5: Reynolds-style steering ────────────────────────
        #  steer = v_desired − v_current, clamped to MAX_FORCE
        steer = desired - self.velocity
        if steer.length() > MAX_FORCE:
            steer.scale_to_length(MAX_FORCE)
        self.apply_force(steer)

    def _compute_projection_and_visibility(self, boids: list):
        """
        Core of the hybrid projection model — angular-interval occlusion.

        For each other bird j, compute the angular interval [θⱼ − αⱼ, θⱼ + αⱼ]
        it subtends, where  αⱼ = arcsin(min(b / dⱼ, 1)).

        Process birds closest-first (distance-sorted).  A bird is *visible*
        iff any part of its interval is NOT already covered by previously
        merged (closer) intervals.  Visible intervals are then merged into
        the occluded set.

        δ̂ is computed from the *boundaries* of the merged occluded intervals:
          δ̂ = Σ_{boundaries} (cos θ, sin θ)   (normalised)

        Returns
        -------
        delta   : pygame.Vector2  — unit vector δ̂ to nearest domain boundary
        visible : list[(Boid, float)] — visible neighbours (closest first)
        theta   : float  — internal opacity Θ_i ∈ [0, 1]
        """
        # ── Build angular intervals for all other birds ────────────
        entries = []  # (boid, distance, centre_angle, half_width)
        for other in boids:
            if other is self:
                continue
            diff = other.position - self.position
            dist = diff.length()
            if dist < 0.001:
                continue
            centre = math.atan2(diff.y, diff.x)
            if centre < 0:
                centre += 2 * math.pi
            half = math.asin(min(BOID_SIZE / dist, 1.0))
            entries.append((other, dist, centre, half))

        if not entries:
            return pygame.Vector2(0, 0), [], 0.0

        # Sort closest-first — occlusion is distance-dependent
        entries.sort(key=lambda x: x[1])

        # ── Incremental occlusion merge ────────────────────────────
        #  For each bird (closest first):
        #    - Build [start, end] segments (handling wrap at 2π)
        #    - Check if any segment is NOT covered by existing merged set
        #    - If visible: add to visible list, merge segments into occluded set
        merged = []              # [(start, end), …]  merged occluded intervals
        visible_neighbours = []  # [(boid, distance), …]

        for other, dist, centre, half in entries:
            start = centre - half
            end   = centre + half
            segments = _normalise_interval(start, end)

            # Visibility test: is ANY segment partially uncovered?
            is_visible = any(
                not _interval_covered(s, e, merged) for s, e in segments
            )
            if is_visible:
                visible_neighbours.append((other, dist))
                for s, e in segments:
                    _merge_interval(s, e, merged)

        # ── δ̂ from domain boundaries ─────────────────────────────
        #  Sum unit vectors to each occluded interval boundary.
        #  If fully surrounded (one interval covering all 2π): δ̂ = 0.
        delta = pygame.Vector2(0, 0)
        for s, e in merged:
            delta += pygame.Vector2(math.cos(s), math.sin(s))
            delta += pygame.Vector2(math.cos(e), math.sin(e))

        if (len(merged) == 1 and
                merged[0][0] < 1e-9 and
                merged[0][1] > 2 * math.pi - 1e-9):
            delta = pygame.Vector2(0, 0)

        if delta.length() > 0:
            delta.normalize_ip()

        # ── Internal opacity Θ_i ──────────────────────────────────
        #  Θ = (total occluded angular width) / 2π
        occluded = sum(e - s for s, e in merged)
        theta = min(occluded / (2 * math.pi), 1.0)

        return delta, visible_neighbours, theta

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  SECTION 6 — SPATIAL MODEL  (MODE 1)                        ║
    # ╚══════════════════════════════════════════════════════════════╝
    #
    #  Reference:  Reynolds, C. W. (1987)
    #    "Flocks, Herds, and Schools: A Distributed Behavioral Model"
    #    SIGGRAPH '87, DOI: 10.1145/37401.37406
    #
    #  Classic three-rule boids with topological neighbour selection:
    #    Separation  — steer away from neighbours that are too close
    #    Alignment   — steer toward the average heading of neighbours
    #    Cohesion    — steer toward the average position of neighbours
    #
    #  Only the σ nearest neighbours within VISUAL_RANGE contribute
    #  (topological, not metric, range — see Ballerini et al. 2008).
    #  Queried via the spatial hash grid in O(1) per bird.
    #
    #  Weights are repurposed from the projection model:
    #    φp → separation strength  (× 2.0)
    #    φa → alignment strength   (× 1.2)
    #    φn → cohesion strength    (× 1.5)
    # ─────────────────────────────────────────────────────────────────

    def _flock_spatial(self, boids: list, config: Config, grid: SpatialGrid):
        """
        Topological Reynolds boids update for one bird.

        Steps:
          1. Query spatial grid for candidate neighbours.
          2. Filter by VISUAL_RANGE, sort by distance, take σ nearest.
          3. Compute separation / alignment / cohesion steering forces.
          4. Add noise, apply weighted forces.
        """
        # ── Step 1: query spatial grid ─────────────────────────────
        #  O(K) where K ≪ N.  Returns boids in cells overlapping the
        #  AABB of VISUAL_RANGE around this bird.
        candidates = grid.get_nearby(self.position, VISUAL_RANGE)

        # ── Step 2: filter by exact distance, sort, take σ nearest ─
        neighbours = []
        for other in candidates:
            if other is self:
                continue
            d = self.position.distance_to(other.position)
            if d < VISUAL_RANGE:
                neighbours.append((other, d))
        neighbours.sort(key=lambda x: x[1])
        neighbours = neighbours[:config.sigma]
        n = len(neighbours)

        separation = pygame.Vector2(0, 0)
        alignment  = pygame.Vector2(0, 0)
        cohesion   = pygame.Vector2(0, 0)

        if n > 0:
            for other, d in neighbours:
                # ── Alignment: sum neighbour velocities ────────────
                alignment += other.velocity

                # ── Cohesion: sum neighbour positions ──────────────
                cohesion += other.position

                # ── Separation: steer away from very close neighbours
                #  Only active when d < 0.3 × VISUAL_RANGE.
                if d < VISUAL_RANGE * 0.3:
                    diff = self.position - other.position
                    if d > 0.001:
                        diff /= d          # weight ∝ 1/distance
                    separation += diff

            alignment /= n
            cohesion  /= n

            # ── Alignment: steer toward mean heading ───────────────
            if alignment.length() > 0.001:
                alignment.scale_to_length(V0)
            alignment -= self.velocity
            if alignment.length() > MAX_FORCE:
                alignment.scale_to_length(MAX_FORCE)

            # ── Cohesion: steer toward mean position ───────────────
            cohesion -= self.position
            if cohesion.length() > 0.001:
                cohesion.scale_to_length(V0)
            cohesion -= self.velocity
            if cohesion.length() > MAX_FORCE:
                cohesion.scale_to_length(MAX_FORCE)

            # ── Separation: steer away from close neighbours ───────
            if separation.length() > 0.001:
                separation.scale_to_length(V0)
            separation -= self.velocity
            if separation.length() > MAX_FORCE:
                separation.scale_to_length(MAX_FORCE)

        # ── Step 4: noise for exploration ──────────────────────────
        na = random.uniform(0, 2 * math.pi)
        noise = pygame.Vector2(math.cos(na), math.sin(na)) * MAX_FORCE * 0.8

        # ── Weighted force accumulation ────────────────────────────
        #  Forces are weighted by repurposed φp/φa/φn plus a noise term.
        self.apply_force(separation * config.phi_p * 2.0)
        self.apply_force(alignment  * config.phi_a * 1.2)
        self.apply_force(cohesion   * config.phi_n * 1.5)
        self.apply_force(noise)

    # ── Opacity (for metrics sampling in spatial mode) ─────────────

    def compute_internal_opacity(self, boids: list) -> float:
        """
        Compute Θ — fraction of 2π view occluded by other birds.

        In PROJECTION mode this is cached during the projection step.
        In SPATIAL mode, FlockMetrics calls this on a small sample (5 birds)
        to estimate Θ without incurring O(N²) per-frame cost.
        """
        intervals = []
        for other in boids:
            if other is self:
                continue
            diff = other.position - self.position
            dist = diff.length()
            if dist < 0.001:
                continue
            centre = math.atan2(diff.y, diff.x)
            if centre < 0:
                centre += 2 * math.pi
            half = math.asin(min(BOID_SIZE / dist, 1.0))
            intervals.extend(_normalise_interval(centre - half, centre + half))

        if not intervals:
            return 0.0
        merged = _merge_all(intervals)
        occluded = sum(e - s for s, e in merged)
        return min(occluded / (2 * math.pi), 1.0)

    # ── Drawing ──────────────────────────────────────────────────────

    def draw(self, screen: pygame.Surface, config: Config):
        """
        Render this bird as a small triangle pointing in its heading direction.
        Colour: cool blue-white in PROJECTION mode, warm amber in SPATIAL mode.
        """
        if self.velocity.length_squared() > 0.001:
            direction = math.atan2(self.velocity.y, self.velocity.x)
        else:
            direction = 0

        tip = self.position + pygame.Vector2(
            math.cos(direction), math.sin(direction)
        ) * BOID_SIZE * 2.5
        back_left = self.position + pygame.Vector2(
            math.cos(direction + 2.3), math.sin(direction + 2.3)
        ) * BOID_SIZE * 1.5
        back_right = self.position + pygame.Vector2(
            math.cos(direction - 2.3), math.sin(direction - 2.3)
        ) * BOID_SIZE * 1.5

        if config.mode == MODE_PROJECTION:
            color = (200, 210, 230)
        else:
            color = (230, 200, 160)

        pygame.draw.polygon(screen, color, [tip, back_left, back_right])


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECTION 4 — ANGULAR-INTERVAL UTILITIES                            ║
# ╚══════════════════════════════════════════════════════════════════════╝
#  Module-level helper functions for working with angular intervals
#  on [0, 2π).  Used by both the projection model and external opacity.
#
#  An angular interval is a pair (start, end) representing the arc
#  [start, end) subtended by a bird as seen from a viewpoint.
#  Intervals may wrap around 2π (e.g., start = 6.0, end = 0.5).
# ──────────────────────────────────────────────────────────────────────

def _normalise_interval(start: float, end: float) -> list:
    """
    Split an angular interval [start, end] into one or two segments
    that each lie entirely within [0, 2π).

    Handles wrap-around:
      start < 0       → [(start + 2π, 2π), (0, end)]
      end > 2π        → [(start, 2π), (0, end − 2π)]
      both in [0, 2π) → [(start, end)]
    """
    segments = []
    if start < 0:
        segments.append((start + 2 * math.pi, 2 * math.pi))
        segments.append((0, end))
    elif end > 2 * math.pi:
        segments.append((start, 2 * math.pi))
        segments.append((0, end - 2 * math.pi))
    else:
        segments.append((start, end))
    return segments


def _interval_covered(start: float, end: float, merged: list) -> bool:
    """
    Check whether the interval [start, end] is fully covered by the
    merged (occluded) interval set.

    Walks through merged intervals in order, advancing a cursor from
    start toward end.  If cursor reaches end, the interval is covered.
    Complexity: O(|merged|) per call.
    """
    cursor = start
    for ms, me in merged:
        if ms <= cursor + 1e-9 < me:
            cursor = max(cursor, me)
        if cursor >= end - 1e-9:
            return True
    return cursor >= end - 1e-9


def _merge_interval(start: float, end: float, merged: list):
    """
    Insert [start, end] into the sorted merged interval list,
    merging with at most two adjacent intervals.

    Uses binary search to find the insertion point, then merges left
    and right (chaining in case the new interval bridges multiple
    existing ones).  Complexity: O(log |merged| + merges).
    """
    n = len(merged)
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        if merged[mid][0] < start:
            lo = mid + 1
        else:
            hi = mid
    idx = lo

    merged.insert(idx, [start, end])

    # Merge with left neighbour if overlapping
    if idx > 0 and merged[idx - 1][1] >= merged[idx][0] - 1e-9:
        merged[idx - 1][1] = max(merged[idx - 1][1], merged[idx][1])
        merged.pop(idx)
        idx -= 1

    # Merge with right neighbours (chain in case of multiple overlaps)
    while idx < len(merged) - 1 and merged[idx][1] >= merged[idx + 1][0] - 1e-9:
        merged[idx][1] = max(merged[idx][1], merged[idx + 1][1])
        merged.pop(idx + 1)


def _merge_all(intervals: list) -> list:
    """
    Sort-and-merge a list of (start, end) intervals into non-overlapping
    merged intervals.  Used by compute_internal_opacity and external opacity.

    Complexity: O(N log N) where N = |intervals|.
    """
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: x[0])
    merged = [list(intervals[0])]
    for s, e in intervals[1:]:
        if s <= merged[-1][1] + 1e-9:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECTION 7 — EXTERNAL OPACITY  (Θ')                                  ║
# ╚══════════════════════════════════════════════════════════════════════╝
#  Θ' — fraction of the sky obscured from a distant external observer.
#  The observer is placed at (−2000, HEIGHT/2), far to the left of the
#  flock.  Angular intervals subtended by each bird are merged to find
#  the total occluded angular width.
#
#  Complexity: O(N log N) where N = |flock|.
# ──────────────────────────────────────────────────────────────────────

def _external_opacity(flock: list) -> float:
    """
    Compute Θ' — external opacity from a distant left-side observer.

    For each bird, compute the angular interval it subtends from the
    viewpoint at (−2000, HEIGHT/2).  Sort all intervals by start angle,
    merge overlaps, and sum the merged widths divided by 2π.
    """
    if not flock:
        return 0.0

    viewpoint = pygame.Vector2(-2000, HEIGHT / 2)
    intervals = []
    for b in flock:
        diff = b.position - viewpoint
        dist = diff.length()
        if dist < 0.001:
            continue
        centre = math.atan2(diff.y, diff.x)
        if centre < 0:
            centre += 2 * math.pi
        half = math.asin(min(BOID_SIZE / dist, 1.0))
        intervals.extend(_normalise_interval(centre - half, centre + half))

    merged = _merge_all(intervals)
    occluded = sum(e - s for s, e in merged)
    return min(occluded / (2 * math.pi), 1.0)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECTION 8 — METRICS COMPUTATION                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝
#  Real-time scientific metrics with exponential moving average (EMA)
#  smoothing.  Updated once per frame.
#
#  Θ   (internal opacity) — mean fraction of each bird's 2π view
#        occluded by other birds.  Exact in PROJECTION mode (cached
#        during the projection step).  Sampled from 5 random birds
#        in SPATIAL mode to avoid O(N²) cost.
#
#  Θ'  (external opacity) — fraction of sky obscured from a distant
#        observer placed far to the left of the flock.
#
#  α   (order parameter) — |Σ v_i| / (N · v₀).  α ≈ 1 when all birds
#        are aligned; α ≈ 0 for random headings.
#
#  All metrics use EMA smoothing:  x_ema ← x_ema + (x_raw − x_ema) × s
#  with default smoothing factor s = 0.04.
# ──────────────────────────────────────────────────────────────────────

class FlockMetrics:
    """Real-time scientific metrics with EMA smoothing."""
    __slots__ = ("_fps", "_theta", "_theta_ext", "_alpha", "_theta_samples")

    SMOOTH  = 0.04    # EMA factor — lower = smoother but slower response
    SAMPLES = 5        # birds sampled for Θ in SPATIAL mode

    def __init__(self):
        self._fps         = 0.0
        self._theta       = 0.0    # Θ  — mean internal opacity (EMA)
        self._theta_ext   = 0.0    # Θ' — external opacity (EMA)
        self._alpha       = 0.0    # α  — order parameter (EMA)
        self._theta_samples = 0

    def update(self, flock: list, clock: pygame.time.Clock, config: Config):
        """
        Update all metrics for the current frame.

        Parameters
        ----------
        flock  : list[Boid]  — all birds
        clock  : pygame.time.Clock
        config : Config      — for mode-dependent Θ computation
        """
        s = self.SMOOTH
        n = len(flock)
        if n == 0:
            return

        # ── FPS (EMA-smoothed) ────────────────────────────────────
        self._fps += (clock.get_fps() - self._fps) * s

        # ── Θ — internal opacity ──────────────────────────────────
        #  PROJECTION: exact, already cached on each boid as _last_theta.
        #  SPATIAL:    sampled from 5 random birds to avoid O(N²).
        if config.mode == MODE_PROJECTION:
            theta = sum(b._last_theta for b in flock) / n
        else:
            sample_n = min(self.SAMPLES, n)
            sampled = random.sample(flock, sample_n)
            theta = sum(b.compute_internal_opacity(flock) for b in sampled) / sample_n
        self._theta += (theta - self._theta) * s

        # ── α — order parameter  |Σ v_i| / (N · v₀) ──────────────
        #  Measures global alignment.  Near 1 = all birds aligned.
        total_v = pygame.Vector2(0, 0)
        for b in flock:
            total_v += b.velocity
        alpha = total_v.length() / (n * V0)
        self._alpha += (alpha - self._alpha) * s

        # ── Θ' — external opacity ─────────────────────────────────
        theta_ext = _external_opacity(flock)
        self._theta_ext += (theta_ext - self._theta_ext) * s

    # ── Properties ───────────────────────────────────────────────────

    @property
    def fps(self) -> float:                return self._fps
    @property
    def internal_opacity(self) -> float:    return self._theta
    @property
    def external_opacity(self) -> float:    return self._theta_ext
    @property
    def order_param(self) -> float:         return self._alpha

    # ── Draw ─────────────────────────────────────────────────────────

    def draw(self, screen: pygame.Surface, font: pygame.font.Font,
             config: Config, flock_len: int):
        """
        Render metrics as a multi-line text overlay in the top-left corner.
        """
        mode_label = MODE_NAMES.get(config.mode, "???")
        theta_label = (
            f"Opacity   internal  Θ  = {self._theta:.3f}"
            if config.mode == MODE_PROJECTION else
            f"Opacity   internal  Θ  ~ {self._theta:.3f}  (sampled ×{self.SAMPLES})"
        )

        lines = [
            f"FPS: {self._fps:.0f}    Boids: {flock_len}    Mode: {mode_label}",
            f"φp={config.phi_p:.3f}    φa={config.phi_a:.3f}    φn={config.phi_n:.3f}    σ={config.sigma}",
            theta_label,
            f"          external  Θ' = {self._theta_ext:.3f}",
            f"Order param          α  = {self._alpha:.3f}",
        ]
        y = 10
        for line in lines:
            surf = font.render(line, True, (170, 200, 170))
            screen.blit(surf, (10, y))
            y += 20


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECTION 10 — HELP OVERLAY                                          ║
# ╚══════════════════════════════════════════════════════════════════════╝
#  Semi-transparent panel in the top-right corner showing all keyboard
#  controls.  Toggled by pressing 'h'.
# ──────────────────────────────────────────────────────────────────────

_HELP_LINES = [
    "CONTROLS",
    "─────────────────────────────────────────",
    "M         toggle PROJECTION / SPATIAL mode",
    "↑ / ↓     φp  ±0.01",
    "← / →     φa  ±0.01   (φn = 1 − φp − φa)",
    "[ / ]     σ   ±1      (neighbour count)",
    "+ / -     add / remove 10 birds",
    "G         toggle grid overlay (SPATIAL)",
    "H         hide this help",
    "SPACE     pause / resume",
    "R         reset flock",
    "ESC       quit",
]


def _draw_help(screen: pygame.Surface, font: pygame.font.Font):
    """
    Render the help overlay as a semi-transparent panel in the top-right.
    """
    x, y = WIDTH - 340, 10
    # Semi-transparent dark background
    bg = pygame.Surface((330, len(_HELP_LINES) * 18 + 12), pygame.SRCALPHA)
    bg.fill((10, 12, 18, 200))
    screen.blit(bg, (x - 4, y - 4))
    for line in _HELP_LINES:
        surf = font.render(line, True, (200, 200, 160))
        screen.blit(surf, (x, y))
        y += 18


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECTION 12 — MAIN LOOP                                             ║
# ╚══════════════════════════════════════════════════════════════════════╝
#  The main simulation loop runs at a target 60 FPS.  Each frame:
#
#    1. INPUT   — process Pygame events (keyboard, window close)
#    2. UPDATE  — if not paused:
#       a. Rebuild spatial grid (if in SPATIAL mode or show_grid)
#       b. For each bird: flock() → compute steering forces
#       c. For each bird: update() → Euler integration + wrap
#       d. Compute metrics (Θ, Θ', α, FPS)
#    3. RENDER  — clear screen, draw birds, metrics, grid, help, badge
#    4. FLIP    — present frame to display
# ──────────────────────────────────────────────────────────────────────

def main():
    # ╔══════════════════════════════════════════════════════════════╗
    # ║  SECTION 2b — FIGURE SETUP  (Pygame window)                  ║
    # ╚══════════════════════════════════════════════════════════════╝
    #
    #  Initialise Pygame and create the display window.
    #  Octave/Scilab use figure() for this; Python uses Pygame.
    # ───────────────────────────────────────────────────────────────
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(
        "Murmuration — M: toggle mode   H: help   SPACE: pause   ESC: quit"
    )

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  SECTION 2c — GRAPHICS SETUP  (clock, fonts)                 ║
    # ╚══════════════════════════════════════════════════════════════╝
    #
    #  Create frame-rate clock and pre-allocate font objects.
    #  Octave/Scilab pre-allocate graphics handles similarly.
    # ───────────────────────────────────────────────────────────────
    clock = pygame.time.Clock()
    font_small = pygame.font.Font(None, 18)
    font_help  = pygame.font.Font(None, 16)

    config = Config()
    grid = SpatialGrid(cell_size=VISUAL_RANGE)

    # ── Open CSV log file ────────────────────────────────────────
    log_fid = None
    if LOG_FILE is not None:
        try:
            log_fid = open(LOG_FILE, "w")
            log_fid.write("frame,mode,num_boids,phi_p,phi_a,phi_n,sigma,theta,theta_ext,alpha,fps\n")
            print(f"Logging metrics to {LOG_FILE} every {LOG_EVERY} frames")
        except OSError as e:
            print(f"WARNING: could not open {LOG_FILE} for writing: {e}")
            log_fid = None

    # ── Initialize flock ──────────────────────────────────────────
    flock = [Boid() for _ in range(config.num_boids)]
    metrics = FlockMetrics()
    frame = 0
    running = True
    paused = False
    pending_reset = False
    pending_add = 0
    pending_remove = 0

    # ═══════════════════════════════════════════════════════════════
    #  MAIN FRAME LOOP
    #  Each iteration processes one simulation frame.
    # ═══════════════════════════════════════════════════════════════
    while running:
        dt = clock.tick(FPS)

        # ╔══════════════════════════════════════════════════════════╗
        # ║  SECTION 11 — INPUT HANDLING  (Pygame events)           ║
        # ╚══════════════════════════════════════════════════════════╝
        #
        #  Python handles input inline via Pygame's event loop
        #  (unlike Octave/Scilab which use figure callback functions).
        #  Keyboard shortcuts mutate Config or set pending flags.
        # ───────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                key = event.key

                # ── Mode toggle  (m) ────────────────────────────
                if key == pygame.K_m:
                    config.mode = 1 - config.mode

                # ── φp  (up/down arrows) ─────────────────────────
                elif key == pygame.K_UP:
                    config.phi_p = min(1.0, config.phi_p + 0.01)
                elif key == pygame.K_DOWN:
                    config.phi_p = max(0.0, config.phi_p - 0.01)

                # ── φa  (left/right arrows) ──────────────────────
                elif key == pygame.K_RIGHT:
                    config.phi_a = min(1.0, config.phi_a + 0.01)
                elif key == pygame.K_LEFT:
                    config.phi_a = max(0.0, config.phi_a - 0.01)

                # ── σ  ([ / ] brackets) ──────────────────────────
                elif key == pygame.K_RIGHTBRACKET:
                    config.sigma = min(50, config.sigma + 1)
                elif key == pygame.K_LEFTBRACKET:
                    config.sigma = max(1,  config.sigma - 1)

                # ── Boid count  (+ / -) — sets pending flags ──
                elif key == pygame.K_EQUALS or key == pygame.K_PLUS:
                    pending_add = min(pending_add + 10, 200)
                    print("Adding 10 birds (pending)")
                elif key == pygame.K_MINUS:
                    pending_remove += 10
                    print("Removing 10 birds (pending)")

                # ── Visual toggles  (g, h) ───────────────────────
                elif key == pygame.K_g:
                    config.show_grid = not config.show_grid
                elif key == pygame.K_h:
                    config.show_help = not config.show_help

                # ── Simulation control  (space, r, esc) ──────────
                elif key == pygame.K_SPACE:
                    paused = not paused
                elif key == pygame.K_r:
                    pending_reset = True
                    print("Resetting flock...")
                elif key == pygame.K_ESCAPE:
                    running = False

        # ───────────────────────────────────────────────────────────
        #  UPDATE  — flocking physics + metrics
        #  Skipped when paused.  Otherwise:
        #    1. Rebuild spatial grid
        #    2. Compute steering forces (flock)
        #    3. Integrate physics (update)
        #    4. Compute metrics
        # ───────────────────────────────────────────────────────────
        if not paused:
            # ╔══════════════════════════════════════════════════════╗
            # ║  SECTION 9a — AUTO-COMPUTE φn                        ║
            # ╚══════════════════════════════════════════════════════╝
            #
            #  φn = max(0, 1 − φp − φa)
            #  Guarantees the three model weights always sum to 1.
            #  In Python, φn is auto-computed via the Config.phi_n
            #  @property — no explicit assignment needed.
            # ───────────────────────────────────────────────────────

            # ╔══════════════════════════════════════════════════════╗
            # ║  SECTION 9c — BOID COUNT CHANGES  (+/- keys)        ║
            # ╚══════════════════════════════════════════════════════╝
            #
            #  Apply pending add/remove requests atomically.
            #  Removal safely leaves at least 1 bird.
            #  Addition capped at 200 pending (set by INPUT handler).
            #
            #  pending_add/pending_remove flags are set by keyboard
            #  handler and applied here (matching Octave/Scilab).
            # ───────────────────────────────────────────────────────
            if pending_remove > 0:
                n_remove = min(pending_remove, len(flock) - 1)
                if n_remove > 0:
                    for _ in range(n_remove):
                        flock.pop()
                    config.num_boids = len(flock)
                    pending_remove -= n_remove
                    print(f"Removed {n_remove} birds, now {config.num_boids}")
            if pending_add > 0:
                n_add = pending_add
                for _ in range(n_add):
                    flock.append(Boid())
                config.num_boids = len(flock)
                pending_add = 0
                print(f"Added {n_add} birds, now {config.num_boids}")

            # ╔══════════════════════════════════════════════════════╗
            # ║  SECTION 9b — RESET LOGIC  (triggered by 'r' key)   ║
            # ╚══════════════════════════════════════════════════════╝
            #
            #  Reinitialise all birds with random positions and
            #  velocities, reset metrics accumulators, rebuild the
            #  spatial grid, and restart the frame counter.
            #
            #  The pending_reset flag is set by the keyboard handler
            #  and applied atomically here (matching Octave/Scilab).
            # ───────────────────────────────────────────────────────
            if pending_reset:
                flock = [Boid() for _ in range(config.num_boids)]
                metrics = FlockMetrics()
                grid = SpatialGrid(cell_size=VISUAL_RANGE)
                frame = 0
                pending_reset = False
                print(f"Flock reset — {config.num_boids} birds")

            # ╔══════════════════════════════════════════════════════╗
            # ║  SECTION 9d — GRID REBUILD  (spatial hash grid)     ║
            # ╚══════════════════════════════════════════════════════╝
            #
            #  Repopulate the toroidal spatial hash grid from the
            #  current bird positions.  O(N) per frame.  Needed for
            #  SPATIAL mode neighbour queries and grid overlay display.
            #  (Octave/Scilab use O(N²) distance matrices instead.)
            # ───────────────────────────────────────────────────────
            if config.mode == MODE_SPATIAL or config.show_grid:
                grid.rebuild(flock)

            # ── Per-bird flocking: compute steering forces ────────
            #  Each bird's flock() method dispatches to the active mode's
            #  logic (projection or spatial) and accumulates steering.
            for boid in flock:
                boid.flock(flock, config, grid)

            # ── Per-bird physics: Euler integration ───────────────
            #  v ← v + a, speed clamp, p ← p + v, toroidal wrap, a ← 0
            for boid in flock:
                boid.update()

            # ── Metrics: Θ, Θ', α, FPS (EMA-smoothed) ─────────────
            metrics.update(flock, clock, config)

            # ── CSV logging  (every LOG_EVERY frames) ─────────────
            if log_fid is not None and frame % LOG_EVERY == 0:
                fps_val = clock.get_fps()   # raw (like Octave/Scilab toc)
                n = len(flock)
                log_fid.write(
                    f"{frame},{config.mode},{n},{config.phi_p:.4f},{config.phi_a:.4f},"
                    f"{config.phi_n:.4f},{config.sigma},{metrics.internal_opacity:.4f},"
                    f"{metrics.external_opacity:.4f},{metrics.order_param:.4f},{fps_val:.1f}\n"
                )
                log_fid.flush()  # ensure data is written even if crash

        # ───────────────────────────────────────────────────────────
        #  RENDER  — draw the frame
        #    1. Clear to dark background
        #    2. Spatial grid overlay (if enabled)
        #    3. Birds (mode-coloured triangles)
        #    4. Metrics text (top-left)
        #    5. Help overlay (top-right, if toggled)
        #    6. Mode badge (top-right)
        #    7. Pause indicator (bottom-centre, if paused)
        # ───────────────────────────────────────────────────────────
        screen.fill((20, 22, 30))

        if config.mode == MODE_SPATIAL and config.show_grid:
            grid.draw(screen, font_help)

        for boid in flock:
            boid.draw(screen, config)

        metrics.draw(screen, font_small, config, len(flock))

        if config.show_help:
            _draw_help(screen, font_help)

        badge_text = "PROJECTION" if config.mode == MODE_PROJECTION else "SPATIAL"
        badge_color = (120, 180, 220) if config.mode == MODE_PROJECTION else (220, 180, 120)
        badge = font_small.render(badge_text, True, badge_color)
        screen.blit(badge, (WIDTH - badge.get_width() - 10, 10))

        if paused:
            ptext = font_small.render(
                "PAUSED  (SPACE to resume, R to reset, ESC to quit)",
                True, (255, 200, 100))
            screen.blit(ptext, (WIDTH // 2 - 220, HEIGHT - 30))

        frame += 1
        pygame.display.flip()

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  SECTION 13 — SHUTDOWN                                      ║
    # ╚══════════════════════════════════════════════════════════════╝
    #
    #  Close CSV log file (if open) and clean up Pygame resources.
    #  Octave/Scilab have an equivalent standalone SECTION 13.
    # ───────────────────────────────────────────────────────────────
    if log_fid is not None:
        log_fid.close()
        print(f"Metrics saved to {LOG_FILE}")
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
