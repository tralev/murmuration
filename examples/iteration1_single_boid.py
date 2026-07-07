"""
╔══════════════════════════════════════════════════════════════════════╗
║  ITERATION 1 — Single Boid                                          ║
╚══════════════════════════════════════════════════════════════════════╝

 A single bird moving across the screen with toroidal boundary wrap.
 This is the minimum viable simulation: one agent, simple physics.

 What we learn:
   • Euler integration    — v += a, p += v
   • Speed clamping        — prevent the bird from going too fast or slow
   • Toroidal wrap         — re-enter from opposite edge
   • Pygame basics         — window, clock, draw loop, event handling
──────────────────────────────────────────────────────────────────────
"""

import math
import random
import pygame
import sys

# ── Constants ──────────────────────────────────────────────────────
WIDTH, HEIGHT = 1000, 700
V0 = 4.0           # cruising speed
BOID_SIZE = 3
FPS = 60

# ── Setup ──────────────────────────────────────────────────────────
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Iteration 1 — Single Boid")
clock = pygame.time.Clock()

# ── Boid state ─────────────────────────────────────────────────────
position = pygame.Vector2(WIDTH / 2, HEIGHT / 2)
velocity = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
velocity.scale_to_length(V0)

# ── Main loop ──────────────────────────────────────────────────────
running = True
while running:
    # 1. Handle input
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            running = False

    # 2. Update physics (Euler integration)
    #    No steering forces yet — the bird just coasts at V0
    position += velocity

    # Toroidal wrap: re-enter from opposite edge
    if position.x > WIDTH:
        position.x = 0
    elif position.x < 0:
        position.x = WIDTH
    if position.y > HEIGHT:
        position.y = 0
    elif position.y < 0:
        position.y = HEIGHT

    # 3. Render
    screen.fill((20, 22, 30))

    # Draw the boid as a small triangle pointing in its heading direction
    direction = math.atan2(velocity.y, velocity.x)
    tip = position + pygame.Vector2(
        math.cos(direction), math.sin(direction)) * BOID_SIZE * 2.5
    back_left = position + pygame.Vector2(
        math.cos(direction + 2.3), math.sin(direction + 2.3)) * BOID_SIZE * 1.5
    back_right = position + pygame.Vector2(
        math.cos(direction - 2.3), math.sin(direction - 2.3)) * BOID_SIZE * 1.5
    pygame.draw.polygon(screen, (200, 210, 230), [tip, back_left, back_right])

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()
