import io
import wave
import time
from dataclasses import dataclass, field
from typing import Optional

import discord


@dataclass
class UserAudio:
    username: str
    start_time: float
    pcm_chunks: list[bytes] = field(default_factory=list)


class MeetingSink(discord.sinks.WaveSink):
    """Per-user audio sink that tracks start timestamps."""

    def __init__(self):
        super().__init__()
        self.recording_start = time.time()
        self.user_start_times: dict[int, float] = {}

    def write(self, data: discord.sinks.core.RawData, user_id: int):
        if user_id not in self.user_start_times:
            self.user_start_times[user_id] = time.time() - self.recording_start
        super().write(data, user_id)

    def get_user_start_offset(self, user_id: int) -> float:
        return self.user_start_times.get(user_id, 0.0)


def save_user_wav(audio_data: discord.sinks.core.AudioData, path: str) -> None:
    """Save AudioData to a WAV file."""
    with wave.open(path, "wb") as wf:
        wf.setnchannels(discord.sinks.WaveSink.AUDIO_CHANNEL)
        wf.setsampwidth(discord.sinks.WaveSink.AUDIO_SAMPLE_SIZE // discord.sinks.WaveSink.AUDIO_CHANNEL)
        wf.setframerate(discord.sinks.WaveSink.AUDIO_SAMPLE_RATE)
        wf.writeframes(audio_data.file.getbuffer())
