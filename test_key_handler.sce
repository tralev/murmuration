// test_key_handler.sce  — exercises the full key_handler from alg2.sce
// Run: scilab-cli -nb -f test_key_handler.sce
// Defines the key_handler function, simulates keypresses via ASCII codes
// (b=98, m=109, p=112, h=104, r=114, arrows, brackets, +/-), and prints
// the state of every toggled global.

global MODE paused PHI_P PHI_A SIGMA pending_add pending_remove pending_reset show_help MARGIN_BOUNDARY

// ── Initialise all globals to their defaults ───────────────────────
MODE         = 0;
paused       = %f;
PHI_P        = 0.03;
PHI_A        = 0.80;
PHI_N        = 0.17;
SIGMA        = 4;
pending_add    = 0;
pending_remove = 0;
pending_reset  = %f;
show_help      = %f;
MARGIN_BOUNDARY = %f;

// ═══════════════════════════════════════════════════════════════════
//  key_handler function — EXACT copy from alg2.sce § SECTION 11
// ═══════════════════════════════════════════════════════════════════

function key_handler(win_id, x, y, ibut)
    global MODE paused PHI_P PHI_A SIGMA pending_add pending_remove pending_reset show_help MARGIN_BOUNDARY
    if ibut < 0 then
        k = abs(ibut);

        // ── Mode toggle: m / M (109, 77) ────────────────────────
        if k == 109 | k == 77 then
            MODE = 1 - MODE;
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
            disp("phi_p = " + string(PHI_P));
        elseif k == 40 | k == 65364 then
            PHI_P = max(0.0, PHI_P - 0.01);
            disp("phi_p = " + string(PHI_P));

        // ── φa  left/right  (Win: 37/39  Linux: 65361/65363) ──
        elseif k == 37 | k == 65361 then
            PHI_A = max(0.0, PHI_A - 0.01);
            disp("phi_a = " + string(PHI_A));
        elseif k == 39 | k == 65363 then
            PHI_A = min(1.0, PHI_A + 0.01);
            disp("phi_a = " + string(PHI_A));

        // ── σ  brackets  [ = 91,  ] = 93 ────────────────────────
        elseif k == 91 then
            SIGMA = max(1, SIGMA - 1);
            disp("sigma = " + string(SIGMA));
        elseif k == 93 then
            SIGMA = min(50, SIGMA + 1);
            disp("sigma = " + string(SIGMA));

        // ── Boid count  + = 43,  = = 61,  - = 45 ───────────────
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

        // ── Scenario presets  (1-5, 6-0, s, l, i, v, k, q) ──────
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


// ═══════════════════════════════════════════════════════════════════
//  TEST RUNNER — call key_handler with negative ASCII codes
// ═══════════════════════════════════════════════════════════════════
//  ibut must be negative for keyboard events: ibut = -ascii_code

// ── T1: Initial state ─────────────────────────────────────────────
mprintf("T1_MARGIN=%d\n", MARGIN_BOUNDARY);
mprintf("T1_MODE=%d\n", MODE);
mprintf("T1_PAUSED=%d\n", paused);
mprintf("T1_HELP=%d\n", show_help);
mprintf("T1_PHIP=%.2f\n", PHI_P);
mprintf("T1_PHIA=%.2f\n", PHI_A);
mprintf("T1_SIGMA=%d\n", SIGMA);
mprintf("T1_PENDADD=%d\n", pending_add);
mprintf("T1_PENDRMV=%d\n", pending_remove);
mprintf("T1_RESET=%d\n", pending_reset);

// ── T2: Press 'b' (98) — toggle MARGIN_BOUNDARY false→true ────────
key_handler(0, 0, 0, -98);
mprintf("T2_MARGIN=%d\n", MARGIN_BOUNDARY);
mprintf("T2_MODE=%d\n", MODE);          // unchanged
mprintf("T2_PAUSED=%d\n", paused);       // unchanged

// ── T3: Press 'm' (109) — toggle MODE 0→1 ────────────────────────
key_handler(0, 0, 0, -109);
mprintf("T3_MARGIN=%d\n", MARGIN_BOUNDARY);  // still 1
mprintf("T3_MODE=%d\n", MODE);

// ── T4: Press 'p' (112) — toggle paused false→true ────────────────
key_handler(0, 0, 0, -112);
mprintf("T4_MODE=%d\n", MODE);           // still 1
mprintf("T4_PAUSED=%d\n", paused);
mprintf("T4_MARGIN=%d\n", MARGIN_BOUNDARY);  // still 1

// ── T5: Press 'h' (104) — toggle show_help false→true ─────────────
key_handler(0, 0, 0, -104);
mprintf("T5_HELP=%d\n", show_help);
mprintf("T5_PAUSED=%d\n", paused);       // still 1

// ── T6: Press 'B' (66, uppercase) — toggle MARGIN_BOUNDARY true→false
key_handler(0, 0, 0, -66);
mprintf("T6_MARGIN=%d\n", MARGIN_BOUNDARY);
mprintf("T6_MODE=%d\n", MODE);           // still 1

// ── T7: Press 'M' (77) — toggle MODE 1→0 ──────────────────────────
key_handler(0, 0, 0, -77);
mprintf("T7_MODE=%d\n", MODE);
mprintf("T7_MARGIN=%d\n", MARGIN_BOUNDARY);  // still 0

// ── T8: Press 'p' again — toggle paused true→false ────────────────
key_handler(0, 0, 0, -112);
mprintf("T8_PAUSED=%d\n", paused);
mprintf("T8_HELP=%d\n", show_help);      // still 1

// ── T9: Press 'h' again — toggle show_help true→false ─────────────
key_handler(0, 0, 0, -104);
mprintf("T9_HELP=%d\n", show_help);

// ── T10: Press ']' (93) — SIGMA 4→5 ───────────────────────────────
key_handler(0, 0, 0, -93);
mprintf("T10_SIGMA=%d\n", SIGMA);

// ── T11: Press up arrow (38) — PHI_P 0.03→0.04 ───────────────────
key_handler(0, 0, 0, -38);
mprintf("T11_PHIP=%.2f\n", PHI_P);

// ── T12: Press left arrow (37) — PHI_A 0.80→0.79 ─────────────────
key_handler(0, 0, 0, -37);
mprintf("T12_PHIA=%.2f\n", PHI_A);

// ── T13: Press '=' (61) — pending_add 0→10 ────────────────────────
key_handler(0, 0, 0, -61);
mprintf("T13_PENDADD=%d\n", pending_add);

// ── T14: Press '-' (45) — pending_remove 0→10 ─────────────────────
key_handler(0, 0, 0, -45);
mprintf("T14_PENDRMV=%d\n", pending_remove);

// ── T15: Press 'r' (114) — pending_reset false→true ───────────────
key_handler(0, 0, 0, -114);
mprintf("T15_RESET=%d\n", pending_reset);

// ── T16: Press multiple times: '+'/']'/'[' ─────────────────────────
key_handler(0, 0, 0, -43);    // + (43) — pending_add 10→20
key_handler(0, 0, 0, -61);    // = (61) — pending_add 20→30
mprintf("T16_PENDADD=%d\n", pending_add);

key_handler(0, 0, 0, -93);    // ] (93) — SIGMA 5→6
key_handler(0, 0, 0, -93);    // ] (93) — SIGMA 6→7
mprintf("T16_SIGMA=%d\n", SIGMA);

key_handler(0, 0, 0, -91);    // [ (91) — SIGMA 7→6
mprintf("T16_SIGMABACK=%d\n", SIGMA);

// ── T17: Press down arrow (40) — PHI_P 0.04→0.03 ─────────────────
key_handler(0, 0, 0, -40);
mprintf("T17_PHIP=%.2f\n", PHI_P);

// ── T18: Press right arrow (39) — PHI_A 0.79→0.80 ────────────────
key_handler(0, 0, 0, -39);
mprintf("T18_PHIA=%.2f\n", PHI_A);

// ── Verify independent toggles don't cross-contaminate ────────────
mprintf("T19_MARGIN=%d\n", MARGIN_BOUNDARY);
mprintf("T19_MODE=%d\n", MODE);
mprintf("T19_PAUSED=%d\n", paused);
mprintf("T19_HELP=%d\n", show_help);

// ── T20: Unrecognized key 'x' (120) — all globals unchanged ──────
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

key_handler(0, 0, 0, -120);

mprintf("T20_MARGIN_UNCHANGED=%d\n", MARGIN_BOUNDARY == margin_before);
mprintf("T20_MODE_UNCHANGED=%d\n", MODE == mode_before);
mprintf("T20_PAUSED_UNCHANGED=%d\n", paused == paused_before);
mprintf("T20_HELP_UNCHANGED=%d\n", show_help == help_before);
mprintf("T20_PHIP_UNCHANGED=%d\n", abs(PHI_P - phip_before) < 0.001);
mprintf("T20_PHIA_UNCHANGED=%d\n", abs(PHI_A - phia_before) < 0.001);
mprintf("T20_SIGMA_UNCHANGED=%d\n", SIGMA == sigma_before);
mprintf("T20_PENDADD_UNCHANGED=%d\n", pending_add == add_before);
mprintf("T20_PENDRMV_UNCHANGED=%d\n", pending_remove == rmv_before);
mprintf("T20_RESET_UNCHANGED=%d\n", pending_reset == reset_before);

// ── T21: Unrecognized key 'z' (122) — all globals unchanged ──────
key_handler(0, 0, 0, -122);

mprintf("T21_MARGIN_UNCHANGED=%d\n", MARGIN_BOUNDARY == margin_before);
mprintf("T21_MODE_UNCHANGED=%d\n", MODE == mode_before);
mprintf("T21_PAUSED_UNCHANGED=%d\n", paused == paused_before);
mprintf("T21_HELP_UNCHANGED=%d\n", show_help == help_before);
mprintf("T21_PHIP_UNCHANGED=%d\n", abs(PHI_P - phip_before) < 0.001);
mprintf("T21_PHIA_UNCHANGED=%d\n", abs(PHI_A - phia_before) < 0.001);
mprintf("T21_SIGMA_UNCHANGED=%d\n", SIGMA == sigma_before);
mprintf("T21_PENDADD_UNCHANGED=%d\n", pending_add == add_before);
mprintf("T21_PENDRMV_UNCHANGED=%d\n", pending_remove == rmv_before);
mprintf("T21_RESET_UNCHANGED=%d\n", pending_reset == reset_before);

// ═══════════════════════════════════════════════════════════════════
//  CLAMPING LIMIT TESTS
// ═══════════════════════════════════════════════════════════════════

// ── T22: PHI_P floor at 0.0  (current PHI_P = 0.03) ──────────────
//  Press downarrow 5 times: 0.03→0.02→0.01→0.00→0.00 (clamped)
for i = 1:5, key_handler(0, 0, 0, -40); end
mprintf("T22_PHIP=%.2f\n", PHI_P);
mprintf("T22_PHIP_AT_FLOOR=%d\n", PHI_P == 0.0);

// ── T23: PHI_A ceiling at 1.0  (current PHI_A = 0.80) ───────────
for i = 1:22, key_handler(0, 0, 0, -39); end
mprintf("T23_PHIA=%.2f\n", PHI_A);
mprintf("T23_PHIA_AT_CEILING=%d\n", PHI_A == 1.0);

// ── T24: PHI_A floor at 0.0  (current PHI_A = 1.00) ──────────────
for i = 1:102, key_handler(0, 0, 0, -37); end
mprintf("T24_PHIA=%.2f\n", PHI_A);
mprintf("T24_PHIA_AT_FLOOR=%d\n", PHI_A == 0.0);

// ── T25: SIGMA ceiling at 50  (current SIGMA = 6 after T16) ──────
for i = 1:50, key_handler(0, 0, 0, -93); end
mprintf("T25_SIGMA=%d\n", SIGMA);
mprintf("T25_SIGMA_AT_CEILING=%d\n", SIGMA == 50);

// ── T26: SIGMA floor at 1  (current SIGMA = 50) ──────────────────
for i = 1:55, key_handler(0, 0, 0, -91); end
mprintf("T26_SIGMA=%d\n", SIGMA);
mprintf("T26_SIGMA_AT_FLOOR=%d\n", SIGMA == 1);

// ── T27: pending_add ceiling at 200  (current pending_add = 30) ───
for i = 1:20, key_handler(0, 0, 0, -61); end
mprintf("T27_PENDADD=%d\n", pending_add);
mprintf("T27_PENDADD_AT_CEILING=%d\n", pending_add == 200);

// ── T28: pending_remove has NO cap — grows unbounded ──────────────
for i = 1:100, key_handler(0, 0, 0, -45); end
mprintf("T28_PENDRMV=%d\n", pending_remove);
mprintf("T28_PENDRMV_UNBOUNDED=%d\n", pending_remove > 200);

// ── T29: PHI_P ceiling at 1.0  (current PHI_P = 0.00) ────────────
for i = 1:102, key_handler(0, 0, 0, -38); end
mprintf("T29_PHIP=%.2f\n", PHI_P);
mprintf("T29_PHIP_AT_CEILING=%d\n", PHI_P == 1.0);

// ── T30: Positive ibut (mouse event) — skipped entirely ──────────
//  key_handler only processes keyboard events (ibut < 0).
//  With ibut >= 0, no globals should change.
phip30_before = PHI_P;
phia30_before = PHI_A;
sigma30_before = SIGMA;
add30_before = pending_add;
rmv30_before = pending_remove;
reset30_before = pending_reset;

key_handler(0, 0, 0, 1);     // ibut = 1 (positive, mouse click)
key_handler(0, 0, 0, 100);   // ibut = 100 (mouse move)
key_handler(0, 0, 0, 0);     // ibut = 0 (boundary case)

mprintf("T30_PHIP_UNCHANGED=%d\n", abs(PHI_P - phip30_before) < 0.001);
mprintf("T30_PHIA_UNCHANGED=%d\n", abs(PHI_A - phia30_before) < 0.001);
mprintf("T30_SIGMA_UNCHANGED=%d\n", SIGMA == sigma30_before);
mprintf("T30_MARGIN_UNCHANGED=%d\n", MARGIN_BOUNDARY == margin_before);
mprintf("T30_MODE_UNCHANGED=%d\n", MODE == mode_before);
mprintf("T30_PAUSED_UNCHANGED=%d\n", paused == paused_before);
mprintf("T30_HELP_UNCHANGED=%d\n", show_help == help_before);
mprintf("T30_PENDADD_UNCHANGED=%d\n", pending_add == add30_before);
mprintf("T30_PENDRMV_UNCHANGED=%d\n", pending_remove == rmv30_before);
mprintf("T30_RESET_UNCHANGED=%d\n", pending_reset == reset30_before);

// ── T31: ibut = 0 boundary case (focused, isolated) ──────────────
//  T30 tested ibut=0 mixed with +1/+100.  T31 verifies the boundary
//  case in isolation with all 10 globals capture-checked.

margin_before31 = MARGIN_BOUNDARY;
mode_before31   = MODE;
paused_before31 = paused;
help_before31   = show_help;
phip_before31   = PHI_P;
phia_before31   = PHI_A;
sigma_before31  = SIGMA;
add_before31    = pending_add;
rmv_before31    = pending_remove;
reset_before31  = pending_reset;

key_handler(0, 0, 0, 0);   // ibut = 0 — NOT < 0, so entire handler skipped

mprintf("T31_MARGIN_UNCHANGED=%d\n", MARGIN_BOUNDARY == margin_before31);
mprintf("T31_MODE_UNCHANGED=%d\n", MODE == mode_before31);
mprintf("T31_PAUSED_UNCHANGED=%d\n", paused == paused_before31);
mprintf("T31_HELP_UNCHANGED=%d\n", show_help == help_before31);
mprintf("T31_PHIP_UNCHANGED=%d\n", abs(PHI_P - phip_before31) < 0.001);
mprintf("T31_PHIA_UNCHANGED=%d\n", abs(PHI_A - phia_before31) < 0.001);
mprintf("T31_SIGMA_UNCHANGED=%d\n", SIGMA == sigma_before31);
mprintf("T31_PENDADD_UNCHANGED=%d\n", pending_add == add_before31);
mprintf("T31_PENDRMV_UNCHANGED=%d\n", pending_remove == rmv_before31);
mprintf("T31_RESET_UNCHANGED=%d\n", pending_reset == reset_before31);

// ═══════════════════════════════════════════════════════════════════
//  PRESET KEY TESTS
// ═══════════════════════════════════════════════════════════════════

// ── T32: Press '3' (51) — Pearce Default ─────────────────────────
key_handler(0, 0, 0, -51);
mprintf("T32_PHIP=%.2f\n", PHI_P);
mprintf("T32_PHIA=%.2f\n", PHI_A);
mprintf("T32_SIGMA=%d\n", SIGMA);
mprintf("T32_MODE=%d\n", MODE);

// ── T33: Press '5' (53) — Classic Boids (SPATIAL) ────────────────
key_handler(0, 0, 0, -53);
mprintf("T33_PHIP=%.2f\n", PHI_P);
mprintf("T33_PHIA=%.2f\n", PHI_A);
mprintf("T33_SIGMA=%d\n", SIGMA);
mprintf("T33_MODE=%d\n", MODE);

// ── T34: Press 's' (115) — Swarm Pilot (letter key) ──────────────
key_handler(0, 0, 0, -115);
mprintf("T34_PHIP=%.2f\n", PHI_P);
mprintf("T34_PHIA=%.2f\n", PHI_A);
mprintf("T34_SIGMA=%d\n", SIGMA);
mprintf("T34_MODE=%d\n", MODE);

// ── T35: Press '0' (48) — Storm Turn (SPATIAL, zero key) ─────────
key_handler(0, 0, 0, -48);
mprintf("T35_PHIP=%.2f\n", PHI_P);
mprintf("T35_PHIA=%.2f\n", PHI_A);
mprintf("T35_SIGMA=%d\n", SIGMA);
mprintf("T35_MODE=%d\n", MODE);

// ── T36: Press '1' (49) — Pure Alignment ─────────────────────────
key_handler(0, 0, 0, -49);
mprintf("T36_PHIP=%.2f\n", PHI_P);
mprintf("T36_PHIA=%.2f\n", PHI_A);
mprintf("T36_SIGMA=%d\n", SIGMA);
mprintf("T36_MODE=%d\n", MODE);

// ── T37: Press 'S' (83, uppercase) — same preset as 's' ──────────
key_handler(0, 0, 0, -83);
mprintf("T37_PHIP=%.2f\n", PHI_P);
mprintf("T37_PHIA=%.2f\n", PHI_A);
mprintf("T37_SIGMA=%d\n", SIGMA);
mprintf("T37_MODE=%d\n", MODE);

quit();
