#!/usr/bin/env bash
# install-hooks.sh — Install git hooks for this repository.
#
# Installs a pre-commit hook that runs the TestDiscovery count checks.
# If any EXPECTED_TEST_COUNT has drifted, the commit is blocked so you
# can update the constant before proceeding.
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
# pre-commit — Run test-count discovery gate before committing.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
exec ./scripts/check-test-count.sh --quiet
EOF

chmod +x "$HOOK"
echo "✓ Installed $HOOK"
echo "  Test discovery counts will be checked before each commit."
