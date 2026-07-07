#!/usr/bin/env bash
# check-test-count.sh — Fast discovery gate for test count regressions.
#
# Runs only the TestDiscovery classes to verify EXPECTED_TEST_COUNT
# constants haven't drifted, before running the full (expensive) suite.
#
# Covers all 10 test modules that define TestDiscovery (see list below).
# Exit 0 if all counts match, non-zero if any don't.
#
# Usage:
#   ./scripts/check-test-count.sh          # human-readable
#   ./scripts/check-test-count.sh --quiet  # CI mode (no output on success)

set -euo pipefail
cd "$(dirname "$0")/.."

QUIET=false
if [ "${1:-}" = "--quiet" ]; then
    QUIET=true
fi

# Every test module that carries a TestDiscovery + EXPECTED_TEST_COUNT.
# Ordered the same as the full-suite invocation.
MODULES=(
    test_occlusion.TestDiscovery
    test_boundary.TestDiscovery
    test_presets.TestDiscovery
    test_cross_language.TestDiscovery
    test_projection_model.TestDiscovery
    test_spatial_model.TestDiscovery
    test_input_handler.TestDiscovery
    test_3d.TestDiscovery
    test_features.TestDiscovery
    extensions.test_extensions.TestDiscovery
)

if $QUIET; then
    python3 -m unittest "${MODULES[@]}" -q > /dev/null 2>&1
else
    echo "→ Checking test counts across ${#MODULES[@]} modules..."
    python3 -m unittest "${MODULES[@]}" -v
    echo "✓ All test counts verified"
fi
