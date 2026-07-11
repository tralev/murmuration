"""
Unit tests for simulation_3d.World — the headless per-frame update loop that
main_3d drives. No window, no GL context: pure numpy/scipy, so the flock-size
edits (+/-/R keys), the physics/metrics step, and the behavioural-dynamics
hooks (predator, roosting) are all exercised directly.
"""

import math
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np

from flock_core import NUM_BOIDS, DEPTH, MODE_SPATIAL
from simulation_3d import World
from predator_3d import Predator3D


class TestWorldFlockEdits(unittest.TestCase):
    """The +/-/R flock-size edits, factored out of main_3d's loop."""

    def test_add_grows_flock(self):
        w = World(num_boids=30)
        leftover = w.apply_flock_edits(0, 20, False)
        self.assertEqual(len(w.flock), 50)
        self.assertEqual(w.config.num_boids, 50)
        self.assertEqual(leftover, 0)

    def test_remove_keeps_at_least_one_and_returns_leftover(self):
        w = World(num_boids=25)
        leftover = w.apply_flock_edits(100, 0, False)   # ask to remove far too many
        self.assertEqual(len(w.flock), 1)               # never empties the flock
        self.assertEqual(leftover, 100 - 24)            # rest spread to later frames

    def test_remove_zero_when_single_bird(self):
        w = World(num_boids=1)
        leftover = w.apply_flock_edits(10, 0, False)
        self.assertEqual(len(w.flock), 1)
        self.assertEqual(leftover, 10)                  # nothing removable

    def test_reset_restores_default_and_rebuilds(self):
        w = World(num_boids=40)
        w.frame = 99
        old_grid = w.grid
        w.apply_flock_edits(0, 0, True)
        self.assertEqual(len(w.flock), NUM_BOIDS)
        self.assertEqual(w.config.num_boids, NUM_BOIDS)
        self.assertEqual(w.frame, 0)
        self.assertIsNot(w.grid, old_grid)              # grid rebuilt fresh

    def test_advance_consumes_add_and_reset(self):
        w = World(num_boids=20)
        pr, pa, prs = w.advance(1 / 60, pending_remove=0, pending_add=5,
                                pending_reset=False)
        self.assertEqual((pr, pa, prs), (0, 0, False))
        self.assertEqual(len(w.flock), 25)


class TestWorldStep(unittest.TestCase):
    def test_step_advances_frame_and_metrics(self):
        w = World(num_boids=40)
        w.step(1 / 60)
        self.assertEqual(w.frame, 1)
        # A metric was folded in (order parameter is a finite number in [0, 1]).
        self.assertGreaterEqual(w.metrics.order_param, 0.0)
        self.assertLessEqual(w.metrics.order_param, 1.0)

    def test_predator_changes_the_trajectory(self):
        """A predator in ext must perturb the flock — same seed, with vs
        without a predator, diverges."""
        base = World(num_boids=60, config=_seeded_config(1))
        pred = World(num_boids=60, config=_seeded_config(1))
        # Re-seed identically so the two flocks start bit-identical.
        _reseed_flock(base, 1)
        _reseed_flock(pred, 1)
        pred.ext["predator"] = Predator3D(pos=tuple(pred.flock[0].pos),
                                          vel=(0, 0, 0))
        for _ in range(8):
            base.step(1 / 60)
            pred.step(1 / 60)
        pb = np.array([b.pos for b in base.flock])
        pp = np.array([b.pos for b in pred.flock])
        self.assertGreater(np.abs(pb - pp).max(), 1.0)   # predator moved birds

    def test_roosting_advances_clock_and_pulls_down(self):
        w = World(num_boids=80)
        w.ext["roosting"] = True
        w.ext["hour"] = 20.0                              # after sunset → strong pull
        z0 = np.mean([b.pos[2] for b in w.flock])
        for _ in range(40):
            w.step(0.2)
        z1 = np.mean([b.pos[2] for b in w.flock])
        self.assertNotEqual(w.ext["hour"], 20.0)         # day clock advanced
        self.assertLess(z1, z0)                          # descended toward the roost


def _seeded_config(seed):
    import random
    from flock_core import Config
    random.seed(seed)
    np.random.seed(seed)
    return Config()


def _reseed_flock(world, seed):
    import random
    from boid_3d import Boid3D
    random.seed(seed)
    np.random.seed(seed)
    world.flock = [Boid3D() for _ in range(len(world.flock))]


# ══════════════════════════════════════════════════════════════════════
#  Discovery gate (tests.md §3.1)
# ══════════════════════════════════════════════════════════════════════

class TestDiscovery(unittest.TestCase):
    EXPECTED = 9

    def test_module_test_count(self):
        import test_simulation_3d as m
        n = unittest.TestLoader().loadTestsFromModule(m).countTestCases()
        self.assertEqual(n, self.EXPECTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
