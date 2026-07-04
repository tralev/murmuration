# Murmuration — Bird Flock Simulation

A Python simulation of starling murmurations implementing **two distinct flocking algorithms**, switchable at runtime:

| Mode | Algorithm | Inspiration |
|------|-----------|------------|
| **PROJECTION** | Hybrid projection model | [Pearce et al. (2014)](#references) |
| **SPATIAL** | Topological Reynolds boids | [Reynolds (1987)](#references) + [Ballerini et al. (2008)](#references) |

---

## Table of Contents

- [Quick Start](#quick-start)
- [Runtime Controls](#runtime-controls)
- [Algorithms](#algorithms)
  - [MODE 0 — Hybrid Projection Model](#mode-0--hybrid-projection-model)
  - [MODE 1 — Topological Reynolds Boids](#mode-1--topological-reynolds-boids)
- [Scientific Metrics](#scientific-metrics)
- [References](#references)
- [File Structure](#file-structure)

---

## Quick Start

```bash
pip install pygame
python alg2.py
```

Press **`M`** to toggle between modes, **`H`** for a help overlay.

---

## Runtime Controls

| Key | Action |
|-----|--------|
| `M` | Toggle **PROJECTION** ↔ **SPATIAL** mode |
| `↑` / `↓` | φp ±0.01 *(projection weight in mode 0, separation weight in mode 1)* |
| `←` / `→` | φa ±0.01 *(alignment weight; φn = 1 − φp − φa is auto-computed)* |
| `[` / `]` | σ ±1 *(nearest-neighbour count)* |
| `+` / `-` | Add / remove 10 birds |
| `G` | Toggle spatial grid overlay *(SPATIAL mode only)* |
| `H` | Toggle help overlay |
| `SPACE` | Pause / resume |
| `R` | Reset flock |
| `ESC` | Quit |

---

## Algorithms

### MODE 0 — Hybrid Projection Model

Based on the 2014 PNAS paper by **Pearce, Miller, Rowlands & Turner**:  
*"Role of projection in the control of bird flocks"*  
PNAS 111(29), 10422–10426 · [DOI: 10.1073/pnas.1402202111](https://doi.org/10.1073/pnas.1402202111)

#### Core Idea

The paper proposes that birds in large flocks do **not** track the positions of hundreds of neighbours. Instead, each bird perceives the flock as a pattern of **dark silhouettes against the sky** — a lower-dimensional projection of the full 6N-dimensional phase space. The bird responds to the boundaries between light (sky) and dark (bird) regions in its visual field.

This contrasts with classic Reynolds boids (implemented in `alg.py`), which use metric-based neighbour rules. The key difference: the **projection term replaces the classic separation and cohesion forces** with a single force derived from the bird's entire view.

#### The Velocity Equation (Eq. 3 from the paper)

```
v(t+1)_i  =  φp · δ̂_i   +   φa · ⟨v̂_k⟩_{vis.n.n.}   +   φn · η̂_i

where:
  δ̂_i   = normalised average direction to all light-dark domain boundaries
  ⟨..⟩  = average over the σ nearest *visible* neighbours
  η̂_i   = uncorrelated random noise (unit vector)
  φp + φa + φn = 1
```

Here is the exact implementation in `Boid._flock_projection()`:

```python
# 1 ─── projection direction & visible neighbours ──────────
delta, visible, theta = self._compute_projection_and_visibility(boids)
self._last_theta = theta

# 2 ─── alignment with σ nearest visible neighbours ────────
align = pygame.Vector2(0, 0)
if visible:
    nearest = visible[:config.sigma]
    for nb, _ in nearest:
        align += nb.velocity
    align /= len(nearest)

# 3 ─── noise ──────────────────────────────────────────────
na = random.uniform(0, 2 * math.pi)
noise = pygame.Vector2(math.cos(na), math.sin(na))

# 4 ─── desired direction  v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂ ──────
desired = delta * config.phi_p
if align.length() > 0.001:
    desired += align.normalize() * config.phi_a
else:
    if self.velocity.length() > 0.001:
        desired += self.velocity.normalize() * config.phi_a
desired += noise * config.phi_n

if desired.length() < 0.001:
    desired = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))

# Normalise to constant speed for smooth animation
desired.normalize_ip()
desired *= V0

# 5 ─── Reynolds-style steering ────────────────────────────
steer = desired - self.velocity
if steer.length() > MAX_FORCE:
    steer.scale_to_length(MAX_FORCE)
self.apply_force(steer)
```

#### Computing δ̂ — The Projection Direction

The projection direction δ̂ is the average of unit vectors pointing to every **domain boundary** — the edges between light (visible sky) and dark (bird silhouettes) in the bird's view.

For each other bird `j` at distance `d`:

```
centre angle  = atan2(y_j − y_i,  x_j − x_i)
half-width    = arcsin(b / d)           # angular radius subtended by bird j
interval      = [centre − half,  centre + half]
```

After merging all intervals (closest birds first, to handle occlusion), the domain boundaries are the start and end of each merged interval:

```python
def _compute_projection_and_visibility(self, boids):
    entries = []  # (boid, distance, centre_angle, half_width)
    for other in boids:
        if other is self:
            continue
        diff = other.position - self.position
        dist = diff.length()
        if dist < 0.001:
            continue
        centre = math.atan2(diff.y, diff.x)
        if centre < 0:
            centre += 2 * math.pi
        half = math.asin(min(BOID_SIZE / dist, 1.0))
        entries.append((other, dist, centre, half))

    entries.sort(key=lambda x: x[1])  # closest first

    merged = []              # [[start, end], …]  in [0, 2π)
    visible_neighbours = []  # [(boid, distance), …]

    for other, dist, centre, half in entries:
        start = centre - half
        end   = centre + half
        segments = _normalise_interval(start, end)

        # A bird is visible iff its interval extends the occluded set
        is_visible = any(
            not _interval_covered(s, e, merged) for s, e in segments
        )
        if is_visible:
            visible_neighbours.append((other, dist))
            for s, e in segments:
                _merge_interval(s, e, merged)

    # δ̂ from domain boundaries: average unit vector to each boundary
    delta = pygame.Vector2(0, 0)
    for s, e in merged:
        delta += pygame.Vector2(math.cos(s), math.sin(s))
        delta += pygame.Vector2(math.cos(e), math.sin(e))

    # Fully surrounded → no projection information
    if (len(merged) == 1 and
            merged[0][0] < 1e-9 and
            merged[0][1] > 2 * math.pi - 1e-9):
        delta = pygame.Vector2(0, 0)

    if delta.length() > 0:
        delta.normalize_ip()

    # Internal opacity Θ_i
    occluded = sum(e - s for s, e in merged)
    theta = min(occluded / (2 * math.pi), 1.0)

    return delta, visible_neighbours, theta
```

Key detail: sorting by distance (closest first) before merging intervals ensures correct occlusion — closer birds block farther ones. A bird whose angular interval is completely covered by intervals from closer birds is considered **not visible** and excluded from the alignment term.

#### Angular Interval Merging

The simulation normalises intervals into the [0, 2π) range, handling wrap-around across the 0/2π boundary:

```python
def _normalise_interval(start: float, end: float) -> list:
    """Split an angular interval into [0, 2π) segments, handling wrap."""
    segments = []
    if start < 0:
        segments.append((start + 2 * math.pi, 2 * math.pi))
        segments.append((0, end))
    elif end > 2 * math.pi:
        segments.append((start, 2 * math.pi))
        segments.append((0, end - 2 * math.pi))
    else:
        segments.append((start, end))
    return segments
```

Intervals are merged using binary-search insertion for O(log K) per insert, then merging with at most two adjacent intervals:

```python
def _merge_interval(start: float, end: float, merged: list):
    """Binary-search insertion + merge with adjacent intervals."""
    n = len(merged)
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        if merged[mid][0] < start:
            lo = mid + 1
        else:
            hi = mid
    idx = lo

    merged.insert(idx, [start, end])

    # merge left
    if idx > 0 and merged[idx - 1][1] >= merged[idx][0] - 1e-9:
        merged[idx - 1][1] = max(merged[idx - 1][1], merged[idx][1])
        merged.pop(idx)
        idx -= 1

    # merge right (chain in case of multiple overlaps)
    while idx < len(merged) - 1 and merged[idx][1] >= merged[idx + 1][0] - 1e-9:
        merged[idx][1] = max(merged[idx][1], merged[idx + 1][1])
        merged.pop(idx + 1)
```

---

### MODE 1 — Topological Reynolds Boids

A modernised version of Craig Reynolds' classic 1987 boids algorithm, incorporating:

- **Topological** (fixed neighbour count) rather than **metric** (fixed radius) neighbourhoods, following [Ballerini et al. (2008)](#references) who found starlings track exactly 6–7 neighbours regardless of distance
- **Spatial hash grid** optimisation for O(N) neighbour queries instead of O(N²)

#### Classic Reynolds Rules

The three rules from Reynolds (1987) "Flocks, Herds, and Schools":

```
Separation:  steer away from neighbours that are too close
Alignment:   steer toward the average heading of neighbours
Cohesion:    steer toward the average position of neighbours
```

#### Topological Neighbour Selection

Unlike `alg.py` (which uses all neighbours within a fixed `VISUAL_RANGE`), the SPATIAL mode selects only the **σ nearest neighbours**, mirroring starling behaviour:

```python
def _flock_spatial(self, boids, config, grid):
    # Query spatial grid for candidates (not all N birds)
    candidates = grid.get_nearby(self.position, VISUAL_RANGE)

    # Filter by exact distance, sort, take σ nearest
    neighbours = []
    for other in candidates:
        if other is self:
            continue
        d = self.position.distance_to(other.position)
        if d < VISUAL_RANGE:
            neighbours.append((other, d))
    neighbours.sort(key=lambda x: x[1])
    neighbours = neighbours[:config.sigma]  # topological cutoff
    n = len(neighbours)

    separation = pygame.Vector2(0, 0)
    alignment  = pygame.Vector2(0, 0)
    cohesion   = pygame.Vector2(0, 0)

    if n > 0:
        for other, d in neighbours:
            alignment += other.velocity
            cohesion  += other.position

            # Separation only when too close (< 30% of visual range)
            if d < VISUAL_RANGE * 0.3:
                diff = self.position - other.position
                if d > 0.001:
                    diff /= d
                separation += diff

        alignment /= n
        cohesion  /= n

        # Steering forces: desired minus current, clamped
        if alignment.length() > 0.001:
            alignment.scale_to_length(V0)
        alignment -= self.velocity
        if alignment.length() > MAX_FORCE:
            alignment.scale_to_length(MAX_FORCE)

        if cohesion.length() > 0.001:
            cohesion.scale_to_length(V0)
        cohesion -= self.velocity
        if cohesion.length() > MAX_FORCE:
            cohesion.scale_to_length(MAX_FORCE)

        if separation.length() > 0.001:
            separation.scale_to_length(V0)
        separation -= self.velocity
        if separation.length() > MAX_FORCE:
            separation.scale_to_length(MAX_FORCE)

    # Noise for exploration
    na = random.uniform(0, 2 * math.pi)
    noise = pygame.Vector2(math.cos(na), math.sin(na)) * MAX_FORCE * 0.8

    # Weighted sum
    self.apply_force(separation * config.phi_p * 2.0)
    self.apply_force(alignment  * config.phi_a * 1.2)
    self.apply_force(cohesion   * config.phi_n * 1.5)
    self.apply_force(noise)
```

#### Spatial Hash Grid

The spatial grid divides the simulation area into cells and maps each cell to the birds inside it. Neighbour queries then only examine cells overlapping the search radius — not all N birds.

```python
class SpatialGrid:
    def __init__(self, cell_size=70):
        self.cell_size = cell_size
        self.cols = max(1, int(math.ceil(WIDTH  / cell_size)))
        self.rows = max(1, int(math.ceil(HEIGHT / cell_size)))
        self.cells = defaultdict(list)

    def rebuild(self, boids):
        """Clear and repopulate in O(N)."""
        self.cells.clear()
        for boid in boids:
            cx = int(boid.position.x // self.cell_size) % self.cols
            cy = int(boid.position.y // self.cell_size) % self.rows
            self.cells[(cx, cy)].append(boid)

    def get_nearby(self, position, radius):
        """Return boids in cells overlapping the AABB of *radius*."""
        cx0 = int((position.x - radius) // self.cell_size)
        cx1 = int((position.x + radius) // self.cell_size)
        cy0 = int((position.y - radius) // self.cell_size)
        cy1 = int((position.y + radius) // self.cell_size)

        nearby = []
        for cx in range(cx0, cx1 + 1):
            wcx = cx % self.cols       # toroidal wrap
            for cy in range(cy0, cy1 + 1):
                wcy = cy % self.rows   # toroidal wrap
                nearby.extend(self.cells.get((wcx, wcy), ()))
        return nearby
```

The grid uses **toroidal (wrap-around) indexing** so birds near opposite screen edges can still interact — the simulation has periodic boundary conditions.

---

## Scientific Metrics

The simulation tracks three metrics from the Pearce et al. paper in real time:

| Metric | Symbol | Definition | Computation |
|--------|--------|------------|-------------|
| **Internal opacity** | Θ | Average fraction of each bird's 2π field of view occluded by other birds | Exact in PROJECTION mode (from already-computed intervals); sampled from 5 birds in SPATIAL mode |
| **External opacity** | Θ′ | Fraction of sky obscured from a distant external observer | O(N log N) interval merge from a fixed viewpoint |
| **Order parameter** | α | \|Σ vᵢ\| / (N · v₀) — degree of flock alignment (0 = chaotic, 1 = perfectly aligned) | O(N) sum of velocity vectors |

The paper predicts that flocks self-organise to a state of **marginal opacity** — Θ ≈ 0.25–0.60, neither fully transparent nor fully opaque. This is an emergent property of the projection model and does not require parameter tuning as flock size changes.

---

## References

1. **Pearce, D. J. G., Miller, A. M., Rowlands, G., & Turner, M. S.** (2014).  
   *"Role of projection in the control of bird flocks."*  
   Proceedings of the National Academy of Sciences, 111(29), 10422–10426.  
   [DOI: 10.1073/pnas.1402202111](https://doi.org/10.1073/pnas.1402202111)  
   *Proposes the hybrid projection model — the basis for MODE 0 (PROJECTION).*

2. **Reynolds, C. W.** (1987).  
   *"Flocks, Herds, and Schools: A Distributed Behavioral Model."*  
   ACM SIGGRAPH Computer Graphics, 21(4), 25–34.  
   [DOI: 10.1145/37402.37406](https://doi.org/10.1145/37402.37406)  
   *The original boids algorithm — the basis for MODE 1 (SPATIAL).*

3. **Ballerini, M., et al.** (2008).  
   *"Interaction ruling animal collective behavior depends on topological rather than metric distance: Evidence from a field study."*  
   Proceedings of the National Academy of Sciences, 105(4), 1232–1237.  
   [DOI: 10.1073/pnas.0711437105](https://doi.org/10.1073/pnas.0711437105)  
   *Empirical finding that starlings track 6–7 nearest neighbours regardless of distance — motivates topological (fixed-σ) rather than metric (fixed-radius) neighbourhoods.*

4. **Ballerini, M., et al.** (2008).  
   *"Empirical investigation of starling flocks: A benchmark study in collective animal behavior."*  
   Animal Behaviour, 76, 201–215.  
   [DOI: 10.1016/j.anbehav.2008.02.004](https://doi.org/10.1016/j.anbehav.2008.02.004)

---

## Code Tour — Module Structure

The codebase is split into focused modules so students can read them one at a time.

### Start here

| File | Lines | Purpose | Read first? |
|------|-------|---------|-------------|
| `alg_simple.py` | ~75 | Minimal boids — 3 rules, one file, zero complexity | **Yes — start here** |

### Core modules (in dependency order)

| File | Lines | Imports from | What's inside |
|------|-------|-------------|---------------|
| `occlusion_geom.py` | 135 | `math` only | 4 pure functions for angular-interval arithmetic on [0, 2π): normalise, coverage check, binary-search merge, sort-and-merge. No Pygame dependency. Unit-tested in `test_alg2.py`. |
| `flock_core.py` | 186 | `math`, `random`, `collections` | All constants (WIDTH, V0, BOID_SIZE, etc.), the `Config` class (mutable parameters + auto-computed φn), and `SpatialGrid` (toroidal hash grid for O(1) neighbour queries). |
| `boid.py` | 335 | `occlusion_geom`, `flock_core`, `pygame` | The `Boid` class — a single bird agent. Contains both flocking modes (`_flock_projection` and `_flock_spatial`), the occlusion-based visibility algorithm (`_compute_projection_and_visibility`), physics (`update`, `apply_force`), and drawing. Look for 🎓 teaching moment callouts. |
| `metrics.py` | 207 | `occlusion_geom`, `flock_core`, `boid`, `pygame` | `FlockMetrics` class (Θ, Θ′, α with EMA smoothing), `_external_opacity()` (distant observer), and `_draw_help()` (the controls overlay). |
| `scenario_presets.py` | 90 | `flock_core` | 5 educational preset configurations (keys 1–5) with `apply_preset()`. Students can add their own. |

### Entry point

| File | Lines | Imports from | What's inside |
|------|-------|-------------|---------------|
| `alg2.py` | ~265 | all modules above + `pygame`, `sys` | `main()` — the simulation loop. Handles input (keyboard + mouse), orchestrates the update/render cycle, CSV logging, focal bird debug view, and shutdown. This is where presets, pause, reset, and boid count changes are applied. |

### Supporting files

| File | Purpose |
|------|---------|
| `alg.py` | Original classic Reynolds boids — metric neighbourhood, Russian comments. Kept for historical comparison. |
| `test_alg2.py` | 47 unit tests for `occlusion_geom.py`. No Pygame needed. |
| `README.md` | This file — scientific background, paper audit, implementation roadmap. |
| `USER_GUIDE.md` | Practical guide — installation, controls, tuning, FAQ. |

### Module structure

```
occlusion_geom.py          (pure math — no dependencies)
       ↓
flock_core.py              (constants, Config, SpatialGrid)
       ↓
boid.py                    (Boid agent — both flocking modes)
       ↓
metrics.py                 (scientific metrics + help overlay)
       ↓
scenario_presets.py         (educational presets)
       ↓
alg2.py                    (main loop — ties everything together)
```

No circular imports. Each module can be read and understood independently.

### `alg.py` vs `alg2.py` (historical comparison)

| | `alg.py` (original) | `alg2.py` (current) |
|---|---|---|
| Neighbourhood | Metric (all within `VISUAL_RANGE=70`) | Topological (σ nearest) |
| Behaviour model | Separation + Alignment + Cohesion | **MODE 0**: projection + Alignment + Noise  \|  **MODE 1**: Separation + Alignment + Cohesion |
| Visibility | Not considered | **MODE 0**: occlusion-aware  \|  **MODE 1**: all within range |
| Performance | O(N²) | **MODE 0**: O(N² log N)  \|  **MODE 1**: O(N) via spatial grid |
| Metrics | None | Θ, Θ′, α, FPS |
| Runtime tuning | None | Full keyboard controls |
| Module structure | Single file | 6 modules + entry point |
| Comments | Russian | English |

---

---

## Code Section Reference

Every numbered section in the codebase maps to a specific file and line range. This table helps you find any section quickly:

| Section | Content | File |
|---------|---------|------|
| 1 | Header & overview | `alg2.py` (lines 1–40) |
| 2 | Configuration constants | `flock_core.py` |
| 2b | CSV logging / Pygame window setup | `alg2.py` `main()` |
| 2c | Graphics setup (clock, fonts) | `alg2.py` `main()` |
| 3 | Runtime state / data structures | `flock_core.py` + `boid.py` |
| 4 | Angular-interval utilities | `occlusion_geom.py` |
| 5 | Projection model (MODE 0) | `boid.py` |
| 6 | Spatial model (MODE 1) | `boid.py` |
| 7 | External opacity Θ′ | `metrics.py` |
| 8 | Metrics computation (Θ, Θ′, α) | `metrics.py` |
| 9 | Physics update (Euler, speed clamp, wrap) | `boid.py` |
| 9a | Auto-compute φn | `alg2.py` `main()` |
| 9b | Reset logic | `alg2.py` `main()` |
| 9c | Boid count changes (+/− keys) | `alg2.py` `main()` |
| 9d | Grid rebuild (spatial hash) | `alg2.py` `main()` |
| 10 | Help overlay | `metrics.py` |
| 11 | Input handling (keyboard + mouse) | `alg2.py` `main()` |
| 12 | Main simulation loop | `alg2.py` |
| 13 | Shutdown (close CSV, quit Pygame) | `alg2.py` (end) |

---

## Paper-to-Code Implementation Audit

Three research papers were cross-referenced against `alg2.py` (July 2026).  
✅ = fully implemented · ⚠️ = present but deviates · ❌ = not yet implemented

### Pearce, Miller, Rowlands & Turner (2014) — PNAS 111(29), 10422–10426

*Primary reference for MODE 0 (PROJECTION).*

| # | Claim from paper | Status | Implementation note |
|---|---|---|---|
| 1 | **Hybrid projection model** (Eq. 3): v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂ | ⚠️ | Formula correct, but code adds Reynolds steering (`steer = desired − velocity`, clamped to `MAX_FORCE=0.15`) instead of setting velocity directly. Adds smoothing/inertia not in the original model. |
| 2 | **δ̂** = vector sum to all domain boundaries (Eq. 1) | ✅ | `_compute_projection_and_visibility()` sums unit vectors to each merged interval's start and end angles, normalises. |
| 3 | **φp + φa + φn = 1** (Eq. 4) | ✅ | `Config.phi_n` @property: `max(0, 1 − φp − φa)`. |
| 4 | **v₀ = 1, b = 1** (constant speed, unit bird size) | ⚠️ | Scaled to `V0 = 4`, `BOID_SIZE = 3` for visual display. Speed clamped to `[0.3·V₀, V₀]` rather than strict constant speed. |
| 5 | **Silhouettes** — birds perceive dark/light pattern on retina | ✅ | Abstracted to merged 1D angular intervals on [0, 2π). |
| 6 | **Visibility by occlusion** — bird j visible iff any part of its angular interval is NOT covered by closer birds | ✅ | `_interval_covered()` advances a cursor; `is_visible = any(not covered(s, e) for s, e in segments)`. |
| 7 | **Closest-first processing** — distance-sorted before occlusion merge | ✅ | `entries.sort(key=lambda x: x[1])`. |
| 8 | **σ = 4** nearest visible neighbours (topological, from Ballerini 2008) | ✅ | `DEFAULT_SIGMA = 4`. |
| 9 | **Emergent marginal opacity** — Θ and Θ′ are intermediate (0.25–0.60 in real data) | ✅ | `FlockMetrics` tracks both with EMA smoothing. Emerges from model dynamics — no opacity target hard-coded. |
| 10 | **Default parameters**: φp = 0.03, φa = 0.80 for bird-like flocks | ✅ | `DEFAULT_PHI_P = 0.03`, `DEFAULT_PHI_A = 0.80`. |
| 11 | **Order parameter α** = speed of centre of mass / individual speed | ✅ | `FlockMetrics.order_param`: `|Σ vᵢ| / (N · V₀)`. |
| 12 | **SI Appendix extensions**: 3D model, steric/repulsive interactions, blind angles behind birds, anisotropic bodies | ❌ | 2D only. No steric forces. No blind sectors. Isotropic circular birds. |
| 13 | **φp > 0 required for cohesion** — flock fragments when projection weight is zero | ✅ | Emergent property; no hard-coded floor on φp, but setting it to 0 causes dispersal. |
| 14 | **Fast dynamics** — correlation time τᵨ decreases as φp increases | ❌ | Not tracked in metrics. |
| 15 | **Density scaling** — marginal opacity implies ρ ~ N^(−1/(d−1)) | ❌ | No spatial density analysis performed. |

### Young, Scardovi, Cavagna, Giardina & Leonard (2013) — PLoS Comput Biol 9(1): e1002894

*Motivates topological neighbour selection and optimal σ.*

| # | Claim from paper | Status | Implementation note |
|---|---|---|---|
| 1 | **Topological interaction provides robustness** — fixed neighbour count outperforms fixed radius | ✅ | Both MODE 0 and MODE 1 use σ-nearest-neighbour selection, not all-within-range. |
| 2 | **Optimal neighbour count**: 6–7 neighbours maximises robustness-per-neighbour | ⚠️ | Default is σ = 4 (from Pearce). Adjustable via `[`/`]` keys, but default doesn't match the 6–7 optimum. |
| 3 | **Independence of σ from N** — optimal count doesn't depend on flock size | ✅ | σ is fixed regardless of `NUM_BOIDS`. |
| 4 | **Dependence on flock thickness** — anisotropy (thin vs. spherical flocks) changes optimal σ | ❌ | 2D simulation; no shape anisotropy analysis. |
| 5 | **Consensus dynamics framework** — Laplacian matrix, H₂ robustness metric | ❌ | Not a consensus model; uses boid dynamics instead. Would require a fundamentally different architecture. |

### Goodenough, Little, Carpenter & Hart (2017) — PLoS ONE 12(1): e0179277

*Citizen-science observations of real murmurations; provides ecological context.*

| # | Claim from paper | Status | Implementation note |
|---|---|---|---|
| 1 | **Mean murmuration size**: ~30,000 birds (max 750,000) | ❌ | Default `NUM_BOIDS = 150`. Python/Pygame performance caps realistic sizes at ~200–300 before O(N log N) occlusion becomes prohibitive. |
| 2 | **Predators** at 29.6% of murmurations — linked to larger/longer displays | ❌ | No predator agents. Predator-prey dynamics not modelled. |
| 3 | **Anti-predator function** — dilution, detection, confusion effects | ❌ | Motivation acknowledged in code comments but not simulated. |
| 4 | **Critical mass** — ~500 birds needed to initiate murmuration behaviour | ❌ | Simulation starts with full flock; no gradual assembly or threshold behaviour. |

---

## Implementation Roadmap — Future Work

Planned extensions ordered by scientific priority. Each entry includes the relevant mathematics.

### Priority 1 — Fidelity to Pearce et al. (2014)

#### 1a. Direct velocity setting (remove Reynolds steering)

**Currently**: the code computes a `desired` direction via Eq. 3, then applies Reynolds steering toward it:

```
steer  = v_desired − v_current          ← not in paper
steer  = clamp(steer, MAX_FORCE)        ← not in paper
apply_force(steer)                      ← not in paper
```

**Should be** (matching Eq. 2–3 exactly):

```
v_i(t+1)  =  φp·δ̂_i(t) + φa·⟨v̂_j⟩_visible + φn·η̂_i(t)     (Eq. 3)
r_i(t+1)  =  r_i(t) + v₀ · v̂_i(t+1)                         (Eq. 2)
```

The velocity is **set directly** to the desired vector, normalised to v₀. There is no steering, no acceleration accumulation, no `MAX_FORCE`. This eliminates artificial inertia and matches the paper's instantaneous response.

**Implementation**: replace the steering block in `_flock_projection()` with:

```python
desired.normalize_ip()
desired *= V0
self.velocity = desired                       # direct set, no steering
# Remove self.apply_force(steer) and self.acceleration from projection path
```

Also remove the speed clamp from `update()` for projection-mode birds (the paper uses strict v₀).

#### 1b. External opacity from multiple viewpoints

**Currently**: Θ′ is computed from a single fixed viewpoint at (−2000, HEIGHT/2).

**Should be**: the paper defines Θ′ as "fraction of sky obscured by individuals from the viewpoint of a distant external observer" — implicitly an average over many viewpoints. More faithful:

```
Θ′  =  ⟨ Θ′(viewpoint_k) ⟩    averaged over K viewpoints on a circle
      at radius R_ext ≫ flock radius, angular spacing 2π/K

For each viewpoint at angle θ_k:
  viewpoint = (R_ext·cos θ_k,  R_ext·sin θ_k)
  Θ′_k = merge_all(asin(b/d_j)) / 2π   (same algorithm as Θ)
```

**Implementation**: sample K = 12 viewpoints on a circle of radius 2000, compute Θ′ per viewpoint, return the mean.

#### 1c. Track correlation time τᵨ

**Add to `FlockMetrics`**: autocorrelation of flock density over time.

```
τᵨ = ∫₀^∞ C_ρρ(Δt) dΔt

where  C_ρρ(Δt) = ⟨ρ(t) · ρ(t + Δt)⟩ − ⟨ρ⟩²
       ρ(t)    = N / (area of convex hull of flock at time t)
```

Requires: convex hull algorithm (e.g. Graham scan, O(N log N)), running window of density snapshots.

### Priority 2 — SI Appendix Extensions (Pearce et al. 2014)

#### 2a. Steric / repulsive interactions

**Paper SI**: introduces a short-range repulsive force to prevent overlap. birds are "phantoms" without it.

```
v_i  +=  φ_s · Σ_{j: d_ij < r_s}  (r̂_ji / d_ij²)   ← repulsion from close neighbours

where:
  φ_s   = steric weight (small, e.g. 0.01–0.05)
  r_s   = steric radius (~2b = 2 · BOID_SIZE)
  r̂_ji  = unit vector from j to i
```

**Implementation**: in `_flock_projection()`, after computing `desired`, add a repulsion term:

```python
repulsion = pygame.Vector2(0, 0)
for other in visible[:config.sigma]:   # only check visible neighbours
    diff = self.position - other.position
    d = diff.length()
    if d < 2 * BOID_SIZE and d > 0.001:
        diff /= d
        repulsion += diff / (d * d)    # 1/r² falloff
self.apply_force(repulsion * config.phi_steric)
```

#### 2b. Blind angles behind each bird

**Paper SI**: birds have a blind sector behind them where they cannot see other birds. This is modelled by masking out an angular region of width β centred on the opposite of the bird's heading.

```
For bird i with heading θ_i:
  blind region = [θ_i + π − β/2,  θ_i + π + β/2]    (mod 2π)

Any bird j whose angular interval is entirely within the blind region
is treated as NOT visible (excluded from occlusion merge).

β = blind angle width (default: π/3 = 60°)
```

**Implementation**: after building entries in `_compute_projection_and_visibility()`, filter out birds whose entire interval falls within the blind sector before the occlusion merge loop.

#### 2c. 3D extension

**Paper SI**: in 3D, light-dark boundaries become **curves on the surface of a sphere**. δ̂ becomes the normalised integral of radial unit vectors along these curves:

```
δ̂_i  =  ∫_{boundaries}  r̂(θ, φ) dΩ    /   |∫ ...|

where dΩ = sin φ dφ dθ   (solid angle element)
```

Discretely:

```
For each other bird j at 3D distance d:
  solid angle subtended:  Ω_j = 2π(1 − cos(arcsin(b/d)))
  ≈ π · (b/d)²   for b ≪ d

Occlusion: birds are projected onto the unit sphere as circular caps.
Cap overlap testing replaces 1D interval merging.
```

**Implementation complexity**: high. Requires replacing the 1D angular interval system with a 2D spherical cap merging algorithm (computationally expensive; Delaunay triangulation on the sphere is one approach). Consider using a GPU-based shadow-mapping approach for real-time performance.

#### 2d. Anisotropic bodies

**Paper SI**: birds modelled as ellipses rather than circles.

```
For a bird with semi-major axis a and semi-minor axis b, oriented at angle ψ:
  projected width at viewing angle θ = √[(a cos(θ−ψ))² + (b sin(θ−ψ))²]
  angular half-width = arcsin(projected_width / (2d))
```

**Implementation**: modify the half-width calculation in `_compute_projection_and_visibility()` to use orientation-dependent projected size. Requires storing orientation per bird (can use velocity direction).

### Priority 3 — Ecological Realism

#### 3a. Predator agent

**Based on Goodenough et al. (2017)**: predators (peregrine falcon, sparrowhawk) are present at ~30% of real murmurations.

```
Predator dynamics:
  r_pred(t+1) = r_pred(t) + v_pred(t)
  v_pred(t+1) = v_pred(t) + a_pred(t)

  a_pred = φ_hunt · r̂_to_nearest_bird  +  φ_random · η̂

  Predator speed ~2× bird speed (v_pred ≈ 2·v₀)
```

**Bird response**: birds within a "danger radius" of the predator flee away from it, plus a startle propagation wave (neighbour-to-neighbour).

#### 3b. Larger flocks via spatial optimisation

**Currently**: O(N log N) per bird for projection mode limits N to ~200.

**Scaling approaches**:
- **Far-field approximation**: for birds at distance d ≫ flock_radius, the flock can be treated as a single extended occluder with angular extent `arcsin(R_flock / d)`. This reduces the per-bird loop from N to O(N_near + log N_far).
- **Level-of-detail**: use exact angular intervals for the σ nearest birds, approximate the rest as a coarse angular histogram.
- **Chunked processing**: split the flock into spatial chunks; birds in distant chunks are merged into a small number of representative occluders.

---

## Licence

GNU General Public License v3.0 — see [LICENSE](LICENSE).

The PNAS paper content is © 2014 National Academy of Sciences. All research papers included in this repository are for reference and scholarly use.
