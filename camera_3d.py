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

    # Default view, captured so reset() can restore it exactly.
    _DEFAULT_AZIMUTH = math.radians(45)
    _DEFAULT_ELEVATION = math.radians(30)
    _DEFAULT_DISTANCE = 1200.0
    AUTO_ROTATE_SPEED = 0.45   # rad/s — companion auto-rotate rate

    def __init__(self, target=(500, 350, 200)):
        self.target = glm.vec3(*target)
        self.azimuth = self._DEFAULT_AZIMUTH
        self.elevation = self._DEFAULT_ELEVATION
        self.distance = self._DEFAULT_DISTANCE
        self.min_distance = 200.0
        self.max_distance = 4000.0
        self.fov = math.radians(50)
        self.near = 1.0
        self.far = 10000.0
        self.auto_rotate = False   # toggled by the O key

    def reset(self):
        """Snap the camera back to its default orbit (R-for-view / V key).
        Leaves auto-rotate state unchanged."""
        self.azimuth = self._DEFAULT_AZIMUTH
        self.elevation = self._DEFAULT_ELEVATION
        self.distance = self._DEFAULT_DISTANCE

    def toggle_auto_rotate(self):
        """Enable/disable unattended auto-rotation; returns new state."""
        self.auto_rotate = not self.auto_rotate
        return self.auto_rotate

    def step_auto_rotate(self, dt):
        """Advance the azimuth for auto-rotate mode (no-op when off).
        *dt* is seconds since the last frame."""
        if self.auto_rotate:
            self.azimuth += self.AUTO_ROTATE_SPEED * dt

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
