% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 1 — HEADER & OVERVIEW                                      ║
% ╚══════════════════════════════════════════════════════════════════════╝
%
%  alg2.m — Dual-Mode Bird Flock Simulation (GNU Octave)
%  ─────────────────────────────────────────────────────
%  Based on:  Pearce, Miller, Rowlands & Turner (2014)
%             "Role of projection in the control of bird flocks"
%             PNAS 111(29), 10422–10426.
%             DOI: 10.1073/pnas.1402202111
%
%  Two switchable flocking modes (press 'm' to toggle):
%  ─────────────────────────────────────────────────────
%    MODE 0 — PROJECTION   Hybrid projection model (Pearce et al., Eq. 3)
%             v_i = φp·δ̂_i + φa·⟨v̂_j⟩_visible + φn·η̂_i
%
%             δ̂_i  = direction to the nearest boundary of the occluded
%                    angular domain (computed via incremental angular-
%                    interval merging of closer-first neighbours).
%             Visibility determined by occlusion: a neighbour is visible
%             iff any portion of its subtended angular interval is NOT
%             already covered by birds closer to the observer.
%             Internal opacity Θ_i = fraction of 2π occluded.
%
%    MODE 1 — SPATIAL      Topological Reynolds boids (Reynolds 1987)
%             Separation / Alignment / Cohesion with σ nearest neighbours
%             within VISUAL_RANGE.  Weights are repurposed:
%               φp → separation, φa → alignment, φn → cohesion.
%
%  See the companion files alg2.py (Python/Pygame) and alg2.sce (Scilab)
%  for ports to other computing environments.
%
%  Usage:  run this script in GNU Octave.
%          Close the figure window to stop.
% =======================================================================


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 2 — CONFIGURATION CONSTANTS                                ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  These are the physical and numerical parameters of the simulation.
%  φp, φa, φn, and σ can be adjusted at runtime via keyboard controls.
%  Declare globals FIRST so all functions can share mutable state.
% ──────────────────────────────────────────────────────────────────────

global NUM_BOIDS BOID_SIZE WIDTH HEIGHT VISUAL_RANGE
global MODE paused PHI_P PHI_A PHI_N SIGMA
global pending_add pending_remove pending_reset show_help

% ── Display ───────────────────────────────────────────────────────────
WIDTH        = 1000;                   % simulation area width  (pixels)
HEIGHT       = 700;                    % simulation area height (pixels)

% ── Flock parameters ──────────────────────────────────────────────────
NUM_BOIDS    = 100;                    % number of birds (reduce if slow)
BOID_SIZE    = 3;                      % bird radius b  (paper: b = 1)
V0           = 4;                      % constant cruising speed v₀
MAX_FORCE    = 0.15;                   % max steering force (smooth turning)
VISUAL_RANGE = 70;                     % neighbour search radius (spatial mode)

% ── Default model weights  (φp + φa ≡ 1 − φn) ────────────────────────
PHI_P  = 0.03;                         % projection / separation weight
PHI_A  = 0.80;                         % alignment weight
PHI_N  = 0.17;                         % noise weight — auto-computed each frame
SIGMA  = 4;                            % number of nearest visible neighbours

% ── Mode identifier ───────────────────────────────────────────────────
MODE   = 0;                            % 0 = PROJECTION, 1 = SPATIAL

% ── CSV logging ───────────────────────────────────────────────────────
LOG_FILE  = 'murmuration_metrics.csv';
LOG_EVERY = 10;                        % write a row every N frames


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 3 — RUNTIME STATE INITIALIZATION                           ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  Octave uses flat matrices for state (no classes).  Parallel N×2
%  arrays for positions, velocities, accelerations — fully vectorized
%  where possible for performance.
% ──────────────────────────────────────────────────────────────────────

% ── Mutable runtime flags ────────────────────────────────────────────
paused         = false;                % toggled by 'p' key
pending_add    = 0;                    % boid count change requests
pending_remove = 0;
pending_reset  = false;                % 'r' triggers full reset
show_help      = false;                % 'h' toggles help overlay

% ── State arrays  (N × 2) ────────────────────────────────────────────
%  pos  — positions           (rows: birds, cols: [x, y])
%  vel  — velocities          (rows: birds, cols: [vx, vy])
%  acc  — steering accumulators  (rows: birds, cols: [ax, ay])
%  last_theta — cached internal opacity Θ per bird  (N × 1)
disp(['Initializing flock with ' num2str(NUM_BOIDS) ' birds ...']);

pos  = rand(NUM_BOIDS, 2) .* [WIDTH, HEIGHT];          % random positions
ang  = rand(NUM_BOIDS, 1) * 2 * pi;                    % random headings
vel  = [cos(ang), sin(ang)] .* (1 + rand(NUM_BOIDS, 1) * (V0 - 1));
acc  = zeros(NUM_BOIDS, 2);
last_theta = zeros(NUM_BOIDS, 1);                      % cached Θ per bird


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 2b — CSV LOGGING SETUP                                    ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  Open the metrics log file and write the CSV header.
% ──────────────────────────────────────────────────────────────────────

log_fid = fopen(LOG_FILE, 'w');
if log_fid == -1
    disp(['WARNING: could not open ' LOG_FILE ' for writing']);
else
    fprintf(log_fid, 'frame,mode,num_boids,phi_p,phi_a,phi_n,sigma,theta,theta_ext,alpha,fps\n');
    disp(['Logging metrics to ' LOG_FILE ' every ' num2str(LOG_EVERY) ' frames']);
end


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 2c — FIGURE & GRAPHICS SETUP                              ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  Create the figure window with keyboard callback.
%  Pre-allocate graphics handles for efficient per-frame updates.
% ──────────────────────────────────────────────────────────────────────

f = figure('Name', ...
    'Murmuration  [m:mode p:pause arrows:phi []:sigma +/-:boids r:reset h:help]', ...
    'NumberTitle', 'off', ...
    'Position', [100, 100, WIDTH, HEIGHT], ...
    'Color', [0.08 0.09 0.12]);

set(f, 'KeyPressFcn', @key_handler);

axis equal;
axis([0 WIDTH 0 HEIGHT]);
axis off;
hold on;

% ── Bird triangles  (3 vertices × N birds, stored as 3×N matrices) ──
%  Each column of X,Y is one triangle (tip, left, right vertices).
%  Updated each frame via set(hBoids, 'XData', X, 'YData', Y).
hBoids = patch(zeros(3, NUM_BOIDS), zeros(3, NUM_BOIDS), ...
               [200 210 230]/255, 'EdgeColor', 'none');

% ── Metrics text handles  (created once, updated via set(.String)) ───
hTextFPS    = text(10, 5,   '', 'Color', [170 200 170]/255, 'FontSize', 12);
hTextParams = text(10, 25,  '', 'Color', [170 200 170]/255, 'FontSize', 12);
hTextTheta  = text(10, 45,  '', 'Color', [170 200 170]/255, 'FontSize', 12);
hTextExt    = text(10, 65,  '', 'Color', [170 200 170]/255, 'FontSize', 12);
hTextAlpha  = text(10, 85,  '', 'Color', [170 200 170]/255, 'FontSize', 12);
hTextBadge  = text(WIDTH-250, 5, '', 'Color', [170 200 170]/255, 'FontSize', 12);

% ── Pause indicator  (hidden by default) ─────────────────────────────
hTextPause  = text(WIDTH/2-100, HEIGHT-30, '', ...
                   'Color', [255 200 100]/255, 'FontSize', 14, ...
                   'Visible', 'off');

% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 10 — HELP OVERLAY  (single text with alpha background)    ║
% ╚══════════════════════════════════════════════════════════════════════╝
% ── Help overlay  (single text with alpha-blended background) ────────
help_str = sprintf([ ...
    'CONTROLS\n', ...
    '───────────────────────────────\n', ...
    'm        toggle  PROJECTION / SPATIAL\n', ...
    'p        pause / resume\n', ...
    'r        reset flock\n', ...
    'h        hide this help\n', ...
    '\x2191 / \x2193    %cp  +/-0.01\n', ...
    '\x2190 / \x2192    %ca  +/-0.01\n', ...
    '[ / ]    %c   +/-1\n', ...
    '+ / -    add / remove 10 birds\n', ...
    'ESC      close window to quit\n']);
help_str = sprintf(help_str, 966, 966, 963);  % φ glyphs
hHelp = text(WIDTH-345, HEIGHT-10, help_str, ...
             'BackgroundColor', [0 0 0 0.8], ...
             'Color', [0.8 0.8 0.6], ...
             'EdgeColor', [0.3 0.3 0.3], ...
             'VerticalAlignment', 'top', ...
             'FontSize', 10, ...
             'Visible', 'off');


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 11 — INPUT HANDLING  (keyboard callback)                   ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  NOTE: This section appears before the core algorithm sections (4–7)
%  because Octave requires function definitions to precede their use.
%  The callback is registered on the figure but executed asynchronously
%  during the main loop via pause() / drawnow().
%  Non-blocking keyboard event handler registered via KeyPressFcn.
%  Mutates global state; pending flags are applied atomically in the
%  main loop to avoid race conditions during rendering.
%
%  Key map (event.Key strings):
%    m/M      — toggle MODE (PROJECTION ↔ SPATIAL)
%    p/P      — toggle pause
%    up/down  — φp ± 0.01
%    left/right — φa ± 0.01
%    leftbracket/rightbracket — σ ± 1
%    add/equal — +10 birds
%    subtract/hyphen — −10 birds
%    r/R      — reset flock
%    h/H      — toggle help overlay
% ──────────────────────────────────────────────────────────────────────

function key_handler(src, event)
    global MODE paused PHI_P PHI_A SIGMA
    global pending_add pending_remove pending_reset show_help

    switch event.Key
        % ── Mode toggle ────────────────────────────────────────────
        case {'m', 'M'}
            MODE = 1 - MODE;                % 0 ↔ 1
            if MODE == 0, disp('PROJECTION mode');
            else,         disp('SPATIAL mode'); end

        % ── Pause ──────────────────────────────────────────────────
        case {'p', 'P'}
            paused = ~paused;
            if paused, disp('Paused'); else, disp('Resumed'); end

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
        %  Pending flags avoid frame-tearing during rendering.
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
% ║  SECTION 4 — ANGULAR-INTERVAL UTILITIES                            ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  Helper for merging overlapping angular intervals on [0, 2π).
%  Used by both the projection model (SECTION 5) and external opacity
%  (SECTION 7).
%
%  Input:  sorted intervals  (n_int × 2: [start, end])
%  Output: merged intervals  (n_merged × 2), with overlaps collapsed.
%  Complexity: O(n_int) — single linear pass over sorted input.
% ──────────────────────────────────────────────────────────────────────

function [merged, n_merged] = merge_angle_intervals(intervals, n_int)
    % Given sorted intervals (n_int × 2; column 1 = start, column 2 = end),
    % merge all overlapping intervals into a minimal set.
    % Returns merged(n_int × 2) with actual data in rows 1:n_merged.

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


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 5 — PROJECTION MODEL  (MODE 0)                             ║
% ╚══════════════════════════════════════════════════════════════════════╝
%
%  Reference:  Pearce et al. (2014), Eq. (3):
%    v_i(t+1) = φp · δ̂_i(t) + φa · ⟨v̂_j(t)⟩_visible + φn · η̂_i(t)
%
%  δ̂_i  — unit vector toward the nearest boundary of the occluded
%          angular domain.  Computed by summing unit vectors to each
%          boundary of each merged occluded interval.
%
%  ⟨v̂_j⟩_visible  — mean heading of the σ nearest *visible* neighbours
%                     (visibility via angular-interval occlusion).
%
%  η̂_i  — random unit vector (intrinsic noise).
%
%  Θ_i  — internal opacity = (sum of merged interval widths) / 2π.
%
%  Steps (for each bird i):
%    1. Compute angular intervals to all other birds (vectorized O(N)).
%    2. Sort by distance, process closest-first.
%    3. For each bird j: if any segment of its interval is NOT covered
%       by already-merged (closer) intervals, mark j as visible and
%       merge its interval into the occluded set.
%    4. δ̂ from domain boundaries of merged occluded intervals.
%    5. Θ from total occluded angular width.
% ──────────────────────────────────────────────────────────────────────

function [delta, vis_idx, vis_dists, n_vis, theta] = ...
         compute_projection(i, pos, vel)
    % For bird i: angular intervals → visible neighbours → δ̂ → Θ
    global NUM_BOIDS BOID_SIZE

    % ── Step 1: distances & angles to all other birds (vectorized) ──
    diffs  = pos - repmat(pos(i,:), NUM_BOIDS, 1);
    dists  = sqrt(sum(diffs.^2, 2));
    angles = atan2(diffs(:,2), diffs(:,1));

    % Normalise angles to [0, 2π)
    angles(angles < 0) = angles(angles < 0) + 2 * pi;

    % Angular half-width αⱼ = arcsin(min(b / dⱼ, 1))
    half = asin(min(BOID_SIZE ./ dists, 1));

    % ── Step 2: collect & sort by distance (closest-first) ──────────
    %  Build entries matrix: [distance, centre_angle, half_width, bird_index]
    entries = [dists, angles, half, (1:NUM_BOIDS)'];
    entries(i, :) = [];                          % remove self

    % Sort by distance (column 1 ascending)
    [~, sort_idx] = sort(entries(:,1));
    entries = entries(sort_idx, :);
    n_entries = size(entries, 1);

    % ── Step 3: incremental occlusion merge ────────────────────────
    %  For each bird (closest first):
    %    - Build [start, end] segments (handling wrap at 2π)
    %    - Check if any segment is NOT covered by merged intervals
    %    - If visible: record, merge segments into occluded set
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

        % Build 1 or 2 segments (wrap at 0 and 2π)
        segs = zeros(2, 2);
        n_segs = 0;
        if start_j < 0
            n_segs = n_segs + 1; segs(n_segs,:) = [start_j + 2*pi, 2*pi];
            n_segs = n_segs + 1; segs(n_segs,:) = [0, end_j];
        elseif end_j > 2*pi
            n_segs = n_segs + 1; segs(n_segs,:) = [start_j, 2*pi];
            n_segs = n_segs + 1; segs(n_segs,:) = [0, end_j - 2*pi];
        else
            n_segs = n_segs + 1; segs(n_segs,:) = [start_j, end_j];
        end

        % Visibility test: is any segment NOT fully covered?
        is_visible = false;
        for s = 1:n_segs
            covered = false;
            cursor  = segs(s, 1);
            for m = 1:n_merged
                if merged(m,1) <= cursor + 1e-9 && cursor < merged(m,2)
                    cursor = max(cursor, merged(m,2));
                end
                if cursor >= segs(s,2) - 1e-9
                    covered = true;
                    break;
                end
            end
            if ~covered
                is_visible = true;
                break;
            end
        end

        if is_visible
            n_vis = n_vis + 1;
            vis_idx(n_vis)   = bird_j;
            vis_dists(n_vis) = d_j;

            % Add segments to merged and re-merge
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

    % Trim outputs to actual lengths
    vis_idx   = vis_idx(1:n_vis);
    vis_dists = vis_dists(1:n_vis);
    merged    = merged(1:n_merged, :);

    % ── Step 4: δ̂ from domain boundaries ──────────────────────────
    %  Sum unit vectors to each occluded interval boundary.
    %  Fully surrounded (one interval covering all 2π) → δ̂ = 0.
    delta = [0, 0];
    if n_merged == 1 && merged(1,1) < 1e-9 && merged(1,2) > 2*pi - 1e-9
        % Fully surrounded — no projection information
        delta = [0, 0];
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

    % ── Step 5: internal opacity Θ_i ──────────────────────────────
    %  Θ = (total occluded angular width) / 2π
    if n_merged > 0
        occluded = sum(merged(:,2) - merged(:,1));
        theta = min(occluded / (2 * pi), 1.0);
    else
        theta = 0;
    end
end


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 7 — EXTERNAL OPACITY  (Θ')                                  ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  Θ' — fraction of the sky obscured from a distant external observer.
%  The observer is placed at (−2000, HEIGHT/2), far to the left of the
%  flock.  Angular intervals subtended by each bird are merged to find
%  the total occluded angular width.
%
%  Complexity: O(N log N) where N = NUM_BOIDS.
% ──────────────────────────────────────────────────────────────────────

function theta_ext = compute_external_opacity(pos)
    global NUM_BOIDS BOID_SIZE WIDTH HEIGHT

    % Observer far to the left
    viewpoint = [-2000, HEIGHT/2];
    diffs  = pos - repmat(viewpoint, NUM_BOIDS, 1);
    dists  = sqrt(sum(diffs.^2, 2));
    angles = atan2(diffs(:,2), diffs(:,1));
    angles(angles < 0) = angles(angles < 0) + 2 * pi;
    half = asin(min(BOID_SIZE ./ dists, 1));

    % Build angular intervals for all birds
    intervals = zeros(NUM_BOIDS * 2, 2);
    n_int = 0;
    for k = 1:NUM_BOIDS
        s = angles(k) - half(k);
        e = angles(k) + half(k);
        if s < 0
            n_int = n_int + 1; intervals(n_int,:) = [s + 2*pi, 2*pi];
            n_int = n_int + 1; intervals(n_int,:) = [0, e];
        elseif e > 2*pi
            n_int = n_int + 1; intervals(n_int,:) = [s, 2*pi];
            n_int = n_int + 1; intervals(n_int,:) = [0, e - 2*pi];
        else
            n_int = n_int + 1; intervals(n_int,:) = [s, e];
        end
    end
    if n_int == 0
        theta_ext = 0;
    else
        % Sort by start angle, merge overlaps, sum widths
        intervals = intervals(1:n_int, :);
        [~, idx] = sort(intervals(:,1));
        intervals = intervals(idx, :);
        [merged, n_m] = merge_angle_intervals(intervals, n_int);
        occluded = sum(merged(:,2) - merged(:,1));
        theta_ext = min(occluded / (2 * pi), 1.0);
    end
end


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 12 — MAIN LOOP                                             ║
% ╚══════════════════════════════════════════════════════════════════════╝
%  The main simulation loop runs until the figure is closed.  Each frame:
%
%    1. APPLY PENDING CHANGES  — add/remove birds, reset, auto-compute φn
%    2. FLOCKING UPDATE  — per-bird steering forces (projection or spatial)
%    3. PHYSICS UPDATE   — Euler integration, speed clamp, toroidal wrap
%    4. METRICS          — Θ, Θ', α with EMA smoothing
%    5. CSV LOGGING      — append row every LOG_EVERY frames
%    6. RENDER           — update patch vertices, text overlays, help
% ──────────────────────────────────────────────────────────────────────

frame    = 0;
smooth   = 0.05;                         % EMA factor for metrics
theta_ema     = 0;                        % Θ  — mean internal opacity (EMA)
theta_ext_ema = 0;                        % Θ' — external opacity (EMA)
alpha_ema     = 0;                        % α  — order parameter (EMA)

% Triangle vertex offsets (relative to position, rotated by heading)
tip_len  = BOID_SIZE * 2.5;
side_len = BOID_SIZE * 1.5;
side_ang = 2.3;

mode_names = {'PROJECTION  (Pearce et al. 2014)', ...
              'SPATIAL     (topological Reynolds)'};

disp('Running — close the figure window to stop.');
disp('  Keys:  m:mode  p:pause  arrows:phi  []:sigma  +/-:boids  r:reset  h:help');

% ═══════════════════════════════════════════════════════════════════
%  MAIN FRAME LOOP
%  Each iteration processes one simulation frame.
% ═══════════════════════════════════════════════════════════════════
while isgraphics(f)
    t_frame = tic();                       % start frame timer

    % ───────────────────────────────────────────────────────────────
    %  UPDATE  — skipped when paused; otherwise:
    %    1. Apply pending state changes (add/remove/reset, auto φn)
    %    2. Flocking update (compute steering per bird)
    %    3. Physics update (Euler integration, vectorized)
    %    4. Metrics computation (Θ, Θ', α with EMA)
    %    5. CSV logging
    % ───────────────────────────────────────────────────────────────
    if ~paused

        % ╔══════════════════════════════════════════════════════════╗
        % ║  SECTION 9a — AUTO-COMPUTE φn                            ║
        % ╚══════════════════════════════════════════════════════════╝
        %
        %  φn = max(0, 1 − φp − φa)
        %  Guarantees the three model weights always sum to 1.
        %  Re-computed every frame so runtime φp/φa adjustments
        %  take effect immediately.
        % ───────────────────────────────────────────────────────────
        PHI_N = max(0.0, 1.0 - PHI_P - PHI_A);

        % ── 1b. Apply pending boid count changes ──────────────────
        %  Removal: trim matrices from the end (safely leaves ≥ 1 bird)
        if pending_remove > 0
            n_remove = min(pending_remove, NUM_BOIDS - 1);
            if n_remove > 0
                pos        = pos(1:NUM_BOIDS - n_remove, :);
                vel        = vel(1:NUM_BOIDS - n_remove, :);
                acc        = acc(1:NUM_BOIDS - n_remove, :);
                last_theta = last_theta(1:NUM_BOIDS - n_remove);
                NUM_BOIDS  = NUM_BOIDS - n_remove;
                pending_remove = pending_remove - n_remove;
                disp(['Removed ' num2str(n_remove) ' birds, now ' num2str(NUM_BOIDS)]);
            end
        end
        % Addition: append new random birds to each state matrix
        if pending_add > 0
            n_add = pending_add;
            new_pos  = rand(n_add, 2) .* [WIDTH, HEIGHT];
            new_ang  = rand(n_add, 1) * 2 * pi;
            new_vel  = [cos(new_ang), sin(new_ang)] .* (1 + rand(n_add, 1) * (V0 - 1));
            pos        = [pos; new_pos];
            vel        = [vel; new_vel];
            acc        = [acc; zeros(n_add, 2)];
            last_theta = [last_theta; zeros(n_add, 1)];
            NUM_BOIDS  = NUM_BOIDS + n_add;
            pending_add = 0;
            disp(['Added ' num2str(n_add) ' birds, now ' num2str(NUM_BOIDS)]);
        end

        % ╔══════════════════════════════════════════════════════════╗
        % ║  SECTION 9b — RESET LOGIC  (triggered by 'r' key)       ║
        % ╚══════════════════════════════════════════════════════════╝
        %
        %  Reinitialise all state matrices with random positions and
        %  velocities, reset metric EMA accumulators to zero, and
        %  restart the frame counter.
        %
        %  The pending_reset flag is set by the keyboard callback
        %  and applied atomically here in the main loop.
        % ───────────────────────────────────────────────────────────
        if pending_reset
            pos  = rand(NUM_BOIDS, 2) .* [WIDTH, HEIGHT];
            ang  = rand(NUM_BOIDS, 1) * 2 * pi;
            vel  = [cos(ang), sin(ang)] .* (1 + rand(NUM_BOIDS, 1) * (V0 - 1));
            acc  = zeros(NUM_BOIDS, 2);
            last_theta = zeros(NUM_BOIDS, 1);
            theta_ema = 0;  theta_ext_ema = 0;  alpha_ema = 0;
            frame = 0;
            pending_reset = false;
            disp(['Flock reset — ' num2str(NUM_BOIDS) ' birds']);
        end

        % ── 2. Flocking update: compute steering forces ────────────
        %  Per-bird loop dispatches by MODE.
        %  MODE 0 (PROJECTION):  v = φp·δ̂ + φa·⟨v̂⟩_visible + φn·η̂
        %  MODE 1 (SPATIAL):     separation/alignment/cohesion + noise
        if MODE == 0
            % ═══════════════════════════════════════════════════════
            %  MODE 0 — PROJECTION MODEL
            %
            %  For each bird i:
            %    1. compute_projection → δ̂, visible neighbours, Θ
            %    2. Alignment: ⟨v̂⟩ of σ nearest visible neighbours
            %    3. Noise: random unit vector η̂
            %    4. Desired direction: v = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
            %    5. Steering: steer = v_desired − v_current, clamped
            % ═══════════════════════════════════════════════════════
            for i = 1:NUM_BOIDS
                [delta, vis_idx, vis_dists, n_vis, theta] = ...
                    compute_projection(i, pos, vel);
                last_theta(i) = theta;            % cache for metrics

                % ── Alignment: mean velocity of σ nearest visible ──
                align = [0, 0];
                if n_vis > 0
                    sigma_use = min(SIGMA, n_vis);
                    for k = 1:sigma_use
                        j_vis = vis_idx(k);
                        align = align + vel(j_vis, :);
                    end
                    align = align / sigma_use;
                end

                % ── Noise: random unit vector ──────────────────────
                na = rand() * 2 * pi;
                noise = [cos(na), sin(na)];

                % ── Desired direction (Eq. 3 from paper) ───────────
                %  v_desired = φp·δ̂ + φa·⟨v̂⟩ + φn·η̂
                desired = delta * PHI_P;
                if norm(align) > 0.001
                    desired = desired + (align / norm(align)) * PHI_A;
                else
                    % Fallback: use own heading when no visible neighbours
                    if norm(vel(i,:)) > 0.001
                        desired = desired + (vel(i,:) / norm(vel(i,:))) * PHI_A;
                    end
                end
                desired = desired + noise * PHI_N;

                if norm(desired) < 0.001
                    desired = [rand()*2-1, rand()*2-1];
                end
                desired = desired / norm(desired) * V0;

                % ── Reynolds steering: steer = v_desired − v ───────
                steer = desired - vel(i,:);
                if norm(steer) > MAX_FORCE
                    steer = steer / norm(steer) * MAX_FORCE;
                end
                acc(i,:) = acc(i,:) + steer;
            end

        else
            % ╔══════════════════════════════════════════════════════╗
            % ║  SECTION 6 — SPATIAL MODEL  (MODE 1)               ║
            % ╚══════════════════════════════════════════════════════╝
            %
            %  Reference:  Reynolds, C. W. (1987)
            %    "Flocks, Herds, and Schools: A Distributed Behavioral Model"
            %    SIGGRAPH '87, DOI: 10.1145/37401.37406
            %
            %  Classic three-rule boids with topological neighbour selection.
            %  Full O(N²) pairwise distance matrix (vectorized).
            %  For each bird i:
            %    1. Find σ nearest neighbours within VISUAL_RANGE
            %    2. Separation: steer away from very close neighbours
            %    3. Alignment: steer toward mean neighbour heading
            %    4. Cohesion: steer toward mean neighbour position
            %    5. Weighted force accumulation + noise
            %
            %  Weights repurposed from the projection model:
            %    φp → separation (× 2.0)
            %    φa → alignment  (× 1.2)
            %    φn → cohesion   (× 1.5)
            % ═══════════════════════════════════════════════════════

            % Pairwise distance matrix  (N × N, vectorized)
            dx = repmat(pos(:,1), 1, NUM_BOIDS) - repmat(pos(:,1)', NUM_BOIDS, 1);
            dy = repmat(pos(:,2), 1, NUM_BOIDS) - repmat(pos(:,2)', NUM_BOIDS, 1);
            dist_mat = sqrt(dx.^2 + dy.^2);

            for i = 1:NUM_BOIDS
                row   = dist_mat(i, :);
                row(i)= Inf;                        % exclude self
                in_range = find(row < VISUAL_RANGE);

                sep = [0, 0];                        % separation steering
                ali = [0, 0];                        % alignment steering
                coh = [0, 0];                        % cohesion steering

                if ~isempty(in_range)
                    range_dists = row(in_range);
                    [~, sort_idx] = sort(range_dists);
                    sigma_use = min(SIGMA, length(in_range));
                    nbs = in_range(sort_idx(1:sigma_use));  % σ nearest

                    % ── Accumulate neighbour contributions ────────
                    for k = 1:sigma_use
                        j = nbs(k);
                        d_ij = dist_mat(i, j);
                        ali = ali + vel(j, :);           % sum velocities
                        coh = coh + pos(j, :);           % sum positions
                        if d_ij < VISUAL_RANGE * 0.3 && d_ij > 0.001
                            diff_ij = pos(i,:) - pos(j,:);
                            sep = sep + diff_ij / d_ij;   % weight ∝ 1/distance
                        end
                    end

                    ali = ali / sigma_use;
                    coh = coh / sigma_use;

                    % ── Alignment steering ────────────────────────
                    if norm(ali) > 0.001, ali = ali / norm(ali) * V0; end
                    ali = ali - vel(i,:);
                    if norm(ali) > MAX_FORCE, ali = ali / norm(ali) * MAX_FORCE; end

                    % ── Cohesion steering ─────────────────────────
                    coh = coh - pos(i,:);
                    if norm(coh) > 0.001, coh = coh / norm(coh) * V0; end
                    coh = coh - vel(i,:);
                    if norm(coh) > MAX_FORCE, coh = coh / norm(coh) * MAX_FORCE; end

                    % ── Separation steering ───────────────────────
                    if norm(sep) > 0.001, sep = sep / norm(sep) * V0; end
                    sep = sep - vel(i,:);
                    if norm(sep) > MAX_FORCE, sep = sep / norm(sep) * MAX_FORCE; end
                end

                % ── Noise for exploration ─────────────────────────
                na = rand() * 2 * pi;
                noise = [cos(na), sin(na)] * MAX_FORCE * 0.8;

                % ── Weighted force accumulation ───────────────────
                acc(i,:) = acc(i,:) + sep * PHI_P * 2.0;
                acc(i,:) = acc(i,:) + ali * PHI_A * 1.2;
                acc(i,:) = acc(i,:) + coh * PHI_N * 1.5;
                acc(i,:) = acc(i,:) + noise;
            end
        end

        % ╔══════════════════════════════════════════════════════════╗
        % ║  SECTION 9 — PHYSICS UPDATE  (shared by both modes)      ║
        % ╚══════════════════════════════════════════════════════════╝
        %
        %  Euler integration with speed clamping and toroidal wrap.
        %  This is the same physics step regardless of flocking mode:
        %
        %    1. v ← v + a          apply accumulated steering force
        %    2. |v| clamped to [0.3·V₀, V₀]
        %       - cap at V₀ (max cruising speed)
        %       - floor at 0.3·V₀ (prevent stagnation)
        %    3. p ← p + v          move forward
        %    4. toroidal wrap      re-enter from opposite edge via mod()
        %    5. a ← 0              reset steering accumulator
        %
        %  Complexity: O(N) — fully vectorized over all birds.
        % ───────────────────────────────────────────────────────────
        vel = vel + acc;
        spd = sqrt(sum(vel.^2, 2));

        % Speed clamp: [0.3·V₀, V₀]
        fast = find(spd > V0);
        if ~isempty(fast)
            vel(fast,:) = vel(fast,:) ./ repmat(spd(fast), 1, 2) * V0;
        end
        slow = find(spd < V0 * 0.3);
        if ~isempty(slow)
            for s = slow'
                if spd(s) > 0.001
                    vel(s,:) = vel(s,:) / spd(s) * V0 * 0.3;
                else
                    na = rand() * 2 * pi;
                    vel(s,:) = [cos(na), sin(na)] * V0 * 0.3;
                end
            end
        end

        pos = pos + vel;
        acc = acc * 0;

        % Toroidal wrap
        pos(:,1) = mod(pos(:,1), WIDTH);
        pos(:,2) = mod(pos(:,2), HEIGHT);

        % ╔══════════════════════════════════════════════════════════╗
        % ║  SECTION 8 — METRICS COMPUTATION                        ║
        % ╚══════════════════════════════════════════════════════════╝
        %  Θ  (internal opacity) — exact in PROJECTION mode, sampled
        %       (5 birds) in SPATIAL mode to avoid O(N²) cost.
        %  Θ' (external opacity) — O(N log N) angular interval merge
        %       from distant observer at (−2000, HEIGHT/2).
        %  α  (order parameter) — |Σv_i| / (N·v₀).  α ≈ 1 = aligned.
        %  All metrics use EMA smoothing: x ← x + (x_raw − x) × s.

        if MODE == 0
            % PROJECTION: Θ already cached as last_theta(i)
            theta_raw = mean(last_theta);
        else
            % SPATIAL: sample 5 random birds for Θ estimate
            sample_n = min(5, NUM_BOIDS);
            sample_idx = randperm(NUM_BOIDS, sample_n);
            theta_sum = 0;
            for s = 1:sample_n
                [~, ~, ~, ~, theta_sample] = ...
                    compute_projection(sample_idx(s), pos, vel);
                theta_sum = theta_sum + theta_sample;
            end
            theta_raw = theta_sum / sample_n;
        end
        theta_ema = theta_ema + (theta_raw - theta_ema) * smooth;

        theta_ext_raw = compute_external_opacity(pos);
        theta_ext_ema = theta_ext_ema + (theta_ext_raw - theta_ext_ema) * smooth;

        total_vel = sum(vel, 1);                     % Σ v_i
        alpha_raw = norm(total_vel) / (NUM_BOIDS * V0);  % |Σv|/(N·v₀)
        alpha_ema = alpha_ema + (alpha_raw - alpha_ema) * smooth;

        % ── 5. CSV logging  (every LOG_EVERY frames) ─────────────
        if log_fid ~= -1 && mod(frame, LOG_EVERY) == 0
            fps = 1 / max(toc(t_frame), 0.001);
            fprintf(log_fid, '%d,%d,%d,%.4f,%.4f,%.4f,%d,%.4f,%.4f,%.4f,%.1f\n', ...
                    frame, MODE, NUM_BOIDS, PHI_P, PHI_A, PHI_N, SIGMA, ...
                    theta_ema, theta_ext_ema, alpha_ema, fps);
        end

    end  % ~paused

    % ───────────────────────────────────────────────────────────────
    %  RENDER  — update graphics handles (no delete/recreate)
    %    1. Bird triangles (3×N matrices for patch)
    %    2. Metrics text overlays
    %    3. Mode badge
    %    4. Pause indicator
    %    5. Help overlay
    % ───────────────────────────────────────────────────────────────

    % ── Bird triangle vertices ────────────────────────────────────
    %  Each bird: 3 vertices forming a triangle pointing in heading dir.
    dirs = atan2(vel(:,2), vel(:,1));               % headings (radians)

    tip_x = pos(:,1)' + cos(dirs)' * tip_len;
    tip_y = pos(:,2)' + sin(dirs)' * tip_len;
    lft_x = pos(:,1)' + cos(dirs + side_ang)' * side_len;
    lft_y = pos(:,2)' + sin(dirs + side_ang)' * side_len;
    rgt_x = pos(:,1)' + cos(dirs - side_ang)' * side_len;
    rgt_y = pos(:,2)' + sin(dirs - side_ang)' * side_len;

    X = [tip_x; lft_x; rgt_x];   % 3 × N  (one column per triangle)
    Y = [tip_y; lft_y; rgt_y];   % 3 × N

    % Mode-dependent colour: cool blue-white vs warm amber
    if MODE == 0
        bird_color = [200 210 230] / 255;
    else
        bird_color = [230 200 160] / 255;
    end
    set(hBoids, 'XData', X, 'YData', Y, 'FaceColor', bird_color);

    % ── Metrics text overlay ──────────────────────────────────────
    fps = 1 / max(toc(t_frame), 0.001);
    set(hTextFPS,    'String', sprintf('FPS: %.0f    Boids: %d    Frame: %d', ...
                                        fps, NUM_BOIDS, frame));
    set(hTextParams, 'String', sprintf('phi_p=%.3f  phi_a=%.3f  phi_n=%.3f  sigma=%d', ...
                                        PHI_P, PHI_A, PHI_N, SIGMA));

    if MODE == 0
        set(hTextTheta, 'String', sprintf('Opacity  Theta  = %.3f', theta_ema));
    else
        set(hTextTheta, 'String', sprintf('Opacity  Theta  ~ %.3f  (sampled)', theta_ema));
    end
    set(hTextExt,   'String', sprintf('          Theta'' = %.3f', theta_ext_ema));
    set(hTextAlpha, 'String', sprintf('Order alpha = %.3f', alpha_ema));

    % ── Mode badge (top-right) ────────────────────────────────────
    set(hTextBadge, 'String', mode_names{MODE + 1});

    % ── Pause indicator ───────────────────────────────────────────
    if paused
        set(hTextPause, 'String', 'PAUSED', 'Visible', 'on');
    else
        set(hTextPause, 'Visible', 'off');
    end

    % ── Help overlay ──────────────────────────────────────────────
    if show_help
        set(hHelp, 'Visible', 'on');
    else
        set(hHelp, 'Visible', 'off');
    end

    % Yield CPU so the event queue processes key presses
    pause(0.001);

    frame = frame + 1;

end  % while isgraphics(f)


% ╔══════════════════════════════════════════════════════════════════════╗
% ║  SECTION 13 — SHUTDOWN                                              ║
% ╚══════════════════════════════════════════════════════════════════════╝

if log_fid ~= -1
    fclose(log_fid);
    disp(['Metrics saved to ' LOG_FILE]);
end
disp(['Simulation ended after ' num2str(frame) ' frames.']);
disp('Run again to restart.');
% =======================================================================
