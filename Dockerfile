# Dockerfile — Murmuration 3D Bird Flock Simulation
#
# A single image that can both run the 3D simulation (headless, via a
# virtual X display) and run the test suite.
#
#   Build:        docker compose build
#   Run the sim:  docker compose run --rm murmuration
#   Run tests:    docker compose run --rm tests
#   Shell:        docker compose run --rm shell
#
# The 3D renderer uses ModernGL; there is no GPU in the container, so the
# GL context is served by Mesa's software rasteriser (llvmpipe) on an Xvfb
# virtual display. `xvfb-run` wraps the sim so no real display is needed.
# (The image can also run capture_3d.py, but the software rasteriser makes
#  a full GIF capture very slow — run that on a GPU host instead.)

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="Murmuration 3D — Bird Flock Simulation"
LABEL org.opencontainers.image.description="3D murmuration simulation with ModernGL rendering, orbit camera, and dual-mode flocking (Pearce 2014 projection + Reynolds boids)"
LABEL org.opencontainers.image.url="https://github.com/tralev/murmuration"
LABEL org.opencontainers.image.licenses="GPL-3.0-or-later"

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ── System + Python dependencies, in one layer ──────────────────────
#  Runtime GL:   mesa (libgl/libegl/dri), SDL2, Xvfb + xauth  — kept.
#  Build-only:   build-essential + libx11-dev  — needed to compile
#                ModernGL's glcontext (no aarch64 wheel), then purged so
#                they do not bloat the final image.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        libgl1-mesa-glx libgl1-mesa-dri libegl1-mesa libx11-6 \
        libsdl2-2.0-0 xvfb xauth \
        build-essential libx11-dev; \
    pip install \
        "pygame>=2.0,<3.0" \
        "numpy>=1.21" \
        "scipy>=1.7" \
        "moderngl>=5.6" \
        "PyGLM>=2.5" \
        "Pillow>=9.0"; \
    apt-get purge -y build-essential libx11-dev; \
    apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/*

# ── Project files ───────────────────────────────────────────────────
#  Copy every Python module (the whole 3D stack + tests) in one shot, so
#  adding a module never requires touching this Dockerfile. The build
#  context is trimmed by .dockerignore (papers, notebooks, VCS, etc.).
WORKDIR /app
COPY *.py ./
COPY LICENSE ./
RUN mkdir -p /app/output

# ── Default: run the simulation headless on a virtual display ───────
CMD ["xvfb-run", "-a", "python", "main_3d.py"]
