# Extensions — Reference for Re-implementation in the 3D Stack

> **Status update:** several paper-grounded modules have since been ported to
> the 3D stack as standalone, unit-tested modules (tests in `test_science_3d.py`):
> **`occlusion_3d.py`** — true 3D spherical-cap occlusion (the `three_d.py`
> item), now driving `spatial_3d.flock_projection_3d` instead of the XY-plane
> approximation; **`h2_robustness.py`** (Young consensus H₂ + cost-optimal m*,
> m*≈6–7 in 3D); **`flock_shape.py`** (Young 3D shape→m*); **`correlation_time.py`**
> (Pearce τρ via 3D convex-hull volume); and **`ecology.py`** (Goodenough
> seasonal + critical mass + predator, merging the former `seasonal.py` +
> `critical_mass.py`). The behaviour/agent extensions below (threat, wander,
> leader, vacuole, …) are still to do; the port notes here remain their spec.
>
> Note: the analytic cap algebra in `occlusion_3d.py` supersedes `three_d.py`'s
> Fibonacci-lattice z-buffer, which under-resolves at this sim's density (a
> distant bird's cap covers < 1 lattice point). It also fixes `three_d.py`'s δ̂
> sign: Pearce's δ̂ points to the light–dark *boundaries* (cohesion), not to the
> unoccluded open sky (separation) as `three_d.py` computed.

## Purpose of this document

The repository was cut down to a **3D-only ModernGL stack** in commit
`6b71b15` ("remove all 2D simulation code, keep only 3D ModernGL stack").
That commit deleted the entire `extensions/` package (30 modules) along with
the 2D simulation. The last commit that still contained everything is
**`c948b22`** — every file quoted here can be recovered with:

```bash
git show c948b22:extensions/<name>.py
```

This document is the **specification for rewriting those extensions against the
current 3D stack** (`boid_3d.Boid3D`, `spatial_3d.SpatialGrid3D`,
`flock_core.Config`, `renderer_3d`). For each removed module it records: what it
did, its scientific reference, its public API, and **what has to change to make
it 3D** — because the originals assumed 2D `pygame.Vector2` state and a 2D
angular-interval projection.

For the core (non-extension) 2D modules — `boid`, `simulation`, `metrics`,
etc. — see the companion [core_modules.md](core_modules.md).

---

## What the current 3D stack already provides (do NOT re-port these)

Before porting anything, note what `spatial_3d.py` / `boid_3d.py` already cover,
so extensions build on them rather than duplicating them:

| Capability | Where it lives now |
|------------|--------------------|
| 3D boid state (pos/vel/acc as numpy Vec3, `last_theta`) | `boid_3d.Boid3D` |
| Euler integration, speed clamp, toroidal wrap (x,y,z) | `Boid3D.update()` |
| 3D spatial hash, 27-cell neighbour queries | `spatial_3d.SpatialGrid3D` |
| PROJECTION mode (Pearce) — **XY-plane occlusion** + Z altitude cohesion | `spatial_3d.flock_projection_3d` |
| SPATIAL mode (Reynolds) in 3D | `spatial_3d.flock_spatial_3d` |
| Internal opacity Θ (cached per bird) | computed in `flock_projection_3d` |

**Important nuance:** the current 3D projection is an *approximation* — it
projects neighbours onto angular intervals in the **XY plane** (reusing the 2D
`occlusion_geom`) and adds a separate Z "altitude cohesion" nudge. The removed
`three_d.py` had the physically-correct version: **spherical-cap occlusion on a
Fibonacci-sphere-discretised view sphere**. Upgrading projection to true 3D
occlusion is the single biggest scientific improvement available (see
`three_d.py` below).

---

## A. Pearce-SI-Appendix inheritance chain (2D roadmap 1a–3b)

These were built as a subclass chain on the **2D** `Boid`:

```
Boid → DirectVelocityBoid → StericBoid → BlindAnglesBoid
     → AnisotropicBoid → OptimizedBoid → PredatorBoid
```

For 3D they must be re-expressed as behaviours on `Boid3D` (numpy Vec3). The
chain-of-inheritance design does not have to be preserved — in the 3D code the
cleaner route is **composable steering functions** (like `flock_projection_3d`)
rather than a deep subclass tower.

### `direct_velocity.py` — Roadmap 1a (Direct velocity setting)
- **Class:** `DirectVelocityBoid(Boid)`
- **What:** replaces Reynolds acceleration-steering with Pearce Eq. 2–3 —
  velocity is *set directly* to `φp·δ̂ + φa·⟨v̂⟩ + φn·η̂`, normalised to v₀ (no
  `MAX_FORCE` clamp, no acceleration accumulation).
- **3D port:** the current `flock_projection_3d` already applies forces via
  `apply_force`; a direct-velocity variant would instead assign `boid.vel`
  directly (3-vector normalise to V0). Small; mostly a policy toggle on the
  existing 3D projection.

### `steric_repulsion.py` — Roadmap 2a (Steric repulsion)
- **Class:** `StericBoid(DirectVelocityBoid)`; const `PHI_STERIC`, `STERIC_RADIUS`
- **What:** short-range `1/r²` repulsion within `2·BOID_SIZE` prevents overlap.
- **3D port:** trivial — same `1/d²` law with 3D distance vectors. Add as a
  steering term in the 3D flock functions. **Low effort, high value** (stops
  birds occupying the same voxel).

### `blind_angles.py` — Roadmap 2b (Blind rear sector)
- **API:** `_interval_in_blind_region(start, end, ...)`, `BlindAnglesBoid(StericBoid)`, `BLIND_ANGLE`
- **What:** a 60° blind cone behind each bird; neighbours whose whole angular
  interval lies in the rear sector are invisible.
- **3D port:** the 2D "interval in blind arc" test becomes a **3D cone test**
  (angle between the bird's heading and the direction to the neighbour vs. a
  blind half-angle). Conceptually simple in 3D (dot-product cone), but must be
  wired into whichever occlusion path is used.

### `anisotropic_bodies.py` — Roadmap 2d (Elliptical bodies)
- **Class:** `AnisotropicBoid(BlindAnglesBoid)`
- **What:** birds are ellipses; projected radius depends on viewing angle
  `√[(a·sinΔ)² + (b·cosΔ)²]`, a=1.4·size, b=0.7·size.
- **3D port:** becomes an **ellipsoid** projected radius (prolate spheroid along
  the heading). Feeds the angular half-width used by occlusion. Medium effort;
  only meaningful once true 3D occlusion exists.

### `spatial_optimization.py` — Roadmap 3b (Chunked far-field)
- **API:** `SpatialChunker`, `OptimizedBoid(AnisotropicBoid)`
- **What:** 10×7 screen grid; near cells get exact per-bird occlusion, far
  chunks contribute one conservative bounding-circle occluder → O(N_near + C).
- **3D port:** **largely superseded** — `spatial_3d.SpatialGrid3D` already does
  27-cell spatial hashing. Only the *far-field conservative-occluder* idea is
  novel and worth porting if true 3D occlusion proves too slow for large flocks
  (bounding **sphere** per far chunk). Otherwise skip.

### `predator.py` — Roadmap 3a (Hunting predator)
- **Classes:** `Predator`, `PredatorBoid(OptimizedBoid)`; `DANGER_RADIUS`, `PREDATOR_SPEED`, `FLIGHT_FORCE`
- **What:** a predator (2× speed) chases the nearest bird; birds within
  `DANGER_RADIUS` flee with `1/d²` force. (Distinct from `threat.py`, which is a
  scripted approach/egress attacker.)
- **3D port:** predator gets a 3D position/velocity; flee force uses 3D
  direction. Straightforward. Overlaps conceptually with `threat.py` — decide
  which predator model the 3D build wants (recommend porting `threat.py`, the
  richer one, and dropping this).

---

## B. Metrics & analysis extensions

### `three_d.py` — Roadmap 2c (**true** 3D occlusion) ★ highest scientific value
- **API:** `fibonacci_sphere(n=FIB_POINTS)`, `Boid3D(Boid)` (the *original* 3D boid)
- **What:** the physically-correct 3D projection — discretises the view sphere
  with a Fibonacci lattice (~80 points), z-buffers spherical-cap occlusion, and
  derives δ̂ from the light/dark boundary on the sphere.
- **3D port:** this is the reference implementation for upgrading
  `flock_projection_3d` from its XY-plane approximation to genuine spherical-cap
  occlusion. **Highest-value port.** Reconcile its `Boid3D` with the current
  `boid_3d.Boid3D` (they are different classes with the same name).

### `multi_viewpoint_opacity.py` — Roadmap 1b (external opacity Θ′)
- **API:** `external_opacity_multi_viewpoint(flock, ...)`, `FlockMetricsExtended(FlockMetrics)`
- **What:** Θ′ averaged over K=12 observer viewpoints on a circle (radius 2000).
- **3D port:** viewpoints become points on a **sphere** around the flock; each
  casts the 3D occlusion. Depends on `metrics.FlockMetrics` (see
  core_modules.md) being ported first.

### `correlation_time.py` — Roadmap 1c (τᵨ)
- **API:** `convex_hull_area(points)` (scipy Qhull), `CorrelationTimeTracker`
- **What:** density ρ = N / hull-area sampled into a ring buffer; τᵨ = ∫ C_ρρ dΔt.
- **3D port:** `convex_hull_area` → **convex hull volume** via
  `scipy.spatial.ConvexHull(pts3d).volume`; density becomes N / volume. The
  autocorrelation tracker is dimension-agnostic and ports unchanged.

### `h2_robustness.py` — Roadmap 6 (consensus robustness)
- **API:** `symmetric_eigenvalues`, `knn_laplacian`, `h2_norm`, `eta_of_m`, `optimal_m`, `cost_optimal_m`
- **What:** Young et al. (2013) — k-NN graph Laplacian spectrum → H₂ norm, per-
  neighbour efficiency η(m), cost-optimal m*.
- **3D port:** **almost free** — already uses `scipy.spatial.cKDTree` and
  `numpy.linalg.eigvalsh`, and `_as_tuple` already handles a `.z`. Feed 3D
  positions and it works. Highest value-per-effort of the analysis set.

### `flock_shape.py` — Roadmap 6 (shape → m*)
- **API:** `ShapeReport`, `suggested_m_star`, `analyze_shape`
- **What:** PCA of position covariance → aspect ratio, orientation, hull area →
  interpolated Young m* (6.05 thin ↔ 9.78 round).
- **3D port:** covariance becomes 3×3 (`numpy.cov` + `eigh` already generalise);
  report three principal axes; "aspect ratio" becomes major/minor axis of the
  3D ellipsoid. Medium effort.

### `data_loader.py` — empirical trajectory ingestion
- **API:** `load_trajectories`, `compute_opacity`, `compute_opacity_timeseries`, `load_simple_format`
- **What:** loads recorded bird trajectories and computes opacity from real data
  (validation against experiment).
- **3D port:** the loader is format-only (dimension-agnostic); `compute_opacity`
  must call the 3D occlusion. Low priority unless validating against 3D datasets.

---

## C. Behaviour / interaction extensions (mostly pure functions)

Most of these were written as **pure functions on `(x, y)` tuples or
`pygame.Vector2`**, returning a force. Porting = accept/return 3-component
vectors and add the Z term. Effort is uniformly **low** unless noted.

### `wander.py` — Roadmap 10c (shared wander attractor)
- **API:** `WanderConfig`, `radial_pulse`, `flock_wander_center`, `wander_force`
- **What:** a deterministic moving "wander centre" (composite trig noise +
  breathing radius) all birds are pulled toward.
- **3D port:** the module is 2D (`flock_wander_center` returns `(cx, cy)` from
  dx/dy composite trig). Add a third composite-trig axis and return
  `(cx, cy, cz)` scaled by `DEPTH`; `wander_force` then pulls in 3D. The
  companion `flockWander` spec (README roadmap 10c) gives the z-axis trig
  coefficients to use. Low effort.

### `threat.py` — Roadmap 7 (scripted attacker + escape wave)
- **API:** `ThreatAgent` (approach→egress state machine), `flee_force`, `escape_wave`
- **What:** a threat dives at the swarm centre then egresses; birds flee; the
  escape response propagates neighbour-to-neighbour as a relaxation wave.
- **3D port:** `ThreatAgent` position/velocity → 3D; `flee_force` uses 3D
  direction; `escape_wave` is graph-based and dimension-agnostic. Medium effort,
  high visual payoff. **Recommended 3D predator model** (supersedes `predator.py`).

### `leader.py` — Priority 5 (Lissajous attractors)
- **API:** `LeaderConfig`, `LeaderAnchor`, `attractor_force`, `leader_force`, `draw_anchors`
- **What:** N anchor points move on sinusoidal Lissajous orbits; birds are drawn
  toward the nearest within range.
- **3D port:** anchors get a z Lissajous term; `attractor_force` uses 3D
  distance; `draw_anchors` → 3D marker in `renderer_3d`. Low/medium effort.

### `flow_field.py` — Priority 10b (wind / drift)
- **API:** `FlowConfig`, `flow_force`, `draw_flow`
- **What:** an ambient wind field with gusts and a slowly wandering direction.
- **3D port:** wind direction becomes a 3-vector (azimuth + elevation);
  `flow_force` returns 3D. Low effort.

### `shell_formation.py` — Priority 5 (concentric shells)
- **API:** `ShellConfig`, `assign_shells`, `shell_force`, `draw_shells`
- **What:** birds orbit the leader in concentric geometric shells.
- **3D port:** shells become **spherical shells** (radius bands in 3D); orbit
  direction is a 3D tangent. Medium effort; more natural in 3D than 2D.

### `inertia.py` — Roadmap 8 (turn smoothing)
- **API:** `blend_inertia(velocity, desired, inertia=0.84)`, `turn_rate`
- **3D port:** blends two vectors and renormalises — works on 3-vectors as-is
  once `_xy` is generalised. Trivial.

### `blob_init.py` — Roadmap 8 (clustered start positions)
- **API:** `blob_positions(count, dims=2|3, ...)`
- **3D port:** **already supports `dims=3`** — call with `dims=3` and 3D bounds.
  No porting needed; just wire into `main_3d` flock initialisation.

### `roosting.py` — Roadmap 5 (dusk roost attractor)
- **API:** `dusk_factor`, `roost_force`, `is_roosting_time`
- **3D port:** roost site becomes a 3D point (near the ground plane, low z);
  `roost_force` returns 3D. Low effort.

### `critical_mass.py` — Roadmap 5 (onset threshold)
- **API:** `coherence_factor`, `has_critical_mass`, `gated_weight`
- **3D port:** **dimension-agnostic** (operates on flock *size*, not geometry).
  Works unchanged.

### `seasonal.py` — Roadmap 5 (flock-size season curve)
- **API:** `seasonal_size_factor`, `flock_size_for_day`, `is_murmuration_season`, `predator_present`
- **3D port:** **dimension-agnostic.** Works unchanged.

---

## D. UI / rendering-support extensions (2D-specific)

### `themes.py` — colour schemes
- **API:** `Theme`, `THEMES`, `get_theme`, `cycle_theme`
- **3D port:** the palette concept survives, but colours feed **GLSL uniforms /
  clear colour** in `renderer_3d`, not pygame draw calls. Re-target rather than
  port. Low effort, optional.

### `pilot_state.py` — Roadmap 16 (rich flock pilot)
- **API:** `SimulationPilot` (heading, radius, roll, medium_pulse)
- **3D port:** heading becomes a 3D direction (or quaternion); roll/bank still
  apply. Only needed if a scripted-leader camera/behaviour is wanted. Low
  priority.

---

## E. Orchestration & framework — explicit decisions requested

### `orchestration.py` — **decision: RE-IMPLEMENT (in adapted form), do it last**
- **API:** `init_ext_state()`, `apply_forces(flock, ext_state, clock)`, `render(screen, ext_state, flock, font)`
- **What:** the central 2D hub — one place that flag-gates every extension's
  state init, per-frame force application, and overlay rendering, so the core
  loop stays extension-agnostic.
- **Decision & rationale:** the *pattern* is worth keeping — as soon as more
  than one or two 3D extensions exist, `main_3d.py`'s loop should delegate to a
  `orchestration_3d` hub rather than growing a branch per extension. **But** it
  cannot be ported verbatim: its `render()` calls pygame 2D draw APIs and its
  `apply_forces()` assumes `pygame.Vector2`. Re-implement it **after** a handful
  of 3D extensions exist (so the hub reflects real 3D needs), targeting
  `renderer_3d` for overlays and `apply_force` (numpy) for forces. Not needed
  for the first one or two extensions.

### `vacuole.py` — **decision: RE-IMPLEMENT (good 3D fit), medium priority**
- **API:** `VacuoleConfig`, `VacuoleAgent`, `vacuole_force`, `draw_vacuole`
- **What:** an orbiting repulsor that carves a moving cavity ("vacuole") in the
  flock — birds within its radius are pushed radially outward.
- **Decision & rationale:** **worth re-implementing** — a moving spherical void
  is arguably more striking in 3D than 2D, and the maths is a clean
  `1/d²`-style radial push that generalises directly to 3 vectors. `VacuoleAgent`
  orbits the swarm centre (add a z orbit component); `vacuole_force` returns a
  3-vector; `draw_vacuole` becomes a translucent sphere / ring in `renderer_3d`.
  Medium priority (behavioural flair, not core science). Note it overlaps with
  the "split/blackening" idea — a threat and a vacuole together produce the
  classic predator-carved hole.

---

## Suggested port order (value ÷ effort)

| Priority | Modules | Why |
|----------|---------|-----|
| 1 | `three_d.py` (spherical-cap occlusion) | Upgrades projection from approximation to correct physics |
| 2 | `h2_robustness`, `critical_mass`, `seasonal`, `blob_init` | Nearly dimension-agnostic — near-zero porting cost |
| 3 | `steric_repulsion`, `inertia`, `wander`, `flow_field`, `roosting` | Simple pure-function force ports |
| 4 | `threat` (+ `vacuole`, `leader`, `shell_formation`) | High visual payoff; drop `predator.py` in favour of `threat` |
| 5 | `metrics`/`external_opacity` → then `multi_viewpoint_opacity`, `correlation_time`, `flock_shape` | Need a 3D metrics core first |
| 6 | `orchestration_3d` hub, `themes`, `pilot_state` | Framework/UI polish, once several extensions exist |
| — | `spatial_optimization`, `data_loader`, `predator` | Skip / low priority (superseded or niche) |

The `blind_angles` and `anisotropic_bodies` refinements only become meaningful
*after* true 3D occlusion (priority 1) is in place.
