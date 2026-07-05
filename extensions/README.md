# Murmuration Extensions — Roadmap Implementations

This directory contains roadmap extensions from the Pearce et al. (2014) paper
implementation audit, implemented as standalone modules that extend the base
simulation **without modifying any original files**.

---

## Quick Start

```bash
# Run the extended 2D simulation (all 8 extensions active)
python3 -m extensions.extended_simulation

# Run the 3D simulation (Fibonacci sphere occlusion)
python3 -m extensions.extended_simulation_3d

# Run all tests (original + extension tests)
python3 -m unittest test_alg2 extensions.test_extensions -v

# Or use the convenience scripts:
./run.sh tests              # Native: 158 tests
./run-docker.sh tests       # Docker: 158 tests
```

---

## What's Included

| Priority | File | Description |
|----------|------|-------------|
| **1a** | `direct_velocity.py` | **Direct velocity setting** — removes Reynolds steering. Velocity set directly per Pearce et al. Eq. 2–3: `v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂`, normalised to v₀. No acceleration accumulation, no MAX_FORCE clamping. |
| **1b** | `multi_viewpoint_opacity.py` | **Multi-viewpoint external opacity** — computes Θ′ as the average over K=12 viewpoints on a circle of radius 2000, replacing the single-viewpoint observer at (−2000, HEIGHT/2). `FlockMetricsExtended` subclasses `FlockMetrics` to use the multi-viewpoint computation. |
| **1c** | `correlation_time.py` | **Correlation time τᵨ** — Graham scan convex hull for flock density estimation + autocorrelation-based τᵨ tracker. Ring buffer (capacity 500, sampled every 10 frames). `τᵨ = ∫ C_ρρ(Δt) dΔt` computed from the density time series. |
| **2a** | `steric_repulsion.py` | **Steric repulsion** — short-range 1/r² repulsive force prevents bird overlap (Pearce et al. SI Appendix). `F_rep = φ_s · Σ(r̂_ji / d_ij²)` for birds within `2·BOID_SIZE`. |
| **2b** | `blind_angles.py` | **Blind angles** — 60° blind sector behind each bird (Pearce et al. SI Appendix). Birds whose entire angular interval falls within `[θ + π − β/2, θ + π + β/2]` are invisible. |
| **2c** | `three_d.py` | **3D extension** — full 3D with spherical cap occlusion. Birds move in (x,y,z) with toroidal wrap. Fibonacci sphere discretization (~80 points) provides z-buffered occlusion on the unit sphere. Perspective projection rendering. Blind cone (60°) filtering. Direct velocity setting. |
| **2d** | `anisotropic_bodies.py` | **Anisotropic bodies** — elliptical birds with orientation-dependent projected radius. Formula: `√[(a·sin(θ−ψ))² + (b·cos(θ−ψ))²]`. Semi-major a=1.4·BOID_SIZE (length), semi-minor b=0.7·BOID_SIZE (width). Birds seen from the side appear larger; from behind appear smaller. |
| **3a** | `predator.py` | **Predator agent** — peregrine falcon / sparrowhawk (Goodenough et al. 2017). Pursues nearest bird at 2× speed. Birds within 120px danger radius flee with 1/d² force. |
| **3b** | `spatial_optimization.py` | **Spatial optimization** — reduces per-bird occlusion cost from O(N) to O(N_near + C). Screen divided into 10×7 grid cells. 3×3 surrounding cells get exact per-bird intervals; far chunks contribute single conservative bounding-circle intervals as passive occluders. Enables 500+ birds at acceptable frame rates. |
| — | `extended_simulation.py` | **Full 2D simulation entry point** — all 8 extensions active. Press `P` to spawn/remove the predator. Extended help overlay, CSV logging, τᵨ display, and density readout. |
| — | `extended_simulation_3d.py` | **Full 3D simulation entry point** — Fibonacci sphere occlusion, perspective rendering, CSV logging. Run with `python -m extensions.extended_simulation_3d`. |
| — | `test_extensions.py` | **111 unit tests** — 2D: pure functions, convex hull, correlation time, multi-viewpoint opacity, anisotropic visibility, spatial chunker, predator dynamics, blind-angle pipeline, inheritance chain. 3D: Fibonacci sphere, spherical cap occlusion, 3D physics. |

---

## Architecture

Extensions chain via inheritance. Each builds on the previous:

```
Boid                       (original — boid.py)
  └─ DirectVelocityBoid    (1a — direct_velocity.py)
      └─ StericBoid        (2a — steric_repulsion.py)
          └─ BlindAnglesBoid  (2b — blind_angles.py)
              └─ AnisotropicBoid  (2d — anisotropic_bodies.py)
                  └─ OptimizedBoid  (3b — spatial_optimization.py)
                      └─ PredatorBoid (3a — predator.py)
```

Method overrides:
- `DirectVelocityBoid` — overrides `flock()` (stashes mode), `update()` (skips clamping), `_flock_projection()` (direct velocity)
- `StericBoid` — extends `_flock_projection()` (adds repulsion after parent)
- `BlindAnglesBoid` — overrides `_compute_projection_and_visibility()` (filters blind region)
- `AnisotropicBoid` — overrides `_compute_projection_and_visibility()` (orientation-dependent projected radius)
- `OptimizedBoid` — overrides `_compute_projection_and_visibility()` (chunk-based far-field approximation, falls back to parent without chunker)
- `PredatorBoid` — adds `apply_predator_response()` (flight from danger)
- `Predator` — standalone class (not in boid hierarchy)
- `FlockMetricsExtended` — overrides `update()` (multi-viewpoint Θ′)
- `SpatialChunker` — standalone class (grid-based spatial partitioning)
- `CorrelationTimeTracker` — standalone class (autocorrelation τᵨ tracking)

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
| `K_VIEWPOINTS` | `multi_viewpoint_opacity.py` | 12 | Number of external observer viewpoints |
| `BOID_SEMI_MAJOR` / `BOID_SEMI_MINOR` | `anisotropic_bodies.py` | `1.4·BOID_SIZE` / `0.7·BOID_SIZE` | Elliptical bird axes |
| `BUFFER_SIZE` | `correlation_time.py` | 500 | Ring buffer capacity for density samples |
| `CORR_SAMPLE_INTERVAL` | `correlation_time.py` | 10 | Frames between density samples |
| `GRID_COLS` / `GRID_ROWS` | `spatial_optimization.py` | 10 / 7 | Grid dimensions for spatial chunker |
| `PREDATOR_SPEED` | `predator.py` | `V0 * 2` | Predator cruising speed |
| `DANGER_RADIUS` | `predator.py` | 120 | Birds flee when predator is this close |
| `FLIGHT_FORCE` | `predator.py` | 1.5 | Strength of flight response |

---

## CSV Output

The extended simulation logs to `output/murmuration_metrics_extended.csv` with
additional columns:

```
frame,mode,num_boids,phi_p,phi_a,phi_n,sigma,theta,theta_ext,alpha,fps,phi_steric,blind_angle,tau,density,predator_active
```

New columns:
- `phi_steric` — steric weight (float)
- `blind_angle` — blind sector width in radians (float)
- `tau` — correlation time τᵨ in frames (float)
- `density` — latest flock density estimate from convex hull (float)
- `predator_active` — 1 if predator is spawned, 0 if not

---

## Testing

```bash
# Extension tests only (111 tests)
python3 -m unittest extensions.test_extensions -v

# All tests (158 tests: 47 original + 111 extension)
python3 -m unittest test_alg2 extensions.test_extensions -v

# Docker
./run-docker.sh tests
```

Test coverage:
- `_interval_in_blind_region` — 15 tests (non-wrapping, wrapping, epsilon, degenerate)
- `DirectVelocityBoid` — 10 tests (mode stashing, update, speed clamping, toroidal wrap)
- `StericBoid` — 3 tests (alone, close repulsion, distant no-effect)
- `BlindAnglesBoid` — 4 tests (behind invisible, ahead visible, side visible, empty flock)
- `AnisotropicBoid` — 5 tests (inheritance, side-vs-behind, projected radius range, stationary, empty flock)
- `OptimizedBoid` — 4 tests (inheritance, fallback without chunker, same visibility, empty flock)
- `SpatialChunker` — 4 tests (empty flock, cell population, bird/chunk entries, distance sorting)
- `FibonacciSphere` — 3 tests (point count, unit sphere, hemisphere coverage)
- `Boid3D` — 9 tests (3D vectors, empty flock, visibility, occlusion, velocity, position, z-wrap, inheritance)
- `ConvexHullArea` — 9 tests (empty, degenerate, square, triangle, interior, collinear, scattered, same-point, large)
- `CorrelationTimeTracker` — 8 tests (initial state, empty flock, buffer fill, constant density, sample rate, capacity)
- `MultiViewpointOpacity` — 7 tests (empty, single bird, monotonic, range, varying K, distance scaling, default K)
- `FlockMetricsExtended` — 3 tests (subclass, empty flock, computes metrics)
- `Predator` — 8 tests (spawn, pursuit, nearest-of-two, speed clamp, minimum floor, toroidal wrap)
- `PredatorBoid` — 6 tests (no response, flight, stronger-when-closer, re-normalization, None predator, same spot)
- `InheritanceChain` — 7 tests (isinstance through full chain, MRO with OptimizedBoid/AnisotropicBoid)
- `BlindOcclusionWorkflow` — 2 integration tests

---

## Implementation Status

From the roadmap in the main [README.md](../README.md#implementation-roadmap--future-work):

| Priority | Item | Status |
|----------|------|--------|
| 1a | Direct velocity setting | ✅ Implemented (`direct_velocity.py`) |
| 1b | External opacity from multiple viewpoints | ✅ Implemented (`multi_viewpoint_opacity.py`) |
| 1c | Track correlation time τᵨ | ✅ Implemented (`correlation_time.py`) |
| 2a | Steric / repulsive interactions | ✅ Implemented (`steric_repulsion.py`) |
| 2b | Blind angles behind each bird | ✅ Implemented (`blind_angles.py`) |
| 2c | 3D extension | ✅ Implemented (`three_d.py`) |
| 2d | Anisotropic bodies | ✅ Implemented (`anisotropic_bodies.py`) |
| 3a | Predator agent | ✅ Implemented (`predator.py`) |
| 3b | Larger flocks via spatial optimisation | ✅ Implemented (`spatial_optimization.py`) |

---

## Licence

GNU General Public License v3.0 — see [LICENSE](../LICENSE).
