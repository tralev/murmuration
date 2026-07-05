"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 1a — DIRECT VELOCITY SETTING                              ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  Pearce et al. (2014), Eq. (2–3):
   v_i(t+1) = φp·δ̂_i(t) + φa·⟨v̂_j⟩_visible + φn·η̂_i(t)     (Eq. 3)
   r_i(t+1) = r_i(t) + v₀·v̂_i(t+1)                            (Eq. 2)

 The velocity is set *directly* to the desired vector — no Reynolds
 steering, no acceleration accumulation, no MAX_FORCE clamping.
 This matches the paper's instantaneous response model.

 In projection mode, update() skips speed clamping (strict v₀).
 In spatial mode, behaviour falls back to the original Boid.

 Usage:  from extensions.direct_velocity import DirectVelocityBoid
──────────────────────────────────────────────────────────────────────
"""

import math
import random
import pygame

from boid import Boid
from flock_core import WIDTH, HEIGHT, V0, MODE_PROJECTION


class DirectVelocityBoid(Boid):
    """
    Extension 1a: Direct velocity setting in projection mode.

    Overrides _flock_projection() to set velocity directly to the
    desired vector from Eq. 3, bypassing Reynolds steering.

    Overrides update() to skip speed clamping in projection mode
    (the paper uses strict v₀, not a range).
    """

    def flock(self, boids: list, config, grid=None):
        """
        Stash the current mode so update() can check it without
        changing the method signature.
        """
        self._current_mode = config.mode
        super().flock(boids, config, grid)

    def update(self):
        """
        In projection mode: move without speed clamping (strict v₀).
        In spatial mode: fall back to original Euler integration.
        """
        if getattr(self, '_current_mode', None) == MODE_PROJECTION:
            # Direct position update — no speed clamping
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
        else:
            super().update()

    def _flock_projection(self, boids: list, config):
        """
        Hybrid projection model with direct velocity setting.

        Steps 1–4 are identical to the original, computing δ̂, visible
        neighbours, Θ, and the desired direction.

        Step 5 is replaced: velocity is set directly to the desired
        vector (normalised to v₀) instead of applying Reynolds steering.
        """
        # ── Step 1: projection direction & visible neighbours ──────
        delta, visible, theta, merged = self._compute_projection_and_visibility(boids)
        self._last_theta = theta
        self._debug_delta = delta
        self._debug_merged = merged

        # ── Step 2: alignment with σ nearest visible neighbours ────
        align = pygame.Vector2(0, 0)
        if visible:
            nearest = visible[:config.sigma]
            for nb, _ in nearest:
                align += nb.velocity
            align /= len(nearest)

        # ── Step 3: noise — random unit vector η̂ ──────────────────
        na = random.uniform(0, 2 * math.pi)
        noise = pygame.Vector2(math.cos(na), math.sin(na))

        # ── Step 4: desired direction from Eq. 3 ──────────────────
        #  v_desired = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
        desired = delta * config.phi_p
        if align.length() > 0.001:
            desired += align.normalize() * config.phi_a
        else:
            if self.velocity.length() > 0.001:
                desired += self.velocity.normalize() * config.phi_a
        desired += noise * config.phi_n

        if desired.length() < 0.001:
            desired = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))

        # ── Step 5: DIRECT velocity set — NO steering ─────────────
        #  This is the key change from the original:
        #    Original: steer = desired - velocity → apply_force(steer)
        #    New:      velocity = desired            (instantaneous)
        desired.normalize_ip()
        desired *= V0
        self.velocity = desired
