"""Storage abstraction for video artifacts.

CURRENT: Copies generated videos to a local cache directory and returns
``storage://lite-avatar/<filename>`` placeholder URLs — matching the same
pattern used by the HeyGen flow in ``apps/workers/dh_providers/base.py``.

The actual file is served via the /artifacts/{filename} endpoint so API
workers can download and re-upload into real object storage later.

TODO: Replace with direct R2/S3 upload when the storage backend is ready.
"""
from __future__ import annotations

import logging
import os
import shutil
import uuid

logger = logging.getLogger(__name__)

# Local cache directory — overridable via env for tests or host-mount.
LOCAL_CACHE_DIR = os.environ.get("VIDEO_CACHE_DIR", "/tmp/lite-avatar-videos")


def save_video_artifact(local_video_path: str) -> str:
    """Copy a generated video into the local cache and return its URL.

    The returned URL uses the ``storage://`` scheme to stay consistent
    with the HeyGen provider, so downstream code does not need to branch
    on provider identity.
    """
    os.makedirs(LOCAL_CACHE_DIR, exist_ok=True)

    artifact_id = str(uuid.uuid4())
    filename = f"{artifact_id}.mp4"
    target_path = os.path.join(LOCAL_CACHE_DIR, filename)

    shutil.copy(local_video_path, target_path)
    logger.info("[storage] Saved artifact: %s", filename)

    return f"storage://lite-avatar/{filename}"


def get_artifact_path(filename: str) -> str:
    """Return the local absolute path for a given artifact filename."""
    return os.path.join(LOCAL_CACHE_DIR, filename)
