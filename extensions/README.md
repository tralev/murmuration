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

# Run the Scilab extended simulation (all 9 priorities)
# scilab -f extensions/alg2_extended.sce
#  or from Scilab console: exec("extensions/alg2_extended.sce");

# Run the GNU Octave extended simulation (all 9 priorities)
# octave extensions/alg2_extended.m
#  or from Octave console: run extensions/alg2_extended.m

# Run all tests (original + extension tests)
python3 -m unittest discover -p 'test_*.py' -v

# Or use the convenience scripts:
./run.sh tests              # Native: 159 tests
./run-docker.sh tests       # Docker: 159 tests
```

---

## What's Included

| Priority | File | Description |
|----------|------|-------------|
| **1a** | `direct_velocity.py` | **Direct velocity setting** — removes Reynolds steering. Velocity set directly per Pearce et al. Eq. 2–3: `v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂`, normalised to v₀. No acceleration accumulation, no MAX_FORCE clamping. |
| **1b** | `multi_viewpoint_opacity.py` | **Multi-viewpoint external opacity** — computes Θ′ as the average over K=12 viewpoints on a circle of radius 2000, replacing the single-viewpoint observer at (−2000, HEIGHT/2). `FlockMetricsExtended` subclasses `FlockMetrics` to use the multi-viewpoint computation. |
| **1c** | `correlation_time.py` | **Correlation time τᵨ** — `scipy.spatial.ConvexHull` (Qhull) for flock density estimation + autocorrelation-based τᵨ tracker. Ring buffer (capacity 500, sampled every 10 frames). `τᵨ = ∫ C_ρρ(Δt) dΔt` computed from the density time series. |
| **2a** | `steric_repulsion.py` | **Steric repulsion** — short-range 1/r² repulsive force prevents bird overlap (Pearce et al. SI Appendix). `F_rep = φ_s · Σ(r̂_ji / d_ij²)` for birds within `2·BOID_SIZE`. |
| **2b** | `blind_angles.py` | **Blind angles** — 60° blind sector behind each bird (Pearce et al. SI Appendix). Birds whose entire angular interval falls within `[θ + π − β/2, θ + π + β/2]` are invisible. |
| **2c** | `three_d.py` | **3D extension** — full 3D with spherical cap occlusion. Birds move in (x,y,z) with toroidal wrap. Fibonacci sphere discretization (~80 points) provides z-buffered occlusion on the unit sphere. Perspective projection rendering. Blind cone (60°) filtering. Direct velocity setting. |
| **2d** | `anisotropic_bodies.py` | **Anisotropic bodies** — elliptical birds with orientation-dependent projected radius. Formula: `√[(a·sin(θ−ψ))² + (b·cos(θ−ψ))²]`. Semi-major a=1.4·BOID_SIZE (length), semi-minor b=0.7·BOID_SIZE (width). Birds seen from the side appear larger; from behind appear smaller. |
| **3a** | `predator.py` | **Predator agent** — peregrine falcon / sparrowhawk (Goodenough et al. 2017). Pursues nearest bird at 2× speed. Birds within 120px danger radius flee with 1/d² force. |
| **3b** | `spatial_optimization.py` | **Spatial optimization** — reduces per-bird occlusion cost from O(N) to O(N_near + C). Screen divided into 10×7 grid cells. 3×3 surrounding cells get exact per-bird intervals; far chunks contribute single conservative bounding-circle intervals as passive occluders. Enables 500+ birds at acceptable frame rates. |
| **5** | `seasonal.py` | **Seasonal/ecological realism** — Goodenough et al. (2017) citizen-science flock-size curve peaking mid-winter (January) and troughing in summer. Raised-cosine day-of-year multiplier in [0.25, 1.0]. Deterministic predator presence (~29.6% rate). Murmuration-season window (Oct–Mar). |
| **6** | `flock_shape.py` | **Flock shape analysis** — PCA of the position covariance (`numpy.cov` + `numpy.linalg.eigh`) to extract aspect ratio, orientation, and convex-hull area. Interpolates Young et al.'s shape-driven m*: ~6.05 for thin/longitudinal flocks, ~9.78 for thick/transverse flocks. |
| **6** | `h2_robustness.py` | **H₂ robustness metric** — Young et al. (2013) consensus robustness via Laplacian eigenvalues of the k-NN interaction graph. Uses `scipy.spatial.cKDTree` for the neighbour graph and `numpy.linalg.eigvalsh` for the symmetric eigenproblem. η(m) per-neighbour efficiency. Cost-optimal m* balancing robustness against O(m) sensing cost. |
| **7** | `threat.py` | **Threat agent & escape-wave propagation** — two-phase state machine (approach → egress). Birds within danger radius flee with 1/d² force. Escape wave propagates through neighbour graph via relaxation sweeps, producing chain-reaction cascades. |
| **10c** | `wander.py` | **Flock wander behaviour** — a shared moving attractor ("wander centre") that drifts via composite trigonometric noise and a radial breathing pulse. All birds are pulled toward it, producing coordinated organic exploration when no threat or attractor is active. Deterministic (time → centre), no RNG. |
| **15** | `adaptive_quality.py` | **Adaptive quality** — three-tier progressive FPS degradation with hysteresis to keep animation smooth on slower hardware. Tier 1 disables trails, Tier 2 reduces render scale (−0.15, floor 0.75×), Tier 3 caps bird count (×0.82, floor 512). Asymmetric degrade/recover thresholds prevent oscillation. |
| — | `medium_presets.py` | **Ambient atmosphere presets** — four media (air, dust, starlight, grid) tuning turbulence, drift, density, opacity, and colour blend. Per-bird turbulence acceleration and global wind bias. Grid is the reference (no perturbation). |
| — | `extended_simulation.py` | **Full 2D simulation entry point** — all 8 extensions active. Press `f` to spawn/remove the predator. Extended help overlay, CSV logging, τᵨ display, and density readout. |
| — | `extended_simulation_3d.py` | **Full 3D simulation entry point** — Fibonacci sphere occlusion, perspective rendering, CSV logging. Run with `python -m extensions.extended_simulation_3d`. |
| — | `test_extensions.py` | **216 unit tests** — 2D: pure functions, convex hull, correlation time, multi-viewpoint opacity, anisotropic visibility, spatial chunker, predator dynamics, blind-angle pipeline, inheritance chain. 3D: Fibonacci sphere, spherical cap occlusion, 3D physics. Wander, threat, adaptive quality, H₂ robustness, seasonal, flock shape, and medium preset tests. |
| — | `data_loader.py` | **Real-world 3D trajectory ingestion** — parses CSV data (frame, bird_id, x, y, z, vx, vy, vz), computes Θ/Θ′/α using the project's angular-interval merging algorithms. Supports simple count-per-frame format. |
| — | `alg2_extended.sce` | **Full Scilab port of all 9 priorities** — standalone extended Scilab simulation with feature flags (ENABLE_1a..3b). 1650 lines. Run with `exec("extensions/alg2_extended.sce");`. |
| — | `alg2_extended.m` | **Full GNU Octave port of all 9 priorities** — standalone extended Octave simulation with feature flags (ENABLE_1a..3b). 1870 lines. Includes 2D projection with steric repulsion, blind angles, anisotropic bodies, spatial chunker, Graham scan τᵨ, multi-viewpoint Θ′, predator agent, and 3D Fibonacci sphere occlusion. Run with `octave extensions/alg2_extended.m`. |

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

Standalone behaviour/analysis modules (pure functions where possible,
no pygame dependency for testability):

- `wander` (10c) — flock_wander_center() + wander_force() + radial_pulse()
- `threat` (7) — ThreatAgent state machine + escape_wave() propagation
- `adaptive_quality` (15) — AdaptiveQuality controller with hysteresis
- `h2_robustness` (6) — h2_norm() + knn_laplacian() + cost_optimal_m()
- `seasonal` (5) — seasonal_size_factor() + flock_size_for_day()
- `flock_shape` (6) — analyze_shape() → ShapeReport with PCA-based m*
- `medium_presets` — MediumConfig + MEDIUM_PRESETS table
- `correlation_time` (1c) — convex_hull_area() + CorrelationTimeTracker
- `multi_viewpoint_opacity` (1b) — external_opacity_multi_viewpoint()
- `data_loader` — real-world 3D trajectory ingestion

---

## Controls (Extended)

All original controls from `alg2.py` work, plus:

### Extended 2D simulation

| Key | Action |
|-----|--------|
| `P` | Spawn / remove predator (peregrine falcon) |
| `F` | Toggle focal bird debug view (shows blind sector, occlusion arcs) |
| `B` | Toggle TOROIDAL / MARGIN boundary |
| `1–5` | Scenario presets |
| `M` | Toggle PROJECTION / SPATIAL mode |
| `G` | Toggle grid overlay (SPATIAL mode) |
| `H` | Toggle extended help overlay |

All base controls from `alg2.py` also work (`↑↓←→` tune φp/φa, `[/]` tune σ, `+/-` add/remove birds, `SPACE` pause, `R` reset, `ESC` quit).

### Extended 3D simulation

The 3D simulation has no PROJECTION/SPATIAL toggle (always PROJECTION), no predator, and no focal bird debug.

| Key | Action |
|-----|--------|
| `B` | Toggle TOROIDAL / MARGIN boundary |
| `1–5` | Scenario presets |
| `H` | Toggle help overlay |

All base controls from `alg2.py` also work (`↑↓←→` tune φp/φa, `[/]` tune σ, `+/-` add/remove birds, `SPACE` pause, `R` reset, `ESC` quit).

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
| `THREAT_SPEED` | `threat.py` | `V0 * 2.0` | Threat cruising speed |
| `THREAT_RADIUS` | `threat.py` | 140 | Danger zone radius (px) |
| `THREAT_STRENGTH` | `threat.py` | 1.8 | Peak flight-response magnitude |
| `WAVE_GAIN` | `threat.py` | 0.15 | Escape-wave amplification per neighbour |
| `WanderConfig.wander_speed` | `wander.py` | 1.0 | Bird pull strength toward wander centre |
| `WanderConfig.attractor_radius` | `wander.py` | 280 | Base excursion radius (px) |
| `DEGRADE_RATIO` / `RECOVER_RATIO` | `adaptive_quality.py` | 0.78 / 0.92 | FPS thresholds for quality tier changes |
| `BIRD_COUNT_FLOOR` | `adaptive_quality.py` | 512 | Minimum birds under tier-3 cap |
| `PEAK_DAY` | `seasonal.py` | 15 | Day-of-year of max flock size (mid-January) |
| `MIN_FACTOR` | `seasonal.py` | 0.25 | Summer trough multiplier |

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
- `threat_phase` — "approach" or "egress"
- `wander_active` — 1 when flock is wander-driven
- `quality_tier` — adaptive quality tier 0–3
- `medium` — current medium name ("air", "dust", "starlight", "grid")
- `aspect_ratio` — flock PCA aspect ratio
- `h2_norm` — H₂ robustness metric (or -1 if disconnected)
- `m_star` — shape-optimal neighbour count

---

## Testing

```bash
# Extension tests only (159 tests)
python3 -m unittest extensions.test_extensions -v

# All tests (600 tests across 12 test files)
python3 -m unittest discover -p 'test_*.py' -v

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
- `FlockMetricsExtended` — 11 tests (subclass, empty flock, metrics, power, angular momentum, dispersion, avg acceleration)
- `Predator` — 8 tests (spawn, pursuit, nearest-of-two, speed clamp, minimum floor, toroidal wrap)
- `PredatorBoid` — 6 tests (no response, flight, stronger-when-closer, re-normalization, None predator, same spot)
- `InheritanceChain` — 7 tests (isinstance through full chain, MRO with OptimizedBoid/AnisotropicBoid)
- `BlindOcclusionWorkflow` — 2 integration tests
- `Wander` — 6 tests (radial pulse bounds, deterministic centre, movement, domain envelope, force direction, zero at centre)
- `ThreatAgent` — 6 tests (starts in approach, approach→egress, speed clamp, flee force, flee away, escape wave propagation)
- `MediumPresets` — 6 tests (4 media present, expected fields, grid reference, apply_medium, turbulence scaling)
- `AdaptiveQuality` — 5 tests (starts full, degrades progressively, tier-3 bird cap, hysteresis, toggle reset)
- `H₂Robustness` — 6 tests (known eigenvalues, Laplacian rows sum to zero, H₂ decreases with m, disconnected→∞, η positive, cost-optimal m in Young range)
- `Seasonal` — 7 tests (peak at midwinter, summer trough, factor bounds, winter > summer, floor, season window, deterministic predator)
- `FlockShape` — 5 tests (thin→high aspect+low m, round→low aspect+high m, orientation, m* monotone, degenerate)

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
| 5 | Ecological realism (seasonal, predator rates) | ✅ Implemented (`seasonal.py`) |
| 6 | Flock shape & H₂ robustness | ✅ Implemented (`flock_shape.py`, `h2_robustness.py`) |
| 7 | Threat agent & escape-wave propagation | ✅ Implemented (`threat.py`) |
| 10c | Wander behaviour | ✅ Implemented (`wander.py`) |
| 15 | Adaptive quality | ✅ Implemented (`adaptive_quality.py`) |
| — | Ambient medium presets | ✅ Implemented (`medium_presets.py`) |

---

## Licence

GNU General Public License v3.0 or later — see [LICENSE](../LICENSE).
