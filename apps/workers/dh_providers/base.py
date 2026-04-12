"""Provider interface, request/response dataclasses, and shared helpers."""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GenerateRequest:
    """Provider-agnostic generation request."""

    text: str
    avatar_id: str
    voice_id: Optional[str] = None  # ElevenLabs provider_voice_id
    background: str = "#FFFFFF"
    language: str = "vi"
    prefer_quality: bool = False
    # Caller context — used for storage paths and fallback decisions
    shop_id: Optional[int] = None


@dataclass
class GenerateResponse:
    """Provider-agnostic generation response."""

    provider: str  # "liteavatar" | "heygen"
    job_id: str
    status: str  # "queued" | "processing" | "ready" | "failed"
    video_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    file_size_bytes: Optional[int] = None
    cost_usd: float = 0.0
    error_message: Optional[str] = None
    raw: dict = field(default_factory=dict)  # provider-specific payload


class DHProvider(ABC):
    """Interface every digital human provider must implement."""

    name: str
    supports_custom_avatar: bool
    cost_per_minute_usd: float

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider is configured and reachable."""

    @abstractmethod
    def supports_avatar(self, avatar_id: str) -> bool:
        """Return True if this provider can render the requested avatar."""

    @abstractmethod
    def generate(self, request: GenerateRequest) -> GenerateResponse:
        """Trigger generation. MUST return immediately with a job_id."""

    @abstractmethod
    def get_status(self, job_id: str) -> GenerateResponse:
        """Poll job status. Return ready/failed/processing."""

    def finalize(
        self, response: GenerateResponse, shop_id: int
    ) -> GenerateResponse:
        """Post-process a ready response.

        Default no-op (provider already returned a finalized URL). HeyGen
        overrides this to download → watermark → store the video. LiteAvatar's
        worker container handles those steps internally so it returns
        ``response`` unchanged.
        """
        return response


# --- Shared helpers ---------------------------------------------------------


WATERMARK_TEXT = "Nội dung tạo bởi AI"


def add_watermark(video_bytes: bytes) -> bytes:
    """Burn the mandatory 'Nội dung tạo bởi AI' watermark into the video.

    Falls back to the original bytes if ffmpeg is unavailable so a missing
    binary cannot block video delivery — but logs a loud warning so the
    compliance gap is visible in production logs.
    """
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as inp:
        inp.write(video_bytes)
        input_path = inp.name

    output_path = input_path.replace(".mp4", "_wm.mp4")

    try:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", (
                f"drawtext=text='{WATERMARK_TEXT}':"
                "fontcolor=white@0.5:fontsize=18:"
                "x=w-tw-20:y=h-th-20:"
                "shadowcolor=black@0.3:shadowx=1:shadowy=1"
            ),
            "-codec:a", "copy",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)

        with open(output_path, "rb") as f:
            return f.read()
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("ffmpeg watermark failed, returning original video")
        return video_bytes
    finally:
        for p in (input_path, output_path):
            try:
                os.unlink(p)
            except OSError:
                pass


def save_video_artifact(video_bytes: bytes, shop_id: int) -> str:
    """Persist a finalized video and return a stable URL.

    TODO: Replace with a real R2/S3 upload when the storage backend is ready.
    Until then this returns a ``storage://`` placeholder identical to the
    pre-refactor behavior so existing video records remain consistent.
    """
    video_key = f"videos/{shop_id}/{uuid.uuid4().hex}.mp4"
    return f"storage://{video_key}"
