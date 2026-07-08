"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D GPU ASSETS — bird mesh + GLSL shaders                           ║
╚══════════════════════════════════════════════════════════════════════╝

 The static GPU-side assets for the 3D renderer, extracted from
 renderer_3d.py so the shading model can be read (and modified) as a
 unit, separate from the buffer/VAO plumbing:

   - bird mesh      — a 4-vertex tetrahedron, instanced per bird
   - bird shaders   — per-instance LookAt rotation in the vertex
                      shader, Blinn-Phong lighting + speed tint in
                      the fragment shader
   - grid shaders   — flat-colour reference grid lines

 GLSL 3.30 — supported by ModernGL on macOS/Metal.

 Dependencies:  numpy (mesh arrays)
──────────────────────────────────────────────────────────────────────
"""

import numpy as np


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
#  GLSL SHADERS
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
