# Dockerfile — Murmuration 3D Bird Flock Simulation
#
# Build:   docker build -t murmuration .
# Run:     docker compose run murmuration
#
# 3D ModernGL stack: requires OpenGL. Use xvfb for headless operation.
# Students can pull and run without installing Python, Pygame, or ModernGL.

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="Murmuration 3D — Bird Flock Simulation"
LABEL org.opencontainers.image.description="3D murmuration simulation with ModernGL GPU rendering, orbit camera, and dual-mode flocking (Pearce 2014 projection + Reynolds boids)"
LABEL org.opencontainers.image.url="https://github.com/tralev/murmuration"
LABEL org.opencontainers.image.licenses="GPL-3.0-or-later"

# ── System dependencies for headless OpenGL (ModernGL + mesa) ───────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libx11-dev \
    libgl1-mesa-glx \
    libgl1-mesa-dri \
    libegl1-mesa \
    libsdl2-2.0-0 \
    xvfb \
    xauth \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ─────────────────────────────────────────────
RUN pip install --no-cache-dir \
    "pygame>=2.0,<3.0" \
    "numpy>=1.21" \
    "scipy>=1.7" \
    "moderngl>=5.6" \
    "PyGLM>=2.5"

# ── Copy 3D project files ───────────────────────────────────────────
WORKDIR /app
COPY main_3d.py boid_3d.py spatial_3d.py renderer_3d.py ./
COPY camera_3d.py shaders_3d.py capture_3d.py ./
COPY input_handler_3d.py flock_core.py features.py ./
# Paper-grounded 3D science modules: Pearce (true spherical-cap occlusion,
# metrics, correlation time τρ), Young (H₂ robustness, shape→m*), Goodenough
# (ecology) + restored 3D scenario presets, and their tests.
COPY occlusion_3d.py metrics_3d.py correlation_time.py flock_shape.py ./
COPY h2_robustness.py ecology.py scenario_presets_3d.py ./
COPY test_3d.py test_science_3d.py ./
COPY LICENSE ./

# ── Default command: headless simulation via xvfb ───────────────────
# Override with `docker compose run murmuration bash` for a shell.
CMD ["xvfb-run", "python", "main_3d.py"]
