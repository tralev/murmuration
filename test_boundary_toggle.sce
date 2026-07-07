// test_boundary_toggle.sce  — isolated MARGIN_BOUNDARY toggle test
// Run: scilab-cli -nb -f test_boundary_toggle.sce
// Simulates pressing 'b' to toggle margin/toroidal boundary mode.
// Prints STATE0, STATE1, STATE2 lines showing the global value across toggles.

global MARGIN_BOUNDARY BOUNDARY_MARGIN BOUNDARY_TURN_FACTOR

// Initialise as the default (toroidal)
MARGIN_BOUNDARY      = %f;
BOUNDARY_MARGIN      = 200;
BOUNDARY_TURN_FACTOR = 1;

// ── Print initial state ───────────────────────────────────────────
mprintf("TOGGLE_STEP=initial\n");
mprintf("STATE0=%d\n", MARGIN_BOUNDARY);

// ── Simulate first press of 'b' ───────────────────────────────────
MARGIN_BOUNDARY = ~MARGIN_BOUNDARY;
mprintf("TOGGLE_STEP=toggled_once\n");
mprintf("STATE1=%d\n", MARGIN_BOUNDARY);

// ── Simulate second press of 'b' ──────────────────────────────────
MARGIN_BOUNDARY = ~MARGIN_BOUNDARY;
mprintf("TOGGLE_STEP=toggled_twice\n");
mprintf("STATE2=%d\n", MARGIN_BOUNDARY);

// Also print the companion globals to verify they exist
mprintf("BOUNDARY_MARGIN=%.0f\n", BOUNDARY_MARGIN);
mprintf("BOUNDARY_TURN_FACTOR=%.0f\n", BOUNDARY_TURN_FACTOR);

quit();
