"""LiteAvatar Worker FastAPI wrapper.

Exposes a thin HTTP interface around the LiteAvatar inference pipeline:
    - GET  /health               — health check (called by Docker + router)
    - GET  /avatars              — list pre-loaded avatars
    - POST /generate             — kick off a video job, returns job_id
    - GET  /status/{job_id}      — poll job status
    - GET  /artifacts/{filename} — download generated video
    - DELETE /jobs/{job_id}      — cleanup finished job from memory
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from storage import get_artifact_path
from worker import generate_avatar_video

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="LiteAvatar Worker", version="1.0.0")

# In-memory job storage. For MVP scale (few concurrent jobs on one box)
# this is enough — if we ever need persistence or multi-instance, swap in
# Redis or SQLite without touching callers.
JOBS: dict[str, dict] = {}

AVATARS_DIR = "/app/avatars"


class GenerateInput(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    avatar_id: str
    voice_audio_url: Optional[str] = None
    background: str = "white"
    language: str = "vi"


class JobStatus(BaseModel):
    job_id: str
    status: str
    video_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


def _list_avatar_ids() -> list[str]:
    if not os.path.exists(AVATARS_DIR):
        return []
    return [
        d
        for d in os.listdir(AVATARS_DIR)
        if os.path.isdir(os.path.join(AVATARS_DIR, d)) and not d.startswith(".")
    ]


@app.get("/health")
def health():
    """Health check. Called by Docker healthcheck and the provider router."""
    avatars = _list_avatar_ids()
    return {
        "status": "ok",
        "service": "lite-avatar-worker",
        "avatars_available": len(avatars),
        "avatars": avatars,
        "active_jobs": sum(1 for j in JOBS.values() if j["status"] == "processing"),
    }


@app.get("/avatars")
def list_avatars():
    """List pre-loaded avatars present in /app/avatars."""
    avatars = []
    for name in _list_avatar_ids():
        avatars.append(
            {
                "id": name,
                "name": name.replace("_", " ").title(),
                "path": os.path.join(AVATARS_DIR, name),
            }
        )
    return {"avatars": avatars}


@app.post("/generate")
def generate(input: GenerateInput, background_tasks: BackgroundTasks):
    """Trigger video generation. Returns job_id immediately."""
    avatar_path = os.path.join(AVATARS_DIR, input.avatar_id)
    if not os.path.exists(avatar_path):
        raise HTTPException(404, f"Avatar '{input.avatar_id}' không tồn tại")

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "status": "queued",
        "video_url": None,
        "duration_seconds": None,
        "error": None,
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
    }

    background_tasks.add_task(
        _run_generation,
        job_id=job_id,
        text=input.text,
        avatar_path=avatar_path,
        voice_audio_url=input.voice_audio_url,
        background=input.background,
        language=input.language,
    )

    logger.info("[generate] Job %s queued for avatar %s", job_id, input.avatar_id)
    return {"job_id": job_id, "status": "queued"}


@app.get("/status/{job_id}")
def get_status(job_id: str) -> JobStatus:
    if job_id not in JOBS:
        raise HTTPException(404, f"Job {job_id} không tồn tại")
    return JobStatus(job_id=job_id, **JOBS[job_id])


@app.delete("/jobs/{job_id}")
def cleanup_job(job_id: str):
    """Drop a job from memory once the client has downloaded its artifact."""
    if job_id in JOBS:
        del JOBS[job_id]
    return {"deleted": True}


@app.get("/artifacts/{filename}")
def get_artifact(filename: str):
    """Serve a generated video file.

    API workers call this to download the MP4 and re-upload it into the
    real storage backend. Guarded against path traversal.
    """
    if not filename.endswith(".mp4"):
        raise HTTPException(400, "Invalid filename")
    if "/" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")

    path = get_artifact_path(filename)
    if not os.path.exists(path):
        raise HTTPException(404, "Artifact không tồn tại")

    return FileResponse(path, media_type="video/mp4", filename=filename)


def _run_generation(
    job_id: str,
    text: str,
    avatar_path: str,
    voice_audio_url: Optional[str],
    background: str,
    language: str,
) -> None:
    """Background task: run inference and update job status."""
    try:
        JOBS[job_id]["status"] = "processing"
        logger.info("[run_generation] Job %s processing started", job_id)

        result = generate_avatar_video(
            text=text,
            avatar_path=avatar_path,
            voice_audio_url=voice_audio_url,
            background=background,
            language=language,
        )

        JOBS[job_id].update(
            {
                "status": "ready",
                "video_url": result["video_url"],
                "duration_seconds": result["duration_seconds"],
                "completed_at": datetime.utcnow().isoformat(),
            }
        )
        logger.info(
            "[run_generation] Job %s completed: %s", job_id, result["video_url"]
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("[run_generation] Job %s failed", job_id)
        JOBS[job_id].update(
            {
                "status": "failed",
                "error": str(exc)[:500],
                "completed_at": datetime.utcnow().isoformat(),
            }
        )
