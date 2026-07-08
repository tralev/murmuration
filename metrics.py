"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 7 — EXTERNAL OPACITY  (Θ')                                 ║
║  SECTION 8 — METRICS COMPUTATION                                    ║
╚══════════════════════════════════════════════════════════════════════╝

 Scientific metrics and external opacity computation.
 Imported by alg2.py for the main simulation loop.

 Dependencies:  occlusion_geom (interval merging)
                flock_core    (constants, Config)
                boid          (Boid class for opacity access)
──────────────────────────────────────────────────────────────────────
"""

import math
import random
import pygame
from statistics import mean

from occlusion_geom import _normalise_interval, _merge_all
from flock_core import (
    WIDTH, HEIGHT, V0, BOID_SIZE,
    MODE_PROJECTION, MODE_NAMES,
    Config,
)
from external_opacity import compute as _external_opacity


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECTION 8 — METRICS COMPUTATION                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝
#  Real-time scientific metrics with exponential moving average (EMA)
#  smoothing.  Updated once per frame.
#
#  Θ   (internal opacity) — mean fraction of each bird's 2π view
#        occluded by other birds.  Exact in PROJECTION mode (cached
#        during the projection step).  Sampled from 5 random birds
#        in SPATIAL mode to avoid O(N²) cost.
#
#  Θ'  (external opacity) — fraction of sky obscured from a distant
#        observer placed far to the left of the flock.
#
#  α   (order parameter) — |Σ v_i| / (N · v₀).  α ≈ 1 when all birds
#        are aligned; α ≈ 0 for random headings.
#
#  All metrics use EMA smoothing:  x_ema ← x_ema + (x_raw − x_ema) × s
#  with default smoothing factor s = 0.04.
# ──────────────────────────────────────────────────────────────────────

class FlockMetrics:
    """Real-time scientific metrics with EMA smoothing."""
    __slots__ = ("_fps", "_theta", "_theta_ext", "_alpha", "_theta_samples",
                "_power", "_angular_momentum", "_avg_accel", "_dispersion")

    SMOOTH  = 0.04    # EMA factor — lower = smoother but slower response
    SAMPLES = 5        # birds sampled for Θ in SPATIAL mode

    def __init__(self):
        self._fps         = 0.0
        self._theta       = 0.0    # Θ  — mean internal opacity (EMA)
        self._theta_ext   = 0.0    # Θ' — external opacity (EMA)
        self._alpha       = 0.0    # α  — order parameter (EMA)
        self._power             = 0.0    # P  — mean instantaneous power (EMA)
        self._angular_momentum  = 0.0    # L  — mean angular momentum (EMA)
        self._avg_accel         = 0.0    # |a| — mean acceleration magnitude (EMA)
        self._dispersion        = 0.0    # σ_r — mean distance from CoM (EMA)

    def update(self, flock: list, clock: pygame.time.Clock, config: Config):
        """
        Update all metrics for the current frame.

        Parameters
        ----------
        flock  : list[Boid]  — all birds
        clock  : pygame.time.Clock
        config : Config      — for mode-dependent Θ computation
        """
        s = self.SMOOTH
        n = len(flock)
        if n == 0:
            return

        # ── FPS (EMA-smoothed) ────────────────────────────────────
        self._fps += (clock.get_fps() - self._fps) * s

        # ── Θ — internal opacity ──────────────────────────────────
        #  PROJECTION: exact, already cached on each boid as _last_theta.
        #  SPATIAL:    sampled from 5 random birds to avoid O(N²).
        if config.mode == MODE_PROJECTION:
            theta = mean(b._last_theta for b in flock)
        else:
            sample_n = min(self.SAMPLES, n)
            sampled = random.sample(flock, sample_n)
            theta = mean(b.compute_internal_opacity(flock) for b in sampled)
        self._theta += (theta - self._theta) * s

        # ── α — order parameter  |Σ v_i| / (N · v₀) ──────────────
        total_v = pygame.Vector2(0, 0)
        for b in flock:
            total_v += b.velocity
        alpha = total_v.length() / (n * V0)
        self._alpha += (alpha - self._alpha) * s

        # ── Θ' — external opacity ─────────────────────────────────
        theta_ext = _external_opacity(flock)
        self._theta_ext += (theta_ext - self._theta_ext) * s

        # ── Power: P = F·v = acc·v (mean instantaneous power) ────
        power_sum = 0.0
        for b in flock:
            power_sum += b.acceleration.dot(b.velocity)
        self._power += (power_sum / n - self._power) * s

        # ── Angular momentum: L = r × v = x·vy − y·vx ────────────
        am_sum = 0.0
        for b in flock:
            am_sum += b.position.x * b.velocity.y - b.position.y * b.velocity.x
        self._angular_momentum += (am_sum / n - self._angular_momentum) * s

        # ── Avg acceleration magnitude: mean |acc| / MAX_FORCE ────
        from flock_core import MAX_FORCE
        accel_sum = sum(b.acceleration.length() for b in flock)
        self._avg_accel += (accel_sum / n / MAX_FORCE - self._avg_accel) * s

        # ── Flock dispersion: mean distance from centre of mass ───
        com_x = mean(b.position.x for b in flock)
        com_y = mean(b.position.y for b in flock)
        disp_sum = 0.0
        for b in flock:
            dx = b.position.x - com_x
            dy = b.position.y - com_y
            disp_sum += math.hypot(dx, dy)
        self._dispersion += (disp_sum / n - self._dispersion) * s

    # ── Properties ───────────────────────────────────────────────────

    @property
    def fps(self) -> float:                return self._fps
    @property
    def internal_opacity(self) -> float:    return self._theta
    @property
    def external_opacity(self) -> float:    return self._theta_ext
    @property
    def order_param(self) -> float:         return self._alpha
    @property
    def power(self) -> float:              return self._power
    @property
    def angular_momentum(self) -> float:   return self._angular_momentum
    @property
    def avg_acceleration(self) -> float:   return self._avg_accel
    @property
    def dispersion(self) -> float:         return self._dispersion

    # ── Draw ─────────────────────────────────────────────────────────

    def draw(self, screen: pygame.Surface, font: pygame.font.Font,
             config: Config, flock_len: int, preset_label: str = ""):
        """
        Render metrics as a multi-line text overlay in the top-left corner.
        """
        mode_label = MODE_NAMES.get(config.mode, "???")
        theta_label = (
            f"Opacity   internal  Θ  = {self._theta:.3f}"
            if config.mode == MODE_PROJECTION else
            f"Opacity   internal  Θ  ~ {self._theta:.3f}  (sampled ×{self.SAMPLES})"
        )

        lines = [
            f"FPS: {self._fps:.0f}    Boids: {flock_len}    Mode: {mode_label}",
            f"φp={config.phi_p:.3f}    φa={config.phi_a:.3f}    φn={config.phi_n:.3f}    σ={config.sigma}",
            theta_label,
            f"          external  Θ' = {self._theta_ext:.3f}",
            f"Order param          α  = {self._alpha:.3f}",
            f"Power       avg       P  = {self._power:.1f}",
            f"Ang. mom.   avg       L  = {self._angular_momentum:.1f}",
            f"Accel.      avg      |a| = {self._avg_accel:.3f}",
            f"Dispersion  σ_r = {self._dispersion:.1f}",
        ]
        if preset_label:
            lines.insert(0, preset_label)

        y = 10
        for line in lines:
            surf = font.render(line, True, (170, 200, 170))
            screen.blit(surf, (10, y))
            y += 20

