#!/usr/bin/env bash
# run-experiment.sh — Run a FaultForge experiment from inside Docker.
#
# Usage:
#   ./scripts/run-experiment.sh experiments/etcd-stale-read.yaml
#   ./scripts/run-experiment.sh experiments/etcd-stale-read.yaml --dry-run
#
# Requirements:
#   - Docker socket at /var/run/docker.sock
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

IMAGE_NAME="faultforge"
EXPERIMENT="${1:?Usage: $0 <experiment.yaml> [--dry-run]}"
shift
EXTRA_ARGS="$*"

# Build image if not present
if ! docker image inspect "$IMAGE_NAME:latest" >/dev/null 2>&1; then
    echo "Building $IMAGE_NAME image..."
    docker build -t "$IMAGE_NAME" -f "$PROJECT_DIR/faultforge/Dockerfile" "$PROJECT_DIR"
fi

# Verify Docker socket
if [ ! -S /var/run/docker.sock ]; then
    echo "ERROR: Docker socket not found at /var/run/docker.sock"
    exit 1
fi

RESULTS_DIR="$PROJECT_DIR/faultforge/results"
mkdir -p "$RESULTS_DIR"

echo "Running experiment: $EXPERIMENT"
echo "Extra args: $EXTRA_ARGS"
echo "Results will be written to: $RESULTS_DIR"

docker run --rm \
    --network host \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$HOME/workdir:/root/workdir" \
    -v "$PROJECT_DIR/faultforge/experiments:/app/experiments:ro" \
    -v "$PROJECT_DIR/faultforge/oracles:/app/oracles:ro" \
    -v "$RESULTS_DIR:/app/results" \
    -e HOME=/root \
    "$IMAGE_NAME" \
    experiment "$EXPERIMENT" --output-dir /app/results $EXTRA_ARGS
