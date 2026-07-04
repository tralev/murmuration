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

## File Structure

```
murmuration/
├── alg.py                                     # Classic Reynolds boids (metric, all-neighbours)
├── alg2.py                                    # Dual-mode simulation (this project)
├── Role of projection in the control of        # Plain-text copy of Pearce et al. (2014)
│   bird flocks
├── Role of projection in the control of        # HTML/PDF version from PNAS website
│   bird flocks.html
└── README.md                                  # This file
```

### `alg.py` vs `alg2.py`

| | `alg.py` | `alg2.py` |
|---|---|---|
| Neighbourhood | Metric (all within `VISUAL_RANGE=70`) | Topological (σ nearest) |
| Behaviour model | Separation + Alignment + Cohesion | **MODE 0**: δ̂ projection + Alignment + Noise  \|  **MODE 1**: Separation + Alignment + Cohesion |
| Visibility | Not considered | **MODE 0**: occlusion-aware  \|  **MODE 1**: all within range |
| Performance | O(N²) | **MODE 0**: O(N² log N)  \|  **MODE 1**: O(N) via spatial grid |
| Metrics | None | Θ, Θ′, α, FPS |
| Runtime tuning | None | Full keyboard controls |
| Comments | Russian | English |

---

## Licence

This project is for educational and research purposes. The PNAS paper content is © 2014 National Academy of Sciences.
