"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D RENDERER — ModernGL Instanced Rendering                         ║
╚══════════════════════════════════════════════════════════════════════╝

 GPU-side rendering: instanced cone meshes with per-bird position +
 velocity (LookAt rotation computed in the vertex shader).
 Perspective camera with orbit controls.

 Uses ModernGL (not raw PyOpenGL) for macOS Metal compatibility.
 Dependencies:  numpy, ModernGL, PyGLM
──────────────────────────────────────────────────────────────────────
"""

import math

import numpy as np
import moderngl
import glm


# ── Bird mesh: a simple tetrahedron (4 vertices, 4 triangles) ──────

BIRD_VERTS = np.array([
    [ 0.0,  0.0,  1.0],     # Front tip
    [-0.5, -0.5, -0.5],     # Back-left
    [ 0.5, -0.5, -0.5],     # Back-right
    [ 0.0,  0.5, -0.5],     # Back-top
], dtype=np.float32)

BIRD_NORMALS = np.array([
    [0.0, 0.0, 1.0],        # Tip normal
    [0.0, 0.0, -1.0],       # Back normals
    [0.0, 0.0, -1.0],
    [0.0, 0.0, -1.0],
], dtype=np.float32)

BIRD_INDICES = np.array([
    0, 1, 2,   # front-bottom
    0, 2, 3,   # front-right
    0, 3, 1,   # front-left
    1, 3, 2,   # back face
], dtype=np.uint32)

BIRD_SCALE = 3.0


# ══════════════════════════════════════════════════════════════════════
#  GLSL SHADERS  (GLSL 3.30 — supported by ModernGL on macOS/Metal)
# ══════════════════════════════════════════════════════════════════════

VERTEX_SHADER = """
#version 330

layout(location = 0) in vec3 in_Position;
layout(location = 1) in vec3 in_Normal;
layout(location = 2) in vec3 in_InstancePos;
layout(location = 3) in vec3 in_InstanceVel;

uniform mat4 u_View;
uniform mat4 u_Projection;
uniform float u_Scale;
uniform vec3 u_LightDir;
uniform vec3 u_CameraPos;

out vec3 v_Normal;
out vec3 v_WorldPos;
out vec3 v_LightDir;
out vec3 v_ViewDir;
out float v_Speed;

mat3 lookAtRotation(vec3 forward) {
    vec3 f = normalize(forward);
    if (length(f) < 0.001)
        return mat3(1.0);

    vec3 arbitraryUp = vec3(0.0, 1.0, 0.0);
    if (abs(dot(f, arbitraryUp)) > 0.999)
        arbitraryUp = vec3(1.0, 0.0, 0.0);

    vec3 r = normalize(cross(arbitraryUp, f));
    vec3 u = cross(f, r);
    return mat3(r, u, f);
}

void main() {
    float speed = length(in_InstanceVel);
    v_Speed = clamp(speed / 4.0, 0.0, 1.0);

    mat3 rot = lookAtRotation(in_InstanceVel);
    vec3 worldPos = rot * (in_Position * u_Scale) + in_InstancePos;
    vec3 worldNormal = rot * in_Normal;

    v_WorldPos = worldPos;
    v_Normal = normalize(worldNormal);
    v_LightDir = normalize(u_LightDir);
    v_ViewDir = normalize(u_CameraPos - worldPos);

    gl_Position = u_Projection * u_View * vec4(worldPos, 1.0);
}
"""

FRAGMENT_SHADER = """
#version 330

in vec3 v_Normal;
in vec3 v_WorldPos;
in vec3 v_LightDir;
in vec3 v_ViewDir;
in float v_Speed;

out vec4 fragColor;

uniform vec3 u_AmbientColor;
uniform vec3 u_DiffuseColor;
uniform float u_SpecularStrength;
uniform float u_Shininess;

void main() {
    vec3 N = normalize(v_Normal);
    vec3 L = normalize(v_LightDir);
    vec3 V = normalize(v_ViewDir);

    vec3 ambient = u_AmbientColor;
    float diff = max(dot(N, L), 0.0);
    vec3 diffuse = diff * u_DiffuseColor;

    vec3 H = normalize(L + V);
    float spec = pow(max(dot(N, H), 0.0), u_Shininess);
    vec3 specular = spec * u_SpecularStrength * u_DiffuseColor;

    vec3 speedTint = mix(
        vec3(0.85, 0.88, 0.95),
        vec3(0.95, 0.85, 0.70),
        v_Speed * 0.3
    );

    vec3 color = (ambient + diffuse) * speedTint + specular * 0.5;
    fragColor = vec4(color, 1.0);
}
"""

GRID_VERTEX_SHADER = """
#version 330

layout(location = 0) in vec3 in_Position;

uniform mat4 u_View;
uniform mat4 u_Projection;

void main() {
    gl_Position = u_Projection * u_View * vec4(in_Position, 1.0);
}
"""

GRID_FRAGMENT_SHADER = """
#version 330

out vec4 fragColor;

void main() {
    fragColor = vec4(0.25, 0.28, 0.32, 1.0);
}
"""


# ══════════════════════════════════════════════════════════════════════
#  CAMERA
# ══════════════════════════════════════════════════════════════════════

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
        """Build grid vertices for the XY plane at z=0."""
        lines = []
        grid_size = 1000
        step = 100
        for i in range(-grid_size // 2, grid_size // 2 + 1, step):
            lines.extend([
                (i, -grid_size // 2, 0.0), (i, grid_size // 2, 0.0),
                (-grid_size // 2, i, 0.0), (grid_size // 2, i, 0.0),
            ])
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

        # Upload uniforms (ModernGL expects bytes via .write())
        prog['u_View'].write(np.array(self.view, dtype=np.float32).tobytes())
        prog['u_Projection'].write(np.array(self.projection, dtype=np.float32).tobytes())
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
        prog['u_View'].write(np.array(self.view, dtype=np.float32).tobytes())
        prog['u_Projection'].write(np.array(self.projection, dtype=np.float32).tobytes())

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
