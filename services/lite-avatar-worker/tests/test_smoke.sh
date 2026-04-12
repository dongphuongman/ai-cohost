#!/bin/bash
# Smoke test for LiteAvatar worker service.
#
# PREREQUISITES — this script only succeeds when:
#   1. The worker container is running AND healthy
#      (standalone: `cd services/lite-avatar-worker && docker compose up -d`
#       main infra: `docker compose --profile lite-avatar up -d lite-avatar-worker`)
#   2. Model weights have finished downloading on first boot (~5-10 min).
#      Watch `docker logs -f lite-avatar-worker` for "Model download complete".
#   3. At least one avatar folder exists under services/lite-avatar-worker/avatars/
#      (download from https://modelscope.cn/models/HumanAIGC-Engineering/LiteAvatarGallery).
#
# Without those preconditions the test will fail fast at step [2/5] with a
# "no avatars loaded" message — that is expected, not a bug.
#
# Default BASE_URL targets the main infra compose mapping (host 8088 → container
# 8080; adminer owns host 8080). Override with LITE_AVATAR_URL=... for other
# setups (standalone compose, remote VPS, etc.).

set -e

BASE_URL="${LITE_AVATAR_URL:-http://localhost:8088}"

echo "=== Smoke Test: LiteAvatar Worker ==="
echo "Base URL: $BASE_URL"
echo ""

# Test 1: Health check ------------------------------------------------------
echo "[1/5] Health check..."
HEALTH=$(curl -sf "$BASE_URL/health")
echo "$HEALTH" | python3 -m json.tool
echo ""

# Test 2: List avatars ------------------------------------------------------
echo "[2/5] List avatars..."
AVATARS=$(curl -sf "$BASE_URL/avatars")
echo "$AVATARS" | python3 -m json.tool
AVATAR_COUNT=$(echo "$AVATARS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['avatars']))")
echo "Found $AVATAR_COUNT avatars"
echo ""

if [ "$AVATAR_COUNT" -eq 0 ]; then
    echo "❌ No avatars loaded. Place avatar data in services/lite-avatar-worker/avatars/"
    exit 1
fi

# Test 3: Generate video ----------------------------------------------------
echo "[3/5] Generate video..."
FIRST_AVATAR=$(echo "$AVATARS" | python3 -c "import sys,json; print(json.load(sys.stdin)['avatars'][0]['id'])")
echo "Using avatar: $FIRST_AVATAR"

GENERATE_RESPONSE=$(curl -sf -X POST "$BASE_URL/generate" \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"Xin chào! Đây là video test từ LiteAvatar worker. Cảm ơn bạn đã sử dụng AI Co-host.\",
    \"avatar_id\": \"$FIRST_AVATAR\",
    \"background\": \"white\",
    \"language\": \"vi\"
  }")

JOB_ID=$(echo "$GENERATE_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
echo "Job ID: $JOB_ID"
echo ""

# Test 4: Poll status -------------------------------------------------------
echo "[4/5] Polling status (max 5 min)..."
VIDEO_URL=""
DURATION=""
for i in $(seq 1 30); do
    STATUS_RESPONSE=$(curl -sf "$BASE_URL/status/$JOB_ID")
    STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
    echo "  Attempt $i: status=$STATUS"

    if [ "$STATUS" = "ready" ]; then
        echo "$STATUS_RESPONSE" | python3 -m json.tool
        VIDEO_URL=$(echo "$STATUS_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['video_url'])")
        DURATION=$(echo "$STATUS_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['duration_seconds'])")
        echo ""
        echo "✅ Video ready: $VIDEO_URL ($DURATION seconds)"
        break
    elif [ "$STATUS" = "failed" ]; then
        echo "$STATUS_RESPONSE" | python3 -m json.tool
        echo "❌ Generation failed"
        exit 1
    fi

    sleep 10
done

if [ -z "$VIDEO_URL" ]; then
    echo "❌ Job did not finish within 5 minutes"
    exit 1
fi

# Test 5: Download artifact -------------------------------------------------
echo ""
echo "[5/5] Download artifact..."
FILENAME=$(echo "$VIDEO_URL" | sed 's|storage://lite-avatar/||')
curl -sf "$BASE_URL/artifacts/$FILENAME" -o /tmp/test-output.mp4
SIZE=$(stat -c%s /tmp/test-output.mp4 2>/dev/null || stat -f%z /tmp/test-output.mp4)
echo "Downloaded: /tmp/test-output.mp4 ($SIZE bytes)"

if [ "$SIZE" -lt 10000 ]; then
    echo "❌ Video too small, likely corrupt"
    exit 1
fi

echo ""
echo "=== ✅ All smoke tests passed ==="
echo "Generated video: /tmp/test-output.mp4"
echo "Open it to verify quality."
