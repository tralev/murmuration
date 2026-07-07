% test_boundary_toggle.m  — isolated MARGIN_BOUNDARY toggle test
% Run: octave --no-gui test_boundary_toggle.m
% Simulates pressing 'b' to toggle margin/toroidal boundary mode.
% Prints STATE0, STATE1, STATE2 lines showing the global value across toggles.

global MARGIN_BOUNDARY BOUNDARY_MARGIN BOUNDARY_TURN_FACTOR

% Initialise as the default (toroidal)
MARGIN_BOUNDARY      = false;
BOUNDARY_MARGIN      = 200;
BOUNDARY_TURN_FACTOR = 1;

% ── Print initial state ───────────────────────────────────────────
fprintf('TOGGLE_STEP=initial\n');
fprintf('STATE0=%d\n', MARGIN_BOUNDARY);

% ── Simulate first press of 'b' ───────────────────────────────────
MARGIN_BOUNDARY = ~MARGIN_BOUNDARY;
fprintf('TOGGLE_STEP=toggled_once\n');
fprintf('STATE1=%d\n', MARGIN_BOUNDARY);

% ── Simulate second press of 'b' ──────────────────────────────────
MARGIN_BOUNDARY = ~MARGIN_BOUNDARY;
fprintf('TOGGLE_STEP=toggled_twice\n');
fprintf('STATE2=%d\n', MARGIN_BOUNDARY);

% Also print the companion globals to verify they exist
fprintf('BOUNDARY_MARGIN=%.0f\n', BOUNDARY_MARGIN);
fprintf('BOUNDARY_TURN_FACTOR=%.0f\n', BOUNDARY_TURN_FACTOR);
