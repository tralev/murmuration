% test_key_handler.m  — exercises the full key_handler function from alg2.m
% Run: octave --no-gui test_key_handler.m
% Defines the key_handler function, simulates keypresses (b, m, p, h, r,
% arrows, brackets, +/-), and prints the state of every toggled global.

global NUM_BOIDS BOID_SIZE WIDTH HEIGHT VISUAL_RANGE
global MODE paused PHI_P PHI_A PHI_N SIGMA
global pending_add pending_remove pending_reset show_help
global MARGIN_BOUNDARY BOUNDARY_MARGIN BOUNDARY_TURN_FACTOR

% ── Initialise all globals to their defaults ───────────────────────
NUM_BOIDS    = 100;
BOID_SIZE    = 3;
WIDTH        = 1000;
HEIGHT       = 700;
VISUAL_RANGE = 70;
MODE         = 0;
paused       = false;
PHI_P        = 0.03;
PHI_A        = 0.80;
PHI_N        = 0.17;
SIGMA        = 4;
pending_add    = 0;
pending_remove = 0;
pending_reset  = false;
show_help      = false;
MARGIN_BOUNDARY      = false;
BOUNDARY_MARGIN      = 200;
BOUNDARY_TURN_FACTOR = 1;

% ═══════════════════════════════════════════════════════════════════
%  key_handler function — EXACT copy from alg2.m § SECTION 11
% ═══════════════════════════════════════════════════════════════════

function key_handler(src, event)
    global MODE paused PHI_P PHI_A SIGMA
    global pending_add pending_remove pending_reset show_help
    global MARGIN_BOUNDARY

    switch event.Key
        case {'m', 'M'}
            MODE = 1 - MODE;
            if MODE == 0, disp('PROJECTION mode');
            else,         disp('SPATIAL mode'); end

        case {'b', 'B'}
            MARGIN_BOUNDARY = ~MARGIN_BOUNDARY;
            if MARGIN_BOUNDARY, disp('MARGIN boundary');
            else,               disp('TOROIDAL wrap'); end

        case {'p', 'P'}
            paused = ~paused;
            if paused, disp('Paused'); else, disp('Resumed'); end

        case 'uparrow'
            PHI_P = min(1.0, PHI_P + 0.01);
            disp(['phi_p = ' num2str(PHI_P)]);
        case 'downarrow'
            PHI_P = max(0.0, PHI_P - 0.01);
            disp(['phi_p = ' num2str(PHI_P)]);

        case 'leftarrow'
            PHI_A = max(0.0, PHI_A - 0.01);
            disp(['phi_a = ' num2str(PHI_A)]);
        case 'rightarrow'
            PHI_A = min(1.0, PHI_A + 0.01);
            disp(['phi_a = ' num2str(PHI_A)]);

        case 'leftbracket'
            SIGMA = max(1, SIGMA - 1);
            disp(['sigma = ' num2str(SIGMA)]);
        case 'rightbracket'
            SIGMA = min(50, SIGMA + 1);
            disp(['sigma = ' num2str(SIGMA)]);

        case {'add', 'equal'}
            pending_add = min(pending_add + 10, 200);
            disp('Adding 10 birds (pending)');
        case {'subtract', 'hyphen'}
            pending_remove = pending_remove + 10;
            disp('Removing 10 birds (pending)');

        case {'r', 'R'}
            pending_reset = true;
            disp('Resetting flock...');

        case {'h', 'H'}
            show_help = ~show_help;
            if show_help, disp('Help ON'); else, disp('Help OFF'); end

        % ── Scenario presets  (1-5, 6-0, s, l, i, v, k, q) ────────
        case {'1'}
            PHI_P = 0.00; PHI_A = 0.95; SIGMA = 8; MODE = 0;
            disp('PRESET 1 — Pure Alignment');
        case {'2'}
            PHI_P = 0.10; PHI_A = 0.20; SIGMA = 2; MODE = 0;
            disp('PRESET 2 — Gas / Exploration');
        case {'3'}
            PHI_P = 0.03; PHI_A = 0.80; SIGMA = 4; MODE = 0;
            disp('PRESET 3 — Pearce Default');
        case {'4'}
            PHI_P = 0.15; PHI_A = 0.70; SIGMA = 6; MODE = 0;
            disp('PRESET 4 — Dense Ball');
        case {'5'}
            PHI_P = 0.30; PHI_A = 0.50; SIGMA = 4; MODE = 1;
            disp('PRESET 5 — Classic Boids (SPATIAL)');
        case {'6'}
            PHI_P = 0.08; PHI_A = 0.82; SIGMA = 8; MODE = 0;
            disp('PRESET 6 — Quiet Roost');
        case {'7'}
            PHI_P = 0.04; PHI_A = 0.88; SIGMA = 5; MODE = 0;
            disp('PRESET 7 — Comfort Flight');
        case {'8'}
            PHI_P = 0.02; PHI_A = 0.85; SIGMA = 3; MODE = 0;
            disp('PRESET 8 — Acro Swarm');
        case {'9'}
            PHI_P = 0.30; PHI_A = 0.55; SIGMA = 8; MODE = 1;
            disp('PRESET 9 — Predator Ripple (SPATIAL)');
        case {'0'}
            PHI_P = 0.20; PHI_A = 0.72; SIGMA = 10; MODE = 1;
            disp('PRESET 0 — Storm Turn (SPATIAL)');
        case {'s', 'S'}
            PHI_P = 0.05; PHI_A = 0.85; SIGMA = 6; MODE = 0;
            disp('PRESET s — Swarm Pilot');
        case {'l', 'L'}
            PHI_P = 0.12; PHI_A = 0.65; SIGMA = 7; MODE = 0;
            disp('PRESET l — Lava Lamp');
        case {'i', 'I'}
            PHI_P = 0.02; PHI_A = 0.40; SIGMA = 2; MODE = 0;
            disp('PRESET i — Ink Cloud');
        case {'v', 'V'}
            PHI_P = 0.35; PHI_A = 0.60; SIGMA = 9; MODE = 1;
            disp('PRESET v — Vacuole (SPATIAL)');
        case {'k', 'K'}
            PHI_P = 0.02; PHI_A = 0.92; SIGMA = 6; MODE = 0;
            disp('PRESET k — Silk Sheet');
        case {'q', 'Q'}
            PHI_P = 0.20; PHI_A = 0.55; SIGMA = 10; MODE = 1;
            disp('PRESET q — Quest 2 Dense (SPATIAL)');
    end
end

% ═══════════════════════════════════════════════════════════════════
%  TEST RUNNER — simulate key presses and print state after each
% ═══════════════════════════════════════════════════════════════════

% Helper: create a fake event struct with a .Key field
function ev = make_event(key_str)
    ev = struct('Key', key_str);
end

% ── T1: Initial state ─────────────────────────────────────────────
fprintf('T1_MARGIN=%d\n', MARGIN_BOUNDARY);
fprintf('T1_MODE=%d\n', MODE);
fprintf('T1_PAUSED=%d\n', paused);
fprintf('T1_HELP=%d\n', show_help);
fprintf('T1_PHIP=%.2f\n', PHI_P);
fprintf('T1_PHIA=%.2f\n', PHI_A);
fprintf('T1_SIGMA=%d\n', SIGMA);
fprintf('T1_PENDADD=%d\n', pending_add);
fprintf('T1_PENDRMV=%d\n', pending_remove);
fprintf('T1_RESET=%d\n', pending_reset);

% ── T2: Press 'b' — toggle MARGIN_BOUNDARY false→true ─────────────
key_handler(0, make_event('b'));
fprintf('T2_MARGIN=%d\n', MARGIN_BOUNDARY);
fprintf('T2_MODE=%d\n', MODE);          % unchanged
fprintf('T2_PAUSED=%d\n', paused);       % unchanged

% ── T3: Press 'm' — toggle MODE 0→1 ───────────────────────────────
key_handler(0, make_event('m'));
fprintf('T3_MARGIN=%d\n', MARGIN_BOUNDARY);  % still 1
fprintf('T3_MODE=%d\n', MODE);

% ── T4: Press 'p' — toggle paused false→true ──────────────────────
key_handler(0, make_event('p'));
fprintf('T4_MODE=%d\n', MODE);           % still 1
fprintf('T4_PAUSED=%d\n', paused);
fprintf('T4_MARGIN=%d\n', MARGIN_BOUNDARY);  % still 1

% ── T5: Press 'h' — toggle show_help false→true ───────────────────
key_handler(0, make_event('h'));
fprintf('T5_HELP=%d\n', show_help);
fprintf('T5_PAUSED=%d\n', paused);       % still 1

% ── T6: Press 'B' (uppercase) — toggle MARGIN_BOUNDARY true→false ─
key_handler(0, make_event('B'));
fprintf('T6_MARGIN=%d\n', MARGIN_BOUNDARY);
fprintf('T6_MODE=%d\n', MODE);           % still 1

% ── T7: Press 'M' — toggle MODE 1→0 ───────────────────────────────
key_handler(0, make_event('M'));
fprintf('T7_MODE=%d\n', MODE);
fprintf('T7_MARGIN=%d\n', MARGIN_BOUNDARY);  % still 0

% ── T8: Press 'p' again — toggle paused true→false ────────────────
key_handler(0, make_event('p'));
fprintf('T8_PAUSED=%d\n', paused);
fprintf('T8_HELP=%d\n', show_help);      % still 1

% ── T9: Press 'h' again — toggle show_help true→false ─────────────
key_handler(0, make_event('h'));
fprintf('T9_HELP=%d\n', show_help);

% ── T10: Press ']' — SIGMA 4→5 ────────────────────────────────────
key_handler(0, make_event('rightbracket'));
fprintf('T10_SIGMA=%d\n', SIGMA);

% ── T11: Press 'uparrow' — PHI_P 0.03→0.04 ────────────────────────
key_handler(0, make_event('uparrow'));
fprintf('T11_PHIP=%.2f\n', PHI_P);

% ── T12: Press 'leftarrow' — PHI_A 0.80→0.79 ──────────────────────
key_handler(0, make_event('leftarrow'));
fprintf('T12_PHIA=%.2f\n', PHI_A);

% ── T13: Press '=' (equal) — pending_add 0→10 ─────────────────────
key_handler(0, make_event('equal'));
fprintf('T13_PENDADD=%d\n', pending_add);

% ── T14: Press '-' — pending_remove 0→10 ──────────────────────────
key_handler(0, make_event('hyphen'));
fprintf('T14_PENDRMV=%d\n', pending_remove);

% ── T15: Press 'r' — pending_reset false→true ─────────────────────
key_handler(0, make_event('r'));
fprintf('T15_RESET=%d\n', pending_reset);

% ── T16: Press multiple times: '=' again, ']' again, '[' ──────────
key_handler(0, make_event('equal'));          % pending_add 10→20
key_handler(0, make_event('equal'));          % pending_add 20→30
fprintf('T16_PENDADD=%d\n', pending_add);

key_handler(0, make_event('rightbracket'));   % SIGMA 5→6
key_handler(0, make_event('rightbracket'));   % SIGMA 6→7
fprintf('T16_SIGMA=%d\n', SIGMA);

key_handler(0, make_event('leftbracket'));    % SIGMA 7→6
fprintf('T16_SIGMABACK=%d\n', SIGMA);

% ── T17: Press 'downarrow' — PHI_P 0.04→0.03 ─────────────────────
key_handler(0, make_event('downarrow'));
fprintf('T17_PHIP=%.2f\n', PHI_P);

% ── T18: Press 'rightarrow' — PHI_A 0.79→0.80 ────────────────────
key_handler(0, make_event('rightarrow'));
fprintf('T18_PHIA=%.2f\n', PHI_A);

% ── Verify independent toggles don't cross-contaminate ────────────
fprintf('T19_MARGIN=%d\n', MARGIN_BOUNDARY);   % still 0
fprintf('T19_MODE=%d\n', MODE);                 % still 0
fprintf('T19_PAUSED=%d\n', paused);             % still 0
fprintf('T19_HELP=%d\n', show_help);            % still 0

% ── T20: Unrecognized key 'x' — all globals unchanged ─────────────
%  Capture state BEFORE sending the key
margin_before = MARGIN_BOUNDARY;
mode_before = MODE;
paused_before = paused;
help_before = show_help;
phip_before = PHI_P;
phia_before = PHI_A;
sigma_before = SIGMA;
add_before = pending_add;
rmv_before = pending_remove;
reset_before = pending_reset;

key_handler(0, make_event('x'));

fprintf('T20_MARGIN_UNCHANGED=%d\n', MARGIN_BOUNDARY == margin_before);
fprintf('T20_MODE_UNCHANGED=%d\n', MODE == mode_before);
fprintf('T20_PAUSED_UNCHANGED=%d\n', paused == paused_before);
fprintf('T20_HELP_UNCHANGED=%d\n', show_help == help_before);
fprintf('T20_PHIP_UNCHANGED=%d\n', abs(PHI_P - phip_before) < 0.001);
fprintf('T20_PHIA_UNCHANGED=%d\n', abs(PHI_A - phia_before) < 0.001);
fprintf('T20_SIGMA_UNCHANGED=%d\n', SIGMA == sigma_before);
fprintf('T20_PENDADD_UNCHANGED=%d\n', pending_add == add_before);
fprintf('T20_PENDRMV_UNCHANGED=%d\n', pending_remove == rmv_before);
fprintf('T20_RESET_UNCHANGED=%d\n', pending_reset == reset_before);

% ── T21: Unrecognized key 'z' — all globals unchanged ─────────────
key_handler(0, make_event('z'));

fprintf('T21_MARGIN_UNCHANGED=%d\n', MARGIN_BOUNDARY == margin_before);
fprintf('T21_MODE_UNCHANGED=%d\n', MODE == mode_before);
fprintf('T21_PAUSED_UNCHANGED=%d\n', paused == paused_before);
fprintf('T21_HELP_UNCHANGED=%d\n', show_help == help_before);
fprintf('T21_PHIP_UNCHANGED=%d\n', abs(PHI_P - phip_before) < 0.001);
fprintf('T21_PHIA_UNCHANGED=%d\n', abs(PHI_A - phia_before) < 0.001);
fprintf('T21_SIGMA_UNCHANGED=%d\n', SIGMA == sigma_before);
fprintf('T21_PENDADD_UNCHANGED=%d\n', pending_add == add_before);
fprintf('T21_PENDRMV_UNCHANGED=%d\n', pending_remove == rmv_before);
fprintf('T21_RESET_UNCHANGED=%d\n', pending_reset == reset_before);

% ═══════════════════════════════════════════════════════════════════
%  CLAMPING LIMIT TESTS
% ═══════════════════════════════════════════════════════════════════
%  Verify that key_handler enforces min/max caps on continuous values.

% ── T22: PHI_P floor at 0.0  (current PHI_P = 0.03) ──────────────
%  Press downarrow 5 times: 0.03→0.02→0.01→0.00→0.00 (clamped)→0.00
for i = 1:5
    key_handler(0, make_event('downarrow'));
end
fprintf('T22_PHIP=%.2f\n', PHI_P);  % should be 0.00 (clamped)
fprintf('T22_PHIP_AT_FLOOR=%d\n', PHI_P == 0.0);

% ── T23: PHI_A ceiling at 1.0  (current PHI_A = 0.80) ───────────
%  Press rightarrow 22 times: 0.80→...→1.00→1.00 (clamped)
for i = 1:22
    key_handler(0, make_event('rightarrow'));
end
fprintf('T23_PHIA=%.2f\n', PHI_A);  % should be 1.00 (clamped)
fprintf('T23_PHIA_AT_CEILING=%d\n', PHI_A == 1.0);

% ── T24: PHI_A floor at 0.0  (current PHI_A = 1.00) ──────────────
%  Press leftarrow 102 times: should bottom out at 0.00
for i = 1:102
    key_handler(0, make_event('leftarrow'));
end
fprintf('T24_PHIA=%.2f\n', PHI_A);  % should be 0.00
fprintf('T24_PHIA_AT_FLOOR=%d\n', PHI_A == 0.0);

% ── T25: SIGMA ceiling at 50  (current SIGMA = 6 after T16) ──────
%  Press ] 50 times: 6→...→50→50 (clamped)
for i = 1:50
    key_handler(0, make_event('rightbracket'));
end
fprintf('T25_SIGMA=%d\n', SIGMA);  % should be 50
fprintf('T25_SIGMA_AT_CEILING=%d\n', SIGMA == 50);

% ── T26: SIGMA floor at 1  (current SIGMA = 50) ──────────────────
%  Press [ 55 times: 50→...→1→1 (clamped)
for i = 1:55
    key_handler(0, make_event('leftbracket'));
end
fprintf('T26_SIGMA=%d\n', SIGMA);  % should be 1
fprintf('T26_SIGMA_AT_FLOOR=%d\n', SIGMA == 1);

% ── T27: pending_add ceiling at 200  (current pending_add = 30) ───
%  Press = 20 times: 30→40→...→200→200 (clamped at ≤200)
for i = 1:20
    key_handler(0, make_event('equal'));
end
fprintf('T27_PENDADD=%d\n', pending_add);  % should be 200
fprintf('T27_PENDADD_AT_CEILING=%d\n', pending_add == 200);

% ── T28: pending_remove has NO cap — grows unbounded ──────────────
%  pending_remove starts at 10 (from T14).  Each '-' press adds 10.
%  100 presses → 10 + 1000 = 1010.  Verifies no max() guard like pending_add.
for i = 1:100
    key_handler(0, make_event('hyphen'));
end
fprintf('T28_PENDRMV=%d\n', pending_remove);  % should be 1010 (uncapped)
fprintf('T28_PENDRMV_UNBOUNDED=%d\n', pending_remove > 200);

% ── T29: PHI_P ceiling at 1.0  (current PHI_P = 0.00 after T22) ─
%  Press uparrow 102 times: 0.00→...→1.00→1.00 (clamped)
for i = 1:102
    key_handler(0, make_event('uparrow'));
end
fprintf('T29_PHIP=%.2f\n', PHI_P);  % should be 1.00 (clamped)
fprintf('T29_PHIP_AT_CEILING=%d\n', PHI_P == 1.0);

% ── T30: Empty-key boundary case (ibut=0 analogue) ────────────────
%  Octave's key_handler uses event.Key dispatch, not ibut.
%  Calling with an empty-string Key tests the switch-case default
%  path — analogous to ibut=0 for the Scilab handler.
%  All globals must remain unchanged.

margin_before30 = MARGIN_BOUNDARY;
mode_before30   = MODE;
paused_before30 = paused;
help_before30   = show_help;
phip_before30   = PHI_P;
phia_before30   = PHI_A;
sigma_before30  = SIGMA;
add_before30    = pending_add;
rmv_before30    = pending_remove;
reset_before30  = pending_reset;

key_handler(0, make_event(''));

fprintf('T30_MARGIN_UNCHANGED=%d\n', MARGIN_BOUNDARY == margin_before30);
fprintf('T30_MODE_UNCHANGED=%d\n', MODE == mode_before30);
fprintf('T30_PAUSED_UNCHANGED=%d\n', paused == paused_before30);
fprintf('T30_HELP_UNCHANGED=%d\n', show_help == help_before30);
fprintf('T30_PHIP_UNCHANGED=%d\n', abs(PHI_P - phip_before30) < 0.001);
fprintf('T30_PHIA_UNCHANGED=%d\n', abs(PHI_A - phia_before30) < 0.001);
fprintf('T30_SIGMA_UNCHANGED=%d\n', SIGMA == sigma_before30);
fprintf('T30_PENDADD_UNCHANGED=%d\n', pending_add == add_before30);
fprintf('T30_PENDRMV_UNCHANGED=%d\n', pending_remove == rmv_before30);
fprintf('T30_RESET_UNCHANGED=%d\n', pending_reset == reset_before30);

% ═══════════════════════════════════════════════════════════════════
%  PRESET KEY TESTS
% ═══════════════════════════════════════════════════════════════════

% ── T32: Press '3' — Pearce Default (restore canonical params) ────
key_handler(0, make_event('3'));
fprintf('T32_PHIP=%.2f\n', PHI_P);
fprintf('T32_PHIA=%.2f\n', PHI_A);
fprintf('T32_SIGMA=%d\n', SIGMA);
fprintf('T32_MODE=%d\n', MODE);

% ── T33: Press '5' — Classic Boids (SPATIAL) ─────────────────────
key_handler(0, make_event('5'));
fprintf('T33_PHIP=%.2f\n', PHI_P);
fprintf('T33_PHIA=%.2f\n', PHI_A);
fprintf('T33_SIGMA=%d\n', SIGMA);
fprintf('T33_MODE=%d\n', MODE);

% ── T34: Press 's' — Swarm Pilot (letter key) ────────────────────
key_handler(0, make_event('s'));
fprintf('T34_PHIP=%.2f\n', PHI_P);
fprintf('T34_PHIA=%.2f\n', PHI_A);
fprintf('T34_SIGMA=%d\n', SIGMA);
fprintf('T34_MODE=%d\n', MODE);

% ── T35: Press '0' — Storm Turn (SPATIAL, zero key) ──────────────
key_handler(0, make_event('0'));
fprintf('T35_PHIP=%.2f\n', PHI_P);
fprintf('T35_PHIA=%.2f\n', PHI_A);
fprintf('T35_SIGMA=%d\n', SIGMA);
fprintf('T35_MODE=%d\n', MODE);

% ── T36: Press '1' — Pure Alignment ──────────────────────────────
key_handler(0, make_event('1'));
fprintf('T36_PHIP=%.2f\n', PHI_P);
fprintf('T36_PHIA=%.2f\n', PHI_A);
fprintf('T36_SIGMA=%d\n', SIGMA);
fprintf('T36_MODE=%d\n', MODE);

% ── T37: Press 'S' (uppercase) — same preset as 's' ──────────────
key_handler(0, make_event('S'));
fprintf('T37_PHIP=%.2f\n', PHI_P);
fprintf('T37_PHIA=%.2f\n', PHI_A);
fprintf('T37_SIGMA=%d\n', SIGMA);
fprintf('T37_MODE=%d\n', MODE);
