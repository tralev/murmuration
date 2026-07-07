"""
╔══════════════════════════════════════════════════════════════════════╗
║  ITERATION 2 — Classic Reynolds Boids (O(N²))                      ║
╚══════════════════════════════════════════════════════════════════════╝

 Multiple birds with three classic steering forces:
   • Separation  — steer away from neighbours that are too close
   • Alignment   — steer toward the average heading of neighbours
   • Cohesion    — steer toward the average position of neighbours

 What we learn:
   • Boid class with position, velocity, acceleration
   • apply_force() — accumulate steering forces
   • O(N²) pairwise neighbour search every frame
   • Reynolds steering — desired velocity minus current, clamped
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
VISUAL_RANGE = 70
FPS = 60


class Boid:
    """A single bird with Reynolds steering rules."""
    def __init__(self):
        self.position = pygame.Vector2(
            random.uniform(0, WIDTH), random.uniform(0, HEIGHT))
        angle = random.uniform(0, 2 * math.pi)
        self.velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * V0
        self.acceleration = pygame.Vector2(0, 0)

    def apply_force(self, force):
        self.acceleration += force

    def update(self):
        """Euler integration: v += a, clamp speed, p += v, toroidal wrap."""
        self.velocity += self.acceleration

        # Speed clamp to [0.3·V0, V0]
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
        self.acceleration *= 0  # reset for next frame

        # Toroidal wrap
        if self.position.x > WIDTH:   self.position.x = 0
        elif self.position.x < 0:    self.position.x = WIDTH
        if self.position.y > HEIGHT:  self.position.y = 0
        elif self.position.y < 0:    self.position.y = HEIGHT

    def flock(self, boids):
        """
        O(N²) neighbour search: check every other bird, compute
        separation / alignment / cohesion steering forces.
        """
        separation = pygame.Vector2(0, 0)
        alignment  = pygame.Vector2(0, 0)
        cohesion   = pygame.Vector2(0, 0)
        count = 0

        for other in boids:
            if other is self:
                continue
            d = self.position.distance_to(other.position)
            if d < VISUAL_RANGE:
                count += 1
                alignment += other.velocity
                cohesion  += other.position

                if d < VISUAL_RANGE * 0.3:  # too close → push away
                    diff = self.position - other.position
                    if d > 0.001:
                        diff /= d  # 1/r falloff
                    separation += diff

        if count > 0:
            alignment /= count
            cohesion  /= count

            # Reynolds steering: desired minus current, clamped
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

        # Weights: more alignment, less separation/cohesion
        self.apply_force(separation * 0.3)
        self.apply_force(alignment  * 1.2)
        self.apply_force(cohesion   * 0.05)

    def draw(self, screen):
        """Render as a triangle pointing in the heading direction."""
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
pygame.display.set_caption("Iteration 2 — Classic Reynolds Boids")
clock = pygame.time.Clock()

flock = [Boid() for _ in range(NUM_BOIDS)]

# ── Main loop ──────────────────────────────────────────────────────
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            running = False

    # 1. Compute steering forces (O(N²) neighbour search)
    for boid in flock:
        boid.flock(flock)

    # 2. Apply physics
    for boid in flock:
        boid.update()

    # 3. Render
    screen.fill((20, 22, 30))
    for boid in flock:
        boid.draw(screen)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()
