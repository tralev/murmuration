# Testing Reference — 3D Murmuration

What is tested, **the math each check asserts**, and the testing *ideas* carried
over from the pre-removal 2D/multi-language suite (last seen at commit
`c948b22`), adapted to the 3D stack. Companion to [`sci.md`](sci.md) (the
science) and [`README.md`](README.md) (the stack).

Recover any original 2D test with `git show c948b22:<name>.py`.

---

## 1. Test layout

| Category | File | Contents |
|----------|------|----------|
| **python** | `test_3d.py` | physics, spatial grid, the two flocking modes, boundary modes |
| **python** | `test_science_3d.py` | the paper-grounded science modules (occlusion, metrics, ecology, Young, density scaling) |
| **python** | `test_ui_3d.py` | the non-science stack testable without a display: `OrbitCamera` (pure glm), `input_handler_3d` (mocked events), `shaders_3d`, `features` |
| **python** | `test_render_3d.py` | `renderer_3d` via a headless ModernGL FBO (one real frame + read-back, instance packing, resize); self-skips where no GL driver exists |
| **python** | `test_simulation_3d.py` | `simulation_3d.World` — the headless per-frame loop main_3d drives: flock-size edits (+/-/R), the physics/metrics step, predator + roosting hooks |
| **python** | `test_docs_3d.py` | doc-drift guards: README module names, `sci.md#anchor` links, and the run_tests.sh module list all resolve |
| **sh** | `run_tests.sh` | the shared gate: syntax check (`py_compile` every module) + `unittest` over the six modules. `RUN_SLOW_TESTS=1` adds the gated integration tests; `COVERAGE=1` runs under coverage and enforces `COVERAGE_MIN` (default 95 %) |
| **docker** | `docker_test.sh` | build image → run tests in-image → headless smoke-launch (§5) |
| **ci** | `.github/workflows/test.yml` | Python-version matrix (RUN_SLOW + COVERAGE on) + the Docker job (§6) |
| **hook** | `.githooks/pre-commit` | runs `run_tests.sh --quiet` before every commit |

`test_3d` / `test_science_3d` / `test_simulation_3d` / `test_docs_3d` are **pure
numpy/scipy**; `test_ui_3d` also needs `pygame` / `glm` / `moderngl` importable
but **never opens a display or GL context** (events are mocked, the camera is
pure maths). Most tests use a duck-typed **stub boid** (`_StubBoid` — numpy Vec3
`.pos`/`.vel` + `.last_theta`) so nothing needs a `Boid3D`, a grid, or a GPU.

### Coverage

`COVERAGE=1 RUN_SLOW_TESTS=1 ./run_tests.sh` → **≈99 %** of the headless-testable
code, enforced by a `coverage report --fail-under=95` gate (CI sets both flags).
Every science and logic module sits at 99–100 %; the only unhit lines are the
`density_scaling` `__main__` entry point, one provably unreachable defensive clip
in `metrics_3d.external_opacity`, and the `World` verbose-print branch. The floor
**omits** the three GL-context modules (`renderer_3d`, `main_3d`, `capture_3d`),
because `test_render_3d` self-skips on a bare CI runner with no OpenGL — leaving
them imported-but-unexecuted; they are exercised by the Docker **smoke-launch**
(§5) instead (and `renderer_3d` hits 100 % locally where a GL context exists).

---

## 2. What is tested — areas and their math

Each subsection lists the assertion math and whether the 3D suite already
covers it (✅) or it is an area to add (⬜, mapped from the 2D suite).

### 2.1 Physics & boundaries — ✅ `TestBoid3DUpdate`

- **Toroidal wrap**, per axis `a ∈ {x, y, z}` with extent `L_a ∈ {W, H, D}`:
  `p_a > L_a ⟹ p_a ← 0`;  `p_a < 0 ⟹ p_a ← L_a`. (2D wrapped only x, y — the
  3D check adds z.)
- **Speed clamp** to the band `|v| ∈ [0.3·V₀, V₀]`: a bird faster than `V₀` is
  rescaled to `V₀`; slower than `0.3·V₀` up to `0.3·V₀`; a frozen bird
  (`|v| ≈ 0`) is re-seeded with a random unit heading.
- **Open boundary** (`OPEN_BOUNDARY=True`, §4.9 of sci.md): positions are left
  untouched — assert no wrap occurs. Restored via a context manager (⬜ a direct
  `TestBoid3DUpdate` case for the open branch would complement the analysis-side
  `test_open_boundary_context_restores`).
- **Margin boundary** (2D `test_boundary.py`): inward nudge within a margin,
  hard clamp outside. 3D `Boid3D` keeps the code (off by default) — ✅
  `test_margin_mode_nudges_all_six_walls` asserts the inward nudge sign at
  every wall (±x, ±y, ±z), `test_margin_mode_nudges_and_clamps` the clamp.

### 2.2 Spherical-cap occlusion — ✅ `TestSphericalCapOcclusion`, `…BlindAngles`, `…AnisotropicBodies`

The 2D angular-interval merge (`test_occlusion.py`: `_normalise_interval`,
`_interval_covered`, `_merge_interval`) becomes cap union on the view sphere.

- **Cap geometry:** neighbour at distance `d`, body radius `b` ⟹ angular radius
  `α = asin(min(b/d, 1))`; a view direction `v̂` is inside iff `v̂·d̂ ≥ cos α`.
  *Asserted:* a lone neighbour at `(100,0,0)` gives `δ̂ ≈ (1,0,0)`; one purely
  above gives `δ̂_z > 0.9` (impossible for the old XY-plane projection).
- **Closest-first visibility:** a farther bird directly behind a nearer one is
  hidden → `len(visible) == 1`; two angularly separated birds → both visible.
- **Internal opacity** `Θ = 1 − Π_{visible}(1 − Ω_j/4π)`, `Ω_j = 2π(1−cos α_j)`.
  *Asserted:* `Θ` rises with more neighbours and stays `≤ 1`.
- **Blind cone** (half-angle `β/2`, default 60°): a neighbour is dropped when
  `d̂·(−ĥ) ≥ cos(β/2)` (ĥ = heading). *Asserted:* a bird directly behind is
  invisible with the cone on, still visible with it off.
- **Anisotropic body:** silhouette radius `b_eff = √((a·sinψ)² + (b·cosψ)²)`,
  `cosψ = |d̂·ĥ_j|`, `a = b·anisotropy`. *Asserted:* broadside `Θ` > end-on `Θ`;
  `anisotropy = 1` reproduces the isotropic result.
- **δ̂ magnitude** (the density-regulation signal, sci.md §4.1):
  `δ̂ = Σ_vis sinα·d̂ / Σ_vis sinα`, `|δ̂| ∈ [0,1]`. ✅
  `test_delta_magnitude_encodes_edge_vs_surrounded` pins the marginal-opacity
  mechanism: |δ̂| < 10⁻⁶ for a symmetric octahedral surround, > 0.9 with all
  neighbours to one side, and exactly 1 for a single visible neighbour.

### 2.3 Projection & spatial flocking modes — ✅ `TestFlockProjection3D`, `TestFlockSpatial3D`, `TestSpatialGrid3D`

- **Projection (Pearce):** desired `v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂`, then Reynolds
  steer `a = clamp(v_desired − v, MAX_FORCE)`. *Asserted:* visible list sorted by
  distance; alignment over the σ nearest visible; determinism given a fixed seed.
- **Spatial (Reynolds) in 3D:** separation pushes away (`F·r̂_{i←j} > 0` for a
  close neighbour), cohesion points toward the neighbour centroid, σ caps the
  neighbour count, a neighbour at exactly `VISUAL_RANGE` is excluded, every
  steering term is clamped to `MAX_FORCE`.
- **Spatial hash:** 27-cell (`3×3×3`) queries return the right candidates;
  Euclidean distance filtering (not minimum-image) so a drifting/open flock is
  handled; rebuild is O(N).

### 2.4 Metrics (Pearce observables) — ✅ `TestOrderParameter`, `…ExternalOpacity`, `…AngularMomentumDispersion`, `TestFlockMetrics3D`

- **Order parameter** `α = |Σᵢ v̂ᵢ| / N ∈ [0,1]`; a perfectly aligned flock → `1`.
- **External opacity** `Θ′` = silhouette coverage: rasterise each bird as a disk
  of radius `b` onto the plane ⟂ the observer axis; `Θ′ = covered / total`.
- **Angular momentum** `L = |Σ rᵢ × vᵢ| / (N·V₀·R)` — large for a mill, ~0 for a
  stream (the 3D cross product replaces the 2D scalar `r×v`).
- **Dispersion** `σ_r = mean|rᵢ − c|`. **EMA smoothing** `x ← x + s(x_raw − x)`
  (`s = 0.04`): asserted to converge to the raw value.
- **Correlation time τρ** (✅ `TestCorrelationTime3D`): density `ρ = N /
  volume(ConvexHull)` (3D — the 2D used hull *area*); `τρ = ∫ C_ρρ(Δt)/C_ρρ(0) dΔt`
  over a ring buffer.

### 2.5 SI refinements — ✅ `TestStericRepulsion`

- **Steric** `F = φ_s · Σ_{d<r_s} r̂_{i←j} / d²`, `r_s = 4b`, clamped to
  `MAX_FORCE`. *Asserted:* pushes away from a close bird, closer pushes harder
  (`1/d²`), zero beyond `r_s`. (Blind + anisotropy are in §2.2.)

### 2.6 Behavioural dynamics & ecology — ✅ `TestPredator3D`, `TestRoostingDaylight`, `TestEcology`

- **Predator:** chases the swarm centre (distance to it decreases over steps);
  **flee** `F = φ · (1 − d/R_d) · r̂_away` for `d < R_d` — away from the raptor and
  stronger when nearer; zero beyond `R_d`.
- **Roosting / day length:** `L(day) = L̄ + A·cos(2π(day−solstice)/365)` peaks at
  the solstice; sunset `= 12 + L/2`; a logistic **dusk factor** rises 0→1 across
  sunset (0.5 at sunset); `F_roost = φ·dusk(hour)·r̂_{→roost}` — zero by day, pulls
  toward the (low-z) roost after sunset; temperature coldest in winter.
- **Ecology:** seasonal size raised-cosine in `[0.25, 1]` peaking mid-January;
  ~500-bird critical-mass gate; ~29.6 % predator presence.

### 2.7 Consensus & shape (Young) — ✅ `TestH2Robustness3D`, `TestFlockShape3D`

- **H₂ robustness:** k-NN graph Laplacian `L = D − A`; symmetric eigenvalues
  `0 = λ₁ ≤ λ₂ ≤ …`; `H₂² = (1/2N) Σ_{i≥2} 1/λᵢ`; per-neighbour efficiency `η(m)`
  and a **cost-optimal `m* ≈ 6–7`** balancing robustness against O(m) sensing
  cost. Uses `scipy.spatial.cKDTree` + `numpy.linalg.eigvalsh` — fed 3D positions
  it works unchanged.
- **Flock shape:** PCA of the `3×3` position covariance (`numpy.cov` + `eigh`) →
  three principal axes → thickness/aspect ratio → interpolated `m*` in
  `[6.05, 9.78]` (thin ↔ round). The 2D `2×2` covariance generalises to `3×3`.

### 2.8 Density scaling & marginal opacity — ✅ `TestMarginalOpacity`, `TestDensityEstimators`, `TestDensityScaling` (slow-gated)

New in the 3D stack (no 2D antecedent). Asserts the estimator math
(`local_spacing` = median k-NN distance; median-centred, tail-trimmed gyration
radius) and that a settled flock reaches the marginal band, and that the
open-boundary scaling sweep returns finite exponents (fit `ρ ~ N^p` against the
Pearce target `−1/2`; see sci.md §4.9). Gated behind `RUN_SLOW_TESTS` because it
runs the dynamics to condensation (~25 s).

### 2.9 Presets — ✅ `TestScenarioPresets3D`

Every preset yields a valid weight split `φp + φa ≤ 1` (so `φn = 1−φp−φa ≥ 0`);
presets are visually distinct; a bad key is a no-op. ⬜ the 2D **toggle
round-trip** (`_save_config`/`_restore_config`: same key restores, different key
overwrites, a manual tweak invalidates the snapshot) is not yet ported — worth
adding if the 3D handler gains preset save/restore.

---

## 3. Testing patterns & ideas to carry forward

Ideas from the 2D/multi-language suite worth adopting in 3D:

### 3.1 Test-count discovery gate  (✅)

Every 2D module carried a `TestDiscovery` class whose single test asserted the
module's **exact test count**, and `scripts/check-test-count.sh` / CI stage 2 ran
them in ~1 ms as a fast gate. It catches *silently dropped* tests (a renamed or
mis-indented method that `unittest` no longer discovers). Adopted: each of the
six test modules ends with a `TestDiscovery` class asserting
`TestLoader().loadTestsFromModule(m).countTestCases()` equals its pinned count
(update the pin when tests are deliberately added or removed).

### 3.2 Determinism / golden reference  (✅, replaces cross-language parity)

The 2D suite proved **Python ≡ Octave ≡ Scilab** produced identical results
(`test_cross_language.py`, `.m`/`.sce` tests, `validate-all.sh`) — a golden
reference across languages. The 3D repo is Python-only, so that parity is moot;
its successor is **seeded determinism**: same `random.seed`/`np.random.seed` ⟹
identical trajectory (2D had `test_deterministic_given_same_positions`). Adopted:
`test_3d.TestDeterminism` runs 15 birds for 30 frames twice (switching
projection → spatial halfway) and asserts bit-identical positions *and*
velocities, guarding against hidden global-state leaks.

Adopted, part two — the **golden reference** itself:
`test_3d.TestGoldenTrajectory` compares the same seeded run against the
committed `golden_trajectory_3d.npz` snapshot (atol 1e-3 — libm ulp differences
across platforms amplify through the dynamics, so bit-exactness is asserted
only within a version). Determinism catches disagreement *within* a version;
the golden file catches an unintended physics change *between* versions. After
a deliberate change, re-pin with
`python3 -c "import test_3d; test_3d.regenerate_golden()"` and say so in the
commit message.

### 3.3 Feature-flag / import guards  (resolved — not applicable)

`test_features.py` used **subprocess** to assert import-time behaviour — e.g.
disabling a model flag means its module is *never imported* (`ENABLE_3D=False`
raises on GL import), exactly N flags exist, defaults are correct. Audited
2026-07: the 3D `features.py` flags (`ENABLE_PROJECTION_MODE` /
`ENABLE_SPATIAL_MODE`) are **declarative only — no module reads them**, so
there is no import-time behaviour to guard; `test_ui_3d.TestFeatures` already
pins their existence and defaults. Adopt the subprocess pattern only if a flag
ever actually gates an import.

### 3.4 Slow-test gating  (✅)

Integration tests that must run the dynamics (`TestMarginalOpacity`,
`TestDensityScaling`) are decorated `@skipUnless(os.environ.get("RUN_SLOW_TESTS"))`
so the pre-commit gate stays ~0.3 s while CI (which sets the flag) still runs
them. Keep new ≥1 s tests behind the same flag.

### 3.5 Duck-typed stub boids  (✅)

Tests inject a minimal `_StubBoid(pos, vel, last_theta)` rather than a real
`Boid3D`, so the science functions are tested in isolation with no grid, no
physics loop, and no GPU. Keep new science pure and stub-testable.

### 3.6 Property / metamorphic tests  (✅)

Beyond fixed examples, invariants are fuzzed over many random configurations:
`test_3d.TestPhysicsInvariants` asserts the speed band (`|v| ≤ V0` always; the
`0.3·V0` floor rescales slow birds) and toroidal position bounds after
`update()`; `test_science_3d.TestMetricInvariances` asserts the *symmetries* the
observables claim — the order parameter is invariant under a global rotation of
all velocities (and = 1 for aligned, ∈ [0, 1] always), dispersion is invariant
under a global translation; `test_science_3d.TestOcclusionInvariants` fuzzes the
occlusion contract (|δ̂| ≤ 1, Θ ∈ [0, 1], visible closest-first, blind-cone
respected, `anisotropy = 1` ≡ isotropic). Metamorphic checks catch
frame-of-reference and numeric bugs that hand-picked cases miss.

### 3.7 Headless simulation loop  (✅)

The per-frame update logic lives in `simulation_3d.World`, factored out of
`main_3d`'s render loop so it runs with no window or GL context.
`test_simulation_3d` drives it directly: flock-size edits (add grows; remove
never empties the flock and spreads leftover across frames; reset restores
`NUM_BOIDS` and rebuilds the grid), the physics/metrics step, and the
behavioural hooks (a predator perturbs the trajectory; roosting advances the
day-clock and pulls the flock down). `main_3d` is now a thin input+render driver.

### 3.8 Doc-drift guards  (✅)

`test_docs_3d` keeps the code↔doc map honest: every ``module.py`` named in the
README resolves to a real file, every section-anchor link into `sci.md` (across
README / sci.md / tests.md) points at a real heading (GitHub's slug algorithm),
and every module in `run_tests.sh`'s `MODULES` list exists. A rename that breaks
the map fails the gate instead of rotting silently.

### 3.9 Enforced coverage floor  (✅)

`COVERAGE=1 ./run_tests.sh` runs the suite under `coverage` and fails if the
headless-testable code drops below `COVERAGE_MIN` (default 95 %). CI sets it
alongside `RUN_SLOW_TESTS=1`. See the [Coverage](#coverage) note for what the
floor omits and why.

---

## 4. Docker testing — `docker_test.sh`

One host-side script is the single source of truth for "test the image":

1. **build** — `docker build -t <tag> .` (the `COPY *.py *.sh` layer puts the
   whole stack + `run_tests.sh` in the image).
2. **unit tests in-image** — `docker run --rm <tag> python -m unittest test_3d test_science_3d`, proving the pinned dependency set (numpy, scipy, pygame, moderngl, PyGLM) imports and passes.
3. **headless smoke-launch** — the 3D sim has no fixed exit, so run it a few
   seconds under **Xvfb + Mesa software GL** (`timeout 15 xvfb-run -a python -u
   main_3d.py`) and assert it reached the main loop (printed its `"Murmuration
   3D"` banner) without crashing on the ModernGL context. This is the only test
   that exercises the GL path; there is no GPU in CI, so Mesa's `llvmpipe`
   software rasteriser serves the context.

`docker-compose.yml` exposes the same image three ways — `murmuration` (run the
sim), `tests` (`./run_tests.sh -v`), `shell`.

## 5. CI pipeline — `.github/workflows/test.yml`

Two jobs, both thin delegators to the scripts above (the 2D CI had three inline
stages: syntax → **test-count gate** → full suite; the count gate is the piece to
re-add per §3.1):

- **tests** — a Python-version **matrix** (`3.9 … 3.12`) on `numpy + scipy` only,
  running `./run_tests.sh -v` with `RUN_SLOW_TESTS=1` (so the gated integration
  tests run where time is cheap).
- **docker** — `./docker_test.sh murmuration:ci` (build + in-image tests + smoke).

## 6. Local scripts & hooks

- **`run_tests.sh`** — the syntax + unit gate (also the pre-commit hook and the
  compose `tests` command).
- **`docker_test.sh`** — the Docker gate (§4).
- **pre-commit hook** — enable once per clone with
  `git config core.hooksPath .githooks` (the 2D repo had `scripts/install-hooks.sh`
  for this; a tracked `core.hooksPath` replaces it). Bypass with
  `git commit --no-verify`.
- **`validate-all.sh` (retired)** — the 2D full-pipeline runner drove Python +
  Octave + Scilab, native and Docker, skipping unavailable toolchains. With the
  stack Python-only, `run_tests.sh` + `docker_test.sh` cover its role.
