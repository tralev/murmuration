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
                    ┌──────────────────┐
                    │  occlusion_geom  │  pure math — angular intervals
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   flock_core     │  constants, Config, SpatialGrid
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────▼────────┐    │    ┌─────────▼─────────┐
    │  projection_model │    │    │   spatial_model   │
    └─────────┬────────┘    │    └─────────┬─────────┘
              │              │              │
    ┌─────────▼────────┐    │              │
    │      boid.py     │◄───┘──────────────┘
    └─────────┬────────┘
              │
    ┌─────────▼────────┐
    │    metrics.py    │────────────── external_opacity.py
    └─────────┬────────┘
              │
    ┌─────────▼────────┐     ┌──────────────────┐
    │    alg2.py       │────▶│  input_handler   │
    │  (2D entry point)│     │  (imports boid,   │
    └──────────────────┘     │   flock_core,      │
                             │   scenario_presets)│
                             └──────────────────┘
                             ┌──────────────────┐
                             │  simulation.py   │
                             │  (imports boid,   │
                             │   metrics,        │
                             │   flock_core)     │
                             └──────────────────┘
                             ┌──────────────────┐
                             │  help_overlay.py │
                             └──────────────────┘
                             ┌──────────────────┐
                             │  focal_debug.py  │
                             └──────────────────┘
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
    │  ModernGL instanced rendering, GLSL      │
    │  shaders, OrbitCamera, FBO capture       │
    └────────────────────┬─────────────────────┘
                         │
    ┌────────────────────▼─────────────────────┐
    │              main_3d.py                  │
    │  3D entry point — Pygame + ModernGL      │
    │  (imports scenario_presets for presets)  │
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
| `flock_core.py` depends only on `occlusion_geom` | Constants + Config shared by both stacks |
| 3D modules use duck typing for boids | `spatial_3d.py` accesses `.pos`, `.vel`, `.apply_force()` without importing `boid_3d.py` |
| Entry points import the full stack | `alg2.py` and `main_3d.py` are the only modules that import from every layer |

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
| `ENABLE_TRAILS` | `False` | `boid.py` (draw, update) | No position-history trail behind birds |
| `ENABLE_FOCAL_DEBUG` | `False` | `alg2.py` (render), `input_handler.py` (F key) | F key does nothing; no debug overlay |
| `ENABLE_GRID_OVERLAY` | `False` | `alg2.py` (render), `simulation.py` (grid rebuild), `input_handler.py` (G key) | G key does nothing; grid never rebuilt or drawn |
| `ENABLE_3D` | `True` | `main_3d.py` (import guard) | `import main_3d` raises `ImportError` — 3D modules never loaded |
| `ENABLE_CSV_LOGGING` | `True` | `alg2.py` (file open), `simulation.py` (row writes) | No CSV file created; no rows written |

### Complete flag declarations

For reference, here is the full content of [`features.py`](features.py):

```python
# ── Visual features  (affect boid.py and alg2.py) ────────────────────

ENABLE_TRAILS        = False   # position-history trail behind each boid
ENABLE_FOCAL_DEBUG   = False   # focal bird debug overlay (F key)
ENABLE_GRID_OVERLAY  = False   # spatial grid overlay (G key)

# ── Simulation mode  (affects which entry point modules are loaded) ──

ENABLE_3D            = True    # 3D simulation (main_3d.py, renderer_3d.py,
                               #   spatial_3d.py, boid_3d.py)
                               #   Requires: moderngl, PyGLM, numpy

# ── Data output  (affects alg2.py, alg2.m, alg2.sce) ─────────────────

ENABLE_CSV_LOGGING   = True    # write metrics to CSV every N frames
```

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
| Rendering | `help_overlay.py`, `focal_debug.py`, `renderer_3d.py` | Visual output |
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
| `test_3d.py` | 3D physics, grid, flocking (39 tests) | `boid_3d`, `spatial_3d`, `flock_core` |
| `extensions/test_extensions.py` | Extension modules | Various |

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
