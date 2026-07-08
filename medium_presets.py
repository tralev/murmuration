"""
╔══════════════════════════════════════════════════════════════════════╗
║  SECTION 5b — MEDIUM PRESETS  (ambient atmosphere)                  ║
╚══════════════════════════════════════════════════════════════════════╝

 Reference:  companion TypeScript project `mediumPresets.ts`.

 Where the scenario presets (scenario_presets.py) tune the *flocking*
 (φp, φa, σ, mode), the medium presets tune the *atmosphere* the flock
 moves through — how the birds are perturbed and rendered, independent
 of the flocking rule.  Four media, from thin to opaque:

   air       — light, breezy, subtle drift
   dust       — heavier, turbulent, dense motes
   starlight  — calm, luminous, near-still
   grid       — reference mode: no perturbation at all

 Each field, and how it feeds the simulation:
   turbulence — random acceleration noise added per bird per frame
   drift      — slow ambient velocity bias (a global "wind")
   density    — number of passive medium particles (dust motes)
   jitter     — random positional offset per medium particle
   opacity / pt_scale / color_mix — rendering hints (alpha, point size,
                colour blend), consumed by the renderer, not the physics.

 Kept dependency-light (stdlib only) so a headless/analysis build can
 import the medium parameters without pygame.

 Usage:
   from medium_presets import MEDIUM_PRESETS, MediumConfig, apply_medium
──────────────────────────────────────────────────────────────────────
"""

import math
import random


# ── Medium preset table (companion mediumPresets.ts values) ─────────
#  Keys are the medium names; each carries the seven companion fields.

MEDIUM_PRESETS = {
    "air": {
        "label":      "MEDIUM air — light breeze",
        "opacity":    0.32, "pt_scale": 0.68, "turbulence": 0.26,
        "drift":      0.24, "color_mix": 0.58, "density": 0.44, "jitter": 0.19,
        "description": "Thin, breezy air with gentle drift and light motes.",
    },
    "dust": {
        "label":      "MEDIUM dust — turbulent haze",
        "opacity":    0.48, "pt_scale": 0.82, "turbulence": 0.42,
        "drift":      0.12, "color_mix": 0.68, "density": 0.76, "jitter": 0.16,
        "description": "Heavy, turbulent dust; dense motes, little steady drift.",
    },
    "starlight": {
        "label":      "MEDIUM starlight — near-still",
        "opacity":    0.72, "pt_scale": 0.66, "turbulence": 0.02,
        "drift":      0.01, "color_mix": 0.88, "density": 0.34, "jitter": 0.15,
        "description": "Calm, luminous, near-still air with sparse bright motes.",
    },
    "grid": {
        "label":      "MEDIUM grid — reference (no perturbation)",
        "opacity":    1.00, "pt_scale": 1.00, "turbulence": 0.00,
        "drift":      0.00, "color_mix": 1.00, "density": 1.00, "jitter": 0.00,
        "description": "Reference medium: no turbulence, no drift, full opacity.",
    },
}

_FIELDS = {"label", "opacity", "pt_scale", "turbulence", "drift",
           "color_mix", "density", "jitter", "description"}

# Physical scale factors mapping the normalised [0, 1] preset fields to
# simulation units (px/frame). Kept here so the presets stay unitless.
_TURBULENCE_ACCEL = 0.15   # max random accel at turbulence = 1.0
_DRIFT_SPEED      = 0.6    # max ambient wind speed at drift = 1.0


class MediumConfig:
    """Active atmosphere parameters, resolved from a medium preset.

    Holds both the raw normalised fields and the derived physical
    quantities (turbulence acceleration, drift velocity) the update
    loop applies to each bird.
    """

    __slots__ = ("name", "opacity", "pt_scale", "turbulence", "drift",
                 "color_mix", "density", "jitter", "drift_dir")

    def __init__(self, name="grid", drift_dir=0.0):
        self.name = name
        self.drift_dir = drift_dir   # radians — direction of the wind
        self.apply(name)

    def apply(self, name):
        """Load a medium preset by name (raises KeyError if unknown)."""
        p = MEDIUM_PRESETS[name]
        self.name = name
        self.opacity = p["opacity"]
        self.pt_scale = p["pt_scale"]
        self.turbulence = p["turbulence"]
        self.drift = p["drift"]
        self.color_mix = p["color_mix"]
        self.density = p["density"]
        self.jitter = p["jitter"]
        return p["label"]

    # ── Derived physical quantities ────────────────────────────────

    def drift_velocity(self):
        """Ambient wind as an (vx, vy) velocity bias, added to every
        bird each frame."""
        speed = self.drift * _DRIFT_SPEED
        return math.cos(self.drift_dir) * speed, math.sin(self.drift_dir) * speed

    def turbulence_accel(self, rng=random):
        """A fresh random acceleration (ax, ay) for one bird this frame,
        with magnitude proportional to the medium's turbulence."""
        if self.turbulence <= 0.0:
            return 0.0, 0.0
        angle = rng.uniform(0, 2 * math.pi)
        mag = rng.uniform(0, self.turbulence * _TURBULENCE_ACCEL)
        return math.cos(angle) * mag, math.sin(angle) * mag


def apply_medium(medium_config: MediumConfig, name: str) -> str:
    """Switch *medium_config* to the named preset; return its label
    (or '' if the name is not a valid medium)."""
    if name not in MEDIUM_PRESETS:
        return ""
    return medium_config.apply(name)
