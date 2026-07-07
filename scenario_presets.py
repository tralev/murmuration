"""
Scenario presets for the murmuration simulation.

Each preset is a dict of parameter overrides applied when the user
presses a number key (1-5, 6-0) or a letter key (s, l, i, v, k, q).
Press 3 (Pearce Default) to restore the canonical paper parameters.

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
        "description": "SPATIAL mode. Strong separation -> school shape.",
    },

    # ═══════════════════════════════════════════════════════════════
    #  Companion presets (keys 6-0) — inspired by the TypeScript/Three.js
    #  murmuration project with 11 richly-tuned scenarios.
    #  Note: companion project flock sizes (3,000-16,000) are scaled
    #  down to Python's ~200-bird performance ceiling.
    # ═══════════════════════════════════════════════════════════════

    # ── Preset 6: Quiet Roost ─────────────────────────────────────
    #  Dense, settled, trail-heavy. Birds cluster tightly and move
    #  slowly — like starlings gathering at a roost site at dusk.
    6: {
        "label":      "PRESET 6 — Quiet Roost  (dense, settled)",
        "phi_p":      0.08,
        "phi_a":      0.82,
        "sigma":      8,
        "mode":       MODE_PROJECTION,
        "description": "Dense projection cluster. Roost-like gathering.",
    },

    # ── Preset 7: Comfort Flight ──────────────────────────────────
    #  Smooth gliding with gentle forces. Birds drift lazily —
    #  like a flock on a calm afternoon with no threats.
    7: {
        "label":      "PRESET 7 — Comfort Flight  (smooth glide)",
        "phi_p":      0.04,
        "phi_a":      0.88,
        "sigma":      5,
        "mode":       MODE_PROJECTION,
        "description": "Gentle projection, strong alignment. Smooth flight.",
    },

    # ── Preset 8: Acro Swarm ──────────────────────────────────────
    #  Fast, acrobatic with tight turns. Light projection lets birds
    #  break formation easily — like a flock evading a predator.
    8: {
        "label":      "PRESET 8 — Acro Swarm  (fast, acrobatic)",
        "phi_p":      0.02,
        "phi_a":      0.85,
        "sigma":      3,
        "mode":       MODE_PROJECTION,
        "description": "Light projection, few neighbours. Acrobatic turns.",
    },

    # ── Preset 9: Predator Ripple ─────────────────────────────────
    #  Reactive spatial school with tight grouping. Strong separation
    #  keeps birds from colliding while alignment maintains direction.
    9: {
        "label":      "PRESET 9 — Predator Ripple  (reactive school)",
        "phi_p":      0.30,
        "phi_a":      0.55,
        "sigma":      8,
        "mode":       MODE_SPATIAL,
        "description": "Strong separation + alignment. Reactive school.",
    },

    # ── Preset 0: Storm Turn ──────────────────────────────────────
    #  Extreme streaming with very high alignment. Many neighbours
    #  synchronise velocity — like a flock turning in a storm.
    0: {
        "label":      "PRESET 0 — Storm Turn  (extreme streaming)",
        "phi_p":      0.20,
        "phi_a":      0.72,
        "sigma":      10,
        "mode":       MODE_SPATIAL,
        "description": "Very high alignment, many neighbours. Storm turn.",
    },

    # ═══════════════════════════════════════════════════════════════
    #  Additional companion presets (letter keys s, l, i, v, k, q).
    #  Inspired by the 11-preset TypeScript/Three.js companion project.
    # ═══════════════════════════════════════════════════════════════

    # ── Preset s: Swarm Pilot ─────────────────────────────────────
    #  Balanced, pilot-like flight — controlled and deliberate.
    #  Moderate projection keeps cohesion without blobbing.
    's': {
        "label":      "PRESET s — Swarm Pilot  (balanced, controlled)",
        "phi_p":      0.05,
        "phi_a":      0.85,
        "sigma":      6,
        "mode":       MODE_PROJECTION,
        "description": "Balanced forces. Pilot-like controlled flight.",
    },

    # ── Preset l: Lava Lamp ───────────────────────────────────────
    #  Slow, blobby, fluid — birds clump and drift lazily like
    #  wax in a lava lamp.
    'l': {
        "label":      "PRESET l — Lava Lamp  (blobby, slow)",
        "phi_p":      0.12,
        "phi_a":      0.65,
        "sigma":      7,
        "mode":       MODE_PROJECTION,
        "description": "Strong projection, moderate alignment. Lava-like flow.",
    },

    # ── Preset i: Ink Cloud ───────────────────────────────────────
    #  Spreading, diffusing — low alignment encourages birds to wander.
    #  Like ink dispersing in water.
    'i': {
        "label":      "PRESET i — Ink Cloud  (spreading, diffuse)",
        "phi_p":      0.02,
        "phi_a":      0.40,
        "sigma":      2,
        "mode":       MODE_PROJECTION,
        "description": "Low alignment, high noise. Ink dispersing in water.",
    },

    # ── Preset v: Vacuole ─────────────────────────────────────────
    #  SPATIAL mode with strong separation → birds maintain distance
    #  from neighbours, creating cavity-like voids in the flock.
    'v': {
        "label":      "PRESET v — Vacuole  (hollow, cavity-like)",
        "phi_p":      0.35,
        "phi_a":      0.60,
        "sigma":      9,
        "mode":       MODE_SPATIAL,
        "description": "Strong separation. Cavity-like voids in the flock.",
    },

    # ── Preset k: Silk Sheet ──────────────────────────────────────
    #  Thin, smooth, sheet-like formation — very high alignment
    #  synchronises birds into a near-perfect single direction.
    'k': {
        "label":      "PRESET k — Silk Sheet  (thin, cohesive)",
        "phi_p":      0.02,
        "phi_a":      0.92,
        "sigma":      6,
        "mode":       MODE_PROJECTION,
        "description": "Very high alignment. Thin, smooth sheet formation.",
    },

    # ── Preset q: Quest 2 Dense ───────────────────────────────────
    #  VR-optimised dense flock — strong projection in SPATIAL mode
    #  produces a tight, reactive school ideal for headset viewing.
    'q': {
        "label":      "PRESET q — Quest 2 Dense  (tight, VR-optimised)",
        "phi_p":      0.20,
        "phi_a":      0.55,
        "sigma":      10,
        "mode":       MODE_SPATIAL,
        "description": "Dense spatial school. VR-optimised tight flock.",
    },
}


def apply_preset(config, preset_key) -> str:
    """
    Apply a scenario preset to the given Config object.
    
    Args:
        config: Config object to mutate in place.
        preset_key: int (1-5, 6-9, 0) or str ('s', 'l', 'i', 'v', 'k', 'q').
    
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
