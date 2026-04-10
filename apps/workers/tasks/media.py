from celery_app import app


@app.task(name="tasks.media.generate_tts")
def generate_tts(suggestion_id: int, text: str, voice_id: str | None = None) -> dict:
    """Generate TTS audio for a suggestion."""
    return {"status": "not_implemented", "suggestion_id": suggestion_id}


@app.task(name="tasks.media.generate_dh_video")
def generate_dh_video(video_id: int) -> dict:
    """Generate digital human video via HeyGen."""
    return {"status": "not_implemented", "video_id": video_id}


@app.task(name="tasks.media.clone_voice")
def clone_voice(voice_clone_id: int) -> dict:
    """Clone voice via ElevenLabs."""
    return {"status": "not_implemented", "voice_clone_id": voice_clone_id}
