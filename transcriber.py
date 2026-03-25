import os
import tempfile
import wave
from dataclasses import dataclass

import whisper
import discord

from recorder import MeetingSink


@dataclass
class Segment:
    start: float  # seconds from recording start
    end: float
    text: str
    username: str


def _wav_duration(path: str) -> float:
    with wave.open(path, "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def transcribe_recording(
    sink: MeetingSink,
    guild: discord.Guild,
    model: whisper.Whisper,
) -> list[Segment]:
    """Transcribe each user's audio and return merged chronological segments."""

    all_segments: list[Segment] = []

    for user_id, audio_data in sink.audio_data.items():
        member = guild.get_member(user_id)
        username = member.display_name if member else str(user_id)

        # Skip empty audio
        audio_data.file.seek(0)
        raw = audio_data.file.read()
        if len(raw) < 1024:
            continue

        # Write to temp WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(discord.sinks.WaveSink.AUDIO_CHANNEL)
                wf.setsampwidth(
                    discord.sinks.WaveSink.AUDIO_SAMPLE_SIZE // discord.sinks.WaveSink.AUDIO_CHANNEL
                )
                wf.setframerate(discord.sinks.WaveSink.AUDIO_SAMPLE_RATE)
                audio_data.file.seek(0)
                wf.writeframes(audio_data.file.read())

            user_offset = sink.get_user_start_offset(user_id)

            result = model.transcribe(tmp_path, language="cs", verbose=False)

            for seg in result["segments"]:
                text = seg["text"].strip()
                if not text:
                    continue
                all_segments.append(
                    Segment(
                        start=user_offset + seg["start"],
                        end=user_offset + seg["end"],
                        text=text,
                        username=username,
                    )
                )
        finally:
            os.unlink(tmp_path)

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
