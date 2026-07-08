"""
╔══════════════════════════════════════════════════════════════════════╗
║  CAPTURE 3D — Headless GIF Generator                                 ║
╚══════════════════════════════════════════════════════════════════════╝

 Renders the 3D murmuration simulation headlessly (via ModernGL FBO)
 and assembles the captured frames into an animated GIF suitable for
 embedding in documentation.

 Usage:
   python capture_3d.py

 Output:
   murmuration_3d.gif   — animated demo (~8 seconds, both modes)

 Dependencies:  numpy, ModernGL, PyGLM, Pillow
──────────────────────────────────────────────────────────────────────
"""

import math
import sys

import numpy as np
from PIL import Image

from flock_core import (
    WIDTH, HEIGHT, V0, NUM_BOIDS,
    MODE_PROJECTION, MODE_SPATIAL,
    Config,
)
from boid_3d import Boid3D
from spatial_3d import SpatialGrid3D
from renderer_3d import Renderer3D

# ── Capture settings ──────────────────────────────────────────────
CAPTURE_W, CAPTURE_H = 800, 600
FPS = 60
TOTAL_FRAMES = 240          # 4 seconds total
CAPTURE_EVERY = 3           # every 3rd frame → ~80 frames @ 20 fps GIF
GIF_DURATION_MS = 50        # 20 fps playback
OUTPUT_FILE = "murmuration_3d.gif"


def _auto_orbit(camera, frame: int, total: int):
    """Slowly orbit the camera for a cinematic sweep."""
    t = frame / total
    camera.azimuth = math.radians(45) + t * math.radians(180)
    camera.elevation = math.radians(25) + math.sin(t * math.pi * 2) * 0.15
    # Close enough that 3-unit birds stay visible after the GIF downsize
    camera.distance = 650 + math.sin(t * math.pi * 1.5) * 100


def main():
    print("Creating headless ModernGL renderer...")
    renderer = Renderer3D(CAPTURE_W, CAPTURE_H, headless=True)

    config = Config()
    config.num_boids = 150
    config.mode = MODE_PROJECTION

    grid = SpatialGrid3D()
    flock = [Boid3D() for _ in range(config.num_boids)]
    frames = []

    print(f"Capturing {TOTAL_FRAMES} frames "
          f"(every {CAPTURE_EVERY} → ~{TOTAL_FRAMES // CAPTURE_EVERY} GIF frames)...")

    # Pre-warm: let the flock settle for 1 second
    for _ in range(FPS):
        grid.rebuild(flock)
        for b in flock:
            b.flock(flock, config, grid)
        for b in flock:
            b.update()

    for frame in range(TOTAL_FRAMES):
        # ── Switch mode halfway ──────────────────────────────
        if frame == TOTAL_FRAMES // 2:
            config.mode = MODE_SPATIAL
            print("  Switching to SPATIAL mode...")

        # ── Auto-orbit camera ────────────────────────────────
        _auto_orbit(renderer.camera, frame, TOTAL_FRAMES)

        # ── Update simulation ────────────────────────────────
        grid.rebuild(flock)
        for b in flock:
            b.flock(flock, config, grid)
        for b in flock:
            b.update()

        # ── Render & capture ─────────────────────────────────
        renderer.begin_frame()
        renderer.draw_birds(flock)
        renderer.draw_grid()
        renderer.end_frame()

        if frame % CAPTURE_EVERY == 0:
            img = renderer.capture_frame()
            # Downsize for smaller GIF
            img = img.resize((400, 300), resample=Image.LANCZOS)
            frames.append(img)
            sys.stdout.write(f"\r  Frame {frame + 1}/{TOTAL_FRAMES} "
                             f"({len(frames)} captured)")
            sys.stdout.flush()

    print(f"\nAssembling GIF ({len(frames)} frames)...")
    frames[0].save(
        OUTPUT_FILE,
        save_all=True,
        append_images=frames[1:],
        duration=GIF_DURATION_MS,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"✅ Saved {OUTPUT_FILE}  ({len(frames)} frames, "
          f"{len(frames) * GIF_DURATION_MS // 1000}s)")


if __name__ == "__main__":
    main()
