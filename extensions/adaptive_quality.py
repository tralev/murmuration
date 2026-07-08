"""
╔══════════════════════════════════════════════════════════════════════╗
║  ROADMAP 15 — ADAPTIVE QUALITY                                      ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  companion TypeScript project `adaptiveQuality.ts`.

 Keeps the animation smooth on slower hardware by degrading rendering
 quality in three progressive tiers when the frame rate falls short,
 and recovering when it improves.  Hysteresis (asymmetric thresholds +
 cooldowns) prevents oscillation between tiers.

 Tiers (0 = full quality, 3 = maximum degradation):
   1  disable trail rendering        (cheapest first)
   2  reduce render scale −0.15  (down to 0.75×)
   3  reduce bird count ×0.82   (floor 512, most aggressive last)

 Decision logic (fps_smoothed is an EMA, α = 0.1):
   degrade when  fps_smoothed < target × 0.78  and  cooldown 1800ms
   recover when  fps_smoothed > target × 0.92  and  cooldown 3000ms
                 (higher recovery threshold = hysteresis)

 Pure logic (no pygame) — you feed it the measured FPS and current bird
 count each frame and it returns the quality state to apply.  This
 keeps it unit-testable with a synthetic FPS trace.

 Usage:
   from extensions.adaptive_quality import AdaptiveQuality
──────────────────────────────────────────────────────────────────────
"""

import math


# ── Thresholds & tier parameters (companion defaults) ───────────────

DEGRADE_RATIO   = 0.78    # trigger below target × this
RECOVER_RATIO   = 0.92    # recover above target × this (> degrade → hysteresis)
DEGRADE_COOLDOWN = 1800.0  # ms between degradations
RECOVER_COOLDOWN = 3000.0  # ms between recoveries
EMA_ALPHA       = 0.1     # frame-rate smoothing factor

RENDER_SCALE_MIN  = 0.75
RENDER_SCALE_STEP = 0.15
BIRD_COUNT_FLOOR  = 512
BIRD_COUNT_FACTOR = 0.82

MAX_TIER = 3


class AdaptiveQuality:
    """FPS-driven quality controller with three degradation tiers.

    Exposed state (read after each update()):
      tier          — current tier 0..3
      trails_enabled — False once tier ≥ 1
      render_scale  — 1.0 → 0.75 across tier 2 steps
      bird_cap      — target bird count (None until tier 3 acts)
    """

    __slots__ = ("target_fps", "enabled", "tier", "fps_smoothed",
                 "_last_adjust_ms", "trails_enabled", "render_scale",
                 "bird_cap", "_baseline_count")

    def __init__(self, target_fps=60, enabled=True):
        self.target_fps = target_fps
        self.enabled = enabled
        self.tier = 0
        self.fps_smoothed = float(target_fps)
        self._last_adjust_ms = -1e9   # allow an immediate first adjustment
        self.trails_enabled = True
        self.render_scale = 1.0
        self.bird_cap = None
        self._baseline_count = None

    def toggle(self):
        """Enable/disable adaptive quality (the 'A' key). Disabling
        restores full quality immediately."""
        self.enabled = not self.enabled
        if not self.enabled:
            self.reset()
        return self.enabled

    def reset(self):
        """Return to full quality (tier 0)."""
        self.tier = 0
        self.trails_enabled = True
        self.render_scale = 1.0
        self.bird_cap = None

    def update(self, current_fps, now_ms, bird_count):
        """Fold one frame's measured FPS into the controller and,
        if warranted, step the quality tier up or down.

        Parameters
        ----------
        current_fps : float — this frame's instantaneous FPS
        now_ms      : float — monotonic time in milliseconds
        bird_count  : int   — current flock size (for the tier-3 cap)

        Returns
        -------
        int — the (possibly changed) current tier.
        """
        # EMA smoothing so a single stutter doesn't trigger degradation.
        self.fps_smoothed = (self.fps_smoothed * (1 - EMA_ALPHA)
                             + current_fps * EMA_ALPHA)
        if self._baseline_count is None:
            self._baseline_count = bird_count

        if not self.enabled:
            return self.tier

        since = now_ms - self._last_adjust_ms
        degrade_thresh = self.target_fps * DEGRADE_RATIO
        recover_thresh = self.target_fps * RECOVER_RATIO

        if (self.fps_smoothed < degrade_thresh and self.tier < MAX_TIER
                and since > DEGRADE_COOLDOWN):
            self._apply_tier(self.tier + 1, bird_count)
            self._last_adjust_ms = now_ms
        elif (self.fps_smoothed > recover_thresh and self.tier > 0
                and since > RECOVER_COOLDOWN):
            self._apply_tier(self.tier - 1, bird_count)
            self._last_adjust_ms = now_ms

        return self.tier

    def _apply_tier(self, tier, bird_count):
        """Set the concrete quality knobs for the given tier.

        Tiers are cumulative: reaching tier 3 means trails off AND
        reduced scale AND a bird cap.  Stepping back down restores the
        knob owned by the tier being left.
        """
        going_up = tier > self.tier
        self.tier = tier

        # Tier 1 owns trails; on at tier 0, off at tier ≥ 1.
        self.trails_enabled = tier < 1

        # Tier 2 owns render scale.
        if tier >= 2:
            if going_up and self.render_scale > RENDER_SCALE_MIN:
                self.render_scale = max(RENDER_SCALE_MIN,
                                        self.render_scale - RENDER_SCALE_STEP)
        else:
            self.render_scale = 1.0

        # Tier 3 owns the bird cap.
        if tier >= 3:
            base = bird_count if self.bird_cap is None else self.bird_cap
            self.bird_cap = max(BIRD_COUNT_FLOOR,
                                int(math.floor(base * BIRD_COUNT_FACTOR)))
        else:
            self.bird_cap = None
