"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D CAMERA — perspective orbit camera                               ║
╚══════════════════════════════════════════════════════════════════════╝

 OrbitCamera, extracted from renderer_3d.py: pure view/projection
 math with no GPU state, so it can be studied and unit-tested without
 a ModernGL context.

 Orbit parametrisation (spherical coordinates around a target point):
   azimuth    — rotation in the XY plane (drag left/right)
   elevation  — angle above the XY plane (drag up/down)
   distance   — radius from the target  (scroll to zoom)

 The world is Z-up (the simulation volume is 1000 × 700 × 400 with Z
 as altitude), hence the (0, 0, 1) up-vector in view_matrix().

 Dependencies:  PyGLM (matrix/vector math)
──────────────────────────────────────────────────────────────────────
"""

import math

import glm


class OrbitCamera:
    """Perspective orbit camera. Drag mouse to rotate, scroll to zoom."""

    def __init__(self, target=(500, 350, 200)):
        self.target = glm.vec3(*target)
        self.azimuth = math.radians(45)
        self.elevation = math.radians(30)
        self.distance = 1200.0
        self.min_distance = 200.0
        self.max_distance = 4000.0
        self.fov = math.radians(50)
        self.near = 1.0
        self.far = 10000.0

    def rotate(self, d_azimuth, d_elevation):
        self.azimuth += d_azimuth
        self.elevation += d_elevation
        self.elevation = max(-math.pi / 2 + 0.05,
                             min(math.pi / 2 - 0.05, self.elevation))

    def zoom(self, delta):
        self.distance -= delta * 50.0
        self.distance = max(self.min_distance,
                            min(self.max_distance, self.distance))

    def position(self):
        x = (self.target.x +
             self.distance * math.cos(self.elevation) * math.cos(self.azimuth))
        y = (self.target.y +
             self.distance * math.cos(self.elevation) * math.sin(self.azimuth))
        z = self.target.z + self.distance * math.sin(self.elevation)
        return glm.vec3(x, y, z)

    def view_matrix(self):
        return glm.lookAt(self.position(), self.target, glm.vec3(0, 0, 1))

    def projection_matrix(self, aspect):
        return glm.perspective(self.fov, aspect, self.near, self.far)
