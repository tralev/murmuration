---
name: murmuration
description: >
  Take a legacy codebase or algorithm, enrich it with scientific paper research,
  implement new features from the literature, port to multiple languages (Python,
  GNU Octave, Scilab), refactor for student readability, and produce comprehensive
  documentation including paper audits, implementation roadmaps, and user guides.
  Use when the user has code implementing a scientific model and wants to evolve
  it based on research papers, make it educational, or port it to other platforms.
license: GPL-3.0
compatibility: "Python 3.7+, GNU Octave 4.0+, Scilab 6.0+"
metadata:
  keywords: ["scientific computing", "code modernization", "multi-language porting",
             "educational refactoring", "research-to-code", "documentation"]
  estimated-duration: "Multi-session (hours)"
  output-files: ["Python modules", "GNU Octave script", "Scilab script",
                 "README files", "User guide", "Unit tests", "Agent skill"]
---

# Scientific Code Modernization

Take an existing codebase implementing a scientific model or algorithm. Research
the relevant academic literature, identify papers that propose extensions or
improvements, implement those ideas, then port the result to multiple languages
and refactor everything for use as educational material.

---

## When to Use This Skill

- You have working code for a scientific model (flocking, agent-based simulation,
  physics, numerical method, etc.)
- The user wants to **evolve** the code based on new research papers
- The user wants the result to be **understandable by students**
- The user needs **multi-language ports** (Python + GNU Octave + Scilab)
- The user wants **comprehensive documentation**: paper audits, roadmaps,
  user guides, and per-language READMEs

---

## Workflow — Step by Step

### Phase 1: Audit the Existing Code and Research Papers

1. **Read the existing code thoroughly.** Understand the algorithm, data flow,
   and all edge cases before touching anything.

2. **Find all research papers in the project directory.** Check for PDFs, HTML
   files, extensionless text files. Use `pdftotext` to extract text from PDFs
   if PyPDF2 is not available. Identify each paper by title, authors, journal,
   and year.

3. **Extract every scientific claim from each paper** that is relevant to the
   code. For each claim, note:
   - The equation or formalism (copy exactly from the paper)
   - The parameter values used
   - Any emergent properties the paper predicts
   - Extensions described in supplementary information

4. **Cross-reference every claim against the code.** Produce a table with
   three statuses:
   - ✅ **Fully implemented** — code matches the paper
   - ⚠️ **Partially implemented** — present but deviates (document the deviation)
   - ❌ **Not implemented** — claim exists in the paper but not in the code

   For each ⚠️ and ❌, write a specific note explaining the gap.

---

### Phase 2: Implement Missing Features and Fix Deviations

5. **Prioritise the primary paper first.** The paper the code was originally
   based on gets priority. Fix any deviations (⚠️) before adding new features.

6. **Add a user guide separate from scientific documentation.** Create a file
   like `USER_GUIDE.md` that covers ONLY practical matters:
   - Dependencies and requirements
   - Installation steps
   - How to run
   - Controls reference
   - Tuning guide
   - Troubleshooting
   - FAQ
   - **No math equations. No paper citations.** Pure practical content.

7. **Document what can't be implemented.** For each ❌ claim, write a brief
   explanation in the implementation roadmap of what would be required
   (formulas, algorithms, complexity estimate).

---

### Phase 3: Port to Multiple Languages

8. **Choose a consistent internal structure across all languages.** Design
   a unified section ordering before writing any code. Every section uses
   the same `╔═╗` box-drawing banner format with:
   - Section number and name
   - Reference to the paper, equation number
   - What math is used and why
   - What loops exist and what is their purpose
   - Algorithmic complexity (e.g., O(N log N))

   Example banner:
   ```
   # ╔══════════════════════════════════════════════════════════╗
   # ║  SECTION 5 — PROJECTION MODEL  (MODE 0)                 ║
   # ╚══════════════════════════════════════════════════════════╝
   #
   #  Reference:  Pearce et al. (2014), Eq. (3):
   #    v_i(t+1) = φp · δ̂_i(t) + φa · ⟨v̂_j(t)⟩_visible + φn · η̂_i(t)
   #
   #  δ̂_i  — unit vector to nearest boundary of occluded domain.
   #  Θ_i  — internal opacity, cached and reused by metrics.
   #
   #  Steps: 1–5 with per-step complexity.
   # ───────────────────────────────────────────────────────
   ```

   The unified section numbering makes cross-language comparison easy:
   a student can look at Section 5 in Python, then Section 5 in Octave,
   and find the same content with the same structure.

   | Section | Content |
   |---------|---------|
   | 1 | Header and overview |
   | 2 | Configuration constants |
   | 3 | Runtime state / data structures |
   | 4 | Utility functions |
   | 5 | Core algorithm A (e.g., projection model) |
   | 6 | Core algorithm B (e.g., spatial/alternative model) |
   | 7–8 | Metrics / derived quantities |
   | 9 | Physics / update step |
   | 10 | Help / display |
   | 11 | Input handling |
   | 12 | Main loop |
   | 13 | Shutdown |

9. **Write the Python reference implementation first.** This is the most
   readable language and will be the reference for the others.

10. **Port to GNU Octave.** Key differences to handle:
    - No classes → use parallel N×2 matrices (`pos`, `vel`, `acc`) instead
    - Rendering is slow → batch all draw calls into a single `patch()` call
      with 3×N vertex matrices
    - Keyboard input → use figure `KeyPressFcn` callback with pending flags
    - Text overlays → create persistent handles once, update `.String` each frame
    - State changes → use pending flags set in the async callback, applied
      atomically in the main loop

11. **Port to Scilab.** Similar to Octave but note:
    - Use `//` comments instead of `%`
    - Use `modulo()` instead of `mod()` for wrap-around
    - Rendering → use `xfpolys()` with NaN-separated vertices for batch drawing
    - Keyboard → figure event handlers with `event_handler_enable = "on"`
    - Use `sleep(1)` (1 ms) before `drawnow()` to yield the event loop

---

### Phase 4: Add Educational Features (if applicable)

12. **Split monolithic files into modules.** Dependency order should form a
    clean DAG (no circular imports). Example split:
    ```
    occlusion_geom.py   → math only (pure functions)
    flock_core.py       → constants + data structures
    boid.py             → agent class with algorithm logic
    metrics.py          → scientific metrics + display
    scenario_presets.py → educational preset configurations
    alg2.py             → entry point (main loop, ties everything together)
    ```

13. **Create a minimal version for students to read first.** ~75 lines, single
    file, zero external imports (besides the necessary library like Pygame).
    Implement only the core algorithm. This is the "read in 5 minutes" version.

14. **Add scenario presets.** Number keys that set parameter combinations to
    demonstrate specific behaviors (e.g. pure alignment, gas-like exploration,
    the canonical paper defaults). Each preset prints a one-line explanation.

15. **Add a focal agent debug view.** Let users click an agent to see its
    internal state rendered in real time — vectors, computed quantities,
    occlusion data. This turns abstract math into visible geometry.

16. **Add "teaching moment" callouts.** Use a consistent marker like `🎓` that
    students can grep for. At key decision points in the algorithm, add a
    3–5 line comment explaining *why* this choice was made, referencing the
    empirical finding or mathematical property that motivates it.

17. **Write unit tests for pure functions.** Anything that doesn't require the
    simulation runtime (e.g., math utilities). Mock any display library.
    Target 40+ tests covering edge cases: empty input, epsilon tolerance,
    wrap-around, chain merging, bridging.

---

### Phase 5: Documentation

18. **Create a main README.md** with:
    - Quick start and runtime controls
    - Algorithm explanation with the key equation(s) and code excerpts
    - Scientific metrics reference
    - **Paper-to-code implementation audit** (complete cross-reference table)
    - **Implementation roadmap** with formulas for future work (3 priority tiers)
    - Code tour showing module structure and dependency graph
    - **Historical comparison table** — old code vs new code (neighbourhood type,
      behaviour model, performance, metrics, comments). Shows what the
      modernisation achieved.
    - References to all papers with DOIs
    - GPLv3 license notice

19. **Create per-language READMEs** (OCTAVE_README.md, SCILAB_README.md).
    Each must be self-contained — a Scilab user should not need to open
    the Octave README. Every per-language README must include:
    - GitHub repository URL
    - GPLv3 license reference
    - Reference to the original algorithm or code that was modernised
    - Scientific paper citations with DOIs
    - Language-specific architecture (data representation, rendering, input)
    - **Condensed audit tables** (cross-reference the main README for details)
    - **Condensed roadmap** (cross-reference the main README for formulas)
    - What's implemented from each paper and what's not (✅/⚠️/❌)

20. **Create the user guide** (`USER_GUIDE.md`) with zero math and zero
    paper references. Pure practical: install, run, controls, tuning, FAQ.

21. **Create this agent skill** (`SKILL.md`) capturing the entire workflow
    so it can be reused for other codebases.

---

### Phase 6: Verification

22. **Verify Python syntax** — run `ast.parse()` on every Python file.

23. **Run all unit tests** — every test must pass.

24. **Run a smoke test** — create objects, run 3–5 frames of the simulation
    loop, verify positions stay in bounds, velocities are non-zero, metrics
    update. Use a dummy video driver (`SDL_VIDEODRIVER=dummy`) for headless.

25. **Cross-file audit** — grep for section banners across all three code
    files. Verify the same sections appear in the same order. Any gaps must
    be explained by language architecture differences.

26. **Run a code reviewer agent** on all changed files before finalising.

27. **Stage and commit to git** with a descriptive message listing what was
    added/changed.

---

## Output Structure

When this skill completes, the project should look like:

```
project/
├── alg2.py                    # Python entry point (main loop)
├── occlusion_geom.py          # Pure utility functions (no display deps)
├── flock_core.py              # Constants + data structures
├── boid.py                    # Agent class with algorithm logic
├── metrics.py                 # Scientific metrics + display helpers
├── scenario_presets.py        # Educational preset configurations
├── alg_simple.py              # ~75-line minimal version for students
├── test_alg2.py               # Unit tests (40+ tests)
│
├── alg2.m                     # GNU Octave port
├── alg2.sce                   # Scilab port
├── alg.py                     # Original legacy code (kept for comparison)
│
├── README.md                  # Scientific docs + paper audit + roadmap + code tour
├── OCTAVE_README.md           # Octave-specific docs (self-contained)
├── SCILAB_README.md           # Scilab-specific docs (self-contained)
├── OCTAVE_README.md           # Octave-specific docs (self-contained)
├── SCILAB_README.md           # Scilab-specific docs (self-contained)
├── USER_GUIDE.md              # Practical guide (no math, no citations)
├── SKILL.md                   # This file (workflow for reuse)
│
├── LICENSE                    # GPLv3
└── .gitignore                 # Python artifacts, CSV output, research papers
```

---

## Gotchas

### Multi-language porting

- **Octave/Scilab have no classes.** All state must be parallel matrices
  (`pos` N×2, `vel` N×2, `acc` N×2). Per-agent data becomes columns/rows.
- **Octave rendering is slow.** Never draw N objects individually. Batch into
  a single `patch()` call with vertex matrices (3×N for triangles).
- **Scilab keyboard is platform-dependent.** Arrow keys have different codes
  on Linux (65xxx) vs Windows (37–40). Handle both variants in the callback.
- **Scilab figure event handlers need `sleep(1)`.** Without yielding the CPU
  for 1 ms before `drawnow()`, the event queue never drains.
- **State mutations from callbacks are unsafe.** Use pending flags: the
  callback sets `pending_add = pending_add + 10`, the main loop applies it
  atomically at the start of the next frame.
- **Performance differs dramatically.** O(N² log N) projection mode caps
  Python at ~200 birds. Octave/Scilab at ~100. Vectorized matrix operations
  help but don't eliminate the asymptotics.

### Documentation

- **Per-language READMEs must not reference each other.** Each stands alone.
  A Scilab user should not need to open the Octave README.
- **The user guide must have zero scientific content.** No equations, no
  Greek letters except those visible on screen (parameter names), no paper
  citations, no DOIs. It's for running the code, not understanding the theory.
- **The implementation audit table must be exhaustive.** Every claim from
  every relevant paper gets a row. Missing rows confuse readers.

### Code structure for education

- **The dependency graph must be a DAG.** Check for circular imports before
  writing any code. Draw the graph as ASCII art in the README.
- **The minimal version must actually produce visible flocking.** If it
  doesn't work, students lose trust. Test it end-to-end.
- **Debug views can allocate memory every frame for translucent surfaces.**
  This is acceptable for educational tools (performance is not the goal),
  but note it in a comment so students understand the trade-off.
- **Stale debug data across mode switches is a real bug.** When switching
  from projection to spatial mode, clear projection-specific debug state
  or guard the rendering to only activate in the relevant mode.

### General

- **Never assume a library is available.** Check `import` at module level.
  For optional display-only functions, use inline imports inside the method.
- **Research papers in the directory are reference material, not source code.**
  Add them to `.gitignore`.
- **CSV logging must be crash-safe.** Call `flush()` after every write so
  data survives even if the simulation is killed.
- **Greek letters in comments need no special encoding** — they're just
  Unicode characters in a UTF-8 file. But test that your terminal/editor
  renders them correctly before relying on them heavily.

---

## Checklist

Before declaring the skill complete, verify:

- [ ] All three papers audited with complete ✅/⚠️/❌ tables
- [ ] Primary paper deviations documented and either fixed or explained
- [ ] Implementation roadmap has 3 priority tiers with formulas
- [ ] Python entry point is ≤300 lines (modules handle the rest)
- [ ] All 6 Python modules import cleanly with no circular deps
- [ ] GNU Octave script has matching section banners and math documentation
- [ ] Scilab script has matching section banners and math documentation
- [ ] Cross-file audit: same sections, same order, any gaps explained
- [ ] All 47+ unit tests pass
- [ ] Smoke test: 3–5 frames run without errors, positions in bounds
- [ ] Main README has paper audit + roadmap + code tour + dependency diagram
- [ ] Per-language READMEs are self-contained (no cross-references to each other)
- [ ] User guide has zero math, zero paper citations
- [ ] Minimal version (`alg_simple.py`) is ~75 lines and actually works
- [ ] Scenario presets have descriptive labels and one-line explanations
- [ ] Focal agent debug view handles mode switches without stale data
- [ ] Teaching moment callouts use a consistent greppable marker
- [ ] Git repo has remote set, initial commit staged, GPLv3 LICENSE, .gitignore
- [ ] This SKILL.md captures everything so the workflow can be reused
