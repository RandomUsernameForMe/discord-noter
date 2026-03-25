import pytest
from unittest.mock import MagicMock, patch, mock_open
import io
import wave
import struct

from transcriber import Segment, format_transcript, _wav_duration


# ---------------------------------------------------------------------------
# format_transcript — čistá funkce, bez externích závislostí
# ---------------------------------------------------------------------------

class TestFormatTranscript:
    def test_empty_segments_returns_placeholder(self):
        assert format_transcript([]) == "(žádný přepis)"

    def test_single_segment(self):
        segments = [Segment(start=0.0, end=2.0, text="Ahoj", username="Alice")]
        result = format_transcript(segments)
        assert "[00:00] **Alice**: Ahoj" in result

    def test_timestamp_minutes_and_seconds(self):
        # 90 sekund → [01:30]
        segments = [Segment(start=90.0, end=92.0, text="Text", username="Alice")]
        result = format_transcript(segments)
        assert "[01:30]" in result

    def test_same_speaker_consecutive_no_repeat_header(self):
        # Stejný mluvčí za sebou → jméno jen jednou
        segments = [
            Segment(start=0.0, end=2.0, text="Věta jedna", username="Alice"),
            Segment(start=2.0, end=4.0, text="Věta dvě", username="Alice"),
        ]
        result = format_transcript(segments)
        assert result.count("**Alice**") == 1
        assert "Věta jedna" in result
        assert "Věta dvě" in result

    def test_different_speakers_each_gets_header(self):
        segments = [
            Segment(start=0.0, end=2.0, text="Ahoj", username="Alice"),
            Segment(start=2.0, end=4.0, text="Nazdar", username="Bob"),
        ]
        result = format_transcript(segments)
        assert "**Alice**" in result
        assert "**Bob**" in result

    def test_alternating_speakers_each_gets_header(self):
        # Alice → Bob → Alice: Alice by měla mít header 2×
        segments = [
            Segment(start=0.0, end=2.0, text="A1", username="Alice"),
            Segment(start=2.0, end=4.0, text="B1", username="Bob"),
            Segment(start=4.0, end=6.0, text="A2", username="Alice"),
        ]
        result = format_transcript(segments)
        assert result.count("**Alice**") == 2
        assert result.count("**Bob**") == 1

    def test_segments_over_one_hour(self):
        # 3700 sekund → [01:41:40] — formát MM:SS, takže [61:40]
        segments = [Segment(start=3700.0, end=3702.0, text="Pozdě", username="Alice")]
        result = format_transcript(segments)
        assert "[61:40]" in result

    def test_preserves_text_content(self):
        segments = [Segment(start=0.0, end=1.0, text="Speciální znaky: & < >", username="Test")]
        result = format_transcript(segments)
        assert "Speciální znaky: & < >" in result


# ---------------------------------------------------------------------------
# _wav_duration — testujeme s reálným in-memory WAV souborem
# ---------------------------------------------------------------------------

def _make_wav_bytes(num_frames: int, framerate: int = 16000) -> bytes:
    """Vytvoří minimální platný WAV soubor v paměti."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        # Tichá data: num_frames * 2 bytes (16-bit mono)
        wf.writeframes(b"\x00\x00" * num_frames)
    return buf.getvalue()


class TestWavDuration:
    def test_duration_two_seconds(self, tmp_path):
        wav_path = tmp_path / "test.wav"
        wav_path.write_bytes(_make_wav_bytes(num_frames=32000, framerate=16000))
        assert _wav_duration(str(wav_path)) == pytest.approx(2.0)

    def test_duration_zero_frames(self, tmp_path):
        wav_path = tmp_path / "empty.wav"
        wav_path.write_bytes(_make_wav_bytes(num_frames=0, framerate=16000))
        assert _wav_duration(str(wav_path)) == pytest.approx(0.0)

    def test_duration_nonexistent_file(self, tmp_path):
        with pytest.raises(Exception):
            _wav_duration(str(tmp_path / "missing.wav"))
