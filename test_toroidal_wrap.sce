// test_toroidal_wrap.sce  — isolated toroidal wrap physics test
// Run: scilab-cli -nb -f test_toroidal_wrap.sce
// Prints KEY=VALUE lines for each test case's position and velocity.

WIDTH = 1000; HEIGHT = 700; V0 = 4;

// Test cases:   T1:right T2:left T3:bottom T4:top T5-6:corners T7:speed T8:vel
pos = [
    1002, 350;
    -2,   350;
    500,  702;
    500,  -2;
    1002, 702;
    -2,   -2;
    500,  350;
    1002, 350;
];
vel = [
    4, 0;
    -4, 0;
    0, 4;
    0, -4;
    4, 4;
    -4, -4;
    1200, 0;
    4, 0;
];
acc = zeros(8, 2);

// Physics step: core toroidal wrap (vel+=acc, speed clamp, pos+=vel, modulo wrap)
// Excludes MARGIN_BOUNDARY nudge block and the random-direction
// zero-speed floor special-case (neither is triggered by these test inputs).
vel = vel + acc;

// Speed clamp
spd = sqrt(sum(vel.^2, 2));

fast = find(spd > V0);
if ~isempty(fast) then
    vel(fast,:) = vel(fast,:) ./ repmat(spd(fast), 1, 2) * V0;
end
slow = find(spd < V0 * 0.3);
if ~isempty(slow) then
    vel(slow,:) = vel(slow,:) ./ repmat(spd(slow), 1, 2) * (V0 * 0.3);
end

pos = pos + vel;

// Toroidal wrap
pos(:,1) = modulo(pos(:,1), WIDTH);
pos(:,2) = modulo(pos(:,2), HEIGHT);

// Print results
for i = 1:size(pos,1)
    mprintf("T%d_X=%.4f\n", i, pos(i,1));
    mprintf("T%d_Y=%.4f\n", i, pos(i,2));
    mprintf("T%d_VX=%.4f\n", i, vel(i,1));
    mprintf("T%d_VY=%.4f\n", i, vel(i,2));
end

quit();
