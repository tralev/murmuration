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
| Spherical-cap occlusion (+ blind angles, anisotropy), δ̂, Θ | Pearce §1–2, SI §4.7 | `occlusion_3d.py` |
| Projection / spatial flocking modes | Pearce Eq. 3 | `spatial_3d.py` |
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
`spatial_3d` / numpy Vec3 state. Commit `6b71b15` removed the 2D simulation, and
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
accepts/returns numpy 3-vectors and adds the z term. Wire into `spatial_3d`
force accumulation or the `main_3d` loop.

| Feature | What it does | 3D rewrite notes | Effort |
|---------|--------------|------------------|--------|
| **Threat + escape wave** (`threat.py`) | Scripted attacker dives at swarm centre then egresses; flee response propagates neighbour-to-neighbour as a relaxation wave | `ThreatAgent` pos/vel → 3-vector; `escape_wave` is graph-based (dimension-agnostic). **Recommended richer predator model** — supersedes the basic chase in `predator_3d` | Medium, high payoff |
| **Vacuole** (`vacuole.py`) | Orbiting repulsor carves a moving cavity in the flock (`1/d²` radial push) | Agent orbits swarm centre with a z component; force is a clean 3-vector; render as a translucent sphere/ring. More striking in 3D | Medium |
| **Shared wander** (`wander.py`) | Deterministic moving "wander centre" (composite-trig noise + breathing radius) all birds drift toward | Add a third composite-trig axis → `(cx,cy,cz)` scaled by `DEPTH` | Low |
| **Leader anchors** (`leader.py`) | N anchor points on Lissajous orbits; birds drawn to the nearest in range | Add z Lissajous term; 3D distance; draw 3D markers | Low/med |
| **Flow field** (`flow_field.py`) | Ambient wind with gusts + slowly wandering direction | Wind direction → 3-vector (azimuth + elevation) | Low |
| **Shell formation** (`shell_formation.py`) | Birds orbit a leader in concentric shells | Becomes **spherical shells** (radius bands); orbit along a 3D tangent — more natural in 3D | Medium |
| **Inertia / turn smoothing** (`inertia.py`) | `blend_inertia(vel, desired, 0.84)` + turn-rate limit | Works on 3-vectors as-is once the `_xy` helper is generalised | Trivial |
| **Blob init** (`blob_init.py`) | Clustered start positions | Already supports `dims=3`; just call it from `main_3d` init | Trivial |
| **Direct-velocity policy** (`direct_velocity.py`) | Set `v = φp·δ̂+φa·⟨v̂⟩+φn·η̂` directly (Pearce Eq. 3) instead of Reynolds steering | A policy toggle on `flock_projection_3d` (assign `boid.vel` vs `apply_force`) | Small |

### 6.2 Metrics / analysis extensions (still to do)

| Feature | What it does | 3D rewrite notes |
|---------|--------------|------------------|
| **Multi-viewpoint Θ′** (`multi_viewpoint_opacity.py`) | External opacity averaged over K observer viewpoints (2D: circle) | Viewpoints become points on a **sphere** around the flock, each casting the 3D occlusion; builds on `metrics_3d.external_opacity` |
| **Empirical trajectory loader** (`data_loader.py`) | Loads recorded bird trajectories, computes opacity from real data (experiment validation) | Loader is format-only (dimension-agnostic); `compute_opacity` must call the 3D occlusion. Low priority unless validating against 3D datasets |
| **Far-field conservative occluder** (`spatial_optimization.py`) | Distant chunks contribute one bounding-circle occluder → `O(N_near + C)` | Only if true 3D occlusion is too slow at large N: bounding **sphere** per far chunk. Otherwise skip (the 27-cell hash already bounds cost) |

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
  reflective/margin boundary and a position ring-buffer if wanted.
