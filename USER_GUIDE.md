# Murmuration — User Guide

Practical setup and usage instructions. For the science behind the simulation, see [`README.md`](README.md).

---

## 🎓 Start Here — For Students

If you're new to this codebase, **don't open `alg2.py` first**. It imports from 5 modules and implements two complex flocking algorithms. Start with the minimal version instead:

```bash
python alg_simple.py
```

`alg_simple.py` is ~75 lines, one file, zero external imports (besides Pygame). It implements classic Reynolds boids — separation, alignment, cohesion — and you can read the entire thing in 5 minutes. Run it, watch the flock, then tweak the numbers at the top (`N`, `V0`, `R`, `F`) to see what changes.

**Suggested learning path:**

| Step | File | What you learn |
|------|------|----------------|
| 1 | `alg_simple.py` | Basic boids — how 3 simple rules create complex flocking |
| 2 | `occlusion_geom.py` | How angular intervals work — pure math, no Pygame |
| 3 | `flock_core.py` | Constants, Config, and the spatial hash grid |
| 4 | `boid.py` | The full Boid class — both projection and spatial modes |
| 5 | `metrics.py` | Scientific metrics, external opacity, help overlay |
| 6 | `alg2.py` | The main loop — ties everything together |

After that, read [`README.md`](README.md) for the scientific background and the implementation audit.

---

## Table of Contents

- [Start Here — For Students](#-start-here--for-students)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running the Simulation](#running-the-simulation)
- [Controls Reference](#controls-reference)
- [CSV Output](#csv-output)
- [Tuning Guide](#tuning-guide)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

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

```bash
python alg2.py
```

A window opens (1000 × 700 pixels) showing a flock of 150 birds in projection mode.

### Command-line options

There are no command-line flags. All configuration is done by editing the constants at the top of `alg2.py` or via keyboard controls at runtime.

### Quick configuration changes (edit `alg2.py`, lines ~60–75)

```python
NUM_BOIDS      = 150      # flock size (higher = slower)
V0             = 4        # bird speed (higher = faster flock)
VISUAL_RANGE   = 70       # neighbour search radius (spatial mode)
FPS            = 60       # target frame rate
LOG_FILE       = "murmuration_metrics.csv"   # set to None to disable CSV
LOG_EVERY      = 10       # write CSV every N frames
```

### Running on a headless server

Use `xvfb-run` (Linux) to create a virtual display:

```bash
xvfb-run -a python alg2.py
```

The simulation will run without a visible window. Useful for batch data collection or automated testing.

### Running unit tests

```bash
python3 -m unittest test_alg2 -v
```

47 tests covering the angular-interval utilities. No display needed — Pygame is mocked.

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

- **PROJECTION** (default) — birds steer toward light-dark boundaries in their view; produces dense, cohesive flocks
- **SPATIAL** — classic separation/alignment/cohesion boids; produces looser, school-like formations

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

Changes take effect on the **next unpaused frame**.

### Display toggles

| Key | Action |
|-----|--------|
| `G` | Toggle spatial grid overlay (SPATIAL mode only) — shows cell boundaries and occupancy counts |
| `H` | Toggle help overlay — top-right panel listing all controls |

### On-screen display

- **Top-left**: FPS, boid count, current mode, φp/φa/φn/σ values, opacity metrics
- **Top-right**: Mode badge (PROJECTION or SPATIAL) plus help panel (when toggled)
- **Bottom-centre**: Pause indicator when paused
- **Bird colour**: cool blue-white in PROJECTION mode, warm amber in SPATIAL mode

---

## CSV Output

When `LOG_FILE` is set (default: `murmuration_metrics.csv`), a row is written every `LOG_EVERY` frames:

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

Set `LOG_FILE = None` near the top of `alg2.py`. No file will be created and no disk I/O will occur.

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

### "No module named 'pygame'"

```bash
pip install pygame
```

If you're using a virtual environment, make sure it's activated first.

### "pygame.error: video system not initialized"

You're running without a display. On Linux, use `xvfb-run -a python alg2.py`. On macOS/Windows, a graphical session is required.

### Simulation runs slowly (< 20 FPS)

- Reduce `NUM_BOIDS` to 100 or less
- Disable CSV logging (`LOG_FILE = None`)
- Close other applications
- Switch to SPATIAL mode (press `M`) — it's O(N) vs O(N² log N) for projection mode

### "ModuleNotFoundError: No module named 'alg2'" when running tests

Run tests from the project root directory:

```bash
cd /path/to/murmuration
python3 -m unittest test_alg2 -v
```

### Flock disperses or fragments

Increase φp slightly (press `↑`). If φp = 0, the projection term has no effect and the flock cannot maintain cohesion.

### Window won't open on macOS

Pygame on macOS requires a framework build of Python. If you installed Python via Homebrew, you should be fine. If using the system Python, try:

```bash
python3 -m pip install --upgrade pygame
```

### CSV file grows very large

Reduce `LOG_EVERY` to 100 or 1000, or set `LOG_FILE = None` to disable logging entirely.

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
