"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 2c — 3D EXTENSION WITH SPHERICAL CAP OCCLUSION            ║
╚══════════════════════════════════════════════════════════════════════╝

 Replaces the 2D angular-interval occlusion with full 3D spherical
 cap merging on the unit sphere.  Birds move in (x, y, z) and project
 as circular caps.

 How it works:
   1. Fibonacci sphere points (N=80) discretize the unit sphere.
   2. Per bird, a z-buffer tracks the closest occluder per point.
   3. Birds are processed closest-first; each bird's spherical cap
      is tested against the z-buffer — visible if any point in
      the cap is not yet occluded.
   4. δ̂ = average unit vector of unoccluded Fibonacci points.
   5. Rendering uses perspective projection (farther = smaller, darker).

 Reference:  Pearce et al. (2014) SI Appendix — 3D model where
 light-dark boundaries become curves on the surface of a sphere.

 Usage:  from extensions.three_d import Boid3D, fibonacci_sphere
──────────────────────────────────────────────────────────────────────
"""

import math
import random
import pygame

from boid import Boid
from flock_core import (
    WIDTH, HEIGHT, V0, BOID_SIZE, MAX_FORCE, VISUAL_RANGE,
    MODE_PROJECTION, MODE_SPATIAL, Config,
)


# ── 3D constants ──────────────────────────────────────────────────

DEPTH = 500                    # z-dimension of simulation volume
CAMERA_Z = -800                # camera distance (negative = behind)
FIB_POINTS = 80                # Fibonacci sphere resolution
STERIC_3D_RADIUS = BOID_SIZE * 2
BLIND_3D_ANGLE = math.pi / 3   # 60° blind cone behind bird


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Fibonacci Sphere                                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝

def fibonacci_sphere(n: int = FIB_POINTS) -> list:
    """
    Generate *n* uniformly distributed points on the unit sphere
    using the Fibonacci (golden-angle) spiral.

    Returns list of (x, y, z) unit vectors.

    Golden angle:  π(3 − √5) ≈ 2.400 rad

    Algorithm:
      1. Distribute y-coordinates linearly from +1 (top) to −1 (bottom).
      2. At each y, compute the radius of the latitude circle: r = √(1 − y²).
      3. Advance the azimuthal angle θ by the golden angle φ = π(3 − √5).
      4. Convert spherical (θ, y) → Cartesian (x, y, z).

    The golden angle ensures that successive points are maximally
    separated — no two points ever align.
    """
    points = []

    # ── Edge case: n ≤ 1 — return trivial point set ──────────────
    if n <= 1:
        if n == 1:
            points.append((0, 0, 1))  # single point at north pole
        return points

    # ── Golden angle: π(3 − √5) ≈ 2.400 rad ──────────────────────
    #  This is the angle that produces optimal spherical packing.
    phi = math.pi * (3.0 - math.sqrt(5.0))

    # ── Main loop: generate n points along the Fibonacci spiral ───
    for i in range(n):
        # y-coordinate: linearly spaced from +1 to −1
        #  i=0 → y=+1 (north pole),  i=n-1 → y=−1 (south pole)
        y = 1.0 - (i / float(n - 1)) * 2.0

        # Radius of the latitude circle at height y
        #  At y=±1, radius=0 (pole).  At y=0, radius=1 (equator).
        radius = math.sqrt(1.0 - y * y)

        # Azimuthal angle: advance by golden angle each step
        #  This wraps around the sphere, ensuring even coverage.
        theta = phi * i

        # Cartesian conversion: (r·cos θ, y, r·sin θ)
        x = math.cos(theta) * radius
        z = math.sin(theta) * radius
        points.append((x, y, z))

    return points


# Pre-compute Fibonacci points as Vector3 objects once at module load
_FIB_POINTS = [pygame.Vector3(x, y, z) for x, y, z in fibonacci_sphere(FIB_POINTS)]


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Boid3D                                                              ║
# ╚══════════════════════════════════════════════════════════════════════╝

class Boid3D(Boid):
    """
    3D bird with spherical cap occlusion and perspective rendering.

    Extends the base Boid class, overriding:
      - __init__   — 3D position/velocity (Vector3)
      - _compute_projection_and_visibility — spherical cap z-buffer
      - _flock_projection — 3D sterics + blind cone + direct velocity
      - update     — 3D Euler integration with toroidal wrap
      - draw       — perspective projection (2D screen from 3D coords)
    """

    def __init__(self):
        super().__init__()
        # Override 2D position with 3D
        self.position = pygame.Vector3(
            random.uniform(0, WIDTH),
            random.uniform(0, HEIGHT),
            random.uniform(0, DEPTH),
        )
        angle = random.uniform(0, 2 * math.pi)
        phi = random.uniform(-math.pi / 2, math.pi / 2)
        self.velocity = pygame.Vector3(
            math.cos(angle) * math.cos(phi),
            math.sin(angle) * math.cos(phi),
            math.sin(phi),
        ) * random.uniform(1, V0)
        self.acceleration = pygame.Vector3(0, 0, 0)
        self._last_theta = 0.0
        self._debug_delta = pygame.Vector3(0, 0, 0)
        self._debug_merged = []

    # ═══════════════════════════════════════════════════════════════
    #  Physics — 3D Euler integration with toroidal wrap
    # ═══════════════════════════════════════════════════════════════

    def update(self):
        """
        3D Euler integration with speed clamping and toroidal wrap.

        Physics pipeline (shared with 2D base class, extended to 3D):
          1.  v ← v + a          — apply accumulated steering force
          2.  |v| clamped to [0.3·V₀, V₀]
          3.  p ← p + v          — move forward (3D translation)
          4.  toroidal wrap      — re-enter from opposite face
          5.  a ← 0              — reset steering accumulator

        Toroidal wrap preserves the periodic boundary condition:
        birds exiting one face re-enter from the opposite face.
        In 3D, this creates a torus topology: S¹ × S¹ × S¹.
        """
        # ── Step 1: apply accumulated acceleration ────────────────
        self.velocity += self.acceleration

        # ── Step 2: speed clamping ────────────────────────────────
        #  Cap at V₀ (max cruising speed), floor at 0.3·V₀
        #  (prevent stagnation — a bird with zero speed would be
        #   stuck; the floor ensures it always moves somewhere)
        speed = self.velocity.length()
        if speed > V0:
            self.velocity.scale_to_length(V0)
        elif speed < V0 * 0.3:
            if speed > 0.001:
                self.velocity.scale_to_length(V0 * 0.3)
            else:
                # Velocity is zero — assign a random direction
                #  Uniform sampling on the sphere:
                #    azimuth a ∈ [0, 2π),  elevation p ∈ [−π/2, π/2]
                a = random.uniform(0, 2 * math.pi)
                p = random.uniform(-math.pi / 2, math.pi / 2)
                self.velocity = pygame.Vector3(
                    math.cos(a) * math.cos(p),
                    math.sin(a) * math.cos(p),
                    math.sin(p),
                ) * V0 * 0.3

        # ── Step 3: move forward ──────────────────────────────────
        self.position += self.velocity

        # ── Step 4: reset acceleration ────────────────────────────
        self.acceleration *= 0

        # ── Step 5: toroidal wrap in all 3 dimensions ─────────────
        #  Each dimension wraps independently.  A bird at x > WIDTH
        #  wraps to x = 0 (and vice versa).  Same for y, z.
        if self.position.x > WIDTH:
            self.position.x = 0
        elif self.position.x < 0:
            self.position.x = WIDTH
        if self.position.y > HEIGHT:
            self.position.y = 0
        elif self.position.y < 0:
            self.position.y = HEIGHT
        if self.position.z > DEPTH:
            self.position.z = 0
        elif self.position.z < 0:
            self.position.z = DEPTH

    # ═══════════════════════════════════════════════════════════════
    #  Flocking — 3D projection with sterics + blind cone
    # ═══════════════════════════════════════════════════════════════

    def flock(self, boids: list, config: Config, grid=None):
        """Dispatch to projection mode (3D-only for now)."""
        if config.mode == MODE_PROJECTION:
            self._flock_projection_3d(boids, config)

    def _flock_projection_3d(self, boids: list, config: Config):
        """
        3D projection model with:
          - Spherical cap occlusion (δ̂, visible neighbours, Θ)
          - 3D steric repulsion (1/r²)
          - Blind cone filtering (behind bird)
          - Direct velocity setting (no Reynolds steering)
        """
        delta, visible, theta = self._compute_projection_and_visibility_3d(boids)
        self._last_theta = theta

        # ── Alignment with σ nearest visible neighbours ────────────
        align = pygame.Vector3(0, 0, 0)
        if visible:
            nearest = visible[:config.sigma]
            for nb, _ in nearest:
                align += nb.velocity
            align /= len(nearest)

        # ── Noise ──────────────────────────────────────────────────
        na = random.uniform(0, 2 * math.pi)
        np = random.uniform(-math.pi / 2, math.pi / 2)
        noise = pygame.Vector3(
            math.cos(na) * math.cos(np),
            math.sin(na) * math.cos(np),
            math.sin(np),
        )

        # ── Desired direction: v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂ ────────
        desired = delta * config.phi_p if delta.length() > 0 else pygame.Vector3(0, 0, 0)
        if align.length() > 0.001:
            desired += align.normalize() * config.phi_a
        elif self.velocity.length() > 0.001:
            desired += self.velocity.normalize() * config.phi_a
        desired += noise * config.phi_n

        if desired.length() < 0.001:
            desired = pygame.Vector3(
                random.uniform(-1, 1),
                random.uniform(-1, 1),
                random.uniform(-1, 1),
            )

        desired.normalize_ip()
        desired *= V0

        # ── Direct velocity setting (Priority 1a) — no steering ────
        self.velocity = desired
        self.acceleration = pygame.Vector3(0, 0, 0)

    # ═══════════════════════════════════════════════════════════════
    #  Spherical Cap Occlusion
    # ═══════════════════════════════════════════════════════════════

    def _compute_projection_and_visibility_3d(self, boids: list):
        """
        3D spherical cap occlusion using Fibonacci sphere z-buffering.

        ── THEORY ──

        In 2D, each bird subtends a 1D angular interval on a circle.
        In 3D, each bird subtends a 2D circular cap on the unit sphere.

        For bird j at distance d with body radius b:
          Direction    = unit vector from self to j
          Angular radius α = asin(b / d)       (Eq. SI-3 from Pearce)
          Solid angle  Ω = 2π(1 − cos α)       (steradians)

        The cap is the set of all unit vectors v̂ such that:
          v̂ · direction ≥ cos α

        ── Z-BUFFER ALGORITHM ──

        1. Pre-compute N Fibonacci points uniformly on the unit sphere.
        2. Per bird, maintain a z-buffer: zbuf[i] = distance to
           closest occluder at Fibonacci point i.  -1.0 = unoccluded.
        3. Sort all birds by distance from viewer (closest first).
        4. For each bird (closest to farthest):
           a. Check if ANY Fibonacci point in its cap is unoccluded.
           b. If yes → bird is visible.  Mark ALL cap points as
              occluded at distance d (so farther birds behind it
              are hidden).
           c. If no  → bird is fully occluded by closer birds.
        5. δ̂ = average of all unoccluded Fibonacci point vectors
           (excluding those in the blind cone behind the bird).
        6. Θ = (# occluded points) / N  (internal opacity).

        ── COMPLEXITY ──

        O(N_birds · N_fib) per bird, where N_fib = 80.  For 150 birds:
        ~150 × 150 × 80 = 1.8M dot-product operations per frame.
        Acceptable for scientific visualisation; can be accelerated
        with spatial hashing (see Priority 3b).

        ── RETURNS ──

        delta   : Vector3 — unit vector δ̂ to nearest domain boundary
        visible : list[(Boid3D, float)] — visible neighbours (closest first)
        theta   : float — internal opacity Θ ∈ [0, 1]
        """

        n_fib = len(_FIB_POINTS)

        # ═══════════════════════════════════════════════════════════
        #  PHASE 1: Build angular entries for all other birds
        # ═══════════════════════════════════════════════════════════
        #
        #  For each other bird j:
        #    direction   = (rⱼ − rᵢ) / |rⱼ − rᵢ|   (unit vector)
        #    α           = asin(b / dⱼ)             (angular radius)
        #    cap          = {v̂ : v̂·direction ≥ cos α}
        # ───────────────────────────────────────────────────────────

        entries = []  # (boid, distance, direction, angular_radius)
        for other in boids:
            if other is self:
                continue

            # 3D displacement vector and Euclidean distance
            diff = other.position - self.position
            dist = diff.length()
            if dist < 0.001:
                continue  # degenerate: co-located birds

            direction = diff.normalize()

            # Angular half-width: asin(b / d)
            #  Clamped to [0, π/2] via min(..., 1.0) — birds can't
            #  subtend more than a hemisphere (b ≤ d).
            angular_radius = math.asin(min(BOID_SIZE / dist, 1.0))

            entries.append((other, dist, direction, angular_radius))

        # No other birds → empty view (Θ = 0, δ̂ = 0)
        if not entries:
            return pygame.Vector3(0, 0, 0), [], 0.0

        # ═══════════════════════════════════════════════════════════
        #  PHASE 2: Sort closest-first
        # ═══════════════════════════════════════════════════════════
        #
        #  WHY CLOSEST-FIRST?  A bird closer to you blocks your view
        #  of birds behind it.  If we processed birds in random order,
        #  a distant bird might be marked "visible" and then a closer
        #  bird (processed later) would incorrectly extend the
        #  occluded region over it.
        # ───────────────────────────────────────────────────────────

        entries.sort(key=lambda x: x[1])

        # ═══════════════════════════════════════════════════════════
        #  PHASE 3: Initialise z-buffer
        # ═══════════════════════════════════════════════════════════
        #
        #  zbuf[i] = distance to the closest bird that occludes
        #            Fibonacci point i.
        #  -1.0 means: no bird has yet been found to occlude
        #  this direction (sky is visible at this point).
        # ───────────────────────────────────────────────────────────

        zbuf = [-1.0] * n_fib

        # ═══════════════════════════════════════════════════════════
        #  PHASE 4: Compute the bird's heading (for blind cone)
        # ═══════════════════════════════════════════════════════════
        #
        #  The blind cone extends behind the bird — the opposite
        #  direction of its velocity.  Birds whose direction falls
        #  within BLIND_3D_ANGLE / 2 of the backward direction are
        #  invisible to this bird.
        #
        #  heading = normalised velocity (or (1,0,0) if stationary)
        #  blind_cone = cone centred on -heading, half-angle = β/2
        # ───────────────────────────────────────────────────────────

        if self.velocity.length_squared() > 0.001:
            heading = self.velocity.normalize()
        else:
            heading = pygame.Vector3(1, 0, 0)  # default forward

        visible_neighbours = []

        # ═══════════════════════════════════════════════════════════
        #  PHASE 5: Process entries (closest-first z-buffer loop)
        # ═══════════════════════════════════════════════════════════
        #
        #  For each bird (processed in order of increasing distance):
        #    A.  BLIND CONE CHECK:  If the bird's direction is
        #        within the blind cone, skip it entirely — invisible.
        #    B.  VISIBILITY CHECK:  Scan all Fibonacci points.
        #        If ANY point in the bird's cap is unoccluded
        #        (zbuf[i] < 0), the bird is visible.
        #    C.  Z-BUFFER UPDATE:  If visible, mark ALL Fibonacci
        #        points in the bird's cap as occluded at distance d.
        #        This ensures farther birds behind it are hidden.
        # ───────────────────────────────────────────────────────────

        for other, dist, direction, angular_radius in entries:

            # ── A. Blind cone filter ─────────────────────────────
            #  heading_neg = -heading = direction BEHIND the bird.
            #  If the other bird's direction lies within β/2 of
            #  heading_neg, it's in the blind cone → skip.
            #
            #  Dot-product test:
            #    direction · heading_neg > cos(β/2)
            #    → angle between direction and backward < β/2
            #    → bird is in the blind cone
            heading_neg = -heading
            if direction.dot(heading_neg) > math.cos(BLIND_3D_ANGLE / 2):
                continue  # bird is in blind cone — invisible

            # ── B. Visibility check ──────────────────────────────
            #  A bird is visible iff at least one Fibonacci point
            #  in its spherical cap is NOT yet occluded.
            #
            #  Cap membership test:
            #    fib_point · direction ≥ cos α
            #    → fib_point is within angular radius α of direction
            #
            #  We break early (any_visible = True) as soon as we
            #  find one unoccluded point — no need to check all.

            any_visible = False
            cos_radius = math.cos(angular_radius)

            for i, fib in enumerate(_FIB_POINTS):
                # Is this Fibonacci point inside the bird's cap?
                if fib.dot(direction) >= cos_radius:
                    # Is this point NOT yet occluded by a closer bird?
                    if zbuf[i] < 0:
                        any_visible = True
                        break  # one unoccluded point is enough

            # ── C. Z-buffer update ───────────────────────────────
            #  The bird is visible — add to the visible list.
            #  Then mark ALL Fibonacci points in its cap as occluded
            #  at distance d.  This is the "occlusion shadow" cast
            #  by this bird onto the sky.

            if any_visible:
                visible_neighbours.append((other, dist))

                for i, fib in enumerate(_FIB_POINTS):
                    if fib.dot(direction) >= cos_radius:
                        # Only mark this point if:
                        #  - it was unoccluded (zbuf[i] < 0), OR
                        #  - it was occluded by a FARTHER bird
                        #    (zbuf[i] > dist — shouldn't happen
                        #     with closest-first ordering, but
                        #     included for robustness)
                        if zbuf[i] < 0 or zbuf[i] > dist:
                            zbuf[i] = dist

        # ═══════════════════════════════════════════════════════════
        #  PHASE 6: Compute δ̂ — projection direction
        # ═══════════════════════════════════════════════════════════
        #
        #  δ̂ is the average of all UNOCCLUDED Fibonacci point
        #  vectors.  Each unoccluded point represents a "gap" in the
        #  bird's view where sky is visible.  The average of these
        #  gaps gives a vector pointing toward the nearest visible
        #  boundary — the direction the bird should turn to find
        #  open sky (or to stay with the flock).
        #
        #  The blind cone filter is also applied here: Fibonacci
        #  points in the blind region (behind the bird) are excluded
        #  from δ̂ computation, even if they are unoccluded.  A bird
        #  cannot see gaps behind its head.
        # ───────────────────────────────────────────────────────────

        delta = pygame.Vector3(0, 0, 0)
        unoccluded_count = 0

        for i, fib in enumerate(_FIB_POINTS):
            if zbuf[i] < 0:  # this direction is NOT occluded
                # Blind cone exclusion:
                #  fib · heading > −cos(β/2)
                #  → fib is NOT in the blind cone behind the bird
                if fib.dot(heading) > -math.cos(BLIND_3D_ANGLE / 2):
                    delta += fib
                    unoccluded_count += 1

        # Normalise: δ̂ = Σ(unoccluded_fib) / |Σ(unoccluded_fib)|
        if unoccluded_count > 0:
            delta /= unoccluded_count

        if delta.length() > 0:
            delta.normalize_ip()

        # ═══════════════════════════════════════════════════════════
        #  PHASE 7: Compute internal opacity Θ_i
        # ═══════════════════════════════════════════════════════════
        #
        #  Θ = (number of occluded Fibonacci points) / N
        #
        #  Each Fibonacci point represents a small patch of the
        #  sky.  Θ measures what fraction of the sky is blocked by
        #  other birds.  Θ = 0 → clear sky; Θ = 1 → fully surrounded.
        # ───────────────────────────────────────────────────────────

        occluded_count = sum(1 for z in zbuf if z > 0)
        theta = occluded_count / n_fib

        return delta, visible_neighbours, theta

    # ═══════════════════════════════════════════════════════════════
    #  Drawing — perspective projection
    # ═══════════════════════════════════════════════════════════════

    def draw(self, screen: pygame.Surface, config: Config):
        """
        Render with perspective projection.
        Birds farther from camera appear smaller and darker.
        """
        # Perspective projection
        z_offset = self.position.z - CAMERA_Z
        if z_offset < 10:
            z_offset = 10  # prevent division by zero
        scale = 400.0 / z_offset

        proj_x = int(WIDTH / 2 + (self.position.x - WIDTH / 2) * scale)
        proj_y = int(HEIGHT / 2 + (self.position.y - HEIGHT / 2) * scale)
        bird_size = max(1.0, BOID_SIZE * 2.5 * scale)

        # Direction in screen space (approximate from velocity)
        if self.velocity.length_squared() > 0.001:
            v = self.velocity.normalize()
            screen_dir = math.atan2(v.y, v.x)
        else:
            screen_dir = 0

        # Color: closer = brighter, farther = darker
        depth_factor = min(1.0, max(0.2, scale * 2.5))
        r = int(200 * depth_factor)
        g = int(210 * depth_factor)
        b = int(230 * depth_factor)
        color = (r, g, b)

        # Draw triangle
        tip = (
            proj_x + math.cos(screen_dir) * bird_size,
            proj_y + math.sin(screen_dir) * bird_size,
        )
        back_left = (
            proj_x + math.cos(screen_dir + 2.3) * bird_size * 0.6,
            proj_y + math.sin(screen_dir + 2.3) * bird_size * 0.6,
        )
        back_right = (
            proj_x + math.cos(screen_dir - 2.3) * bird_size * 0.6,
            proj_y + math.sin(screen_dir - 2.3) * bird_size * 0.6,
        )

        pygame.draw.polygon(screen, color, [tip, back_left, back_right])

    # ── Stubs for 2D spatial mode (not used in 3D) ─────────────────

    def _flock_spatial(self, boids, config, grid):
        """3D simulation uses projection mode. Fall back to parent silently."""
        self._flock_projection_3d(boids, config)

    def compute_internal_opacity(self, boids: list) -> float:
        return self._last_theta
