"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D SCENARIO PRESETS — educational parameter combinations           ║
╚══════════════════════════════════════════════════════════════════════╝

 Restores the 3D scenario presets that existed before the 3D-only cut
 (they were documented in README.md and lived in the removed
 scenario_presets.py). Each preset is one keystroke that sets φp, φa, σ,
 and mode to demonstrate a distinctive 3D flocking regime.

 Tuned for the 1000 × 700 × 400 volume: PROJECTION-mode presets rely on
 the altitude-cohesion term in spatial_3d.flock_projection_3d, and
 SPATIAL-mode presets use full 3D separation/alignment/cohesion.

 Wired into input_handler_3d.py on keys a–h and w.

 Usage:
   from scenario_presets_3d import apply_preset_3d, PRESETS_3D
──────────────────────────────────────────────────────────────────────
"""

from flock_core import MODE_PROJECTION, MODE_SPATIAL


# Each entry: label, φp, φa, σ, mode, description. φn = 1 − φp − φa.
PRESETS_3D = {
    'a': {"label": "PRESET a — 3D Pearce Default  (marginal opacity)",
          "phi_p": 0.04, "phi_a": 0.80, "sigma": 6, "mode": MODE_PROJECTION,
          "description": "Paper parameters adapted for 3D. Marginal opacity."},
    'b': {"label": "PRESET b — Ball of Birds  (dense sphere)",
          "phi_p": 0.18, "phi_a": 0.70, "sigma": 7, "mode": MODE_PROJECTION,
          "description": "Strong projection -> dense 3D sphere."},
    'c': {"label": "PRESET c — Storm Cloud  (dispersed 3D)",
          "phi_p": 0.06, "phi_a": 0.45, "sigma": 3, "mode": MODE_PROJECTION,
          "description": "Low alignment, high noise. Birds fill the volume."},
    'd': {"label": "PRESET d — 3D Stream  (directional school)",
          "phi_p": 0.25, "phi_a": 0.55, "sigma": 8, "mode": MODE_SPATIAL,
          "description": "Strong 3D separation. Directional stream."},
    'e': {"label": "PRESET e — Vertical Column  (layered pancake)",
          "phi_p": 0.10, "phi_a": 0.75, "sigma": 6, "mode": MODE_PROJECTION,
          "description": "Altitude cohesion -> vertical layering."},
    'f': {"label": "PRESET f — 3D Acro  (rapid 3D turns)",
          "phi_p": 0.02, "phi_a": 0.85, "sigma": 3, "mode": MODE_PROJECTION,
          "description": "Light projection, few neighbours. Acrobatic flight."},
    'w': {"label": "PRESET w — Spiral Vortex  (rotating 3D)",
          "phi_p": 0.08, "phi_a": 0.82, "sigma": 10, "mode": MODE_SPATIAL,
          "description": "Many neighbours, high alignment. 3D spiral vortex."},
    'h': {"label": "PRESET h — 3D Void  (cavity voids)",
          "phi_p": 0.35, "phi_a": 0.58, "sigma": 9, "mode": MODE_SPATIAL,
          "description": "Maximum 3D separation. Hollow cavity formations."},
}

_ENTRY_FIELDS = {"label", "phi_p", "phi_a", "sigma", "mode", "description"}


def apply_preset_3d(config, preset_key) -> str:
    """Apply a 3D preset to *config* in place; return its label (or '' if
    the key is not a valid 3D preset). φn is recomputed automatically by
    Config as 1 − φp − φa."""
    preset = PRESETS_3D.get(preset_key)
    if preset is None:
        return ""
    config.phi_p = preset["phi_p"]
    config.phi_a = preset["phi_a"]
    config.sigma = preset["sigma"]
    config.mode = preset["mode"]
    print(f"[PRESET {preset_key}] {preset['description']}")
    return preset["label"]
