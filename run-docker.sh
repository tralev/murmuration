#!/usr/bin/env bash
# run-docker.sh — Start the murmuration simulation via Docker
#
# No Python or Pygame installation needed — just Docker.
#
# Usage:
#   ./run-docker.sh              — full simulation (builds image, runs headless)
#   ./run-docker.sh tests        — run unit tests in container
#   ./run-docker.sh extended     — extended simulation (all modules active)
#   ./run-docker.sh shell        — open a bash shell in the container
#   ./run-docker.sh octave       — open GNU Octave interactive CLI in container
#   ./run-docker.sh scilab       — open Scilab interactive CLI in container
#   ./run-docker.sh validate-all — full multi-stage validation pipeline
#   ./run-docker.sh stop         — stop and remove the container + image
#
# Requirements: Docker with compose plugin, or docker-compose standalone
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-sim}"

# ── Detect compose command ────────────────────────────────────────────
if docker compose version &>/dev/null; then
    COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE="docker-compose"
else
    echo "ERROR: Neither 'docker compose' nor 'docker-compose' found."
    echo "Install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# ── Create output directory (needed for volume mount) ─────────────────
mkdir -p output

case "$MODE" in
    tests)
        echo "═══════════════════════════════════════════════════════════"
        echo "  Running the full Python test suite in Docker (600 tests)..."
        echo "═══════════════════════════════════════════════════════════"
        $COMPOSE build shell 2>&1 | tail -3
        # Run the full canonical module list (not just the 2-module compose
        # service) so `tests` matches CI and the pre-commit hook.
        # -T disables TTY allocation so output streams correctly when the
        # command is piped or run non-interactively.
        $COMPOSE run --rm -T \
            -e SDL_VIDEODRIVER=dummy -e SDL_AUDIODRIVER=dummy \
            shell python -m unittest \
                test_occlusion test_boundary test_presets test_alg2 \
                test_cross_language test_projection_model test_spatial_model \
                test_input_handler test_3d test_features test_help_overlay \
                extensions.test_extensions
        ;;

    shell)
        echo "→ Opening bash shell in the murmuration container..."
        echo "  (type 'exit' to leave)"
        $COMPOSE build shell 2>&1
        $COMPOSE run --rm shell
        ;;

    octave)
        echo "→ Opening GNU Octave CLI in the murmuration container..."
        echo "  (type 'exit' to leave)"
        $COMPOSE build shell 2>&1
        $COMPOSE run --rm octave
        ;;

    scilab)
        echo "→ Opening Scilab CLI in the murmuration container..."
        echo "  (type 'exit' to leave)"
        $COMPOSE build shell 2>&1
        $COMPOSE run --rm scilab
        ;;

    validate-all)
        echo "═══════════════════════════════════════════════════════════"
        echo "  Full Validation Pipeline (all languages, all environments)"
        echo "═══════════════════════════════════════════════════════════"
        echo ""
        if [ -x scripts/validate-all.sh ]; then
            scripts/validate-all.sh
        else
            echo "ERROR: scripts/validate-all.sh not found or not executable."
            exit 1
        fi
        ;;

    stop)
        echo "→ Stopping and cleaning up..."
        $COMPOSE down --rmi local 2>/dev/null || true
        docker rm -f murmuration 2>/dev/null || true
        echo "Done."
        ;;

    extended)
        echo "═══════════════════════════════════════════════════════════"
        echo "  Murmuration EXTENDED — roadmap extensions active (Docker)"
        echo "  Direct-velocity + steric + blind-angle + anisotropic +"
        echo "  predator + spatial-optimisation chain, multi-viewpoint Θ',"
        echo "  and correlation-time τᵨ. Headless with virtual display."
        echo "  CSV metrics → output/murmuration_metrics_extended.csv"
        echo "  Press Ctrl+C to stop"
        echo "═══════════════════════════════════════════════════════════"
        echo ""
        $COMPOSE build shell 2>&1 | tail -3
        echo ""
        docker run --rm \
            -v "$PWD/output:/app/output" \
            -e SDL_VIDEODRIVER=dummy \
            -e SDL_AUDIODRIVER=dummy \
            -e PYTHONUNBUFFERED=1 \
            murmuration:latest python -m extensions.extended_simulation
        ;;

    sim|*)
        echo "═══════════════════════════════════════════════════════════"
        echo "  Murmuration — Bird Flock Simulation  (Docker)"
        echo "  Running headless with virtual display..."
        echo "  CSV metrics → output/murmuration_metrics.csv"
        echo "  Press Ctrl+C to stop"
        echo "═══════════════════════════════════════════════════════════"
        echo ""
        $COMPOSE build shell 2>&1 | tail -3
        echo ""
        # Run the simulation directly (not via compose up — gives better logs)
        docker run --rm \
            -v "$PWD/output:/app/output" \
            -e SDL_VIDEODRIVER=dummy \
            -e SDL_AUDIODRIVER=dummy \
            -e PYTHONUNBUFFERED=1 \
            murmuration:latest python alg2.py
        ;;
esac
