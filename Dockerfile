# Dockerfile — Murmuration Bird Flock Simulation
#
# Build:   docker build -t murmuration .
# Run:     docker compose up
#
# This container runs the simulation headless via xvfb (virtual display).
# Students can pull and run without installing Python or Pygame.

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="Murmuration — Bird Flock Simulation"
LABEL org.opencontainers.image.description="Dual-mode flocking simulation (Pearce 2014 projection model + Reynolds boids) with 16 scenario presets (5 educational + 11 from companion TypeScript/Three.js project), real-time scientific metrics, and 17 roadmap priorities"
LABEL org.opencontainers.image.url="https://github.com/tralev/murmuration"
LABEL org.opencontainers.image.licenses="GPL-3.0-or-later"

# ── Install system dependencies ───────────────────────────────────────
#  Pygame runtime (SDL2), GNU Octave CLI, and Scilab CLI for
#  cross-language validation of .m and .sce test scripts.
#  Note: if scilab-cli is not in your distro's repos, see
#  https://www.scilab.org/download for manual installation.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsdl2-2.0-0 \
    libsdl2-image-2.0-0 \
    libsdl2-mixer-2.0-0 \
    libsdl2-ttf-2.0-0 \
    libfreetype6 \
    libportmidi0 \
    octave \
    scilab-cli \
    && rm -rf /var/lib/apt/lists/*

# ── Install Python deps ──────────────────────────────────────────────
RUN pip install --no-cache-dir pygame

# ── Copy project files ───────────────────────────────────────────────
WORKDIR /app
COPY *.py ./
COPY *.m ./
COPY *.sce ./
COPY extensions/ extensions/
COPY *.md ./
COPY LICENSE ./
RUN mkdir -p /app/output

# ── Default command: run headless via xvfb ───────────────────────────
# Override with `docker compose run murmuration python alg2.py` for the
# full simulation, or `docker compose run murmuration python -m unittest
# test_alg2 -v` to run tests.
CMD ["python", "alg2.py"]
