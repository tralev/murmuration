"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 5 — PROJECTION MODEL  (MODE 0)                             ║
║  SECTION 6 — SPATIAL MODEL     (MODE 1)                             ║
║  SECTION 9 — PHYSICS UPDATE    (shared)                             ║
╚══════════════════════════════════════════════════════════════════════╝

 The Boid class — a single bird agent with both flocking modes.
 Imported by metrics.py (for opacity sampling) and alg2.py (for the
 main simulation loop).  Drawing lives in boid_render.py so the agent
 stays free of rendering concerns.

 Feature flags (set BEFORE importing this module):
   ENABLE_PROJECTION_MODE / ENABLE_SPATIAL_MODE — each model's module
   is only imported when its flag is True, so either model can run
   entirely on its own.  At least one must be enabled.

 Dependencies:  occlusion_geom (angular intervals)
                flock_core    (constants, Config, SpatialGrid)
                projection_model / spatial_model (flag-gated)
──────────────────────────────────────────────────────────────────────
"""

import math
import random
import pygame
from collections import deque

import features

from occlusion_geom import (
    _normalise_interval,
    _merge_all,
)

# ── Flag-gated model imports — a disabled model is never loaded ──────
if not (features.ENABLE_PROJECTION_MODE or features.ENABLE_SPATIAL_MODE):
    raise ImportError(
        "Both flocking models are disabled in features.py. "
        "Enable ENABLE_PROJECTION_MODE and/or ENABLE_SPATIAL_MODE "
        "before importing boid."
    )
if features.ENABLE_PROJECTION_MODE:
    import projection_model
if features.ENABLE_SPATIAL_MODE:
    import spatial_model

from flock_core import (
    WIDTH, HEIGHT, V0, BOID_SIZE,
    MODE_PROJECTION, MODE_SPATIAL,
    TRAIL_LENGTH,
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
        self.history = deque(maxlen=TRAIL_LENGTH)

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
        boundary nudge          (margin mode: steer away from walls)
        speed clamped to [0.3·V₀, V₀]
        p ← p + v               (move)
        position clamp / wrap   (keep within bounds)
        a ← 0                   (reset steering accumulator)
        """
        self.velocity += self.acceleration

        # ── Boundary nudge (margin mode — before speed clamp) ───
        #  Nudging before the clamp means speed is re-normalized
        #  afterward, eliminating the one-frame overshoot and
        #  reducing wall-jitter from the speed floor.
        if MARGIN_BOUNDARY:
            # keepWithinBounds: nudge velocity toward center near edges
            if self.position.x < BOUNDARY_MARGIN:
                self.velocity.x += BOUNDARY_TURN_FACTOR
            if self.position.x > WIDTH - BOUNDARY_MARGIN:
                self.velocity.x -= BOUNDARY_TURN_FACTOR
            if self.position.y < BOUNDARY_MARGIN:
                self.velocity.y += BOUNDARY_TURN_FACTOR
            if self.position.y > HEIGHT - BOUNDARY_MARGIN:
                self.velocity.y -= BOUNDARY_TURN_FACTOR

        # ── Speed clamp ────────────────────────────────────────
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

        # ── Position boundary handling ─────────────────────────
        if MARGIN_BOUNDARY:
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
        if features.ENABLE_TRAILS:
            self.history.append(pygame.Vector2(self.position))

    def apply_force(self, force: pygame.Vector2):
        """Accumulate a steering force for the current frame."""
        self.acceleration += force

    # ── Mode dispatch ──────────────────────────────────────────────

    def flock(self, boids: list, config: Config, grid: SpatialGrid = None):
        """
        Dispatch to the active flocking logic based on config.mode.
        This is the per-frame decision rule for each bird.

        If the requested mode's model is disabled in features.py, the
        enabled model is used instead — a single-model build keeps
        running regardless of config.mode.
        """
        use_projection = config.mode == MODE_PROJECTION
        if use_projection and not features.ENABLE_PROJECTION_MODE:
            use_projection = False
        elif not use_projection and not features.ENABLE_SPATIAL_MODE:
            use_projection = True

        if use_projection:
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
        Delegates to projection_model.flock_projection().

        Steps:
          1. Compute δ̂, visible neighbours, and Θ via angular occlusion.
          2. Alignment with σ nearest visible neighbours.
          3. Noise vector.
          4. Desired direction: v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
          5. Reynolds steering toward desired direction.
        """
        projection_model.flock_projection(self, boids, config)

    def _compute_projection_and_visibility(self, boids: list):
        """
        Core of the hybrid projection model — angular-interval occlusion.
        Delegates to projection_model.compute_projection_and_visibility().

        Returns
        -------
        delta   : pygame.Vector2  — unit vector δ̂ to nearest domain boundary
        visible : list[(Boid, float)] — visible neighbours (closest first)
        theta   : float  — internal opacity Θ_i ∈ [0, 1]
        merged  : list[(float, float)] — merged intervals (for debug view)
        """
        return projection_model.compute_projection_and_visibility(self, boids)

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
        Delegates to spatial_model.flock_spatial().

        Steps:
          1. Query spatial grid for candidate neighbours.
          2. Filter by VISUAL_RANGE, sort by distance, take σ nearest.
          3. Compute separation / alignment / cohesion steering forces.
          4. Add noise, apply weighted forces.
        """
        spatial_model.flock_spatial(self, boids, config, grid)

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
        Render this bird — delegates to boid_render.draw_boid().

        The import is local so that the agent module has no static
        dependency on rendering code (agents don't know about pixels);
        this method exists only for backward compatibility.
        """
        import boid_render
        boid_render.draw_boid(screen, self, config)
