# Murmuration — 3D Bird Flock Simulation

A Python simulation of starling murmurations in a full **3D** volume, with
GPU-accelerated rendering via ModernGL and two runtime-switchable flocking
models grounded in three founding papers.

| Mode | Algorithm | Inspiration |
|------|-----------|------------|
| **PROJECTION** | Hybrid projection model (true 3D spherical-cap occlusion) | [Pearce et al. (2014)](#references) |
| **SPATIAL** | Topological Reynolds boids in 3D | [Reynolds (1987)](#references) + [Ballerini et al. (2008)](#references) |

The science — the projection model, Young's consensus robustness, Goodenough's
ecological dynamics, and the full 3D mathematics — is documented with equations
in **[sci.md](sci.md)**. Practical setup and usage is in
**[USER_GUIDE.md](USER_GUIDE.md)**.

![3D murmuration demo](murmuration_3d.gif)

*150 birds, auto-orbiting camera. First half: PROJECTION mode (Pearce et al.);
second half: SPATIAL mode (topological Reynolds boids). Captured headlessly via
a ModernGL FBO.*

---

## Table of Contents

- [Quick Start](#quick-start)
- [Runtime Controls](#runtime-controls)
- [3D Science Modules](#3d-science-modules)
- [The Model & the Maths](#the-model--the-maths)
- [How the 3D Stack Fits Together](#how-the-3d-stack-fits-together)
- [Build, Test & Docker](#build-test--docker)
- [References](#references)
- [Roadmap](#roadmap)
- [Licence](#licence)

---

## Quick Start

```bash
pip install -r requirements.txt      # pygame moderngl PyGLM numpy scipy
python main_3d.py
```

Mouse-drag to orbit the camera, scroll to zoom, **`M`** to toggle mode. See the
[full controls](#runtime-controls) below.

---

## Runtime Controls

| Key / Mouse | Action |
|-------------|--------|
| `M` | Toggle **PROJECTION** ↔ **SPATIAL** mode |
| `↑` / `↓` | φp ±0.01 |
| `←` / `→` | φa ±0.01 |
| `[` / `]` | σ ±1 |
| `+` / `-` | Add / remove 10 birds |
| `a`–`h`, `w` | 3D scenario presets (see `scenario_presets_3d.py`) |
| `T` | Spawn / remove a **predator** (flock takes flight) |
| `K` | Toggle the **roosting** day/night cycle (dusk descent) |
| `U` | Toggle Pearce **SI refinements** (steric + blind angles + anisotropy; on by default) |
| `G` | Toggle grid overlay |
| `O` | Toggle camera auto-rotate |
| `V` | Reset camera view |
| `SPACE` | Pause / resume |
| `R` | Reset flock |
| `ESC` | Quit |
| **Mouse drag** | Orbit camera |
| **Scroll** | Zoom in/out |

Live scientific metrics (order parameter α, internal/external opacity Θ/Θ′,
angular momentum L, dispersion σ_r) are shown in the window title bar.

---

## 3D Science Modules

The 3D stack implements the observables and models from the three founding
papers — Pearce et al. (2014), Young et al. (2013), Goodenough et al. (2017) —
distilled with their equations and the 3D maths in **[sci.md](sci.md)**. These
are standalone, unit-tested modules (`test_science_3d.py`) usable independently
of the render loop:

| Module | Paper | What it provides |
|--------|-------|------------------|
| `occlusion_3d.py` | Pearce et al. 2014 (SI) | **true 3D spherical-cap occlusion** — each neighbour subtends a circular cap on the view sphere; δ̂ is the boundary-length-weighted resolved direction of the light–dark *domain boundaries* (its magnitude regulates density → marginal opacity), Θ is the union of the caps. Analytic (not a lattice z-buffer), so it resolves sparse caps at any density |
| `metrics_3d.py` | Pearce et al. 2014 | `FlockMetrics3D` — order parameter α = \|Σv̂\|/N, internal opacity Θ (marginally-opaque flocks sit near μ≈0.30), external opacity Θ′ (rasterised silhouette coverage from a distant observer), angular momentum L, dispersion σ_r |
| `correlation_time.py` | Pearce et al. 2014 (Fig 2f) | density autocorrelation time τρ — density ρ = N / convex-hull **volume** (scipy Qhull), autocorrelated over a ring buffer |
| `density_scaling.py` | Pearce et al. 2014 | measures how density scales with N and fits the exponent against the marginal-opacity target ρ ~ N^(−1/2) (open-boundary free-flight sweep; see sci.md §4.9) |
| `h2_robustness.py` | Young et al. 2013 | consensus-network robustness — k-NN Laplacian H₂ norm, per-neighbour efficiency η(m), and `cost_optimal_m()` reproducing the paper's optimal **m\* ≈ 6–7** |
| `flock_shape.py` | Young et al. 2013 | 3D PCA shape analysis — aspect/thickness ratio → shape-driven optimal **m\*** (thin ≈6, round ≈9.8) |
| `steric_3d.py` | Pearce et al. 2014 (SI) | short-range 1/d² **steric repulsion** (part of the SI refinements, `U` key) |
| `predator_3d.py` | Goodenough et al. 2017 | a hunting **predator** (≈2× speed, chases the swarm centre) + per-bird **flight response** (`T` key) |
| `ecology.py` | Goodenough et al. 2017 | seasonal flock-size curve, ~500-bird critical-mass gate, ~29.6% predator rate, plus **roosting**, **day-length**, and **temperature** models (`K` key) |
| `scenario_presets_3d.py` | — | eight one-key 3D regimes (Pearce Default, Ball of Birds, Storm Cloud, 3D Stream, Vertical Column, 3D Acro, Spiral Vortex, 3D Void) |

The Pearce **SI refinements** — blind rear cone + anisotropic (ellipsoid) bodies
in `occlusion_3d.py`, and steric repulsion in `steric_3d.py` — are on by default
and toggle together with `U`.

---

## The Model & the Maths

Rather than duplicate the derivations, the scientific reference lives in one
place: **[sci.md](sci.md)**. It covers

- **§1–§2** the Pearce hybrid projection model and Young's consensus robustness,
- **§3** Goodenough's ecological envelope (seasonal size, critical mass,
  predator rate, roosting),
- **§4** the **3D mathematics as implemented** — spherical-cap occlusion, the
  boundary-seeking δ̂, opacity Θ/Θ′, τρ, H₂ in 3D, the SI refinements, the
  behavioural dynamics, and (§4.9) density scaling & the limits of
  N-independence,
- **§6** the 2D features still to rewrite for 3D.

In PROJECTION mode a neighbour directly above or below the observer is correctly
occluded and steered toward — genuine 3D geometry, not the XY-plane projection
the earliest 3D prototype used.

---

## How the 3D Stack Fits Together

The simulation is a thin main loop over a few focused modules. Positions,
velocities and accelerations are numpy `float32` Vec3s so they pack straight
into GPU vertex buffers.

| File | Role |
|------|------|
| `flock_core.py` | Constants (WIDTH×HEIGHT×DEPTH, V0, BOID_SIZE, φ defaults) and the mutable `Config` (auto-computes φn = 1 − φp − φa) |
| `boid_3d.py` | `Boid3D` — numpy Vec3 physics: `flock()` dispatches by mode, `update()` does Euler integration + speed clamp + toroidal wrap (with an `OPEN_BOUNDARY` free-flight option used by the density-scaling analysis) |
| `spatial_3d.py` | `SpatialGrid3D` (27-cell hash for O(1) neighbour queries) + the two mode functions `flock_projection_3d` / `flock_spatial_3d` |
| `occlusion_3d.py` | the analytic 3D spherical-cap projection — δ̂, visibility, Θ (see the science table above) |
| `renderer_3d.py` / `shaders_3d.py` | ModernGL **instanced** rendering — one tetrahedron mesh, one draw call for the whole flock; each bird's velocity → rotation matrix is computed **in the vertex shader**, so the CPU uploads only 6 floats (pos + vel) per bird |
| `camera_3d.py` | orbit camera (azimuth / elevation / distance) via `glm.lookAt` + `glm.perspective` |
| `input_handler_3d.py` | keyboard + mouse events (mode, φ/σ tuning, presets, predator/roosting toggles, camera) |
| `main_3d.py` | the entry point — a 3-phase loop: **input → update (grid rebuild → flock → integrate) → render** |
| `capture_3d.py` | headless GIF capture via a ModernGL FBO (no window needed) |

**Why GPU-side rotation?** Instancing draws thousands of birds in one call, but
computing per-bird rotation matrices on the CPU would be the bottleneck. Doing
the velocity→`lookAt` rotation in the vertex shader lets the GPU parallelise it
across cores; the CPU just streams position + velocity.

**Why ModernGL?** On macOS, Apple deprecated OpenGL for Metal. PyOpenGL only
creates legacy GL 2.1 contexts (no VAOs, no instancing, no GLSL 3.30). ModernGL
exposes a modern GL 3.3+ API over Metal, so instanced rendering works
unchanged.

For a per-file line-level walkthrough, read the modules themselves — they are
heavily commented — alongside sci.md.

---

## Build, Test & Docker

```bash
# install
pip install -r requirements.txt

# run the simulation
python main_3d.py

# headless GIF
pip install Pillow && python capture_3d.py     # → murmuration_3d.gif

# tests (fast; the two ~25s integration tests are gated)
python -m unittest test_3d test_science_3d
RUN_SLOW_TESTS=1 python -m unittest test_3d test_science_3d   # include slow

# docker
docker compose up murmuration     # or: tests / shell
```

A tracked pre-commit hook (`.githooks/pre-commit`, enabled with
`git config core.hooksPath .githooks`) runs a syntax check plus the fast suite;
CI (`.github/workflows/test.yml`) additionally runs the gated slow tests and a
headless Docker smoke-launch. See **[tests.md](tests.md)** for what each test
area asserts (with the math), and the testing patterns behind the suite.

---

## References

1. **Pearce, D. J. G., Miller, A. M., Rowlands, G., & Turner, M. S.** (2014).
   *"Role of projection in the control of bird flocks."* PNAS 111(29),
   10422–10426. [DOI](https://doi.org/10.1073/pnas.1402202111) — the hybrid
   projection model (MODE 0).
2. **Young, G. F., Scardovi, L., Cavagna, A., Giardina, I., & Leonard, N. E.**
   (2013). *"Starling Flock Networks Manage Uncertainty in Consensus at Low
   Cost."* PLoS Comput Biol 9(1): e1002894.
   [DOI](https://doi.org/10.1371/journal.pcbi.1002894) — consensus robustness,
   optimal m*.
3. **Goodenough, A. E., Little, N., Carpenter, W. S., & Hart, A. G.** (2017).
   *"Birds of a feather flock together: Insights into starling murmuration
   behaviour revealed using citizen science."* PLoS ONE 12(6): e0179277.
   [DOI](https://doi.org/10.1371/journal.pone.0179277) — ecological dynamics.
4. **Reynolds, C. W.** (1987). *"Flocks, Herds, and Schools: A Distributed
   Behavioral Model."* ACM SIGGRAPH 21(4), 25–34.
   [DOI](https://doi.org/10.1145/37402.37406) — the boids algorithm (MODE 1).
5. **Ballerini, M., et al.** (2008). *"Interaction ruling animal collective
   behavior depends on topological rather than metric distance."* PNAS 105(4),
   1232–1237. [DOI](https://doi.org/10.1073/pnas.0711437105) — topological
   (fixed-σ) neighbourhoods.

---

## Roadmap

The still-unported behaviour / analysis / UI features (threat + escape wave,
vacuole, shared wander, Lissajous leaders, flow field, spherical shells,
multi-viewpoint Θ′, an in-frame HUD, an orchestration hub, …) are catalogued
with 3D rewrite notes in **[sci.md §6](sci.md#6-2d-features-still-to-rewrite-for-3d)**,
along with the `git show c948b22:…` pointers for recovering the original 2D
sources.

---

## Licence

GNU General Public License v3.0 or later — see [LICENSE](LICENSE).
Research-paper content remains © its respective publishers and is included for
reference and scholarly use only.
