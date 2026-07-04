"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 7 — EXTERNAL OPACITY  (Θ')                                 ║
║  SECTION 8 — METRICS COMPUTATION                                    ║
║  SECTION 10 — HELP OVERLAY                                          ║
╚══════════════════════════════════════════════════════════════════════╝

 Scientific metrics, external opacity computation, and help overlay.
 Imported by alg2.py for the main simulation loop.

 Dependencies:  occlusion_geom (interval merging)
                flock_core    (constants, Config)
                boid          (Boid class for opacity access)
──────────────────────────────────────────────────────────────────────
"""

import math
import random
import pygame

from occlusion_geom import _normalise_interval, _merge_all
from flock_core import (
    WIDTH, HEIGHT, V0, BOID_SIZE,
    MODE_PROJECTION, MODE_NAMES,
    Config,
)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECTION 7 — EXTERNAL OPACITY  (Θ')                                  ║
# ╚══════════════════════════════════════════════════════════════════════╝
#  Θ' — fraction of the sky obscured from a distant external observer.
#  The observer is placed at (−2000, HEIGHT/2), far to the left of the
#  flock.  Angular intervals subtended by each bird are merged to find
#  the total occluded angular width.
#
#  Complexity: O(N log N) where N = |flock|.
# ──────────────────────────────────────────────────────────────────────

def _external_opacity(flock: list) -> float:
    """
    Compute Θ' — external opacity from a distant left-side observer.

    For each bird, compute the angular interval it subtends from the
    viewpoint at (−2000, HEIGHT/2).  Sort all intervals by start angle,
    merge overlaps, and sum the merged widths divided by 2π.
    """
    if not flock:
        return 0.0

    viewpoint = pygame.Vector2(-2000, HEIGHT / 2)
    intervals = []
    for b in flock:
        diff = b.position - viewpoint
        dist = diff.length()
        if dist < 0.001:
            continue
        centre = math.atan2(diff.y, diff.x)
        if centre < 0:
            centre += 2 * math.pi
        half = math.asin(min(BOID_SIZE / dist, 1.0))
        intervals.extend(_normalise_interval(centre - half, centre + half))

    merged = _merge_all(intervals)
    occluded = sum(e - s for s, e in merged)
    return min(occluded / (2 * math.pi), 1.0)


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
    __slots__ = ("_fps", "_theta", "_theta_ext", "_alpha", "_theta_samples")

    SMOOTH  = 0.04    # EMA factor — lower = smoother but slower response
    SAMPLES = 5        # birds sampled for Θ in SPATIAL mode

    def __init__(self):
        self._fps         = 0.0
        self._theta       = 0.0    # Θ  — mean internal opacity (EMA)
        self._theta_ext   = 0.0    # Θ' — external opacity (EMA)
        self._alpha       = 0.0    # α  — order parameter (EMA)
        self._theta_samples = 0

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
            theta = sum(b._last_theta for b in flock) / n
        else:
            sample_n = min(self.SAMPLES, n)
            sampled = random.sample(flock, sample_n)
            theta = sum(b.compute_internal_opacity(flock) for b in sampled) / sample_n
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

    # ── Properties ───────────────────────────────────────────────────

    @property
    def fps(self) -> float:                return self._fps
    @property
    def internal_opacity(self) -> float:    return self._theta
    @property
    def external_opacity(self) -> float:    return self._theta_ext
    @property
    def order_param(self) -> float:         return self._alpha

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
        ]
        if preset_label:
            lines.insert(0, preset_label)

        y = 10
        for line in lines:
            surf = font.render(line, True, (170, 200, 170))
            screen.blit(surf, (10, y))
            y += 20


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SECTION 10 — HELP OVERLAY                                          ║
# ╚══════════════════════════════════════════════════════════════════════╝
#  Semi-transparent panel in the top-right corner showing all keyboard
#  controls.  Toggled by pressing 'h'.
# ──────────────────────────────────────────────────────────────────────

_HELP_LINES = [
    "CONTROLS",
    "─────────────────────────────────────────",
    "M         toggle PROJECTION / SPATIAL mode",
    "1–5       scenario presets",
    "↑ / ↓     φp  ±0.01",
    "← / →     φa  ±0.01   (φn = 1 − φp − φa)",
    "[ / ]     σ   ±1      (neighbour count)",
    "+ / -     add / remove 10 birds",
    "F         toggle focal bird debug view",
    "G         toggle grid overlay (SPATIAL)",
    "H         hide this help",
    "SPACE     pause / resume",
    "R         reset flock",
    "ESC       quit",
]


def _draw_help(screen: pygame.Surface, font: pygame.font.Font):
    """
    Render the help overlay as a semi-transparent panel in the top-right.
    """
    x, y = WIDTH - 370, 10
    bg = pygame.Surface((360, len(_HELP_LINES) * 18 + 12), pygame.SRCALPHA)
    bg.fill((10, 12, 18, 200))
    screen.blit(bg, (x - 4, y - 4))
    for line in _HELP_LINES:
        surf = font.render(line, True, (200, 200, 160))
        screen.blit(surf, (x, y))
        y += 18
