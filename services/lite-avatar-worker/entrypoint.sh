#!/bin/bash
set -e

MODEL_DIR="/app/lite-avatar/weights"
MARKER_FILE="$MODEL_DIR/.downloaded"

mkdir -p "$MODEL_DIR"

if [ ! -f "$MARKER_FILE" ]; then
    echo "[entrypoint] Downloading LiteAvatar model weights (~5-8GB), first-run only..."
    cd /app/lite-avatar
    if [ -f "download_model.sh" ]; then
        bash download_model.sh
    else
        echo "[entrypoint] WARNING: download_model.sh not found in upstream repo. Skipping."
    fi
    touch "$MARKER_FILE"
    echo "[entrypoint] Model download complete"
else
    echo "[entrypoint] Model already downloaded, skipping"
fi

echo "[entrypoint] Starting LiteAvatar worker service..."
exec "$@"
