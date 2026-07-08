# Core 2D Modules — 3D-Port Assessment

## Purpose of this document

Commit `6b71b15` removed the 2D simulation, leaving a **3D-only ModernGL
stack**. Besides the `extensions/` package (documented in [ext.md](ext.md)),
that cut also deleted the *core* 2D modules listed below. They can be recovered
from the last pre-removal commit **`c948b22`**:

```bash
git show c948b22:<name>.py
```

This document records what each removed core module did, its public API, the
**equivalent (if any) that already exists in the 3D stack**, and a **decision on
whether it needs a 3D implementation**. This is the input for deciding what to
rebuild — several of these are already covered by `boid_3d.py` /
`spatial_3d.py` / `main_3d.py` and should **not** be re-created.

### Current 3D stack (the target these would plug into)

`boid_3d.Boid3D` · `spatial_3d.SpatialGrid3D` + `flock_projection_3d` +
`flock_spatial_3d` · `camera_3d.OrbitCamera` · `renderer_3d` · `shaders_3d` ·
`main_3d` · `input_handler_3d` · `capture_3d` · `flock_core` (Config,
constants) · `occlusion_geom` (shared angular-interval math) · `features` ·
`test_3d`.

---

## The projection model (explicitly requested)

### `projection_model.py` — Pearce hybrid projection (2D)
- **API:** `compute_projection_and_visibility(boid, boids)`,
  `flock_projection(boid, boids, config)`
- **What:** the 2D Pearce et al. (2014) model — for one bird, merge neighbours'
  angular intervals (via `occlusion_geom`) to find visible birds and the
  light/dark domain boundaries, compute δ̂, alignment over σ nearest visible
  neighbours, noise, and the cached internal opacity Θ.
- **Already in 3D?** **Yes, in approximate form.** `spatial_3d.flock_projection_3d`
  is the 3D counterpart: it reuses the same 2D `occlusion_geom` on an **XY-plane
  projection** of the neighbours and adds a separate Z "altitude cohesion" term.
- **Decision — needed for 3D?** The *basic* projection is already implemented,
  so a straight port is **not** required. What **is** worth implementing is the
  **true 3D projection** (spherical-cap occlusion on a Fibonacci-sphere view
  sphere) from the removed `extensions/three_d.py` — that replaces the XY-plane
  approximation with correct physics. In other words: don't port
  `projection_model.py` verbatim; **upgrade `flock_projection_3d` using
  `three_d.py` as the reference** (see [ext.md](ext.md) §B). **Priority: high**
  (this is the scientific heart of the model).

---

## Core simulation modules

### `boid.py` — the 2D agent
- **API:** `Boid` with `update()`, `apply_force()`, `flock()`,
  `_flock_projection()`, `_flock_spatial()`, `compute_internal_opacity()`,
  `draw()`
- **What:** per-bird 2D state (`pygame.Vector2` pos/vel/acc, `history` trail,
  `last_theta`), Euler integration with speed clamp and toroidal/margin
  boundary, mode dispatch, and 2D triangle drawing.
- **Already in 3D?** **Yes — fully.** `boid_3d.Boid3D` is the direct equivalent
  (numpy Vec3 pos/vel/acc, `last_theta`, `update()`, `apply_force()`, `flock()`
  dispatching to the 3D mode functions).
- **Decision — needed for 3D?** **No.** `Boid3D` already covers it. Two gaps
  worth noting only if wanted: (a) no **margin boundary** mode in 3D (only
  toroidal wrap); (b) no **trail history** (`self.history`) — needed only if
  3D velocity trails are added later.

### `boid_render.py` — 2D bird/trail drawing
- **API:** `draw_boid(screen, boid, config)`
- **What:** draws a bird as a heading-oriented triangle (+ trail polyline) with
  pygame; duck-types the boid.
- **Already in 3D?** **Yes — conceptually.** `renderer_3d` draws all birds as
  instanced 3D meshes (oriented by velocity in the vertex shader) — a GPU
  equivalent that scales far better.
- **Decision — needed for 3D?** **No.** Rendering is handled by `renderer_3d` /
  `shaders_3d`. Do not port pygame drawing into the 3D stack.

### `simulation.py` — per-frame 2D update orchestrator
- **API:** `update_frame(config, flock, metrics, grid, frame, clock,
  pending_remove, pending_add, pending_reset, focal_index, log_fid)`
- **What:** one frame of the 2D loop — apply pending boid-count changes and
  reset, rebuild the grid, run `flock()` then `update()` on every bird, update
  metrics, and write CSV.
- **Already in 3D?** **Yes — inlined.** `main_3d.main()` already performs the
  same sequence (count changes, reset, `grid.rebuild`, flock, update) directly
  in its loop.
- **Decision — needed for 3D?** **Not as a separate module now.** It would only
  be worth **extracting** an equivalent `simulation_3d.update_frame()` for the
  same reason the 2D code did it — testability and to keep `main_3d` lean — and
  especially once metrics + an extension hub are added. Optional refactor, low
  priority.

### `metrics.py` — scientific metrics + HUD panel
- **API:** `FlockMetrics` with `update()`, `draw()`, and properties `fps`,
  `internal_opacity` (Θ), `external_opacity` (Θ′), `order_param` (α), `power`,
  `angular_momentum`, `avg_acceleration`, `dispersion`
- **What:** EMA-smoothed real-time metrics; draws the top-left readout panel.
  Duck-types the flock (uses 2D velocity/position).
- **Already in 3D?** **Partially.** Internal opacity Θ is computed (as
  `Boid3D.last_theta`), but there is **no metrics aggregation, no Θ′, α, power,
  angular momentum, dispersion, and no on-screen readout** in the 3D stack.
- **Decision — needed for 3D?** **Yes, worth implementing** if the 3D build
  should be a scientific tool rather than a demo. Port as `metrics_3d` computing
  the same quantities with 3D vectors (α and dispersion generalise directly;
  angular momentum becomes the 3-vector L = Σ r×v). The HUD `draw()` must be
  re-targeted to a text overlay in `renderer_3d` (or a pygame HUD surface
  blended over the GL frame). **Prerequisite** for `multi_viewpoint_opacity`
  and `correlation_time` from ext.md. Medium effort, medium/high value.

### `external_opacity.py` — observer-side opacity Θ′
- **API:** `compute(flock) -> float`
- **What:** fraction of the sky a single distant observer (far to the left of
  the flock) sees occluded — the "external opacity" Θ′.
- **Already in 3D?** **No.**
- **Decision — needed for 3D?** **Yes if metrics are ported** (Θ′ is one of the
  headline Pearce metrics). In 3D the observer is a point on a sphere around the
  flock casting the 3D occlusion; the multi-viewpoint version
  (`multi_viewpoint_opacity`, ext.md §B) generalises it to K viewpoints. Bundle
  this with the `metrics_3d` work.

---

## UI / input modules (2D-specific)

### `input_handler.py` — 2D keyboard/mouse events
- **API:** `handle_events(...)`, `_get_preset_key`, `_save_config`, `_restore_config`
- **What:** the fixed 2D controls (presets, mode, φ/σ tuning, boid count, focal
  bird, pause/reset, boundary toggle) and mouse focal-selection.
- **Already in 3D?** **Yes.** `input_handler_3d.handle_input()` is the 3D
  counterpart (adds orbit/zoom/auto-rotate/camera-reset; drops the 2D-only
  boundary toggle and — currently — scenario presets).
- **Decision — needed for 3D?** **No** — `input_handler_3d` covers it. Only gap:
  **scenario presets were dropped** from the 3D handler. If 3D presets are
  wanted, port `scenario_presets.apply_preset_3d` (it already existed) and wire
  the a–h/w keys back into `input_handler_3d`. Low effort.

### `focal_debug.py` — focal-bird debug overlay
- **API:** `draw(screen, boid, font)`
- **What:** highlights one bird and draws its occlusion intervals / δ̂ vector —
  a teaching aid that makes the projection maths visible.
- **Already in 3D?** **No.**
- **Decision — needed for 3D?** **Optional / low priority.** Valuable
  pedagogically, but re-implementing occlusion-arc visualisation in 3D
  (spherical caps on a wireframe view sphere) is real work and only makes sense
  after true 3D occlusion exists. Defer.

### `hud.py` — status badges, paused banner, preset tooltip
- **API:** `draw_badges()`, `draw_paused_banner()`, `draw_preset_tooltip()`
- **What:** small pygame text overlays (mode/boundary badge, PAUSED notice,
  active-preset tooltip).
- **Already in 3D?** **Partially** — `main_3d` shows mode/φ/σ/FPS in the
  **window title bar** instead of an on-screen HUD.
- **Decision — needed for 3D?** **Optional.** The title-bar readout covers the
  essentials. A proper in-frame HUD would be part of the same text-overlay work
  as `metrics_3d`; fold it in there rather than porting `hud.py` standalone.

### `help_overlay.py` — H-key controls panel
- **API:** `_build_help_lines()`, `draw(screen, font)`
- **What:** a flag-aware, semi-transparent panel listing all key bindings.
- **Already in 3D?** **No** (3D controls are only printed to stdout at startup).
- **Decision — needed for 3D?** **Optional, nice-to-have.** Re-implement as a
  text overlay in `renderer_3d` listing the 3D controls. Low effort once a text-
  overlay path exists; bundle with the HUD/metrics overlay work.

---

## Summary decision table

| Module | 3D equivalent exists? | Implement for 3D? | Priority |
|--------|-----------------------|-------------------|----------|
| `projection_model.py` | Yes (XY-plane approx in `flock_projection_3d`) | Upgrade to true 3D occlusion via `three_d.py` | **High** |
| `boid.py` | Yes — `Boid3D` | No | — |
| `boid_render.py` | Yes — `renderer_3d` | No | — |
| `simulation.py` | Yes — inlined in `main_3d` | Optional extract (`simulation_3d`) | Low |
| `metrics.py` | Partial (Θ only) | Yes — `metrics_3d` | Medium |
| `external_opacity.py` | No | Yes, with metrics | Medium |
| `input_handler.py` | Yes — `input_handler_3d` | No (only re-add presets if wanted) | Low |
| `focal_debug.py` | No | Optional — defer to after 3D occlusion | Low |
| `hud.py` | Partial (title bar) | Optional — fold into metrics overlay | Low |
| `help_overlay.py` | No | Optional — nice-to-have overlay | Low |

**Bottom line:** the agent, rendering, spatial grid, physics, input, and basic
projection are **already covered** by the 3D stack — do not re-create them. The
genuinely worthwhile new 3D work is: (1) **true 3D spherical-cap occlusion**
(from `three_d.py`), and (2) a **3D metrics core** (`metrics_3d` + `external_opacity`
+ HUD overlay), which then unlocks the metric extensions in [ext.md](ext.md).
Everything else is optional polish.
