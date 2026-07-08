# Murmuration — User Guide

Practical setup and usage instructions. For the science behind the simulation, see [`README.md`](README.md).

---

## 🎓 Start Here — For Students

If you're new to this codebase, **don't open `alg2.py` first**. It imports from 5 modules and implements two complex flocking algorithms. Start with the minimal version instead:

```bash
python alg_simple.py
```

`alg_simple.py` is ~75 lines, one file, zero external imports (besides Pygame). It implements classic Reynolds boids — separation, alignment, cohesion — and you can read the entire thing in 5 minutes. Run it, watch the flock, then tweak the numbers at the top (`N`, `V0`, `R`, `F`) to see what changes.

Steps 1–6 cover the 2D codebase; steps 7–10 cover the GPU-accelerated 3D extension.

**Suggested learning path:**

| Step | File | What you learn |
|------|------|----------------|
| 1 | `alg_simple.py` | Basic boids — how 3 simple rules create complex flocking |
| 2 | `occlusion_geom.py` | How angular intervals work — pure math, no Pygame |
| 3 | `flock_core.py` | Constants, Config, and the spatial hash grid |
| 4 | `boid.py` | The full Boid class — both projection and spatial modes |
| 5 | `metrics.py` | Scientific metrics, external opacity, help overlay |
| 6 | `alg2.py` | The 2D main loop — ties everything together |
| 7 | `spatial_3d.py` | **3D** spatial grid with 27-cell queries + 3D flocking modes |
| 8 | `boid_3d.py` | **3D** bird agent — numpy Vec3 physics, Euler integration |
| 9 | `renderer_3d.py` | **3D** ModernGL GPU instanced rendering, GLSL shaders, orbit camera |
| 10 | `main_3d.py` | **3D** main loop — Pygame window + ModernGL rendering |

After that, read [`README.md`](README.md) for the scientific background and the implementation audit.

The [3D Simulation](#3d-simulation) section below covers the GPU-accelerated 3D version built with ModernGL.

---

## Table of Contents

- [Start Here — For Students](#-start-here--for-students)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running the Simulation](#running-the-simulation)
- [Controls Reference](#controls-reference)
- [CSV Output](#csv-output)
- [Tuning Guide](#tuning-guide)
- [Docker](#running-with-docker)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
  - [How do I use Docker?](#how-do-i-use-docker)
- [3D Simulation](#3d-simulation)
  - [3D Requirements](#3d-requirements)
  - [3D Installation](#3d-installation)
  - [Running the 3D Simulation](#running-the-3d-simulation)
  - [3D Controls Reference](#3d-controls-reference)
  - [3D Preset Scenarios](#3d-preset-scenarios)
  - [3D Tuning Guide](#3d-tuning-guide)
  - [3D Troubleshooting](#3d-troubleshooting)
  - [3D FAQ](#3d-faq)

---

## Requirements

| Component | Minimum | Notes |
|-----------|---------|-------|
| **Python** | 3.7+ | 3.9+ recommended; tested on 3.9–3.12 |
| **Pygame** | 2.0+ | 2.1+ recommended for `SCALED` display support |
| **OS** | macOS, Linux, Windows | No platform-specific code |
| **Display** | 1000 × 700 px minimum | Window is fixed-size; can work headless with a virtual framebuffer (`xvfb-run`) |
| **RAM** | ~100 MB | Grows linearly with flock size |
| **Disk** | < 1 MB for code; CSV log grows ~1 KB per 100 frames at default N=150 |

No GPU, CUDA, or other specialised hardware is required. The simulation runs entirely on CPU.

---

## Installation

### 1. Clone or download the repository

```bash
git clone https://github.com/tralev/murmuration.git
cd murmuration
```

Or download and extract the ZIP from GitHub.

### 2. Set up a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# or:
venv\Scripts\activate           # Windows
```

### 3. Install Pygame

```bash
pip install pygame
```

That's the **only dependency**. The simulation uses only Python standard library modules (`math`, `random`, `sys`, `collections`) plus Pygame for graphics and input.

### 4. Verify

```bash
python3 -c "import pygame; print('pygame', pygame.version.ver)"
```

Should print something like `pygame 2.6.1`.

---

## Running the Simulation

### Python (Recommended)

```bash
python alg2.py
```

A window opens (1000 × 700 pixels) showing a flock of 150 birds in projection mode.

### GNU Octave

```bash
octave alg2.m
```

**Requirements:** GNU Octave 4.0 or later. A figure window opens — close it to stop the simulation.

Performance in Octave is lower than Python due to interpreted linear algebra in the projection-mode loop. Expect ~10–20 FPS at N=100. Reduce `NUM_BOIDS` at the top of `alg2.m` if the simulation is too slow.

### Scilab

From the Scilab console:

```scilab
exec("alg2.sce");
```

Or from the command line:

```bash
scilab -f alg2.sce
```

**Requirements:** Scilab 6.0 or later. No additional toolboxes needed.

Scilab's event loop requires `sleep(1)` (1 ms) before `drawnow()` to process keyboard input. If keyboard controls feel unresponsive, increase the sleep duration slightly near line 615 of `alg2.sce`.

### Command-line options (Python)

There are no command-line flags. All configuration is done by editing the constants at the top of `alg2.py` or via keyboard controls at runtime.

### Quick configuration changes (Python — edit `alg2.py`, lines ~60–75)

```python
NUM_BOIDS      = 150      # flock size (higher = slower)
V0             = 4        # bird speed (higher = faster flock)
VISUAL_RANGE   = 70       # neighbour search radius (spatial mode)
FPS            = 60       # target frame rate
LOG_FILE       = "output/murmuration_metrics.csv"   # set to None to disable CSV
LOG_EVERY      = 10       # write CSV every N frames
```

### Running on a headless server (Python)

Use `xvfb-run` (Linux) to create a virtual display:

```bash
xvfb-run -a python alg2.py
```

The simulation will run without a visible window. Useful for batch data collection or automated testing.

### Running with Docker

No Python or Pygame installation needed — just Docker:

```bash
./run-docker.sh              # full simulation (headless)
./run-docker.sh tests        # run unit tests in container
./run-docker.sh shell        # open bash shell in container
./run-docker.sh octave       # open GNU Octave interactive CLI
./run-docker.sh scilab       # open Scilab interactive CLI
./run-docker.sh validate-all # full multi-stage validation pipeline
./run-docker.sh stop         # clean up container and image
```

Or use docker compose directly:

```bash
docker compose up                  # run simulation
docker compose run tests           # run unit tests
docker compose run shell           # interactive shell
docker compose run octave          # GNU Octave CLI
docker compose run scilab          # Scilab CLI
```

### Running unit tests (Python)

```bash
python3 -m unittest test_alg2 -v
python3 -m unittest extensions.test_extensions -v
```

600 tests covering occlusion geometry, all 16 presets, preset toggle behaviour, letter-key presets, feature-flag gating, the 3D stack, and the full extensions suite (predator, wander, threat, adaptive quality, H₂ robustness, seasonal, flock shape, inertia, blob init, roosting, critical mass, themes, pilot state, and more). No display needed — Pygame is mocked. Run the full validation pipeline with `./scripts/validate-all.sh` or `./run-docker.sh validate-all`.

---

## Controls Reference

### Simulation controls

| Key | Action |
|-----|--------|
| `SPACE` | Pause / resume |
| `R` | Reset flock — randomise positions, zero metrics, restart frame counter |
| `ESC` | Quit |

### Mode switching

| Key | Action |
|-----|--------|
| `M` | Toggle **PROJECTION** ↔ **SPATIAL** mode |
| `B` | Toggle **TOROIDAL** ↔ **MARGIN** boundary |

- **PROJECTION** (default) — birds steer toward light-dark boundaries in their view; produces dense, cohesive flocks
- **SPATIAL** — classic separation/alignment/cohesion boids; produces looser, school-like formations
- **TOROIDAL** (default) — birds wrap around edges (exit right → enter left); infinite-feeling space
- **MARGIN** — birds nudge away from edges and hard-clamp within bounds; contained arena

### Parameter tuning (live)

| Key | Parameter | Range | Step | Effect |
|-----|-----------|-------|------|--------|
| `↑` / `↓` | φp | 0.0 – 1.0 | ±0.01 | Projection / separation weight |
| `←` / `→` | φa | 0.0 – 1.0 | ±0.01 | Alignment weight |
| `[` / `]` | σ | 1 – 50 | ±1 | Nearest-neighbour count |

φn (noise/cohesion weight) is always `1 − φp − φa` and updates automatically.

### Flock size

| Key | Action |
|-----|--------|
| `+` / `=` | Add 10 birds (capped at 200 pending) |
| `-` | Remove 10 birds (leaves at least 1) |

### Extension toggles

Enable/disable individual extensions via the flags in `features.py`.
The table below shows which are active by default.

| Key | Extension | Effect | Default |
|-----|-----------|--------|---------|
| `T` | Threat agent | Spawn / remove predator that chases the flock | On |
| `W` | Wander behaviour | Toggle random-walk perturbation per bird | On |
| `O` | Leader / attractor | Toggle sinusoidal Lissajous anchor orbits | On |
| `E` | Vacuole cavity | Spawn / remove orbiting repulsor (creates empty space) | On |
| `P` | Shell formation | Toggle birds orbiting in concentric geometric shells | On |
| `D` | Flow field | Toggle environmental wind with gusts and drift | On |
| `A` | Adaptive quality | Toggle dynamic frame-skip | Off |
| `N` | Medium presets | Cycle ambient medium (air, dust, starlight, grid) | Off |
| `J` | H₂ robustness | Compute consensus robustness norm (Young et al. 2013) | Off |
| `C` | Seasonal | Advance seasonal day (+30) | Off |
| `Y` | Flock shape | PCA aspect ratio and shape analysis | Off |

Changes take effect on the **next unpaused frame**.

#### Programmatic extension modules (no key — used from code)

Some extensions are pure library helpers rather than interactive toggles.
They live in `extensions/` and are imported directly (see `extensions/__init__.py`
for the full export list) — useful for analysis, custom initialisation, or the
extended simulation:

| Module | What it provides |
|--------|-----------------|
| `inertia.py` | `blend_inertia()` — smooth velocity toward desired (momentum, default 0.84) |
| `blob_init.py` | `blob_positions()` — 5-centre spherical blob start layout (2D & 3D) |
| `roosting.py` | `roost_force()` / `dusk_factor()` — dusk-gated roost attractor |
| `critical_mass.py` | `coherence_factor()` — ~500-bird murmuration-onset gate |
| `themes.py` | `THEMES`, `get_theme()`, `cycle_theme()` — colour schemes |
| `pilot_state.py` | `SimulationPilot` — flock heading, radius, bank-roll, medium pulse |
| `h2_robustness.py` | `h2_norm()`, `cost_optimal_m()` — Young et al. consensus robustness |

### Preset scenarios (16 total)

Press any preset key to apply it. Press the **same key again** to toggle back
to your previous settings (including mode, weights, and neighbour count).

| Keys | Presets |
|------|---------|
| `1` – `5` | Original educational presets (Pure Alignment, Gas, Pearce Default, Dense Ball, Classic Boids) |
| `6` – `0` | Companion presets (Quiet Roost, Comfort Flight, Acro Swarm, Predator Ripple, Storm Turn) |
| `s`, `l`, `i`, `v`, `k`, `q` | Letter-key presets (Swarm Pilot, Lava Lamp, Ink Cloud, Vacuole, Silk Sheet, Quest 2 Dense) |

### Display toggles

| Key | Action |
|-----|--------|
| `F` | Toggle focal bird debug view — highlights one bird and draws its occlusion intervals |
| `G` | Toggle spatial grid overlay (SPATIAL mode only) — shows cell boundaries and occupancy counts |
| `H` | Toggle help overlay — top-right panel listing all controls |

### On-screen display

- **Top-left**: FPS, boid count, current mode, φp/φa/φn/σ values, opacity metrics
- **Top-right**: Mode badge (PROJECTION or SPATIAL), boundary badge (TOROIDAL or MARGIN), plus help panel (when toggled)
- **Bottom-centre**: Pause indicator when paused
- **Bird colour**: cool blue-white in PROJECTION mode, warm amber in SPATIAL mode

---

## CSV Output

When `LOG_FILE` is set (default: `output/murmuration_metrics.csv`), a row is written every `LOG_EVERY` frames:

```csv
frame,mode,num_boids,phi_p,phi_a,phi_n,sigma,theta,theta_ext,alpha,fps
0,0,150,0.0300,0.8000,0.1700,4,0.0123,0.0008,0.0341,59.2
10,0,150,0.0300,0.8000,0.1700,4,0.0234,0.0012,0.0892,60.1
```

| Column | Meaning |
|--------|---------|
| `frame` | Frame number (resets to 0 on flock reset) |
| `mode` | 0 = PROJECTION, 1 = SPATIAL |
| `num_boids` | Current flock size |
| `phi_p`, `phi_a`, `phi_n` | Model weights (sum to 1) |
| `sigma` | Neighbour count |
| `theta` | Internal opacity (0–1) |
| `theta_ext` | External opacity (0–1) |
| `alpha` | Order parameter — flock alignment (0 = chaotic, 1 = perfect) |
| `fps` | Instantaneous frames per second |

The file is **flushed after every write** — data is safe even if the simulation crashes or is killed. The file is closed cleanly on normal exit (`ESC`).

### Disabling CSV logging

Set `LOG_FILE = None` near the top of `flock_core.py`. No file will be created and no disk I/O will occur.

### Loading CSV data

```python
import pandas as pd
df = pd.read_csv("murmuration_metrics.csv")
df.plot(x="frame", y="theta")
```

Or in any spreadsheet: File → Import → CSV.

---

## Tuning Guide

### Getting a dense, cohesive flock

| Parameter | Value | Why |
|-----------|-------|-----|
| φp | 0.03 – 0.10 | Low projection weight keeps the flock together without over-compacting |
| φa | 0.70 – 0.85 | High alignment produces smooth, coordinated motion |
| σ | 3 – 6 | More neighbours = stronger alignment, tighter flock |

Default values (φp=0.03, φa=0.80, σ=4) produce a dense, cohesive flock with good outward visibility.

### Getting a loose, school-like flock

| Parameter | Value | Why |
|-----------|-------|-----|
| φp | 0.10 – 0.20 | Higher projection weight spreads birds apart |
| φa | 0.50 – 0.70 | Lower alignment allows more individual variation |
| σ | 2 – 3 | Fewer neighbours = weaker social forces |

### Preset exploration — try these to see different flock behaviors

Instead of tuning parameters manually, press a preset key to instantly switch.
Press the **same key again** to toggle back to your previous settings.

#### 🔵 PROJECTION mode presets (dense, murmuration-like)

| Key | Preset | φp | φa | σ | Visual character |
|-----|--------|----|----|---|------------------|
| `3` | Pearce Default | 0.03 | 0.80 | 4 | Canonical bird-flock — marginal opacity emerges naturally |
| `4` | Dense Ball | 0.15 | 0.70 | 6 | Near-opaque, slow-turning, hypnotic pulsing |
| `6` | Quiet Roost | 0.08 | 0.82 | 8 | Settled, calm, trail-heavy — like birds at dusk |
| `7` | Comfort Flight | 0.04 | 0.88 | 5 | Smooth gliding, gentle curves, minimal jitter |
| `8` | Acro Swarm | 0.02 | 0.85 | 3 | Fast turns, acrobatic, tightly coupled |
| `s` | Swarm Pilot | 0.05 | 0.85 | 6 | Balanced, controlled flight with crisp turns |
| `l` | Lava Lamp | 0.12 | 0.65 | 7 | Blobby, slow, fluid — organic pulsing shapes |
| `i` | Ink Cloud | 0.02 | 0.40 | 2 | Spreading, diffusing — high noise, low alignment |
| `k` | Silk Sheet | 0.02 | 0.92 | 6 | Near-perfect alignment — thin, smooth, ribbon-like |

#### 🟠 SPATIAL mode presets (loose, school-like)

| Key | Preset | φp | φa | σ | Visual character |
|-----|--------|----|----|---|------------------|
| `5` | Classic Boids | 0.30 | 0.50 | 4 | Reynolds school — elongated, fish-like formation |
| `9` | Predator Ripple | 0.30 | 0.55 | 8 | Reactive, strong separation — birds spread then snap back |
| `0` | Storm Turn | 0.20 | 0.72 | 10 | Extreme streaming, high alignment — directional banding |
| `v` | Vacuole | 0.35 | 0.60 | 9 | Hollow voids, cavity-like — birds pushed to edges |
| `q` | Quest 2 Dense | 0.20 | 0.55 | 10 | Tight, dense school — VR-optimised for close viewing |

#### 🔴 Edge cases — see what happens at extremes

| Key | Preset | φp | φa | σ | What to watch for |
|-----|--------|----|----|---|-------------------|
| `1` | Pure Alignment | 0.00 | 0.95 | 8 | No projection force → rigid crystal, no cohesion mechanism. Flock should fragment unless alignment alone holds it. |
| `2` | Gas / Exploration | 0.10 | 0.20 | 2 | High noise, low alignment → random walk. Birds explore independently; flock barely holds together. |

#### Quick tour (60 seconds)

1. Start with `3` (Pearce Default) — watch for ~20 seconds. See how the flock naturally settles into marginal opacity.
2. Press `0` (Storm Turn) — the flock switches to SPATIAL mode and forms directional streams.
3. Press `0` again — toggles back to default. Notice the smooth transition.
4. Press `l` (Lava Lamp) — watch the blobby, fluid motion for ~15 seconds.
5. Press `2` (Gas) — the flock disperses. Press `3` to return to normal.
6. Press `M` to manually toggle modes — compare PROJECTION vs SPATIAL at same parameters.

### Boundary mode — TOROIDAL vs MARGIN

Press `B` to switch between two boundary behaviours. The on-screen badge shows the
current mode (green = TOROIDAL, amber = MARGIN).

**TOROIDAL (default)** — birds wrapping around edges.

| Behaviour | Details |
|-----------|---------|
| Exit right | Reappear at left edge |
| Exit left | Reappear at right edge |
| Exit bottom | Reappear at top edge |
| Exit top | Reappear at bottom edge |
| Position | Wrapped with `position %= WIDTH`, `position %= HEIGHT` |
| Velocity | Preserved across wrap |

Use TOROIDAL when you want:
- **Infinite-feeling space** — no edges, flock never hits a wall
- **Continuous flow** — birds stream seamlessly across boundaries
- **Maximum flock mobility** — no edge-avoidance forces interfering with flock dynamics
- **Large-flock realism** — real starling flocks operate in open sky, not in a cage

**MARGIN** — birds nudged away from edges and hard-clamped within bounds.

| Behaviour | Details |
|-----------|---------|
| Margin zone | 200 px from each edge — birds feel a nudge inward |
| Nudge force | `velocity += 1` toward centre when inside margin zone |
| Hard clamp | Position hard-clamped to `[0, WIDTH] × [0, HEIGHT]` after each update |
| Turn factor | `BOUNDARY_TURN_FACTOR = 1` — configurable in `flock_core.py` |

Use MARGIN when you want:
- **Contained arena** — birds stay in a bounded box, cannot escape
- **Edge clustering study** — watch how the flock compresses against walls
- **Confinement effects** — study how boundaries affect flock shape and density
- **Tighter visuals** — all birds remain visible; no wrapping disorientation

**Visual differences to watch for:**

| Aspect | TOROIDAL | MARGIN |
|--------|----------|--------|
| Flock shape | Free, can stretch across edges | Compressed near boundaries |
| Edge behaviour | Birds flow through edges smoothly | Birds turn away from edges |
| Density at edges | Uniform (edges are invisible) | Higher (birds stack up against walls) |
| Opacity (Θ) | Lower (flock spreads across wrap) | Higher (flock contained, more overlap) |
| Order (α) | Similar in both modes | Slightly lower near edges (turning reduces alignment) |

**Try this experiment:**
1. Start with `3` (Pearce Default) in TOROIDAL — watch for 15 seconds.
2. Press `B` to switch to MARGIN — watch the flock compress and bounce off edges.
3. Press `B` again to return to TOROIDAL — the flock flows freely again.
4. Try MARGIN with `5` (Classic Boids in SPATIAL mode) — the Reynolds school
   avoids edges with separation forces, creating a distinct boundary layer.

**Tuning MARGIN parameters** (edit `flock_core.py`):

```python
BOUNDARY_MARGIN     = 200   # px from edge where nudge begins (lower = steeper wall)
BOUNDARY_TURN_FACTOR = 1     # nudge strength per frame (higher = sharper turn)
```

Increase `BOUNDARY_TURN_FACTOR` to make birds avoid edges more aggressively
(useful for smaller flocks). Increase `BOUNDARY_MARGIN` to give birds more
room to turn before hitting the hard clamp.

### Getting maximum performance

1. **Reduce `NUM_BOIDS`** — the biggest factor. 50 birds run at ~200+ FPS; 300 birds at ~20 FPS.
2. **Set `LOG_FILE = None`** to eliminate disk I/O.
3. **Set `FPS = 0`** to run unthrottled (useful for batch data collection).
4. **Close other applications** — Pygame's software renderer is CPU-bound.
5. **In SPATIAL mode**, the spatial hash grid provides O(N) scaling; in PROJECTION mode, scaling is O(N² log N) due to per-bird occlusion computation.

### Saving a specific configuration

Edit the constants at the top of `alg2.py`:

```python
DEFAULT_PHI_P  = 0.05    # your preferred projection weight
DEFAULT_PHI_A  = 0.75    # your preferred alignment weight
DEFAULT_SIGMA  = 6       # your preferred neighbour count
NUM_BOIDS      = 200     # your preferred flock size
```

---

## Troubleshooting

### Python

#### "No module named 'pygame'"

```bash
pip install pygame
```

If you're using a virtual environment, make sure it's activated first.

#### "pygame.error: video system not initialized"

You're running without a display. On Linux, use `xvfb-run -a python alg2.py`. On macOS/Windows, a graphical session is required.

#### Simulation runs slowly (< 20 FPS)

- Reduce `NUM_BOIDS` to 100 or less
- Disable CSV logging (`LOG_FILE = None`)
- Close other applications
- Switch to SPATIAL mode (press `M`) — it's O(N) vs O(N² log N) for projection mode

#### "ModuleNotFoundError: No module named 'alg2'" when running tests

Run tests from the project root directory:

```bash
cd /path/to/murmuration
python3 -m unittest test_alg2 -v
```

#### Flock disperses or fragments

Increase φp slightly (press `↑`). If φp = 0, the projection term has no effect and the flock cannot maintain cohesion.

#### Window won't open on macOS

Pygame on macOS requires a framework build of Python. If you installed Python via Homebrew, you should be fine. If using the system Python, try:

```bash
python3 -m pip install --upgrade pygame
```

#### CSV file grows very large

Reduce `LOG_EVERY` to 100 or 1000, or set `LOG_FILE = None` to disable logging entirely.

### GNU Octave

#### "error: 'randperm' undefined"

You're using Octave < 4.0. Upgrade to Octave 4.0 or later.

#### Simulation is very slow (< 5 FPS)

- Reduce `NUM_BOIDS` at the top of `alg2.m` (line ~30)
- Disable CSV logging by setting `LOG_FILE = ''`
- The projection mode loop is O(N² log N) and cannot be fully vectorized — this is the bottleneck
- Switch to SPATIAL mode (press `m`) for significantly better performance

#### Figure window is unresponsive

Octave's event loop processes key presses during `pause(0.001)`. If keys don't register, try increasing the pause duration near the end of the main loop in `alg2.m`.

#### "error: 'BackgroundColor' undefined"

You're using Octave < 4.4. The help overlay uses 4-element RGBA `BackgroundColor`. Upgrade Octave or comment out the help overlay creation.

### Scilab

#### "Undefined variable: repmat" or "Undefined variable: gsort"

These are standard Scilab functions available in version 5.4+. Ensure you're using Scilab 6.0 or later.

#### Keyboard controls don't respond

Scilab's event handler is asynchronous and requires `sleep(1)` before `drawnow()` to yield the event loop. If keys don't register consistently, increase the sleep duration near line 615 of `alg2.sce` (try `sleep(5)` or `sleep(10)`).

#### Figure window opens blank

Some Scilab configurations require `drawnow()` to be called before the main loop. Check that `drawlater()` and `drawnow()` are paired correctly. Try running `drawnow()` once before entering the main `while running` loop.

#### Simulation crashes with "invalid index"

This can happen when removing birds brings `NUM_BOIDS` to 0. The code prevents this (leaves at least 1 bird), but if you modified the logic, check that `NUM_BOIDS > 0` before any matrix operation.

---

## FAQ

### What's the difference between the two modes?

- **PROJECTION** — each bird computes what it "sees" (which directions are blocked by other birds) and steers toward the edges between blocked and clear sky. Produces dense, murmuration-like flocks.
- **SPATIAL** — each bird follows three simple rules: stay close to neighbours (cohesion), match their direction (alignment), avoid crowding (separation). Produces school-like formations.

Press `M` to switch at any time.

### Can I change the number of birds while the simulation is running?

Yes — press `+` to add 10 birds, `-` to remove 10. Changes apply on the next frame.

### Can I run this without a display?

Yes, on Linux with `xvfb-run -a python alg2.py`. The simulation will run, CSV logging will work, but you won't see the window.

### Can I record a video of the simulation?

You can screen-record the window with any screen capture tool (OBS, QuickTime, etc.). There's no built-in video export.

Alternatively, capture frames with Pygame's `pygame.image.save()` — add this snippet inside the main loop:

```python
pygame.image.save(screen, f"frame_{frame:06d}.png")
```

Then compile frames into a video with ffmpeg:

```bash
ffmpeg -framerate 60 -i frame_%06d.png -c:v libx264 output.mp4
```

### Why does the CSV file show mode as a number?

`0` = PROJECTION mode, `1` = SPATIAL mode. This keeps the CSV compact and easy to filter programmatically.

### How do I make the simulation fullscreen?

At the top of `alg2.py`, change the display setup:

```python
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
```

Or for a larger window:

```python
screen = pygame.display.set_mode((1920, 1080))
```

Also update `WIDTH` and `HEIGHT` to match.

### Can I run multiple simulations in parallel?

Yes — each instance writes to the same CSV file by default. Set a unique `LOG_FILE` per instance, or set `LOG_FILE = None` for non-logging runs.

### Where does the CSV file go?

It's created in the directory where you run `python alg2.py`. Usually the project root. Check your working directory with `pwd` (macOS/Linux) or `cd` (Windows).

### The help overlay is in the way — how do I hide it?

Press `H`. Press `H` again to bring it back.

### Can I contribute?

Yes — the project is on GitHub at [`tralev/murmuration`](https://github.com/tralev/murmuration). Pull requests, issues, and feature suggestions are welcome.

### How do I use Docker?

Docker runs the simulation **headless** (no visible window). The `SDL_VIDEODRIVER=dummy`
environment variable tells Pygame to use a virtual framebuffer — the simulation
computes everything normally but renders to nowhere.

**Quick reference:**

```bash
./run-docker.sh              # full simulation (headless)
./run-docker.sh tests        # run unit tests
./run-docker.sh validate-all # full validation pipeline
```

**Where does the CSV go?**  
The `docker-compose.yml` mounts `./output` to `/app/output` inside the container.
CSV files written to `/app/output/murmuration_metrics.csv` appear in
`output/murmuration_metrics.csv` on your host machine. If the `output/`
directory doesn't exist on your host, Docker creates it but the file will
be owned by `root`.

**Persistent data across runs:**  
The CSV is written to the mounted `output/` volume, so it persists after
the container stops. To collect multiple runs, either copy the file between
runs or change `LOG_FILE` in `flock_core.py` before rebuilding.

**Rebuilding after code changes:**  
The Docker image copies source files at build time. If you edit `.py` files,
rebuild with `docker compose build` (or `./run-docker.sh` which auto-builds).

**Viewing logs:**  
The `run-docker.sh` script uses `docker run` (not `docker compose up`), so
logs stream directly to your terminal. Press `Ctrl+C` to stop.

---

## 3D Simulation

The 3D simulation extends the flocking algorithms into a full 3D volume
(1000 × 700 × 400) with GPU-accelerated rendering via ModernGL. Birds
steer in all three dimensions; the camera can orbit freely around the flock.

![3D murmuration demo](murmuration_3d.gif)

For the step-by-step build guide, see the [3D Simulation Build Guide](README.md#3d-simulation-build-guide)
in the README. For the underlying science, see [README.md](README.md).

### 3D Requirements

| Component | Minimum | Notes |
|-----------|---------|-------|
| **Python** | 3.7+ | 3.9+ recommended |
| **Pygame** | 2.0+ | Window and event handling only |
| **ModernGL** | 5.0+ | GPU rendering backend; 5.12+ recommended for macOS Metal support |
| **PyGLM** | 2.0+ | Matrix math — `lookAt`, `perspective`, `vec3` |
| **NumPy** | 1.20+ | Vector math and GPU buffer packing |
| **Pillow** | 9.0+ | Optional — only needed for `capture_3d.py` GIF generation |
| **GPU** | OpenGL 3.3 capable | Integrated GPU is fine; on macOS, Metal-backed via ModernGL |
| **RAM** | ~200 MB | Grows with instance count (6 floats × N birds) |

### 3D Installation

```bash
pip install pygame moderngl PyGLM numpy
```

Optional (for GIF capture):

```bash
pip install Pillow
```

Verify:

```bash
python3 -c "import moderngl; print('ModernGL', moderngl.__version__)"
python3 -c "import glm; print('PyGLM', glm.__version__)"
```

### Running the 3D Simulation

```bash
python main_3d.py
```

A 1200 × 800 window opens showing 150 birds in a 3D volume with a
perspective camera. The window title bar shows the current mode,
bird count, parameter values, and FPS.

**Startup output:**

```
Murmuration 3D — 150 birds
Mode: PROJECTION
Press M to toggle mode | Space to pause | ESC to quit
Mouse drag to orbit | Scroll to zoom
Presets: a=Default b=Ball c=Cloud d=Stream e=Column f=Acro w=Vortex h=Void
```

**Quick configuration:** edit the constants near the top of `main_3d.py`:

```python
NUM_BOIDS      = 150      # flock size
FPS            = 60       # target frame rate
WINDOW_WIDTH   = 1200     # window dimensions
WINDOW_HEIGHT  = 800
DEPTH          = 400      # Z-axis extent (defined in spatial_3d.py)
```

**Capturing a GIF:**

```bash
pip install Pillow
python capture_3d.py
# → murmuration_3d.gif  (80 frames, 4 seconds)
```

### 3D Controls Reference

#### Simulation controls

| Key | Action |
|-----|--------|
| `SPACE` | Pause / resume |
| `R` | Reset flock — randomise positions and velocities in 3D |
| `M` | Toggle **PROJECTION** ↔ **SPATIAL** mode |
| `ESC` | Quit |

#### Camera controls

| Input | Action |
|-------|--------|
| **Click + drag** | Orbit camera (azimuth + elevation) |
| **Scroll up** | Zoom in |
| **Scroll down** | Zoom out |
| `O` | Toggle **auto-rotate** — slow automatic orbit at 0.45 rad/s for unattended demos |
| `V` | **Reset camera** — snap back to the default view (azimuth 45°, elevation 30°, distance 1200) |

The camera orbits around the centre of the volume (500, 350, 200) by default.
Drag left/right to rotate horizontally, up/down to change elevation.
Elevation is clamped to ±89° to prevent gimbal lock. Note that `R` resets the
**flock** (not the camera) — use `V` to reset the camera view.

#### Parameter tuning

| Key | Parameter | Range | Step |
|-----|-----------|-------|------|
| `↑` / `↓` | φp | 0.0 – 1.0 | ±0.01 |
| `←` / `→` | φa | 0.0 – 1.0 | ±0.01 |
| `[` / `]` | σ | 1 – 20 | ±1 |

#### Flock size

| Key | Action |
|-----|--------|
| `+` / `=` | Add 10 birds |
| `-` | Remove 10 birds (leaves at least 1) |

#### Display toggles

| Key | Action |
|-----|--------|
| `G` | Toggle reference grid overlay (XY plane at z=0) |

### 3D Preset Scenarios

8 presets tuned specifically for the larger 3D volume. Press any letter key
to apply the preset instantly.

#### 🔵 PROJECTION mode presets (3D altitude cohesion)

| Key | Preset | φp | φa | σ | Visual character |
|-----|--------|----|----|---|------------------|
| `a` | 3D Pearce Default | 0.04 | 0.80 | 6 | Marginal opacity adapted for 3D volume |
| `b` | Ball of Birds | 0.18 | 0.70 | 7 | Dense 3D sphere, narrow altitude band |
| `c` | Storm Cloud | 0.06 | 0.45 | 3 | Dispersed through full 3D volume |
| `e` | Vertical Column | 0.10 | 0.75 | 6 | Altitude cohesion → layered pancake shape |
| `f` | 3D Acro | 0.02 | 0.85 | 3 | Rapid 3D turns, light cohesion |

#### 🟠 SPATIAL mode presets (full 3D steering)

| Key | Preset | φp | φa | σ | Visual character |
|-----|--------|----|----|---|------------------|
| `d` | 3D Stream | 0.25 | 0.55 | 8 | Directional 3D school formation |
| `w` | Spiral Vortex | 0.08 | 0.82 | 10 | Rotating 3D vortex, many neighbours |
| `h` | 3D Void | 0.35 | 0.58 | 9 | Maximum 3D separation, cavity voids |

#### Quick 3D tour (60 seconds)

1. Start with `a` (3D Pearce Default) — watch from the default camera angle.
2. Press `w` (Spiral Vortex) — the flock switches to SPATIAL mode, forms a rotating vortex.
3. Drag the mouse to orbit around the vortex — see it from all angles.
4. Press `b` (Ball of Birds) — the flock collapses into a dense 3D sphere.
5. Scroll to zoom in close. Press `c` (Storm Cloud) — birds disperse.
6. Press `a` to return to the default.

### 3D Tuning Guide

#### Understanding 3D flocking modes

**PROJECTION mode (3D):**
- XY-plane occlusion: same angular-interval algorithm as 2D, projected onto the horizontal plane
- Altitude cohesion: birds are nudged toward the mean Z of their visible neighbours
  - Formula: `altitude_cohesion = (mean_z_visible − self.z) × 0.01`
  - Weighted by φn (noise weight), so higher φn = stronger altitude pull
- Effect: birds naturally form layers at similar altitudes — like a flock of starlings flying at roughly the same height

**SPATIAL mode (3D):**
- All three steering forces (separation, alignment, cohesion) operate in full 3D
- 3×3×3 = 27-cell spatial grid queries for neighbour lookups
- Toroidal wrap in all three dimensions (X, Y, Z)
- Effect: looser, more exploratory 3D formations — birds can be above, below, or beside each other freely

#### Getting a dense 3D flock

| Parameter | Value | Why |
|-----------|-------|-----|
| φp | 0.04 – 0.12 | Moderate projection keeps XY-plane cohesion without over-compacting |
| φa | 0.75 – 0.85 | High alignment for smooth, coordinated 3D motion |
| σ | 5 – 7 | More neighbours maintain connectivity in the larger 3D volume |

#### Getting an exploratory 3D flock

| Parameter | Value | Why |
|-----------|-------|-----|
| φp | 0.02 – 0.05 | Light projection lets birds spread through the volume |
| φa | 0.40 – 0.55 | Lower alignment = more individual variation in 3D |
| σ | 2 – 4 | Fewer neighbours = weaker social coupling |

#### Performance scaling in 3D

Rough estimates on a modern integrated GPU (Apple M1 / Intel Iris). Your
mileage will vary by hardware.

| Birds | PROJECTION FPS | SPATIAL FPS | Bottleneck |
|-------|---------------|-------------|------------|
| 150 | ~55–60 | ~60 | None |
| 500 | ~40–50 | ~55–60 | Per-bird occlusion sort (O(K log K)) |
| 2000 | ~15–25 | ~45–55 | CPU flocking dominates; GPU rendering still fast |
| 5000 | ~5–10 | ~30–40 | PROJECTION: `MAX_VISIBILITY_RANGE` caps candidates but sort cost grows |

**Tips for large flocks:**
- Use SPATIAL mode — it scales O(N) vs PROJECTION's O(N × K log K)
- Reduce `MAX_VISIBILITY_RANGE` in `spatial_3d.py` (default: 200) to limit occlusion candidates
- Set `FPS = 0` in `main_3d.py` for unthrottled benchmarking
- GPU instanced rendering handles 5000+ birds in a single draw call; CPU flocking is the bottleneck

### 3D Troubleshooting

#### "No module named 'moderngl'"

```bash
pip install moderngl
```

#### "No module named 'glm'"

```bash
pip install PyGLM
```
Note: the package is `PyGLM` but the import is `import glm`.

#### "Failed creating OpenGL context at version requested"

Your GPU or driver doesn't support OpenGL 3.3. On macOS, this usually means
ModernGL's Metal backend isn't working. Try:

```bash
pip install --upgrade moderngl
```

ModernGL 5.12+ includes improved Metal support for macOS.

#### Black window, nothing renders

This can happen if ModernGL's standalone context fails silently. Check the
terminal output for errors. Common causes:
- Pygame window created without `OPENGL` flag — verify `DOUBLEBUF | OPENGL`
- ModernGL version too old — upgrade to 5.12+
- On Linux, missing GPU drivers — install Mesa drivers
- **macOS**: some users need to grant accessibility permissions in
  System Settings → Privacy & Security → Accessibility for the Terminal
  or Python to access GPU-accelerated graphics

#### Simulation runs at very low FPS

- Reduce `NUM_BOIDS` in `main_3d.py`
- Switch to SPATIAL mode (press `M`) — it scales much better than PROJECTION
- Close other GPU-intensive applications
- On macOS with integrated GPU, expect ~30 FPS at 2000 birds in SPATIAL mode

#### Camera spins uncontrollably

The orbit camera uses relative mouse motion. If the mouse cursor leaves the
window and re-enters, Pygame may report a large delta. This is normal — just
click and drag more gently. The camera clamps elevation to ±89° to prevent
flipping.

#### "pygame.error: video system not initialized"

Same as the 2D simulation — you need a graphical session. On headless Linux
servers, use `xvfb-run`:

```bash
xvfb-run -a python main_3d.py
```

But note: ModernGL may not work through `xvfb` depending on your GPU drivers.
Use `capture_3d.py` for headless operation instead.

#### Can't see the grid

Press `G` to toggle the reference grid on/off. The grid is drawn on the XY
plane at z=0. If your camera is looking from below (negative Z), the grid
may be clipped by the near plane — orbit the camera to a higher elevation.

### 3D FAQ

#### What's different between 2D and 3D simulation?

| Aspect | 2D (`alg2.py`) | 3D (`main_3d.py`) |
|--------|---------------|---------------------|
| Dimensions | X, Y only | X, Y, Z (400 depth) |
| Rendering | Pygame CPU drawing | ModernGL GPU instanced |
| Camera | Fixed orthographic | Free orbit perspective |
| Bird mesh | 2D triangles | 3D tetrahedrons with Blinn-Phong lighting |
| Bird count | ~150 optimal, ~300 max | ~2000 optimal, ~5000 max |
| Spatial grid | 2D toroidal (4–9 cells) | 3D toroidal (27 cells) |
| Projection model | Full 2D occlusion | XY-plane occlusion + Z altitude cohesion |
| Presets | 16 (keys 1–0, s,l,i,v,k,q) | 8 (keys a–f, h, w) |

#### Why ModernGL instead of PyOpenGL?

On macOS, Apple deprecated OpenGL in favour of Metal. PyOpenGL can only
create legacy OpenGL 2.1 contexts, which lack the GLSL 3.30 shaders,
Vertex Array Objects, and instanced rendering required for GPU-side 3D
rendering. ModernGL wraps Metal and exposes a modern GL 3.3+ API, making
instanced rendering work on macOS without code changes.

#### Can I run the 3D simulation without a GPU?

No — ModernGL requires a GPU with OpenGL 3.3 support. Integrated GPUs
(Intel, Apple M-series) work fine. Software rendering (LLVMpipe) is
unusably slow for real-time 3D.

#### Does the 3D simulation share code with the 2D version?

Yes — both use `flock_core.py` (Config, constants) and `occlusion_geom.py`
(angular interval math) without modification. The 3D simulation adds four
new files (`spatial_3d.py`, `boid_3d.py`, `renderer_3d.py`, `main_3d.py`)
that sit alongside the existing 2D code. The 2D code is completely untouched.

#### How many birds can the 3D simulation handle?

- **PROJECTION mode**: ~2000 birds at 20+ FPS (bottleneck: per-bird occlusion sort)
- **SPATIAL mode**: ~5000 birds at 30+ FPS (bottleneck: CPU flocking, not GPU rendering)
- GPU instanced rendering draws all birds in one call regardless of count

#### Can I capture screenshots or video?

Yes — use `capture_3d.py` for headless GIF generation:

```bash
python capture_3d.py
# → murmuration_3d.gif
```

For video, use a screen recorder (OBS, QuickTime) while the simulation runs.
You can also modify `capture_3d.py` to save individual PNG frames and assemble
them with ffmpeg.
