"""
alg_simple.py — Minimal flocking simulation for students.

Read this FIRST before diving into the full module structure
(occlusion_geom, flock_core, boid, metrics, alg2).

This is the simplest possible boids simulation:
  - 3 rules: separation, alignment, cohesion
  - No occlusion, no metrics, no CSV, no presets
  - ~70 lines — one file, one class, one loop

Run:  pip install pygame && python alg_simple.py
"""

import pygame
import random
import math

W, H = 1000, 700
N  = 100          # number of birds
V0 = 4            # speed
R  = 70           # neighbour radius
F  = 0.15         # max steering force


class Boid:
    def __init__(self):
        self.pos = pygame.Vector2(random.uniform(0, W), random.uniform(0, H))
        a = random.uniform(0, 2 * math.pi)
        self.vel = pygame.Vector2(math.cos(a), math.sin(a)) * random.uniform(1, V0)
        self.acc = pygame.Vector2(0, 0)

    def update(self):
        self.vel += self.acc
        s = self.vel.length()
        if s > V0:      self.vel.scale_to_length(V0)
        elif s < V0 * 0.3:
            self.vel.scale_to_length(V0 * 0.3) if s > 0.001 else self.vel.from_polar(
                (V0 * 0.3, random.uniform(0, 360)))
        self.pos += self.vel
        self.acc *= 0
        self.pos.x %= W; self.pos.y %= H   # toroidal wrap

    def flock(self, boids):
        sep = align = coh = pygame.Vector2(0, 0)
        neighbours = []
        for other in boids:
            if other is self: continue
            d = self.pos.distance_to(other.pos)
            if d < R: neighbours.append((other, d))
        neighbours.sort(key=lambda x: x[1])
        n = len(neighbours)
        if n == 0: return
        for other, d in neighbours:
            align += other.vel
            coh   += other.pos
            if d < R * 0.3 and d > 0.001:
                sep += (self.pos - other.pos) / d
        align /= n; coh /= n
        for v in (sep, align, coh):
            if v.length() > 0.001:
                v.scale_to_length(V0); v -= self.vel
                if v.length() > F: v.scale_to_length(F)
        self.acc += sep * 1.5 + align * 1.0 + coh * 0.8
        # Small noise for exploration — prevents the flock from becoming rigid
        self.acc += pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1)) * F * 0.5

    def draw(self, screen):
        a = math.atan2(self.vel.y, self.vel.x) if self.vel.length_squared() > 0.001 else 0
        r = 4
        tip = self.pos + pygame.Vector2(math.cos(a), math.sin(a)) * r * 2.5
        bl  = self.pos + pygame.Vector2(math.cos(a + 2.3), math.sin(a + 2.3)) * r * 1.5
        br  = self.pos + pygame.Vector2(math.cos(a - 2.3), math.sin(a - 2.3)) * r * 1.5
        pygame.draw.polygon(screen, (200, 210, 230), [tip, bl, br])


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Simple Boids — ESC to quit")
    clock = pygame.time.Clock()
    flock = [Boid() for _ in range(N)]
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit(); return
        clock.tick(60)
        for b in flock: b.flock(flock)
        for b in flock: b.update()
        screen.fill((20, 22, 30))
        for b in flock: b.draw(screen)
        pygame.display.flip()


if __name__ == "__main__":
    main()
