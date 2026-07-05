"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 5 — PROJECTION MODEL  (MODE 0)                             ║
║  SECTION 6 — SPATIAL MODEL     (MODE 1)                             ║
║  SECTION 9 — PHYSICS UPDATE    (shared)                             ║
╚══════════════════════════════════════════════════════════════════════╝

 The Boid class — a single bird agent with both flocking modes.
 Imported by metrics.py (for opacity sampling) and alg2.py (for the
 main simulation loop).

 Dependencies:  occlusion_geom (angular intervals)
                flock_core    (constants, Config, SpatialGrid)
──────────────────────────────────────────────────────────────────────
"""

import math
import random
import pygame

from occlusion_geom import (
    _normalise_interval,
    _interval_covered,
    _merge_interval,
    _merge_all,
)
from flock_core import (
    WIDTH, HEIGHT, V0, BOID_SIZE, MAX_FORCE, VISUAL_RANGE,
    MODE_PROJECTION, MODE_SPATIAL,
    DRAW_TRAIL, TRAIL_LENGTH,
    MARGIN_BOUNDARY, BOUNDARY_MARGIN, BOUNDARY_TURN_FACTOR,
    Config, SpatialGrid,
)


class Boid:
    """
    A single bird agent.  Holds position, velocity, acceleration, and
    a cached internal opacity Θ (computed during the projection step
    and reused by the metrics system).

    Physics (shared by both modes):
      Euler integration with speed clamping to [0.3·V₀, V₀] and
      toroidal position wrap.
    """
    __slots__ = ("position", "velocity", "acceleration", "_last_theta",
                 "_debug_delta", "_debug_merged", "history")

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
        self._debug_delta = pygame.Vector2(0, 0)   # δ̂ for debug view
        self._debug_merged = []          # merged intervals for debug view
        self.history = []                # position trail (ring buffer, last TRAIL_LENGTH)

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

        # ── Boundary handling ───────────────────────────────────
        if MARGIN_BOUNDARY:
            # keepWithinBounds: nudge velocity toward center near edges,
            # then hard-clamp position (matching boids.js behavior).
            if self.position.x < BOUNDARY_MARGIN:
                self.velocity.x += BOUNDARY_TURN_FACTOR
            if self.position.x > WIDTH - BOUNDARY_MARGIN:
                self.velocity.x -= BOUNDARY_TURN_FACTOR
            if self.position.y < BOUNDARY_MARGIN:
                self.velocity.y += BOUNDARY_TURN_FACTOR
            if self.position.y > HEIGHT - BOUNDARY_MARGIN:
                self.velocity.y -= BOUNDARY_TURN_FACTOR
            # Hard clamp position within bounds
            self.position.x = max(0, min(WIDTH, self.position.x))
            self.position.y = max(0, min(HEIGHT, self.position.y))
        else:
            # Toroidal wrap: birds exiting one edge re-enter from the opposite
            if   self.position.x > WIDTH:  self.position.x = 0
            elif self.position.x < 0:      self.position.x = WIDTH
            if   self.position.y > HEIGHT: self.position.y = 0
            elif self.position.y < 0:      self.position.y = HEIGHT

        # ── Trail history ──────────────────────────────────────
        if DRAW_TRAIL:
            self.history.append(pygame.Vector2(self.position))
            if len(self.history) > TRAIL_LENGTH:
                self.history.pop(0)

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
        delta, visible, theta, merged = self._compute_projection_and_visibility(boids)
        self._last_theta = theta
        self._debug_delta = delta
        self._debug_merged = merged

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

        # 🎓 TEACHING MOMENT:  Eq. 3 from Pearce et al. (2014)
        #  v_desired = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
        #  This *replaces* the classic separation + cohesion forces.
        #  The projection term δ̂ alone is enough to keep the flock
        #  together — no explicit attraction/repulsion needed.
        desired = delta * config.phi_p
        if align.length() > 0.001:
            desired += align.normalize() * config.phi_a
        else:
            if self.velocity.length() > 0.001:
                desired += self.velocity.normalize() * config.phi_a
        desired += noise * config.phi_n

        if desired.length() < 0.001:
            desired = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))

        # Normalise to constant speed V₀ for smooth animation
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
        merged  : list[(float, float)] — merged intervals (for debug view)
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
            return pygame.Vector2(0, 0), [], 0.0, []

        # 🎓 WHY CLOSEST-FIRST?  A bird closer to you blocks your
        # view of birds behind it.  If we processed birds in random
        # order, a distant bird might be marked "visible" and then a
        # closer bird (processed later) would incorrectly extend the
        # occluded set over it.  Sorting by distance gives correct
        # occlusion: near birds cast shadows over far birds.
        entries.sort(key=lambda x: x[1])

        # ── Incremental occlusion merge ────────────────────────────
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
        occluded = sum(e - s for s, e in merged)
        theta = min(occluded / (2 * math.pi), 1.0)

        return delta, visible_neighbours, theta, merged

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  SECTION 6 — SPATIAL MODEL  (MODE 1)                        ║
    # ╚══════════════════════════════════════════════════════════════╝
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
        # Clear projection debug state — not meaningful in spatial mode
        self._debug_delta = pygame.Vector2(0, 0)
        self._debug_merged = []

        candidates = grid.get_nearby(self.position, VISUAL_RANGE)

        neighbours = []
        for other in candidates:
            if other is self:
                continue
            d = self.position.distance_to(other.position)
            if d < VISUAL_RANGE:
                neighbours.append((other, d))

        # 🎓 WHY TOPOLOGICAL?  Starling data shows each bird tracks
        # ~6-7 neighbours regardless of how far away they are.  If we
        # used a fixed radius (metric), dense flocks would have hundreds
        # of neighbours and dilute flocks would have none — neither
        # matches reality.  Topological interaction is scale-free.
        neighbours.sort(key=lambda x: x[1])
        neighbours = neighbours[:config.sigma]
        n = len(neighbours)

        separation = pygame.Vector2(0, 0)
        alignment  = pygame.Vector2(0, 0)
        cohesion   = pygame.Vector2(0, 0)

        if n > 0:
            for other, d in neighbours:
                alignment += other.velocity
                cohesion  += other.position

                if d < VISUAL_RANGE * 0.3:
                    diff = self.position - other.position
                    if d > 0.001:
                        diff /= d
                    separation += diff

            alignment /= n
            cohesion  /= n

            if alignment.length() > 0.001:
                alignment.scale_to_length(V0)
            alignment -= self.velocity
            if alignment.length() > MAX_FORCE:
                alignment.scale_to_length(MAX_FORCE)

            cohesion -= self.position
            if cohesion.length() > 0.001:
                cohesion.scale_to_length(V0)
            cohesion -= self.velocity
            if cohesion.length() > MAX_FORCE:
                cohesion.scale_to_length(MAX_FORCE)

            if separation.length() > 0.001:
                separation.scale_to_length(V0)
            separation -= self.velocity
            if separation.length() > MAX_FORCE:
                separation.scale_to_length(MAX_FORCE)

        na = random.uniform(0, 2 * math.pi)
        noise = pygame.Vector2(math.cos(na), math.sin(na)) * MAX_FORCE * 0.8

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

        # ── Trail (position-history polyline, drawn behind the bird) ──
        if DRAW_TRAIL and len(self.history) > 1:
            pts = [(p.x, p.y) for p in self.history]
            pygame.draw.aalines(screen, (85, 140, 244), False, pts, 1)

        if config.mode == MODE_PROJECTION:
            color = (200, 210, 230)
        else:
            color = (230, 200, 160)

        pygame.draw.polygon(screen, color, [tip, back_left, back_right])
