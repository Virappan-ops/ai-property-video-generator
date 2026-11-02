"""Text-to-speech for each scene. Uses Edge neural voices when available, otherwise gTTS."""

import asyncio
from pathlib import Path
from typing import List, Optional, Tuple

from moviepy.audio.io.AudioFileClip import AudioFileClip  # type: ignore[import-untyped]

import config
from src.logger import log_step, log_warning

SpeechSegment = Tuple[Path, float]  # (mp3 path, duration in seconds)


def _measure(path: Path) -> float:
    """Return the duration of an MP3 file in seconds."""
    clip = AudioFileClip(str(path))
    try:
        return float(clip.duration)
    finally:
        clip.close()


def _edge_installed() -> bool:
    """Check whether the edge-tts package is available."""
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return False


async def _edge_save(text: str, path: Path) -> None:
    """Save one line with the Edge neural voice."""
    import edge_tts

    communicate = edge_tts.Communicate(text, config.EDGE_VOICE, rate=config.EDGE_RATE)
    await communicate.save(str(path))


def _gtts_save(text: str, path: Path) -> None:
    """Save one line with the gTTS voice."""
    from gtts import gTTS  # type: ignore[import-untyped]

    gTTS(text=text, lang=config.NARRATION_LANG, tld=config.NARRATION_TLD, slow=False).save(str(path))


def synthesize_scene_speech(lines: List[str], temp_dir: Path) -> Optional[List[SpeechSegment]]:
    """Create one MP3 per scene line.

    Returns a list of (path, duration) in scene order, or None if no voice could be generated
    (for example, when the computer is offline).
    """
    temp_dir.mkdir(parents=True, exist_ok=True)

    use_edge = config.TTS_ENGINE == "edge" and _edge_installed()
    if config.TTS_ENGINE == "edge" and not use_edge:
        log_warning("Warning: edge-tts is not installed. Using the gTTS voice. Run: pip install edge-tts")

    segments: List[SpeechSegment] = []
    for idx, text in enumerate(lines, start=1):
        path = temp_dir / f"speech_{idx:02d}.mp3"
        try:
            if use_edge:
                try:
                    asyncio.run(_edge_save(text, path))
                except Exception as exc:  # noqa: BLE001
                    log_warning(f"Warning: Edge voice failed ({exc}). Switching to the gTTS voice.")
                    use_edge = False
                    _gtts_save(text, path)
            else:
                _gtts_save(text, path)

            segments.append((path, _measure(path)))
        except Exception:  # noqa: BLE001
            log_warning(
                "Narration could not be generated (no internet connection). "
                "The video will be exported without narration."
            )
            return None

    log_step(f"Generating narration... OK ({len(segments)} scene lines)")
    return segments