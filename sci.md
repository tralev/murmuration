# Scientific Reference — Papers, Models & 3D Math

This is the durable scientific reference for the simulation. It distills the
three founding papers (their features, equations, and quantitative results) and
derives the **3D mathematics** the simulation actually uses. It was written from
the PDFs that used to live in `sci/`; those PDFs (and `sci.zip`) have been
removed — everything needed to understand or re-derive the model is here.

**The three papers**

| Ref | Paper | Where used |
|-----|-------|-----------|
| **Pearce 2014** | Pearce, Miller, Rowlands & Turner, *"Role of Projection in the Control of Bird Flocks"*, PNAS 111(29):10422–10426. arXiv:1407.2414. DOI:10.1073/pnas.1402202111 | projection model, opacity, order parameter, τρ |
| **Young 2013** | Young, Scardovi, Cavagna, Giardina & Leonard, *"Starling Flock Networks Manage Uncertainty in Consensus at Low Cost"*, PLoS Comput Biol 9(1):e1002894. arXiv:1302.3195 | H₂ robustness, optimal neighbour count m\* |
| **Goodenough 2017** | Goodenough, Little, Carpenter & Hart, *"Birds of a feather flock together…"*, PLoS ONE 12(6):e0179277 | seasonal size, critical mass, predators |

---

## 1. Pearce et al. (2014) — The Hybrid Projection Model

### 1.1 Core idea

Birds in large flocks do not track hundreds of individual neighbours. Each bird
perceives the flock as a **coarse-grained pattern of dark (bird) against light
(sky)** — the projection of the flock onto its retina. The bird steers toward
the **light–dark domain boundaries** of that projected pattern. This single
mechanism replaces the classic separation + cohesion forces and, crucially,
*regulates the flock's density*: flocks self-organise to **marginal opacity**
(neither transparent nor opaque), a state rich in information.

### 1.2 Governing equations (2D)

Each individual `i` has body size `b = 1` (the unit of length) and moves at
constant speed `v₀ = 1`.

**Projection direction (Eq. 1)** — the average direction to all `Nᵢ` light–dark
domain boundaries, at boundary angles `θᵢⱼ` (measured from the x-axis):

```
δᵢ = (1/Nᵢ) · Σⱼ ( cos θᵢⱼ , sin θᵢⱼ )
```

`δᵢ` is the **resolved vector sum of unit vectors to the domain boundaries** —
birds are "equally attracted to all the light–dark domain boundaries." (For the
central bird in the paper's Fig. 1, `Nᵢ = 10`.)

**Equation of motion (Eqs. 2–3):**

```
r_i(t+1) = r_i(t) + v₀ · v̂_i(t)                                    [2]

v_i(t+1) ∝  φp · δ̂_i  +  φa · ⟨v̂_k⟩_{k∈[1,σ] n.n.}  +  φn · η̂_i    [3]
```

- `δ̂_i` — normalised projection direction (Eq. 1).
- `⟨v̂_k⟩` — mean heading of the `σ` nearest **visible** neighbours (topological,
  `σ = 4` in all the paper's simulations). "Visible" = unbroken line of sight.
- `η̂_i` — unit-magnitude noise, a fresh uncorrelated random direction per bird
  per timestep.
- The result is renormalised to speed `v₀`.

**Weight constraint (Eq. 4):**

```
φp + φa + φn = 1
```

So the model has only **two free parameters** (`φp`, `φa`); `φn` follows. Sweeping
`{φp, φa}` produces distinct phenotypes reminiscent of birds, fish and insects.

### 1.3 Observables

- **Internal opacity Θ** — the fraction of a *typical bird's* view occluded by
  other birds.
- **External opacity Θ′** — the fraction of sky an *outside observer* sees
  occluded (their Fig. 3 quantity).
- **Marginal opacity** — real flocks sit at `0.25 ≲ Θ′ ≲ 0.6`. Fitted Gaussians:
  their data Fig. 3D `μ = 0.30, σ² = 0.059`; public-domain images Fig. 3E
  `μ = 0.41, σ² = 0.012`. Marginal opacity **emerges** — it is not targeted, and
  it holds across flock sizes `N` at fixed `φp, φa` (a bird need not know the
  flock size).
- **Order parameter** (Fig. 2E) — the flock polarisation `α = |Σᵢ v̂_i| / N ∈
  [0,1]` (net momentum normalised by speed); `1` = perfectly aligned stream,
  `~0` = disordered or milling.
- **Density autocorrelation time τρ** (Fig. 2F) — the timescale over which
  density fluctuations persist, in simulation timesteps. `τρ = ∫ C_ρρ(Δt)/C_ρρ(0)
  dΔt` with density `ρ = N / area(convex hull)`.

### 1.4 SI-Appendix generalisations

All three are **implemented for 3D** (see §4.7) and default on, toggled together
with the `U` key:

- **Anisotropic bodies** — elliptical/ellipsoid birds; projected size depends on
  viewing angle.
- **Steric repulsion** — short-range `1/r²` to prevent overlap ("phantom" birds
  in the base model have none).
- **Blind angles** — an incomplete rear angular field (a blind cone behind each
  bird).
- **3D extension** — see §4.

---

## 2. Young et al. (2013) — Consensus Robustness (H₂)

### 2.1 Core idea

Starlings track a **fixed number of nearest neighbours**; empirically that number
is ~7. Young et al. explain *why*: modelling heading agreement as noisy linear
**consensus** on the interaction graph, they show interacting with **six or
seven** neighbours optimises the trade-off between group cohesion and individual
sensing effort. The optimum is **independent of flock size**; it depends on the
flock's **shape — notably its thickness**.

### 2.2 Consensus dynamics and the H₂ norm

Each agent updates toward its neighbours with additive white noise:

```
ẋ_i = Σ_{j∈N_i} a_ij (x_j − x_i) + ξ_i
```

Stacking all agents gives `ẋ = −L x + ξ`, where **L is the graph Laplacian**:
off-diagonal `L_ij = −a_ij` (negative edge weight, 0 if absent), diagonal
`L_ii = Σ_j a_ij` (out-degree). Consensus (noise-free) is reachable iff the graph
is connected.

Project out the consensus direction with `Q` to get the **reduced Laplacian**
`L̄ = Q L Qᵀ`. The steady-state disagreement covariance `Σ` solves the **Lyapunov
equation**:

```
L̄ Σ + Σ L̄ᵀ = I                                                   (4)
```

and the robustness metric is the **H₂ norm**:

```
H₂ = √( Trace(Σ) )                                               (5)
```

Smaller `H₂` = more robust (less noise-driven disagreement). Equivalently, for a
symmetric Laplacian this is `H₂² = (1/2) Σ_{i≥2} 1/λ_i`, summing over the nonzero
Laplacian eigenvalues `0 = λ₁ ≤ λ₂ ≤ …` (the `λ₁ = 0` consensus mode is skipped).
`H₂` is `+∞` exactly when the graph is disconnected. Dividing by `√N` gives a
size-independent **nodal robustness**.

### 2.3 Result

Over empirical flocks of **440–2600 birds**, **m\* = 6–7 maximises robustness per
unit sensing cost**, independent of `N`, dependent on shape. A cost/benefit
reading — minimise `J(m) = H₂(m) + λ·m` — reproduces the interior optimum
(raw `H₂` alone always favours the maximum `m`).

---

## 3. Goodenough et al. (2017) — Ecological Envelope

Citizen-science analysis of **>3,000 murmurations** (23 countries, UK
predominant). Pre-roost displays, typically at sunset, usually ending with the
flock descending *en masse* to roost.

- **Seasonal size** — increases significantly **October → early February**, then
  decreases to the end of the season in **March**. Overall mean **30,082 birds**,
  maximum **750,000**. No habitat association (urban/rural/wetland alike).
- **Duration** — mean **26 minutes (± 44 s SEM)**. Positively correlated with
  **day length**; negatively (and more weakly) with **temperature**.
- **Predators** — birds of prey at **29.6%** of murmurations (harrier *Circus*,
  peregrine *Falco peregrinus*, sparrowhawk *Accipiter nisus*). Predator presence
  positively correlated with **size** (R² = 0.401) and **duration** (R² = 0.258).
  With predators present, displays were more likely to end *en masse* to roost.
- **Interpretation** — murmurations are primarily an **anti-predator adaptation**
  (dilution / detection / confusion — "safer together"), rather than recruiting
  birds for a warmer roost. A **critical mass** (~hundreds of birds) is implied
  for a coherent display to form.

These behavioural dynamics — a **hunting predator + flight response**, the
**dusk roosting descent**, and the **day-length / temperature** envelope that
sets the roost schedule — are implemented for 3D (see §4.8).

---

## 4. 3D Mathematics (as implemented)

Pearce's Eq. 1 states the 2D projection "easily can be extended to 3D flocks, in
which the light–dark boundaries become **curves on the surface of a sphere** and
`δ` becomes the normalised integral of radial unit vectors traced along these
curves." This section makes that concrete — it is the math the 3D simulation
runs (`occlusion_3d.py`), plus the 3D forms of the other observables.

### 4.1 Spherical-cap occlusion (the 3D projection)

The observer `i` looks out along all directions on the unit **view sphere**. A
neighbour `j` at displacement `Δ = r_j − r_i`, distance `d = |Δ|`, body radius
`b`, subtends a **circular cap**:

```
centre direction   d̂ = Δ / d
angular radius      α = arcsin( min(b/d, 1) )                (Pearce SI-3)
solid angle         Ω = 2π (1 − cos α)                       (steradians)
```

A view direction `v̂` lies inside the cap iff `v̂ · d̂ ≥ cos α`. The **dark
region** is the union of all neighbour caps.

**Occlusion (visibility), closest-first.** Sort neighbours by distance. A
neighbour is *visible* unless the direction to it lies inside a **nearer visible**
neighbour's cap:

```
j hidden  ⇔  ∃ nearer visible k :  d̂_j · d̂_k ≥ cos α_k
```

**Internal opacity Θ** — the sky fraction covered by the union of visible caps.
Using the probabilistic union (hidden caps lie inside visible ones and add
nothing):

```
Θ = 1 − Π_{visible j} ( 1 − Ω_j / 4π )
```

**Projection direction δ̂** — Pearce's "resolved vector sum of the light–dark
domain boundaries." The boundary of cap `j` is a circle whose resolved
(centroid) direction is `d̂_j` and whose boundary length ∝ `sin α_j`. The
resolved sum is divided by the **total** boundary length `Σ sin α_j`, *not* by
its own vector magnitude:

```
δ̂ = ( Σ_{visible j}  sin α_j · d̂_j ) / ( Σ_{visible j}  sin α_j )
```

so `δ̂` is a boundary-length-weighted **mean direction** with `|δ̂| ∈ [0, 1]`.
That surviving magnitude is the point: it is `≈ 1` when the boundaries all
resolve one way (a bird at the silhouette edge) and `→ 0` when they cancel (a
bird deep inside, fully dark). An interior bird therefore feels almost no
cohesion and drifts apart until it nears the edge, where `δ̂` grows and draws it
back — the flock self-regulates toward a light–dark balance (*marginal opacity*)
rather than a fixed spacing. Occlusion gates the sum (hidden birds drop out).
Normalising `δ̂` to unit length instead (as an earlier version did) discards this
magnitude and gives every bird full cohesion, which produces a constant-density
flock whose opacity climbs with `N`. (Averaging the **unoccluded** sky would give
the opposite sign — a "flee to open sky" separation force — and is *not* the
Pearce model.)

**Why analytic, not a lattice z-buffer.** Discretising the sphere with a
Fibonacci lattice (the obvious approach) fails at simulation density: with `b`
small in a large volume a neighbour's cap covers well under one lattice point, so
`Θ` and `δ̂` collapse to zero. The cap algebra above is exact and
**density-independent**. The 2D model avoided this because a 1-D angular interval
is continuous; the 2-D analogue on a sphere is the analytic cap union.

**3D velocity update.** Identical in form to Eq. 3, with `δ̂` now a genuine
3-vector (so cohesion in the vertical axis falls out for free — no ad-hoc
"altitude" term):

```
v_desired ∝ φp·δ̂_i + φa·⟨v̂_k⟩_{σ vis. n.n.} + φn·η̂_i ,   |v_desired| = v₀
```

The simulation reaches `v_desired` by steering, not by setting it instantly —
see §4.6. With `η̂` a uniform random unit vector on the sphere
`(cosθ sinφ, sinθ sinφ, cosφ)`, `θ∈[0,2π)`, `φ∈[0,π]`.

### 4.2 3D observables

- **Order parameter** `α = |Σ v̂_i| / N` — unchanged (3-vectors).
- **Internal opacity Θ** — from §4.1 (mean of per-bird Θ).
- **External opacity Θ′** — project the flock onto the plane perpendicular to a
  distant observer's line of sight and measure the covered fraction of the
  silhouette (rasterised union of projected disks).
- **Angular momentum** `L = ⟨ r × v ⟩` about the centre of mass — a 3-vector;
  distinguishes a milling vortex (large `|L|`) from a straight stream (`|L|≈0`).
- **Dispersion** `σ_r = ⟨ |r_i − r_com| ⟩`.

### 4.3 H₂ robustness in 3D

Dimension-agnostic (§2). Build the `m`-nearest-neighbour graph from the **3D**
positions (a k-d tree), symmetrise it, form `L = D − A`, and evaluate
`H₂² = (1/2N) Σ_{i≥2} 1/λ_i` from the Laplacian spectrum. The cost-optimal `m`
minimises `H₂(m) + λ·m` and lands at `m* ≈ 6–7` for typical 3D flocks.

### 4.4 Flock shape → optimal m\* (3D)

Young's "optimum depends on shape, not size" quantified in 3D via PCA of the
position covariance `C = cov(positions)` (a 3×3 symmetric matrix). Its
eigenvalues `λ₁ ≥ λ₂ ≥ λ₃` give:

```
aspect ratio     = √(λ₁ / λ₃)         (elongation, ≥ 1)
thickness ratio  = √(λ₃ / λ₁)         ∈ (0, 1]
```

Interpolate `m*` between the empirical endpoints: thin/longitudinal flocks
`m* ≈ 6.05`, thick/round flocks `m* ≈ 9.78`.

### 4.5 Correlation time τρ in 3D

`τρ` (Pearce Fig. 2F) with the density based on the convex-hull **volume**
(not area) in 3D:

```
ρ(t)     = N / volume( convex hull of the flock )
C_ρρ(Δt) = ⟨ρ(t)·ρ(t+Δt)⟩ − ⟨ρ⟩²
τρ       = Σ_{Δt≥0} C_ρρ(Δt)/C_ρρ(0)      (to the first zero crossing)
```

### 4.6 Implementation notes — where the code refines the idealised model

Two practical choices in the simulation depart from the bare Pearce equations
above; both are common in agent-based flocking and neither changes the
projection geometry:

- **Smooth turning (Reynolds steering).** Eq. 3 sets the new velocity directly
  (renormalised to `v₀`). The code instead computes that desired velocity and
  then *steers* toward it, limiting the per-frame change to `MAX_FORCE`:
  `a = clamp(v_desired − v, MAX_FORCE)`, `v ← v + a`. This gives birds inertia
  (they cannot reverse instantly) and a smoother trajectory, at the cost of the
  velocity not being exactly `v_desired` on any single frame.
- **Speed band, not a fixed speed.** Rather than holding `|v| = v₀` exactly, the
  integrator clamps speed to `[0.3·v₀, v₀]` — a ceiling at the cruise speed and a
  floor that prevents a bird from stalling (a zero-speed bird is re-seeded with a
  random heading). Over the flock the speed sits at `v₀` for all but briefly
  decelerating birds.
- **Body radius set to the domain scale, so marginal opacity emerges.** Pearce
  uses `b = 1` as the length unit; the flock then self-organises to a density at
  which internal opacity sits at the marginal value `Θ ≈ 0.30`. Here the domain
  spans `~1000` units, so a literal `b = 1..3` would leave the default 150 birds
  `~330` body-lengths apart — far sparser than a real flock — and `Θ` collapses to
  `~0.04`. Setting `BOID_SIZE = 9` sizes the domain to `~110` body-lengths across
  (a real murmuration's extent). At that scale the self-organised flock condenses
  well above the uniform density and the settled internal opacity reaches Pearce's
  marginal value `Θ ≈ 0.30` at the default `N = 150`. This is a unit choice, not an
  opacity target: nothing steers toward `0.30`; it emerges from the boundary-`δ̂`
  regulation (§4.1) once the density scale is physical. `b` sets the overall
  opacity *level*; the boundary-`δ̂` sets how it responds to density. (Regression-
  guarded by `TestMarginalOpacity`, CI-only as it must run the dynamics to
  condensation.)

The position update `p ← p + v` (Eq. 2), the weight constraint (Eq. 4, via
`Config.phi_n = max(0, 1 − φp − φa)`), and every quantity in §4.1–§4.5 are
implemented exactly as written.

- **Wrap is toroidal; interaction is *not*.** `Boid3D.update()` re-enters a
  bird on the opposite wall (per-axis, §4.9), but neighbour finding and the
  δ̂ / Reynolds geometry use the plain **Euclidean** displacement `p_i − p_j`
  — there is no minimum-image (nearest-across-the-seam) convention. So a bird
  at `x ≈ 0` and one at `x ≈ WIDTH` are spatially adjacent on the torus yet do
  **not** flock with each other. This is a deliberate simplification: the
  viewer's toroidal wrap only recycles birds that drift off-domain, while the
  scientifically-load-bearing runs use the open (free-flight) boundary (§4.9)
  where there is no seam at all, so a wrap-aware interaction metric would add
  cost and edge cases for no benefit to the modelled regime. `SpatialGrid3D`
  reflects the same choice: its cell indices wrap (`% cols`) so a query near a
  wall still returns candidates, but the caller re-filters them by Euclidean
  distance, so cross-seam candidates are gathered and then discarded.
  (Pinned by `test_3d.TestSpatialGrid3D.test_seam_and_drift_guarantees`.)
- **Bounded occlusion neighbourhood.** The closest-first visibility test is
  `O(V²)` in the number of in-range neighbours `V`. `occlusion_3d.py` caps `V`
  at `MAX_OCCLUSION_NEIGHBOURS = 64` (nearest-first), which bounds cost for
  pathologically dense neighbourhoods. A far bird is almost always occluded by
  nearer ones and contributes nothing to δ̂ or Θ, and the cap sits well above
  any realistic in-range count, so ordinary flocks — and the golden-trajectory
  config — are numerically identical with or without it.

### 4.7 Pearce SI refinements in 3D (`U` key; on by default)

- **Steric repulsion** — a short-range push away from every neighbour inside a
  steric radius `r_s` (a few body radii):
  `F_steric = φ_s · Σ_{d<r_s} r̂_{i←j} / d²`.
- **Blind angles** — a rear blind cone of full angle `β` (default 60°). With
  heading `ĥ`, a neighbour direction `d̂` is invisible when it lies in the cone
  behind the bird: `d̂ · (−ĥ) ≥ cos(β/2)`; such neighbours are dropped before
  occlusion.
- **Anisotropic bodies** — each neighbour is a prolate spheroid, semi-major
  `a = b·(a/b)` along its heading `ĥ_j`, semi-minor `b`. Viewed from direction
  `d̂` (angle `ψ`, `cos ψ = |d̂·ĥ_j|`) its silhouette radius is
  `b_eff = √((a·sin ψ)² + (b·cos ψ)²)` — large broadside, small end-on — and this
  `b_eff` replaces `b` in the cap radius `α = asin(b_eff/d)`.

### 4.8 Goodenough behavioural dynamics in 3D

- **Predator + flight response.** A raptor at `r_p` flies ~`2·v₀` toward the
  swarm centre `r_com`: `v_p ← clamp(v_p + a·unit(r_com − r_p), 2v₀)`,
  `r_p ← r_p + v_p`. Each bird within the danger radius `R_d` flees away from it,
  harder when nearer: `F_flee = φ_flee · (1 − d/R_d) · unit(r_i − r_p)`. The
  dilution/confusion "safer together" behaviour then emerges from the flock's
  collective flight.
- **Roosting + day length.** A UK-latitude day-length model
  `L(day) = L̄ + A·cos(2π(day − solstice)/365)` sets the sunset hour
  `= 12 + L/2`. A logistic **dusk factor** rises 0→1 across sunset, driving a pull
  toward a ground **roost** point `p_r` (low `z`):
  `F_roost = φ_r · dusk(hour) · unit(p_r − r_i)` — zero by day, strongest after
  sunset, producing the en-masse descent. A seasonal **temperature** proxy
  (coldest late January) slightly strengthens/prolongs the roost pull, matching
  the paper's weak negative temperature–duration correlation.

### 4.9 Density scaling and the limits of N-independence (`density_scaling.py`)

Pearce reports that marginal opacity is **N-independent** — a bird need not know
the flock size. The mechanism is a self-regulated density

`ρ(N) ~ N^(−1/(d−1))`  (3D: `ρ ~ N^(−1/2)`, linear size `L ~ N^(1/2)`),

so the optical depth `ρ·L`, and hence external opacity `Θ′`, stay constant as `N`
grows. `density_scaling.py` measures this scaling in the simulation rather than
asserting it, using straggler-robust statistics (median k-NN spacing; a gyration
radius trimmed of the far tail; `Θ′` of the core).

Three findings, honest about where the model stands:

- **`δ̂` now carries the density-regulation signal (§4.1).** The projection
  direction is the boundary-length-weighted mean `Σ sinα·d̂ / Σ sinα`, so
  `|δ̂| ∈ [0, 1]` — near 0 for a bird deep inside a dark flock, near 1 at the
  silhouette edge. This is the faithful Pearce mechanism: interior birds feel
  little cohesion and spread, edge birds are drawn in, so the flock seeks a
  light–dark balance rather than a fixed spacing. (An earlier version normalised
  `δ̂` to unit length, discarding the magnitude and giving every bird full
  cohesion → a constant-density flock whose opacity climbed with `N`.)
- **The toroidal viewer domain still breaks N-independence.** On the torus every
  bird is interior — there is no silhouette edge to regulate against — so the
  flock is pinned to the fixed domain volume and `ρ ∝ N`; internal `Θ` still
  climbs with `N` (measured spread ≈ 0.2 over `N = 80…320`). No `δ̂` can fix this
  while the domain is bounded; it is a property of the viewer, not the model. The
  free-flight **open boundary** (`boid_3d.OPEN_BOUNDARY`, used by the analysis)
  removes the artifact so the flock can float and self-size.
- **In free flight the regulation helps but does not fully close the gap.** The
  boundary-`δ̂` improves the measured open-boundary density exponent (from `≈ +0.5`
  under the old unit-normalised `δ̂` toward `≈ +0.4`), i.e. less over-condensation,
  but it does not reach Pearce's `ρ ~ N^(−1/2)`: at the canonical `φp = 0.03` the
  free flock also sheds stragglers (weak cohesion in open space), which limits how
  cleanly the density self-regulates. Closing the remaining gap is a matter of the
  other model approximations (discrete steric, alignment-dominated `φa`, the speed
  band), not the projection direction. `density_scaling.py` is the instrument that
  quantifies this, so the claim can be tracked as the model evolves.

---

## 5. Where each idea lives in the code

| Idea | Paper | Module |
|------|-------|--------|
| Bird physics — Euler integration, speed band, toroidal wrap / open boundary | §4.6, §4.9 | `boid_3d.py` |
| Spherical-cap occlusion (+ blind angles, anisotropy), δ̂, Θ | Pearce §1–2, SI §4.7 | `occlusion_3d.py` |
| 3D spatial hash grid (neighbour lookups) | — | `spatial_grid_3d.py` |
| Projection (Pearce) & spatial (Reynolds) flocking modes | Pearce Eq. 3 | `flocking_modes_3d.py` |
| Steric repulsion | Pearce SI §4.7 | `steric_3d.py` |
| Order param, Θ, Θ′, L, dispersion | Pearce §1.3 | `metrics_3d.py` |
| Density autocorrelation time τρ | Pearce Fig. 2F | `correlation_time.py` |
| H₂ consensus robustness, cost-optimal m\* | Young | `h2_robustness.py` |
| Flock shape → m\* | Young | `flock_shape.py` |
| Predator agent + flight response | Goodenough §4.8 | `predator_3d.py` |
| Seasonal size, critical mass, predator rate, roosting, day-length, temperature | Goodenough §4.8 | `ecology.py` |
| Density scaling ρ(N), marginal-opacity N-independence test | Pearce §1.3, §4.9 | `density_scaling.py` |
| Scenario presets (φp, φa, σ regimes) | — | `scenario_presets_3d.py` |

---

## 6. 2D features still to rewrite for 3D

The repository is **3D-only**: all simulation code runs on `boid_3d.Boid3D` /
`spatial_grid_3d` / `flocking_modes_3d` / numpy Vec3 state. Commit `6b71b15`
removed the 2D simulation, and
the 2D-era design/port docs (`ext.md`, `core_modules.md`, `OCTAVE_README.md`,
`SCILAB_README.md`, `BOUNDARY_MODES.md`, `ARCHITECTURE.md`) have now been removed
too. This section preserves the still-unported **features and ideas** from them
so they can be rebuilt against the 3D stack. The original 2D sources are
recoverable from the last pre-removal commit:

```bash
git show c948b22:extensions/<name>.py      # extensions
git show c948b22:<name>.py                 # core 2D modules
```

**Already ported (do not re-do):** true 3D spherical-cap occlusion + δ̂ + Θ
(`occlusion_3d`), steric / blind-angle / anisotropic-body SI refinements,
`metrics_3d` (α, Θ, Θ′, L, dispersion), `correlation_time`, `h2_robustness`,
`flock_shape`, `ecology` (seasonal + critical mass + roosting + day-length +
temperature), `predator_3d`, `scenario_presets_3d`, `density_scaling`.

### 6.1 Behaviour / interaction extensions (still to do)

Each was a pure 2D force function (`pygame.Vector2` → force); the 3D rewrite
accepts/returns numpy 3-vectors and adds the z term. Formulas below give the 2D
original and its 3D generalisation. Domain centre `c = (W/2, H/2, D/2)`; `r̂`
denotes a unit direction; `s` a strength gain.

- **Threat + escape wave** (`threat.py`) — a scripted attacker dives at the swarm
  centre then egresses (approach→egress state machine, `|v_threat| ≤ 2v₀`); each
  bird flees with a linear-falloff force, and the alarm propagates neighbour-to-
  neighbour as a relaxation wave.
  - *Flee:* `F_flee = s·(1 − d/R_threat)·r̂_{i←threat}` for `d < R_threat`.
  - *Escape wave:* over the neighbour graph, sweep `a_i ← max(a_i, γ·max_{j∈N(i)} a_j)`
    (`sweeps≈4`), then scale each bird's flee gain by `a_i`.
  - *3D:* `r̂` and `v_threat` become 3-vectors; the wave is graph-based
    (dimension-agnostic). **Recommended richer predator** — supersedes the basic
    chase in `predator_3d`. Medium effort, high payoff.
- **Vacuole** (`vacuole.py`) — an orbiting repulsor carves a moving cavity.
  - *2D:* agent at `c + R_orbit·(cos φ, sin φ)`; `F = s·(1 − d/R_vac)·r̂_away`,
    `d < R_vac` (linear falloff, full at `d=0`).
  - *3D:* orbit on a (tilted) circle `c + R_orbit·(cos φ, sin φ, h·sin φ)`; `r̂_away`
    a 3-vector; render as a translucent sphere. More striking in 3D.
- **Shared wander** (`wander.py`) — a deterministic moving "wander centre" all
  birds drift toward.
  - *2D:* `dx = cos(0.53t + cos 0.37t)·0.84`, `dy = sin(0.47t + sin 0.41t)·0.72`,
    `û = (dx,dy)/|·|`, `centre = c + û·R·pulse(t)` with a breathing `pulse(t)`;
    `F = s·r̂_{i→centre}`.
  - *3D:* add a third composite-trig axis `dz = cos(0.61t + sin 0.29t)·0.7`, so
    `û ∈ S²` and `centre = c + û·R·pulse(t)`.
- **Leader anchors** (`leader.py`) — N anchors on Lissajous orbits; birds are
  drawn to the nearest within range.
  - *2D:* `anchor_i(t) = c + A·(sin(ω_i t + φ_x), cos(ω_i t + φ_y))`;
    `F = s·r̂_{i→anchor}` for the nearest anchor in range.
  - *3D:* a 3D Lissajous `anchor_i(t) = c + A·(sin(ω_i t+φ_x), cos(ω_i t+φ_y), sin(κω_i t+φ_z))`.
- **Flow field** (`flow_field.py`) — ambient wind with gusts and a slowly
  wandering direction.
  - *2D:* `ψ(t) = ψ₀ + 0.4 sin ωt + 0.25 cos 0.7ωt`; `F = strength·(cos ψ, sin ψ)`.
  - *3D:* azimuth `ψ(t)` and elevation `θ(t)`, each a wandering trig, give
    `F = strength·(cos θ cos ψ, cos θ sin ψ, sin θ)`.
- **Shell formation** (`shell_formation.py`) — birds orbit in concentric shells.
  - *2D:* radius bands `R_k`; `target = c + R_k·(cos α, sin α)`, `α` the orbit
    angle; `F = s·r̂_{i→target}`.
  - *3D:* **spherical shells** — `target = c + R_k·(sin φ cos α, sin φ sin α, cos φ)`;
    birds occupy nested spheres of radius `R_k`. More natural in 3D.
- **Inertia / turn smoothing** (`inertia.py`) — limits the per-frame heading
  change (`inertia ≈ 0.84`).
  - *2D:* blend headings `a₀ = atan2(v)`, `a₁ = atan2(desired)`, clamp `Δa` to a
    max turn rate.
  - *3D:* slerp the unit vectors — `v̂_new = normalize((1−k)v̂ + k d̂)`, or rotate
    `v̂` toward `d̂` by `min(∠(v̂,d̂), Δθ_max)`; `k` from the inertia constant.
- **Blob init** (`blob_init.py`) — clustered start positions, `p = c + σ·𝒩(0, I)`.
  Already supports `dims=3` (use `I₃`); just call it from `main_3d` init. Trivial.
- **Direct-velocity policy** (`direct_velocity.py`) — set the velocity directly
  from Pearce Eq. 3, `v_{t+1} = v₀·normalize(φp δ̂ + φa ⟨v̂⟩ + φn η̂)`, instead of
  Reynolds steering `a = clamp(v_desired − v, F_max)`. A policy toggle on
  `flock_projection_3d` (assign `boid.vel` vs `apply_force`). Small.

### 6.2 Metrics / analysis extensions (still to do)

- **Multi-viewpoint Θ′** (`multi_viewpoint_opacity.py`) — external opacity
  averaged over K observer viewpoints.
  - *2D:* viewpoints on a circle, `viewpoint_k = R_ext·(cos θ_k, sin θ_k)`,
    `θ_k = 2πk/K`; `Θ′ = (1/K) Σ_k` occluded-angle-fraction of the flock seen from
    `viewpoint_k`.
  - *3D:* viewpoints on a **sphere** of radius `R_ext` (Fibonacci lattice of K
    points); each rasterises the flock silhouette along its axis
    (`metrics_3d.external_opacity`); `Θ′ = mean` over the K viewpoints.
- **Empirical trajectory loader** (`data_loader.py`) — loads recorded bird
  trajectories and computes opacity from real data (experiment validation). The
  loader is format-only (dimension-agnostic); `compute_opacity` must call the 3D
  occlusion. Low priority unless validating against 3D datasets.
- **Far-field conservative occluder** (`spatial_optimization.py`) — a 10×7 chunk
  grid where near cells give exact per-bird occlusion and each far chunk
  contributes one bounding-circle occluder → `O(N_near + C)`. In 3D, only worth
  it if the analytic occlusion is too slow at large N: use a bounding **sphere**
  per far chunk. Otherwise skip — the 27-cell hash already bounds candidate cost.

### 6.3 UI / rendering / framework (still to do, optional)

- **`orchestration_3d` hub** — a flag-gated central place for extension state
  init + per-frame forces + overlay render, so `main_3d`'s loop stays
  extension-agnostic. Re-implement *after* a few 3D extensions exist (so the hub
  reflects real needs); target `renderer_3d` overlays + numpy `apply_force`.
- **In-frame HUD / help overlay** — the 3D build shows metrics in the window
  title bar only; a proper text overlay in `renderer_3d` (metrics readout,
  H-key controls panel) would fold in the removed `hud.py` / `help_overlay.py`.
- **Focal-bird debug overlay** (`focal_debug.py`) — visualise one bird's
  occlusion caps + δ̂ on a wireframe view sphere. Strong teaching aid; real work
  in 3D. Defer.
- **Themes** (`themes.py`) — palette concept survives but feeds GLSL uniforms /
  clear colour in `renderer_3d`, not pygame draw calls. Re-target, don't port.
- **Pilot state** (`pilot_state.py`) — scripted flock "pilot" (heading, radius,
  roll); heading → 3D direction or quaternion. Only if a scripted-leader camera
  is wanted.
- **`simulation_3d.update_frame()` extract** — optional refactor pulling the
  per-frame sequence out of `main_3d` for testability, as the 2D `simulation.py`
  did. Low priority.
- **Margin-boundary mode & velocity trails in 3D** — `Boid3D` has only toroidal
  wrap (plus the `OPEN_BOUNDARY` free-flight flag) and no trail history; add a
  reflective/margin boundary and a position ring-buffer if wanted. Trails also
  feed the adaptive-quality tier-1 toggle (§6.4).

### 6.4 Rendering / environment (still to do)

Two companion-derived (`*.ts`) systems that touch rendering and the ambient
medium rather than the flocking rule itself.

- **Adaptive quality** (`adaptive_quality.py`) — keeps the frame rate near a
  target by degrading rendering in progressive tiers, with hysteresis to prevent
  oscillation. Pure logic (no GL): fed the measured FPS + bird count each frame,
  returns the quality state.
  - *Math:* EMA `fps̄ ← fps̄ + α(fps − fps̄)` (`α = 0.1`). **Degrade** a tier when
    `fps̄ < target·0.78` (cooldown 1800 ms); **recover** when `fps̄ > target·0.92`
    (cooldown 3000 ms). The asymmetric thresholds (0.78 < 0.92) are the
    hysteresis. Tiers: **1** disable trails; **2** render scale −0.15 (floor
    0.75×); **3** bird count ×0.82 (floor 512).
  - *3D:* the decision logic ports unchanged; only the *actuators* change — tier
    2 → the ModernGL framebuffer/viewport resolution scale, tier 3 → the instance
    count uploaded to `renderer_3d`, tier 1 → the trail pass (see §6.3). Stays
    unit-testable with a synthetic FPS trace.
- **Medium presets** (`medium_presets.py`) — tune the *atmosphere* the flock
  moves through (independent of φp/φa/σ). Four media — **air**, **dust**,
  **starlight**, **grid** (reference: no perturbation) — each carrying
  turbulence, drift, particle density, jitter, and rendering hints.
  - *Math (per bird per frame):* turbulence `a_turb = c_turb · turbulence · η̂`
    (random unit vector `η̂`, `c_turb ≈ 0.15`); ambient drift `v += drift · d̂_wind`
    (a global "wind" bias). Plus `density` passive medium particles with random
    positional `jitter`, and render hints (`opacity`, point scale, colour mix).
  - *3D:* `η̂` is drawn uniformly on `S²` (as the projection-mode noise already
    is), `d̂_wind` is a 3-vector (azimuth + elevation); medium particles become 3D
    points; the render hints feed GLSL uniforms (alpha, `gl_PointSize`, colour
    blend) in `renderer_3d`. Overlaps with the flow field (§6.1) — `drift` is the
    steady component, `flow_field` the gusting one; a 3D build could unify them.

---

## 7. Scaling, rendering & validation ideas (roadmap / companion project)

These come from the **non-code** files at the pre-removal state — the README
"Implementation Roadmap" and the companion TypeScript/Three.js project it
references, plus the analysis notebook. They were prose specifications with *no*
2D code module, so they are preserved here (3D-adapted, with math) for the 3D
build to pick up. Recover the originals with `git show c948b22:README.md` and
`git show c948b22:notebooks/murmuration.ipynb`.

### 7.1 Large-flock scaling — field-based O(N) simulation

*(README Priority 11, companion `CpuMurmurationSimulation.ts`.)* Above a
threshold (~11k birds) the boids neighbour query (O(N·m)) dominates. The
companion switches to a **field / slot** method with no neighbour queries — O(N):

- **Slot assignment.** Birds are spread over A anchors: `numSlots = ⌈N/A⌉`,
  `slot_i = i mod numSlots`; each slot's target is `anchor + slotOffset(slot_i)`,
  where `slotOffset` places points by the **golden ratio** `ϕ=(1+√5)/2` for even
  spacing.
  - *3D:* the 2D "stratified offset on concentric rings" is exactly the
    **Fibonacci sphere** already in `occlusion_3d.fibonacci_sphere` — golden-angle
    points on nested spherical shells of radius `R_k`, so
    `slotOffset(i) = R_{k(i)}·fib_dir(i)`.
- **Slot repulsion** (replaces separation): for birds sharing a slot,
  `F_rep += r̂_{i←j}·(s_min − d)` when `d < s_min` (`r̂` a 3-vector in 3D).
- **Ripple propagation:** `ripple_i = A·sin(ωt + k·r_i + φ_i)` — a travelling wave
  with wave-vector `k`, per-bird phase `φ_i`; `k·r_i` is a 3-vector dot product in
  3D. Produces wave deformations with **no neighbour communication**.
- **Field velocity update:**
  `v_{t+1} = inertia·v_t + (1−inertia)·[ chase·slotPull + coh·blobAttract + align·headingBias + flow·field(r) + noise·η̂ ]`,
  with `slotPull = normalize(target − r)·shellError`. There is **no local
  separation/alignment** — cohesion and alignment become global biases; slot
  repulsion handles spacing.
- *3D switch:* add a `FIELD` mode beside `PROJECTION`/`SPATIAL`, auto-selected
  when `N > threshold`. Everything is already 3-vector-friendly and the slot
  shells reuse `fibonacci_sphere`.

### 7.2 GPU compute offload

*(README Priority 9, companion WebGL/WebGPU.)* Move the per-bird force
integration onto the GPU for 30k–50k+ birds.

- **Texture-state / ping-pong (WebGL2 / GLES):** state stored as textures
  `pos[slot]=(x,y,z,1)`, `vel[slot]=(vx,vy,vz,1)`; slot→uv by `w=⌈√N⌉`,
  `uv=((slot%w+0.5)/w, (⌊slot/w⌋+0.5)/h)`; a fragment shader reads neighbours from
  the read texture and writes new state to the write texture, swapping read/write
  each frame. Already 3D (RGBA carries z).
- **Compute shaders (WebGPU / GL 4.3):** in/out `array<Particle>` storage buffers,
  `@workgroup_size(256)`, no texture round-trip.
- *3D fit:* the state layout is dimension-agnostic; the **hard part is the
  projection occlusion** — `occlusion_3d`'s per-bird cap sort is not a fixed-size
  loop, so a GPU port would either (a) build a bounded neighbour list on the CPU
  and only integrate on the GPU, or (b) approximate occlusion with a capped
  neighbour set. `renderer_3d` already streams pos+vel per instance, so only the
  integration moves to the GPU; ModernGL exposes compute shaders on GL 4.3 hosts.

### 7.3 Trail rendering

*(README Priority 14, companion `TrailLines.ts` / `accumulation.ts`.)* Two ways to
give the flock motion history; both feed the adaptive-quality tier-1 toggle (§6.4).

- **Geometric trails:** each bird draws `S` segments behind it. For segment
  `s∈[0,S)`, `t=s/(S−1)`, `trailPos = r − v̂·(t·L)` (`L` the trail length). A
  sinusoidal **wave offset** `A·sin(|v|·waviness + seed)` displaces each point
  perpendicular to `v` so the trail reads as an organic ribbon.
  - *3D:* store a per-bird position ring buffer (§6.3); the perpendicular is any
    unit vector ⟂ `v̂` — e.g. `normalize(v̂ × ê_up)`, falling back to `ê_x` when
    parallel (the same guard `renderer_3d`'s `lookAtRotation` already uses).
    Render the segments as GL lines in one batched draw.
- **Frame accumulation (ghosting):** don't clear the framebuffer; each frame blend
  a translucent background-coloured full-screen quad over it, so old positions
  fade geometrically (`α_n = (1−β)^n` after n frames). In ModernGL: disable the
  clear and draw a fullscreen quad with alpha `β` before the birds.

### 7.4 Headless validation & analysis

**Done — `notebooks/murmuration.ipynb`.** A runnable 3D analysis notebook drives
the science modules headlessly (`%matplotlib inline`, no GPU) and plots four
things: (1) the order parameter α(t), internal/external opacity Θ/Θ′ and
dispersion as the flock self-organises — via the new `simulation_3d.World`;
(2) consensus robustness H₂(m) with the cost-optimal m\* (Young); (3) the
shape-driven suggested m\* for thin vs round flocks (`flock_shape`); and (4) the
density-scaling exponent fit (`density_scaling`, §4.9). It is committed with its
executed outputs so it renders on GitHub, and it re-runs from either the repo
root or `notebooks/`. The gated integration tests in `run_tests.sh` exercise the
same modules programmatically.

**Already done:** README Priority 13 (companion `cpuSpatialHash.ts` — a
string-keyed 3D hash with 27-cell queries) is implemented by
`spatial_grid_3d.SpatialGrid3D` (tuple keys, 3×3×3 queries); the only companion variant
not adopted — *no toroidal wrap + boundary push-back* — is partially provided by
the `OPEN_BOUNDARY` free-flight flag (§4.9).
