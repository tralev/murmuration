# Murmuration — Architecture & Module Reference

This document describes the module dependency graph, feature flag system,
configuration knobs, and the process for adding new features. For usage
instructions see [USER_GUIDE.md](USER_GUIDE.md); for scientific background
see [README.md](README.md).

---

## Module Dependency Graph

The codebase is split into two independent stacks — 2D (Pygame CPU rendering)
and 3D (ModernGL GPU rendering) — that share only the pure-math occlusion
geometry and the constants/config module.

```
    ┌──────────────────┐        ┌──────────────────┐
    │  occlusion_geom  │        │    flock_core    │
    │  pure math —     │        │  constants,      │
    │  angular         │        │  Config,         │
    │  intervals       │        │  SpatialGrid     │
    └────────┬─────────┘        └────────┬─────────┘
             │   two zero-dependency     │
             │   roots — flock_core      │
             │   imports stdlib only     │
             └────────────┬──────────────┘
                          │  (imported by every module below)
         ┌────────────────┼────────────────────┐
         │                │                    │
┌────────▼─────────┐ ┌────▼──────────────┐ ┌───▼──────────────┐
│ projection_model │ │   spatial_model   │ │ external_opacity │
└────────┬─────────┘ └────┬──────────────┘ └───┬──────────────┘
         └───────┬────────┘                    │
        ┌────────▼─────────┐          ┌────────▼─────────┐
        │      boid.py     │          │    metrics.py    │
        └────────┬─────────┘          └────────┬─────────┘
                 │        metrics duck-types   │
                 │        the flock — it does  │
                 │        NOT import boid      │
    ┌────────────┴─────────────┐               │
    │                          │               │
┌───▼──────────────┐ ┌─────────▼────────┐      │
│  input_handler   │ │  simulation.py   │◄─────┘
│  (also imports   │ │  (also imports   │
│ scenario_presets)│ │   metrics)       │
└───┬──────────────┘ └─────────┬────────┘
    │                          │
┌───▼──────────────────────────▼────────────────┐
│           alg2.py  (2D entry point)           │
│  also imports boid, boid_render, hud, and     │
│  (flag-gated) metrics, help_overlay,          │
│  focal_debug                                  │
└───────────────────────────────────────────────┘

    ┌──────────────────┐  ┌──────────────────┐    (leaf render helpers —
    │  boid_render.py  │  │      hud.py      │     import flock_core
    └──────────────────┘  └──────────────────┘     [+ features] only;
    ┌──────────────────┐  ┌──────────────────┐     boid_render duck-types
    │  help_overlay.py │  │  focal_debug.py  │     the boid, no boid.py
    └──────────────────┘  └──────────────────┘     import)
```

### 3D Stack (independent of 2D, shares only occlusion_geom + flock_core)

```
    ┌──────────────────┐     ┌──────────────────┐
    │  occlusion_geom  │     │   flock_core     │
    └────────┬─────────┘     └────────┬─────────┘
             │                        │
    ┌────────▼────────────────────────▼─────────┐
    │              spatial_3d.py                │
    │  SpatialGrid3D + both 3D flocking modes   │
    └────────────────────┬─────────────────────┘
                         │
    ┌────────────────────▼─────────────────────┐
    │              boid_3d.py                  │
    │  Boid3D — numpy Vec3 physics             │
    └────────────────────┬─────────────────────┘
                         │
    ┌────────────────────▼─────────────────────┐
    │            renderer_3d.py                │
    │  ModernGL buffers, uniforms, instanced   │
    │  draw calls, FBO capture — imports       │
    │  camera_3d (OrbitCamera) and shaders_3d  │
    │  (bird mesh + GLSL sources)              │
    └────────────────────┬─────────────────────┘
                         │
    ┌────────────────────▼─────────────────────┐
    │              main_3d.py                  │
    │  3D entry point — Pygame + ModernGL      │
    │  (imports scenario_presets for presets)  │
    └──────────────────────────────────────────┘

    ┌──────────────────────────────────────────┐
    │             capture_3d.py                │
    │  headless 3D entry point — renders via   │
    │  ModernGL FBO, assembles an animated     │
    │  GIF with Pillow (same stack as main_3d, │
    │  minus pygame, scenario_presets,         │
    │  and features)                           │
    └──────────────────────────────────────────┘

    ┌──────────────────┐
    │ scenario_presets │  (imported by both
    │  (imports        │   2D input_handler
    │   flock_core)    │   and 3D main_3d)
    └──────────────────┘
```

### Key dependency rules

| Rule | Reason |
|------|--------|
| No circular imports | Every module imports only "upstream" modules |
| `occlusion_geom.py` has zero project dependencies | Pure math — imported by both 2D and 3D stacks |
| `flock_core.py` also has zero project dependencies | Constants + Config shared by both stacks — a second root alongside `occlusion_geom` (stdlib imports only) |
| 3D modules use duck typing for boids | `spatial_3d.py` accesses `.pos`, `.vel`, `.apply_force()` without importing `boid_3d.py`; `metrics.py` duck-types the flock the same way |
| Entry points import the full stack | `alg2.py`, `main_3d.py`, and headless `capture_3d.py` import from every layer of their stack. Note: `capture_3d.py` does not import `features`, so it bypasses the `ENABLE_3D` guard |

---

## Feature Flag System

Feature flags live in [`features.py`](features.py). Set them *before* importing
any simulation module:

```python
import features
features.ENABLE_TRAILS = False
features.ENABLE_3D = True

from boid import Boid        # no trails
from main_3d import main     # 3D guard passes
```

### Active flags

| Flag | Default | Checked in | Effect when `False` |
|------|---------|-----------|---------------------|
| `ENABLE_PROJECTION_MODE` | `True` | `boid.py` (import guard, dispatch), `input_handler.py` (M key), `alg2.py` (initial mode) | `projection_model.py` never imported; dispatch falls back to spatial |
| `ENABLE_SPATIAL_MODE` | `True` | `boid.py` (import guard, dispatch), `input_handler.py` (M key), `alg2.py` (initial mode) | `spatial_model.py` never imported; dispatch falls back to projection. Disabling **both** models makes `import boid` raise `ImportError` |
| `ENABLE_TRAILS` | `False` | `boid.py` (update), `boid_render.py` (draw) | No position-history trail behind birds |
| `ENABLE_FOCAL_DEBUG` | `False` | `alg2.py` (import + render), `input_handler.py` (F key) | `focal_debug.py` never imported; F key does nothing |
| `ENABLE_GRID_OVERLAY` | `False` | `alg2.py` (render), `simulation.py` (grid rebuild), `input_handler.py` (G key) | G key does nothing; grid never rebuilt or drawn |
| `ENABLE_METRICS` | `True` | `alg2.py` + `simulation.py` (import guard, update, draw) | `metrics.py`/`external_opacity.py` never imported; no HUD panel; no CSV (rows contain metrics) |
| `ENABLE_PRESETS` | `True` | `input_handler.py` (import guard, preset keys) | `scenario_presets.py` never imported; preset keys do nothing |
| `ENABLE_HELP_OVERLAY` | `True` | `alg2.py` (import + render), `input_handler.py` (H key) | `help_overlay.py` never imported; H key does nothing |
| `ENABLE_3D` | `True` | `main_3d.py` (import guard) | `import main_3d` raises `ImportError` — 3D modules never loaded |
| `ENABLE_CSV_LOGGING` | `True` | `alg2.py` (file open), `simulation.py` (row writes) | No CSV file created; no rows written |
| `ENABLE_THREAT` | `True` | `alg2.py` (import + render), `simulation.py` (force), `input_handler.py` (T key) | T key does nothing; `extensions/threat.py` never imported |
| `ENABLE_WANDER` | `True` | `alg2.py` (import), `simulation.py` (force), `input_handler.py` (W key) | W key does nothing; `extensions/wander.py` never imported (force-only, no render) |
| `ENABLE_LEADER` | `True` | `alg2.py` (import + render), `simulation.py` (force), `input_handler.py` (O key) | O key does nothing; `extensions/leader.py` never imported |
| `ENABLE_VACUOLE` | `True` | `alg2.py` (import + render), `simulation.py` (force), `input_handler.py` (E key) | E key does nothing; `extensions/vacuole.py` never imported |
| `ENABLE_SHELL` | `True` | `alg2.py` (import + render), `simulation.py` (force), `input_handler.py` (P key) | P key does nothing; `extensions/shell_formation.py` never imported |
| `ENABLE_FLOW_FIELD` | `True` | `alg2.py` (import + render), `simulation.py` (force), `input_handler.py` (D key) | D key does nothing; `extensions/flow_field.py` never imported |
| `ENABLE_ADAPTIVE_QUALITY` | `False` | `simulation.py` (frame skip), `input_handler.py` (A key) | A key does nothing; dynamic quality never applied |
| `ENABLE_H2_ROBUSTNESS` | `False` | `input_handler.py` (J key) | J key does nothing; H₂ norm never computed |
| `ENABLE_SEASONAL` | `False` | `input_handler.py` (C key) | C key does nothing; seasonal day never advanced |
| `ENABLE_FLOCK_SHAPE` | `False` | `input_handler.py` (Y key) | Y key does nothing; flock shape never analysed |
| `ENABLE_MEDIUM_PRESETS` | `False` | `input_handler.py` (N key) | N key does nothing; medium presets never cycled |

### Complete flag declarations

For reference, here are the flag declarations from [`features.py`](features.py):

```python
# ── Flocking models  (affect boid.py — at least one must be True) ────

ENABLE_PROJECTION_MODE = True  # Pearce et al. (2014) hybrid projection model
ENABLE_SPATIAL_MODE    = True  # Reynolds (1987) boids, topological neighbours

# ── Visual features  (affect boid_render.py and alg2.py) ─────────────

ENABLE_TRAILS        = False   # position-history trail behind each boid
ENABLE_FOCAL_DEBUG   = False   # focal bird debug overlay (F key)
ENABLE_GRID_OVERLAY  = False   # spatial grid overlay (G key)

# ── Analysis & UI  (affect alg2.py, simulation.py, input_handler.py) ─

ENABLE_METRICS       = True    # FlockMetrics: Θ, Θ', α + HUD panel
ENABLE_PRESETS       = True    # scenario preset keys (1-0, s,l,i,v,k,q)
ENABLE_HELP_OVERLAY  = True    # H-key help overlay

# ── Simulation mode  (affects which entry point modules are loaded) ──

ENABLE_3D            = True    # 3D simulation (main_3d.py, renderer_3d.py,
                               #   spatial_3d.py, boid_3d.py)
                               #   Requires: moderngl, PyGLM, numpy

# ── Data output  (affects alg2.py, alg2.m, alg2.sce) ─────────────────

ENABLE_CSV_LOGGING   = True    # write metrics to CSV every N frames

# ── Extensions  (affect alg2.py, simulation.py, input_handler.py) ───

ENABLE_THREAT            = True    # predator agent (T key)
ENABLE_WANDER            = True    # random-walk perturbation (W key)
ENABLE_LEADER            = True    # attractor / leader system — sinusoidal
                                   #   Lissajous orbits (O key)
ENABLE_VACUOLE           = True    # vacuole cavity — orbiting repulsor that
                                   #   pushes birds outward (E key)
ENABLE_SHELL             = True    # shell formation / piloting — birds orbit
                                   #   leaders in concentric rings (P key)
ENABLE_FLOW_FIELD        = True    # environmental wind / drift field (D key)
ENABLE_ADAPTIVE_QUALITY  = False   # dynamic quality scaling (A key)
ENABLE_H2_ROBUSTNESS     = False   # H₂ robustness norm (J key)
ENABLE_SEASONAL          = False   # seasonal / ecological realism (C key)
ENABLE_FLOCK_SHAPE       = False   # flock shape analysis (Y key)
ENABLE_MEDIUM_PRESETS    = False   # medium preset cycling (N key)
```

A disabled feature's module is **never imported** — running
`import alg2` with `ENABLE_METRICS = False` leaves `metrics.py` and
`external_opacity.py` entirely out of `sys.modules`, so any subset of
features forms a working build (verified by `test_features.py`).

### Pattern for wiring a new flag

1. **Define the flag** in `features.py` with a clear docstring.
2. **Import `features`** in the module that should be gated.
3. **Check the flag** at the right point:
   - Visual features: check in the render loop (like `ENABLE_FOCAL_DEBUG`)
   - Import-time features: check before heavy imports (like `ENABLE_3D`)
   - Data features: check before I/O operations (like `ENABLE_CSV_LOGGING`)
4. **Default to safe/fast**: new flags should default to `False` unless they're essential for normal operation.

### Example: adding a hypothetical `ENABLE_PREDATOR` flag

```python
# 1. In features.py:
ENABLE_PREDATOR = False    # predator agent (WIP)

# 2. In a new predator.py:
import features

class Predator:
    ...

# 3. In simulation.py or alg2.py:
if features.ENABLE_PREDATOR:
    predator.update(flock)

# 4. In the entry point:
if features.ENABLE_PREDATOR:
    from predator import Predator
    predator = Predator()
```

---

## Configuration Knobs

### Constants (`flock_core.py`)

| Constant | Default | Meaning |
|----------|---------|---------|
| `WIDTH`, `HEIGHT` | 1000, 700 | 2D simulation area (pixels) |
| `FPS` | 60 | Target frame rate |
| `NUM_BOIDS` | 150 | Initial flock size |
| `BOID_SIZE` | 3 | Bird radius (paper: b = 1) |
| `V0` | 4 | Cruising speed |
| `MAX_FORCE` | 0.15 | Max steering force per frame |
| `VISUAL_RANGE` | 70 | Neighbour search radius (spatial mode) |
| `DEFAULT_PHI_P` | 0.03 | Default projection/separation weight |
| `DEFAULT_PHI_A` | 0.80 | Default alignment weight |
| `DEFAULT_SIGMA` | 4 | Default topological neighbour count |
| `MODE_PROJECTION`, `MODE_SPATIAL` | 0, 1 | Mode identifiers (also `MODE_NAMES` dict) |
| `MARGIN_BOUNDARY` | `False` | Use margin boundary instead of toroidal wrap |
| `BOUNDARY_MARGIN` | 200 | Distance from edge to start turning (margin) |
| `BOUNDARY_TURN_FACTOR` | 1 | Nudge strength toward centre (margin) |
| `LOG_FILE` | `"output/murmuration_metrics.csv"` | CSV output path. Set to `None` to skip file creation entirely. Also gated by `features.ENABLE_CSV_LOGGING`. |
| `LOG_EVERY` | 10 | Write CSV row every N frames |
| `TRAIL_LENGTH` | 50 | Max trail history positions |

### 3D-specific constants (`spatial_3d.py`)

| Constant | Default | Meaning |
|----------|---------|---------|
| `DEPTH` | 400 | Z-axis extent |
| `BOUNDARY_MARGIN_Z` | 120 | Z margin for boundary nudge |
| `MAX_VISIBILITY_RANGE` | 200 | Max distance for projection occlusion (performance) |
| `_CELL_SIZE_3D` | 80 | 3D spatial grid cell size |

### Runtime parameters (`Config` class in `flock_core.py`)

| Attribute | Type | Mutable via |
|-----------|------|-------------|
| `mode` | `int` (0 or 1) | `M` key, presets |
| `phi_p` | `float` 0–1 | `↑`/`↓` keys, presets |
| `phi_a` | `float` 0–1 | `←`/`→` keys, presets |
| `sigma` | `int` 1–50 | `[`/`]` keys, presets |
| `num_boids` | `int` | `+`/`-` keys |
| `show_grid` | `bool` | `G` key |
| `show_help` | `bool` | `H` key |
| `phi_n` | `float` (read-only) | Auto-computed: `1 − phi_p − phi_a` |

### Scenario presets (`scenario_presets.py`)

Two preset dictionaries with the same shape:
- `PRESETS` — 16 presets for 2D (keys 1–0, s,l,i,v,k,q)
- `PRESETS_3D` — 8 presets for 3D (keys a–f, h, w)

Each preset is a dict with keys: `label`, `phi_p`, `phi_a`, `sigma`, `mode`, `description`.

```python
# Example preset:
'a': {
    "label":      "PRESET a — 3D Pearce Default",
    "phi_p":      0.04,
    "phi_a":      0.80,
    "sigma":      6,
    "mode":       MODE_PROJECTION,
    "description": "Paper parameters adapted for 3D.",
}
```

To add a new preset, append an entry to `PRESETS` (2D) or `PRESETS_3D` (3D),
then wire the key into `input_handler.py` (2D) or `main_3d.py` (3D).

---

## How to Add a New Feature

### 1. Choose the layer

| Layer | Example module | When to use |
|-------|---------------|-------------|
| Pure math | `occlusion_geom.py` | Zero-dependency utility functions |
| Core data | `flock_core.py` | Constants, data classes, spatial grids |
| Algorithm | `projection_model.py`, `spatial_3d.py` | Flocking behaviour, steering forces |
| Agent | `boid.py`, `boid_3d.py` | Per-bird state and lifecycle |
| Metrics | `metrics.py`, `external_opacity.py` | Scientific measurements |
| Rendering | `boid_render.py`, `hud.py`, `help_overlay.py`, `focal_debug.py`, `renderer_3d.py` (+ `camera_3d.py`, `shaders_3d.py`) | Visual output |
| Orchestration | `alg2.py`, `main_3d.py`, `simulation.py` | Main loop, frame update |
| Input | `input_handler.py` | Keyboard/mouse → state changes |

### 2. Create the module

- Follow the existing file header convention (box-top comment with section number).
- Import only from upstream modules (see the dependency graph above).
- Use duck typing where possible to avoid circular imports.

### 3. Add a feature flag (optional)

If the feature should be toggleable:

```python
# In features.py:
ENABLE_MY_FEATURE = False

# In your new module:
import features
if features.ENABLE_MY_FEATURE:
    ...  # guarded code
```

### 4. Wire into the entry point

- **2D**: `alg2.py` → import the module, call it in the main loop.
- **3D**: `main_3d.py` → same pattern.

### 5. Add tests

Create `test_my_feature.py` using `unittest.TestCase`. Follow the existing convention
of using Mock objects (see `test_3d.py` for 3D-specific patterns, `test_projection_model.py`
for algorithm testing).

### 6. Update documentation

- Add to `README.md` (Step-by-Step Build Guide if it's a new iteration, or Code Tour).
- Add to `USER_GUIDE.md` (controls, tuning, troubleshooting, FAQ).
- Add to this file (dependency graph, feature flags, config knobs).

---

## Extension Architecture

Extensions are self-contained modules in `extensions/` that add optional
behaviours to the simulation. Each follows a consistent wiring pattern across
four files:

### Module structure

Every extension module exports **pure functions** (for testability) and an
optional agent class:

```
extensions/<name>.py
├── <Name>Config     dataclass — tunable parameters
├── <name>_force()   pure function — computes steering force per bird
├── draw_<name>()    renderer — draws the extension's visual overlay
└── <Name>Agent      (optional) stateful agent class
```

Example — `extensions/leader.py`:

```python
@dataclass
class LeaderConfig:
    anchor_count: int = 3
    attractor_radius: float = 120.0
    attractor_speed: float = 0.5
    attractor_range: float = 150.0
    chase_strength: float = 0.08

class LeaderAnchor:
    def __init__(self, cx=None, cy=None, config=None): ...
    def update(self, time): ...      # sinusoidal Lissajous orbit
    def position(self) -> tuple: ...

def attractor_force(bird_pos, anchor_pos, config): ...  # linear falloff
def leader_force(bird_pos, anchors, config): ...         # sum across anchors
def draw_anchors(screen, anchors, config=None): ...
```

### Wiring pattern

Each extension is wired into exactly four files:

| File | What's added |
|------|-------------|
| `features.py` | `ENABLE_<NAME>` flag (default `False` for heavy/unstable, `True` for stable) |
| `alg2.py` | Flag-gated import, `ext_state` initialisation, render call |
| `input_handler.py` | Key handler with local imports (avoids stale module-level imports) |
| `simulation.py` | Per-frame force application between `flock()` and `update()` |
| `help_overlay.py` | One-line help entry showing key + description |

Example — wiring `leader` into `alg2.py`:

```python
# Flag-gated import (top of file):
if features.ENABLE_LEADER:
    from extensions.leader import LeaderAnchor, LeaderConfig, draw_anchors

# ext_state init:
if features.ENABLE_LEADER:
    ext_state['leader_active'] = False
    ext_state['leader_cfg'] = LeaderConfig()
    ext_state['leader_time'] = 0.0
    ext_state['leader_anchors'] = []

# Render:
if ext_state.get('leader_active'):
    draw_anchors(screen, ext_state.get('leader_anchors', []))
```

### Key assignment rules

- Keys must **not conflict** with preset keys (1–0, s, l, i, v, k, q in 2D).
- Handler uses **local imports** inside the key-press branch — never rely on
  module-level conditional imports (they become stale if the flag changes).

### Current extension modules

| Module | Key | Flag | Default | Description |
|--------|-----|------|---------|-------------|
| `threat.py` | `T` | `ENABLE_THREAT` | `True` | Predator agent that chases the flock |
| `wander.py` | `W` | `ENABLE_WANDER` | `True` | Random-walk perturbation per bird |
| `leader.py` | `O` | `ENABLE_LEADER` | `True` | Sinusoidal Lissajous anchor orbits — birds are attracted toward anchors |
| `vacuole.py` | `E` | `ENABLE_VACUOLE` | `True` | Orbiting repulsor that pushes birds radially outward, creating a cavity |
| `shell_formation.py` | `P` | `ENABLE_SHELL` | `True` | Birds orbit anchor points in concentric geometric shells |
| `flow_field.py` | `D` | `ENABLE_FLOW_FIELD` | `True` | Environmental wind / drift field, gusts, wandering direction |
| `adaptive_quality.py` | `A` | `ENABLE_ADAPTIVE_QUALITY` | `False` | Dynamic frame-skip / quality scaling |
| `h2_robustness.py` | `J` | `ENABLE_H2_ROBUSTNESS` | `False` | H₂ robustness norm computation |
| `seasonal.py` | `C` | `ENABLE_SEASONAL` | `False` | Seasonal / ecological realism (day-length, temperature) |
| `flock_shape.py` | `Y` | `ENABLE_FLOCK_SHAPE` | `False` | Flock shape analysis |
| `medium_presets.py` | `N` | `ENABLE_MEDIUM_PRESETS` | `False` | Medium preset cycling (grid → air → water → vacuum) |

### Tests

All extension unit tests live in `extensions/test_extensions.py`, organised as
one `TestCase` class per module (e.g., `TestLeaderAnchor`, `TestVacuoleAgent`,
`TestShellFormation`). Key-handler tests for extension toggles are in
`test_input_handler.py` under `TestExtensionToggles`.

---

## Test Structure

| File | Tests what | Dependencies |
|------|-----------|-------------|
| `test_occlusion.py` | Angular interval math (`occlusion_geom.py`) | None |
| `test_boundary.py` | Toroidal wrap, margin boundary | `flock_core` |
| `test_presets.py` | Preset application + toggle logic | `flock_core`, `scenario_presets` |
| `test_alg2.py` | Integration / occlusion geometry | `occlusion_geom`, `flock_core` |
| `test_cross_language.py` | Cross-language output consistency | None |
| `test_projection_model.py` | `projection_model.py` functions | `occlusion_geom`, `flock_core` |
| `test_spatial_model.py` | `spatial_model.py` functions | `flock_core` |
| `test_input_handler.py` | `input_handler.py` event processing | `pygame`, `flock_core` |
| `test_features.py` | Feature flag gating (`features.py`) | `features`, `flock_core` |
| `test_3d.py` | 3D physics, grid, flocking (39 tests) | `boid_3d`, `spatial_3d`, `flock_core` |
| `test_count_mixin.py` | *(helper, contributes no tests)* — shared `TestCountMixin` for the per-module test-count discovery gates | None |
| `extensions/test_extensions.py` | Extension modules (190 tests) — leader, vacuole, shell formation, flow field, wander, threat, adaptive quality, H₂, seasonal, flock shape, medium presets, predator, steric, blind angles, 3D, anisotropic, spatial opt, direct velocity, multi-viewpoint, correlation time | Various |

Run all tests:

```bash
python3 -m unittest discover -p "test_*.py"
```

---

## Entry Points

| Command | File | Stack | Requires |
|---------|------|-------|----------|
| `python alg2.py` | `alg2.py` | 2D | `pygame` |
| `python main_3d.py` | `main_3d.py` | 3D | `pygame`, `moderngl`, `PyGLM`, `numpy` |
| `python alg_simple.py` | `alg_simple.py` | Minimal | `pygame` |
| `python capture_3d.py` | `capture_3d.py` | 3D headless | `moderngl`, `PyGLM`, `numpy`, `Pillow` |
| `octave alg2.m` | `alg2.m` | 2D (Octave) | GNU Octave 4.0+ |
| `scilab -f alg2.sce` | `alg2.sce` | 2D (Scilab) | Scilab 6.0+ |
