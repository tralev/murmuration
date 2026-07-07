% test_toroidal_wrap.m  — isolated toroidal wrap physics test
% Run: octave --no-gui test_toroidal_wrap.m
% Prints KEY=VALUE lines for each test case's position and velocity.

WIDTH = 1000; HEIGHT = 700; V0 = 4;

% Test cases:
%   T1: wrap right→left    T2: wrap left→right
%   T3: wrap bottom→top    T4: wrap top→bottom
%   T5: corner bottom-right T6: corner top-left
%   T7: high-speed clamp   T8: velocity preserved
pos = [
    1002, 350;   % T1
    -2,   350;   % T2
    500,  702;   % T3
    500,  -2;    % T4
    1002, 702;   % T5
    -2,   -2;    % T6
    500,  350;   % T7
    1002, 350;   % T8
];
vel = [
    4, 0;        % T1
    -4, 0;       % T2
    0, 4;        % T3
    0, -4;       % T4
    4, 4;        % T5
    -4, -4;      % T6
    1200, 0;     % T7 (speed clamped to V0)
    4, 0;        % T8 (velocity unchanged after wrap)
];
acc = zeros(8, 2);

% Physics step: core toroidal wrap (vel+=acc, speed clamp, pos+=vel, mod wrap)
% Excludes MARGIN_BOUNDARY nudge block and the random-direction
% zero-speed floor special-case (neither is triggered by these test inputs).
vel = vel + acc;

% No margin nudge (MARGIN_BOUNDARY not defined → toroidal path)

spd = sqrt(sum(vel.^2, 2));

% Speed clamp: [0.3·V0, V0]
fast = find(spd > V0);
if ~isempty(fast)
    vel(fast,:) = vel(fast,:) ./ repmat(spd(fast), 1, 2) * V0;
end
slow = find(spd < V0 * 0.3);
if ~isempty(slow)
    vel(slow,:) = vel(slow,:) ./ repmat(spd(slow), 1, 2) * (V0 * 0.3);
end

pos = pos + vel;

% Toroidal wrap
pos(:,1) = mod(pos(:,1), WIDTH);
pos(:,2) = mod(pos(:,2), HEIGHT);

% Print results as KEY=VALUE
for i = 1:size(pos,1)
    fprintf('T%d_X=%.4f\n', i, pos(i,1));
    fprintf('T%d_Y=%.4f\n', i, pos(i,2));
    fprintf('T%d_VX=%.4f\n', i, vel(i,1));
    fprintf('T%d_VY=%.4f\n', i, vel(i,2));
end
