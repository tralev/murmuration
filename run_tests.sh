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
#   COVERAGE=1                # run the unit tests under coverage and enforce
#                             # a minimum (COVERAGE_MIN, default 95%). Needs the
#                             # `coverage` package; CI sets this.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 1/2  Syntax check — compile every module ────────────────────────
echo "── run_tests 1/2: syntax check ──"
find . -name '*.py' \
    -not -path './.git/*' \
    -not -path './venv/*' \
    -not -path './__pycache__/*' \
    -not -path './sci/*' \
    -not -path './google_site/*' \
    -print0 | xargs -0 -P 4 python3 -m py_compile
echo "  ✓ syntax OK"

# ── 2/2  Unit tests ─────────────────────────────────────────────────
#  test_3d / test_science_3d / test_simulation_3d / test_docs_3d are pure
#  numpy/scipy; test_ui_3d also needs pygame + glm + moderngl importable, but
#  no display or GL context (events are mocked, the camera is pure maths).
#  test_render_3d renders into an offscreen ModernGL FBO — still no window —
#  and skips itself cleanly where no GL driver exists (bare CI runners). None
#  open a window.
MODULES="test_3d test_science_3d test_ui_3d test_render_3d test_simulation_3d test_docs_3d"
COVERAGE_MIN="${COVERAGE_MIN:-95}"

if [ "${COVERAGE:-0}" = "1" ]; then
  echo "── run_tests 2/2: unit tests under coverage (min ${COVERAGE_MIN}%) ──"
  SDL_VIDEODRIVER=dummy python3 -m coverage run -m unittest $MODULES "$@"
  # Enforce a floor over the headless-testable code. The three GL-context
  # modules (renderer_3d, main_3d, capture_3d) are omitted: they need a live
  # OpenGL context, so their unit test (test_render_3d) self-skips on a bare
  # CI runner — leaving them imported-but-unexecuted, which would drag the
  # floor down. They are instead exercised by the Docker smoke-launch job.
  GL_OMIT="renderer_3d.py,main_3d.py,capture_3d.py"
  python3 -m coverage report --omit="venv/*,test_*,$GL_OMIT" --fail-under="$COVERAGE_MIN"
  echo "  ✓ tests passed (coverage ≥ ${COVERAGE_MIN}%)"
else
  echo "── run_tests 2/2: unit tests ($MODULES) ──"
  SDL_VIDEODRIVER=dummy python3 -m unittest $MODULES "$@"
  echo "  ✓ tests passed"
fi
