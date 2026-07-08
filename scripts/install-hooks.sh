#!/usr/bin/env bash
# install-hooks.sh — Install git hooks for this repository.
#
# Installs a pre-commit hook that:
#   1. Runs py_compile syntax check on all .py files.
#   2. Runs the TestDiscovery count check (prevents test-count drift).
#   3. Runs the full Python test suite (472 tests on 12 test modules).
# If any fails, the commit is blocked.
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
# pre-commit — Syntax check → test-count gate → full test suite.
# If any stage fails, the commit is blocked.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  PRE-COMMIT  —  Stage 1/3  (syntax check)                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
find . -name '*.py' \
    -not -path './.git/*' \
    -not -path './venv/*' \
    -not -path './__pycache__/*' \
    -print0 | xargs -0 -P 4 python3 -m py_compile 2>&1 || {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  COMMIT BLOCKED — syntax errors found above.                ║"
    echo "║  Fix the syntax errors before committing.                   ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    exit 1
}
echo "  ✓ syntax OK"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  PRE-COMMIT  —  Stage 2/3  (test-count gate)               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
./scripts/check-test-count.sh --quiet
echo "  ✓ test counts consistent"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  PRE-COMMIT  —  Stage 3/3  (Python test suite)             ║"
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
    test_help_overlay \
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

echo "  ✓ all 472 tests passed"
echo ""
EOF

chmod +x "$HOOK"
echo "✓ Installed $HOOK"
echo "  Pre-commit will now run: syntax check → test-count gate → full test suite (472 tests)"
