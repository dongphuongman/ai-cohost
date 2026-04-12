"""TTS helper using gTTS (free, no API key required).

For voice cloning, the API workers pre-generate audio via ElevenLabs and
pass ``voice_audio_url`` to /generate. This module is the fallback when no
voice clone is available.
"""
from __future__ import annotations

import logging
import os

from gtts import gTTS

logger = logging.getLogger(__name__)


def generate_tts_audio(text: str, output_path: str, lang: str = "vi") -> str:
    """Generate speech audio from text using gTTS.

    Args:
        text: Text to speak (default Vietnamese).
        output_path: Where to save the MP3 file.
        lang: Language code, default 'vi' for Vietnamese.

    Returns:
        Path to generated audio file.
    """
    logger.info("[tts] Generating TTS for %d chars in %s", len(text), lang)

    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(output_path)

    if not os.path.exists(output_path):
        raise RuntimeError(f"TTS failed: output file not created at {output_path}")

    file_size = os.path.getsize(output_path)
    logger.info("[tts] Generated %d bytes audio at %s", file_size, output_path)

    return output_path
