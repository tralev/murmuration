# Murmuration Extensions — Roadmap Implementations

This directory contains roadmap extensions from the Pearce et al. (2014) paper
implementation audit, implemented as standalone modules that extend the base
simulation **without modifying any original files**.

---

## Quick Start

```bash
# Run the extended simulation (all extensions active)
python3 -m extensions.extended_simulation

# Run all tests (original + extension tests)
python3 -m unittest test_alg2 extensions.test_extensions -v

# Or use the convenience scripts:
./run.sh tests              # Native: 106 tests
./run-docker.sh tests       # Docker: 106 tests
```

---

## What's Included

| Priority | File | Description |
|----------|------|-------------|
| **1a** | `direct_velocity.py` | **Direct velocity setting** — removes Reynolds steering. Velocity set directly per Pearce et al. Eq. 2–3: `v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂`, normalised to v₀. No acceleration accumulation, no MAX_FORCE clamping. |
| **2a** | `steric_repulsion.py` | **Steric repulsion** — short-range 1/r² repulsive force prevents bird overlap (Pearce et al. SI Appendix). `F_rep = φ_s · Σ(r̂_ji / d_ij²)` for birds within `2·BOID_SIZE`. |
| **2b** | `blind_angles.py` | **Blind angles** — 60° blind sector behind each bird (Pearce et al. SI Appendix). Birds whose entire angular interval falls within `[θ + π − β/2, θ + π + β/2]` are invisible. |
| **3a** | `predator.py` | **Predator agent** — peregrine falcon / sparrowhawk (Goodenough et al. 2017). Pursues nearest bird at 2× speed. Birds within 120px danger radius flee with 1/d² force. |
| — | `extended_simulation.py` | **Full simulation entry point** — all extensions active. Press `P` to spawn/remove the predator. Extended help overlay and CSV logging. |
| — | `test_extensions.py` | **59 unit tests** — pure functions, predator dynamics, flight response, blind-angle pipeline, inheritance chain. |

---

## Architecture

Extensions chain via inheritance. Each builds on the previous:

```
Boid                       (original — boid.py)
  └─ DirectVelocityBoid    (1a — direct_velocity.py)
      └─ StericBoid        (2a — steric_repulsion.py)
          └─ BlindAnglesBoid  (2b — blind_angles.py)
              └─ PredatorBoid (3a — predator.py)
```

Method overrides:
- `DirectVelocityBoid` — overrides `flock()` (stashes mode), `update()` (skips clamping), `_flock_projection()` (direct velocity)
- `StericBoid` — extends `_flock_projection()` (adds repulsion after parent)
- `BlindAnglesBoid` — overrides `_compute_projection_and_visibility()` (filters blind region)
- `PredatorBoid` — adds `apply_predator_response()` (flight from danger)
- `Predator` — standalone class (not in boid hierarchy)

---

## Controls (Extended)

All original controls from `alg2.py` work, plus:

| Key | Action |
|-----|--------|
| `P` | Spawn / remove predator |
| `F` | Toggle focal bird debug view (shows blind sector, occlusion arcs) |
| `1–5` | Scenario presets |
| `M` | Toggle PROJECTION / SPATIAL mode |
| `H` | Toggle extended help overlay |

---

## Tunable Parameters

Edit these constants in the module files to experiment:

| Constant | File | Default | Effect |
|----------|------|---------|--------|
| `PHI_STERIC` | `steric_repulsion.py` | 0.03 | Steric repulsion strength |
| `STERIC_RADIUS` | `steric_repulsion.py` | `2 * BOID_SIZE` | Distance where repulsion activates |
| `BLIND_ANGLE` | `blind_angles.py` | `π/3` (60°) | Blind sector width |
| `PREDATOR_SPEED` | `predator.py` | `V0 * 2` | Predator cruising speed |
| `DANGER_RADIUS` | `predator.py` | 120 | Birds flee when predator is this close |
| `FLIGHT_FORCE` | `predator.py` | 1.5 | Strength of flight response |

---

## CSV Output

The extended simulation logs to `output/murmuration_metrics_extended.csv` with
additional columns:

```
frame,mode,num_boids,phi_p,phi_a,phi_n,sigma,theta,theta_ext,alpha,fps,phi_steric,blind_angle,predator_active
```

New columns:
- `phi_steric` — steric weight (float)
- `blind_angle` — blind sector width in radians (float)
- `predator_active` — 1 if predator is spawned, 0 if not

---

## Testing

```bash
# Extension tests only (59 tests)
python3 -m unittest extensions.test_extensions -v

# All tests (106 tests: 47 original + 59 extension)
python3 -m unittest test_alg2 extensions.test_extensions -v

# Docker
./run-docker.sh tests
```

Test coverage:
- `_interval_in_blind_region` — 15 tests (non-wrapping, wrapping, epsilon, degenerate)
- `DirectVelocityBoid` — 10 tests (mode stashing, update, speed clamping, toroidal wrap)
- `StericBoid` — 3 tests (alone, close repulsion, distant no-effect)
- `BlindAnglesBoid` — 4 tests (behind invisible, ahead visible, side visible, empty flock)
- `Predator` — 8 tests (spawn, pursuit, speed clamp, toroidal wrap)
- `PredatorBoid` — 6 tests (no response, flight, stronger-when-closer, re-normalization)
- `InheritanceChain` — 7 tests (isinstance, MRO)
- `BlindOcclusionWorkflow` — 2 integration tests

---

## Implementation Status

From the roadmap in the main [README.md](../README.md#implementation-roadmap--future-work):

| Priority | Item | Status |
|----------|------|--------|
| 1a | Direct velocity setting | ✅ Implemented (`direct_velocity.py`) |
| 1b | External opacity from multiple viewpoints | ❌ Not yet |
| 1c | Track correlation time τᵨ | ❌ Not yet |
| 2a | Steric / repulsive interactions | ✅ Implemented (`steric_repulsion.py`) |
| 2b | Blind angles behind each bird | ✅ Implemented (`blind_angles.py`) |
| 2c | 3D extension | ❌ Not yet |
| 2d | Anisotropic bodies | ❌ Not yet |
| 3a | Predator agent | ✅ Implemented (`predator.py`) |
| 3b | Larger flocks via spatial optimisation | ❌ Not yet |

---

## Licence

GNU General Public License v3.0 — see [LICENSE](../LICENSE).
