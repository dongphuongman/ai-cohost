"""LiteAvatar inference worker.

Pipeline:
    1. Get/generate audio (ElevenLabs URL or gTTS fallback)
    2. Run LiteAvatar inference via subprocess
    3. Add 'Nội dung tạo bởi AI' watermark via ffmpeg (matches HeyGen)
    4. Save artifact via storage helper
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile

import httpx

from storage import save_video_artifact
from tts import generate_tts_audio

logger = logging.getLogger(__name__)

LITE_AVATAR_SCRIPT = "/app/lite-avatar/lite_avatar.py"
# Must match apps/workers/dh_providers/base.py::WATERMARK_TEXT so the
# visual watermark is identical across providers.
WATERMARK_TEXT = "Nội dung tạo bởi AI"


def generate_avatar_video(
    text: str,
    avatar_path: str,
    voice_audio_url: str | None,
    background: str,
    language: str = "vi",
) -> dict:
    """End-to-end video generation.

    Returns a dict with ``video_url`` and ``duration_seconds`` keys.
    Raises on any step failure — the caller wraps in job status.
    """
    work_dir = tempfile.mkdtemp(prefix="lite-avatar-")

    try:
        # Step 1: Get audio
        audio_path = os.path.join(work_dir, "input.wav")

        if voice_audio_url:
            logger.info("[generate] Downloading voice audio from %s", voice_audio_url)
            _download_audio(voice_audio_url, audio_path)
        else:
            logger.info("[generate] Generating gTTS audio (lang=%s)", language)
            mp3_path = os.path.join(work_dir, "tts.mp3")
            generate_tts_audio(text, mp3_path, lang=language)
            _convert_to_wav(mp3_path, audio_path)

        # Step 2: Run LiteAvatar inference
        result_dir = os.path.join(work_dir, "result")
        os.makedirs(result_dir, exist_ok=True)

        logger.info("[generate] Running LiteAvatar inference...")
        cmd = [
            "python",
            LITE_AVATAR_SCRIPT,
            "--data_dir",
            avatar_path,
            "--audio_file",
            audio_path,
            "--result_dir",
            result_dir,
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )

        if proc.returncode != 0:
            raise RuntimeError(
                f"LiteAvatar failed (exit {proc.returncode}): {proc.stderr[-500:]}"
            )

        # Step 3: Find output video
        video_files = [f for f in os.listdir(result_dir) if f.endswith(".mp4")]
        if not video_files:
            raise RuntimeError("LiteAvatar did not produce any video output")

        raw_video_path = os.path.join(result_dir, video_files[0])
        logger.info("[generate] Inference complete: %s", raw_video_path)

        # Step 4: Add watermark
        watermarked_path = os.path.join(work_dir, "final.mp4")
        _add_watermark(raw_video_path, watermarked_path)

        # Step 5: Duration
        duration = get_video_duration(watermarked_path)

        # Step 6: Save artifact
        video_url = save_video_artifact(watermarked_path)

        logger.info("[generate] Complete: %s (%ds)", video_url, duration)
        return {
            "video_url": video_url,
            "duration_seconds": duration,
        }

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _download_audio(url: str, output_path: str) -> None:
    """Stream audio from a URL into ``output_path``."""
    with httpx.stream("GET", url, timeout=60) as response:
        response.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)


def _convert_to_wav(mp3_path: str, wav_path: str) -> None:
    """Convert MP3 to 16kHz mono WAV (the format LiteAvatar expects)."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        mp3_path,
        "-ac",
        "1",
        "-ar",
        "16000",
        wav_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)


def _add_watermark(input_path: str, output_path: str) -> None:
    """Burn the 'Nội dung tạo bởi AI' watermark into the video via ffmpeg.

    The drawtext filter mirrors apps/workers/dh_providers/base.py exactly,
    so LiteAvatar and HeyGen produce visually identical watermarks.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-vf",
        (
            f"drawtext=text='{WATERMARK_TEXT}':"
            "fontcolor=white@0.5:fontsize=18:"
            "x=w-tw-20:y=h-th-20:"
            "shadowcolor=black@0.3:shadowx=1:shadowy=1"
        ),
        "-codec:a",
        "copy",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)


def get_video_duration(video_path: str) -> int:
    """Return video duration in whole seconds via ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return int(float(result.stdout.strip()))
