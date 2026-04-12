#!/bin/bash
set -e

MODEL_DIR="/app/lite-avatar/weights"
MARKER_FILE="$MODEL_DIR/.downloaded"

mkdir -p "$MODEL_DIR"

# Dev/CI escape hatch: skip the 5-8GB model download so the FastAPI
# wrapper can be exercised on machines where real inference is not the
# goal (e.g. Apple Silicon where the arm64 image can boot the server
# but cannot run LiteAvatar's AVX2-dependent kernels at useful speed).
#
# When set, /health and /avatars still work and /generate will return a
# 404 for any avatar that isn't on disk. Inference paths will fail —
# that's expected; use a real x86_64 VPS for end-to-end smoke testing.
if [ "${SKIP_MODEL_DOWNLOAD:-0}" = "1" ]; then
    echo "[entrypoint] SKIP_MODEL_DOWNLOAD=1 — skipping model weights download (dev/CI mode)"
elif [ ! -f "$MARKER_FILE" ]; then
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
