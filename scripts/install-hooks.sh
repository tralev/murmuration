#!/usr/bin/env bash
# install-hooks.sh — Install git hooks for this repository.
#
# Installs a pre-commit hook that:
#   1. Runs the TestDiscovery count check (prevents test-count drift).
#   2. Runs the full Python test suite (457 tests on 11 test modules).
# If either fails, the commit is blocked.
#
# Usage:
#   ./scripts/install-hooks.sh

set -euo pipefail
cd "$(dirname "$0")/.."

HOOK=".git/hooks/pre-commit"

if [ -f "$HOOK" ]; then
    echo "⚠  $HOOK already exists."
    echo "   Overwriting it. Your previous hook will be lost."
    echo "   To cancel: press Ctrl-C. To proceed: press Enter."
    read -r
fi

cat > "$HOOK" << 'EOF'
#!/usr/bin/env bash
# pre-commit — Test count gate → full test suite.
# If either stage fails, the commit is blocked.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  PRE-COMMIT  —  Stage 1/2  (test-count gate)               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
./scripts/check-test-count.sh --quiet
echo "  ✓ test counts consistent"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  PRE-COMMIT  —  Stage 2/2  (Python test suite)             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
python3 -m unittest \
    test_occlusion \
    test_boundary \
    test_presets \
    test_alg2 \
    test_cross_language \
    test_projection_model \
    test_spatial_model \
    test_input_handler \
    test_3d \
    test_features \
    extensions.test_extensions \
    --quiet 2>&1 || {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  COMMIT BLOCKED — tests failed.                             ║"
    echo "║  Fix the failing tests before committing.                   ║"
    echo "║  Use 'git commit --no-verify' to bypass (not recommended).  ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    exit 1
}

echo "  ✓ all 457 tests passed"
echo ""
EOF

chmod +x "$HOOK"
echo "✓ Installed $HOOK"
echo "  Pre-commit will now run: test-count gate → full test suite (457 tests)"
