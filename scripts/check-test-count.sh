#!/usr/bin/env bash
# check-test-count.sh — Fast discovery gate for test count regressions.
#
# Runs only the TestDiscovery classes to verify EXPECTED_TEST_COUNT
# constants haven't drifted, before running the full (expensive) suite.
#
# Exit 0 if counts match, non-zero if they don't.
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

if $QUIET; then
    python3 -m unittest test_alg2.TestDiscovery extensions.test_extensions.TestDiscovery -q > /dev/null 2>&1
else
    echo "→ Checking test counts..."
    python3 -m unittest test_alg2.TestDiscovery extensions.test_extensions.TestDiscovery -v
    echo "✓ Test counts verified"
fi
