"""
╔══════════════════════════════════════════════════════════════════════╗
║  3D UI / INFRASTRUCTURE UNIT TESTS                                  ║
╚══════════════════════════════════════════════════════════════════════╝

 Tests for the non-science 3D stack — the parts that talk to Pygame / glm /
 ModernGL but can still be exercised *without a display or GL context*:

   • camera_3d.OrbitCamera   — pure view/projection math (glm)
   • input_handler_3d        — keyboard/mouse handling, via mocked events
   • shaders_3d              — mesh arrays + GLSL source strings
   • features               — feature-flag defaults

 These need pygame / glm / moderngl importable (they are in the Docker image
 and any full install), but never open a window or a GL context — event
 handling is driven by mocked ``pygame.event.get`` and the camera is pure
 maths. The science tests live in test_3d.py / test_science_3d.py.
"""

import os
import types
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np


# ══════════════════════════════════════════════════════════════════════
#  camera_3d — OrbitCamera (pure glm math, no GL state)
# ══════════════════════════════════════════════════════════════════════

class TestOrbitCamera(unittest.TestCase):
    def _cam(self):
        from camera_3d import OrbitCamera
        return OrbitCamera(target=(500, 350, 200))

    def test_defaults_and_reset(self):
        import math
        cam = self._cam()
        cam.rotate(1.0, 0.3)
        cam.zoom(5.0)
        cam.reset()
        self.assertAlmostEqual(cam.azimuth, math.radians(45), places=5)
        self.assertAlmostEqual(cam.elevation, math.radians(30), places=5)
        self.assertAlmostEqual(cam.distance, 1200.0, places=3)

    def test_rotate_clamps_elevation(self):
        import math
        cam = self._cam()
        cam.rotate(0.0, +10.0)                       # way past the top
        self.assertLessEqual(cam.elevation, math.pi / 2 - 0.05 + 1e-9)
        cam.rotate(0.0, -20.0)                        # way past the bottom
        self.assertGreaterEqual(cam.elevation, -math.pi / 2 + 0.05 - 1e-9)

    def test_rotate_advances_azimuth(self):
        cam = self._cam()
        a0 = cam.azimuth
        cam.rotate(0.5, 0.0)
        self.assertAlmostEqual(cam.azimuth, a0 + 0.5, places=6)

    def test_zoom_clamps_distance(self):
        cam = self._cam()
        cam.zoom(1e6)                                # zoom in hard
        self.assertAlmostEqual(cam.distance, cam.min_distance, places=3)
        cam.zoom(-1e6)                               # zoom out hard
        self.assertAlmostEqual(cam.distance, cam.max_distance, places=3)

    def test_zoom_delta_direction(self):
        cam = self._cam()
        d0 = cam.distance
        cam.zoom(1.0)                                # positive delta → closer
        self.assertLess(cam.distance, d0)

    def test_auto_rotate_toggle_and_step(self):
        cam = self._cam()
        self.assertFalse(cam.auto_rotate)
        self.assertTrue(cam.toggle_auto_rotate())    # returns new state
        a0 = cam.azimuth
        cam.step_auto_rotate(1.0)                     # 1 s advances azimuth
        self.assertAlmostEqual(cam.azimuth, a0 + cam.AUTO_ROTATE_SPEED, places=6)
        cam.toggle_auto_rotate()                      # off again
        a1 = cam.azimuth
        cam.step_auto_rotate(1.0)                      # no-op when off
        self.assertAlmostEqual(cam.azimuth, a1, places=9)

    def test_position_matches_spherical(self):
        import math
        cam = self._cam()
        p = cam.position()
        # z = target.z + distance·sin(elevation)
        self.assertAlmostEqual(
            p.z, 200 + cam.distance * math.sin(cam.elevation), places=2)

    def test_matrices_are_4x4(self):
        import glm
        cam = self._cam()
        v = cam.view_matrix()
        pj = cam.projection_matrix(aspect=1.5)
        self.assertIsInstance(v, glm.mat4)
        self.assertIsInstance(pj, glm.mat4)


# ══════════════════════════════════════════════════════════════════════
#  input_handler_3d — keyboard/mouse handling via mocked pygame events
# ══════════════════════════════════════════════════════════════════════

def _key(k):
    import pygame
    return types.SimpleNamespace(type=pygame.KEYDOWN, key=k)


def _run(events, config=None, camera=None, ext=None,
         running=True, paused=False, show_grid=False,
         pending_remove=0, pending_add=0, pending_reset=False):
    """Drive handle_input once with a mocked event queue. Returns
    (result_tuple, config, camera, ext)."""
    from input_handler_3d import handle_input
    from flock_core import Config
    from camera_3d import OrbitCamera
    if config is None:
        config = Config()
    if camera is None:
        camera = OrbitCamera()
    if ext is None:
        ext = {}
    with mock.patch("pygame.event.get", return_value=events), \
            mock.patch("pygame.mouse.get_pos", return_value=(10, 20)):
        result = handle_input(config, [], running, paused, camera,
                              pending_remove, pending_add, pending_reset,
                              show_grid, ext)
    return result, config, camera, ext


class TestInputHandler3D(unittest.TestCase):
    def test_quit_event_stops_running(self):
        import pygame
        quit_ev = types.SimpleNamespace(type=pygame.QUIT)
        result, *_ = _run([quit_ev])
        self.assertFalse(result[0])                   # running

    def test_escape_stops_running(self):
        import pygame
        result, *_ = _run([_key(pygame.K_ESCAPE)])
        self.assertFalse(result[0])

    def test_space_toggles_pause(self):
        import pygame
        result, *_ = _run([_key(pygame.K_SPACE)], paused=False)
        self.assertTrue(result[1])                    # paused

    def test_r_sets_pending_reset(self):
        import pygame
        result, *_ = _run([_key(pygame.K_r)])
        self.assertTrue(result[4])                    # pending_reset

    def test_m_toggles_mode(self):
        import pygame
        from flock_core import Config
        cfg = Config()
        m0 = cfg.mode
        _run([_key(pygame.K_m)], config=cfg)
        self.assertEqual(cfg.mode, 1 - m0)

    def test_g_toggles_grid(self):
        import pygame
        result, *_ = _run([_key(pygame.K_g)], show_grid=False)
        self.assertTrue(result[5])                    # show_grid

    def test_arrows_tune_phi(self):
        import pygame
        from flock_core import Config
        cfg = Config()
        p0, a0 = cfg.phi_p, cfg.phi_a
        _run([_key(pygame.K_UP)], config=cfg)
        self.assertAlmostEqual(cfg.phi_p, min(1.0, p0 + 0.01), places=6)
        _run([_key(pygame.K_LEFT)], config=cfg)
        self.assertAlmostEqual(cfg.phi_a, max(0.0, a0 - 0.01), places=6)

    def test_phi_p_clamped_at_zero(self):
        import pygame
        from flock_core import Config
        cfg = Config()
        cfg.phi_p = 0.0
        _run([_key(pygame.K_DOWN)], config=cfg)
        self.assertGreaterEqual(cfg.phi_p, 0.0)

    def test_brackets_tune_sigma(self):
        import pygame
        from flock_core import Config
        cfg = Config()
        s0 = cfg.sigma
        _run([_key(pygame.K_RIGHTBRACKET)], config=cfg)
        self.assertEqual(cfg.sigma, min(20, s0 + 1))
        _run([_key(pygame.K_LEFTBRACKET)], config=cfg)
        self.assertEqual(cfg.sigma, s0)

    def test_plus_minus_flock_size(self):
        import pygame
        add, *_ = _run([_key(pygame.K_EQUALS)])
        self.assertEqual(add[3], 10)                  # pending_add
        rem, *_ = _run([_key(pygame.K_MINUS)])
        self.assertEqual(rem[2], 10)                  # pending_remove

    def test_u_toggles_refinements(self):
        import pygame
        from flock_core import Config
        cfg = Config()
        r0 = cfg.refinements
        _run([_key(pygame.K_u)], config=cfg)
        self.assertEqual(cfg.refinements, not r0)

    def test_t_spawns_and_removes_predator(self):
        import pygame
        ext = {"predator": None}
        _run([_key(pygame.K_t)], ext=ext)
        self.assertIsNotNone(ext["predator"])         # spawned
        _run([_key(pygame.K_t)], ext=ext)
        self.assertIsNone(ext["predator"])            # removed

    def test_k_toggles_roosting(self):
        import pygame
        ext = {}
        _run([_key(pygame.K_k)], ext=ext)
        self.assertTrue(ext["roosting"])

    def test_preset_key_applies(self):
        import pygame
        from flock_core import Config
        cfg = Config()
        _run([_key(pygame.K_b)], config=cfg)          # 'b' = Ball of Birds
        self.assertAlmostEqual(cfg.phi_p, 0.18)

    def test_scroll_zooms_camera(self):
        import pygame
        from camera_3d import OrbitCamera
        cam = OrbitCamera()
        d0 = cam.distance
        scroll_in = types.SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, button=4)
        _run([scroll_in], camera=cam)
        self.assertLess(cam.distance, d0)

    def test_drag_rotates_camera(self):
        import pygame
        from camera_3d import OrbitCamera
        cam = OrbitCamera()
        a0 = cam.azimuth
        down = types.SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, button=1)
        move = types.SimpleNamespace(type=pygame.MOUSEMOTION,
                                     buttons=(1, 0, 0), pos=(120, 20))
        _run([down, move], camera=cam)
        self.assertNotAlmostEqual(cam.azimuth, a0, places=6)

    def test_returns_six_tuple(self):
        import pygame
        result, *_ = _run([_key(pygame.K_SPACE)])
        self.assertEqual(len(result), 6)


# ══════════════════════════════════════════════════════════════════════
#  shaders_3d — bird mesh arrays + GLSL source strings
# ══════════════════════════════════════════════════════════════════════

class TestShaders3D(unittest.TestCase):
    def test_bird_mesh_arrays(self):
        import shaders_3d as s
        self.assertEqual(s.BIRD_VERTS.shape[1], 3)          # xyz per vertex
        self.assertEqual(s.BIRD_NORMALS.shape, s.BIRD_VERTS.shape)
        self.assertGreater(len(s.BIRD_INDICES), 0)
        # every index refers to a real vertex
        self.assertLess(int(np.max(s.BIRD_INDICES)), len(s.BIRD_VERTS))
        self.assertGreater(s.BIRD_SCALE, 0)

    def test_glsl_sources_are_complete(self):
        import shaders_3d as s
        for name in ("VERTEX_SHADER", "FRAGMENT_SHADER",
                     "GRID_VERTEX_SHADER", "GRID_FRAGMENT_SHADER"):
            src = getattr(s, name)
            self.assertIsInstance(src, str)
            self.assertIn("#version", src)              # a real GLSL header
            self.assertIn("main", src)                  # has an entry point


# ══════════════════════════════════════════════════════════════════════
#  features — flag defaults
# ══════════════════════════════════════════════════════════════════════

class TestFeatures(unittest.TestCase):
    def test_flocking_flags_default_on(self):
        import features
        self.assertTrue(features.ENABLE_PROJECTION_MODE)
        self.assertTrue(features.ENABLE_SPATIAL_MODE)
        for flag in ("ENABLE_PROJECTION_MODE", "ENABLE_SPATIAL_MODE"):
            self.assertIsInstance(getattr(features, flag), bool)


if __name__ == "__main__":
    unittest.main(verbosity=2)
