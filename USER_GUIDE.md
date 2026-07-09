# Murmuration — User Guide

Practical setup and usage for the **3D** murmuration simulation. For the science
and the 3D maths, see [`sci.md`](sci.md); for the build walk-through, see the
[3D Simulation Build Guide](README.md#3d-simulation-build-guide) in the README.

The simulation runs birds in a full 3D volume (1000 × 700 × 400) with
GPU-accelerated rendering via ModernGL; the camera orbits freely around the
flock.

![3D murmuration demo](murmuration_3d.gif)

---

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Running the Simulation](#running-the-simulation)
- [Controls Reference](#controls-reference)
- [Preset Scenarios](#preset-scenarios)
- [Tuning Guide](#tuning-guide)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

---

## Requirements

| Component | Minimum | Notes |
|-----------|---------|-------|
| **Python** | 3.7+ | 3.9+ recommended; tested on 3.9–3.12 |
| **Pygame** | 2.0+ | Window and event handling only |
| **ModernGL** | 5.0+ | GPU rendering backend; 5.12+ recommended for macOS Metal support |
| **PyGLM** | 2.0+ | Matrix math — `lookAt`, `perspective`, `vec3` |
| **NumPy** | 1.20+ | Vector math and GPU buffer packing |
| **SciPy** | 1.7+ | `cKDTree` / `ConvexHull` for the science modules |
| **Pillow** | 9.0+ | Optional — only for `capture_3d.py` GIF generation |
| **GPU** | OpenGL 3.3 capable | Integrated GPU is fine; on macOS, Metal-backed via ModernGL |
| **RAM** | ~200 MB | Grows with instance count (6 floats × N birds) |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/tralev/murmuration.git
cd murmuration
```

### 2. Set up a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# or:
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
# or explicitly:
pip install pygame moderngl PyGLM numpy scipy
```

Optional (for GIF capture):

```bash
pip install Pillow
```

### 4. Verify

```bash
python3 -c "import moderngl; print('ModernGL', moderngl.__version__)"
python3 -c "import glm; print('PyGLM', glm.__version__)"
```

Note: the package is `PyGLM` but the import is `import glm`.

---

## Running the Simulation

```bash
python main_3d.py
```

A 1200 × 800 window opens showing 150 birds in a 3D volume with a perspective
camera. The window title bar shows the current mode, bird count, parameter
values, live metrics, and FPS.

**Startup output:**

```
Murmuration 3D — 150 birds
Mode: PROJECTION
Press M to toggle mode | Space to pause | ESC to quit
Mouse drag to orbit | Scroll to zoom
T: predator | K: roosting cycle | U: SI refinements (on)
```

**Quick configuration:** edit the constants near the top of `flock_core.py`
(model) and `main_3d.py` (window / FPS):

```python
NUM_BOIDS      = 150      # flock size          (flock_core.py)
BOID_SIZE      = 9        # effective body radius b for occlusion (flock_core.py)
FPS            = 60       # target frame rate   (main_3d.py)
WINDOW_WIDTH   = 1200     # window dimensions   (main_3d.py)
WINDOW_HEIGHT  = 800
```

**Capturing a GIF:**

```bash
pip install Pillow
python capture_3d.py
# → murmuration_3d.gif
```

---

## Controls Reference

### Simulation controls

| Key | Action |
|-----|--------|
| `SPACE` | Pause / resume |
| `R` | Reset flock — randomise positions and velocities in 3D |
| `M` | Toggle **PROJECTION** ↔ **SPATIAL** mode |
| `U` | Toggle Pearce SI refinements (steric + blind cone + anisotropic bodies) |
| `T` | Spawn / remove a predator (Goodenough flight response) |
| `K` | Toggle the dusk roosting cycle (day-length + roost descent) |
| `ESC` | Quit |

### Camera controls

| Input | Action |
|-------|--------|
| **Click + drag** | Orbit camera (azimuth + elevation) |
| **Scroll up / down** | Zoom in / out |
| `O` | Toggle **auto-rotate** — slow automatic orbit for unattended demos |
| `V` | **Reset camera** — snap back to the default view |

The camera orbits the centre of the volume (500, 350, 200). Elevation is clamped
to ±89° to prevent gimbal lock. `R` resets the **flock**, not the camera — use
`V` to reset the view.

### Parameter tuning

| Key | Parameter | Range | Step |
|-----|-----------|-------|------|
| `↑` / `↓` | φp (projection) | 0.0 – 1.0 | ±0.01 |
| `←` / `→` | φa (alignment) | 0.0 – 1.0 | ±0.01 |
| `[` / `]` | σ (aligned neighbours) | 1 – 20 | ±1 |

### Flock size & display

| Key | Action |
|-----|--------|
| `+` / `=` | Add 10 birds |
| `-` | Remove 10 birds (leaves at least 1) |
| `G` | Toggle reference grid overlay (XY plane at z=0) |

---

## Preset Scenarios

Eight presets tuned for the 3D volume — press the letter key to apply instantly.

### PROJECTION mode presets (Pearce hybrid projection)

| Key | Preset | φp | φa | σ | Visual character |
|-----|--------|----|----|---|------------------|
| `a` | 3D Pearce Default | 0.04 | 0.80 | 6 | Marginal opacity in the 3D volume |
| `b` | Ball of Birds | 0.18 | 0.70 | 7 | Dense 3D sphere |
| `c` | Storm Cloud | 0.06 | 0.45 | 3 | Dispersed through the full volume |
| `e` | Vertical Column | 0.10 | 0.75 | 6 | Layered, pancake-shaped flock |
| `f` | 3D Acro | 0.02 | 0.85 | 3 | Rapid 3D turns, light cohesion |

### SPATIAL mode presets (Reynolds steering in 3D)

| Key | Preset | φp | φa | σ | Visual character |
|-----|--------|----|----|---|------------------|
| `d` | 3D Stream | 0.25 | 0.55 | 8 | Directional 3D school |
| `w` | Spiral Vortex | 0.08 | 0.82 | 10 | Rotating 3D vortex |
| `h` | 3D Void | 0.35 | 0.58 | 9 | Maximum separation, cavity voids |

#### Quick 3D tour (60 seconds)

1. Start with `a` (3D Pearce Default) from the default camera angle.
2. Press `w` (Spiral Vortex) — SPATIAL mode forms a rotating vortex.
3. Drag the mouse to orbit around it.
4. Press `b` (Ball of Birds) — the flock collapses into a dense sphere.
5. Scroll to zoom in, then `c` (Storm Cloud) — birds disperse.
6. Press `a` to return to the default.

---

## Tuning Guide

### The two flocking modes

**PROJECTION mode** — the Pearce et al. (2014) hybrid projection model in true
3D. Each neighbour subtends a **spherical cap** on the observer's view sphere
(`occlusion_3d.py`); the projection direction δ̂ is the resolved light–dark
boundary and the internal opacity Θ is the union of the caps. Cohesion in all
three axes falls out of the 3D geometry — there is no separate "altitude" term.
With the SI refinements on (`U`), each bird also has a rear blind cone, an
anisotropic (prolate) body, and short-range steric repulsion.

**SPATIAL mode** — topological Reynolds boids in full 3D: separation, alignment
and cohesion over the σ nearest neighbours found via a 27-cell spatial hash,
with toroidal wrap in X, Y and Z.

### Getting a dense 3D flock

| Parameter | Value | Why |
|-----------|-------|-----|
| φp | 0.04 – 0.12 | Moderate projection cohesion without over-compacting |
| φa | 0.75 – 0.85 | High alignment for smooth, coordinated motion |
| σ | 5 – 7 | More neighbours maintain connectivity in the large volume |

### Getting an exploratory 3D flock

| Parameter | Value | Why |
|-----------|-------|-----|
| φp | 0.02 – 0.05 | Light projection lets birds spread through the volume |
| φa | 0.40 – 0.55 | Lower alignment = more individual variation |
| σ | 2 – 4 | Fewer neighbours = weaker social coupling |

---

## Performance

Rough estimates on a modern integrated GPU (Apple M1 / Intel Iris); hardware
varies.

| Birds | PROJECTION FPS | SPATIAL FPS | Bottleneck |
|-------|---------------|-------------|------------|
| 150 | ~55–60 | ~60 | None |
| 500 | ~40–50 | ~55–60 | Per-bird occlusion sort (O(K log K)) |
| 2000 | ~15–25 | ~45–55 | CPU flocking dominates; GPU rendering still fast |
| 5000 | ~5–10 | ~30–40 | PROJECTION occlusion sort cost grows |

**Tips for large flocks:**
- Use SPATIAL mode — it scales O(N) vs PROJECTION's O(N × K log K).
- Reduce `MAX_VISIBILITY_RANGE` in `spatial_3d.py` (default 200) to limit
  occlusion candidates.
- GPU instanced rendering draws all birds in one call; CPU flocking is the
  bottleneck.

---

## Troubleshooting

#### "No module named 'moderngl'" / "'glm'"

```bash
pip install moderngl PyGLM
```

The `glm` import comes from the `PyGLM` package.

#### "Failed creating OpenGL context at version requested"

Your GPU or driver doesn't support OpenGL 3.3. On macOS this usually means
ModernGL's Metal backend isn't working — `pip install --upgrade moderngl`
(5.12+ has improved Metal support).

#### Black window, nothing renders

- Verify the Pygame window is created with `DOUBLEBUF | OPENGL`.
- Upgrade ModernGL to 5.12+.
- On Linux, install Mesa GPU drivers.

#### Very low FPS

- Reduce `NUM_BOIDS` in `flock_core.py`.
- Switch to SPATIAL mode (`M`) — it scales much better than PROJECTION.

#### Camera spins uncontrollably

The orbit camera uses relative mouse motion; a cursor leaving and re-entering
the window can report a large delta. Drag more gently — elevation is clamped to
±89°.

#### Headless operation

ModernGL may not work through `xvfb` depending on GPU drivers. Use
`capture_3d.py` for headless GIF generation instead of `main_3d.py`.

---

## FAQ

#### Why ModernGL instead of PyOpenGL?

On macOS, Apple deprecated OpenGL in favour of Metal. PyOpenGL can only create
legacy 2.1 contexts, which lack the GLSL 3.30 shaders, VAOs, and instanced
rendering needed here. ModernGL wraps Metal and exposes a modern GL 3.3+ API, so
instanced rendering works on macOS without code changes.

#### Can I run without a GPU?

No — ModernGL requires a GPU with OpenGL 3.3 support. Integrated GPUs (Intel,
Apple M-series) work fine; software rendering (LLVMpipe) is unusably slow.

#### How many birds can it handle?

- **PROJECTION**: ~2000 birds at 20+ FPS (bottleneck: per-bird occlusion sort).
- **SPATIAL**: ~5000 birds at 30+ FPS (bottleneck: CPU flocking, not rendering).
- GPU instanced rendering draws all birds in one call regardless of count.

#### Can I capture screenshots or video?

Use `capture_3d.py` for headless GIF generation. For video, screen-record
(OBS, QuickTime) while the sim runs, or modify `capture_3d.py` to save PNG
frames and assemble them with ffmpeg.
