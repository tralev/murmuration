// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 1 — HEADER & OVERVIEW                                      ║
// ╚══════════════════════════════════════════════════════════════════════╝
//
//  alg2.sce — Dual-Mode Bird Flock Simulation (Scilab)
//  ──────────────────────────────────────────────────
//  Based on:  Pearce, Miller, Rowlands & Turner (2014)
//             "Role of projection in the control of bird flocks"
//             PNAS 111(29), 10422–10426.
//             DOI: 10.1073/pnas.1402202111
//
//  Two switchable flocking modes (press 'm' to toggle):
//  ─────────────────────────────────────────────────────
//    MODE 0 — PROJECTION   Hybrid projection model (Pearce et al., Eq. 3)
//             v_i = φp·δ̂_i + φa·⟨v̂_j⟩_visible + φn·η̂_i
//
//             δ̂_i  = direction to the nearest boundary of the occluded
//                    angular domain (computed via incremental angular-
//                    interval merging of closer-first neighbours).
//             Visibility determined by occlusion: a neighbour is visible
//             iff any portion of its subtended angular interval is NOT
//             already covered by birds closer to the observer.
//             Internal opacity Θ_i = fraction of 2π occluded.
//
//    MODE 1 — SPATIAL      Topological Reynolds boids (Reynolds 1987)
//             Separation / Alignment / Cohesion with σ nearest neighbours
//             within VISUAL_RANGE.  Weights are repurposed:
//               φp → separation, φa → alignment, φn → cohesion.
//
//  See the companion files alg2.py (Python/Pygame) and alg2.m (GNU Octave)
//  for ports to other computing environments.
//
//  Usage:  run this script in Scilab (Execute → run).
//          Close the figure window to stop.
// =======================================================================


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 2 — CONFIGURATION CONSTANTS                                ║
// ╚══════════════════════════════════════════════════════════════════════╝
//  These are the physical and numerical parameters of the simulation.
//  φp, φa, φn, and σ can be adjusted at runtime via keyboard controls.
//  Declare globals FIRST so all functions can share mutable state.
// ──────────────────────────────────────────────────────────────────────

global NUM_BOIDS BOID_SIZE WIDTH HEIGHT VISUAL_RANGE MODE paused PHI_P PHI_A PHI_N SIGMA pending_add pending_remove pending_reset show_help MARGIN_BOUNDARY BOUNDARY_MARGIN BOUNDARY_TURN_FACTOR

// ── Display ───────────────────────────────────────────────────────────
WIDTH        = 1000;                   // simulation area width  (pixels)
HEIGHT       = 700;                    // simulation area height (pixels)

// ── Flock parameters ──────────────────────────────────────────────────
NUM_BOIDS    = 100;                    // number of birds (reduce if slow)
BOID_SIZE    = 3;                      // bird radius b  (paper: b = 1)
V0           = 4;                      // constant cruising speed v₀
MAX_FORCE    = 0.15;                   // max steering force (smooth turning)
VISUAL_RANGE = 70;                     // neighbour search radius (spatial mode)

// ── Default model weights  (φp + φa ≡ 1 − φn) ────────────────────────
PHI_P  = 0.03;                         // projection / separation weight
PHI_A  = 0.80;                         // alignment weight
PHI_N  = 0.17;                         // noise weight — auto-computed each frame
SIGMA  = 4;                            // number of nearest visible neighbours

// ── Mode identifier ───────────────────────────────────────────────────
MODE   = 0;                            // 0 = PROJECTION, 1 = SPATIAL

// ── CSV logging ───────────────────────────────────────────────────────
LOG_FILE  = "murmuration_metrics.csv";
LOG_EVERY = 10;                        // write a row every N frames

// ── Trail rendering  (position-history polyline behind each boid) ──
DRAW_TRAIL   = %f;                      // draw position history trail behind each boid
TRAIL_LENGTH = 50;                      // max trail positions to keep

// ── Boundary mode  (toroidal wrap or margin-based keepWithinBounds) ──
MARGIN_BOUNDARY      = %f;              // use margin-based keepWithinBounds instead of toroidal wrap
BOUNDARY_MARGIN      = 200;              // distance from edge to start turning
BOUNDARY_TURN_FACTOR = 1;                // velocity nudge strength toward center


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 2b — CSV LOGGING SETUP                                    ║
// ╚══════════════════════════════════════════════════════════════════════╝
//  Open the metrics log file and write the CSV header.
// ──────────────────────────────────────────────────────────────────────

log_fid = mopen(LOG_FILE, "wt");
if log_fid == -1 then
    disp("WARNING: could not open " + LOG_FILE + " for writing");
else
    mfprintf(log_fid, "frame,mode,num_boids,phi_p,phi_a,phi_n,sigma,theta,theta_ext,alpha,fps\n");
    disp("Logging metrics to " + LOG_FILE + " every " + string(LOG_EVERY) + " frames");
end


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 3 — RUNTIME STATE INITIALIZATION                           ║
// ╚══════════════════════════════════════════════════════════════════════╝
//  Scilab uses flat matrices for state (no classes).  Parallel N×2
//  arrays for positions, velocities, accelerations — fully vectorized
//  where possible for performance.
// ──────────────────────────────────────────────────────────────────────

// ── Mutable runtime flags ────────────────────────────────────────────
paused = %f;                            // toggled by 'p' key
pending_add    = 0;                     // boid count change requests
pending_remove = 0;
pending_reset  = %f;                    // 'r' triggers full reset
show_help      = %f;                    // 'h' toggles help overlay
disp("Initializing flock with " + string(NUM_BOIDS) + " birds ...");

// ── State arrays  (N × 2) ────────────────────────────────────────────
//  pos  — positions           (rows: birds, cols: [x, y])
//  vel  — velocities          (rows: birds, cols: [vx, vy])
//  acc  — steering accumulators  (rows: birds, cols: [ax, ay])
//  last_theta — cached internal opacity Θ per bird  (N × 1)
pos  = rand(NUM_BOIDS, 2) .* repmat([WIDTH, HEIGHT], NUM_BOIDS, 1);  // random positions
ang  = rand(NUM_BOIDS, 1) * 2 * %pi;                      // random headings
vel  = [cos(ang), sin(ang)] .* repmat(1 + rand(NUM_BOIDS, 1) * (V0 - 1), 1, 2);
acc  = zeros(NUM_BOIDS, 2);
last_theta = zeros(NUM_BOIDS, 1);                          // cached Θ per bird
if DRAW_TRAIL then
    trail       = zeros(TRAIL_LENGTH, NUM_BOIDS, 2);
    trail_idx   = 1;
    trail_count = 0;
end


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 2c — FIGURE & GRAPHICS SETUP                              ║
// ╚══════════════════════════════════════════════════════════════════════╝
//  Create the figure window with keyboard event handler.
//  Scilab uses f.event_handler / f.event_handler_enable for callbacks
//  (different from Python's Pygame events and Octave's KeyPressFcn).
//  Pre-register custom colours once to avoid colormap pollution.
// ──────────────────────────────────────────────────────────────────────

f = figure("Figure_name", "Murmuration  [1-0/sl:presets m:mode b:boundary p:pause r:reset h:help]", ...
           "Position", [100, 100, WIDTH, HEIGHT], ...
           "Background", [20, 22, 30] / 255);
f.event_handler = "key_handler";
f.event_handler_enable = "on";

a = gca();
a.data_bounds   = [0, 0; WIDTH, HEIGHT];
a.isoview       = "on";
a.axes_visible  = "off";
a.margins       = [0, 0, 0, 0];

// Pre-register custom colours for the help overlay (once, not per-frame)
HELP_GRAY_IDX = addcolor([80, 80, 80] / 255);
HELP_GOLD_IDX = addcolor([200, 200, 160] / 255);


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 11 — INPUT HANDLING  (keyboard callback)                   ║
// ╚══════════════════════════════════════════════════════════════════════╝
//  NOTE: This section appears before the core algorithm sections (4–7)
//  because Scilab requires function definitions to precede their use.
//  The callback is registered on the figure via event_handler but
//  executed asynchronously during the main loop via sleep(1)/drawnow().
//  Non-blocking keyboard event handler registered via event_handler.
//  Mutates global state; pending flags are applied atomically in the
//  main loop to avoid race conditions during rendering.
//
//  Scilab callback signature: key_handler(win_id, x, y, ibut)
//    ibut < 0  → keyboard event  (abs(ibut) = ASCII code)
//    ibut > 0  → mouse event
//
//  Arrow keys have different codes on Windows (37–40) vs Linux (65xxx).
//  Both variants are handled for cross-platform compatibility.
//
//  Key map:
//    1-5,6-9,0,s,l,i,v,k,q  — scenario presets (φp, φa, σ, mode)
//    m/M  (109/77)   — toggle MODE
//    b/B  (98/66)    — toggle TOROIDAL / MARGIN boundary
//    p/P  (112/80)   — toggle pause
//    ↑↓   (38/40, 65362/65364) — φp ± 0.01
//    ←→   (37/39, 65361/65363) — φa ± 0.01
//    [/]  (91/93)    — σ ± 1
//    +/=  (43/61)    — +10 birds
//    -    (45)       — −10 birds
//    r/R  (114/82)   — reset flock
//    h/H  (104/72)   — toggle help overlay
// ──────────────────────────────────────────────────────────────────────

function key_handler(win_id, x, y, ibut)
    global MODE paused PHI_P PHI_A SIGMA pending_add pending_remove pending_reset show_help MARGIN_BOUNDARY
    if ibut < 0 then
        k = abs(ibut);

        // ── Mode toggle: m / M (109, 77) ────────────────────────
        if k == 109 | k == 77 then
            MODE = 1 - MODE;                   // 0 ↔ 1
            if MODE == 0 then disp("PROJECTION mode");
            else              disp("SPATIAL mode"); end

        // ── Boundary toggle: b / B (98, 66) ────────────────────
        elseif k == 98 | k == 66 then
            MARGIN_BOUNDARY = ~MARGIN_BOUNDARY;
            if MARGIN_BOUNDARY then disp("MARGIN boundary");
            else                   disp("TOROIDAL wrap"); end

        // ── Pause: p / P (112, 80) ──────────────────────────────
        elseif k == 112 | k == 80 then
            paused = ~paused;
            if paused then disp("Paused"); else disp("Resumed"); end

        // ── φp  up/down  (Win: 38/40  Linux: 65362/65364) ──────
        elseif k == 38 | k == 65362 then
            PHI_P = min(1.0, PHI_P + 0.01);
            disp("φp = " + string(PHI_P));
        elseif k == 40 | k == 65364 then
            PHI_P = max(0.0, PHI_P - 0.01);
            disp("φp = " + string(PHI_P));

        // ── φa  left/right  (Win: 37/39  Linux: 65361/65363) ──
        elseif k == 37 | k == 65361 then
            PHI_A = max(0.0, PHI_A - 0.01);
            disp("φa = " + string(PHI_A));
        elseif k == 39 | k == 65363 then
            PHI_A = min(1.0, PHI_A + 0.01);
            disp("φa = " + string(PHI_A));

        // ── σ  brackets  [ = 91,  ] = 93 ────────────────────────
        elseif k == 91 then
            SIGMA = max(1, SIGMA - 1);
            disp("σ = " + string(SIGMA));
        elseif k == 93 then
            SIGMA = min(50, SIGMA + 1);
            disp("σ = " + string(SIGMA));

        // ── Boid count  + = 43,  = = 61,  - = 45 ───────────────
        //  Pending flags avoid frame-tearing during rendering.
        elseif k == 43 | k == 61 then
            pending_add = min(pending_add + 10, 200);
            disp("Adding 10 birds (pending)");
        elseif k == 45 then
            pending_remove = pending_remove + 10;
            disp("Removing 10 birds (pending)");

        // ── Reset: r / R (114, 82) ──────────────────────────────
        elseif k == 114 | k == 82 then
            pending_reset = %t;
            disp("Resetting flock...");

        // ── Help overlay: h / H (104, 72) ──────────────────────
        elseif k == 104 | k == 72 then
            show_help = ~show_help;
            if show_help then disp("Help ON"); else disp("Help OFF"); end

        // ── Scenario presets  (1-5, 6-0, s, l, i, v, k, q) ─────
        //  ASCII: 1=49,2=50,3=51,4=52,5=53,6=54,7=55,8=56,9=57,0=48
        //         s=115,S=83, l=108,L=76, i=105,I=73
        //         v=118,V=86, k=107,K=75, q=113,Q=81
        elseif k == 49 then
            PHI_P = 0.00; PHI_A = 0.95; SIGMA = 8; MODE = 0;
            disp("PRESET 1 — Pure Alignment");
        elseif k == 50 then
            PHI_P = 0.10; PHI_A = 0.20; SIGMA = 2; MODE = 0;
            disp("PRESET 2 — Gas / Exploration");
        elseif k == 51 then
            PHI_P = 0.03; PHI_A = 0.80; SIGMA = 4; MODE = 0;
            disp("PRESET 3 — Pearce Default");
        elseif k == 52 then
            PHI_P = 0.15; PHI_A = 0.70; SIGMA = 6; MODE = 0;
            disp("PRESET 4 — Dense Ball");
        elseif k == 53 then
            PHI_P = 0.30; PHI_A = 0.50; SIGMA = 4; MODE = 1;
            disp("PRESET 5 — Classic Boids (SPATIAL)");
        elseif k == 54 then
            PHI_P = 0.08; PHI_A = 0.82; SIGMA = 8; MODE = 0;
            disp("PRESET 6 — Quiet Roost");
        elseif k == 55 then
            PHI_P = 0.04; PHI_A = 0.88; SIGMA = 5; MODE = 0;
            disp("PRESET 7 — Comfort Flight");
        elseif k == 56 then
            PHI_P = 0.02; PHI_A = 0.85; SIGMA = 3; MODE = 0;
            disp("PRESET 8 — Acro Swarm");
        elseif k == 57 then
            PHI_P = 0.30; PHI_A = 0.55; SIGMA = 8; MODE = 1;
            disp("PRESET 9 — Predator Ripple (SPATIAL)");
        elseif k == 48 then
            PHI_P = 0.20; PHI_A = 0.72; SIGMA = 10; MODE = 1;
            disp("PRESET 0 — Storm Turn (SPATIAL)");
        elseif k == 115 | k == 83 then
            PHI_P = 0.05; PHI_A = 0.85; SIGMA = 6; MODE = 0;
            disp("PRESET s — Swarm Pilot");
        elseif k == 108 | k == 76 then
            PHI_P = 0.12; PHI_A = 0.65; SIGMA = 7; MODE = 0;
            disp("PRESET l — Lava Lamp");
        elseif k == 105 | k == 73 then
            PHI_P = 0.02; PHI_A = 0.40; SIGMA = 2; MODE = 0;
            disp("PRESET i — Ink Cloud");
        elseif k == 118 | k == 86 then
            PHI_P = 0.35; PHI_A = 0.60; SIGMA = 9; MODE = 1;
            disp("PRESET v — Vacuole (SPATIAL)");
        elseif k == 107 | k == 75 then
            PHI_P = 0.02; PHI_A = 0.92; SIGMA = 6; MODE = 0;
            disp("PRESET k — Silk Sheet");
        elseif k == 113 | k == 81 then
            PHI_P = 0.20; PHI_A = 0.55; SIGMA = 10; MODE = 1;
            disp("PRESET q — Quest 2 Dense (SPATIAL)");
        end
    end
endfunction


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 4 — ANGULAR-INTERVAL UTILITIES                            ║
// ╚══════════════════════════════════════════════════════════════════════╝
//  Helper for merging overlapping angular intervals on [0, 2π).
//  Used by both the projection model (SECTION 5) and external opacity
//  (SECTION 7).
//
//  Input:  sorted intervals  (n_int × 2: [start, end])
//  Output: merged intervals  (n_merged × 2), with overlaps collapsed.
//  Complexity: O(n_int) — single linear pass over sorted input.
// ──────────────────────────────────────────────────────────────────────

function [merged, n_merged] = merge_angle_intervals(intervals, n_int)
    // Given sorted intervals (n_int × 2; column 1 = start, column 2 = end),
    // merge all overlapping intervals into a minimal set.
    // Returns merged(n_int × 2) with actual data in rows 1:n_merged.

    merged  = zeros(n_int, 2);
    n_merged = 0;
    j = 1;
    while j <= n_int
        cur_s = intervals(j, 1);
        cur_e = intervals(j, 2);
        k = j + 1;
        // Extend cur_e while next interval starts within current end
        while k <= n_int & intervals(k, 1) <= cur_e + 1e-9
            if intervals(k, 2) > cur_e then
                cur_e = intervals(k, 2);
            end
            k = k + 1;
        end
        n_merged = n_merged + 1;
        merged(n_merged, :) = [cur_s, cur_e];
        j = k;
    end
    merged = merged(1:n_merged, :);
endfunction


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 5 — PROJECTION MODEL  (MODE 0)                             ║
// ╚══════════════════════════════════════════════════════════════════════╝
//
//  Reference:  Pearce et al. (2014), Eq. (3):
//    v_i(t+1) = φp · δ̂_i(t) + φa · ⟨v̂_j(t)⟩_visible + φn · η̂_i(t)
//
//  δ̂_i  — unit vector toward the nearest boundary of the occluded
//          angular domain.  Computed by summing unit vectors to each
//          boundary of each merged occluded interval.
//
//  ⟨v̂_j⟩_visible  — mean heading of the σ nearest *visible* neighbours
//                     (visibility via angular-interval occlusion).
//
//  η̂_i  — random unit vector (intrinsic noise).
//
//  Θ_i  — internal opacity = (sum of merged interval widths) / 2π.
//
//  Steps (for each bird i):
//    1. Compute angular intervals to all other birds (vectorized O(N)).
//    2. Sort by distance, process closest-first.
//    3. For each bird j: if any segment of its interval is NOT covered
//       by already-merged (closer) intervals, mark j as visible and
//       merge its interval into the occluded set.
//    4. δ̂ from domain boundaries of merged occluded intervals.
//    5. Θ from total occluded angular width.
// ──────────────────────────────────────────────────────────────────────

function [delta, vis_idx, vis_dists, n_vis, theta] = ...
         compute_projection(i, pos, vel)
    // For bird i: angular intervals → visible neighbours → δ̂ → Θ
    global NUM_BOIDS BOID_SIZE

    // ── Step 1: distances & angles to all other birds (vectorized) ──
    diffs  = pos - repmat(pos(i,:), NUM_BOIDS, 1);
    dists  = sqrt(sum(diffs.^2, 2));
    angles = atan(diffs(:,2), diffs(:,1));          // atan2 equivalent

    // Normalise angles to [0, 2π)
    neg_mask = angles < 0;
    angles(neg_mask) = angles(neg_mask) + 2 * %pi;

    // Angular half-width αⱼ = arcsin(min(b / dⱼ, 1))
    half = asin(min(BOID_SIZE ./ dists, 1));

    // ── Step 2: collect & sort by distance (closest-first) ──────────
    //  Build entries matrix: [distance, centre_angle, half_width, bird_index]
    entries = [dists, angles, half, (1:NUM_BOIDS)'];
    entries(i, :) = [];                              // remove self

    // Sort by distance (column 1 ascending)
    [tmp, sort_idx] = gsort(entries(:,1), 'g', 'i');
    entries = entries(sort_idx, :);
    n_entries = size(entries, 1);

    // ── Step 3: incremental occlusion merge ────────────────────────
    //  For each bird (closest first):
    //    - Build [start, end] segments (handling wrap at 2π)
    //    - Check if any segment is NOT covered by merged intervals
    //    - If visible: record, merge segments into occluded set
    merged     = zeros(n_entries * 2, 2);
    n_merged   = 0;
    vis_idx    = zeros(n_entries, 1);
    vis_dists  = zeros(n_entries, 1);
    n_vis      = 0;

    for k = 1:n_entries
        bird_j   = entries(k, 4);
        d_j      = entries(k, 1);
        centre_j = entries(k, 2);
        half_j   = entries(k, 3);

        start_j = centre_j - half_j;
        end_j   = centre_j + half_j;

        // Build 1 or 2 segments (wrap at 0 and 2π)
        segs = zeros(2, 2);
        n_segs = 0;
        if start_j < 0 then
            n_segs = n_segs + 1; segs(n_segs,:) = [start_j + 2*%pi, 2*%pi];
            n_segs = n_segs + 1; segs(n_segs,:) = [0, end_j];
        elseif end_j > 2*%pi then
            n_segs = n_segs + 1; segs(n_segs,:) = [start_j, 2*%pi];
            n_segs = n_segs + 1; segs(n_segs,:) = [0, end_j - 2*%pi];
        else
            n_segs = n_segs + 1; segs(n_segs,:) = [start_j, end_j];
        end

        // Visibility test: is any segment NOT fully covered?
        is_visible = %f;
        for s = 1:n_segs
            covered = %f;
            cursor  = segs(s, 1);
            for m = 1:n_merged
                if merged(m,1) <= cursor + 1e-9 & cursor < merged(m,2) then
                    cursor = max(cursor, merged(m,2));
                end
                if cursor >= segs(s,2) - 1e-9 then
                    covered = %t;
                    break;
                end
            end
            if ~covered then
                is_visible = %t;
                break;
            end
        end

        if is_visible then
            n_vis = n_vis + 1;
            vis_idx(n_vis)   = bird_j;
            vis_dists(n_vis) = d_j;

            // Add segments to merged and re-merge
            for s = 1:n_segs
                n_merged = n_merged + 1;
                merged(n_merged,:) = segs(s,:);
            end
            if n_merged > 1 then
                [tmp2, midx] = gsort(merged(1:n_merged,1), 'g', 'i');
                merged(1:n_merged,:) = merged(midx,:);
                [merged, n_merged] = merge_angle_intervals(merged(1:n_merged,:), n_merged);
            end
        end
    end

    // Trim outputs to actual lengths
    vis_idx   = vis_idx(1:n_vis);
    vis_dists = vis_dists(1:n_vis);
    merged    = merged(1:n_merged, :);

    // ── Step 4: δ̂ from domain boundaries ──────────────────────────
    //  Sum unit vectors to each occluded interval boundary.
    //  Fully surrounded (one interval covering all 2π) → δ̂ = 0.
    delta = [0, 0];
    if n_merged == 1 & merged(1,1) < 1e-9 & merged(1,2) > 2*%pi - 1e-9 then
        // Fully surrounded — no projection information
        delta = [0, 0];
    else
        for m = 1:n_merged
            delta = delta + [cos(merged(m,1)), sin(merged(m,1))];
            delta = delta + [cos(merged(m,2)), sin(merged(m,2))];
        end
        dnorm = norm(delta);
        if dnorm > 1e-9 then
            delta = delta / dnorm;
        end
    end

    // ── Step 5: internal opacity Θ_i ──────────────────────────────
    //  Θ = (total occluded angular width) / 2π
    if n_merged > 0 then
        occluded = sum(merged(:,2) - merged(:,1));
        theta = min(occluded / (2 * %pi), 1.0);
    else
        theta = 0;
    end
endfunction


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 7 — EXTERNAL OPACITY  (Θ')                                  ║
// ╚══════════════════════════════════════════════════════════════════════╝
//  Θ' — fraction of the sky obscured from a distant external observer.
//  The observer is placed at (−2000, HEIGHT/2), far to the left of the
//  flock.  Angular intervals subtended by each bird are merged to find
//  the total occluded angular width.
//
//  Complexity: O(N log N) where N = NUM_BOIDS.
// ──────────────────────────────────────────────────────────────────────

function theta_ext = compute_external_opacity(pos)
    global NUM_BOIDS BOID_SIZE WIDTH HEIGHT VISUAL_RANGE

    // Observer far to the left
    viewpoint = [-2000, HEIGHT/2];
    diffs  = pos - repmat(viewpoint, NUM_BOIDS, 1);
    dists  = sqrt(sum(diffs.^2, 2));
    angles = atan(diffs(:,2), diffs(:,1));
    neg_mask = angles < 0;
    angles(neg_mask) = angles(neg_mask) + 2 * %pi;
    half = asin(min(BOID_SIZE ./ dists, 1));

    // Build angular intervals for all birds
    intervals = zeros(NUM_BOIDS * 2, 2);
    n_int = 0;
    for k = 1:NUM_BOIDS
        s = angles(k) - half(k);
        e = angles(k) + half(k);
        if s < 0 then
            n_int = n_int + 1; intervals(n_int,:) = [s + 2*%pi, 2*%pi];
            n_int = n_int + 1; intervals(n_int,:) = [0, e];
        elseif e > 2*%pi then
            n_int = n_int + 1; intervals(n_int,:) = [s, 2*%pi];
            n_int = n_int + 1; intervals(n_int,:) = [0, e - 2*%pi];
        else
            n_int = n_int + 1; intervals(n_int,:) = [s, e];
        end
    end
    if n_int == 0 then
        theta_ext = 0;
    else
        // Sort by start angle, merge overlaps, sum widths
        intervals = intervals(1:n_int, :);
        [tmp, idx] = gsort(intervals(:,1), 'g', 'i');
        intervals = intervals(idx, :);
        [merged, n_m] = merge_angle_intervals(intervals, n_int);
        occluded = sum(merged(:,2) - merged(:,1));
        theta_ext = min(occluded / (2 * %pi), 1.0);
    end
endfunction


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 10 — HELP OVERLAY  (rendered when show_help = %t)           ║
// ╚══════════════════════════════════════════════════════════════════════╝
//  Dark panel in the top-right corner showing all keyboard controls.
//  Uses pre-registered custom colours (set up during figure init)
//  to avoid calling addcolor() every frame.
// ──────────────────────────────────────────────────────────────────────

function _draw_help_overlay()
    global WIDTH HEIGHT HELP_GRAY_IDX HELP_GOLD_IDX

    // Build help text inside the function — no global needed.
    lines = [..
        "CONTROLS";..
        "───────────────────────────────────";..
        "1-5,6-0,s,l,i,v,k,q  scenario presets";..
        "m        toggle  PROJECTION / SPATIAL";..
        "b        toggle  TOROIDAL / MARGIN boundary";..
        "p        pause / resume";..
        "r        reset flock";..
        "h        hide this help";..
        "↑ / ↓    φp  ±0.01";..
        "← / →    φa  ±0.01";..
        "[ / ]    σ   ±1";..
        "+ / -    add / remove 10 birds";..
        "ESC      close window to quit";..
    ];
    n_lines = size(lines, 1);

    px = WIDTH - 345;
    py = 5;
    pw = 335;
    ph = n_lines * 18 + 8;

    // Dark panel background
    xrect(px, HEIGHT - py - ph, pw, ph);
    r = gce();
    r.background = color("black");
    r.fill_mode  = "on";
    r.foreground = HELP_GRAY_IDX;
    r.line_mode  = "on";

    // Text lines (top to bottom)
    for i = 1:n_lines
        xstring(px + 6, HEIGHT - py - 18*i - 4, lines(i));
        th = gce();
        th.font_size  = 1;
        th.font_color = HELP_GOLD_IDX;
    end
endfunction


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 12 — MAIN LOOP                                             ║
// ╚══════════════════════════════════════════════════════════════════════╝
//  The main simulation loop runs until the figure is closed.  Each frame:
//
//    1. CHECK FIGURE  — break if window closed
//    2. APPLY PENDING  — add/remove birds, reset, auto-compute φn
//    3. FLOCKING       — per-bird steering (projection or spatial)
//    4. PHYSICS        — Euler integration (vectorized), speed clamp, wrap
//    5. METRICS        — Θ, Θ', α with EMA smoothing
//    6. CSV LOGGING    — append row every LOG_EVERY frames
//    7. RENDER         — clear axes, draw birds (batch xfpolys), text, help
// ──────────────────────────────────────────────────────────────────────

mode_names = ["PROJECTION  (Pearce et al. 2014)", ...
              "SPATIAL     (topological Reynolds)"];

frame    = 0;
running  = %t;
smooth   = 0.05;                         // EMA factor for metrics
theta_ema     = 0;                        // Θ  — mean internal opacity (EMA)
theta_ext_ema = 0;                        // Θ' — external opacity (EMA)
alpha_ema     = 0;                        // α  — order parameter (EMA)

// Triangle vertex offsets (relative to position, rotated by heading)
tip_len   = BOID_SIZE * 2.5;
side_len  = BOID_SIZE * 1.5;
side_ang  = 2.3;

disp("Running — close the figure window to stop.");
disp("  Keys:  1-0/sl:presets  m:mode  p:pause  arrows:φ  []:σ  +/-:boids  r:reset  h:help");

// ═══════════════════════════════════════════════════════════════════
//  MAIN FRAME LOOP
//  Each iteration processes one simulation frame.
// ═══════════════════════════════════════════════════════════════════
while running
    t_frame = tic();                       // start frame timer

    // ── Check if figure still open ────────────────────────────────
    if ~is_handle_valid(f) then
        break;
    end

    // ───────────────────────────────────────────────────────────────
    //  UPDATE  — skipped when paused; otherwise:
    //    1. Apply pending state changes (add/remove/reset, auto φn)
    //    2. Flocking update (compute steering per bird)
    //    3. Physics update (Euler integration, vectorized)
    //    4. Metrics computation (Θ, Θ', α with EMA)
    //    5. CSV logging
    // ───────────────────────────────────────────────────────────────
    if ~paused then

        // ╔══════════════════════════════════════════════════════════╗
        // ║  SECTION 9a — AUTO-COMPUTE φn                            ║
        // ╚══════════════════════════════════════════════════════════╝
        //
        //  φn = max(0, 1 − φp − φa)
        //  Guarantees the three model weights always sum to 1.
        //  Re-computed every frame so runtime φp/φa adjustments
        //  take effect immediately.
        // ───────────────────────────────────────────────────────────
        PHI_N = max(0.0, 1.0 - PHI_P - PHI_A);

        // ╔══════════════════════════════════════════════════════════╗
        // ║  SECTION 9c — BOID COUNT CHANGES  (+/- keys)            ║
        // ╚══════════════════════════════════════════════════════════╝
        //
        //  Add or remove birds via pending flags set by the keyboard
        //  callback. Changes are applied atomically at the start of
        //  each frame to avoid race conditions during rendering.
        //  Removal: trim matrices from the end (safely leaves ≥ 1 bird)
        if pending_remove > 0 then
            n_remove = min(pending_remove, NUM_BOIDS - 1);
            if n_remove > 0 then
                pos        = pos(1:NUM_BOIDS - n_remove, :);
                vel        = vel(1:NUM_BOIDS - n_remove, :);
                acc        = acc(1:NUM_BOIDS - n_remove, :);
                last_theta = last_theta(1:NUM_BOIDS - n_remove);
                if DRAW_TRAIL then
                    trail = trail(:, 1:NUM_BOIDS - n_remove, :);
                end
                NUM_BOIDS  = NUM_BOIDS - n_remove;
                pending_remove = pending_remove - n_remove;
                disp("Removed " + string(n_remove) + " birds, now " + string(NUM_BOIDS));
            end
        end
        // Addition: append new random birds to each state matrix
        if pending_add > 0 then
            n_add = pending_add;
            new_pos  = rand(n_add, 2) .* repmat([WIDTH, HEIGHT], n_add, 1);
            new_ang  = rand(n_add, 1) * 2 * %pi;
            new_vel  = [cos(new_ang), sin(new_ang)] .* repmat(1 + rand(n_add, 1) * (V0 - 1), 1, 2);
            pos        = [pos; new_pos];
            vel        = [vel; new_vel];
            acc        = [acc; zeros(n_add, 2)];
            last_theta = [last_theta; zeros(n_add, 1)];
            if DRAW_TRAIL then
                trail = cat(2, trail, zeros(TRAIL_LENGTH, n_add, 2));
            end
            NUM_BOIDS  = NUM_BOIDS + n_add;
            pending_add = 0;
            disp("Added " + string(n_add) + " birds, now " + string(NUM_BOIDS));
        end

        // ╔══════════════════════════════════════════════════════════╗
        // ║  SECTION 9b — RESET LOGIC  (triggered by 'r' key)       ║
        // ╚══════════════════════════════════════════════════════════╝
        //
        //  Reinitialise all state matrices with random positions and
        //  velocities, reset metric EMA accumulators to zero, and
        //  restart the frame counter.
        //
        //  The pending_reset flag is set by the keyboard callback
        //  and applied atomically here in the main loop.
        // ───────────────────────────────────────────────────────────
        if pending_reset then
            pos  = rand(NUM_BOIDS, 2) .* repmat([WIDTH, HEIGHT], NUM_BOIDS, 1);
            ang  = rand(NUM_BOIDS, 1) * 2 * %pi;
            vel  = [cos(ang), sin(ang)] .* repmat(1 + rand(NUM_BOIDS, 1) * (V0 - 1), 1, 2);
            acc  = zeros(NUM_BOIDS, 2);
            last_theta = zeros(NUM_BOIDS, 1);
            theta_ema = 0;  theta_ext_ema = 0;  alpha_ema = 0;
            if DRAW_TRAIL then
                trail       = zeros(TRAIL_LENGTH, NUM_BOIDS, 2);
                trail_idx   = 1;
                trail_count = 0;
            end
            frame = 0;
            pending_reset = %f;
            disp("Flock reset — " + string(NUM_BOIDS) + " birds");
        end

        // ── 2. Flocking update: compute steering forces ────────────
        //  Per-bird loop dispatches by MODE.
        //  MODE 0 (PROJECTION):  v = φp·δ̂ + φa·⟨v̂⟩_visible + φn·η̂
        //  MODE 1 (SPATIAL):     separation/alignment/cohesion + noise
        if MODE == 0 then
            // ═══════════════════════════════════════════════════════
            //  MODE 0 — PROJECTION MODEL
            //
            //  For each bird i:
            //    1. compute_projection → δ̂, visible neighbours, Θ
            //    2. Alignment: ⟨v̂⟩ of σ nearest visible neighbours
            //    3. Noise: random unit vector η̂
            //    4. Desired direction: v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
            //    5. Steering: steer = v_desired − v_current, clamped
            // ═══════════════════════════════════════════════════════
            for i = 1:NUM_BOIDS
                [delta, vis_idx, vis_dists, n_vis, theta] = ...
                    compute_projection(i, pos, vel);
                last_theta(i) = theta;            // cache for metrics

                // ── Alignment: mean velocity of σ nearest visible ──
                align = [0, 0];
                if n_vis > 0 then
                    sigma_use = min(SIGMA, n_vis);
                    for k = 1:sigma_use
                        j_vis = vis_idx(k);
                        align = align + vel(j_vis, :);
                    end
                    align = align / sigma_use;
                end

                // ── Noise: random unit vector ──────────────────────
                na = rand() * 2 * %pi;
                noise = [cos(na), sin(na)];

                // ── Desired direction (Eq. 3 from paper) ───────────
                //  v_desired = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
                desired = delta * PHI_P;
                if norm(align) > 0.001 then
                    desired = desired + (align / norm(align)) * PHI_A;
                else
                    // Fallback: use own heading when no visible neighbours
                    if norm(vel(i,:)) > 0.001 then
                        desired = desired + (vel(i,:) / norm(vel(i,:))) * PHI_A;
                    end
                end
                desired = desired + noise * PHI_N;

                if norm(desired) < 0.001 then
                    desired = [rand()*2-1, rand()*2-1];
                end
                desired = desired / norm(desired) * V0;

                // ── Reynolds steering: steer = v_desired − v ───────
                steer = desired - vel(i,:);
                if norm(steer) > MAX_FORCE then
                    steer = steer / norm(steer) * MAX_FORCE;
                end
                acc(i,:) = acc(i,:) + steer;
            end

        else
            // ╔══════════════════════════════════════════════════════╗
            // ║  SECTION 6 — SPATIAL MODEL  (MODE 1)               ║
            // ╚══════════════════════════════════════════════════════╝
            //
            //  Reference:  Reynolds, C. W. (1987)
            //    "Flocks, Herds, and Schools: A Distributed Behavioral Model"
            //    SIGGRAPH '87, DOI: 10.1145/37401.37406
            //
            //  Classic three-rule boids with topological neighbour selection.
            //  Full O(N²) pairwise distance matrix (vectorized).
            //  For each bird i:
            //    1. Find σ nearest neighbours within VISUAL_RANGE
            //    2. Separation: steer away from very close neighbours
            //    3. Alignment: steer toward mean neighbour heading
            //    4. Cohesion: steer toward mean neighbour position
            //    5. Weighted force accumulation + noise
            //
            //  Weights repurposed from the projection model:
            //    φp → separation (× 2.0)
            //    φa → alignment  (× 1.2)
            //    φn → cohesion   (× 1.5)
            // ═══════════════════════════════════════════════════════

            // Pairwise distance matrix  (N × N, vectorized)
            dx = repmat(pos(:,1), 1, NUM_BOIDS) - repmat(pos(:,1)', NUM_BOIDS, 1);
            dy = repmat(pos(:,2), 1, NUM_BOIDS) - repmat(pos(:,2)', NUM_BOIDS, 1);
            dist_mat = sqrt(dx.^2 + dy.^2);

            for i = 1:NUM_BOIDS
                row   = dist_mat(i, :);
                row(i)= %inf;                        // exclude self
                in_range = find(row < VISUAL_RANGE);

                sep = [0, 0];                        // separation steering
                ali = [0, 0];                        // alignment steering
                coh = [0, 0];                        // cohesion steering

                if ~isempty(in_range) then
                    range_dists = row(in_range);
                    [sorted, sort_idx] = gsort(range_dists, 'g', 'i');
                    sigma_use = min(SIGMA, length(in_range));
                    nbs = in_range(sort_idx(1:sigma_use));  // σ nearest

                    // ── Accumulate neighbour contributions ────────
                    for k = 1:sigma_use
                        j = nbs(k);
                        d_ij = dist_mat(i, j);
                        ali = ali + vel(j, :);           // sum velocities
                        coh = coh + pos(j, :);           // sum positions
                        if d_ij < VISUAL_RANGE * 0.3 & d_ij > 0.001 then
                            diff_ij = pos(i,:) - pos(j,:);
                            sep = sep + diff_ij / d_ij;   // weight ∝ 1/distance
                        end
                    end

                    ali = ali / sigma_use;
                    coh = coh / sigma_use;

                    // ── Alignment steering ────────────────────────
                    if norm(ali) > 0.001 then
                        ali = ali / norm(ali) * V0;
                    end
                    ali = ali - vel(i,:);
                    if norm(ali) > MAX_FORCE then ali = ali / norm(ali) * MAX_FORCE; end

                    // ── Cohesion steering ─────────────────────────
                    coh = coh - pos(i,:);
                    if norm(coh) > 0.001 then coh = coh / norm(coh) * V0; end
                    coh = coh - vel(i,:);
                    if norm(coh) > MAX_FORCE then coh = coh / norm(coh) * MAX_FORCE; end

                    // ── Separation steering ───────────────────────
                    if norm(sep) > 0.001 then sep = sep / norm(sep) * V0; end
                    sep = sep - vel(i,:);
                    if norm(sep) > MAX_FORCE then sep = sep / norm(sep) * MAX_FORCE; end
                end

                // ── Noise for exploration ─────────────────────────
                na = rand() * 2 * %pi;
                noise = [cos(na), sin(na)] * MAX_FORCE * 0.8;

                // ── Weighted force accumulation ───────────────────
                acc(i,:) = acc(i,:) + sep * PHI_P * 2.0;
                acc(i,:) = acc(i,:) + ali * PHI_A * 1.2;
                acc(i,:) = acc(i,:) + coh * PHI_N * 1.5;
                acc(i,:) = acc(i,:) + noise;
            end
        end

        // ╔══════════════════════════════════════════════════════════╗
        // ║  SECTION 9 — PHYSICS UPDATE  (shared by both modes)      ║
        // ╚══════════════════════════════════════════════════════════╝
        //
        //  Euler integration with speed clamping and toroidal wrap.
        //  This is the same physics step regardless of flocking mode:
        //
        //    1. v ← v + a          apply accumulated steering force
        //    2. |v| clamped to [0.3·V₀, V₀]
        //       - cap at V₀ (max cruising speed)
        //       - floor at 0.3·V₀ (prevent stagnation)
        //    3. p ← p + v          move forward
        //    4. toroidal wrap      re-enter from opposite edge via modulo()
        //    5. a ← 0              reset steering accumulator
        //
        //  Complexity: O(N) — fully vectorized over all birds.
        // ───────────────────────────────────────────────────────────
        vel = vel + acc;

        // ── Boundary nudge (margin mode — before speed clamp) ───
        //  Nudging before the clamp means speed is re-normalized
        //  afterward, eliminating the one-frame overshoot and
        //  reducing wall-jitter from the speed floor.
        if MARGIN_BOUNDARY then
            near_left  = find(pos(:,1) < BOUNDARY_MARGIN);
            near_right = find(pos(:,1) > WIDTH - BOUNDARY_MARGIN);
            near_top   = find(pos(:,2) < BOUNDARY_MARGIN);
            near_btm   = find(pos(:,2) > HEIGHT - BOUNDARY_MARGIN);
            vel(near_left,  1) = vel(near_left,  1) + BOUNDARY_TURN_FACTOR;
            vel(near_right, 1) = vel(near_right, 1) - BOUNDARY_TURN_FACTOR;
            vel(near_top,   2) = vel(near_top,   2) + BOUNDARY_TURN_FACTOR;
            vel(near_btm,   2) = vel(near_btm,   2) - BOUNDARY_TURN_FACTOR;
        end

        spd = sqrt(sum(vel.^2, 2));

        // Speed clamp: [0.3·V₀, V₀]
        fast = find(spd > V0);
        if ~isempty(fast) then
            vel(fast,:) = vel(fast,:) ./ repmat(spd(fast), 1, 2) * V0;
        end
        slow = find(spd < V0 * 0.3);
        if ~isempty(slow) then
            for s = slow'
                if spd(s) > 0.001 then
                    vel(s,:) = vel(s,:) / spd(s) * V0 * 0.3;
                else
                    na = rand() * 2 * %pi;
                    vel(s,:) = [cos(na), sin(na)] * V0 * 0.3;
                end
            end
        end

        pos = pos + vel;
        acc = acc * 0;

        // ── Boundary handling ───────────────────────────────────
        if MARGIN_BOUNDARY then
            pos(:,1) = max(0, min(WIDTH,  pos(:,1)));
            pos(:,2) = max(0, min(HEIGHT, pos(:,2)));
        else
            // Toroidal wrap
            pos(:,1) = modulo(pos(:,1), WIDTH);
            pos(:,2) = modulo(pos(:,2), HEIGHT);
        end

        // ── Trail: record position (ring buffer) ──────────────────
        if DRAW_TRAIL then
            trail_idx = modulo(trail_idx, TRAIL_LENGTH) + 1;
            trail(trail_idx, :, 1) = pos(:, 1)';
            trail(trail_idx, :, 2) = pos(:, 2)';
            trail_count = min(trail_count + 1, TRAIL_LENGTH);
        end

        // ╔══════════════════════════════════════════════════════════╗
        // ║  SECTION 8 — METRICS COMPUTATION                        ║
        // ╚══════════════════════════════════════════════════════════╝
        //  Θ  (internal opacity) — exact in PROJECTION mode, sampled
        //       (5 birds) in SPATIAL mode to avoid O(N²) cost.
        //  Θ' (external opacity) — O(N log N) angular interval merge
        //       from distant observer at (−2000, HEIGHT/2).
        //  α  (order parameter) — |Σv_i| / (N·v₀).  α ≈ 1 = aligned.
        //  All metrics use EMA smoothing: x ← x + (x_raw − x) × s.

        if MODE == 0 then
            // PROJECTION: Θ already cached as last_theta(i)
            theta_raw = mean(last_theta);
        else
            // SPATIAL: sample 5 random birds for Θ estimate
            sample_n = min(5, NUM_BOIDS);
            sample_idx = grand(1, "prm", (1:NUM_BOIDS)');
            sample_idx = sample_idx(1:sample_n);
            theta_sum = 0;
            for s = 1:sample_n
                [tmp_d, tmp_v, tmp_vd, tmp_nv, theta_sample] = ...
                    compute_projection(sample_idx(s), pos, vel);
                theta_sum = theta_sum + theta_sample;
            end
            theta_raw = theta_sum / sample_n;
        end
        theta_ema = theta_ema + (theta_raw - theta_ema) * smooth;

        theta_ext_raw = compute_external_opacity(pos);
        theta_ext_ema = theta_ext_ema + (theta_ext_raw - theta_ext_ema) * smooth;

        total_vel = sum(vel, 1);                     // Σ v_i
        alpha_raw = norm(total_vel) / (NUM_BOIDS * V0);  // |Σv|/(N·v₀)
        alpha_ema = alpha_ema + (alpha_raw - alpha_ema) * smooth;

        // ── 5. CSV logging  (every LOG_EVERY frames) ─────────────
        if log_fid ~= -1 & modulo(frame, LOG_EVERY) == 0 then
            fps = 1 / max(toc(t_frame), 0.001);
            mfprintf(log_fid, "%d,%d,%d,%.4f,%.4f,%.4f,%d,%.4f,%.4f,%.4f,%.1f\n", ..
                     frame, MODE, NUM_BOIDS, PHI_P, PHI_A, PHI_N, SIGMA, ..
                     theta_ema, theta_ext_ema, alpha_ema, fps);
        end

    end  // ~paused

    // ───────────────────────────────────────────────────────────────
    //  RENDER  — clear and redraw all graphics
    //    1. Clear axes children
    //    2. Bird triangles (batch xfpolys with NaN separators)
    //    3. Metrics text (xstring)
    //    4. Mode badge
    //    5. Pause indicator
    //    6. Help overlay
    // ───────────────────────────────────────────────────────────────

    // Clear previous frame
    if ~isempty(a.children) then
        delete(a.children);
    end
    a.data_bounds = [0, 0; WIDTH, HEIGHT];
    a.isoview      = "on";
    a.axes_visible = "off";

    drawlater();

    // ── Bird triangles (batch via NaN-separated vertices) ──────────
    //  Scilab's xfpolys interprets NaN vertices as polygon breaks.
    //  4 vertices per bird: tip, left, right, NaN (separator).
    dirs = atan(vel(:,2), vel(:,1));                // headings (radians)

    tip_x = pos(:,1) + cos(dirs) * tip_len;
    tip_y = pos(:,2) + sin(dirs) * tip_len;
    lft_x = pos(:,1) + cos(dirs + side_ang) * side_len;
    lft_y = pos(:,2) + sin(dirs + side_ang) * side_len;
    rgt_x = pos(:,1) + cos(dirs - side_ang) * side_len;
    rgt_y = pos(:,2) + sin(dirs - side_ang) * side_len;

    // Interleave vertices with NaN separators
    X_verts = zeros(4 * NUM_BOIDS, 1);
    Y_verts = zeros(4 * NUM_BOIDS, 1);
    X_verts(1:4:$) = tip_x;  X_verts(2:4:$) = lft_x;
    X_verts(3:4:$) = rgt_x;  X_verts(4:4:$) = %nan;
    Y_verts(1:4:$) = tip_y;  Y_verts(2:4:$) = lft_y;
    Y_verts(3:4:$) = rgt_y;  Y_verts(4:4:$) = %nan;

    // Mode-dependent colour: cool blue-white vs warm amber
    if MODE == 0 then
        bird_color = [200, 210, 230] / 255;
    else
        bird_color = [230, 200, 160] / 255;
    end
    xfpolys(X_verts, Y_verts, bird_color);

    // ── Trail rendering ──────────────────────────────────────────
    if DRAW_TRAIL & trail_count > 1 then
        order = modulo((trail_idx - trail_count : trail_idx - 1), TRAIL_LENGTH) + 1;
        order(order < 1) = order(order < 1) + TRAIL_LENGTH;
        for i = 1:NUM_BOIDS
            tx = trail(order, i, 1);
            ty = trail(order, i, 2);
            if length(tx) > 1 then
                xpoly(tx, ty, "lines", 0);
                e = gce();
                e.foreground = addcolor([100, 140, 220]/255);
                e.thickness = 1;
            end
        end
    end

    // ── Metrics text overlay ──────────────────────────────────────
    txt = msprintf("FPS: %.0f    Boids: %d    Frame: %d", ...
                   1/max(toc(t_frame), 0.001), NUM_BOIDS, frame);
    xstring(10, 5, txt);

    txt2 = msprintf("φp=%.3f  φa=%.3f  φn=%.3f  σ=%d", PHI_P, PHI_A, PHI_N, SIGMA);
    xstring(10, 25, txt2);

    if MODE == 0 then
        t3 = msprintf("Opacity  Θ  = %.3f", theta_ema);
    else
        t3 = msprintf("Opacity  Θ  ~ %.3f  (sampled)", theta_ema);
    end
    xstring(10, 45, t3);

    t4 = msprintf("          Θ'' = %.3f", theta_ext_ema);
    xstring(10, 65, t4);

    t5 = msprintf("Order α = %.3f", alpha_ema);
    xstring(10, 85, t5);

    // ── Mode badge (top-right) ────────────────────────────────────
    badge = mode_names(MODE + 1);
    xstring(WIDTH - 250, 5, badge);

    // ── Boundary mode badge (top-right, below mode badge) ─────────
    if MARGIN_BOUNDARY then
        bdy_badge = "MARGIN";
    else
        bdy_badge = "TOROIDAL";
    end
    xstring(WIDTH - 250, 25, bdy_badge);

    // ── Pause indicator ───────────────────────────────────────────
    if paused then
        xstring(WIDTH/2 - 100, HEIGHT - 30, "PAUSED");
    end

    // ── Help overlay (top-right panel) ───────────────────────────
    if show_help then
        _draw_help_overlay();
    end

    // Apply uniform text styling to all text children
    ch = a.children;
    for c = 1:length(ch)
        if ch(c).type == "Text" then
            ch(c).font_size  = 2;
            ch(c).font_color = [170, 200, 170] / 255;
        end
    end

    // Brief yield so the event loop can deliver key presses
    sleep(1);
    drawnow();

    frame = frame + 1;

end  // while running


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 13 — SHUTDOWN                                              ║
// ╚══════════════════════════════════════════════════════════════════════╝

if log_fid ~= -1 then
    mclose(log_fid);
    disp("Metrics saved to " + LOG_FILE);
end

disp("Simulation ended after " + string(frame) + " frames.");
disp("Run again to restart.");
// =======================================================================
