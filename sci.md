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
(centroid) direction is `d̂_j` and whose boundary length ∝ `sin α_j`, so:

```
δ̂ = normalise( Σ_{visible j}  sin α_j · d̂_j )
```

`δ̂` is **cohesive** — it points toward the silhouette edges — and occlusion
gates it (hidden birds drop out), which is the mechanism that yields *marginal
opacity*. (Note: averaging the **unoccluded** sky instead would give the opposite
sign — a "flee to open sky" separation force — and is *not* the Pearce model.)

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
| Scenario presets (φp, φa, σ regimes) | — | `scenario_presets_3d.py` |
