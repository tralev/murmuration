"""
╔══════════════════════════════════════════════════════════════════════╗
║  ITERATION 5 — Projection Model (Pearce et al. 2014)               ║
╚══════════════════════════════════════════════════════════════════════╝

 Replaces classic Reynolds rules with the hybrid projection model from
 Pearce, Miller, Rowlands & Turner (2014) PNAS 111(29), 10422–10426.

 What we learn:
   • Angular occlusion — each bird sees others as silhouette intervals
   • Closest-first processing — near birds occlude far birds
   • δ̂ (delta) vector — points toward domain boundaries (→ flock cohesion)
   • Θ (theta) — internal opacity = fraction of view occluded
   • Visibility-aware alignment — only σ nearest VISIBLE neighbours

 Key equation (Eq. 3):
   v_i(t+1) = φp·δ̂_i(t) + φa·⟨v̂_j⟩_visible + φn·η̂_i(t)

 This file includes the occlusion geometry from Iteration 4 inline.
──────────────────────────────────────────────────────────────────────
"""

import math
import random
import pygame
import sys

# ── Constants ──────────────────────────────────────────────────────
WIDTH, HEIGHT = 1000, 700
NUM_BOIDS = 80
V0 = 4.0
BOID_SIZE = 3
MAX_FORCE = 0.15
FPS = 60

# Projection model weights (φp + φa + φn = 1)
PHI_P = 0.03    # projection weight
PHI_A = 0.80    # alignment weight
PHI_N = 0.17    # noise weight (auto: 1 − φp − φa)
SIGMA = 4       # topological neighbour count

_EPS = 1e-7


# ══════════════════════════════════════════════════════════════════════
#  OCCLUSION GEOMETRY (from Iteration 4)
# ══════════════════════════════════════════════════════════════════════

def _normalise_interval(start, end):
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


def _interval_covered(start, end, merged):
    cursor = start
    for ms, me in merged:
        if ms - _EPS <= cursor:
            cursor = max(cursor, me)
        if cursor >= end - _EPS:
            return True
        if ms > cursor + _EPS:
            break
    return cursor >= end - _EPS


def _merge_interval(start, end, merged):
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
    if idx > 0 and merged[idx - 1][1] >= merged[idx][0] - _EPS:
        merged[idx - 1][1] = max(merged[idx - 1][1], merged[idx][1])
        merged.pop(idx)
        idx -= 1
    while idx < len(merged) - 1 and merged[idx][1] >= merged[idx + 1][0] - _EPS:
        merged[idx][1] = max(merged[idx][1], merged[idx + 1][1])
        merged.pop(idx + 1)


# ══════════════════════════════════════════════════════════════════════
#  PROJECTION MODEL
# ══════════════════════════════════════════════════════════════════════

def compute_projection(boid, boids):
    """
    Angular-interval occlusion — the core of the projection model.

    For each other bird j, compute the angular interval it subtends:
      centre = atan2(y_j − y_i, x_j − x_i)
      half   = arcsin(b / d)
      interval = [centre − half, centre + half]

    Process closest-first: near birds block far birds.
    Returns (delta, visible_neighbours, theta, merged_intervals).
    """
    # Build angular intervals
    entries = []
    for other in boids:
        if other is boid:
            continue
        diff = other.position - boid.position
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

    # 🎓 WHY CLOSEST-FIRST? Closer birds block view of farther ones.
    # Sorting by distance gives correct partial occlusion.
    entries.sort(key=lambda x: x[1])

    merged = []
    visible = []

    for other, dist, centre, half in entries:
        start = centre - half
        end = centre + half
        segments = _normalise_interval(start, end)

        is_visible = any(not _interval_covered(s, e, merged) for s, e in segments)
        if is_visible:
            visible.append((other, dist))
            for s, e in segments:
                _merge_interval(s, e, merged)

    # δ̂ — sum of unit vectors to all domain boundaries
    delta = pygame.Vector2(0, 0)
    for s, e in merged:
        delta += pygame.Vector2(math.cos(s), math.sin(s))
        delta += pygame.Vector2(math.cos(e), math.sin(e))

    # Fully surrounded → no projection information
    if (len(merged) == 1 and merged[0][0] < 1e-9
            and merged[0][1] > 2 * math.pi - 1e-9):
        delta = pygame.Vector2(0, 0)

    if delta.length() > 0:
        delta.normalize_ip()

    # Θ = total occluded angle / 2π
    occluded = sum(e - s for s, e in merged)
    theta = min(occluded / (2 * math.pi), 1.0)

    return delta, visible, theta, merged


class Boid:
    def __init__(self):
        self.position = pygame.Vector2(
            random.uniform(0, WIDTH), random.uniform(0, HEIGHT))
        angle = random.uniform(0, 2 * math.pi)
        self.velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * V0
        self.acceleration = pygame.Vector2(0, 0)
        # Projection debug state
        self._last_theta = 0.0
        self._debug_delta = pygame.Vector2(0, 0)
        self._debug_merged = []

    def apply_force(self, force):
        self.acceleration += force

    def update(self):
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
        if self.position.x > WIDTH:   self.position.x = 0
        elif self.position.x < 0:    self.position.x = WIDTH
        if self.position.y > HEIGHT:  self.position.y = 0
        elif self.position.y < 0:    self.position.y = HEIGHT

    def flock(self, boids):
        """
        Eq. 3 from Pearce et al. (2014):
          v_desired = φp·δ̂ + φa·⟨v̂⟩_visible + φn·η̂

        1. Compute δ̂ and visible neighbours via angular occlusion.
        2. Alignment with σ nearest visible neighbours.
        3. Noise vector.
        4. Reynolds steering toward desired direction.
        """
        # Step 1: compute projection
        delta, visible, theta, merged = compute_projection(self, boids)
        self._last_theta = theta
        self._debug_delta = delta
        self._debug_merged = merged

        # Step 2: alignment with σ nearest visible neighbours
        align = pygame.Vector2(0, 0)
        if visible:
            nearest = visible[:SIGMA]
            for nb, _ in nearest:
                align += nb.velocity
            align /= len(nearest)

        # Step 3: noise
        na = random.uniform(0, 2 * math.pi)
        noise = pygame.Vector2(math.cos(na), math.sin(na))

        # Step 4: v_desired = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
        desired = delta * PHI_P
        if align.length() > 0.001:
            desired += align.normalize() * PHI_A
        elif self.velocity.length() > 0.001:
            desired += self.velocity.normalize() * PHI_A
        desired += noise * PHI_N

        if desired.length() < 0.001:
            desired = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
        desired.normalize_ip()
        desired *= V0

        # Step 5: Reynolds steering
        steer = desired - self.velocity
        if steer.length() > MAX_FORCE:
            steer.scale_to_length(MAX_FORCE)
        self.apply_force(steer)

    def draw(self, screen):
        if self.velocity.length_squared() > 0.001:
            direction = math.atan2(self.velocity.y, self.velocity.x)
        else:
            direction = 0
        tip = self.position + pygame.Vector2(
            math.cos(direction), math.sin(direction)) * BOID_SIZE * 2.5
        back_left = self.position + pygame.Vector2(
            math.cos(direction + 2.3), math.sin(direction + 2.3)) * BOID_SIZE * 1.5
        back_right = self.position + pygame.Vector2(
            math.cos(direction - 2.3), math.sin(direction - 2.3)) * BOID_SIZE * 1.5
        pygame.draw.polygon(screen, (200, 210, 230), [tip, back_left, back_right])


# ── Setup ──────────────────────────────────────────────────────────
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Iteration 5 — Projection Model (Pearce 2014)")
clock = pygame.time.Clock()
flock = [Boid() for _ in range(NUM_BOIDS)]

# ── Main loop ──────────────────────────────────────────────────────
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            running = False

    for boid in flock:
        boid.flock(flock)
    for boid in flock:
        boid.update()

    screen.fill((20, 22, 30))
    for boid in flock:
        boid.draw(screen)
    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()
