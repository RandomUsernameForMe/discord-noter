import os
import tempfile
import wave
from dataclasses import dataclass

import discord
from faster_whisper import WhisperModel


@dataclass
class Segment:
    start: float  # seconds from recording start
    end: float
    text: str
    username: str


def load_model(name: str) -> WhisperModel:
    return WhisperModel(name, device="auto", compute_type="int8")


def _write_wav(pcm: bytes, path: str) -> None:
    dec = discord.opus.Decoder
    with wave.open(path, "wb") as wf:
        wf.setnchannels(dec.CHANNELS)
        wf.setsampwidth(dec.SAMPLE_SIZE // dec.CHANNELS)
        wf.setframerate(dec.SAMPLING_RATE)
        wf.writeframes(pcm)


def _transcribe_user(model: WhisperModel, pcm: bytes, username: str) -> list[Segment]:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        _write_wav(pcm, tmp_path)
        # vad_filter přeskočí ticho (stopy jsou díky sync_start dorovnané tichem), časy zachová
        segments, _ = model.transcribe(tmp_path, language="cs", vad_filter=True)
        return [
            Segment(start=s.start, end=s.end, text=s.text.strip(), username=username)
            for s in segments
            if s.text.strip()
        ]
    finally:
        os.unlink(tmp_path)


def transcribe_recording(
    sink: discord.sinks.Sink,
    guild: discord.Guild,
    model: WhisperModel,
) -> list[Segment]:
    """Transcribe each user's audio and return merged chronological segments."""
    all_segments: list[Segment] = []

    for user_id, audio_data in sink.audio_data.items():
        member = guild.get_member(user_id)
        username = member.display_name if member else str(user_id)

        audio_data.file.seek(0)
        raw = audio_data.file.read()
        # WaveSink.format_audio přepíše začátek bufferu prázdnou WAV hlavičkou
        if raw.startswith(b"RIFF"):
            raw = raw[44:]
        if len(raw) < 1024:
            continue

        all_segments.extend(_transcribe_user(model, raw, username))

    all_segments.sort(key=lambda s: s.start)
    return all_segments


def format_transcript(segments: list[Segment]) -> str:
    """Format segments into readable transcript."""
    if not segments:
        return "(žádný přepis)"

    lines = []
    prev_user = None
    for seg in segments:
        minutes = int(seg.start // 60)
        seconds = int(seg.start % 60)
        timestamp = f"[{minutes:02d}:{seconds:02d}]"

        if seg.username != prev_user:
            lines.append(f"\n{timestamp} **{seg.username}**: {seg.text}")
            prev_user = seg.username
        else:
            lines.append(f"  {seg.text}")

    return "\n".join(lines).strip()
