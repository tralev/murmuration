"""
Headless GL smoke tests for renderer_3d (the ModernGL offscreen path that
capture_3d builds on).

These are the only tests that create a real GL context. They render into
the offscreen FBO (`Renderer3D(..., headless=True)`) — no window, no
display — so they run on any dev machine whose driver can create a
standalone ModernGL context (macOS included). Where that fails (bare CI
runners without GL) the whole module skips cleanly, and the renderer is
covered by the Docker smoke-launch instead (tests.md §5).

Run directly:  python3 -m unittest test_render_3d -v
"""

import os
import types
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np


def _stub(pos, vel):
    """Minimal bird for the instanced renderer: indexable .pos/.vel."""
    return types.SimpleNamespace(pos=np.array(pos, dtype=np.float32),
                                 vel=np.array(vel, dtype=np.float32))


class TestRenderer3DHeadless(unittest.TestCase):
    """One real frame through the full pipeline (shaders, instanced birds,
    grid, FBO read-back), plus the instance-buffer and capture guards."""

    @classmethod
    def setUpClass(cls):
        try:
            from renderer_3d import Renderer3D
        except Exception as exc:                 # moderngl/glm missing
            raise unittest.SkipTest(f"renderer imports unavailable: {exc}")
        try:
            cls.renderer = Renderer3D(64, 48, headless=True)
        except Exception as exc:                 # no GL driver (bare CI)
            raise unittest.SkipTest(f"no headless GL context: {exc}")

    def test_frame_renders_nonuniform_pixels(self):
        """Birds at the camera target + the reference grid must leave
        visibly brighter-than-background pixels in the captured frame."""
        r = self.renderer
        flock = [_stub((450 + 10 * i, 350, 200), (4, 0, 0))
                 for i in range(10)]
        r.begin_frame()
        r.draw_birds(flock)
        r.draw_grid()
        r.end_frame()
        img = r.capture_frame()
        self.assertEqual(img.size, (64, 48))
        arr = np.asarray(img)
        self.assertEqual(arr.shape, (48, 64, 3))
        self.assertGreater(len(np.unique(arr.reshape(-1, 3), axis=0)), 1)
        self.assertGreater(int(arr.max()), 40)   # clear colour tops out ~36

    def test_instance_buffer_grows_on_demand(self):
        r = self.renderer
        needed = r.max_instances + 1
        flock = [_stub((500, 350, 200), (4, 0, 0))] * needed
        self.assertEqual(r.update_instances(flock), needed)
        self.assertGreaterEqual(r.max_instances, needed)

    def test_capture_requires_headless(self):
        from renderer_3d import Renderer3D
        windowed = Renderer3D(32, 24, headless=False)
        with self.assertRaises(RuntimeError):
            windowed.capture_frame()

    def test_update_instances_packs_pos_and_vel(self):
        """update_instances must copy each bird's pos+vel into the six-float
        instance rows in order."""
        r = self.renderer
        flock = [_stub((1, 2, 3), (4, 5, 6)),
                 _stub((7, 8, 9), (10, 11, 12))]
        count = r.update_instances(flock)
        self.assertEqual(count, 2)
        np.testing.assert_allclose(r.instance_data[0], [1, 2, 3, 4, 5, 6])
        np.testing.assert_allclose(r.instance_data[1], [7, 8, 9, 10, 11, 12])

    def test_resize_updates_dimensions_and_viewport(self):
        from renderer_3d import Renderer3D
        r = Renderer3D(48, 32, headless=True)
        r.resize(96, 72)
        self.assertEqual((r.width, r.height), (96, 72))
        self.assertEqual(tuple(r.ctx.viewport), (0, 0, 96, 72))


# ══════════════════════════════════════════════════════════════════════
#  Discovery gate (tests.md §3.1)
# ══════════════════════════════════════════════════════════════════════

class TestDiscovery(unittest.TestCase):
    """Pinned test count — a renamed or mis-indented test silently drops
    out of unittest discovery; this fails loudly instead. Update the pin
    when tests are deliberately added or removed."""

    EXPECTED = 6

    def test_module_test_count(self):
        import test_render_3d as m
        n = unittest.TestLoader().loadTestsFromModule(m).countTestCases()
        self.assertEqual(n, self.EXPECTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
