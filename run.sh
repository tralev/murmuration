#!/usr/bin/env bash
# run.sh — Start the murmuration simulation (native Python)
#
# This script handles virtual environment setup and dependency installation
# so students can run the simulation with a single command.
#
# Usage:
#   ./run.sh              — full simulation (alg2.py)
#   ./run.sh simple       — minimal version for learning (alg_simple.py)
#   ./run.sh tests        — run unit tests
#
# Requirements: Python 3.7+, pip
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

# ── Choose what to run ───────────────────────────────────────────────
MODE="${1:-full}"
case "$MODE" in
    simple)  SCRIPT="alg_simple.py"; ARGS=() ;;
    tests)   SCRIPT="-m"; ARGS=("unittest" "test_alg2" "-v") ;;
    full|*)  SCRIPT="alg2.py"; ARGS=() ;;
esac

# ── Set up virtual environment (if not already active) ───────────────
if [ -z "${VIRTUAL_ENV:-}" ]; then
    if [ ! -d "venv" ]; then
        echo "→ Creating virtual environment..."
        python3 -m venv venv
    fi
    echo "→ Activating virtual environment..."
    source venv/bin/activate
fi

# ── Install dependencies ─────────────────────────────────────────────
if ! python3 -c "import pygame" 2>/dev/null; then
    echo "→ Installing pygame..."
    pip install -q pygame
fi

# ── Create output directory for CSV metrics ──────────────────────────
mkdir -p output

# ── Run ───────────────────────────────────────────────────────────────
echo ""
if [ "$MODE" = "tests" ]; then
    echo "═══════════════════════════════════════════════════════════"
    echo "  Running unit tests..."
    echo "═══════════════════════════════════════════════════════════"        python3 "$SCRIPT" "${ARGS[@]}"
else
    echo "═══════════════════════════════════════════════════════════"
    echo "  Murmuration — Bird Flock Simulation"
    echo "  Press M to switch modes, H for help, ESC to quit"
    echo "  CSV metrics → output/murmuration_metrics.csv"
    echo "═══════════════════════════════════════════════════════════"
    echo ""        python3 "$SCRIPT"
fi
