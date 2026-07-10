#!/usr/bin/env bash
# docker_test.sh — the project's Docker test gate. Builds the image, runs the
# unit tests inside it, and proves the 3D simulation launches headless (Xvfb +
# Mesa software GL). Host-side: needs the docker CLI, not a checkout inside the
# image.
#
# This is the single source of truth for "test the docker image"; CI's docker
# job calls it, and it can be run locally the same way.
#
# Usage:
#   ./docker_test.sh                 # tag: murmuration:test
#   ./docker_test.sh murmuration:ci  # custom image tag
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

IMAGE="${1:-murmuration:test}"

# ── 1/3  Build ──────────────────────────────────────────────────────
echo "── docker_test 1/3: build $IMAGE ──"
docker build -t "$IMAGE" .

# ── 2/3  Unit tests inside the image ────────────────────────────────
echo "── docker_test 2/3: unit tests inside the image ──"
docker run --rm "$IMAGE" python -m unittest test_3d test_science_3d test_ui_3d

# ── 3/3  Headless smoke-launch of the 3D simulation ─────────────────
#  The sim has no fixed exit, so run it for a few seconds and assert it reached
#  the main loop (printed its banner) without crashing on the ModernGL context.
echo "── docker_test 3/3: headless smoke-launch ──"
out=$(docker run --rm "$IMAGE" \
        timeout 15 xvfb-run -a python -u main_3d.py 2>&1 || true)
echo "$out"
if echo "$out" | grep -q "Murmuration 3D"; then
    echo "  ✓ simulation launched"
else
    echo "  ✗ simulation did not start"
    exit 1
fi
