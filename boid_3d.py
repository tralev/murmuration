"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D BOID — Single Bird Agent                                        ║
╚══════════════════════════════════════════════════════════════════════╝

 A single bird agent with 3D position, velocity, and acceleration.
 Uses numpy arrays for efficient math and VBO packing.

 Physics (shared by both modes; see sci.md §4.6 for why these depart from
 the bare Pearce equations):
   Euler integration with speed clamping to the band [0.3·V₀, V₀] (a floor
   that prevents stalling, not a strict constant speed) and toroidal
   position wrap in all 3 dimensions. The OPEN_BOUNDARY flag (§4.9) swaps
   the wrap for free flight so the flock can self-size.

 Dependencies:  numpy, flock_core, spatial_3d
──────────────────────────────────────────────────────────────────────
"""

import random
import math

import numpy as np

from flock_core import (
    WIDTH, HEIGHT, DEPTH, V0, MAX_FORCE,
    MODE_PROJECTION, MODE_SPATIAL,
)
from spatial_3d import BOUNDARY_MARGIN_Z, flock_projection_3d, flock_spatial_3d

# ── Boundary mode constants (local) ────────────────────────────────
MARGIN_BOUNDARY     = False
BOUNDARY_MARGIN     = 200
BOUNDARY_TURN_FACTOR = 1

# Open (free-flight) boundary: no toroidal wrap and no wall clamp, so the
# flock floats in unbounded space and self-sizes to a real light–dark
# silhouette edge. This is what makes Pearce's marginal opacity N-independent
# (density ρ ~ N^(−1/2) in 3D); on a torus every bird is interior, there is no
# edge, and the flock is forced to the fixed domain volume so ρ ∝ N instead.
# The interactive viewer keeps the torus (birds stay on screen); the
# density-scaling analysis flips this on. See density_scaling.py.
OPEN_BOUNDARY       = False


class Boid3D:
    """
    A single bird agent in 3D.

    Attributes
    ----------
    pos   : np.ndarray (3,) float32 — position [x, y, z]
    vel   : np.ndarray (3,) float32 — velocity [vx, vy, vz]
    acc   : np.ndarray (3,) float32 — accumulated steering forces
    last_theta : float — cached internal opacity Θ (for metrics)
    """
    __slots__ = ("pos", "vel", "acc", "last_theta")

    def __init__(self):
        self.pos = np.array([
            random.uniform(0, WIDTH),
            random.uniform(0, HEIGHT),
            random.uniform(0, DEPTH),
        ], dtype=np.float32)

        # Random initial direction on the unit sphere
        theta = random.uniform(0, 2 * math.pi)
        phi = random.uniform(0, math.pi)
        speed = random.uniform(1, V0)
        self.vel = np.array([
            math.cos(theta) * math.sin(phi) * speed,
            math.sin(theta) * math.sin(phi) * speed,
            math.cos(phi) * speed,
        ], dtype=np.float32)

        self.acc = np.zeros(3, dtype=np.float32)
        self.last_theta = 0.0

    def apply_force(self, force):
        """Accumulate a steering force for the current frame."""
        self.acc += force

    def update(self):
        """
        Euler integration step (3D).
        1. v ← v + a          apply accumulated steering
        2. boundary nudge     margin mode: steer away from walls
        3. speed clamped to [0.3·V₀, V₀]
        4. p ← p + v          move forward
        5. position wrap      toroidal re-entry or hard clamp
        6. a ← 0              reset steering accumulator
        """
        self.vel += self.acc

        # ── Boundary nudge (margin mode — before speed clamp) ──
        if MARGIN_BOUNDARY:
            if self.pos[0] < BOUNDARY_MARGIN:
                self.vel[0] += BOUNDARY_TURN_FACTOR
            if self.pos[0] > WIDTH - BOUNDARY_MARGIN:
                self.vel[0] -= BOUNDARY_TURN_FACTOR
            if self.pos[1] < BOUNDARY_MARGIN:
                self.vel[1] += BOUNDARY_TURN_FACTOR
            if self.pos[1] > HEIGHT - BOUNDARY_MARGIN:
                self.vel[1] -= BOUNDARY_TURN_FACTOR
            if self.pos[2] < BOUNDARY_MARGIN_Z:
                self.vel[2] += BOUNDARY_TURN_FACTOR
            if self.pos[2] > DEPTH - BOUNDARY_MARGIN_Z:
                self.vel[2] -= BOUNDARY_TURN_FACTOR

        # ── Speed clamp ──────────────────────────────────────
        speed = np.linalg.norm(self.vel)
        if speed > V0:
            self.vel = (self.vel / speed) * V0
        elif speed < V0 * 0.3:
            if speed > 0.001:
                self.vel = (self.vel / speed) * V0 * 0.3
            else:
                theta = random.uniform(0, 2 * math.pi)
                phi = random.uniform(0, math.pi)
                self.vel = np.array([
                    math.cos(theta) * math.sin(phi),
                    math.sin(theta) * math.sin(phi),
                    math.cos(phi),
                ], dtype=np.float32) * V0 * 0.3

        self.pos += self.vel
        self.acc = np.zeros(3, dtype=np.float32)

        # ── Position boundary handling ───────────────────────
        if OPEN_BOUNDARY:
            # Free flight: leave the position untouched so the flock can
            # float and self-size (marginal opacity becomes N-independent).
            pass
        elif MARGIN_BOUNDARY:
            self.pos[0] = max(0.0, min(float(WIDTH), self.pos[0]))
            self.pos[1] = max(0.0, min(float(HEIGHT), self.pos[1]))
            self.pos[2] = max(0.0, min(float(DEPTH), self.pos[2]))
        else:
            # Toroidal wrap in all 3 dimensions
            if self.pos[0] > WIDTH:   self.pos[0] = 0.0
            elif self.pos[0] < 0:     self.pos[0] = float(WIDTH)
            if self.pos[1] > HEIGHT:  self.pos[1] = 0.0
            elif self.pos[1] < 0:     self.pos[1] = float(HEIGHT)
            if self.pos[2] > DEPTH:   self.pos[2] = 0.0
            elif self.pos[2] < 0:     self.pos[2] = float(DEPTH)

    def flock(self, all_boids, config, grid):
        """
        Dispatch to the active flocking logic based on config.mode.

        Parameters
        ----------
        all_boids : list[Boid3D]
        config    : Config
        grid      : SpatialGrid3D
        """
        if config.mode == MODE_PROJECTION:
            flock_projection_3d(self, all_boids, config, grid)
        else:
            flock_spatial_3d(self, all_boids, config, grid)
