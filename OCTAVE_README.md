# Murmuration — GNU Octave Port

> **Repository:** [https://github.com/tralev/murmuration](https://github.com/tralev/murmuration)  
> **Licence:** GNU General Public License v3.0 — see [LICENSE](LICENSE)

A **GNU Octave** implementation of a dual-mode bird flock (murmuration) simulation implementing the **hybrid projection model** from Pearce et al. (2014) and the classic **topological Reynolds boids** algorithm, switchable at runtime with a single key press.

---

## Table of Contents

- [Scientific Context](#scientific-context)
- [The Two Flocking Modes](#the-two-flocking-modes)
- [Octave Architecture](#octave-architecture)
- [Runtime Controls](#runtime-controls)
- [CSV Metrics Logging](#csv-metrics-logging)
- [How to Run](#how-to-run)
- [References](#references)

---

## Scientific Context

### Why Birds Don't Track Every Neighbour

A starling murmuration can contain over 300,000 individuals. It's unrealistic to expect each bird to identify and track the position and velocity of even a significant fraction of them. Two key empirical findings constrain how flocking models should work:

1. **Topological, not metric, interactions** — Ballerini et al. (2008a, 2008b) reconstructed 3D positions of starlings in the field and found that each bird interacts with a **fixed number of neighbours (6–7)** regardless of their physical distance. A bird 50 metres from its 7th neighbour behaves the same as a bird 5 metres from its 7th neighbour. This is a *topological* interaction rule, not a *metric* one.

2. **Projection, not tracking** — Pearce et al. (2014) proposed that the primary visual input to a bird in a large flock is not individual tracking but rather the **projection of the flock onto the retina**: a dynamic pattern of dark (bird) silhouettes against light (sky). This lower-dimensional projection provides global information about flock density and shape while being computationally manageable — both for the bird's brain and for mathematical modelling.

### The Problem with Metric Models

Classic Reynolds boids (the inspiration for **SPATIAL** mode) use three local rules — separation, alignment, cohesion — applied within a fixed radius. These models cannot explain how density is regulated in large flocks. As the number of birds grows, metric models either become fully opaque (every bird sees only other birds) or they require continuous re-tuning of parameters with flock size.

### The Solution: Hybrid Projection Model

Pearce et al. proposed that birds respond to the **boundaries between light and dark regions** in their visual field — the edges of bird silhouettes seen against the sky. The bird computes a single direction vector (δ̂) from these boundaries and combines it with alignment to visible neighbours and a noise term:

```
v(t+1)_i  =  φp · δ̂_i   +   φa · ⟨v̂_k⟩_vis   +   φn · η̂_i

where:
  δ̂_i   = normalised average direction to all light-dark domain boundaries
  ⟨v̂_k⟩ = average velocity of the σ nearest *visible* neighbours
  η̂_i   = uncorrelated random noise (unit vector)
  φp + φa + φn = 1
```

Critically, the projection term δ̂_i **replaces** the classic separation and cohesion forces. This model naturally produces:

- **Robust cohesion** — the flock never fragments, even with very weak projection coupling (φp > 0)
- **Marginal opacity** — flocks self-organise to Θ ≈ 0.25–0.60, a state rich in visual information, matching field observations
- **Fast dynamics** — the projection provides a global interaction channel, so information propagates at the speed of light, not neighbour-to-neighbour

---

## The Two Flocking Modes

### MODE 0 — PROJECTION

Implements Eq. 3 from Pearce et al. (2014). The projection direction δ̂ is computed by:

1. **For every other bird *j* at distance *d***: compute the angular interval it subtends on the viewing circle. The centre angle is `atan2(y_j − y_i, x_j − x_i)`, the half-width is `arcsin(b/d)` where *b* is the bird's physical size.

2. **Sort by distance** (closest first) and incrementally merge intervals. A bird *j* is **visible** if any part of its angular interval extends the already-merged (occluded) set — i.e., it is not completely hidden behind closer birds.

3. **Extract domain boundaries**: the start and end of each merged dark region. These are the transition points between sky (light) and bird silhouettes (dark).

4. **Compute δ̂**: the normalised average of unit vectors pointing to every domain boundary. A bird surrounded on all sides (opacity = 1) has no boundaries to steer toward and δ̂ = 0 — it must rely on alignment and noise alone.

5. **Alignment**: average velocity of the σ nearest visible neighbours.

### MODE 1 — SPATIAL

A topological variant of Reynolds' classic boids with three modifications:

- **Topological neighbourhood**: only the σ nearest neighbours within `VISUAL_RANGE` contribute (not all neighbours within range, as in the original). This follows Ballerini et al.'s finding that starlings use a fixed neighbour count.

- **Separation**: steers away from neighbours closer than 30% of `VISUAL_RANGE`. The repulsion force is inversely proportional to distance.

- **Full pairwise distance matrix**: computed in one vectorized operation (`repmat` broadcasts) for O(N²) memory but fast execution in Octave's BLAS-backed linear algebra.

The weights φp, φa, and φn are repurposed as separation strength, alignment strength, and cohesion strength respectively — φn is auto-computed each frame as `1 − φp − φa` so the sum always equals 1.

---

## Octave Architecture

### Data Representation: Parallel Matrices

All bird state is stored in **N × 2 matrices** — there are no classes, structs, or cell arrays for per-bird data:

| Matrix | Shape | Description |
|--------|-------|-------------|
| `pos` | N × 2 | Positions (x, y) |
| `vel` | N × 2 | Velocities (vx, vy) |
| `acc` | N × 2 | Accelerations (ax, ay) |
| `last_theta` | N × 1 | Cached internal opacity per bird |

Physics updates are fully vectorized — no per-bird loops for integration:

```matlab
vel = vel + acc;                          % Euler integration
spd = sqrt(sum(vel.^2, 2));               % speeds (N×1)
fast = find(spd > V0);                    % mask: too fast
vel(fast,:) = vel(fast,:) ./ repmat(spd(fast), 1, 2) * V0;  % clamp
pos = pos + vel;
acc = acc * 0;
pos(:,1) = mod(pos(:,1), WIDTH);          % toroidal wrap
pos(:,2) = mod(pos(:,2), HEIGHT);
```

### Rendering: Single Patch Object

Instead of drawing triangles one-by-one (prohibitively slow in Octave), all N birds are rendered in a **single `patch` call**. Triangle vertices are arranged as **3 × N matrices** — each column holds the three vertices of one bird's triangle:

```matlab
% Compute all triangle vertices in matrix form
dirs = atan2(vel(:,2), vel(:,1));
tip_x = pos(:,1)' + cos(dirs)' * tip_len;
tip_y = pos(:,2)' + sin(dirs)' * tip_len;
% ... left and right vertices similarly ...

X = [tip_x; lft_x; rgt_x];   % 3 × N
Y = [tip_y; lft_y; rgt_y];   % 3 × N

% Update handles — no object creation/destruction per frame
set(hBoids, 'XData', X, 'YData', Y, 'FaceColor', bird_color);
```

This is **extremely efficient** — only the vertex data is sent to the renderer each frame, no geometry reallocation occurs.

### Text Overlays: Persistent Handles

Text objects for metrics (FPS, φ values, Θ, Θ′, α) are created **once** before the main loop. Each frame, only their `.String` property is updated:

```matlab
% Creation (once):
hTextFPS = text(10, 5, '', 'Color', [170 200 170]/255, 'FontSize', 12);

% Update (each frame):
set(hTextFPS, 'String', sprintf('FPS: %.0f    Boids: %d    Frame: %d', ...
                                fps, NUM_BOIDS, frame));
```

This avoids the memory allocation and garbage collection cost of recreating text objects 10–30 times per second.

### Keyboard Interaction: KeyPressFcn

Octave's figure `KeyPressFcn` property provides non-blocking keyboard callbacks. The handler receives an `event` struct whose `.Key` field gives the key name as a string:

```matlab
set(f, 'KeyPressFcn', @key_handler);

function key_handler(src, event)
    global MODE paused PHI_P PHI_A SIGMA ...
    switch event.Key
        case 'uparrow'
            PHI_P = min(1.0, PHI_P + 0.01);
        case 'leftbracket'
            SIGMA = max(1, SIGMA - 1);
        % ... etc ...
    end
end
```

Key names are platform-independent (`'uparrow'`, `'leftbracket'`, `'add'`, `'subtract'`) — no ASCII code tables needed. Events are processed during `pause(0.001)` which yields the CPU and drains the event queue.

### Help Overlay: Single Text with Background

Rather than combining a separate rectangle and multiple text objects, the help panel uses a **single `text` object** with a 4-element `BackgroundColor` (RGBA) for alpha-blended transparency:

```matlab
hHelp = text(x, y, help_str, ...
             'BackgroundColor', [0 0 0 0.8], ...   % black, 80% opacity
             'Color', [0.8 0.8 0.6], ...
             'EdgeColor', [0.3 0.3 0.3], ...
             'VerticalAlignment', 'top', ...
             'Visible', 'off');
```

Toggling visibility is a single `set` call — no geometry to manage.

### State Changes: Pending Flags

Keyboard callbacks run asynchronously and **cannot safely modify** the simulation state matrices (pos, vel, acc) from a different call stack. Instead, callbacks set **pending flags** that the main loop applies atomically at the start of each frame:

```matlab
% Callback (async):
pending_add    = pending_add + 10;      % request more birds
pending_reset  = true;                   % request flock reset

% Main loop (sync, at frame start):
if pending_add > 0
    pos = [pos; new_pos];               % atomically append
    vel = [vel; new_vel];
    NUM_BOIDS = NUM_BOIDS + n_add;
    pending_add = 0;
end
```

This pattern is used for boid count changes (`+`/`-`), flock reset (`r`), and mode toggling.

---

## Runtime Controls

| Key | Action |
|-----|--------|
| `m` | Toggle **PROJECTION** ↔ **SPATIAL** mode |
| `↑` / `↓` | φp ±0.01 (projection weight in mode 0, separation in mode 1) |
| `←` / `→` | φa ±0.01 (alignment weight) |
| `[` / `]` | σ ±1 (nearest-neighbour count) |
| `+` / `-` | Add / remove 10 birds (capped at 200 pending adds) |
| `p` | Pause / resume |
| `r` | Reset flock — randomise all positions, zero all metrics |
| `h` | Toggle help overlay |
| Close window | Exit simulation (CSV file is flushed and closed) |

φn is **auto-computed** each frame as `max(0, 1 − φp − φa)`, guaranteeing that the three weights always sum to 1. All parameter changes take effect on the very next frame — no restart needed.

---

## CSV Metrics Logging

Every `LOG_EVERY` frames (default: 10), a row is appended to `murmuration_metrics.csv` in the current working directory:

```
frame,mode,num_boids,phi_p,phi_a,phi_n,sigma,theta,theta_ext,alpha,fps
0,0,100,0.0300,0.8000,0.1700,4,0.0123,0.0008,0.0341,12.3
10,0,100,0.0300,0.8000,0.1700,4,0.0234,0.0012,0.0892,14.1
20,1,100,0.0300,0.8000,0.1700,4,0.0156,0.0010,0.0523,18.7
...
```

Columns:
- `mode`: 0 = PROJECTION, 1 = SPATIAL
- `theta` (Θ): internal opacity — exact in PROJECTION mode, sampled (5 birds) in SPATIAL mode
- `theta_ext` (Θ′): external opacity from a distant observer placed far to the left
- `alpha` (α): order parameter — `|Σ vᵢ| / (N · v₀)`, 0 = chaotic, 1 = perfectly aligned

The CSV can be loaded into Octave, MATLAB, or any spreadsheet:

```matlab
% In Octave, after simulation:
data = csvread('murmuration_metrics.csv', 1, 0);  % skip header row
plot(data(:,1), data(:,8));  % frame vs theta
xlabel('Frame'); ylabel('\Theta');
```

---

## How to Run

```bash
octave alg2.m
```

Requirements: GNU Octave 4.0 or later (for `randperm(N, K)` two-argument form and 4-element `BackgroundColor` alpha support).---

## References

1. **Pearce, D. J. G., Miller, A. M., Rowlands, G., & Turner, M. S.** (2014). *"Role of projection in the control of bird flocks."* Proceedings of the National Academy of Sciences, 111(29), 10422–10426. [DOI: 10.1073/pnas.1402202111](https://doi.org/10.1073/pnas.1402202111)

2. **Reynolds, C. W.** (1987). *"Flocks, Herds, and Schools: A Distributed Behavioral Model."* ACM SIGGRAPH Computer Graphics, 21(4), 25–34. [DOI: 10.1145/37402.37406](https://doi.org/10.1145/37402.37406)

3. **Ballerini, M., et al.** (2008a). *"Interaction ruling animal collective behavior depends on topological rather than metric distance: Evidence from a field study."* PNAS, 105(4), 1232–1237. [DOI: 10.1073/pnas.0711437105](https://doi.org/10.1073/pnas.0711437105)

4. **Ballerini, M., et al.** (2008b). *"Empirical investigation of starling flocks: A benchmark study in collective animal behavior."* Animal Behaviour, 76, 201–215. [DOI: 10.1016/j.anbehav.2008.02.004](https://doi.org/10.1016/j.anbehav.2008.02.004)

5. **Young, G. F., Scardovi, L., Cavagna, A., Giardina, I., & Leonard, N. E.** (2013). *"Starling Flock Networks Manage Uncertainty in Consensus at Low Cost."* PLoS Comput Biol 9(1): e1002894. [DOI: 10.1371/journal.pcbi.1002894](https://doi.org/10.1371/journal.pcbi.1002894)

6. **Goodenough, A. E., Little, N., Carpenter, W. S., & Hart, A. G.** (2017). *"Birds of a feather flock together: Insights into starling murmuration behaviour revealed using citizen science."* PLoS ONE 12(1): e0179277. [DOI: 10.1371/journal.pone.0179277](https://doi.org/10.1371/journal.pone.0179277)

---

## Code Section Reference

Every numbered section in `alg2.m` maps to a specific line range. The section numbers are consistent with the project's unified structure, making it easy to locate the same algorithm across all implementations:

| Section | Content | `alg2.m` lines |
|---------|---------|---------------|
| 1 | Header & overview | 1–35 |
| 2 | Configuration constants | 37–70 |
| 2b | CSV logging setup | 95–107 |
| 2c | Figure & graphics setup | 109–130 |
| 3 | Runtime state initialization | 72–93 |
| 4 | Angular-interval utilities | 185–220 |
| 5 | Projection model (MODE 0) | 222–365 |
| 6 | Spatial model (MODE 1) | 390–470 |
| 7 | External opacity Θ′ | 367–430 |
| 8 | Metrics computation | 475–510 |
| 9 | Physics update | 512–540 |
| 9a | Auto-compute φn | 340–345 |
| 9b | Reset logic | 400–420 |
| 9c | Boid count changes | 348–398 |
| 10 | Help overlay | 132–160 |
| 11 | Input handling (keyboard callback) | 162–218 |
| 12 | Main simulation loop | 432–650 |
| 13 | Shutdown (close CSV, cleanup) | 652–660 |

Section 9d (grid rebuild) is not present — Octave uses a fully vectorized O(N²) pairwise distance matrix instead of a spatial hash grid.

---

## Paper-to-Code Implementation Audit

Three papers were cross-referenced against the codebase (July 2026).

### Pearce et al. (2014) — Primary Reference

| # | Claim | Status |
|---|-------|--------|
| 1 | Hybrid projection model: v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂ (Eq. 3) | ⚠️ Formula correct; code adds steering layer |
| 2 | δ̂ = vector sum to domain boundaries (Eq. 1) | ✅ |
| 3 | φp + φa + φn = 1 (Eq. 4) | ✅ |
| 4 | v₀ = 1, b = 1 (constant speed) | ⚠️ Scaled for display; speed allowed to vary |
| 5 | Silhouettes as dark/light pattern | ✅ |
| 6 | Visibility by occlusion (closer birds block farther) | ✅ |
| 7 | Closest-first processing | ✅ |
| 8 | σ = 4 visible neighbours | ✅ |
| 9 | Emergent marginal opacity (Θ ≈ 0.25–0.60) | ✅ |
| 10 | Default φp = 0.03, φa = 0.80 | ✅ |
| 11 | Order parameter α = \|Σv\|/(N·v₀) | ✅ |
| 12 | SI extensions: 3D, steric, blind angles, anisotropic | ❌ Not implemented |
| 13 | φp > 0 required for cohesion | ✅ Emergent |
| 14 | Correlation time τᵨ | ❌ Not tracked |
| 15 | Density scaling N^(−1/(d−1)) | ❌ Not analysed |

### Young et al. (2013) — Topological Neighbour Justification

| # | Claim | Status |
|---|-------|--------|
| 1 | Topological interaction provides robustness | ✅ |
| 2 | Optimal σ = 6–7 neighbours | ⚠️ Default is 4 |
| 3 | σ independent of N | ✅ |
| 4 | Dependence on flock thickness | ❌ 2D only |
| 5 | Consensus dynamics / H₂ robustness | ❌ Different model family |

### Goodenough et al. (2017) — Ecological Context

| # | Claim | Status |
|---|-------|--------|
| 1 | Mean murmuration: ~30,000 birds | ❌ Default N=150 |
| 2 | Predators at 29.6% of events | ❌ No predators |
| 3 | Anti-predator function | ❌ Not modelled |
| 4 | Critical mass ~500 birds | ❌ No threshold behaviour |

---

## Implementation Roadmap

Summary of planned extensions with relevant mathematics.

### Priority 1 — Fidelity to Pearce (2014)

**1a. Direct velocity setting (remove Reynolds steering)**

Currently, the code computes a desired direction via the projection model, then applies Reynolds steering toward it — a smoothing layer not present in the original paper. The fix is to set velocity directly:

```
v_i(t+1)  =  φp · δ̂_i(t)  +  φa · ⟨v̂_j⟩_visible  +  φn · η̂_i(t)      (Eq. 3)
r_i(t+1)  =  r_i(t) + v₀ · v̂_i(t+1)                                      (Eq. 2)
```

The velocity is set directly to the desired vector, normalised to v₀. No steering, no acceleration accumulation, no `MAX_FORCE` clamping. This eliminates artificial inertia and matches the paper's instantaneous response. Also remove the speed clamp from the physics update for projection-mode birds (the paper uses strict constant speed v₀).

**1b. External opacity from multiple viewpoints**

Θ′ should be averaged over multiple distant viewpoints, not a single fixed point:

```
Θ′  =  ⟨ Θ′(viewpoint_k) ⟩    averaged over K viewpoints on a circle
      at radius R_ext ≫ flock radius, angular spacing 2π/K

For each viewpoint at angle θ_k:  viewpoint = (R_ext·cos θ_k, R_ext·sin θ_k)
  Θ′_k = (sum of merged interval widths) / 2π
```

Sample K = 12 viewpoints on a circle of radius ~2000, compute Θ′ per viewpoint, return the mean.

**1c. Track correlation time τᵨ**

Autocorrelation of flock density over time:

```
τᵨ = ∫₀^∞ C_ρρ(Δt) dΔt

where  C_ρρ(Δt) = ⟨ρ(t) · ρ(t + Δt)⟩ − ⟨ρ⟩²
       ρ(t)    = N / (area of convex hull of flock at time t)
```

Requires: convex hull algorithm (e.g. Graham scan, O(N log N)), running window of density snapshots.

### Priority 2 — SI Appendix Extensions (Pearce et al., SI)

**2a. Steric / repulsive interactions**

Short-range repulsive force to prevent bird overlap (birds are "phantoms" without it, per the SI):

```
v_i  +=  φ_s · Σ_{j: d_ij < r_s}  (r̂_ji / d_ij²)

where:  φ_s = steric weight (~0.01–0.05)
        r_s = steric radius (~2b = 2 · BOID_SIZE)
        r̂_ji = unit vector from j to i
```

Add a repulsion loop in the projection update after computing `desired`, checking only the σ nearest visible neighbours.

**2b. Blind angles behind each bird**

Birds have a blind sector behind them (SI appendix). Birds whose entire angular interval falls within the blind region are treated as invisible:

```
For bird i with heading θ_i:
  blind region = [θ_i + π − β/2,  θ_i + π + β/2]    (mod 2π)

Any bird j whose angular interval is entirely within the blind region
is excluded from the occlusion merge (treated as NOT visible).

β = blind angle width (default: π/3 = 60°)
```

Filter entries in `compute_projection()` before the closest-first occlusion loop.

**2c. 3D extension**

In 3D, light-dark boundaries become curves on the unit sphere. δ̂ becomes the normalised integral of radial unit vectors along boundary curves:

```
δ̂_i  =  ∫_{boundaries}  r̂(θ, φ) dΩ   /   |∫ ...|
where   dΩ = sin φ dφ dθ   (solid angle element)

For each other bird j at 3D distance d:
  solid angle subtended:  Ω_j = 2π(1 − cos(arcsin(b/d)))   ≈ π·(b/d)²   for b ≪ d
```

Occlusion: birds project onto the unit sphere as circular caps. Replaces 1D interval merging with 2D spherical cap overlap testing. High complexity — consider GPU shadow-mapping for real time.

**2d. Anisotropic bodies**

Model birds as ellipses rather than circles (SI appendix):

```
For a bird with semi-major axis a and semi-minor axis b, oriented at angle ψ:
  projected width at viewing angle θ = √[(a·cos(θ − ψ))² + (b·sin(θ − ψ))²]
  angular half-width = arcsin(projected_width / (2d))
```

Modify the half-width calculation to use orientation-dependent projected size. Orientation can use the bird's velocity direction.

### Priority 3 — Ecological Realism

**3a. Predator agent (peregrine falcon / sparrowhawk)**

Based on Goodenough et al. (2017) — predators present at ~30% of real murmurations:

```
Predator dynamics:
  r_pred(t+1) = r_pred(t) + v_pred(t)
  v_pred(t+1) = v_pred(t) + a_pred(t)

  a_pred = φ_hunt · r̂_to_nearest_bird  +  φ_random · η̂
  Predator speed ~2× bird speed  (v_pred ≈ 2·v₀)
```

Bird response: birds within a danger radius flee away from the predator with a force proportional to 1/d², plus a startle propagation wave (neighbour-to-neighbour).

**3b. Larger flocks via spatial optimisation**

O(N log N) per bird limits N to ~100–150 in Octave. Scaling approaches:
- **Far-field approximation**: treat distant flock as a single extended occluder
- **Level-of-detail**: exact intervals for σ nearest, coarse angular histogram for the rest
- **Chunked processing**: split flock spatially; merge distant chunks into representative occluders

---

## Licence

GNU General Public License v3.0 — see [LICENSE](LICENSE).
