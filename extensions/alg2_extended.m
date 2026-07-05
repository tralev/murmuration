% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 1 — HEADER & OVERVIEW                                      ║
% ╚══════════════════════════════════════════════════════════════════════╝
%
%  alg2_extended.m — Extended Bird Flock Simulation (GNU Octave)
%  ──────────────────────────────────────────────────────────────
%  Based on:  Pearce, Miller, Rowlands & Turner (2014)
%             "Role of projection in the control of bird flocks"
%             PNAS 111(29), 10422–10426.
%             DOI: 10.1073/pnas.1402202111
%
%  This is the FULL extended version with all 9 roadmap priorities
%  ported from the Python extensions/ directory.  All features can
%  be individually toggled via the ENABLE_* flags in SECTION 2.
%
%  ── CROSS-LANGUAGE COMPARISON ─────────────────────────────────────
%  Same algorithm is available in three computing environments:
%
%    Python      extensions/alg2_extended.py, extensions/three_d.py, …
%    ⇔ Octave    extensions/alg2_extended.m  ← you are here
%    ⇔ Scilab    extensions/alg2_extended.sce
%
%  All three share identical variable names (ENABLE_*, PHI_*, SIGMA,
%  NUM_BOIDS, BOID_SIZE, STERIC_RADIUS, etc.) and feature-flag logic.
%  Look for "⇔" comments throughout to find the equivalent code block
%  in the other two languages.
%
%  Feature flags (set true or false at the top of SECTION 2):
%  ────────────────────────────────────────────────────────────────────
%    1a — Direct velocity setting (no Reynolds steering)
%    1b — Multi-viewpoint Θ′ (K=12 viewpoints)
%    1c — Correlation time τᵨ (Graham scan convex hull)
%    2a — Steric repulsion (1/r² force)
%    2b — Blind angles (60° rear blind cone)
%    2c — 3D extension (Fibonacci sphere spherical cap occlusion)
%    2d — Anisotropic bodies (elliptical projected size)
%    3a — Predator agent (peregrine falcon)
%    3b — Spatial optimization (grid-based chunker)
%
%  Two flocking modes (press 'm' to toggle):
%  ─────────────────────────────────────────────────────
%    MODE 0 — PROJECTION   Hybrid projection model (Pearce et al., Eq. 3)
%             v_i = φp·δ̂_i + φa·⟨v̂_j⟩_visible + φn·η̂_i
%
%    MODE 1 — SPATIAL      Topological Reynolds boids (Reynolds 1987)
%             Separation / Alignment / Cohesion with σ nearest neighbours
%             within VISUAL_RANGE.
%
%  Usage:  run this script in GNU Octave.
%          close the figure window to stop.
% =======================================================================


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 2 — CONFIGURATION CONSTANTS & FEATURE FLAGS                ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  Declare globals FIRST so all functions can share mutable state.
% ──────────────────────────────────────────────────────────────────────

global NUM_BOIDS BOID_SIZE WIDTH HEIGHT VISUAL_RANGE DEPTH
global MODE DIMENSIONS paused PHI_P PHI_A PHI_N PHI_S SIGMA
global pending_add pending_remove pending_reset show_help predator_active
global ENABLE_1a ENABLE_1b ENABLE_1c ENABLE_2a ENABLE_2b ENABLE_2c ENABLE_2d ENABLE_3a ENABLE_3b
global K_VIEWPOINTS R_EXT BLIND_ANGLE_VAL STERIC_RADIUS
global BOID_SEMI_MAJOR BOID_SEMI_MINOR BUFFER_SIZE_TAU CORR_SAMPLE_INTERVAL MAX_LAG_FRACTION
global GRID_COLS GRID_ROWS CELL_W CELL_H
global PREDATOR_SPEED PREDATOR_ACCEL DANGER_RADIUS FLIGHT_FORCE
global tau_buffer tau_frames tau_idx tau_count tau_timer tau_val

% ── Feature flags — set to true to enable, false to disable ──────────
ENABLE_1a = true;   % Direct velocity setting (Pearce Eq. 2-3, no Reynolds steering)
ENABLE_1b = true;   % Multi-viewpoint external opacity Θ′ (K viewpoints)
ENABLE_1c = true;   % Correlation time τᵨ (Graham scan convex hull)
ENABLE_2a = true;   % Steric repulsion (1/r² force, prevents overlap)
ENABLE_2b = true;   % Blind angles (β=60° rear blind sector)
ENABLE_2c = false;  % 3D extension (Fibonacci sphere spherical cap occlusion)
ENABLE_2d = true;   % Anisotropic bodies (elliptical projected size)
ENABLE_3a = true;   % Predator agent (peregrine falcon)
ENABLE_3b = true;   % Spatial optimization (grid-based chunker)

% ── Display ───────────────────────────────────────────────────────────
WIDTH        = 1000;                   % simulation area width  (pixels)
HEIGHT       = 700;                    % simulation area height (pixels)
DEPTH        = 1000;                   % 3D depth (only used when ENABLE_2c = true)

% ── Flock parameters ──────────────────────────────────────────────────
NUM_BOIDS    = 100;                    % number of birds (reduce if slow)
BOID_SIZE    = 3;                      % bird radius b  (paper: b = 1)
V0           = 4;                      % constant cruising speed v₀
MAX_FORCE    = 0.15;                   % max steering force (spatial mode)
VISUAL_RANGE = 70;                     % neighbour search radius (spatial mode)

% ── Default model weights  (φp + φa + φn + φs = 1) ───────────────────
PHI_P  = 0.03;                         % projection weight
PHI_A  = 0.80;                         % alignment weight
PHI_N  = 0.14;                         % noise weight — auto-computed each frame
PHI_S  = 0.03;                         % steric repulsion weight (Priority 2a)
SIGMA  = 4;                            % number of nearest visible neighbours

% ── Mode identifier ───────────────────────────────────────────────────
MODE   = 0;                            % 0 = PROJECTION, 1 = SPATIAL

% ── Priority 1b: Multi-viewpoint Θ′ ──────────────────────────────────
K_VIEWPOINTS = 12;                     % number of observer viewpoints
R_EXT        = 2000;                   % radius of the observer circle

% ── Priority 2a: Steric repulsion ────────────────────────────────────
STERIC_RADIUS = 2 * BOID_SIZE;        % r_s — birds within this repel

% ── Priority 2b: Blind angles ────────────────────────────────────────
BLIND_ANGLE_VAL = pi / 3;             % β — blind sector width (60°)

% ── Priority 2d: Anisotropic bodies ─────────────────────────────────
BOID_SEMI_MAJOR = BOID_SIZE * 1.4;    % a — length along flight direction
BOID_SEMI_MINOR = BOID_SIZE * 0.7;    % b — width across flight direction

% ── Priority 1c: Correlation time τᵨ ────────────────────────────────
BUFFER_SIZE_TAU      = 500;           % max density snapshots
CORR_SAMPLE_INTERVAL = 10;            % sample every N frames
MAX_LAG_FRACTION     = 0.25;          % integrate up to 25% of buffer

% ── Priority 3b: Spatial optimization ────────────────────────────────
GRID_COLS = 10;
GRID_ROWS = 7;
CELL_W    = WIDTH / GRID_COLS;
CELL_H    = HEIGHT / GRID_ROWS;

% ── Priority 3a: Predator ────────────────────────────────────────────
PREDATOR_SPEED  = V0 * 2.0;           % predator is ~2× faster
PREDATOR_ACCEL  = 0.3;                % hunting acceleration
DANGER_RADIUS   = 120;                % birds within this flee
FLIGHT_FORCE    = 1.5;                % strength of flight response

% ── Dimensionality ────────────────────────────────────────────────────
DIMENSIONS = 2;                        % 2 or 3 (set by ENABLE_2c)

% ── Trail rendering  (position-history polyline behind each boid) ──
DRAW_TRAIL   = false;                   % draw position history trail behind each boid
TRAIL_LENGTH = 50;                      % max trail positions to keep

% ── CSV logging ───────────────────────────────────────────────────────
LOG_FILE  = 'murmuration_metrics_extended.csv';
LOG_EVERY = 10;


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 2b — CSV LOGGING SETUP                                    ║
% ╚══════════════════════════════════════════════════════════════════════╝

log_fid = fopen(LOG_FILE, 'w');
if log_fid == -1
    disp(['WARNING: could not open ' LOG_FILE ' for writing']);
else        fprintf(log_fid, 'frame,mode,num_boids,phi_p,phi_a,phi_n,phi_s,sigma,theta,theta_ext,tau,alpha,fps,power,angmom,avg_accel,disp\n');
    disp(['Logging metrics to ' LOG_FILE ' every ' num2str(LOG_EVERY) ' frames']);
end


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 3 — RUNTIME STATE INITIALIZATION                           ║
% ╚══════════════════════════════════════════════════════════════════════╝

% ── Mutable runtime flags ────────────────────────────────────────────
paused         = false;
pending_add    = 0;
pending_remove = 0;
pending_reset  = false;
show_help      = false;
predator_active = false;               % 'f' toggles predator on/off

if ENABLE_2c
    disp(['Initializing 3D flock with ' num2str(NUM_BOIDS) ' birds ...']);
    DIMENSIONS = 3;
else
    disp(['Initializing 2D flock with ' num2str(NUM_BOIDS) ' birds ...']);
    DIMENSIONS = 2;
end

% ── State arrays (N × D) ──────────────────────────────────────────
if ENABLE_2c
    pos  = rand(NUM_BOIDS, 3) .* [WIDTH, HEIGHT, DEPTH];
    ang  = rand(NUM_BOIDS, 1) * 2 * pi;
    phi  = (rand(NUM_BOIDS, 1) - 0.5) * pi;        % elevation
    vel  = [cos(ang).*cos(phi), sin(ang).*cos(phi), sin(phi)] .* V0;
    acc  = zeros(NUM_BOIDS, 3);
else
    pos  = rand(NUM_BOIDS, 2) .* [WIDTH, HEIGHT];
    ang  = rand(NUM_BOIDS, 1) * 2 * pi;
    vel  = [cos(ang), sin(ang)] .* (1 + rand(NUM_BOIDS, 1) * (V0 - 1));
    acc  = zeros(NUM_BOIDS, 2);
end
last_theta  = zeros(NUM_BOIDS, 1);
last_density = 0;                      % latest flock density ρ

% ── Priority 1c: Correlation time ring buffer ──────────────────────
tau_buffer  = zeros(BUFFER_SIZE_TAU, 1);
tau_frames  = zeros(BUFFER_SIZE_TAU, 1);
tau_idx     = 1;
tau_count   = 0;
tau_timer   = 0;
tau_val     = 0;                       % latest τᵨ estimate

% ── Priority 3a: Predator state ────────────────────────────────────
predator_pos = [WIDTH/2, HEIGHT/2];
predator_vel = [0, 0];
predator_trail = [];                    % for drawing trail

% ── Boid trail ring buffer ──────────────────────────────────────
if DRAW_TRAIL
    trail       = zeros(TRAIL_LENGTH, NUM_BOIDS, 2);
    trail_idx   = 1;
    trail_count = 0;
end

% ── Priority 3b: Chunk cache — cell array of structs ───────────────
%  Each struct:  .key=[cx,cy], .birds=[indices], .cx, .cy, .r
chunk_cells = {};                       % rebuilt each frame


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 2c — HELP TEXT BUILDER  (defined EARLY for use in setup)   ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  Must be defined BEFORE Section 2d (figure setup) since build_help_lines
%  is called during graphics initialisation.
% ──────────────────────────────────────────────────────────────────────

function lines = build_help_lines()
    global ENABLE_1a ENABLE_2a ENABLE_2b ENABLE_2c ENABLE_2d ENABLE_3a ENABLE_3b

    % Inline checkmark — no nested functions in Octave script files
    if ENABLE_1a, s1a = '✓'; else, s1a = '✗'; end
    if ENABLE_2a, s2a = '✓'; else, s2a = '✗'; end
    if ENABLE_2b, s2b = '✓'; else, s2b = '✗'; end
    if ENABLE_2c, s2c = '✓'; else, s2c = '✗'; end
    if ENABLE_2d, s2d = '✓'; else, s2d = '✗'; end
    if ENABLE_3a, s3a = '✓'; else, s3a = '✗'; end
    if ENABLE_3b, s3b = '✓'; else, s3b = '✗'; end

    lines = {
        'CONTROLS                                       EXTENSIONS';
        '────────────────────────────────────────  ────────────────────';
        ['m      toggle  PROJECTION / SPATIAL    1a ' s1a ' direct velocity'];
        ['p      pause / resume                  2a ' s2a ' steric'];
        ['f      toggle predator                 2b ' s2b ' blind'];
        ['r      reset flock                     2c ' s2c ' 3D'];
        ['h      hide this help                  2d ' s2d ' aniso'];
        ['↑/↓    φp  ±0.01                       3a ' s3a ' predator'];
        ['←/→    φa  ±0.01                       3b ' s3b ' chunker'];
        ['[ / ]  σ   ±1                          φp=proj φa=align φn=noise'];
        ['+ / -  add / remove 10 birds            φs=steric  σ=neighbours'];
        'ESC    close window to quit';
    };
end


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 2d — FIGURE & GRAPHICS SETUP                              ║
% ╚══════════════════════════════════════════════════════════════════════╝

f = figure('Name', ...
    'Murmuration Extended  [m:mode p:pause f:falcon h:help]', ...
    'NumberTitle', 'off', ...
    'Position', [100, 100, WIDTH, HEIGHT], ...
    'Color', [0.08 0.09 0.12]);

set(f, 'KeyPressFcn', @key_handler_extended);

axis equal;
axis([0 WIDTH 0 HEIGHT]);
axis off;
hold on;

% ── Bird patch — pre-allocated 3×N vertices (2D mode) ─────────────
%  Tagged 'keep' so the 3D render cleanup doesn't destroy these handles.
hBoids = patch(zeros(3, NUM_BOIDS), zeros(3, NUM_BOIDS), ...
               [200 210 230]/255, 'EdgeColor', 'none', 'Tag', 'keep');

% ── Predator patch — single triangle ───────────────────────────────
%  Also tagged 'keep' for the same reason.
hPredator = patch(zeros(3, 1), zeros(3, 1), [255 80 60]/255, ...
                  'EdgeColor', 'none', 'Visible', 'off', 'Tag', 'keep');

% ── Metrics text handles ───────────────────────────────────────────
hTextFPS    = text(10, 5,   '', 'Color', [170 200 170]/255, 'FontSize', 12);
hTextParams = text(10, 25,  '', 'Color', [170 200 170]/255, 'FontSize', 12);
hTextTheta  = text(10, 45,  '', 'Color', [170 200 170]/255, 'FontSize', 12);
hTextExt    = text(10, 65,  '', 'Color', [170 200 170]/255, 'FontSize', 12);
hTextTau    = text(10, 85,  '', 'Color', [170 200 170]/255, 'FontSize', 12);
hTextPower  = text(10, 105, '', 'Color', [170 200 170]/255, 'FontSize', 12);
hTextBadge  = text(WIDTH-300, 5, '', 'Color', [170 200 170]/255, 'FontSize', 12);

% ── Pause indicator ─────────────────────────────────────────────────
hTextPause  = text(WIDTH/2-100, HEIGHT-30, '', ...
                   'Color', [255 200 100]/255, 'FontSize', 14, ...
                   'Visible', 'off');

% ── Help overlay ────────────────────────────────────────────────────
help_lines = build_help_lines();
n_help_lines = length(help_lines);
hHelp = text(WIDTH-460, HEIGHT-10, '', ...
             'BackgroundColor', [0 0 0], ...
             'Color', [0.8 0.8 0.6], ...
             'EdgeColor', [0.3 0.3 0.3], ...
             'VerticalAlignment', 'top', ...
             'FontSize', 10, ...
             'Visible', 'off');


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 4 — ANGULAR-INTERVAL UTILITIES                            ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  ⇔ Scilab: alg2_extended.sce SECTION 4 (identical algorithm)
%  ⇔ Python: flock_core.py — occlusion_geom.py
%  ──────────────────────────────────────────────────────────────────────

function [merged, n_merged] = merge_angle_intervals(intervals, n_int)
    % Merge overlapping angular intervals on [0, 2π).  O(n_int).
    % Input:  sorted intervals (n_int × 2: [start, end])
    % Output: merged intervals (n_merged × 2), with overlaps collapsed.
    %
    % Complexity: O(n_int) — single linear pass over sorted input.

    merged   = zeros(n_int, 2);
    n_merged = 0;
    j = 1;
    while j <= n_int
        cur_s = intervals(j, 1);
        cur_e = intervals(j, 2);
        k = j + 1;
        % Extend cur_e while next interval starts within current end
        while k <= n_int && intervals(k, 1) <= cur_e + 1e-9
            if intervals(k, 2) > cur_e
                cur_e = intervals(k, 2);
            end
            k = k + 1;
        end
        n_merged = n_merged + 1;
        merged(n_merged, :) = [cur_s, cur_e];
        j = k;
    end
    merged = merged(1:n_merged, :);
end


function segments = normalise_interval_2d(start_val, end_val)
    % Normalise an angular interval [start, end] into [0, 2π) segments.
    % Returns up to 2 segments if the interval wraps around 0 or 2π.

    segments = zeros(2, 2);
    n_segs = 0;
    if start_val < 0
        n_segs = n_segs + 1; segments(n_segs,:) = [start_val + 2*pi, 2*pi];
        n_segs = n_segs + 1; segments(n_segs,:) = [0, end_val];
    elseif end_val > 2*pi
        n_segs = n_segs + 1; segments(n_segs,:) = [start_val, 2*pi];
        n_segs = n_segs + 1; segments(n_segs,:) = [0, end_val - 2*pi];
    else
        n_segs = 1; segments(1,:) = [start_val, end_val];
    end
    segments = segments(1:n_segs, :);
end


function is_covered = interval_covered_2d(start_val, end_val, merged, n_merged)
    % Check if [start_val, end_val] is fully covered by merged intervals.
    % Used in the visibility test of the incremental occlusion merge.
    %
    % Algorithm:
    %   1. Start a cursor at start_val.
    %   2. For each merged interval: if cursor is inside it, advance cursor
    %      to the end of that interval.
    %   3. If cursor reaches end_val, the segment is fully covered → return true.
    %   4. If cursor stalls before end_val, the segment is NOT covered → return false.

    cursor = start_val;
    for m = 1:n_merged
        if merged(m,1) <= cursor + 1e-9 && cursor < merged(m,2)
            cursor = max(cursor, merged(m,2));
        end
        if cursor >= end_val - 1e-9
            is_covered = true;
            return;
        end
    end
    is_covered = false;
end


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 5 — GRAHAM SCAN CONVEX HULL  (Priority 1c: τᵨ)            ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  ⇔ Scilab: alg2_extended.sce SECTION 5 (convex_hull_area_2d)
%  ⇔ Python: extensions/correlation_time.py
%  Reference:  Graham, R.L. (1972) "An efficient algorithm for
%              determining the convex hull of a finite planar set."
%              Information Processing Letters 1(4), 132–133.
%
%  Used to compute flock area from bird positions, which feeds into
%  density ρ = N / area for the autocorrelation-based τᵨ estimator.
%
%  Algorithm (detailed trace):
%    Step 1 — Find pivot: bird with lowest y (break ties by leftmost x).
%    Step 2 — Sort all other birds by polar angle from pivot.
%             Ties broken by distance (closer first).
%    Step 3 — Build hull: iterate sorted points, pop from hull while
%             the cross product of the last two hull points with the
%             new point is ≤ 0 (right turn or collinear).
%    Step 4 — Shoelace formula: area = ½|Σ(xᵢyᵢ₊₁ − xᵢ₊₁yᵢ)|
% ──────────────────────────────────────────────────────────────────────

function area = convex_hull_area_2d(pts)
    % Compute area of convex hull of N×2 points using Graham scan.
    % Returns 0 if fewer than 3 points.

    n = size(pts, 1);
    if n < 3
        area = 0;
        return;
    end

    % ── Step 1: find pivot (lowest y, then leftmost x) ──────────────
    pivot_idx = 1;
    for i = 2:n
        if pts(i,2) < pts(pivot_idx,2) || ...
           (pts(i,2) == pts(pivot_idx,2) && pts(i,1) < pts(pivot_idx,1))
            pivot_idx = i;
        end
    end
    % Swap pivot to position 1
    tmp = pts(1,:); pts(1,:) = pts(pivot_idx,:); pts(pivot_idx,:) = tmp;

    % ── Step 2: compute polar angles and sort ──────────────────────
    n_rest = n - 1;
    polar_data = zeros(n_rest, 3);  % [angle, dist_sq, original_index]
    for i = 1:n_rest
        dx = pts(i+1,1) - pts(1,1);
        dy = pts(i+1,2) - pts(1,2);
        polar_data(i,1) = atan2(dy, dx);
        if polar_data(i,1) < 0
            polar_data(i,1) = polar_data(i,1) + 2*pi;
        end
        polar_data(i,2) = dx*dx + dy*dy;
        polar_data(i,3) = i + 1;
    end
    % Sort by angle (ascending), then distance (ascending)
    [~, sort_idx] = sortrows(polar_data, [1, 2]);
    polar_data = polar_data(sort_idx, :);

    % ── Step 3: build hull ─────────────────────────────────────────
    hull = [pts(1,:); pts(polar_data(1,3), :)];
    m = 2;
    for i = 2:n_rest
        p_next = pts(polar_data(i,3), :);
        % Pop while the last turn is not a left turn
        while m >= 2
            o = hull(m-1,:);
            a = hull(m,:);
            cross_val = (a(1)-o(1))*(p_next(2)-o(2)) - (a(2)-o(2))*(p_next(1)-o(1));
            if cross_val <= 0
                m = m - 1;
            else
                break;
            end
        end
        m = m + 1;
        hull(m,:) = p_next;
    end
    hull = hull(1:m, :);

    % ── Step 4: shoelace formula for area ──────────────────────────
    area = 0;
    for i = 1:m
        j = mod(i, m) + 1;
        area = area + hull(i,1)*hull(j,2) - hull(j,1)*hull(i,2);
    end
    area = abs(area) / 2;
end


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 6 — SPATIAL CHUNKER  (Priority 3b)                        ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  ⇔ Scilab: alg2_extended.sce SECTION 6 (rebuild_chunker)
%  ⇔ Python: extensions/spatial_optimization.py
%  Two-pass grid-based spatial partitioning.
%
%  Pass 1 — Bin birds: assign each bird to a cell (cx, cy) in the
%           GRID_COLS × GRID_ROWS grid.
%  Pass 2 — Compute centroids: for each occupied cell, compute the
%           centroid of its birds and the maximum distance from the
%           centroid (bounding radius r).
%
%  The chunker is used in the extended projection function to:
%    - Near phase: process birds in the 3×3 surrounding cells
%    - Far phase: treat distant cells as passive occluders (sentinel idx=0)
%
%  Complexity: O(N + C) where N = NUM_BOIDS, C = number of occupied cells.
% ──────────────────────────────────────────────────────────────────────

function chunks = rebuild_chunker_octave(pos)
    % Rebuild chunk grid from flock positions.  Returns cell array of
    % structs, each with: .key(2), .birds, .cx, .cy, .r
    global GRID_COLS GRID_ROWS CELL_W CELL_H BOID_SEMI_MAJOR NUM_BOIDS

    % ── Pass 1: bin birds ──────────────────────────────────────────
    bins = {};   % cell array of structs
    n_bins = 0;
    for i = 1:NUM_BOIDS
        cx = mod(floor(pos(i,1) / CELL_W), GRID_COLS);
        cy = mod(floor(pos(i,2) / CELL_H), GRID_ROWS);

        % Find or create bin
        found = false;
        for b = 1:n_bins
            if bins{b}.key(1) == cx && bins{b}.key(2) == cy
                bins{b}.birds(end+1) = i;
                found = true;
                break;
            end
        end
        if ~found
            n_bins = n_bins + 1;
            bins{n_bins} = struct('key', [cx, cy], 'birds', [i], ...
                                  'cx', 0, 'cy', 0, 'r', 0);
        end
    end

    % ── Pass 2: compute centroids and bounding radii ───────────────
    for c = 1:n_bins
        indices = bins{c}.birds;
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
            if dsq > max_dist_sq, max_dist_sq = dsq; end
        end
        radius = sqrt(max_dist_sq) + BOID_SEMI_MAJOR;

        bins{c}.cx = centroid_x;
        bins{c}.cy = centroid_y;
        bins{c}.r  = radius;
    end

    chunks = bins;  % return cell array
end


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 7 — PROJECTION MODEL WITH ALL 2D EXTENSIONS               ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  ⇔ Scilab: alg2_extended.sce SECTION 7 (compute_projection_extended)
%  ⇔ Python: extensions/direct_velocity.py + flock_core.py
%  Priorities integrated: 1a, 2a, 2b, 2d, 3b
%
%  This is the core occlusion algorithm, shared with the original
%  compute_projection() but extended with:
%    - Spatial chunker (3b): near/far phases for O(N) occlusion entries
%    - Blind angles (2b): rear blind cone filter before occlusion merge
%    - Anisotropic bodies (2d): elliptical projected radius based on
%      flight direction (birds appear wider from the side, narrower
%      from head-on).
%
%  The visibility algorithm remains the same: incremental angular interval
%  merging with closest-first processing.  A neighbour is visible iff any
%  segment of its subtended angular interval is NOT already covered by
%  closer birds.
% ──────────────────────────────────────────────────────────────────────

function [delta, vis_idx, vis_dists, n_vis, theta] = ...
         compute_projection_extended(i, pos, vel, chunks)
    global NUM_BOIDS BOID_SIZE WIDTH HEIGHT ENABLE_2b ENABLE_2d
    global BLIND_ANGLE_VAL BOID_SEMI_MAJOR BOID_SEMI_MINOR
    global ENABLE_3b GRID_COLS GRID_ROWS CELL_W CELL_H

    % ═══════════════════════════════════════════════════════════════
    %  PHASE 1: Build angular entries for all other birds
    % ═══════════════════════════════════════════════════════════════

    if ENABLE_3b && ~isempty(chunks)
        % ── Use spatial chunker for near + far entries ──────────

        n_bins = length(chunks);
        n_entries = 0;
        entries = zeros(NUM_BOIDS * 2 + n_bins, 4);  % [dist, centre, half, bird_idx]

        % Viewer's cell
        vx = mod(floor(pos(i,1) / CELL_W), GRID_COLS);
        vy = mod(floor(pos(i,2) / CELL_H), GRID_ROWS);

        % Phase 1a: near birds (3×3 surrounding cells)
        for dx = -1:1
            for dy = -1:1
                cx = mod(vx + dx, GRID_COLS);
                cy = mod(vy + dy, GRID_ROWS);
                for c = 1:n_bins
                    if chunks{c}.key(1) == cx && chunks{c}.key(2) == cy
                        indices = chunks{c}.birds;
                        for k = 1:length(indices)
                            j = indices(k);
                            if j == i, continue; end

                            % Toroidal distance
                            dx_b = pos(j,1) - pos(i,1);
                            dy_b = pos(j,2) - pos(i,2);
                            if abs(dx_b) > WIDTH/2, dx_b = dx_b - sign(dx_b)*WIDTH; end
                            if abs(dy_b) > HEIGHT/2, dy_b = dy_b - sign(dy_b)*HEIGHT; end
                            dist = sqrt(dx_b*dx_b + dy_b*dy_b);
                            if dist < 0.001, continue; end

                            centre = atan2(dy_b, dx_b);
                            if centre < 0, centre = centre + 2*pi; end

                            % Anisotropic half-width (Priority 2d)
                            if ENABLE_2d
                                if norm(vel(j,:)) > 0.001
                                    psi = atan2(vel(j,2), vel(j,1));
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
                        break;  % each cell appears at most once
                    end
                end
            end
        end

        % Phase 1b: far chunks (passive occluders, sentinel idx=0)
        for c = 1:n_bins
            cx_c = chunks{c}.key(1);
            cy_c = chunks{c}.key(2);
            dx_wrap = min(abs(cx_c - vx), GRID_COLS - abs(cx_c - vx));
            dy_wrap = min(abs(cy_c - vy), GRID_ROWS - abs(cy_c - vy));
            if dx_wrap <= 1 && dy_wrap <= 1, continue; end  % near

            % Toroidal distance to chunk centroid
            dx_c = chunks{c}.cx - pos(i,1);
            dy_c = chunks{c}.cy - pos(i,2);
            if abs(dx_c) > WIDTH/2, dx_c = dx_c - sign(dx_c)*WIDTH; end
            if abs(dy_c) > HEIGHT/2, dy_c = dy_c - sign(dy_c)*HEIGHT; end
            dist = sqrt(dx_c*dx_c + dy_c*dy_c);
            if dist < 0.001, continue; end

            centre = atan2(dy_c, dx_c);
            if centre < 0, centre = centre + 2*pi; end
            half = asin(min(chunks{c}.r / dist, 1));

            n_entries = n_entries + 1;
            entries(n_entries,:) = [dist, centre, half, 0];  % 0 = passive occluder
        end

        entries = entries(1:n_entries, :);
        if n_entries == 0
            delta = [0, 0]; vis_idx = []; vis_dists = []; n_vis = 0; theta = 0;
            return;
        end

        % Sort closest-first
        [~, sort_idx] = sort(entries(:,1));
        entries = entries(sort_idx, :);

    else
        % ── O(N²) — all birds (fallback when chunker disabled) ────
        n_entries = 0;
        entries = zeros(NUM_BOIDS - 1, 4);
        for j = 1:NUM_BOIDS
            if j == i, continue; end
            dx_b = pos(j,1) - pos(i,1);
            dy_b = pos(j,2) - pos(i,2);
            if abs(dx_b) > WIDTH/2, dx_b = dx_b - sign(dx_b)*WIDTH; end
            if abs(dy_b) > HEIGHT/2, dy_b = dy_b - sign(dy_b)*HEIGHT; end
            dist = sqrt(dx_b*dx_b + dy_b*dy_b);
            if dist < 0.001, continue; end

            centre = atan2(dy_b, dx_b);
            if centre < 0, centre = centre + 2*pi; end

            if ENABLE_2d
                if norm(vel(j,:)) > 0.001
                    psi = atan2(vel(j,2), vel(j,1));
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
        if n_entries == 0
            delta = [0, 0]; vis_idx = []; vis_dists = []; n_vis = 0; theta = 0;
            return;
        end
        [~, sort_idx] = sort(entries(:,1));
        entries = entries(sort_idx, :);
    end

    % ═══════════════════════════════════════════════════════════════
    %  PHASE 2: Blind angles filter (Priority 2b)
    % ═══════════════════════════════════════════════════════════════
    %  Remove entries whose entire angular interval falls within the
    %  rear blind sector of width β = BLIND_ANGLE_VAL behind the bird.
    %
    %  The blind sector is centred on heading + π (straight behind).
    %  An entry is blocked if ALL its normalised segments lie within
    %  the blind sector.

    if ENABLE_2b
        if norm(vel(i,:)) > 0.001
            heading = atan2(vel(i,2), vel(i,1));
        else heading = 0; end
        if heading < 0, heading = heading + 2*pi; end

        blind_centre = heading + pi;
        if blind_centre >= 2*pi, blind_centre = blind_centre - 2*pi; end
        blind_start = blind_centre - BLIND_ANGLE_VAL/2;
        blind_end   = blind_centre + BLIND_ANGLE_VAL/2;
        if blind_start < 0, blind_start = blind_start + 2*pi; end
        if blind_end > 2*pi, blind_end = blind_end - 2*pi; end

        n_filtered = 0;
        filtered = zeros(n_entries, 4);
        for k = 1:n_entries
            start_k = entries(k,2) - entries(k,3);
            end_k   = entries(k,2) + entries(k,3);
            segs = normalise_interval_2d(start_k, end_k);
            n_segs = size(segs, 1);
            all_blind = true;
            for s = 1:n_segs
                s1 = segs(s,1); e1 = segs(s,2);
                in_blind = false;
                if blind_start <= blind_end
                    if blind_start <= s1 + 1e-9 && e1 <= blind_end + 1e-9
                        in_blind = true;
                    end
                else
                    if (blind_start <= s1 + 1e-9 && e1 <= 2*pi + 1e-9) || ...
                       (s1 >= -1e-9 && e1 <= blind_end + 1e-9)
                        in_blind = true;
                    end
                end
                if ~in_blind
                    all_blind = false;
                    break;
                end
            end
            if ~all_blind
                n_filtered = n_filtered + 1;
                filtered(n_filtered,:) = entries(k,:);
            end
        end
        entries = filtered(1:n_filtered, :);
        n_entries = n_filtered;
    end

    if n_entries == 0
        delta = [0, 0]; vis_idx = []; vis_dists = []; n_vis = 0; theta = 0;
        return;
    end

    % ═══════════════════════════════════════════════════════════════
    %  PHASE 3: Incremental occlusion merge
    % ═══════════════════════════════════════════════════════════════
    %  Process entries closest-first.  For each entry:
    %    - Build [start, end] segments (handling wrap at 2π)
    %    - Check if any segment is NOT covered by merged intervals
    %    - If visible: record (unless sentinel idx=0), merge segments

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

        is_visible = false;
        for s = 1:n_segs
            if ~interval_covered_2d(segs(s,1), segs(s,2), merged, n_merged)
                is_visible = true;
                break;
            end
        end

        if is_visible
            % Passive occluders (bird_j == 0) merge but don't count as visible
            if bird_j > 0
                n_vis = n_vis + 1;
                vis_idx(n_vis)   = bird_j;
                vis_dists(n_vis) = d_j;
            end

            % Add segments to merged and re-sort+merge
            for s = 1:n_segs
                n_merged = n_merged + 1;
                merged(n_merged,:) = segs(s,:);
            end
            if n_merged > 1
                [~, midx] = sort(merged(1:n_merged,1));
                merged(1:n_merged,:) = merged(midx,:);
                [merged, n_merged] = merge_angle_intervals(merged(1:n_merged,:), n_merged);
            end
        end
    end

    vis_idx   = vis_idx(1:n_vis);
    vis_dists = vis_dists(1:n_vis);
    merged    = merged(1:n_merged, :);

    % ═══════════════════════════════════════════════════════════════
    %  PHASE 4: δ̂ from domain boundaries
    % ═══════════════════════════════════════════════════════════════
    %  Sum unit vectors to each occluded interval boundary.
    %  Fully surrounded (one interval covering all 2π) → δ̂ = 0.

    delta = [0, 0];
    if n_merged == 1 && merged(1,1) < 1e-9 && merged(1,2) > 2*pi - 1e-9
        delta = [0, 0];  % fully surrounded
    else
        for m = 1:n_merged
            delta = delta + [cos(merged(m,1)), sin(merged(m,1))];
            delta = delta + [cos(merged(m,2)), sin(merged(m,2))];
        end
        dnorm = norm(delta);
        if dnorm > 1e-9
            delta = delta / dnorm;
        end
    end

    % ═══════════════════════════════════════════════════════════════
    %  PHASE 5: Internal opacity Θ_i
    % ═══════════════════════════════════════════════════════════════
    %  Θ = (total occluded angular width) / 2π

    if n_merged > 0
        occluded = sum(merged(:,2) - merged(:,1));
        theta = min(occluded / (2 * pi), 1.0);
    else
        theta = 0;
    end
end


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 7b — 3D PROJECTION MODEL  (Priority 2c)                    ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  ⇔ Scilab: alg2_extended.sce SECTION 7b (compute_projection_3d)
%  ⇔ Python: extensions/three_d.py
%  Fibonacci sphere z-buffered spherical cap occlusion.
%
%  In 2D, each bird subtends a 1D angular interval on a circle.
%  In 3D, each bird subtends a 2D circular cap on the unit sphere.
%
%  Algorithm:
%    1. Generate N=80 uniform points on the unit sphere (Fibonacci spiral).
%    2. Per bird, maintain a z-buffer: zbuf[i] = distance to closest
%       occluder at Fibonacci point i.  -1.0 = unoccluded.
%    3. Sort all birds by distance (closest first).
%    4. For each bird: check if ANY Fibonacci point in its cap is unoccluded.
%       If yes → visible.  Mark ALL cap points as occluded at distance d.
%    5. δ̂ = average of unoccluded Fibonacci point vectors.
%    6. Θ = (# occluded points) / N.
%
%  Complexity: O(N² · F) per bird; F=80 for good sphere coverage.
% ──────────────────────────────────────────────────────────────────────

function fib_pts = fibonacci_sphere_3d(n)
    % Generate n uniformly distributed points on the unit sphere
    % using the Fibonacci (golden-angle) spiral.
    %
    % Golden angle:  π(3 − √5) ≈ 2.400 rad
    %
    % Algorithm:
    %   1. Distribute y-coordinates linearly from +1 (top) to −1 (bottom).
    %   2. At each y, compute latitude circle radius: r = √(1 − y²).
    %   3. Advance azimuthal angle θ by golden angle φ each step.
    %   4. Convert spherical (θ, y) → Cartesian (x, y, z).

    gold_phi = pi * (3 - sqrt(5));
    fib_pts = zeros(n, 3);
    n1 = max(n, 2);  % guard against n≤1
    for k = 1:n1
        y = 1 - (2*(k-1) + 1) / n1;     % linearly from +1 to −1
        radius = sqrt(1 - y*y);           % latitude circle radius
        theta = gold_phi * (k - 1);       % golden-angle azimuth
        fib_pts(k,1) = cos(theta) * radius;
        fib_pts(k,2) = y;
        fib_pts(k,3) = sin(theta) * radius;
    end
end


function [delta, vis_idx, vis_dists, n_vis, theta] = ...
         compute_projection_3d(i, pos, vel)
    global NUM_BOIDS BOID_SIZE WIDTH HEIGHT DEPTH ENABLE_2b BLIND_ANGLE_VAL

    n_fib = 80;  % Fibonacci sphere resolution
    N = NUM_BOIDS;

    % ═══════════════════════════════════════════════════════════════
    %  PHASE 1: Build angular entries for all other birds
    % ═══════════════════════════════════════════════════════════════
    %  Each entry: [bird_idx, dist, dir_x, dir_y, dir_z, ang_radius]

    n_entries = 0;
    entries = zeros(N - 1, 6);
    for j = 1:N
        if j == i, continue; end

        % Toroidal distance in 3D
        dx = pos(j,1) - pos(i,1);
        dy = pos(j,2) - pos(i,2);
        dz = pos(j,3) - pos(i,3);
        if abs(dx) > WIDTH/2, dx = dx - sign(dx)*WIDTH; end
        if abs(dy) > HEIGHT/2, dy = dy - sign(dy)*HEIGHT; end
        if abs(dz) > DEPTH/2, dz = dz - sign(dz)*DEPTH; end

        dist = sqrt(dx*dx + dy*dy + dz*dz);
        if dist < 0.001, continue; end

        n_entries = n_entries + 1;
        entries(n_entries, 1) = j;
        entries(n_entries, 2) = dist;
        entries(n_entries, 3) = dx / dist;   % dir_x
        entries(n_entries, 4) = dy / dist;   % dir_y
        entries(n_entries, 5) = dz / dist;   % dir_z
        entries(n_entries, 6) = asin(min(BOID_SIZE / dist, 1));
    end

    if n_entries == 0
        delta = [0, 0, 0]; vis_idx = []; vis_dists = []; n_vis = 0; theta = 0;
        return;
    end
    entries = entries(1:n_entries, :);

    % ═══════════════════════════════════════════════════════════════
    %  PHASE 2: Sort closest-first
    % ═══════════════════════════════════════════════════════════════
    [~, sort_idx] = sort(entries(:,2));
    entries_sorted = entries(sort_idx, :);

    % ═══════════════════════════════════════════════════════════════
    %  PHASE 3: Blind cone filter (Priority 2b in 3D)
    % ═══════════════════════════════════════════════════════════════
    %  A bird in the blind cone has its direction within β/2 of
    %  -heading.  If the entire cap is in the blind cone, skip it.

    if ENABLE_2b
        vn = norm(vel(i,:));
        if vn > 0.001
            hx = vel(i,1)/vn; hy = vel(i,2)/vn; hz = vel(i,3)/vn;
        else
            hx = 1; hy = 0; hz = 0;
        end
        cos_blind = cos(BLIND_ANGLE_VAL / 2);

        n_filtered = 0;
        filtered = zeros(n_entries, 6);
        for k = 1:n_entries
            % Dot product of -heading with direction to bird
            dot_vb = -(hx*entries_sorted(k,3) + hy*entries_sorted(k,4) + hz*entries_sorted(k,5));
            cos_ang_radius = cos(entries_sorted(k,6));
            % If even the nearest edge of the cap is within the blind cone, skip
            if dot_vb + cos_ang_radius < -cos_blind
                continue;
            end
            n_filtered = n_filtered + 1;
            filtered(n_filtered,:) = entries_sorted(k,:);
        end
        entries_sorted = filtered(1:n_filtered, :);
        n_eff = n_filtered;
    else
        n_eff = n_entries;
    end

    if n_eff == 0
        delta = [0, 0, 0]; vis_idx = []; vis_dists = []; n_vis = 0; theta = 0;
        return;
    end

    % ═══════════════════════════════════════════════════════════════
    %  PHASE 4: Fibonacci sphere z-buffer occlusion
    % ═══════════════════════════════════════════════════════════════

    fib = fibonacci_sphere_3d(n_fib);
    zbuf = -ones(n_fib, 1);    % -1 = unoccluded
    vis_idx = zeros(n_eff, 1);
    vis_dists = zeros(n_eff, 1);
    n_vis = 0;

    for k = 1:n_eff
        dir_x = entries_sorted(k, 3);
        dir_y = entries_sorted(k, 4);
        dir_z = entries_sorted(k, 5);
        ang_r = entries_sorted(k, 6);
        cos_r = cos(ang_r);
        d_j   = entries_sorted(k, 2);

        % Check if any Fibonacci point in this cap is unoccluded
        visible = false;
        for p = 1:n_fib
            if zbuf(p) < 0 || d_j < zbuf(p)
                dot_p = fib(p,1)*dir_x + fib(p,2)*dir_y + fib(p,3)*dir_z;
                if dot_p >= cos_r
                    visible = true;
                    break;
                end
            end
        end

        if visible
            n_vis = n_vis + 1;
            vis_idx(n_vis) = entries_sorted(k, 1);
            vis_dists(n_vis) = d_j;

            % Update z-buffer: mark all cap points as occluded at distance d_j
            for p = 1:n_fib
                dot_p = fib(p,1)*dir_x + fib(p,2)*dir_y + fib(p,3)*dir_z;
                if dot_p >= cos_r
                    if zbuf(p) < 0 || d_j < zbuf(p)
                        zbuf(p) = d_j;
                    end
                end
            end
        end
    end

    vis_idx = vis_idx(1:n_vis);
    vis_dists = vis_dists(1:n_vis);

    % ═══════════════════════════════════════════════════════════════
    %  PHASE 5: δ̂ — average of unoccluded Fibonacci points
    % ═══════════════════════════════════════════════════════════════

    delta = [0, 0, 0];
    n_unocc = 0;
    for p = 1:n_fib
        if zbuf(p) < 0
            delta = delta + [fib(p,1), fib(p,2), fib(p,3)];
            n_unocc = n_unocc + 1;
        end
    end
    if n_unocc > 0
        delta = delta / n_unocc;
        dnorm = norm(delta);
        if dnorm > 1e-9, delta = delta / dnorm; end
    end

    % ═══════════════════════════════════════════════════════════════
    %  PHASE 6: Internal opacity Θ_i = fraction of sphere occluded
    % ═══════════════════════════════════════════════════════════════

    n_occ = 0;
    for p = 1:n_fib
        if zbuf(p) > 0, n_occ = n_occ + 1; end
    end
    theta = n_occ / n_fib;
end


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 8 — MULTI-VIEWPOINT EXTERNAL OPACITY  (Priority 1b)       ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  ⇔ Scilab: alg2_extended.sce SECTION 8 (compute_external_opacity_multi)
%  ⇔ Python: extensions/multi_viewpoint_opacity.py
%  Θ′ — fraction of the sky obscured from a distant external observer.
%
%  Single viewpoint (ENABLE_1b = false):
%    Observer at (−2000, HEIGHT/2).  Merge all angular intervals.
%
%  Multi-viewpoint (ENABLE_1b = true):
%    K=12 observers on a circle of radius R_EXT around the flock centre.
%    Θ′ = (1/K) · Σ Θ′(viewpoint_k)
%    This reduces viewpoint-dependent bias, giving a rotation-invariant
%    measure of external opacity.
% ──────────────────────────────────────────────────────────────────────

function theta_ext = compute_external_opacity_multi(pos)
    global NUM_BOIDS BOID_SIZE ENABLE_1b K_VIEWPOINTS R_EXT WIDTH HEIGHT

    if ~ENABLE_1b
        % ── Single viewpoint fallback ──────────────────────────────
        viewpoint = [-2000, HEIGHT/2];
        diffs  = pos - repmat(viewpoint, NUM_BOIDS, 1);
        dists  = sqrt(sum(diffs.^2, 2));
        angles = atan2(diffs(:,2), diffs(:,1));
        angles(angles < 0) = angles(angles < 0) + 2 * pi;
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
        if n_int == 0, theta_ext = 0; return; end
        intervals = intervals(1:n_int, :);
        [~, idx] = sort(intervals(:,1));
        intervals = intervals(idx, :);
        [merged, n_m] = merge_angle_intervals(intervals, n_int);
        occluded = sum(merged(:,2) - merged(:,1));
        theta_ext = min(occluded / (2 * pi), 1.0);
        return;
    end

    % ── Multi-viewpoint: average over K viewpoints ────────────────
    total = 0;
    for vp = 0:K_VIEWPOINTS-1
        theta_vp = 2 * pi * vp / K_VIEWPOINTS;
        viewpoint = [R_EXT * cos(theta_vp), R_EXT * sin(theta_vp)];

        intervals = zeros(NUM_BOIDS * 2, 2);
        n_int = 0;
        for k = 1:NUM_BOIDS
            dx = pos(k,1) - viewpoint(1);
            dy = pos(k,2) - viewpoint(2);
            dist = sqrt(dx*dx + dy*dy);
            if dist < 0.001, continue; end
            centre = atan2(dy, dx);
            if centre < 0, centre = centre + 2*pi; end
            half = asin(min(BOID_SIZE / dist, 1));
            segs = normalise_interval_2d(centre - half, centre + half);
            for ss = 1:size(segs,1)
                n_int = n_int + 1;
                intervals(n_int,:) = segs(ss,:);
            end
        end
        if n_int > 0
            intervals = intervals(1:n_int, :);
            [~, idx] = sort(intervals(:,1));
            intervals = intervals(idx, :);
            [merged, n_m] = merge_angle_intervals(intervals, n_int);
            occluded = sum(merged(:,2) - merged(:,1));
            total = total + min(occluded / (2 * pi), 1.0);
        end
    end
    theta_ext = total / K_VIEWPOINTS;
end


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 9 — CORRELATION TIME COMPUTATION  (Priority 1c)           ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  τᵨ — density autocorrelation time.
%
%  The density ρ = N / area is sampled every CORR_SAMPLE_INTERVAL frames
%  into a ring buffer of size BUFFER_SIZE_TAU.  The autocorrelation function
%  C(τ) = ⟨ρ(t)·ρ(t+τ)⟩ − ⟨ρ⟩²  is integrated from lag 0 to the first
%  zero crossing (or maximum lag fraction), and τᵨ = ∫C(τ)dτ / C(0).
%
%  τᵨ measures the characteristic timescale over which the flock maintains
%  its density structure — higher τᵨ means more persistent flocking.
% ──────────────────────────────────────────────────────────────────────

function new_tau = compute_tau_from_buffer()
    global tau_buffer tau_frames tau_count BUFFER_SIZE_TAU CORR_SAMPLE_INTERVAL MAX_LAG_FRACTION

    m = tau_count;
    if m < 10, new_tau = 0; return; end

    % ── Step 1: Unroll ring buffer into time-ordered array ──────────
    dens = zeros(m, 1);
    for i = 1:m
        idx = mod(tau_idx - m + i - 2, BUFFER_SIZE_TAU) + 1;
        dens(i) = tau_buffer(idx);
    end

    % ── Step 2: Mean and variance ──────────────────────────────────
    mean_d = mean(dens);
    vari = sum((dens - mean_d).^2) / m;
    if vari < 1e-12, new_tau = 0; return; end

    % ── Step 3: Integrate autocorrelation ──────────────────────────
    max_lag = max(1, floor(m * MAX_LAG_FRACTION));
    dt = CORR_SAMPLE_INTERVAL;
    tau_sum = 0;

    for lag = 0:max_lag-1
        n_pairs = m - lag;
        if n_pairs < 2, break; end

        cross = 0;
        for i = 1:n_pairs
            cross = cross + dens(i) * dens(i + lag);
        end
        cross = cross / n_pairs;
        c = cross - mean_d * mean_d;
        if c <= 0, break; end  % stop at first zero crossing
        tau_sum = tau_sum + c * dt;
    end

    new_tau = tau_sum / vari;  % τᵨ = ∫C(τ)dτ / C(0)
end


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 10 — INPUT HANDLING  (keyboard callback)                   ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  Non-blocking keyboard event handler registered via KeyPressFcn.
%  Mutates global state; pending flags are applied atomically in the
%  main loop to avoid race conditions during rendering.
%
%  Key map (event.Key strings):
%    m/M      — toggle MODE
%    p/P      — toggle pause
%    f/F      — toggle predator
%    up/down  — φp ± 0.01
%    left/right — φa ± 0.01
%    leftbracket/rightbracket — σ ± 1
%    add/equal — +10 birds
%    subtract/hyphen — −10 birds
%    r/R      — reset flock
%    h/H      — toggle help overlay
% ──────────────────────────────────────────────────────────────────────

function key_handler_extended(src, event)
    global MODE paused PHI_P PHI_A SIGMA
    global pending_add pending_remove pending_reset show_help predator_active

    switch event.Key
        % ── Mode toggle ────────────────────────────────────────────
        case {'m', 'M'}
            MODE = 1 - MODE;
            if MODE == 0, disp('PROJECTION mode');
            else,         disp('SPATIAL mode'); end

        % ── Pause ──────────────────────────────────────────────────
        case {'p', 'P'}
            paused = ~paused;
            if paused, disp('Paused'); else, disp('Resumed'); end

        % ── Predator toggle ────────────────────────────────────────
        case {'f', 'F'}
            predator_active = ~predator_active;
            if predator_active, disp('Predator ON');
            else,               disp('Predator OFF'); end

        % ── φp  (up/down arrows) ───────────────────────────────────
        case 'uparrow'
            PHI_P = min(1.0, PHI_P + 0.01);
            disp(['phi_p = ' num2str(PHI_P)]);
        case 'downarrow'
            PHI_P = max(0.0, PHI_P - 0.01);
            disp(['phi_p = ' num2str(PHI_P)]);

        % ── φa  (left/right arrows) ────────────────────────────────
        case 'leftarrow'
            PHI_A = max(0.0, PHI_A - 0.01);
            disp(['phi_a = ' num2str(PHI_A)]);
        case 'rightarrow'
            PHI_A = min(1.0, PHI_A + 0.01);
            disp(['phi_a = ' num2str(PHI_A)]);

        % ── σ  (bracket keys) ─────────────────────────────────────
        case 'leftbracket'
            SIGMA = max(1, SIGMA - 1);
            disp(['sigma = ' num2str(SIGMA)]);
        case 'rightbracket'
            SIGMA = min(50, SIGMA + 1);
            disp(['sigma = ' num2str(SIGMA)]);

        % ── Boid count  (+/= and - keys) ──────────────────────────
        case {'add', 'equal'}
            pending_add = min(pending_add + 10, 200);
            disp('Adding 10 birds (pending)');
        case {'subtract', 'hyphen'}
            pending_remove = pending_remove + 10;
            disp('Removing 10 birds (pending)');

        % ── Reset ──────────────────────────────────────────────────
        case {'r', 'R'}
            pending_reset = true;
            disp('Resetting flock...');

        % ── Help overlay ───────────────────────────────────────────
        case {'h', 'H'}
            show_help = ~show_help;
            if show_help, disp('Help ON'); else, disp('Help OFF'); end
    end
end


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 11 — MAIN LOOP                                             ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  Each frame:
%    1. APPLY PENDING CHANGES  — add/remove birds, reset, auto φn
%    2. REBUILD CHUNKER       — grid-based spatial index (Priority 3b)
%    3. UPDATE PREDATOR       — hunt nearest bird (Priority 3a)
%    4. FLOCKING UPDATE       — per-bird steering (projection or spatial)
%    5. PREDATOR FLIGHT RESPONSE  — birds flee (Priority 3a)
%    6. PHYSICS UPDATE        — Euler integration, speed clamp, toroidal wrap
%    7. METRICS               — Θ, Θ′, α, τᵨ with EMA smoothing
%    8. CSV LOGGING           — append row every LOG_EVERY frames
%    9. RENDER                — update patches and text overlays
% ──────────────────────────────────────────────────────────────────────

frame    = 0;
smooth   = 0.05;                         % EMA factor for metrics
theta_ema     = 0;                        % Θ  — mean internal opacity (EMA)
theta_ext_ema = 0;                        % Θ' — external opacity (EMA)
alpha_ema     = 0;                        % α  — order parameter (EMA)
tau_ema       = 0;                        % τᵨ — correlation time (EMA)
power_ema     = 0;                        % P  — mean power (EMA)
angmom_ema    = 0;                        % L  — mean angular momentum (EMA)
avg_accel_ema = 0;                        % |a| — mean acceleration magnitude (EMA)
disp_ema      = 0;                        % σ_r — mean distance from CoM (EMA)

% Triangle vertex offsets (relative to position, rotated by heading)
tip_len  = BOID_SIZE * 2.5;
side_len = BOID_SIZE * 1.5;
side_ang = 2.3;

mode_names = {'PROJECTION  (Pearce et al. 2014) Extended', ...
              'SPATIAL     (topological Reynolds)  Extended'};

disp('Running — close the figure window to stop.');
disp('  9 roadmap priorities active (see ''h'' for feature flags)');
disp('  Keys:  m:mode  p:pause  f:falcon  h:help  arrows:phi  []:sigma  +/-:boids  r:reset');

% ═══════════════════════════════════════════════════════════════════
%  MAIN FRAME LOOP
% ═══════════════════════════════════════════════════════════════════
while isgraphics(f)
    t_frame = tic();

    if ~paused

        % ── 1. Auto-compute φn ─────────────────────────────────────
        %  φn = max(0, 1 − φp − φa − φs)
        %  Guarantees all weights sum to 1.
        PHI_N = max(0.0, 1.0 - PHI_P - PHI_A - PHI_S);

        % ── 1b. Boid count changes ─────────────────────────────────
        if pending_remove > 0
            n_remove = min(pending_remove, NUM_BOIDS - 1);
            if n_remove > 0
                pos        = pos(1:NUM_BOIDS - n_remove, :);
                vel        = vel(1:NUM_BOIDS - n_remove, :);
                acc        = acc(1:NUM_BOIDS - n_remove, :);
                last_theta = last_theta(1:NUM_BOIDS - n_remove);
                if DRAW_TRAIL
                    trail = trail(:, 1:NUM_BOIDS - n_remove, :);
                    trail_count = min(trail_count, NUM_BOIDS - n_remove);
                end
                NUM_BOIDS  = NUM_BOIDS - n_remove;
                pending_remove = pending_remove - n_remove;
                disp(['Removed ' num2str(n_remove) ' birds, now ' num2str(NUM_BOIDS)]);
            end
        end
        if pending_add > 0
            n_add = pending_add;
            new_ang = rand(n_add, 1) * 2 * pi;
            if ENABLE_2c
                new_pos = rand(n_add, 3) .* [WIDTH, HEIGHT, DEPTH];
                new_phi = (rand(n_add, 1) - 0.5) * pi;
                new_vel = [cos(new_ang).*cos(new_phi), sin(new_ang).*cos(new_phi), sin(new_phi)] .* V0;
                new_acc = zeros(n_add, 3);
            else
                new_pos = rand(n_add, 2) .* [WIDTH, HEIGHT];
                new_vel = [cos(new_ang), sin(new_ang)] .* (1 + rand(n_add, 1) * (V0 - 1));
                new_acc = zeros(n_add, 2);
            end
            pos        = [pos; new_pos];
            vel        = [vel; new_vel];
            acc        = [acc; new_acc];
            last_theta = [last_theta; zeros(n_add, 1)];
            if DRAW_TRAIL
                trail = cat(2, trail, zeros(TRAIL_LENGTH, n_add, 2));
            end
            NUM_BOIDS  = NUM_BOIDS + n_add;
            pending_add = 0;
            disp(['Added ' num2str(n_add) ' birds, now ' num2str(NUM_BOIDS)]);
        end

        % ── 1c. Reset ─────────────────────────────────────────────
        if pending_reset
            if ENABLE_2c
                pos = rand(NUM_BOIDS, 3) .* [WIDTH, HEIGHT, DEPTH];
                ang = rand(NUM_BOIDS, 1) * 2 * pi;
                phi = (rand(NUM_BOIDS, 1) - 0.5) * pi;
                vel = [cos(ang).*cos(phi), sin(ang).*cos(phi), sin(phi)] .* V0;
                acc = zeros(NUM_BOIDS, 3);
            else
                pos = rand(NUM_BOIDS, 2) .* [WIDTH, HEIGHT];
                ang = rand(NUM_BOIDS, 1) * 2 * pi;
                vel = [cos(ang), sin(ang)] .* (1 + rand(NUM_BOIDS, 1) * (V0 - 1));
                acc = zeros(NUM_BOIDS, 2);
            end
            last_theta = zeros(NUM_BOIDS, 1);
            theta_ema = 0; theta_ext_ema = 0; alpha_ema = 0; tau_ema = 0; power_ema = 0; angmom_ema = 0; avg_accel_ema = 0; disp_ema = 0;
            if DRAW_TRAIL
                trail       = zeros(TRAIL_LENGTH, NUM_BOIDS, 2);
                trail_idx   = 1;
                trail_count = 0;
            end
            tau_count = 0; tau_idx = 1; tau_timer = 0;
            frame = 0;
            pending_reset = false;
            disp(['Flock reset — ' num2str(NUM_BOIDS) ' birds']);
        end

        % ── 2. Rebuild spatial chunker (Priority 3b) ──────────────
        if ENABLE_3b && ~ENABLE_2c
            chunk_cells = rebuild_chunker_octave(pos);
        else
            chunk_cells = {};
        end

        % ── 3. Update predator (Priority 3a) ──────────────────────
        if ENABLE_3a && predator_active && ~ENABLE_2c
            % Find nearest bird
            nearest_dist = Inf;
            nearest_idx = 1;
            for i = 1:NUM_BOIDS
                dx_p = pos(i,1) - predator_pos(1);
                dy_p = pos(i,2) - predator_pos(2);
                if abs(dx_p) > WIDTH/2, dx_p = dx_p - sign(dx_p)*WIDTH; end
                if abs(dy_p) > HEIGHT/2, dy_p = dy_p - sign(dy_p)*HEIGHT; end
                d = sqrt(dx_p*dx_p + dy_p*dy_p);
                if d < nearest_dist
                    nearest_dist = d; nearest_idx = i;
                end
            end

            % Hunt toward nearest bird
            to_target = pos(nearest_idx,:) - predator_pos;
            dx_tt = to_target(1); dy_tt = to_target(2);
            if abs(dx_tt) > WIDTH/2, dx_tt = dx_tt - sign(dx_tt)*WIDTH; end
            if abs(dy_tt) > HEIGHT/2, dy_tt = dy_tt - sign(dy_tt)*HEIGHT; end
            dist_tt = sqrt(dx_tt*dx_tt + dy_tt*dy_tt);
            if dist_tt > 0.001
                predator_acc = [dx_tt/dist_tt, dy_tt/dist_tt] * PREDATOR_ACCEL;
            else
                predator_acc = [0, 0];
            end
            % Noise for exploration
            na = rand() * 2 * pi;
            predator_acc = predator_acc + [cos(na), sin(na)] * PREDATOR_ACCEL * 0.3;

            predator_vel = predator_vel + predator_acc;
            spd_p = norm(predator_vel);
            if spd_p > PREDATOR_SPEED
                predator_vel = predator_vel / spd_p * PREDATOR_SPEED;
            end
            if spd_p < PREDATOR_SPEED * 0.3 && spd_p > 0.001
                predator_vel = predator_vel / spd_p * PREDATOR_SPEED * 0.3;
            end

            predator_pos = predator_pos + predator_vel;
            predator_pos(1) = mod(predator_pos(1), WIDTH);
            predator_pos(2) = mod(predator_pos(2), HEIGHT);

            % Track trail (last 20 positions)
            predator_trail = [predator_trail; predator_pos];
            if size(predator_trail,1) > 20
                predator_trail = predator_trail(2:end, :);
            end
        end

        % ═══════════════════════════════════════════════════════════
        %  4. FLOCKING UPDATE
        % ═══════════════════════════════════════════════════════════

        if MODE == 0
            if ENABLE_2c
                % ── 3D Projection ────────────────────────────────
                for i = 1:NUM_BOIDS
                    [delta, vis_idx, vis_dists, n_vis, theta] = ...
                        compute_projection_3d(i, pos, vel);
                    last_theta(i) = theta;

                    align = [0, 0, 0];
                    if n_vis > 0
                        sigma_use = min(SIGMA, n_vis);
                        for k = 1:sigma_use
                            j_vis = vis_idx(k);
                            align = align + vel(j_vis, :);
                        end
                        align = align / sigma_use;
                    end

                    na1 = rand() * 2 * pi;
                    na2 = (rand() - 0.5) * pi;
                    noise = [cos(na1)*cos(na2), sin(na1)*cos(na2), sin(na2)];

                    desired = delta * PHI_P;
                    if norm(align) > 0.001
                        desired = desired + (align / norm(align)) * PHI_A;
                    else
                        if norm(vel(i,:)) > 0.001
                            desired = desired + (vel(i,:) / norm(vel(i,:))) * PHI_A;
                        end
                    end
                    desired = desired + noise * PHI_N;

                    if norm(desired) < 0.001
                        desired = [rand()*2-1, rand()*2-1, rand()*2-1];
                    end
                    desired = desired / norm(desired) * V0;

                    if ENABLE_1a
                        % Priority 1a: Direct velocity setting
                        vel(i,:) = desired;
                    else
                        steer = desired - vel(i,:);
                        if norm(steer) > MAX_FORCE
                            steer = steer / norm(steer) * MAX_FORCE;
                        end
                        acc(i,:) = acc(i,:) + steer;
                    end
                end

            else
                % ── 2D Projection ────────────────────────────────
                for i = 1:NUM_BOIDS
                    [delta, vis_idx, vis_dists, n_vis, theta] = ...
                        compute_projection_extended(i, pos, vel, chunk_cells);
                    last_theta(i) = theta;

                    align = [0, 0];
                    if n_vis > 0
                        sigma_use = min(SIGMA, n_vis);
                        for k = 1:sigma_use
                            j_vis = vis_idx(k);
                            align = align + vel(j_vis, :);
                        end
                        align = align / sigma_use;
                    end

                    na = rand() * 2 * pi;
                    noise = [cos(na), sin(na)];

                    desired = delta * PHI_P;
                    if norm(align) > 0.001
                        desired = desired + (align / norm(align)) * PHI_A;
                    else
                        if norm(vel(i,:)) > 0.001
                            desired = desired + (vel(i,:) / norm(vel(i,:))) * PHI_A;
                        end
                    end
                    desired = desired + noise * PHI_N;

                    if norm(desired) < 0.001
                        desired = [rand()*2-1, rand()*2-1];
                    end
                    desired = desired / norm(desired) * V0;

                    if ENABLE_1a
                        % Priority 1a: Direct velocity setting
                        vel(i,:) = desired;
                    else
                        steer = desired - vel(i,:);
                        if norm(steer) > MAX_FORCE
                            steer = steer / norm(steer) * MAX_FORCE;
                        end
                        acc(i,:) = acc(i,:) + steer;
                    end

                    % ── Priority 2a: Steric repulsion ───────────
                    if ENABLE_2a
                        repulsion = [0, 0];
                        for j = 1:NUM_BOIDS
                            if j == i, continue; end
                            diff = pos(i,:) - pos(j,:);
                            dx_r = diff(1); dy_r = diff(2);
                            if abs(dx_r) > WIDTH/2, dx_r = dx_r - sign(dx_r)*WIDTH; end
                            if abs(dy_r) > HEIGHT/2, dy_r = dy_r - sign(dy_r)*HEIGHT; end
                            d = sqrt(dx_r*dx_r + dy_r*dy_r);
                            if d < STERIC_RADIUS && d > 0.001
                                repulsion = repulsion + [dx_r/d, dy_r/d] / (d * d);
                            end
                        end
                        if norm(repulsion) > 0.001
                            repulsion = repulsion / norm(repulsion) * PHI_S * BOID_SIZE;
                            vel(i,:) = vel(i,:) + repulsion;
                            if norm(vel(i,:)) > 0.001
                                vel(i,:) = vel(i,:) / norm(vel(i,:)) * V0;
                            end
                        end
                    end
                end
            end

        else
            % ── MODE 1: SPATIAL (Reynolds boids) ──────────────
            dx = repmat(pos(:,1), 1, NUM_BOIDS) - repmat(pos(:,1)', NUM_BOIDS, 1);
            dy = repmat(pos(:,2), 1, NUM_BOIDS) - repmat(pos(:,2)', NUM_BOIDS, 1);
            dist_mat = sqrt(dx.^2 + dy.^2);

            for i = 1:NUM_BOIDS
                row = dist_mat(i, :); row(i) = Inf;
                in_range = find(row < VISUAL_RANGE);

                sep = [0, 0]; ali = [0, 0]; coh = [0, 0];

                if ~isempty(in_range)
                    range_dists = row(in_range);
                    [~, sort_idx] = sort(range_dists);
                    sigma_use = min(SIGMA, length(in_range));
                    nbs = in_range(sort_idx(1:sigma_use));

                    for k = 1:sigma_use
                        j = nbs(k);
                        d_ij = dist_mat(i, j);
                        ali = ali + vel(j, :);
                        coh = coh + pos(j, :);
                        if d_ij < VISUAL_RANGE * 0.3 && d_ij > 0.001
                            diff_ij = pos(i,:) - pos(j,:);
                            sep = sep + diff_ij / d_ij;
                        end
                    end

                    ali = ali / sigma_use;
                    coh = coh / sigma_use;

                    if norm(ali) > 0.001, ali = ali / norm(ali) * V0; end
                    ali = ali - vel(i,:);
                    if norm(ali) > MAX_FORCE, ali = ali / norm(ali) * MAX_FORCE; end

                    coh = coh - pos(i,:);
                    if norm(coh) > 0.001, coh = coh / norm(coh) * V0; end
                    coh = coh - vel(i,:);
                    if norm(coh) > MAX_FORCE, coh = coh / norm(coh) * MAX_FORCE; end

                    if norm(sep) > 0.001, sep = sep / norm(sep) * V0; end
                    sep = sep - vel(i,:);
                    if norm(sep) > MAX_FORCE, sep = sep / norm(sep) * MAX_FORCE; end
                end

                na = rand() * 2 * pi;
                noise = [cos(na), sin(na)] * MAX_FORCE * 0.8;

                acc(i,:) = acc(i,:) + sep * PHI_P * 2.0;
                acc(i,:) = acc(i,:) + ali * PHI_A * 1.2;
                acc(i,:) = acc(i,:) + coh * PHI_N * 1.5;
                acc(i,:) = acc(i,:) + noise;
            end
        end

        % ── 5. Predator flight response (Priority 3a) ──────────────
        if ENABLE_3a && predator_active && ~ENABLE_2c
            for i = 1:NUM_BOIDS
                diff_p = pos(i,:) - predator_pos;
                dx_p = diff_p(1); dy_p = diff_p(2);
                if abs(dx_p) > WIDTH/2, dx_p = dx_p - sign(dx_p)*WIDTH; end
                if abs(dy_p) > HEIGHT/2, dy_p = dy_p - sign(dy_p)*HEIGHT; end
                d = sqrt(dx_p*dx_p + dy_p*dy_p);
                if d < DANGER_RADIUS && d > 0.001
                    flight = [dx_p/d, dy_p/d] * FLIGHT_FORCE * ((DANGER_RADIUS - d) / DANGER_RADIUS);
                    vel(i,:) = vel(i,:) + flight;
                    if norm(vel(i,:)) > 0.001
                        vel(i,:) = vel(i,:) / norm(vel(i,:)) * V0;
                    end
                end
            end
        end

        % ═══════════════════════════════════════════════════════════
        %  6. PHYSICS UPDATE  (shared by both modes)
        % ═══════════════════════════════════════════════════════════
        %  Euler integration with speed clamping and toroidal wrap.
        %  Skipped when ENABLE_1a is active (velocity set directly).

        % ── Power & angular momentum (computed BEFORE acc cleared) ──
        % ⇔ Python: metrics.py §FlockMetrics.update
        % ⇔ Scilab: alg2_extended.sce §PHASE 6
        if ~ENABLE_2c
            power_raw  = mean(sum(acc .* vel, 2));
            angmom_raw = mean(pos(:,1) .* vel(:,2) - pos(:,2) .* vel(:,1));
            power_ema  = power_ema  + (power_raw  - power_ema)  * smooth;
            angmom_ema = angmom_ema + (angmom_raw - angmom_ema) * smooth;

            % Avg acceleration magnitude: mean |acc| / MAX_FORCE
            accel_raw = mean(sqrt(sum(acc.^2, 2))) / MAX_FORCE;
            avg_accel_ema = avg_accel_ema + (accel_raw - avg_accel_ema) * smooth;
        end

        if ~ENABLE_1a || MODE == 1
            vel = vel + acc;
            spd = sqrt(sum(vel.^2, 2));

            fast = find(spd > V0);
            if ~isempty(fast)
                if DIMENSIONS == 3
                    vel(fast,:) = vel(fast,:) ./ repmat(spd(fast), 1, 3) * V0;
                else
                    vel(fast,:) = vel(fast,:) ./ repmat(spd(fast), 1, 2) * V0;
                end
            end
            slow = find(spd < V0 * 0.3);
            if ~isempty(slow)
                for s = slow'
                    if spd(s) > 0.001
                        vel(s,:) = vel(s,:) / spd(s) * V0 * 0.3;
                    else
                        if DIMENSIONS == 3
                            na1 = rand()*2*pi; na2 = (rand()-0.5)*pi;
                            vel(s,:) = [cos(na1)*cos(na2), sin(na1)*cos(na2), sin(na2)] * V0 * 0.3;
                        else
                            na = rand()*2*pi;
                            vel(s,:) = [cos(na), sin(na)] * V0 * 0.3;
                        end
                    end
                end
            end
        end

        pos = pos + vel;
        acc = acc * 0;

        % Toroidal wrap
        pos(:,1) = mod(pos(:,1), WIDTH);
        pos(:,2) = mod(pos(:,2), HEIGHT);
        if ENABLE_2c
            pos(:,3) = mod(pos(:,3), DEPTH);
        end

        % ── Trail: record position (ring buffer) ──────────────────
        if DRAW_TRAIL
            trail_idx = mod(trail_idx, TRAIL_LENGTH) + 1;
            trail(trail_idx, :, 1) = pos(:, 1)';
            trail(trail_idx, :, 2) = pos(:, 2)';
            trail_count = min(trail_count + 1, TRAIL_LENGTH);
        end

% ═══════════════════════════════════════════════════════════
%  7. METRICS  (Θ, Θ′, α, τᵨ, dispersion)
% ═══════════════════════════════════════════════════════════

% ── Flock dispersion: mean distance from CoM ─────────────
if ~ENABLE_2c
    com = mean(pos, 1);
    disp_raw = mean(sqrt(sum((pos - com).^2, 2)));
    disp_ema = disp_ema + (disp_raw - disp_ema) * smooth;
end

% Θ — internal opacity
        if MODE == 0
            theta_raw = mean(last_theta);
        else
            sample_n = min(5, NUM_BOIDS);
            sample_idx = randperm(NUM_BOIDS, sample_n);
            theta_sum = 0;
            for s = 1:sample_n
                [~, ~, ~, ~, theta_sample] = ...
                    compute_projection_extended(sample_idx(s), pos, vel, chunk_cells);
                theta_sum = theta_sum + theta_sample;
            end
            theta_raw = theta_sum / sample_n;
        end
        theta_ema = theta_ema + (theta_raw - theta_ema) * smooth;

        % Θ′ — external opacity (Priority 1b)
        theta_ext_raw = compute_external_opacity_multi(pos);
        theta_ext_ema = theta_ext_ema + (theta_ext_raw - theta_ext_ema) * smooth;

        % α — order parameter
        total_vel = sum(vel, 1);
        alpha_raw = norm(total_vel) / (NUM_BOIDS * V0);
        alpha_ema = alpha_ema + (alpha_raw - alpha_ema) * smooth;

        % Priority 1c: Correlation time τᵨ
        if ENABLE_1c && ~ENABLE_2c
            tau_timer = tau_timer + 1;
            if tau_timer >= CORR_SAMPLE_INTERVAL
                tau_timer = 0;
                if NUM_BOIDS >= 3
                    area = convex_hull_area_2d(pos);
                    if area > 1
                        density = NUM_BOIDS / area;
                        last_density = density;
                        tau_buffer(tau_idx) = density;
                        tau_frames(tau_idx) = frame;
                        tau_idx = mod(tau_idx, BUFFER_SIZE_TAU) + 1;
                        if tau_count < BUFFER_SIZE_TAU, tau_count = tau_count + 1; end
                        tau_val = compute_tau_from_buffer();
                    end
                end
            end
            tau_ema = tau_ema + (tau_val - tau_ema) * smooth;
        end



        % ── 8. CSV logging ─────────────────────────────────────────
        if log_fid ~= -1 && mod(frame, LOG_EVERY) == 0
            fps = 1 / max(toc(t_frame), 0.001);
            fprintf(log_fid, '%d,%d,%d,%.4f,%.4f,%.4f,%.4f,%d,%.4f,%.4f,%.1f,%.4f,%.1f,%.4f,%.4f\n', ...
                    frame, MODE, NUM_BOIDS, PHI_P, PHI_A, PHI_N, PHI_S, SIGMA, ...
                    theta_ema, theta_ext_ema, tau_ema, alpha_ema, fps, power_ema, angmom_ema, avg_accel_ema, disp_ema);
        end

    end  % ~paused

    % ═══════════════════════════════════════════════════════════════
    %  9. RENDER
    % ═══════════════════════════════════════════════════════════════

    if ~ENABLE_2c || MODE == 1
        % ── 2D bird triangles ──────────────────────────────────────
        dirs = atan2(vel(:,2), vel(:,1));

        tip_x = pos(:,1)' + cos(dirs)' * tip_len;
        tip_y = pos(:,2)' + sin(dirs)' * tip_len;
        lft_x = pos(:,1)' + cos(dirs + side_ang)' * side_len;
        lft_y = pos(:,2)' + sin(dirs + side_ang)' * side_len;
        rgt_x = pos(:,1)' + cos(dirs - side_ang)' * side_len;
        rgt_y = pos(:,2)' + sin(dirs - side_ang)' * side_len;

        X = [tip_x; lft_x; rgt_x];
        Y = [tip_y; lft_y; rgt_y];

        if MODE == 0
            bird_color = [200 210 230] / 255;
        else
            bird_color = [230 200 160] / 255;
        end
        set(hBoids, 'XData', X, 'YData', Y, 'FaceColor', bird_color, 'Visible', 'on');

        % ── Predator ────────────────────────────────────────────────
        if ENABLE_3a && predator_active
            if norm(predator_vel) > 0.001
                pdir = atan2(predator_vel(2), predator_vel(1));
            else pdir = 0; end
            psize = 6;
            px_tip = predator_pos(1) + cos(pdir) * psize * 3;
            py_tip = predator_pos(2) + sin(pdir) * psize * 3;
            px_lft = predator_pos(1) + cos(pdir + 2.3) * psize * 2;
            py_lft = predator_pos(2) + sin(pdir + 2.3) * psize * 2;
            px_rgt = predator_pos(1) + cos(pdir - 2.3) * psize * 2;
            py_rgt = predator_pos(2) + sin(pdir - 2.3) * psize * 2;

            set(hPredator, 'XData', [px_tip; px_lft; px_rgt], ...
                           'YData', [py_tip; py_lft; py_rgt], ...
                           'FaceColor', [255 80 60]/255, ...
                           'Visible', 'on');
        else
            set(hPredator, 'Visible', 'off');
        end
    else
        % ── 3D perspective projection ──────────────────────────────
        %  Hide 2D patch, draw circles with depth-dependent size
        set(hBoids, 'Visible', 'off');
        set(hPredator, 'Visible', 'off');

        % Clear any previous 3D patches
        delete(findobj(gca, 'Type', 'patch', '-not', 'Tag', 'keep'));
        % Re-draw: each bird as a small circle
        n_circle = 6;
        total_verts = (n_circle + 1) * NUM_BOIDS;  % +1 for NaN separator
        X3D = zeros(total_verts, 1);
        Y3D = zeros(total_verts, 1);
        % We'll use one patch per bird for color; simpler: precompute all
        for i = 1:NUM_BOIDS
            depth_factor = max(0.2, pos(i,3) / DEPTH);
            px = pos(i,1);
            py = pos(i,2);
            sz = max(1, 6 * depth_factor);
            rad = max(0.3, 1.0 * depth_factor);

            base = (i-1) * (n_circle + 1);
            for ci = 0:n_circle-1
                ca = 2*pi*ci/n_circle;
                X3D(base + ci + 1) = px + cos(ca)*sz;
                Y3D(base + ci + 1) = py + sin(ca)*sz*rad;
            end
            X3D(base + n_circle + 1) = NaN;
            Y3D(base + n_circle + 1) = NaN;

            % Color: darker when farther
            r = min(1, 0.15 + 0.7*depth_factor);
            g = min(1, 0.17 + 0.7*depth_factor);
            b = min(1, 0.19 + 0.7*depth_factor);
            patch(X3D(base+1:base+n_circle), Y3D(base+1:base+n_circle), ...
                  'FaceColor', [r g b], 'EdgeColor', 'none');
        end
    end

    % ── Trail rendering (2D mode only) ───────────────────────────
    if DRAW_TRAIL && trail_count > 1 && ~ENABLE_2c
        delete(trail_h(ishandle(trail_h)));
        trail_h = [];
        for i = 1:NUM_BOIDS
            order = mod((trail_idx - trail_count : trail_idx - 1), TRAIL_LENGTH) + 1;
            order(order < 1) = order(order < 1) + TRAIL_LENGTH;
            tx = trail(order, i, 1);
            ty = trail(order, i, 2);
            if length(tx) > 1
                h = line(tx, ty, 'Color', [85 140 244]/255 * 0.4, 'LineWidth', 0.5);
                trail_h = [trail_h; h];
            end
        end
    end

    % ── Metrics text overlay ──────────────────────────────────────
    fps = 1 / max(toc(t_frame), 0.001);
    set(hTextFPS,    'String', sprintf('FPS: %.0f    Boids: %d    Frame: %d', ...
                                        fps, NUM_BOIDS, frame));
    set(hTextParams, 'String', sprintf('φp=%.3f  φa=%.3f  φn=%.3f  φs=%.3f  σ=%d', ...
                                        PHI_P, PHI_A, PHI_N, PHI_S, SIGMA));

    if MODE == 0
        set(hTextTheta, 'String', sprintf('Opacity  Θ  = %.3f', theta_ema));
    else
        set(hTextTheta, 'String', sprintf('Opacity  Θ  ~ %.3f  (sampled)', theta_ema));
    end
    set(hTextExt,   'String', sprintf('          Θ'' = %.3f', theta_ext_ema));

    if ENABLE_1c
        set(hTextTau, 'String', sprintf('τᵨ = %.1f fr   α = %.3f', tau_ema, alpha_ema));
    else
        set(hTextTau, 'String', sprintf('Order α = %.3f', alpha_ema));
    end
    set(hTextPower, 'String', sprintf('P=%.1f  L=%.0f  |a|=%.3f  σ=%.0f', power_ema, angmom_ema, avg_accel_ema, disp_ema));

    % ── Mode badge ─────────────────────────────────────────────────
    set(hTextBadge, 'String', mode_names{MODE + 1});

    % ── Pause indicator ────────────────────────────────────────────
    if paused
        set(hTextPause, 'String', 'PAUSED', 'Visible', 'on');
    else
        set(hTextPause, 'Visible', 'off');
    end

    % ── Help overlay ───────────────────────────────────────────────
    if show_help
        help_str = '';
        for l = 1:length(help_lines)
            help_str = [help_str help_lines{l} '\n'];
        end
        set(hHelp, 'String', sprintf(help_str), 'Visible', 'on');
    else
        set(hHelp, 'Visible', 'off');
    end

    % Yield CPU so the event queue processes key presses
    pause(0.001);

    frame = frame + 1;

end  % while isgraphics(f)


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 12 — SHUTDOWN                                              ║
% ╚══════════════════════════════════════════════════════════════════════╝

if log_fid ~= -1
    fclose(log_fid);
    disp(['Metrics saved to ' LOG_FILE]);
end
disp(['Simulation ended after ' num2str(frame) ' frames.']);
disp('Run again to restart.');
% =======================================================================
