# Murmuration — Scilab Port

> **Repository:** [https://github.com/tralev/murmuration](https://github.com/tralev/murmuration)  
> **Licence:** GNU General Public License v3.0 — see [LICENSE](LICENSE)

A **Scilab** implementation of a dual-mode bird flock (murmuration) simulation implementing the **hybrid projection model** from Pearce et al. (2014) and the classic **topological Reynolds boids** algorithm, switchable at runtime with a single key press. This document covers the scientific foundations, algorithmic design, and Scilab-specific implementation patterns.

---

## Table of Contents

- [Scientific Foundations](#scientific-foundations)
- [The Two Flocking Modes](#the-two-flocking-modes)
- [Scilab Architecture](#scilab-architecture)
- [Core Concepts & Implementation](#core-concepts--implementation)
- [Runtime Controls](#runtime-controls)
- [CSV Metrics Logging](#csv-metrics-logging)
- [Limitations vs. the Python Version](#limitations-vs-the-python-version)
- [References](#references)

---

## Scientific Foundations

### Craig Reynolds' Boids (1987)

The seminal paper *"Flocks, Herds, and Schools: A Distributed Behavioral Model"* (Reynolds, 1987) introduced three simple rules that produce complex, lifelike flocking behaviour from local interactions alone:

```
Separation   — steer away from neighbours that are too close
Alignment    — steer toward the average heading of neighbours
Cohesion     — steer toward the average position of neighbours
```

Each agent ("boid") applies these rules using only information from its local neighbourhood. No central controller is needed — the flock self-organises.

### Topological vs. Metric Neighbourhoods (Ballerini et al., 2008)

Ballerini et al. (2008a, 2008b) reconstructed the 3D positions of individual starlings in large flocks and discovered a crucial fact: **starlings interact with a fixed number of neighbours (6–7) regardless of their physical distance**. This is a *topological* interaction (fixed neighbour count) as opposed to a *metric* one (fixed radius).

This finding is incorporated into both modes of the simulation:
- In **PROJECTION** mode, the alignment term averages over the σ nearest *visible* neighbours
- In **SPATIAL** mode, Reynolds rules are applied to the σ nearest neighbours within visual range

### The Hybrid Projection Model (Pearce et al., 2014)

The central paper: *"Role of projection in the control of bird flocks"* (Pearce, Miller, Rowlands & Turner, PNAS 2014) proposes that birds in large flocks do **not** track hundreds of individual neighbours. Instead, each bird perceives the flock as a **pattern of dark silhouettes against the sky** — the projection of the 3D flock onto the bird's retina (2D in our simulation).

Key insight: the projection is a **lower-dimensional representation** of the full 6N-dimensional phase space of the flock. It provides global information (density, shape) that local neighbour interactions alone cannot.

The paper's hybrid projection model defines the velocity of bird *i* as:

```
v(t+1)_i  =  φp · δ̂_i   +   φa · ⟨v̂_k⟩_{vis.n.n.}   +   φn · η̂_i

where:
  δ̂_i   = normalised average direction to all light-dark domain boundaries
  ⟨v̂_k⟩ = average over the σ nearest *visible* neighbours (topological alignment)
  η̂_i   = uncorrelated random noise (unit vector)
  φp + φa + φn = 1
```

**Crucially**, the projection term δ̂_i replaces the classic **separation and cohesion** forces. The model naturally produces:
- Robustly cohesive swarms (no fragmentation)
- **Marginal opacity** — flocks self-organise to Θ ≈ 0.25–0.60, neither fully opaque nor fully transparent
- Fast dynamic response (global information propagates at the speed of light, not neighbour-to-neighbour)

---

## The Two Flocking Modes

### MODE 0 — PROJECTION (Hybrid Projection Model)

The projection term δ̂_i is computed by:

1. **For every other bird *j* at distance *d***: compute the angular interval it subtends on the viewing circle:
   ```
   centre angle  = atan2(y_j − y_i,  x_j − x_i)
   half-width    = arcsin(b / d)
   interval      = [centre − half,  centre + half]
   ```

2. **Sort by distance** (closest first) and incrementally merge intervals. A bird *j* is **visible** if any part of its angular interval extends the already-merged (occluded) set — i.e., it's not completely hidden behind closer birds.

3. **Extract domain boundaries**: the start/end of each merged dark region. These are the edges between sky (light) and bird silhouettes (dark).

4. **Compute δ̂_i**: the normalised average of unit vectors pointing to every domain boundary:
   ```
   δ_i = (1/N_i) · Σ [cos(θ_boundary),  sin(θ_boundary)]
   δ̂_i = δ_i / |δ_i|
   ```

5. **Alignment**: average velocity of the σ nearest visible neighbours.

6. **Velocity**: `v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂`

In Scilab, this is implemented in `compute_projection()`:

```scilab
function [delta, vis_idx, vis_dists, n_vis, theta] = ...
         compute_projection(i, pos, vel)
    // Vectorized distance/angle computation for all other birds
    diffs  = pos - repmat(pos(i,:), NUM_BOIDS, 1);
    dists  = sqrt(sum(diffs.^2, 2));
    angles = atan(diffs(:,2), diffs(:,1));
    half   = asin(min(BOID_SIZE ./ dists, 1));
    
    // Sort by distance (closest first) for correct occlusion
    entries = [dists, angles, half, (1:NUM_BOIDS)'];
    entries(i, :) = [];
    [tmp, sort_idx] = gsort(entries(:,1), 'g', 'i');
    
    // Incremental merge + visibility determination
    // ... (see full source for the interval merging logic)
    
    // δ̂ from domain boundaries
    delta = [0, 0];
    for m = 1:n_merged
        delta = delta + [cos(merged(m,1)), sin(merged(m,1))];
        delta = delta + [cos(merged(m,2)), sin(merged(m,2))];
    end
    if norm(delta) > 0 then
        delta = delta / norm(delta);
    end
endfunction
```

### MODE 1 — SPATIAL (Topological Reynolds Boids)

A modernised version of Reynolds' classic algorithm:

1. **Compute the full N×N distance matrix** (vectorized in Scilab for speed):
   ```scilab
   dx = repmat(pos(:,1), 1, N) - repmat(pos(:,1)', N, 1);
   dy = repmat(pos(:,2), 1, N) - repmat(pos(:,2)', N, 1);
   dist_mat = sqrt(dx.^2 + dy.^2);
   ```

2. **For each bird, select the σ nearest neighbours** within VISUAL_RANGE (topological, not metric).

3. **Apply the three Reynolds rules**:
   - **Separation**: steer away from neighbours closer than 30% of VISUAL_RANGE
   - **Alignment**: steer toward average heading of the σ nearest
   - **Cohesion**: steer toward average position of the σ nearest

4. **Add noise** for exploration.

The weights φp/φa/φn are repurposed in spatial mode: separation strength, alignment strength, and cohesion strength respectively.

---

## Scilab Architecture

### Data Representation: Parallel Matrices

Since Scilab has no classes, all bird state is stored in parallel **N × 2 matrices**:

| Matrix | Shape | Description |
|--------|-------|-------------|
| `pos` | N × 2 | Positions (x, y) |
| `vel` | N × 2 | Velocities (vx, vy) |
| `acc` | N × 2 | Accelerations (ax, ay) |
| `last_theta` | N × 1 | Cached internal opacity per bird |

This enables **fully vectorized physics updates**:

```scilab
// Physics update — operates on entire matrices at once
vel = vel + acc;
spd = sqrt(sum(vel.^2, 2));          // speeds (N×1)
fast = find(spd > V0);               // clamp fast birds
vel(fast,:) = vel(fast,:) ./ repmat(spd(fast), 1, 2) * V0;
pos = pos + vel;                     // Euler integration
acc = acc * 0;                       // reset accelerations
pos(:,1) = modulo(pos(:,1), WIDTH);  // toroidal wrap
pos(:,2) = modulo(pos(:,2), HEIGHT);
```

### Rendering: Batch Polygons

Instead of drawing 100+ triangles one at a time (which is slow in Scilab), all bird triangles are **batched into a single `xfpolys` call** using NaN-separated vertices:

```scilab
// Compute all triangle vertices in matrix form (vectorized)
dirs = atan(vel(:,2), vel(:,1));
tip_x = pos(:,1) + cos(dirs) * tip_len;
tip_y = pos(:,2) + sin(dirs) * tip_len;
// ... left/right vertices ...

// Interleave with NaN for batch polygon drawing
X_verts = zeros(4 * NUM_BOIDS, 1);
Y_verts = zeros(4 * NUM_BOIDS, 1);
X_verts(1:4:$) = tip_x;   X_verts(2:4:$) = lft_x;
X_verts(3:4:$) = rgt_x;   X_verts(4:4:$) = %nan;
// Same for Y

xfpolys(X_verts, Y_verts, bird_color);  // single call!
```

This is **orders of magnitude faster** than per-bird `xpoly` calls.

### Keyboard Interaction: Figure Event Handlers

Scilab supports non-blocking keyboard input via **figure event handlers**. The callback function `key_handler(win_id, x, y, ibut)` is triggered by the Scilab event loop whenever a key is pressed:

```scilab
f.event_handler = "key_handler";
f.event_handler_enable = "on";
```

- `ibut < 0` indicates a keyboard event; `abs(ibut)` gives the key code
- ASCII keys (letters, brackets, +/−) use their ASCII codes
- Arrow keys have platform-dependent codes (both Linux 65xxx and Windows 37-40 variants are handled)
- Callback modifies **global variables** (`MODE`, `PHI_P`, `PHI_A`, etc.) which the main loop reads on the next frame

A crucial detail: `sleep(1)` (1 ms) is placed before `drawnow()` to yield control to the event loop:

```scilab
sleep(1);   // allow event queue to process key presses
drawnow();  // render the frame
```

### State Changes via Pending Flags

Since the callback runs asynchronously (during `sleep`/`drawnow`), it cannot safely modify the simulation state matrices (`pos`, `vel`, `acc`). Instead, it sets **pending flags**:

```scilab
// Callback (asynchronous):
pending_add    = pending_add + 10;    // request 10 more birds
pending_reset  = %t;                  // request a reset

// Main loop (synchronous, at frame start):
if pending_add > 0 then
    // safely append new boids to all state matrices
    pos = [pos; new_pos];
    vel = [vel; new_vel];
    NUM_BOIDS = NUM_BOIDS + n_add;
    pending_add = 0;
end
```

This pattern is used for: boid count changes (`+/−`), flock reset (`r`), and mode toggling.

---

## Runtime Controls

| Key | Action |
|-----|--------|
| `m` | Toggle **PROJECTION** ↔ **SPATIAL** mode |
| `↑` / `↓` | φp ±0.01 |
| `←` / `→` | φa ±0.01 (φn = 1−φp−φa is auto-computed each frame) |
| `[` / `]` | σ ±1 (nearest-neighbour count) |
| `+` / `-` | Add / remove 10 birds |
| `p` | Pause / resume |
| `r` | Reset flock (randomise positions, zero metrics) |
| `h` | Toggle help overlay |
| Close window | Exit simulation |

All parameter changes take effect on the **very next frame** — no restart needed.

---

## CSV Metrics Logging

Every `LOG_EVERY` frames (default: 10), a row is appended to `murmuration_metrics.csv`:

```
frame,mode,num_boids,phi_p,phi_a,phi_n,sigma,theta,theta_ext,alpha,fps
0,0,100,0.0300,0.8000,0.1700,4,0.0123,0.0008,0.0341,12.3
10,0,100,0.0300,0.8000,0.1700,4,0.0234,0.0012,0.0892,14.1
...
```

Columns:
- `mode`: 0 = PROJECTION, 1 = SPATIAL
- `theta` (Θ): internal opacity (exact in PROJECTION mode, sampled in SPATIAL)
- `theta_ext` (Θ′): external opacity from a distant observer
- `alpha` (α): order parameter — flock alignment (0 = chaotic, 1 = perfect)
- `fps`: frames per second

The CSV can be loaded into Scilab, MATLAB, or any spreadsheet for offline analysis:

```scilab
// In Scilab, after the simulation ends:
data = csvRead("murmuration_metrics.csv", [], [], "string");
// Plot opacity over time
plot(data(2:$,1), data(2:$,8));  // frame vs theta
```

---

## Performance Characteristics

The Scilab implementation uses fully vectorized matrix operations for physics and pairwise distance calculations, avoiding explicit loops where possible. Rendering batches all bird triangles into a single `xfpolys` call with NaN-separated vertices.

| Aspect | Detail |
|--------|--------|
| **Rendering** | Batch `xfpolys` with NaN-separated vertices |
| **Data model** | Parallel N×2 matrices (no classes) |
| **Performance** | ~10–30 FPS at N=100 (Scilab is interpreted) |
| **Keyboard** | Figure event handlers (async, needs `sleep(1)` before `drawnow()`) |
| **Spatial grid** | Full O(N²) pairwise distance matrix via `repmat` |
| **Help overlay** | Toggled with `h` key |
| **CSV logging** | Built-in (every `LOG_EVERY` frames) |
| **Runtime tuning** | All params adjustable via keyboard |

---

## References

1. **Reynolds, C. W.** (1987). *"Flocks, Herds, and Schools: A Distributed Behavioral Model."* ACM SIGGRAPH Computer Graphics, 21(4), 25–34. [DOI: 10.1145/37402.37406](https://doi.org/10.1145/37402.37406)

2. **Pearce, D. J. G., Miller, A. M., Rowlands, G., & Turner, M. S.** (2014). *"Role of projection in the control of bird flocks."* PNAS, 111(29), 10422–10426. [DOI: 10.1073/pnas.1402202111](https://doi.org/10.1073/pnas.1402202111)

3. **Ballerini, M., et al.** (2008a). *"Interaction ruling animal collective behavior depends on topological rather than metric distance."* PNAS, 105(4), 1232–1237. [DOI: 10.1073/pnas.0711437105](https://doi.org/10.1073/pnas.0711437105)

4. **Ballerini, M., et al.** (2008b). *"Empirical investigation of starling flocks: A benchmark study."* Animal Behaviour, 76, 201–215. [DOI: 10.1016/j.anbehav.2008.02.004](https://doi.org/10.1016/j.anbehav.2008.02.004)

5. **Young, G. F., Scardovi, L., Cavagna, A., Giardina, I., & Leonard, N. E.** (2013). *"Starling Flock Networks Manage Uncertainty in Consensus at Low Cost."* PLoS Comput Biol 9(1): e1002894. [DOI: 10.1371/journal.pcbi.1002894](https://doi.org/10.1371/journal.pcbi.1002894)

6. **Goodenough, A. E., Little, N., Carpenter, W. S., & Hart, A. G.** (2017). *"Birds of a feather flock together: Insights into starling murmuration behaviour revealed using citizen science."* PLoS ONE 12(1): e0179277. [DOI: 10.1371/journal.pone.0179277](https://doi.org/10.1371/journal.pone.0179277)

---

## Code Section Reference

Every numbered section in `alg2.sce` maps to a specific line range. The section numbers are consistent with the project's unified structure, making it easy to locate the same algorithm across all implementations:

| Section | Content | `alg2.sce` lines |
|---------|---------|-----------------|
| 1 | Header & overview | 1–35 |
| 2 | Configuration constants | 37–70 |
| 2b | CSV logging setup | 72–82 |
| 2c | Figure & graphics setup | 84–110 |
| 3 | Runtime state initialization | 55–70 |
| 4 | Angular-interval utilities | 165–200 |
| 5 | Projection model (MODE 0) | 202–345 |
| 6 | Spatial model (MODE 1) | 370–450 |
| 7 | External opacity Θ′ | 347–400 |
| 8 | Metrics computation | 455–490 |
| 9 | Physics update | 492–520 |
| 9a | Auto-compute φn | 310–315 |
| 9b | Reset logic | 370–390 |
| 9c | Boid count changes | 318–368 |
| 10 | Help overlay | 112–155 |
| 11 | Input handling (keyboard callback) | 127–162 |
| 12 | Main simulation loop | 412–620 |
| 13 | Shutdown (close CSV, cleanup) | 622–630 |

Section 9d (grid rebuild) is not present — Scilab uses a fully vectorized O(N²) pairwise distance matrix via `repmat` instead of a spatial hash grid.

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

O(N log N) per bird limits N to ~100–150 in Scilab. Scaling approaches:
- **Far-field approximation**: treat distant flock as a single extended occluder
- **Level-of-detail**: exact intervals for σ nearest, coarse angular histogram for the rest
- **Chunked processing**: split flock spatially; merge distant chunks into representative occluders

---

## How to Run

### Requirements

- **Scilab** 6.0 or later
- No additional toolboxes or packages required

### Execution

Run from the **Scilab console**:

```scilab
exec("alg2.sce");
```

Or from the command line:

```bash
scilab -f alg2.sce
```

A figure window opens (1000 × 700 pixels) showing a flock of 100 birds in projection mode. Close the figure window to stop the simulation. CSV metrics are saved to `murmuration_metrics.csv` in the current working directory.

### Performance Notes

- Expect **10–30 FPS** at N=100 (Scilab is interpreted, not JIT-compiled)
- Reduce `NUM_BOIDS` at the top of `alg2.sce` for higher frame rates
- Set `LOG_FILE` to `""` to disable CSV writes if I/O is a bottleneck
- Closing other Scilab figures and clearing the workspace helps

---

## Licence

GNU General Public License v3.0 — see [LICENSE](LICENSE).
