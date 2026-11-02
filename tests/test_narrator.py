"""Tests for narrator.py covering mocked offline fallback and mocked gTTS MP3 output."""

from pathlib import Path
import pytest
from gtts.tts import gTTSError
import src.narrator as narrator


def test_offline_fallback_returns_none_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """When gTTS raises gTTSError (no internet), generate_narration warns and returns None."""
    def _raise_offline(text: str, out_path: Path) -> None:
        raise gTTSError("No internet connection")

    monkeypatch.setattr(narrator, "_synthesize_to_file", _raise_offline)
    mp3_path, duration, _ = narrator.generate_narration("Welcome to Sunrise Heights.", temp_dir=tmp_path)

    assert mp3_path is None
    assert duration == 0.0
    out = capsys.readouterr().out
    assert (
        "Narration could not be generated (no internet connection). The video will be exported without narration."
        in out
    )


def test_mocked_gtts_returns_mp3_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With mocked gTTS synthesis and duration measurement, an MP3 path is returned."""
    def _fake_synth(text: str, out_path: Path) -> None:
        out_path.write_bytes(b"ID3-mock-mp3-bytes")

    monkeypatch.setattr(narrator, "_synthesize_to_file", _fake_synth)
    monkeypatch.setattr(narrator, "_measure_mp3_duration", lambda p: 19.4)

    mp3_path, duration, _ = narrator.generate_narration("Welcome to Sunrise Heights.", temp_dir=tmp_path)
    assert mp3_path is not None and mp3_path.exists()
    assert duration == pytest.approx(19.4)