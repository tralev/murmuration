"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D RENDERER — ModernGL Instanced Rendering                         ║
╚══════════════════════════════════════════════════════════════════════╝

 GPU buffer/VAO plumbing and per-frame draw calls: all birds are drawn
 in a single instanced call with per-bird position + velocity (LookAt
 rotation computed in the vertex shader).

 Split for readability:
   camera_3d.py   — OrbitCamera (view/projection math, no GPU state)
   shaders_3d.py  — bird mesh + GLSL shader sources
   this module    — ModernGL context, buffers, uniforms, draw calls

 Uses ModernGL (not raw PyOpenGL) for macOS Metal compatibility.
 Dependencies:  numpy, ModernGL, PyGLM, camera_3d, shaders_3d
──────────────────────────────────────────────────────────────────────
"""

import numpy as np
import moderngl
import glm

from camera_3d import OrbitCamera
from shaders_3d import (
    BIRD_VERTS, BIRD_NORMALS, BIRD_INDICES, BIRD_SCALE,
    VERTEX_SHADER, FRAGMENT_SHADER,
    GRID_VERTEX_SHADER, GRID_FRAGMENT_SHADER,
)


def _mat4_bytes(m):
    """Column-major float32 bytes for a glm.mat4 uniform upload.

    Built from the GLM API's column semantics (m.to_list() returns the
    four columns) rather than the raw buffer, because PyGLM builds
    differ in memory layout: some expose bytes(mat4) row-major, which
    silently transposes every matrix handed to glUniformMatrix4fv and
    throws all geometry off-screen.
    """
    return np.array(m.to_list(), dtype=np.float32).tobytes()


# ══════════════════════════════════════════════════════════════════════
#  RENDERER
# ══════════════════════════════════════════════════════════════════════

class Renderer3D:
    """ModernGL renderer with instanced bird drawing.

    Parameters
    ----------
    width, height : int     Framebuffer dimensions in pixels.
    headless : bool         If True, render into an offscreen FBO so frames
                            can be read back via capture_frame().  When False
                            (the default) rendering goes directly to the
                            Pygame window via the standalone context.
    """

    def __init__(self, width, height, headless=False):
        self.width = width
        self.height = height
        self.headless = headless
        self.camera = OrbitCamera()

        # ── Create ModernGL context (standalone for macOS/Metal) ──
        self.ctx = moderngl.create_context(standalone=True, require=330)

        # ── Offscreen capture FBO (headless mode) ───────────
        self._capture_fbo = None
        if headless:
            self._capture_fbo = self.ctx.framebuffer(
                color_attachments=[
                    self.ctx.renderbuffer((width, height), components=3),
                ],
                depth_attachment=self.ctx.depth_renderbuffer((width, height)),
            )

        # ── Compile shader programs ───────────────────────────
        self.bird_prog = self.ctx.program(
            vertex_shader=VERTEX_SHADER,
            fragment_shader=FRAGMENT_SHADER,
        )
        self.grid_prog = self.ctx.program(
            vertex_shader=GRID_VERTEX_SHADER,
            fragment_shader=GRID_FRAGMENT_SHADER,
        )

        # ── Bird mesh buffers ─────────────────────────────────
        mesh_data = np.hstack([BIRD_VERTS, BIRD_NORMALS]).astype(np.float32)
        self.mesh_vbo = self.ctx.buffer(mesh_data)
        self.index_ibo = self.ctx.buffer(BIRD_INDICES)

        # ── Instance buffer (pre-allocated for 5000 birds) ────
        # 6 floats per bird: pos.x, pos.y, pos.z, vel.x, vel.y, vel.z
        self.max_instances = 5000
        self.instance_data = np.zeros((self.max_instances, 6), dtype=np.float32)
        self.instance_vbo = self.ctx.buffer(self.instance_data)

        # ── Bird VAO with per-instance attributes ─────────────
        #  '3f 3f' = two 3-float per-vertex attributes (position, normal)
        #  '3f 3f/i' = two 3-float per-instance attributes (/i = divisor 1)
        self.bird_vao = self.ctx.vertex_array(
            self.bird_prog,
            [
                (self.mesh_vbo, '3f 3f', 'in_Position', 'in_Normal'),
                (self.instance_vbo, '3f 3f/i', 'in_InstancePos', 'in_InstanceVel'),
            ],
            index_buffer=self.index_ibo,
        )

        # ── Grid buffers ──────────────────────────────────────
        grid_verts = self._build_grid_verts()
        self.grid_vbo = self.ctx.buffer(grid_verts)
        self.grid_vao = self.ctx.vertex_array(
            self.grid_prog,
            [(self.grid_vbo, '3f', 'in_Position')],
        )
        self.grid_vertex_count = len(grid_verts)

        # ── State ──────────────────────────────────────────────
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.clear(0.08, 0.10, 0.14)

        # Light direction (upper-right, slightly behind)
        self.light_dir = glm.normalize(glm.vec3(0.5, 0.7, 1.0))

    def _build_grid_verts(self):
        """Build grid vertices for the XY plane at z=0.

        Spans the simulation volume (x 0..1000, y 0..700, matching the
        camera target at its centre) rather than being centred on the
        origin, so the grid sits underneath the flock.
        """
        lines = []
        size_x, size_y = 1000, 700
        step = 100
        for x in range(0, size_x + 1, step):
            lines.extend([(x, 0, 0.0), (x, size_y, 0.0)])
        for y in range(0, size_y + 1, step):
            lines.extend([(0, y, 0.0), (size_x, y, 0.0)])
        return np.array(lines, dtype=np.float32)

    def _grow_instance_buffer(self, needed):
        """Expand the instance buffer if more birds are needed."""
        new_size = needed + 1000
        self.instance_data = np.zeros((new_size, 6), dtype=np.float32)
        self.instance_vbo = self.ctx.buffer(self.instance_data)
        self.max_instances = new_size

        # Rebuild the VAO with the new buffer
        self.bird_vao = self.ctx.vertex_array(
            self.bird_prog,
            [
                (self.mesh_vbo, '3f 3f', 'in_Position', 'in_Normal'),
                (self.instance_vbo, '3f 3f/i', 'in_InstancePos', 'in_InstanceVel'),
            ],
            index_buffer=self.index_ibo,
        )

    def update_instances(self, boids):
        """Pack position + velocity data for instanced rendering."""
        count = len(boids)
        if count > self.max_instances:
            self._grow_instance_buffer(count)

        for i, b in enumerate(boids):
            self.instance_data[i, 0] = b.pos[0]
            self.instance_data[i, 1] = b.pos[1]
            self.instance_data[i, 2] = b.pos[2]
            self.instance_data[i, 3] = b.vel[0]
            self.instance_data[i, 4] = b.vel[1]
            self.instance_data[i, 5] = b.vel[2]

        self.instance_vbo.write(self.instance_data[:count])
        return count

    def begin_frame(self):
        """Clear the framebuffer and compute camera matrices."""
        if self._capture_fbo is not None:
            self._capture_fbo.use()
        self.ctx.clear(0.08, 0.10, 0.14)

        aspect = self.width / self.height
        self.view = self.camera.view_matrix()
        self.projection = self.camera.projection_matrix(aspect)

    def end_frame(self):
        """No-op — Pygame handles buffer swap."""
        pass

    def draw_birds(self, boids):
        """Draw all birds in a single instanced draw call."""
        count = self.update_instances(boids)
        prog = self.bird_prog

        # Upload uniforms (ModernGL expects column-major bytes via .write())
        prog['u_View'].write(_mat4_bytes(self.view))
        prog['u_Projection'].write(_mat4_bytes(self.projection))
        prog['u_Scale'].value = BIRD_SCALE
        prog['u_LightDir'].write(np.array(self.light_dir, dtype=np.float32).tobytes())
        prog['u_CameraPos'].write(np.array(self.camera.position(), dtype=np.float32).tobytes())
        prog['u_AmbientColor'].value = (0.15, 0.17, 0.22)
        prog['u_DiffuseColor'].value = (0.65, 0.68, 0.78)
        prog['u_SpecularStrength'].value = 0.3
        prog['u_Shininess'].value = 16.0

        self.bird_vao.render(instances=count)

    def draw_grid(self):
        """Draw the reference grid on the XY plane."""
        prog = self.grid_prog
        prog['u_View'].write(_mat4_bytes(self.view))
        prog['u_Projection'].write(_mat4_bytes(self.projection))

        self.grid_vao.render(moderngl.LINES)

    def capture_frame(self):
        """Read back the current framebuffer and return a PIL Image.

        Only valid when the renderer was created with ``headless=True``.
        The image has its origin at the top-left (OpenGL FBO data is
        flipped vertically).

        Pillow is imported lazily so that normal (non-headless)
        simulations do not require it as a dependency.
        """
        if self._capture_fbo is None:
            raise RuntimeError(
                "capture_frame() requires headless=True at construction"
            )
        from PIL import Image
        data = self._capture_fbo.read(
            attachment=0, viewport=(0, 0, self.width, self.height),
        )
        img = Image.frombytes('RGB', (self.width, self.height), data)
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
        return img

    def resize(self, width, height):
        """Handle window resize."""
        self.width = width
        self.height = height
        self.ctx.viewport = (0, 0, width, height)
