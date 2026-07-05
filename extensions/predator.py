"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 3a — PREDATOR AGENT                                        ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  Goodenough et al. (2017) — predators at ~30% of
 murmurations.  Peregrine falcon or sparrowhawk.

 Predator dynamics:
   r_pred(t+1) = r_pred(t) + v_pred(t)
   v_pred(t+1) = v_pred(t) + a_pred(t)
   a_pred = φ_hunt · r̂_to_nearest_bird  +  φ_random · η̂
   v_pred ≈ 2·v₀ (predator is faster)

 Bird response:
   Birds within a DANGER_RADIUS flee away from the predator with a
   force proportional to 1/d², plus a startle propagation wave
   (neighbour-to-neighbour).

 Builds on OptimizedBoid (Roadmap 3b — full extension chain).

⇔ Octave: alg2_extended.m main loop steps 3+5  ⇔ Scilab: alg2_extended.sce main loop PHASE 3+5

 Usage:  from extensions.predator import Predator, PredatorBoid
──────────────────────────────────────────────────────────────────────
"""

import math
import random
import pygame

from extensions.spatial_optimization import OptimizedBoid
from flock_core import WIDTH, HEIGHT, V0


# ── Predator constants ─────────────────────────────────────────────

PREDATOR_SPEED  = V0 * 2.0          # predator is ~2× faster than birds
PREDATOR_ACCEL  = 0.3               # hunting acceleration
DANGER_RADIUS   = 120               # birds within this radius flee
FLIGHT_FORCE    = 1.5               # strength of flight response
PREDATOR_COLOR  = (255, 80, 60)     # red-orange
PREDATOR_SIZE   = 6                 # larger than birds


class Predator:
    """
    A predator agent (peregrine falcon / sparrowhawk) that pursues
    the nearest bird in the flock.

    Birds within DANGER_RADIUS flee away from the predator with a
    force proportional to 1/d².
    """

    __slots__ = ("position", "velocity", "acceleration")

    def __init__(self):
        # Start from a random edge of the screen
        edge = random.choice(['top', 'bottom', 'left', 'right'])
        if edge == 'top':
            self.position = pygame.Vector2(random.uniform(0, WIDTH), -50)
        elif edge == 'bottom':
            self.position = pygame.Vector2(random.uniform(0, WIDTH), HEIGHT + 50)
        elif edge == 'left':
            self.position = pygame.Vector2(-50, random.uniform(0, HEIGHT))
        else:
            self.position = pygame.Vector2(WIDTH + 50, random.uniform(0, HEIGHT))

        angle = random.uniform(0, 2 * math.pi)
        self.velocity = pygame.Vector2(
            math.cos(angle), math.sin(angle)
        ) * PREDATOR_SPEED * 0.5
        self.acceleration = pygame.Vector2(0, 0)

    def update(self, flock: list):
        """
        Update predator position and velocity.

        1. Find nearest bird
        2. Accelerate toward it (hunting)
        3. Add random noise for realistic movement
        4. Euler integration with toroidal wrap
        """
        if not flock:
            return

        # ── Find nearest bird ──────────────────────────────────────
        nearest_dist = float('inf')
        nearest_pos = None
        for boid in flock:
            d = self.position.distance_to(boid.position)
            if d < nearest_dist:
                nearest_dist = d
                nearest_pos = boid.position

        if nearest_pos is None:
            return

        # ── Hunting acceleration toward nearest bird ───────────────
        to_target = nearest_pos - self.position
        if to_target.length() > 0.001:
            to_target.normalize_ip()
        self.acceleration += to_target * PREDATOR_ACCEL

        # ── Random noise for realistic movement ────────────────────
        na = random.uniform(0, 2 * math.pi)
        noise = pygame.Vector2(math.cos(na), math.sin(na)) * PREDATOR_ACCEL * 0.3
        self.acceleration += noise

        # ── Euler integration ──────────────────────────────────────
        self.velocity += self.acceleration
        speed = self.velocity.length()
        if speed > PREDATOR_SPEED:
            self.velocity.scale_to_length(PREDATOR_SPEED)
        elif speed < PREDATOR_SPEED * 0.3:
            if speed > 0.001:
                self.velocity.scale_to_length(PREDATOR_SPEED * 0.3)

        self.position += self.velocity
        self.acceleration *= 0

        # Toroidal wrap
        if self.position.x > WIDTH:
            self.position.x = 0
        elif self.position.x < 0:
            self.position.x = WIDTH
        if self.position.y > HEIGHT:
            self.position.y = 0
        elif self.position.y < 0:
            self.position.y = HEIGHT

    def draw(self, screen: pygame.Surface):
        """
        Draw predator as a larger, red triangle with a danger-radius
        circle.
        """
        if self.velocity.length_squared() > 0.001:
            direction = math.atan2(self.velocity.y, self.velocity.x)
        else:
            direction = 0

        tip = self.position + pygame.Vector2(
            math.cos(direction), math.sin(direction)
        ) * PREDATOR_SIZE * 3
        back_left = self.position + pygame.Vector2(
            math.cos(direction + 2.3), math.sin(direction + 2.3)
        ) * PREDATOR_SIZE * 2
        back_right = self.position + pygame.Vector2(
            math.cos(direction - 2.3), math.sin(direction - 2.3)
        ) * PREDATOR_SIZE * 2

        pygame.draw.polygon(screen, PREDATOR_COLOR, [tip, back_left, back_right])

        # Optional: danger radius circle (semi-transparent)
        # surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        # pygame.draw.circle(surf, (255, 80, 60, 20),
        #                    (int(self.position.x), int(self.position.y)),
        #                    DANGER_RADIUS, 1)
        # screen.blit(surf, (0, 0))


class PredatorBoid(OptimizedBoid):
    """
    Extension 3a: Bird with predator-avoidance behaviour.

    Extends OptimizedBoid to add a flight response: when a predator
    is within DANGER_RADIUS, the bird steers away from it with a force
    proportional to 1/d².
    """

    def apply_predator_response(self, predator: Predator):
        """
        Apply flight response away from the predator.

        Called after flocking forces are computed, before physics update.
        Uses 1/d² falloff for realistic escape behaviour.
        """
        if predator is None:
            return

        diff = self.position - predator.position
        d = diff.length()
        if d < DANGER_RADIUS and d > 0.001:
            # Flee away from predator — force inversely proportional
            # to distance squared (closer = more urgent flight)
            diff /= d
            flight = diff * FLIGHT_FORCE * ((DANGER_RADIUS - d) / DANGER_RADIUS)
            self.velocity += flight
            # Re-normalise to V0 so flight changes direction not speed
            if self.velocity.length() > 0.001:
                self.velocity.scale_to_length(V0)
