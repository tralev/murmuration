"""
╔══════════════════════════════════════════════════════════════════════╗
║  ITERATION 3 — Spatial Hash Grid (O(1) Neighbour Queries)          ║
╚══════════════════════════════════════════════════════════════════════╝

 Replaces O(N²) pairwise neighbour search with O(1)-per-bird queries
 using a toroidal spatial hash grid.

 What we learn:
   • Grid cells — divide space into VISUAL_RANGE-sized buckets
   • rebuild() — O(N) repopulation each frame
   • get_nearby() — only check adjacent cells, not all N birds
   • Toroidal cell indexing — wrap-around for periodic boundaries
──────────────────────────────────────────────────────────────────────
"""

import math
import random
from collections import defaultdict
import pygame
import sys

# ── Constants ──────────────────────────────────────────────────────
WIDTH, HEIGHT = 1000, 700
NUM_BOIDS = 80
V0 = 4.0
BOID_SIZE = 3
MAX_FORCE = 0.15
VISUAL_RANGE = 70
FPS = 60


class SpatialGrid:
    """Toroidal spatial hash grid — O(1) neighbour queries."""
    def __init__(self, cell_size=VISUAL_RANGE):
        self.cell_size = cell_size
        self.cols = max(1, int(math.ceil(WIDTH / cell_size)))
        self.rows = max(1, int(math.ceil(HEIGHT / cell_size)))
        self.cells = defaultdict(list)

    def rebuild(self, boids):
        """Clear and repopulate in O(N)."""
        self.cells.clear()
        for boid in boids:
            cx = int(boid.position.x // self.cell_size) % self.cols
            cy = int(boid.position.y // self.cell_size) % self.rows
            self.cells[(cx, cy)].append(boid)

    def get_nearby(self, position, radius):
        """Return boids in cells overlapping the search radius."""
        cx0 = int((position.x - radius) // self.cell_size)
        cx1 = int((position.x + radius) // self.cell_size)
        cy0 = int((position.y - radius) // self.cell_size)
        cy1 = int((position.y + radius) // self.cell_size)
        nearby = []
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                wcx = cx % self.cols  # toroidal wrap
                wcy = cy % self.rows
                nearby.extend(self.cells.get((wcx, wcy), ()))
        return nearby


class Boid:
    """A single bird with Reynolds steering rules + spatial grid."""
    def __init__(self):
        self.position = pygame.Vector2(
            random.uniform(0, WIDTH), random.uniform(0, HEIGHT))
        angle = random.uniform(0, 2 * math.pi)
        self.velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * V0
        self.acceleration = pygame.Vector2(0, 0)

    def apply_force(self, force):
        self.acceleration += force

    def update(self):
        """Euler integration + speed clamp + toroidal wrap."""
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

    def flock(self, grid):
        """
        O(K) neighbour search via spatial grid —
        where K = birds in adjacent cells (≪ N).
        """
        candidates = grid.get_nearby(self.position, VISUAL_RANGE)

        separation = pygame.Vector2(0, 0)
        alignment  = pygame.Vector2(0, 0)
        cohesion   = pygame.Vector2(0, 0)
        count = 0

        for other in candidates:
            if other is self:
                continue
            d = self.position.distance_to(other.position)
            if d < VISUAL_RANGE:
                count += 1
                alignment += other.velocity
                cohesion  += other.position
                if d < VISUAL_RANGE * 0.3:
                    diff = self.position - other.position
                    if d > 0.001:
                        diff /= d
                    separation += diff

        if count > 0:
            alignment /= count
            cohesion  /= count
            # Reynolds steering
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

        self.apply_force(separation * 0.3)
        self.apply_force(alignment  * 1.2)
        self.apply_force(cohesion   * 0.05)

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
        pygame.draw.polygon(screen, (230, 200, 160), [tip, back_left, back_right])


# ── Setup ──────────────────────────────────────────────────────────
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Iteration 3 — Spatial Grid")
clock = pygame.time.Clock()
flock = [Boid() for _ in range(NUM_BOIDS)]
grid = SpatialGrid()

# ── Main loop ──────────────────────────────────────────────────────
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            running = False

    # 1. Rebuild grid (O(N))
    grid.rebuild(flock)

    # 2. Compute steering (O(K) per bird)
    for boid in flock:
        boid.flock(grid)

    # 3. Physics
    for boid in flock:
        boid.update()

    # 4. Render
    screen.fill((20, 22, 30))
    for boid in flock:
        boid.draw(screen)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()
