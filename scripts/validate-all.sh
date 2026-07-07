#!/usr/bin/env bash
# validate-all.sh — Full validation pipeline
#
# Runs the complete test suite across all languages and environments:
#   1. Test count discovery gate (~1 ms)
#   2. Python tests (native)
#   3. Python tests (Docker)
#   4. GNU Octave tests (native or Docker)
#   5. Scilab tests (Docker)
#
# Stages that require unavailable tools (Docker, Octave) are skipped
# rather than treated as failures.  Only actual test FAILURES cause
# a non-zero exit.
#
# Usage:
#   ./scripts/validate-all.sh
#
# Environment variables:
#   SKIP_DOCKER=1    — skip all Docker-dependent stages
#   SKIP_OCTAVE=1    — skip the Octave stage
# ──────────────────────────────────────────────────────────────────────

set -euo pipefail
cd "$(dirname "$0")/.."

# ── Color helpers ────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'  # No Color

pass=0
skip=0
fail=0

_pass()   { echo -e "  ${GREEN}PASS${NC}  $*"; pass=$((pass + 1)); }
_skip()   { echo -e "  ${YELLOW}SKIP${NC}  $*"; skip=$((skip + 1)); }
_fail()   { echo -e "  ${RED}FAIL${NC}  $*"; fail=$((fail + 1)); }
_header() { echo -e "\n${BOLD}${CYAN}═══ $* ═══${NC}"; }

# ── Detect available tools ───────────────────────────────────────────
has_docker() {
    if [ "${SKIP_DOCKER:-0}" = "1" ]; then
        return 1
    fi
    docker compose version &>/dev/null
}

has_octave() {
    if [ "${SKIP_OCTAVE:-0}" = "1" ]; then
        return 1
    fi
    command -v octave &>/dev/null
}

echo -e "${BOLD}Murmuration — Full Validation Pipeline${NC}"
echo ""

# ══════════════════════════════════════════════════════════════════════
#  Stage 1 — Test count discovery gate
# ══════════════════════════════════════════════════════════════════════
_header "1/5  Test count gate"

if ./scripts/check-test-count.sh --quiet; then
    _pass "TestDiscovery counts match"
else
    _fail "TestDiscovery counts drifted — update EXPECTED_TEST_COUNT"
fi

# ══════════════════════════════════════════════════════════════════════
#  Stage 2 — Python tests (native)
# ══════════════════════════════════════════════════════════════════════
_header "2/5  Python tests (native)"

PYTEST_OUT="$(mktemp)"
if python3 -m unittest test_alg2 extensions.test_extensions -q > "$PYTEST_OUT" 2>&1; then
    _pass "Python unit tests"
else
    _fail "Python unit tests"
    echo ""
    tail -20 "$PYTEST_OUT" | sed 's/^/    /'
fi
rm -f "$PYTEST_OUT"

# ══════════════════════════════════════════════════════════════════════
#  Stage 3 — Python tests (Docker)
# ══════════════════════════════════════════════════════════════════════
_header "3/5  Python tests (Docker)"

if has_docker; then
    DOCKER_OUT="$(mktemp)"
    if docker compose run --rm tests > "$DOCKER_OUT" 2>&1; then
        tail -3 "$DOCKER_OUT"
        _pass "Python tests in Docker"
    else
        echo ""
        tail -20 "$DOCKER_OUT" | sed 's/^/    /'
        _fail "Python tests in Docker"
    fi
    rm -f "$DOCKER_OUT"
else
    _skip "Docker not available"
fi

# ══════════════════════════════════════════════════════════════════════
#  Stage 4 — GNU Octave tests
# ══════════════════════════════════════════════════════════════════════
_header "4/5  GNU Octave tests"

OCTAVE_TESTS=(
    "test_toroidal_wrap.m"
    "test_key_handler.m"
    "test_boundary_toggle.m"
)

if has_octave; then
    OCTAVE_BIN="$(command -v octave)"
    echo "  Octave: $OCTAVE_BIN"
    octave_ok=true
    for script in "${OCTAVE_TESTS[@]}"; do
        if [ ! -f "$script" ]; then
            echo "  ${YELLOW}WARN${NC}  Missing $script — skipping"
            continue
        fi
        OCT_OUT="$(mktemp)"
        printf "  %-35s " "$script"
        if octave --no-gui --silent "$script" > "$OCT_OUT" 2>&1; then
            echo -e "${GREEN}PASS${NC}"
        else
            echo -e "${RED}FAIL${NC}"
            tail -5 "$OCT_OUT" | sed 's/^/      /'
            octave_ok=false
        fi
        rm -f "$OCT_OUT"
    done
    if $octave_ok; then
        _pass "GNU Octave test scripts"
    else
        _fail "GNU Octave test scripts"
    fi
elif has_docker; then
    echo "  Running Octave tests via Docker..."
    docker_octave_ok=true
    for script in "${OCTAVE_TESTS[@]}"; do
        if [ ! -f "$script" ]; then
            continue
        fi
        DOCK_OCT_OUT="$(mktemp)"
        printf "  %-35s " "$script"
        if docker compose run --rm -T shell octave --no-gui --silent "$script" > "$DOCK_OCT_OUT" 2>&1; then
            echo -e "${GREEN}PASS${NC}"
        else
            echo -e "${RED}FAIL${NC}"
            tail -5 "$DOCK_OCT_OUT" | sed 's/^/      /'
            docker_octave_ok=false
        fi
        rm -f "$DOCK_OCT_OUT"
    done
    if $docker_octave_ok; then
        _pass "GNU Octave test scripts (Docker)"
    else
        _fail "GNU Octave test scripts (Docker)"
    fi
else
    _skip "Octave not installed and Docker not available"
fi

# ══════════════════════════════════════════════════════════════════════
#  Stage 5 — Scilab tests (Docker)
# ══════════════════════════════════════════════════════════════════════
_header "5/5  Scilab tests (Docker)"

SCILAB_TESTS=(
    "test_toroidal_wrap.sce"
    "test_key_handler.sce"
    "test_boundary_toggle.sce"
)

if has_docker; then
    scilab_ok=true
    for script in "${SCILAB_TESTS[@]}"; do
        if [ ! -f "$script" ]; then
            echo "  ${YELLOW}WARN${NC}  Missing $script — skipping"
            continue
        fi
        SCI_OUT="$(mktemp)"
        printf "  %-35s " "$script"
        if docker compose run --rm -T shell scilab-cli -nb -f "$script" > "$SCI_OUT" 2>&1; then
            echo -e "${GREEN}PASS${NC}"
        else
            echo -e "${RED}FAIL${NC}"
            tail -5 "$SCI_OUT" | sed 's/^/      /'
            scilab_ok=false
        fi
        rm -f "$SCI_OUT"
    done
    if $scilab_ok; then
        _pass "Scilab test scripts"
    else
        _fail "Scilab test scripts"
    fi
else
    _skip "Docker not available"
fi

# ══════════════════════════════════════════════════════════════════════
#  Summary
# ══════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}──────────────────────────────────────────────────────${NC}"
echo -e "${BOLD}  Results:${NC}  ${GREEN}${pass} passed${NC}  ${YELLOW}${skip} skipped${NC}  ${RED}${fail} failed${NC}"
echo -e "${BOLD}──────────────────────────────────────────────────────${NC}"

if [ "$fail" -gt 0 ]; then
    echo ""
    echo -e "${RED}Validation FAILED — ${fail} stage(s) have errors.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}All validations passed.${NC}"
exit 0
