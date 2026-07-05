// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 1 — HEADER & OVERVIEW                                      ║
// ╚══════════════════════════════════════════════════════════════════════╝
//
//  alg2_extended.sce — Extended Dual-Mode Bird Flock Simulation (Scilab)
//  ────────────────────────────────────────────────────────────────────
//  Based on:  Pearce, Miller, Rowlands & Turner (2014)
//             "Role of projection in the control of bird flocks"
//             PNAS 111(29), 10422–10426.
//             DOI: 10.1073/pnas.1402202111
//
//  This is the FULL extended version with all 9 roadmap priorities
//  ported from the Python extensions/ directory.  All features can
//  be individually toggled via the ENABLE_* flags in SECTION 2.
//
//  ── CROSS-LANGUAGE COMPARISON ─────────────────────────────────────
//  Same algorithm is available in three computing environments:
//
//    Python      extensions/alg2_extended.py, extensions/three_d.py, …
//    ⇔ Octave    extensions/alg2_extended.m
//    ⇔ Scilab    extensions/alg2_extended.sce  ← you are here
//
//  All three share identical variable names (ENABLE_*, PHI_*, SIGMA,
//  NUM_BOIDS, BOID_SIZE, STERIC_RADIUS, etc.) and feature-flag logic.
//  Look for "⇔" comments throughout to find the equivalent code block
//  in the other two languages.
//
//  Feature flags (set %t or %f at the top of SECTION 2):
//  ────────────────────────────────────────────────────────────────────
//    1a — Direct velocity setting (no Reynolds steering)
//    1b — Multi-viewpoint Θ′ (K=12 viewpoints)
//    1c — Correlation time τᵨ (Graham scan convex hull)
//    2a — Steric repulsion (1/r² force)
//    2b — Blind angles (60° rear blind cone)
//    2c — 3D extension (Fibonacci sphere spherical cap occlusion)
//    2d — Anisotropic bodies (elliptical projected size)
//    3a — Predator agent (peregrine falcon)
//    3b — Spatial optimization (grid-based chunker)
//
//  Two flocking modes (press 'm' to toggle):
//  ─────────────────────────────────────────────────────
//    MODE 0 — PROJECTION   Hybrid projection model (Pearce et al., Eq. 3)
//             v_i = φp·δ̂_i + φa·⟨v̂_j⟩_visible + φn·η̂_i
//
//    MODE 1 — SPATIAL      Topological Reynolds boids (Reynolds 1987)
//             Separation / Alignment / Cohesion with σ nearest neighbours
//             within VISUAL_RANGE.
//
//  Usage:  exec("extensions/alg2_extended.sce");
//          Close the figure window to stop.
// =======================================================================


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 2 — CONFIGURATION CONSTANTS & FEATURE FLAGS                ║
// ╚══════════════════════════════════════════════════════════════════════╝
//  Declare globals FIRST so all functions can share mutable state.
// ──────────────────────────────────────────────────────────────────────

global NUM_BOIDS BOID_SIZE WIDTH HEIGHT VISUAL_RANGE DEPTH
global MODE DIMENSIONS paused PHI_P PHI_A PHI_N PHI_S SIGMA
global pending_add pending_remove pending_reset show_help
global ENABLE_1a ENABLE_1b ENABLE_1c ENABLE_2a ENABLE_2b ENABLE_2c ENABLE_2d ENABLE_3a ENABLE_3b
global K_VIEWPOINTS R_EXT BLIND_ANGLE_VAL PHI_STERIC STERIC_RADIUS
global BOID_SEMI_MAJOR BOID_SEMI_MINOR BUFFER_SIZE_TAU CORR_SAMPLE_INTERVAL MAX_LAG_FRACTION
global GRID_COLS GRID_ROWS CELL_W CELL_H
global PREDATOR_SPEED PREDATOR_ACCEL DANGER_RADIUS FLIGHT_FORCE

// ── Feature flags — set to %t to enable, %f to disable ──────────────
ENABLE_1a = %t;   // Direct velocity setting (Pearce Eq. 2-3, no Reynolds steering)
ENABLE_1b = %t;   // Multi-viewpoint external opacity Θ′ (K viewpoints)
ENABLE_1c = %t;   // Correlation time τᵨ (Graham scan convex hull)
ENABLE_2a = %t;   // Steric repulsion (1/r² force, prevents overlap)
ENABLE_2b = %t;   // Blind angles (β=60° rear blind sector)
ENABLE_2c = %f;   // 3D extension (Fibonacci sphere spherical cap occlusion)
ENABLE_2d = %t;   // Anisotropic bodies (elliptical projected size)
ENABLE_3a = %t;   // Predator agent (peregrine falcon)
ENABLE_3b = %t;   // Spatial optimization (grid-based chunker)

// ── Display ───────────────────────────────────────────────────────────
WIDTH        = 1000;                   // simulation area width  (pixels)
HEIGHT       = 700;                    // simulation area height (pixels)
DEPTH        = 1000;                   // 3D depth (only used when ENABLE_2c = %t)

// ── Flock parameters ──────────────────────────────────────────────────
NUM_BOIDS    = 100;                    // number of birds (reduce if slow)
BOID_SIZE    = 3;                      // bird radius b  (paper: b = 1)
V0           = 4;                      // constant cruising speed v₀
MAX_FORCE    = 0.15;                   // max steering force (spatial mode)
VISUAL_RANGE = 70;                     // neighbour search radius (spatial mode)

// ── Default model weights  (φp + φa + φn = 1) ────────────────────────
PHI_P  = 0.03;                         // projection weight
PHI_A  = 0.80;                         // alignment weight
PHI_N  = 0.17;                         // noise weight — auto-computed each frame
PHI_S  = 0.03;                         // steric repulsion weight (Priority 2a)
SIGMA  = 4;                            // number of nearest visible neighbours

// ── Mode identifier ───────────────────────────────────────────────────
MODE   = 0;                            // 0 = PROJECTION, 1 = SPATIAL

// ── Priority 1b: Multi-viewpoint Θ′ ──────────────────────────────────
K_VIEWPOINTS = 12;                     // number of observer viewpoints
R_EXT        = 2000;                   // radius of the observer circle

// ── Priority 2a: Steric repulsion ────────────────────────────────────
STERIC_RADIUS = 2 * BOID_SIZE;        // r_s — birds within this repel

// ── Priority 2b: Blind angles ────────────────────────────────────────
BLIND_ANGLE_VAL = %pi / 3;            // β — blind sector width (60°)

// ── Priority 2d: Anisotropic bodies ─────────────────────────────────
BOID_SEMI_MAJOR = BOID_SIZE * 1.4;    // a — length along flight direction
BOID_SEMI_MINOR = BOID_SIZE * 0.7;    // b — width across flight direction

// ── Priority 1c: Correlation time τᵨ ────────────────────────────────
BUFFER_SIZE_TAU      = 500;           // max density snapshots
CORR_SAMPLE_INTERVAL = 10;            // sample every N frames
MAX_LAG_FRACTION     = 0.25;          // integrate up to 25% of buffer

// ── Priority 3b: Spatial optimization ────────────────────────────────
GRID_COLS = 10;
GRID_ROWS = 7;
CELL_W    = WIDTH / GRID_COLS;
CELL_H    = HEIGHT / GRID_ROWS;

// ── Priority 3a: Predator ────────────────────────────────────────────
PREDATOR_SPEED  = V0 * 2.0;           // predator is ~2× faster
PREDATOR_ACCEL  = 0.3;                // hunting acceleration
DANGER_RADIUS   = 120;                // birds within this flee
FLIGHT_FORCE    = 1.5;                // strength of flight response

// ── Dimensionality ────────────────────────────────────────────────────
DIMENSIONS = 2;                        // 2 or 3 (set by ENABLE_2c)

// ── CSV logging ───────────────────────────────────────────────────────
LOG_FILE  = "murmuration_metrics_extended.csv";
LOG_EVERY = 10;


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 2b — CSV LOGGING SETUP                                    ║
// ╚══════════════════════════════════════════════════════════════════════╝
log_fid = mopen(LOG_FILE, "wt");
if log_fid == -1 then
    disp("WARNING: could not open " + LOG_FILE + " for writing");
else        mfprintf(log_fid, "frame,mode,num_boids,phi_p,phi_a,phi_n,phi_s,sigma,theta,theta_ext,tau,alpha,fps,power,angmom,avg_accel\n");
    disp("Logging metrics to " + LOG_FILE + " every " + string(LOG_EVERY) + " frames");
end


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 3 — RUNTIME STATE INITIALIZATION                           ║
// ╚══════════════════════════════════════════════════════════════════════╝

// ── Mutable runtime flags ────────────────────────────────────────────
paused         = %f;
pending_add    = 0;
pending_remove = 0;
pending_reset  = %f;
show_help      = %f;
predator_active = %f;                  // 'f' toggles predator on/off

if ENABLE_2c then
    disp("Initializing 3D flock with " + string(NUM_BOIDS) + " birds ...");
    DIMENSIONS = 3;
else
    disp("Initializing 2D flock with " + string(NUM_BOIDS) + " birds ...");
    DIMENSIONS = 2;
end

// ── State arrays (N × D) ──────────────────────────────────────────
if ENABLE_2c then
    pos  = rand(NUM_BOIDS, 3) .* repmat([WIDTH, HEIGHT, DEPTH], NUM_BOIDS, 1);
    ang  = rand(NUM_BOIDS, 1) * 2 * %pi;
    phi  = (rand(NUM_BOIDS, 1) - 0.5) * %pi;       // elevation
    vel  = [cos(ang).*cos(phi), sin(ang).*cos(phi), sin(phi)] .* V0;
    acc  = zeros(NUM_BOIDS, 3);
else
    pos  = rand(NUM_BOIDS, 2) .* repmat([WIDTH, HEIGHT], NUM_BOIDS, 1);
    ang  = rand(NUM_BOIDS, 1) * 2 * %pi;
    vel  = [cos(ang), sin(ang)] .* repmat(1 + rand(NUM_BOIDS, 1) * (V0 - 1), 1, 2);
    acc  = zeros(NUM_BOIDS, 2);
end
last_theta  = zeros(NUM_BOIDS, 1);
last_density = 0;                      // latest flock density ρ

// ── Priority 1c: Correlation time ring buffer ──────────────────────
tau_buffer  = zeros(BUFFER_SIZE_TAU, 1);
tau_frames  = zeros(BUFFER_SIZE_TAU, 1);
tau_idx     = 1;
tau_count   = 0;
tau_timer   = 0;
tau_val     = 0;                       // latest τᵨ estimate

// ── Priority 3a: Predator state ────────────────────────────────────
predator_pos = [WIDTH/2, HEIGHT/2];
predator_vel = [0, 0];
predator_trail = [];                    // for drawing trail

// ── Priority 3b: Chunk cache (rebuilt each frame) ──────────────────
// Each chunk: [cx, cy, n_birds, centroid_x, centroid_y, radius]
// We store as a struct array: chunk_cells(i).birds, .cx, .cy, .r
chunk_cells = list();                  // list of chunks


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 2c — FIGURE & GRAPHICS SETUP                              ║
// ╚══════════════════════════════════════════════════════════════════════╝

f = figure("Figure_name", "Murmuration Extended  [m:mode p:pause f:falcon h:help]", ...
           "Position", [100, 100, WIDTH, HEIGHT], ...
           "Background", [20, 22, 30] / 255);
f.event_handler = "key_handler";
f.event_handler_enable = "on";

a = gca();
a.data_bounds   = [0, 0; WIDTH, HEIGHT];
a.isoview       = "on";
a.axes_visible  = "off";
a.margins       = [0, 0, 0, 0];

// Pre-register custom colours
HELP_GRAY_IDX = addcolor([80, 80, 80] / 255);
HELP_GOLD_IDX = addcolor([200, 200, 160] / 255);
PREDATOR_RED_IDX = addcolor([255, 80, 60] / 255);


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 4 — ANGULAR-INTERVAL UTILITIES                            ║
// ╚══════════════════════════════════════════════════════════════════════╝

function [merged, n_merged] = merge_angle_intervals(intervals, n_int)
    // Merge overlapping angular intervals on [0, 2π).  O(n_int).
    // Input:  sorted intervals (n_int × 2: [start, end])
    // Output: merged intervals (n_merged × 2)

    merged  = zeros(n_int, 2);
    n_merged = 0;
    j = 1;
    while j <= n_int
        cur_s = intervals(j, 1);
        cur_e = intervals(j, 2);
        k = j + 1;
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


function segments = normalise_interval_2d(start, end_val)
    // Normalise an angular interval [start, end] into [0, 2π) segments.
    // Returns up to 2 segments if the interval wraps.
    segments = zeros(2, 2);
    n_segs = 0;
    if start < 0 then
        n_segs = n_segs + 1; segments(n_segs,:) = [start + 2*%pi, 2*%pi];
        n_segs = n_segs + 1; segments(n_segs,:) = [0, end_val];
    elseif end_val > 2*%pi then
        n_segs = n_segs + 1; segments(n_segs,:) = [start, 2*%pi];
        n_segs = n_segs + 1; segments(n_segs,:) = [0, end_val - 2*%pi];
    else
        n_segs = 1; segments(1,:) = [start, end_val];
    end
    segments = segments(1:n_segs, :);
endfunction


function covered = interval_covered_2d(start, end_val, merged, n_merged)
    // Check if [start, end_val] is fully covered by merged intervals.
    cursor = start;
    for m = 1:n_merged
        if merged(m,1) <= cursor + 1e-9 & cursor < merged(m,2) then
            cursor = max(cursor, merged(m,2));
        end
        if cursor >= end_val - 1e-9 then
            covered = %t;
            return;
        end
    end
    covered = %f;
endfunction


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 5 — GRAHAM SCAN CONVEX HULL  (Priority 1c: τᵨ)            ║
// ╚══════════════════════════════════════════════════════════════════════╝

function area = convex_hull_area_2d(points)
    // Compute area of convex hull of N×2 points using Graham scan.
    // Returns 0 if fewer than 3 points.
    n = size(points, 1);
    if n < 3 then
        area = 0;
        return;
    end

    // Step 1: find pivot (lowest y, then leftmost x)
    pivot_idx = 1;
    for i = 2:n
        if points(i,2) < points(pivot_idx,2) | ...
           (points(i,2) == points(pivot_idx,2) & points(i,1) < points(pivot_idx,1)) then
            pivot_idx = i;
        end
    end
    // Swap pivot to position 1
    tmp = points(1,:); points(1,:) = points(pivot_idx,:); points(pivot_idx,:) = tmp;

    // Step 2: compute polar angles and sort
    n_rest = n - 1;
    polar = zeros(n_rest, 3);  // [angle, dist_sq, original_index]
    for i = 1:n_rest
        dx = points(i+1,1) - points(1,1);
        dy = points(i+1,2) - points(1,2);
        polar(i,1) = atan(dy, dx);
        if polar(i,1) < 0 then polar(i,1) = polar(i,1) + 2*%pi; end
        polar(i,2) = dx*dx + dy*dy;
        polar(i,3) = i + 1;
    end
    // Sort by angle, then distance
    [tmp_sorted, sort_idx] = gsort(polar(:,1), 'g', 'i');
    polar = polar(sort_idx, :);

    // Step 3: build hull
    function c = cross_2d(o, a, b)
        c = (a(1)-o(1))*(b(2)-o(2)) - (a(2)-o(2))*(b(1)-o(1));
    endfunction

    hull = [points(1,:); points(polar(1,3),:)];
    m = 2;
    for i = 2:n_rest
        p_next = points(polar(i,3), :);
        while m >= 2 & cross_2d(hull(m-1,:), hull(m,:), p_next) <= 0
            m = m - 1;
        end
        m = m + 1;
        hull(m,:) = p_next;
    end
    hull = hull(1:m, :);

    // Step 4: shoelace formula
    area = 0;
    for i = 1:m
        j = modulo(i, m) + 1;
        area = area + hull(i,1)*hull(j,2) - hull(j,1)*hull(i,2);
    end
    area = abs(area) / 2;
endfunction


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 6 — SPATIAL CHUNKER  (Priority 3b)                        ║
// ╚══════════════════════════════════════════════════════════════════════╝

function chunks = rebuild_chunker(pos)
    // Rebuild chunk grid from flock positions.  O(N).
    // Returns a list where each element is a struct with:
    //   .key = [cx, cy], .birds = indices, .cx = centroid_x, .cy = centroid_y, .r = radius
    global GRID_COLS GRID_ROWS CELL_W CELL_H BOID_SEMI_MAJOR NUM_BOIDS

    // Pass 1: bin birds
    bins = list();
    for i = 1:NUM_BOIDS
        cx = modulo(floor(pos(i,1) / CELL_W), GRID_COLS);
        cy = modulo(floor(pos(i,2) / CELL_H), GRID_ROWS);
        key = [cx, cy];

        // Find or create bin
        found = %f;
        for b = 1:length(bins)
            if bins(b).key(1) == cx & bins(b).key(2) == cy then
                bins(b).birds($+1) = i;
                found = %t;
                break;
            end
        end
        if ~found then
            new_bin = tlist(["bin","key","birds"], key, [i]);
            bins($+1) = new_bin;
        end
    end

    // Pass 2: compute centroids and bounding radii
    n_chunks = length(bins);
    for c = 1:n_chunks
        indices = bins(c).birds;
        n = length(indices);
        sum_x = sum(pos(indices, 1));
        sum_y = sum(pos(indices, 2));
        centroid_x = sum_x / n;
        centroid_y = sum_y / n;

        max_dist_sq = 0;
        for k = 1:n
            dx = pos(indices(k), 1) - centroid_x;
            dy = pos(indices(k), 2) - centroid_y;
            dsq = dx*dx + dy*dy;
            if dsq > max_dist_sq then max_dist_sq = dsq; end
        end
        radius = sqrt(max_dist_sq) + BOID_SEMI_MAJOR;

        bins(c).cx = centroid_x;
        bins(c).cy = centroid_y;
        bins(c).r  = radius;
    end

    chunks = bins;
endfunction


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 7 — PROJECTION MODEL WITH ALL 2D EXTENSIONS               ║
// ╚══════════════════════════════════════════════════════════════════════╝
//  Priorities: 1a, 2a, 2b, 2d, 3b — all integrated into one function.
// ──────────────────────────────────────────────────────────────────────

function [delta, vis_idx, vis_dists, n_vis, theta] = ...
         compute_projection_extended(i, pos, vel, chunks)
    global NUM_BOIDS BOID_SIZE WIDTH HEIGHT ENABLE_2b ENABLE_2d
    global BLIND_ANGLE_VAL BOID_SEMI_MAJOR BOID_SEMI_MINOR
    global ENABLE_3b GRID_COLS GRID_ROWS CELL_W CELL_H

    // ── Build entries from all other birds ─────────────────────────
    if ENABLE_3b & length(chunks) > 0 then
        // Use spatial chunker for near+far entries
        n_entries = 0;
        entries = zeros(NUM_BOIDS * 2, 4);  // [dist, centre, half, bird_idx]

        // Viewer's cell
        vx = modulo(floor(pos(i,1) / CELL_W), GRID_COLS);
        vy = modulo(floor(pos(i,2) / CELL_H), GRID_ROWS);

        // Phase 1: near birds (3x3 surrounding cells)
        for dx = -1:1
            for dy = -1:1
                cx = modulo(vx + dx, GRID_COLS);
                cy = modulo(vy + dy, GRID_ROWS);
                for c = 1:length(chunks)
                    if chunks(c).key(1) == cx & chunks(c).key(2) == cy then
                        indices = chunks(c).birds;
                        for k = 1:length(indices)
                            j = indices(k);
                            if j == i then continue; end

                            // Toroidal distance
                            dx_b = pos(j,1) - pos(i,1);
                            dy_b = pos(j,2) - pos(i,2);
                            if abs(dx_b) > WIDTH/2 then dx_b = dx_b - sign(dx_b)*WIDTH; end
                            if abs(dy_b) > HEIGHT/2 then dy_b = dy_b - sign(dy_b)*HEIGHT; end
                            dist = sqrt(dx_b*dx_b + dy_b*dy_b);
                            if dist < 0.001 then continue; end

                            centre = atan(dy_b, dx_b);
                            if centre < 0 then centre = centre + 2*%pi; end

                            // Anisotropic half-width
                            if ENABLE_2d then
                                if norm(vel(j,:)) > 0.001 then
                                    psi = atan(vel(j,2), vel(j,1));
                                else psi = 0; end
                                d_ang = centre - psi;
                                proj_rad = sqrt((BOID_SEMI_MAJOR*sin(d_ang))^2 + (BOID_SEMI_MINOR*cos(d_ang))^2);
                                half = asin(min(proj_rad / dist, 1));
                            else
                                half = asin(min(BOID_SIZE / dist, 1));
                            end

                            n_entries = n_entries + 1;
                            entries(n_entries,:) = [dist, centre, half, j];
                        end
                        break;  // each cell appears at most once
                    end
                end
            end
        end

        // Phase 2: far chunks (passive occluders, sentinel j=0)
        for c = 1:length(chunks)
            cx_c = chunks(c).key(1);
            cy_c = chunks(c).key(2);
            dx_wrap = min(abs(cx_c - vx), GRID_COLS - abs(cx_c - vx));
            dy_wrap = min(abs(cy_c - vy), GRID_ROWS - abs(cy_c - vy));
            if dx_wrap <= 1 & dy_wrap <= 1 then continue; end  // near

            // Toroidal distance to chunk centroid
            dx_c = chunks(c).cx - pos(i,1);
            dy_c = chunks(c).cy - pos(i,2);
            if abs(dx_c) > WIDTH/2 then dx_c = dx_c - sign(dx_c)*WIDTH; end
            if abs(dy_c) > HEIGHT/2 then dy_c = dy_c - sign(dy_c)*HEIGHT; end
            dist = sqrt(dx_c*dx_c + dy_c*dy_c);
            if dist < 0.001 then continue; end

            centre = atan(dy_c, dx_c);
            if centre < 0 then centre = centre + 2*%pi; end
            half = asin(min(chunks(c).r / dist, 1));

            n_entries = n_entries + 1;
            entries(n_entries,:) = [dist, centre, half, 0];  // 0 = passive occluder
        end

        entries = entries(1:n_entries, :);
        if n_entries == 0 then
            delta = [0, 0]; vis_idx = []; vis_dists = []; n_vis = 0; theta = 0;
            return;
        end

        // Sort closest-first
        [tmp, sort_idx] = gsort(entries(:,1), 'g', 'i');
        entries = entries(sort_idx, :);

    else
        // O(N²) — all birds
        n_entries = 0;
        entries = zeros(NUM_BOIDS - 1, 4);
        for j = 1:NUM_BOIDS
            if j == i then continue; end
            dx_b = pos(j,1) - pos(i,1);
            dy_b = pos(j,2) - pos(i,2);
            if abs(dx_b) > WIDTH/2 then dx_b = dx_b - sign(dx_b)*WIDTH; end
            if abs(dy_b) > HEIGHT/2 then dy_b = dy_b - sign(dy_b)*HEIGHT; end
            dist = sqrt(dx_b*dx_b + dy_b*dy_b);
            if dist < 0.001 then continue; end

            centre = atan(dy_b, dx_b);
            if centre < 0 then centre = centre + 2*%pi; end

            if ENABLE_2d then
                if norm(vel(j,:)) > 0.001 then
                    psi = atan(vel(j,2), vel(j,1));
                else psi = 0; end
                d_ang = centre - psi;
                proj_rad = sqrt((BOID_SEMI_MAJOR*sin(d_ang))^2 + (BOID_SEMI_MINOR*cos(d_ang))^2);
                half = asin(min(proj_rad / dist, 1));
            else
                half = asin(min(BOID_SIZE / dist, 1));
            end

            n_entries = n_entries + 1;
            entries(n_entries,:) = [dist, centre, half, j];
        end
        entries = entries(1:n_entries, :);
        if n_entries == 0 then
            delta = [0, 0]; vis_idx = []; vis_dists = []; n_vis = 0; theta = 0;
            return;
        end
        [tmp, sort_idx] = gsort(entries(:,1), 'g', 'i');
        entries = entries(sort_idx, :);
    end

    // ── Priority 2b: Blind angles filter ────────────────────────────
    if ENABLE_2b then
        if norm(vel(i,:)) > 0.001 then
            heading = atan(vel(i,2), vel(i,1));
        else heading = 0; end
        if heading < 0 then heading = heading + 2*%pi; end

        blind_centre = heading + %pi;
        if blind_centre >= 2*%pi then blind_centre = blind_centre - 2*%pi; end
        blind_start = blind_centre - BLIND_ANGLE_VAL/2;
        blind_end   = blind_centre + BLIND_ANGLE_VAL/2;
        if blind_start < 0 then blind_start = blind_start + 2*%pi; end
        if blind_end > 2*%pi then blind_end = blind_end - 2*%pi; end

        n_filtered = 0;
        filtered = zeros(n_entries, 4);
        for k = 1:n_entries
            start_k = entries(k,2) - entries(k,3);
            end_k   = entries(k,2) + entries(k,3);
            segs = normalise_interval_2d(start_k, end_k);
            n_segs = size(segs, 1);
            all_blind = %t;
            for s = 1:n_segs
                s1 = segs(s,1); e1 = segs(s,2);
                in_blind = %f;
                if blind_start <= blind_end then
                    if blind_start <= s1 + 1e-9 & e1 <= blind_end + 1e-9 then in_blind = %t; end
                else
                    if (blind_start <= s1 + 1e-9 & e1 <= 2*%pi + 1e-9) | ...
                       (s1 >= -1e-9 & e1 <= blind_end + 1e-9) then in_blind = %t; end
                end
                if ~in_blind then all_blind = %f; break; end
            end
            if ~all_blind then
                n_filtered = n_filtered + 1;
                filtered(n_filtered,:) = entries(k,:);
            end
        end
        entries = filtered(1:n_filtered, :);
        n_entries = n_filtered;
    end

    if n_entries == 0 then
        delta = [0, 0]; vis_idx = []; vis_dists = []; n_vis = 0; theta = 0;
        return;
    end

    // ── Incremental occlusion merge ────────────────────────────────
    merged    = zeros(n_entries * 2, 2);
    n_merged  = 0;
    vis_idx   = zeros(n_entries, 1);
    vis_dists = zeros(n_entries, 1);
    n_vis     = 0;

    for k = 1:n_entries
        bird_j   = entries(k, 4);
        d_j      = entries(k, 1);
        centre_j = entries(k, 2);
        half_j   = entries(k, 3);

        start_j = centre_j - half_j;
        end_j   = centre_j + half_j;
        segs = normalise_interval_2d(start_j, end_j);
        n_segs = size(segs, 1);

        is_visible = %f;
        for s = 1:n_segs
            if ~interval_covered_2d(segs(s,1), segs(s,2), merged, n_merged) then
                is_visible = %t;
                break;
            end
        end

        if is_visible then
            // Passive occluders (bird_j == 0) merge but don't count as visible
            if bird_j > 0 then
                n_vis = n_vis + 1;
                vis_idx(n_vis)   = bird_j;
                vis_dists(n_vis) = d_j;
            end

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

    vis_idx   = vis_idx(1:n_vis);
    vis_dists = vis_dists(1:n_vis);
    merged    = merged(1:n_merged, :);

    // ── δ̂ from domain boundaries ──────────────────────────────────
    delta = [0, 0];
    if n_merged == 1 & merged(1,1) < 1e-9 & merged(1,2) > 2*%pi - 1e-9 then
        delta = [0, 0];
    else
        for m = 1:n_merged
            delta = delta + [cos(merged(m,1)), sin(merged(m,1))];
            delta = delta + [cos(merged(m,2)), sin(merged(m,2))];
        end
        dnorm = norm(delta);
        if dnorm > 1e-9 then delta = delta / dnorm; end
    end

    // ── Internal opacity Θ_i ───────────────────────────────────────
    if n_merged > 0 then
        occluded = sum(merged(:,2) - merged(:,1));
        theta = min(occluded / (2 * %pi), 1.0);
    else
        theta = 0;
    end
endfunction


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 7b — 3D PROJECTION MODEL (Priority 2c)                    ║
// ╚══════════════════════════════════════════════════════════════════════╝
//  Fibonacci sphere z-buffered spherical cap occlusion.
// ──────────────────────────────────────────────────────────────────────

function fib_pts = fibonacci_sphere_3d(n)
    // Generate n points on the unit sphere using the Fibonacci spiral.
    // Returns n×3 array of [x, y, z] unit vectors.
    gold_phi = %pi * (3 - sqrt(5));
    fib_pts = zeros(n, 3);
    n1 = max(n, 2);
    for k = 1:n1
        y = 1 - (2*(k-1) + 1) / n1;
        radius = sqrt(1 - y*y);
        theta = gold_phi * (k - 1);
        fib_pts(k,1) = cos(theta) * radius;
        fib_pts(k,2) = y;
        fib_pts(k,3) = sin(theta) * radius;
    end
endfunction


function [delta, vis_idx, vis_dists, n_vis, theta] = ...
         compute_projection_3d(i, pos, vel)
    global NUM_BOIDS BOID_SIZE WIDTH HEIGHT DEPTH ENABLE_2b BLIND_ANGLE_VAL

    n_fib = 80;  // Fibonacci sphere resolution
    N = NUM_BOIDS;

    // ── Build entries: (boid, dist, dir_x, dir_y, dir_z, ang_radius) ──
    n_entries = 0;
    max_entries = N - 1;
    for j = 1:N
        if j == i then continue; end

        // Toroidal distance in 3D
        dx = pos(j,1) - pos(i,1);
        dy = pos(j,2) - pos(i,2);
        dz = pos(j,3) - pos(i,3);
        if abs(dx) > WIDTH/2 then dx = dx - sign(dx)*WIDTH; end
        if abs(dy) > HEIGHT/2 then dy = dy - sign(dy)*HEIGHT; end
        if abs(dz) > DEPTH/2 then dz = dz - sign(dz)*DEPTH; end

        dist = sqrt(dx*dx + dy*dy + dz*dz);
        if dist < 0.001 then continue; end

        n_entries = n_entries + 1;
        entries(n_entries, 1) = j;                       // bird index
        entries(n_entries, 2) = dist;                     // distance
        entries(n_entries, 3) = dx / dist;                // direction x
        entries(n_entries, 4) = dy / dist;                // direction y
        entries(n_entries, 5) = dz / dist;                // direction z
        entries(n_entries, 6) = asin(min(BOID_SIZE / dist, 1));  // angular radius
    end

    if n_entries == 0 then
        delta = [0, 0, 0]; vis_idx = []; vis_dists = []; n_vis = 0; theta = 0;
        return;
    end

    // ── Sort closest-first ─────────────────────────────────────────
    [tmp, sort_idx] = gsort(entries(1:n_entries,2), 'g', 'i');

    // ── Priority 2b: Blind cone in 3D ──────────────────────────────
    if ENABLE_2b then
        // Determine heading
        vn = norm(vel(i,:));
        if vn > 0.001 then
            hx = vel(i,1)/vn; hy = vel(i,2)/vn; hz = vel(i,3)/vn;
        else
            hx = 1; hy = 0; hz = 0;
        end
        cos_blind = cos(BLIND_ANGLE_VAL / 2);

        n_filtered = 0;
        filtered = zeros(n_entries, 6);
        for k = 1:n_entries
            idx = sort_idx(k);
            // Dot product of heading with direction to bird → if > cos(π−β/2)=−cos(β/2), it's outside blind cone
            dot_vb = -(hx*entries(idx,3) + hy*entries(idx,4) + hz*entries(idx,5));
            // Blind cone: dot < −cos(β/2) means inside blind cone → invisible
            cos_ang_radius = cos(entries(idx,6));
            // Check if entire cap is within blind cone
            if dot_vb + cos_ang_radius < -cos_blind then
                continue;  // entirely in blind cone
            end
            n_filtered = n_filtered + 1;
            filtered(n_filtered,:) = entries(idx,:);
        end
        entries_f = filtered(1:n_filtered, :);
        n_eff = n_filtered;
    else
        // Reorder by sort_idx
        entries_f = entries(sort_idx, :);
        n_eff = n_entries;
    end

    if n_eff == 0 then
        delta = [0, 0, 0]; vis_idx = []; vis_dists = []; n_vis = 0; theta = 0;
        return;
    end

    // ── Fibonacci sphere z-buffer ──────────────────────────────────
    fib = fibonacci_sphere_3d(n_fib);
    zbuf = -ones(n_fib, 1);    // -1 = unoccluded
    vis_idx = zeros(n_eff, 1);
    vis_dists = zeros(n_eff, 1);
    n_vis = 0;

    for k = 1:n_eff
        dir_x = entries_f(k, 3);
        dir_y = entries_f(k, 4);
        dir_z = entries_f(k, 5);
        ang_r = entries_f(k, 6);
        cos_r = cos(ang_r);
        d_j   = entries_f(k, 2);

        // Check if any Fibonacci point in this cap is unoccluded
        visible = %f;
        for p = 1:n_fib
            if zbuf(p) < 0 | d_j < zbuf(p) then
                dot_p = fib(p,1)*dir_x + fib(p,2)*dir_y + fib(p,3)*dir_z;
                if dot_p >= cos_r then
                    visible = %t;
                    break;
                end
            end
        end

        if visible then
            n_vis = n_vis + 1;
            vis_idx(n_vis) = entries_f(k, 1);
            vis_dists(n_vis) = d_j;

            // Update z-buffer
            for p = 1:n_fib
                dot_p = fib(p,1)*dir_x + fib(p,2)*dir_y + fib(p,3)*dir_z;
                if dot_p >= cos_r then
                    if zbuf(p) < 0 | d_j < zbuf(p) then
                        zbuf(p) = d_j;
                    end
                end
            end
        end
    end

    vis_idx = vis_idx(1:n_vis);
    vis_dists = vis_dists(1:n_vis);

    // ── δ̂ in 3D: average of unoccluded Fibonacci points ──────────
    delta = [0, 0, 0];
    n_unocc = 0;
    for p = 1:n_fib
        if zbuf(p) < 0 then
            delta = delta + [fib(p,1), fib(p,2), fib(p,3)];
            n_unocc = n_unocc + 1;
        end
    end
    if n_unocc > 0 then
        delta = delta / n_unocc;
        dnorm = norm(delta);
        if dnorm > 1e-9 then delta = delta / dnorm; end
    end

    // ── Internal opacity Θ_i = fraction of sphere occluded ────────
    n_occ = 0;
    for p = 1:n_fib
        if zbuf(p) > 0 then n_occ = n_occ + 1; end
    end
    theta = n_occ / n_fib;
endfunction


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 8 — MULTI-VIEWPOINT EXTERNAL OPACITY  (Priority 1b)       ║
// ╚══════════════════════════════════════════════════════════════════════╝

function theta_ext = compute_external_opacity_multi(pos)
    global NUM_BOIDS BOID_SIZE ENABLE_1b K_VIEWPOINTS R_EXT WIDTH HEIGHT

    if ~ENABLE_1b then
        // Fallback: single viewpoint at (-2000, HEIGHT/2)
        viewpoint = [-2000, HEIGHT/2];
        diffs  = pos - ones(NUM_BOIDS,1) * viewpoint;
        dists  = sqrt(sum(diffs.^2, 2));
        angles = atan(diffs(:,2), diffs(:,1));
        neg_mask = angles < 0;
        angles(neg_mask) = angles(neg_mask) + 2 * %pi;
        half = asin(min(BOID_SIZE ./ dists, 1));

        intervals = zeros(NUM_BOIDS * 2, 2);
        n_int = 0;
        for k = 1:NUM_BOIDS
            s = angles(k) - half(k);
            e = angles(k) + half(k);
            segs = normalise_interval_2d(s, e);
            for ss = 1:size(segs,1)
                n_int = n_int + 1;
                intervals(n_int,:) = segs(ss,:);
            end
        end
        if n_int == 0 then theta_ext = 0; return; end
        intervals = intervals(1:n_int, :);
        [tmp, idx] = gsort(intervals(:,1), 'g', 'i');
        intervals = intervals(idx, :);
        [merged, n_m] = merge_angle_intervals(intervals, n_int);
        occluded = sum(merged(:,2) - merged(:,1));
        theta_ext = min(occluded / (2 * %pi), 1.0);
        return;
    end

    // Multi-viewpoint: average over K viewpoints
    total = 0;
    for vp = 0:K_VIEWPOINTS-1
        theta_vp = 2 * %pi * vp / K_VIEWPOINTS;
        viewpoint = [R_EXT * cos(theta_vp), R_EXT * sin(theta_vp)];

        intervals = zeros(NUM_BOIDS * 2, 2);
        n_int = 0;
        for k = 1:NUM_BOIDS
            dx = pos(k,1) - viewpoint(1);
            dy = pos(k,2) - viewpoint(2);
            dist = sqrt(dx*dx + dy*dy);
            if dist < 0.001 then continue; end
            centre = atan(dy, dx);
            if centre < 0 then centre = centre + 2*%pi; end
            half = asin(min(BOID_SIZE / dist, 1));
            segs = normalise_interval_2d(centre - half, centre + half);
            for ss = 1:size(segs,1)
                n_int = n_int + 1;
                intervals(n_int,:) = segs(ss,:);
            end
        end
        if n_int > 0 then
            intervals = intervals(1:n_int, :);
            [tmp, idx] = gsort(intervals(:,1), 'g', 'i');
            intervals = intervals(idx, :);
            [merged, n_m] = merge_angle_intervals(intervals, n_int);
            occluded = sum(merged(:,2) - merged(:,1));
            total = total + min(occluded / (2 * %pi), 1.0);
        end
    end
    theta_ext = total / K_VIEWPOINTS;
endfunction


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 9 — CORRELATION TIME COMPUTATION  (Priority 1c)           ║
// ╚══════════════════════════════════════════════════════════════════════╝

function new_tau = compute_tau_from_buffer()
    global tau_buffer tau_frames tau_count BUFFER_SIZE_TAU CORR_SAMPLE_INTERVAL MAX_LAG_FRACTION

    m = tau_count;
    if m < 10 then new_tau = 0; return; end

    // Unroll ring buffer
    dens = zeros(m, 1);
    for i = 1:m
        idx = modulo(tau_idx - m + i - 2, BUFFER_SIZE_TAU) + 1;
        dens(i) = tau_buffer(idx);
    end

    mean_d = mean(dens);
    vari = sum((dens - mean_d).^2) / m;
    if vari < 1e-12 then new_tau = 0; return; end

    max_lag = max(1, floor(m * MAX_LAG_FRACTION));
    dt = CORR_SAMPLE_INTERVAL;
    tau_sum = 0;

    for lag = 0:max_lag-1
        n_pairs = m - lag;
        if n_pairs < 2 then break; end

        cross = 0;
        for i = 1:n_pairs
            cross = cross + dens(i) * dens(i + lag);
        end
        cross = cross / n_pairs;
        c = cross - mean_d * mean_d;
        if c <= 0 then break; end
        tau_sum = tau_sum + c * dt;
    end

    new_tau = tau_sum / vari;
endfunction


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 10 — HELP OVERLAY                                          ║
// ╚══════════════════════════════════════════════════════════════════════╝

// Helper for help overlay — MUST be defined BEFORE _draw_help_overlay_ext
function s = iif(cond, t_str, f_str)
    if cond then s = t_str; else s = f_str; end
endfunction


function _draw_help_overlay_ext()
    global WIDTH HEIGHT HELP_GRAY_IDX HELP_GOLD_IDX ENABLE_1a ENABLE_2a ENABLE_2b ENABLE_2c ENABLE_2d ENABLE_3a ENABLE_3b

    lines = [..
        "CONTROLS                                       EXTENSIONS";..
        "────────────────────────────────────────  ────────────────────";..
        "m      toggle  PROJECTION / SPATIAL    " + iif(ENABLE_1a,"1a ✓ direct velocity","1a ✗");..
        "p      pause / resume                  " + iif(ENABLE_2a,"2a ✓ steric","2a ✗");..
        "f      toggle predator                 " + iif(ENABLE_2b,"2b ✓ blind","2b ✗");..
        "r      reset flock                     " + iif(ENABLE_2c,"2c ✓ 3D","2c ✗");..
        "h      hide this help                  " + iif(ENABLE_2d,"2d ✓ aniso","2d ✗");..
        "↑/↓    φp  ±0.01                       " + iif(ENABLE_3a,"3a ✓ predator","3a ✗");..
        "←/→    φa  ±0.01                       " + iif(ENABLE_3b,"3b ✓ chunker","3b ✗");..
        "[ / ]  σ   ±1                          φp=proj φa=align φn=noise";..
        "+ / -  add / remove 10 birds           φs=steric σ=neighbours";..
        "ESC    close window to quit";..
    ];
    n_lines = size(lines, 1);

    px = WIDTH - 450;
    py = 5;
    pw = 440;
    ph = n_lines * 16 + 8;

    xrect(px, HEIGHT - py - ph, pw, ph);
    r = gce();
    r.background = color("black");
    r.fill_mode  = "on";
    r.foreground = HELP_GRAY_IDX;
    r.line_mode  = "on";

    for i = 1:n_lines
        xstring(px + 6, HEIGHT - py - 16*i - 4, lines(i));
        th = gce();
        th.font_size  = 1;
        th.font_color = HELP_GOLD_IDX;
    end
endfunction


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 11 — INPUT HANDLING  (keyboard callback)                   ║
// ╚══════════════════════════════════════════════════════════════════════╝

function key_handler(win_id, x, y, ibut)
    global MODE paused PHI_P PHI_A SIGMA pending_add pending_remove pending_reset show_help predator_active
    if ibut < 0 then
        k = abs(ibut);

        if k == 109 | k == 77 then  // m/M — mode toggle
            MODE = 1 - MODE;
            if MODE == 0 then disp("PROJECTION mode");
            else              disp("SPATIAL mode"); end

        elseif k == 112 then  // p — pause
            paused = ~paused;
            if paused then disp("Paused"); else disp("Resumed"); end

        elseif k == 38 | k == 65362 then  // up — φp+
            PHI_P = min(1.0, PHI_P + 0.01);
            disp("phi_p = " + string(PHI_P));
        elseif k == 40 | k == 65364 then  // down — φp-
            PHI_P = max(0.0, PHI_P - 0.01);
            disp("phi_p = " + string(PHI_P));

        elseif k == 37 | k == 65361 then  // left — φa-
            PHI_A = max(0.0, PHI_A - 0.01);
            disp("phi_a = " + string(PHI_A));
        elseif k == 39 | k == 65363 then  // right — φa+
            PHI_A = min(1.0, PHI_A + 0.01);
            disp("phi_a = " + string(PHI_A));

        elseif k == 91 then  // [ — σ-
            SIGMA = max(1, SIGMA - 1);
            disp("sigma = " + string(SIGMA));
        elseif k == 93 then  // ] — σ+
            SIGMA = min(50, SIGMA + 1);
            disp("sigma = " + string(SIGMA));

        elseif k == 43 | k == 61 then  // +/=
            pending_add = min(pending_add + 10, 200);
            disp("Adding 10 birds (pending)");
        elseif k == 45 then  // -
            pending_remove = pending_remove + 10;
            disp("Removing 10 birds (pending)");

        elseif k == 114 | k == 82 then  // r/R
            pending_reset = %t;
            disp("Resetting flock...");

        elseif k == 70 | k == 102 then  // f/F — toggle predator (falcon)
            predator_active = ~predator_active;
            if predator_active then disp("Predator ON"); else disp("Predator OFF"); end

        elseif k == 104 | k == 72 then  // h/H
            show_help = ~show_help;
            if show_help then disp("Help ON"); else disp("Help OFF"); end
        end
    end
endfunction


// ╔══════════════════════════════════════════════════════════════════════╗
// ║  SECTION 12 — MAIN LOOP                                             ║
// ╚══════════════════════════════════════════════════════════════════════╝

frame    = 0;
running  = %t;
smooth   = 0.05;
theta_ema     = 0;
theta_ext_ema = 0;
alpha_ema     = 0;
tau_ema       = 0;
power_ema     = 0;     // P  — mean power (EMA)
angmom_ema    = 0;     // L  — mean angular momentum (EMA)
avg_accel_ema = 0;     // |a| — mean acceleration magnitude (EMA)

// Triangle vertex offsets
tip_len   = BOID_SIZE * 2.5;
side_len  = BOID_SIZE * 1.5;
side_ang  = 2.3;

mode_names = ["PROJECTION  (Pearce et al. 2014) Extended", ...
              "SPATIAL     (topological Reynolds)  Extended"];

disp("Running — close the figure window to stop.");
disp("  9 roadmap priorities active (see ''h'' for feature flags)");
disp("  Keys:  m:mode  p:pause  f:falcon  h:help  arrows:phi  []:sigma  +/-:boids  r:reset");

while running
    t_frame = tic();

    if ~is_handle_valid(f) then break; end

    if ~paused then

        // ═══════════════════════════════════════════════════════════════
        //  PHASE 1 — APPLY PENDING CHANGES
        //    • Auto-compute φn = 1 − φp − φa − φs
        //    • Add / remove birds, reset flock
        // ═══════════════════════════════════════════════════════════════
        // ⇔ Octave: alg2_extended.m SECTION 11, steps 1–1c
        // ⇔ Python: flock_core.py §main loop (state management)

        // ── Auto-compute φn ─────────────────────────────────────────
        PHI_N = max(0.0, 1.0 - PHI_P - PHI_A - PHI_S);

        // ── Boid count changes ──────────────────────────────────────
        if pending_remove > 0 then
            n_remove = min(pending_remove, NUM_BOIDS - 1);
            if n_remove > 0 then
                pos        = pos(1:NUM_BOIDS - n_remove, :);
                vel        = vel(1:NUM_BOIDS - n_remove, :);
                acc        = acc(1:NUM_BOIDS - n_remove, :);
                last_theta = last_theta(1:NUM_BOIDS - n_remove);
                NUM_BOIDS  = NUM_BOIDS - n_remove;
                pending_remove = pending_remove - n_remove;
                disp("Removed " + string(n_remove) + " birds, now " + string(NUM_BOIDS));
            end
        end
        if pending_add > 0 then
            n_add = pending_add;
            new_ang = rand(n_add, 1) * 2 * %pi;
            if ENABLE_2c then
                new_pos = rand(n_add, 3) .* repmat([WIDTH, HEIGHT, DEPTH], n_add, 1);
                new_phi = (rand(n_add, 1) - 0.5) * %pi;
                new_vel = [cos(new_ang).*cos(new_phi), sin(new_ang).*cos(new_phi), sin(new_phi)] .* V0;
                new_acc = zeros(n_add, 3);
            else
                new_pos = rand(n_add, 2) .* repmat([WIDTH, HEIGHT], n_add, 1);
                new_vel = [cos(new_ang), sin(new_ang)] .* repmat(1 + rand(n_add, 1) * (V0 - 1), 1, 2);
                new_acc = zeros(n_add, 2);
            end
            pos        = [pos; new_pos];
            vel        = [vel; new_vel];
            acc        = [acc; new_acc];
            last_theta = [last_theta; zeros(n_add, 1)];
            NUM_BOIDS  = NUM_BOIDS + n_add;
            pending_add = 0;
            disp("Added " + string(n_add) + " birds, now " + string(NUM_BOIDS));
        end

        // ── Reset ───────────────────────────────────────────────────
        if pending_reset then
            if ENABLE_2c then
                pos = rand(NUM_BOIDS, 3) .* repmat([WIDTH, HEIGHT, DEPTH], NUM_BOIDS, 1);
                ang = rand(NUM_BOIDS, 1) * 2 * %pi;
                phi = (rand(NUM_BOIDS, 1) - 0.5) * %pi;
                vel = [cos(ang).*cos(phi), sin(ang).*cos(phi), sin(phi)] .* V0;
                acc = zeros(NUM_BOIDS, 3);
            else
                pos = rand(NUM_BOIDS, 2) .* repmat([WIDTH, HEIGHT], NUM_BOIDS, 1);
                ang = rand(NUM_BOIDS, 1) * 2 * %pi;
                vel = [cos(ang), sin(ang)] .* (1 + rand(NUM_BOIDS, 1) * (V0 - 1));
                acc = zeros(NUM_BOIDS, 2);
            end
            last_theta = zeros(NUM_BOIDS, 1);
            theta_ema = 0; theta_ext_ema = 0; alpha_ema = 0; tau_ema = 0; power_ema = 0; angmom_ema = 0; avg_accel_ema = 0;
            tau_count = 0; tau_idx = 1; tau_timer = 0;
            frame = 0;
            pending_reset = %f;
            disp("Flock reset — " + string(NUM_BOIDS) + " birds");
        end

        // ═══════════════════════════════════════════════════════════════
        //  PHASE 2 — REBUILD SPATIAL CHUNKER  (Priority 3b)
        //    Grid-based spatial index for O(N) nearest-neighbour lookup.
        //    Rebuilt every frame since birds move.
        // ═══════════════════════════════════════════════════════════════
        // ⇔ Python: extensions/spatial_optimization.py §rebuild_grid
        // ⇔ Octave: alg2_extended.m SECTION 6 + main loop step 2
        if ENABLE_3b & ~ENABLE_2c then
            chunk_cells = rebuild_chunker(pos);
        else
            chunk_cells = list();
        end

        // ═══════════════════════════════════════════════════════════════
        //  PHASE 3 — UPDATE PREDATOR  (Priority 3a)
        //    Falcon hunts nearest bird at ~2× cruising speed.
        //    Trail of last 20 positions stored for rendering.
        // ═══════════════════════════════════════════════════════════════
        // ⇔ Python: extensions/predator.py §PredatorAgent
        // ⇔ Octave: alg2_extended.m main loop step 3
        if ENABLE_3a & predator_active & ~ENABLE_2c then
            // Find nearest bird
            nearest_dist = %inf;
            nearest_idx = 1;
            for i = 1:NUM_BOIDS
                dx_p = pos(i,1) - predator_pos(1);
                dy_p = pos(i,2) - predator_pos(2);
                if abs(dx_p) > WIDTH/2 then dx_p = dx_p - sign(dx_p)*WIDTH; end
                if abs(dy_p) > HEIGHT/2 then dy_p = dy_p - sign(dy_p)*HEIGHT; end
                d = sqrt(dx_p*dx_p + dy_p*dy_p);
                if d < nearest_dist then nearest_dist = d; nearest_idx = i; end
            end

            // Hunt toward nearest bird
            to_target = pos(nearest_idx,:) - predator_pos;
            dx_tt = to_target(1); dy_tt = to_target(2);
            if abs(dx_tt) > WIDTH/2 then dx_tt = dx_tt - sign(dx_tt)*WIDTH; end
            if abs(dy_tt) > HEIGHT/2 then dy_tt = dy_tt - sign(dy_tt)*HEIGHT; end
            dist_tt = sqrt(dx_tt*dx_tt + dy_tt*dy_tt);
            if dist_tt > 0.001 then
                predator_acc = [dx_tt/dist_tt, dy_tt/dist_tt] * PREDATOR_ACCEL;
            else
                predator_acc = [0, 0];
            end
            // Noise
            na = rand() * 2 * %pi;
            predator_acc = predator_acc + [cos(na), sin(na)] * PREDATOR_ACCEL * 0.3;

            predator_vel = predator_vel + predator_acc;
            spd_p = norm(predator_vel);
            if spd_p > PREDATOR_SPEED then predator_vel = predator_vel / spd_p * PREDATOR_SPEED; end
            if spd_p < PREDATOR_SPEED * 0.3 & spd_p > 0.001 then predator_vel = predator_vel / spd_p * PREDATOR_SPEED * 0.3; end

            predator_pos = predator_pos + predator_vel;
            predator_pos(1) = modulo(predator_pos(1), WIDTH);
            predator_pos(2) = modulo(predator_pos(2), HEIGHT);

            // Track trail
            predator_trail = [predator_trail; predator_pos];
            if size(predator_trail,1) > 20 then
                predator_trail = predator_trail(2:$, :);
            end
        end

        // ═══════════════════════════════════════════════════════════════
        //  PHASE 4 — FLOCKING UPDATE
        //    MODE 0 (PROJECTION): v_i = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂  (Eq. 3)
        //      • 2D: compute_projection_extended (angular-interval occlusion)
        //      • 3D: compute_projection_3d (Fibonacci sphere z-buffer)
        //      • Priority 1a: Direct velocity setting (skip Reynolds steer)
        //      • Priority 2a: Steric repulsion (1/r² force, O(N²) per bird)
        //    MODE 1 (SPATIAL): Separation/Alignment/Cohesion (Reynolds 1987)
        // ═══════════════════════════════════════════════════════════════
        // ⇔ Python: extensions/direct_velocity.py + flock_core.py
        // ⇔ Octave: alg2_extended.m SECTION 7 + main loop step 4
        if MODE == 0 then
            if ENABLE_2c then
                // ── 3D Projection ──────────────────────────────────
                for i = 1:NUM_BOIDS
                    [delta, vis_idx, vis_dists, n_vis, theta] = ...
                        compute_projection_3d(i, pos, vel);
                    last_theta(i) = theta;

                    align = [0, 0, 0];
                    if n_vis > 0 then
                        sigma_use = min(SIGMA, n_vis);
                        for k = 1:sigma_use
                            j_vis = vis_idx(k);
                            align = align + vel(j_vis, :);
                        end
                        align = align / sigma_use;
                    end

                    na1 = rand() * 2 * %pi;
                    na2 = (rand() - 0.5) * %pi;
                    noise = [cos(na1)*cos(na2), sin(na1)*cos(na2), sin(na2)];

                    desired = delta * PHI_P;
                    if norm(align) > 0.001 then
                        desired = desired + (align / norm(align)) * PHI_A;
                    else
                        if norm(vel(i,:)) > 0.001 then
                            desired = desired + (vel(i,:) / norm(vel(i,:))) * PHI_A;
                        end
                    end
                    desired = desired + noise * PHI_N;

                    if norm(desired) < 0.001 then
                        desired = [rand()*2-1, rand()*2-1, rand()*2-1];
                    end
                    desired = desired / norm(desired) * V0;

                    if ENABLE_1a then
                        // Direct velocity setting (Priority 1a)
                        vel(i,:) = desired;
                    else
                        steer = desired - vel(i,:);
                        if norm(steer) > MAX_FORCE then steer = steer / norm(steer) * MAX_FORCE; end
                        acc(i,:) = acc(i,:) + steer;
                    end
                end

            else
                // ── 2D Projection ──────────────────────────────────
                for i = 1:NUM_BOIDS
                    [delta, vis_idx, vis_dists, n_vis, theta] = ...
                        compute_projection_extended(i, pos, vel, chunk_cells);
                    last_theta(i) = theta;

                    align = [0, 0];
                    if n_vis > 0 then
                        sigma_use = min(SIGMA, n_vis);
                        for k = 1:sigma_use
                            j_vis = vis_idx(k);
                            align = align + vel(j_vis, :);
                        end
                        align = align / sigma_use;
                    end

                    na = rand() * 2 * %pi;
                    noise = [cos(na), sin(na)];

                    desired = delta * PHI_P;
                    if norm(align) > 0.001 then
                        desired = desired + (align / norm(align)) * PHI_A;
                    else
                        if norm(vel(i,:)) > 0.001 then
                            desired = desired + (vel(i,:) / norm(vel(i,:))) * PHI_A;
                        end
                    end
                    desired = desired + noise * PHI_N;

                    if norm(desired) < 0.001 then
                        desired = [rand()*2-1, rand()*2-1];
                    end
                    desired = desired / norm(desired) * V0;

                    if ENABLE_1a then
                        // Priority 1a: Direct velocity setting
                        vel(i,:) = desired;
                    else
                        steer = desired - vel(i,:);
                        if norm(steer) > MAX_FORCE then steer = steer / norm(steer) * MAX_FORCE; end
                        acc(i,:) = acc(i,:) + steer;
                    end

                    // ── Priority 2a: Steric repulsion ─────────────
                    if ENABLE_2a then
                        repulsion = [0, 0];
                        for j = 1:NUM_BOIDS
                            if j == i then continue; end
                            diff = pos(i,:) - pos(j,:);
                            dx_r = diff(1); dy_r = diff(2);
                            if abs(dx_r) > WIDTH/2 then dx_r = dx_r - sign(dx_r)*WIDTH; end
                            if abs(dy_r) > HEIGHT/2 then dy_r = dy_r - sign(dy_r)*HEIGHT; end
                            d = sqrt(dx_r*dx_r + dy_r*dy_r);
                            if d < STERIC_RADIUS & d > 0.001 then
                                repulsion = repulsion + [dx_r/d, dy_r/d] / (d * d);
                            end
                        end
                        if norm(repulsion) > 0.001 then
                            repulsion = repulsion / norm(repulsion) * PHI_S * BOID_SIZE;
                            vel(i,:) = vel(i,:) + repulsion;
                            if norm(vel(i,:)) > 0.001 then
                                vel(i,:) = vel(i,:) / norm(vel(i,:)) * V0;
                            end
                        end
                    end
                end
            end

        else
            // ── MODE 1: SPATIAL (Reynolds boids) ──────────────────
            dx = ones(NUM_BOIDS,1)*pos(:,1)' - pos(:,1)*ones(1,NUM_BOIDS);
            dy = ones(NUM_BOIDS,1)*pos(:,2)' - pos(:,2)*ones(1,NUM_BOIDS);
            dist_mat = sqrt(dx.^2 + dy.^2);

            for i = 1:NUM_BOIDS
                row = dist_mat(i, :); row(i) = %inf;
                in_range = find(row < VISUAL_RANGE);

                sep = [0, 0]; ali = [0, 0]; coh = [0, 0];

                if ~isempty(in_range) then
                    range_dists = row(in_range);
                    [sorted, sort_idx] = gsort(range_dists, 'g', 'i');
                    sigma_use = min(SIGMA, length(in_range));
                    nbs = in_range(sort_idx(1:sigma_use));

                    for k = 1:sigma_use
                        j = nbs(k);
                        d_ij = dist_mat(i, j);
                        ali = ali + vel(j, :);
                        coh = coh + pos(j, :);
                        if d_ij < VISUAL_RANGE * 0.3 & d_ij > 0.001 then
                            diff_ij = pos(i,:) - pos(j,:);
                            sep = sep + diff_ij / d_ij;
                        end
                    end

                    ali = ali / sigma_use;
                    coh = coh / sigma_use;

                    if norm(ali) > 0.001 then ali = ali / norm(ali) * V0; end
                    ali = ali - vel(i,:);
                    if norm(ali) > MAX_FORCE then ali = ali / norm(ali) * MAX_FORCE; end

                    coh = coh - pos(i,:);
                    if norm(coh) > 0.001 then coh = coh / norm(coh) * V0; end
                    coh = coh - vel(i,:);
                    if norm(coh) > MAX_FORCE then coh = coh / norm(coh) * MAX_FORCE; end

                    if norm(sep) > 0.001 then sep = sep / norm(sep) * V0; end
                    sep = sep - vel(i,:);
                    if norm(sep) > MAX_FORCE then sep = sep / norm(sep) * MAX_FORCE; end
                end

                na = rand() * 2 * %pi;
                noise = [cos(na), sin(na)] * MAX_FORCE * 0.8;

                acc(i,:) = acc(i,:) + sep * PHI_P * 2.0;
                acc(i,:) = acc(i,:) + ali * PHI_A * 1.2;
                acc(i,:) = acc(i,:) + coh * PHI_N * 1.5;
                acc(i,:) = acc(i,:) + noise;
            end
        end

        // ═══════════════════════════════════════════════════════════════
        //  PHASE 5 — PREDATOR FLIGHT RESPONSE  (Priority 3a)
        //    Birds within DANGER_RADIUS flee away from the falcon.
        //    Force ∝ (DANGER_RADIUS − d) / DANGER_RADIUS (linear decay).
        // ═══════════════════════════════════════════════════════════════
        // ⇔ Python: extensions/predator.py §PredatorAgent
        // ⇔ Octave: alg2_extended.m main loop step 5
        if ENABLE_3a & predator_active & ~ENABLE_2c then
            for i = 1:NUM_BOIDS
                diff_p = pos(i,:) - predator_pos;
                dx_p = diff_p(1); dy_p = diff_p(2);
                if abs(dx_p) > WIDTH/2 then dx_p = dx_p - sign(dx_p)*WIDTH; end
                if abs(dy_p) > HEIGHT/2 then dy_p = dy_p - sign(dy_p)*HEIGHT; end
                d = sqrt(dx_p*dx_p + dy_p*dy_p);
                if d < DANGER_RADIUS & d > 0.001 then
                    flight = [dx_p/d, dy_p/d] * FLIGHT_FORCE * ((DANGER_RADIUS - d) / DANGER_RADIUS);
                    vel(i,:) = vel(i,:) + flight;
                    if norm(vel(i,:)) > 0.001 then
                        vel(i,:) = vel(i,:) / norm(vel(i,:)) * V0;
                    end
                end
            end
        end

        // ═══════════════════════════════════════════════════════════════
        //  PHASE 6 — PHYSICS UPDATE
        //    Euler integration: v ← v + a, p ← p + v.
        //    Speed clamped to [0.3·V₀, V₀]; toroidal wrap at edges.
        //    Skipped when ENABLE_1a (velocity set directly from Eq. 3).
        // ═══════════════════════════════════════════════════════════════
        // ⇔ Python: extensions/direct_velocity.py §Step 5
        // ⇔ Octave: alg2_extended.m main loop step 6

        // ── Power & angular momentum (computed BEFORE acc cleared) ──
        // ⇔ Python: metrics.py §FlockMetrics.update
        // ⇔ Octave: alg2_extended.m §PHASE 6
        if ~ENABLE_2c then
            power_raw  = mean(sum(acc .* vel, 2));
            angmom_raw = mean(pos(:,1) .* vel(:,2) - pos(:,2) .* vel(:,1));
            power_ema  = power_ema  + (power_raw  - power_ema)  * smooth;
            angmom_ema = angmom_ema + (angmom_raw - angmom_ema) * smooth;

            // Avg acceleration magnitude: mean |acc| / MAX_FORCE
            accel_raw = mean(sqrt(sum(acc.^2, 2))) / MAX_FORCE;
            avg_accel_ema = avg_accel_ema + (accel_raw - avg_accel_ema) * smooth;
        end

        if ~ENABLE_1a | MODE == 1 then
            vel = vel + acc;
            spd = sqrt(sum(vel.^2, 2));
            fast = find(spd > V0);
            if ~isempty(fast) then
                if DIMENSIONS == 3 then
                    vel(fast,:) = vel(fast,:) ./ (spd(fast) * ones(1,3)) * V0;
                else
                    vel(fast,:) = vel(fast,:) ./ (spd(fast) * ones(1,2)) * V0;
                end
            end
            slow = find(spd < V0 * 0.3);
            if ~isempty(slow) then
                for s = slow'
                    if spd(s) > 0.001 then
                        vel(s,:) = vel(s,:) / spd(s) * V0 * 0.3;
                    else
                        if DIMENSIONS == 3 then
                            na1 = rand()*2*%pi; na2 = (rand()-0.5)*%pi;
                            vel(s,:) = [cos(na1)*cos(na2), sin(na1)*cos(na2), sin(na2)] * V0 * 0.3;
                        else
                            na = rand()*2*%pi;
                            vel(s,:) = [cos(na), sin(na)] * V0 * 0.3;
                        end
                    end
                end
            end
        end

        pos = pos + vel;
        acc = acc * 0;

        // Toroidal wrap
        pos(:,1) = modulo(pos(:,1), WIDTH);
        pos(:,2) = modulo(pos(:,2), HEIGHT);
        if ENABLE_2c then
            pos(:,3) = modulo(pos(:,3), DEPTH);
        end

        // ═══════════════════════════════════════════════════════════════
        //  PHASE 7 — METRICS COMPUTATION
        //    Θ  — mean internal opacity (from projection or sampled)
        //    Θ′ — multi-viewpoint external opacity (Priority 1b)
        //    α  — order parameter: |Σv_i| / (N·v₀).  α ≈ 1 = aligned.
        //    τᵨ — density autocorrelation time (Priority 1c)
        //    All smoothed by EMA (smooth=0.05).
        // ═══════════════════════════════════════════════════════════════
        // ⇔ Python: extensions/multi_viewpoint_opacity.py + metrics.py
        // ⇔ Octave: alg2_extended.m SECTION 8-9 + main loop step 7

        // Θ — internal opacity
        if MODE == 0 then
            theta_raw = mean(last_theta);
        else
            sample_n = min(5, NUM_BOIDS);
            sample_idx = grand(1, "prm", (1:NUM_BOIDS)');
            sample_idx = sample_idx(1:sample_n);
            theta_sum = 0;
            for s = 1:sample_n
                [tmp_d, tmp_v, tmp_vd, tmp_nv, theta_sample] = ...
                    compute_projection_extended(sample_idx(s), pos, vel, chunk_cells);
                theta_sum = theta_sum + theta_sample;
            end
            theta_raw = theta_sum / sample_n;
        end
        theta_ema = theta_ema + (theta_raw - theta_ema) * smooth;

        // Θ′ — external opacity (Priority 1b: multi-viewpoint)
        theta_ext_raw = compute_external_opacity_multi(pos);
        theta_ext_ema = theta_ext_ema + (theta_ext_raw - theta_ext_ema) * smooth;

        // α — order parameter
        total_vel = sum(vel, 1);
        alpha_raw = norm(total_vel) / (NUM_BOIDS * V0);
        alpha_ema = alpha_ema + (alpha_raw - alpha_ema) * smooth;

        // Priority 1c: Correlation time τᵨ
        if ENABLE_1c then
            tau_timer = tau_timer + 1;
            if tau_timer >= CORR_SAMPLE_INTERVAL then
                tau_timer = 0;
                if NUM_BOIDS >= 3 then
                    area = convex_hull_area_2d(pos);
                    if area > 1 then
                        density = NUM_BOIDS / area;
                        last_density = density;
                        tau_buffer(tau_idx) = density;
                        tau_frames(tau_idx) = frame;
                        tau_idx = modulo(tau_idx, BUFFER_SIZE_TAU) + 1;
                        if tau_count < BUFFER_SIZE_TAU then tau_count = tau_count + 1; end
                        tau_val = compute_tau_from_buffer();
                    end
                end
            end
            tau_ema = tau_ema + (tau_val - tau_ema) * smooth;
        end



        // ═══════════════════════════════════════════════════════════════
        //  PHASE 8 — CSV LOGGING
        //    Append metrics row every LOG_EVERY frames.
        // ═══════════════════════════════════════════════════════════════
        if log_fid ~= -1 & modulo(frame, LOG_EVERY) == 0 then
            fps = 1 / max(toc(t_frame), 0.001);
            mfprintf(log_fid, "%d,%d,%d,%.4f,%.4f,%.4f,%.4f,%d,%.4f,%.4f,%.1f,%.4f,%.1f,%.4f,%.4f\n", ...
                     frame, MODE, NUM_BOIDS, PHI_P, PHI_A, PHI_N, PHI_S, SIGMA, ...
                     theta_ema, theta_ext_ema, tau_ema, alpha_ema, fps, power_ema, angmom_ema, avg_accel_ema);
        end

    end  // ~paused

    // ═══════════════════════════════════════════════════════════════════
    //  PHASE 9 — RENDER
    //    2D: xfpolys bird triangles (mode-dependent colour) + predator
    //    3D: one circle per bird with depth-dependent size and colour
    //    Metrics text overlay, mode badge, pause indicator, help overlay.
    // ═══════════════════════════════════════════════════════════════════
    // ⇔ Octave: alg2_extended.m main loop step 9
    // ⇔ Python: boid.py §render + scenario_presets.py

    if ~isempty(a.children) then delete(a.children); end
    a.data_bounds = [0, 0; WIDTH, HEIGHT];
    a.isoview      = "on";
    a.axes_visible = "off";

    drawlater();

    if ~ENABLE_2c | MODE == 1 then
        // ── 2D bird triangles ──────────────────────────────────────
        dirs = atan(vel(:,2), vel(:,1));

        tip_x = pos(:,1) + cos(dirs) * tip_len;
        tip_y = pos(:,2) + sin(dirs) * tip_len;
        lft_x = pos(:,1) + cos(dirs + side_ang) * side_len;
        lft_y = pos(:,2) + sin(dirs + side_ang) * side_len;
        rgt_x = pos(:,1) + cos(dirs - side_ang) * side_len;
        rgt_y = pos(:,2) + sin(dirs - side_ang) * side_len;

        X_verts = zeros(4 * NUM_BOIDS, 1);
        Y_verts = zeros(4 * NUM_BOIDS, 1);
        X_verts(1:4:$) = tip_x; X_verts(2:4:$) = lft_x; X_verts(3:4:$) = rgt_x; X_verts(4:4:$) = %nan;
        Y_verts(1:4:$) = tip_y; Y_verts(2:4:$) = lft_y; Y_verts(3:4:$) = rgt_y; Y_verts(4:4:$) = %nan;

        if MODE == 0 then
            bird_color = [200, 210, 230] / 255;
        else
            bird_color = [230, 200, 160] / 255;
        end
        xfpolys(X_verts, Y_verts, bird_color);

        // ── Predator ────────────────────────────────────────────────
        if ENABLE_3a & predator_active then
            if norm(predator_vel) > 0.001 then
                pdir = atan(predator_vel(2), predator_vel(1));
            else pdir = 0; end
            psize = 6;
            px_tip = predator_pos(1) + cos(pdir) * psize * 3;
            py_tip = predator_pos(2) + sin(pdir) * psize * 3;
            px_lft = predator_pos(1) + cos(pdir + 2.3) * psize * 2;
            py_lft = predator_pos(2) + sin(pdir + 2.3) * psize * 2;
            px_rgt = predator_pos(1) + cos(pdir - 2.3) * psize * 2;
            py_rgt = predator_pos(2) + sin(pdir - 2.3) * psize * 2;

            X_pred = [px_tip; px_lft; px_rgt; %nan];
            Y_pred = [py_tip; py_lft; py_rgt; %nan];
            xfpolys(X_pred, Y_pred, [255, 80, 60] / 255);
        end

    else
        // ── 3D perspective projection render ───────────────────────
        for i = 1:NUM_BOIDS
            depth_factor = max(0.2, pos(i,3) / DEPTH);  // 0 (far) to 1 (near)
            px = pos(i,1);
            py = pos(i,2);
            // Size: smaller when far away
            sz = max(1, 6 * depth_factor);
            rad = max(0.3, 1.0 * depth_factor);

            if norm(vel(i,:)) > 0.001 then
                dir_i = atan(vel(i,2), vel(i,1));
            else
                dir_i = 0;
            end
            // Draw circle instead of triangle for 3D
            n_circle = 6;
            cX = zeros(n_circle+1, 1);
            cY = zeros(n_circle+1, 1);
            for ci = 1:n_circle
                ca = 2*%pi*ci/n_circle;
                cX(ci) = px + cos(ca)*sz;
                cY(ci) = py + sin(ca)*sz*rad;
            end
            cX(n_circle+1) = %nan;
            cY(n_circle+1) = %nan;
            color_3d = min(1, [0.15+0.7*depth_factor, 0.17+0.7*depth_factor, 0.19+0.7*depth_factor]);
            xfpolys(cX, cY, color_3d);
        end
    end

    // ── Metrics text ───────────────────────────────────────────────
    fps = 1 / max(toc(t_frame), 0.001);
    xstring(10, 5, msprintf("FPS: %.0f    Boids: %d    Frame: %d", fps, NUM_BOIDS, frame));
    xstring(10, 25, msprintf("phi_p=%.3f  phi_a=%.3f  phi_n=%.3f  phi_s=%.3f  sigma=%d", PHI_P, PHI_A, PHI_N, PHI_S, SIGMA));

    if MODE == 0 then
        t3 = msprintf("Opacity  Theta  = %.3f", theta_ema);
    else
        t3 = msprintf("Opacity  Theta  ~ %.3f  (sampled)", theta_ema);
    end
    xstring(10, 45, t3);

    t4 = msprintf("          Theta'' = %.3f", theta_ext_ema);
    xstring(10, 65, t4);

    if ENABLE_1c then
        t5 = msprintf("Corr tau = %.1f fr   alpha = %.3f", tau_ema, alpha_ema);
    else
        t5 = msprintf("Order alpha = %.3f", alpha_ema);
    end
    xstring(10, 85, t5);

    t6 = msprintf("P=%.1f  L=%.0f  |a|=%.3f", power_ema, angmom_ema, avg_accel_ema);
    xstring(10, 105, t6);

    // Mode badge
    xstring(WIDTH - 250, 5, mode_names(MODE + 1));

    // Pause indicator
    if paused then xstring(WIDTH/2 - 100, HEIGHT - 30, "PAUSED"); end

    // Help overlay
    if show_help then _draw_help_overlay_ext(); end

    // Uniform text styling
    ch = a.children;
    for c = 1:length(ch)
        if ch(c).type == "Text" then
            ch(c).font_size  = 2;
            ch(c).font_color = [170, 200, 170] / 255;
        end
    end

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
