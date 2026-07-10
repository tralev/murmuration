#!/usr/bin/env bash
# run_tests.sh — the project's Python test gate: a syntax check of every module
# plus the 3D unit tests (test_3d, test_science_3d). Pure numpy/scipy — no GPU
# or display required.
#
# This is the single source of truth for "run the tests"; the pre-commit hook,
# CI (.github/workflows/test.yml) and the docker `tests` service all call it, so
# the gate is defined in exactly one place.
#
# Usage:
#   ./run_tests.sh            # normal run
#   ./run_tests.sh -v         # verbose (extra args pass through to unittest)
#   ./run_tests.sh --quiet    # quiet
#
# Env:
#   RUN_SLOW_TESTS=1          # also run the ~25s gated integration tests
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 1/2  Syntax check — compile every module ────────────────────────
echo "── run_tests 1/2: syntax check ──"
find . -name '*.py' \
    -not -path './.git/*' \
    -not -path './venv/*' \
    -not -path './__pycache__/*' \
    -not -path './sci/*' \
    -print0 | xargs -0 -P 4 python3 -m py_compile
echo "  ✓ syntax OK"

# ── 2/2  Unit tests ─────────────────────────────────────────────────
#  test_3d / test_science_3d are pure numpy/scipy; test_ui_3d also needs
#  pygame + glm + moderngl importable, but no display or GL context (events
#  are mocked, the camera is pure maths). None open a window.
echo "── run_tests 2/2: unit tests (test_3d, test_science_3d, test_ui_3d) ──"
SDL_VIDEODRIVER=dummy python3 -m unittest test_3d test_science_3d test_ui_3d "$@"
echo "  ✓ tests passed"
