"""
╔══════════════════════════════════════════════════════════════════════╗
║  ITERATION 7 — Scientific Metrics (Θ, Θ', α)                        ║
╚══════════════════════════════════════════════════════════════════════╝

 Tracks three metrics from Pearce et al. (2014) in real time:

   • Θ  (theta)   — internal opacity: average fraction of each bird's
                    2π field of view occluded by other birds
   • Θ' (theta_ext) — external opacity: fraction of sky obscured from
                     a distant observer's viewpoint
   • α  (alpha)   — order parameter: |Σvᵢ|/(N·v₀), 0=chaos, 1=aligned

 All three use EMA (exponential moving average) smoothing for display.

 What we learn:
   • EMA formula — new = old × 0.9 + raw × 0.1
   • Θ computed exactly in projection mode (from already-merged intervals)
   • Θ' computed from a fixed viewpoint outside the flock
   • α computed as normalised sum of velocity vectors
──────────────────────────────────────────────────────────────────────
"""

class FlockMetrics:
    """
    Tracks Θ, Θ', α with EMA smoothing.
    In projection mode, Θ is exact (from cached intervals).
    In spatial mode, Θ is sampled from 5 random birds.
    """
    def __init__(self):
        self.internal_opacity = 0.0   # Θ
        self.external_opacity = 0.0   # Θ'
        self.order_param = 0.0        # α
        self._alpha = 0.1             # EMA smoothing factor

    def update(self, flock, clock, config, mode):
        """
        Call once per frame after flocking/physics.
        Updates Θ, Θ', α with EMA smoothing.
        """
        import pygame

        # ── Internal opacity Θ ─────────────────────────────────
        if flock:
            # Average cached theta from projection model
            raw_theta = sum(b._last_theta for b in flock) / len(flock)
        else:
            raw_theta = 0.0
        self.internal_opacity = (
            self.internal_opacity * (1 - self._alpha) + raw_theta * self._alpha
        )

        # ── External opacity Θ' ────────────────────────────────
        # Viewpoint: distant observer (-2000, HEIGHT/2) looking right
        raw_ext = self._compute_external_opacity(flock)
        self.external_opacity = (
            self.external_opacity * (1 - self._alpha) + raw_ext * self._alpha
        )

        # ── Order parameter α = |Σvᵢ| / (N·V₀) ────────────────
        if flock:
            from flock_core import V0 as _V0
            total = pygame.Vector2(0, 0)
            for b in flock:
                total += b.velocity
            raw_alpha = total.length() / (len(flock) * _V0)
        else:
            raw_alpha = 0.0
        self.order_param = (
            self.order_param * (1 - self._alpha) + raw_alpha * self._alpha
        )

    def _compute_external_opacity(self, flock):
        """
        Θ' — fraction of sky obscured from viewpoint (-2000, HEIGHT/2).
        Same angular-interval algorithm as Θ but from a fixed observer.
        """
        import math
        viewpoint = (-2000, 350)  # distant left-side observer

        intervals = []
        for b in flock:
            from flock_core import BOID_SIZE as _B
            dx = b.position.x - viewpoint[0]
            dy = b.position.y - viewpoint[1]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.001:
                continue
            centre = math.atan2(dy, dx)
            if centre < 0:
                centre += 2 * math.pi
            half = math.asin(min(_B / dist, 1.0))
            # Extend each interval into [0, 2π) segments
            s, e = centre - half, centre + half
            if s < 0:
                intervals.extend([(s + 2*math.pi, 2*math.pi), (0, e)])
            elif e > 2*math.pi:
                intervals.extend([(s, 2*math.pi), (0, e - 2*math.pi)])
            else:
                intervals.append((s, e))

        if not intervals:
            return 0.0

        from occlusion_geom import _merge_all
        merged = _merge_all(intervals)
        occluded = sum(e - s for s, e in merged)
        return min(occluded / (2 * math.pi), 1.0)

    def draw(self, screen, font, config, n_boids, preset_label=""):
        """
        Render metrics overlay in top-left corner.
        Shows: mode badge, Θ, Θ', α, FPS, boid count.
        """
        import pygame
        mode_name = "PROJECTION" if config.mode == 0 else "SPATIAL"
        lines = [
            f"Mode: {mode_name}    Birds: {n_boids}",
            f"φp={config.phi_p:.2f}  φa={config.phi_a:.2f}  "
            f"φn={config.phi_n:.2f}  σ={config.sigma}",
            f"Θ={self.internal_opacity:.3f}  "
            f"Θ'={self.external_opacity:.3f}  α={self.order_param:.3f}",
        ]
        if preset_label:
            lines.append(preset_label)
        y = 10
        for line in lines:
            txt = font.render(line, True, (200, 210, 180))
            screen.blit(txt, (10, y))
            y += 18


# Note: this file is a standalone metrics module — import it alongside
# the main simulation. See the full codebase for the integrated version.
