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

        ── COMPARISON WITH ORIGINAL ──

        Original (boid.py):
          1. Compute δ̂, visible, Θ via angular occlusion
          2. Alignment with σ nearest visible neighbours
          3. Noise vector
          4. Desired = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
          5. steer = desired − velocity  →  apply_force(steer)   ← REYNOLDS

        This override (matching Pearce Eq. 2–3):
          1–4. Same as original
          5. velocity = desired  (normalised to v₀)    ← DIRECT SET

        The Reynolds steering adds artificial inertia — the bird
        doesn't instantly change direction.  Direct velocity setting
        matches the paper's assumption of instantaneous response.

        ── STEP-BY-STEP ──

        Step 1: δ̂ — projection direction from domain boundaries.
                δ̂ points toward the nearest gap in the occluded
                visual field, acting as an implicit attraction
                toward the edge of the flock.

        Step 2: ⟨v̂⟩ — average heading of σ nearest visible neighbours.
                Visible means: not occluded by closer birds AND
                not in the blind sector (if roadmaps 2b–2d active).

        Step 3: η̂ — isotropic unit noise.  Provides stochastic
                exploration; prevents the flock from locking into
                a perfectly aligned (and brittle) state.

        Step 4: v_desired = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂  (Pearce Eq. 3).
                φp + φa + φn = 1.  Default: φp=0.03, φa=0.80.

        Step 5: DIRECT velocity assignment — the key change.
        """

        # ── Step 1: projection direction & visible neighbours ──────
        #  O(N²) occlusion computation (O(N_near+C) with Priority 3b).  Returns:
        #    delta   : unit vector δ̂ to nearest domain boundary
        #    visible : list of (boid, distance) sorted closest-first
        #    theta   : internal opacity Θ ∈ [0, 1]
        #    merged  : merged occluded intervals (for debug view)
        delta, visible, theta, merged = self._compute_projection_and_visibility(boids)
        self._last_theta = theta
        self._debug_delta = delta
        self._debug_merged = merged

        # ── Step 2: alignment with σ nearest visible neighbours ────
        #  ⟨v̂_j⟩_visible — mean velocity of σ closest visible birds.
        #  σ = config.sigma (default 4).  Topological, not metric.
        align = pygame.Vector2(0, 0)
        if visible:
            nearest = visible[:config.sigma]
            for nb, _ in nearest:
                align += nb.velocity
            align /= len(nearest)

        # ── Step 3: noise — random unit vector η̂ ──────────────────
        #  Uniform sampling on the unit circle: angle ∈ [0, 2π).
        na = random.uniform(0, 2 * math.pi)
        noise = pygame.Vector2(math.cos(na), math.sin(na))

        # ── Step 4: desired direction from Eq. 3 ──────────────────
        #  v_desired = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
        #
        #  Each term is weighted by its coefficient and summed.
        #  If δ̂ = 0 (fully surrounded), the projection term
        #  contributes nothing — only alignment + noise remain.
        desired = delta * config.phi_p
        if align.length() > 0.001:
            desired += align.normalize() * config.phi_a
        else:
            # No visible neighbours — align with self (inertia)
            if self.velocity.length() > 0.001:
                desired += self.velocity.normalize() * config.phi_a
        desired += noise * config.phi_n

        # Safety: if desired is zero (all terms cancel), randomise
        if desired.length() < 0.001:
            desired = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))

        # ── Step 5: DIRECT velocity set — NO steering ─────────────
        #  Pearce Eq. (2): r_i(t+1) = r_i(t) + v₀·v̂_i(t+1)
        #  The velocity IS the desired direction — no acceleration,
        #  no MAX_FORCE clamping, no inertia.
        #
        #  Compare with original (boid.py):
        #    steer = desired - self.velocity
        #    if steer.length() > MAX_FORCE: steer.scale_to_length(MAX_FORCE)
        #    self.apply_force(steer)
        desired.normalize_ip()
        desired *= V0
        self.velocity = desired
