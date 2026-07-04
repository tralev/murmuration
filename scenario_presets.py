"""
Scenario presets for the murmuration simulation.

Each preset is a dict of parameter overrides applied when the user
presses a number key (1–5).  Press '0' or the preset key again to
return to default values.

Students can add their own presets — just append to the PRESETS dict.
"""

from flock_core import (
    DEFAULT_PHI_P, DEFAULT_PHI_A, DEFAULT_SIGMA,
    MODE_PROJECTION, MODE_SPATIAL,
)


PRESETS = {
    # ── Preset 1: Pure Alignment ──────────────────────────────────
    #  φp = 0 → no projection/separation force.
    #  The flock crystallises into rigid parallel motion.
    #  Students learn: without projection, there is no cohesion —
    #  birds drift apart until only alignment remains.
    1: {
        "label":      "PRESET 1 — Pure Alignment  (rigid crystal)",
        "phi_p":      0.00,
        "phi_a":      0.95,
        "sigma":      8,
        "mode":       MODE_PROJECTION,
        "description": "φp=0: no projection force. Flock crystallises.",
    },

    # ── Preset 2: Gas / Exploration ───────────────────────────────
    #  Low alignment, high noise.  Birds behave like a gas —
    #  random walks with weak social forces.
    #  Students learn: noise dominates when alignment is weak.
    2: {
        "label":      "PRESET 2 — Gas / Exploration  (random walk)",
        "phi_p":      0.10,
        "phi_a":      0.20,
        "sigma":      2,
        "mode":       MODE_PROJECTION,
        "description": "High noise, low alignment. Gas-like behaviour.",
    },

    # ── Preset 3: Pearce et al. Default ───────────────────────────
    #  The canonical bird-flock parameters from the 2014 paper.
    #  Students learn: these values produce marginal opacity —
    #  the "correct" flocking regime the paper predicted.
    3: {
        "label":      "PRESET 3 — Pearce Default  (bird-like flock)",
        "phi_p":      DEFAULT_PHI_P,
        "phi_a":      DEFAULT_PHI_A,
        "sigma":      DEFAULT_SIGMA,
        "mode":       MODE_PROJECTION,
        "description": "φp=0.03, φa=0.80, σ=4. Marginal opacity flock.",
    },

    # ── Preset 4: Dense Ball ──────────────────────────────────────
    #  High projection weight pulls birds tightly together.
    #  Students learn: too much projection → near-opaque ball,
    #  birds can't see out, information propagation slows.
    4: {
        "label":      "PRESET 4 — Dense Ball  (high opacity)",
        "phi_p":      0.15,
        "phi_a":      0.70,
        "sigma":      6,
        "mode":       MODE_PROJECTION,
        "description": "φp=0.15: strong projection. Near-opaque ball.",
    },

    # ── Preset 5: Classic Boids ───────────────────────────────────
    #  SPATIAL mode with strong separation — classic Reynolds school.
    #  Students learn: spatial mode produces elongated schools, not
    #  round murmurations. The two modes have different morphology.
    5: {
        "label":      "PRESET 5 — Classic Boids  (school formation)",
        "phi_p":      0.30,
        "phi_a":      0.50,
        "sigma":      4,
        "mode":       MODE_SPATIAL,
        "description": "SPATIAL mode. Strong separation → school shape.",
    },
}


def apply_preset(config, preset_key: int) -> str:
    """
    Apply a scenario preset to the given Config object.
    Returns the preset label for on-screen display,
    or empty string if the key is not a valid preset.
    """
    preset = PRESETS.get(preset_key)
    if preset is None:
        return ""

    config.phi_p = preset["phi_p"]
    config.phi_a = preset["phi_a"]
    config.sigma = preset["sigma"]
    config.mode  = preset["mode"]

    print(f"[PRESET {preset_key}] {preset['description']}")
    return preset["label"]
