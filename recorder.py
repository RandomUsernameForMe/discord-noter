import time

import discord
from discord.opus import Decoder

BYTES_PER_SEC = Decoder.SAMPLING_RATE * Decoder.SAMPLE_SIZE
MIN_GAP = BYTES_PER_SEC // 10  # 100 ms — menší mezery jsou jen jitter


def padding_needed(elapsed: float, written: int, chunk_len: int) -> int:
    """Kolik bajtů ticha vložit, aby chunk začínal v čase `elapsed` od startu nahrávání."""
    gap = int(elapsed * BYTES_PER_SEC) - chunk_len - written
    if gap < MIN_GAP:
        return 0
    return gap - gap % Decoder.SAMPLE_SIZE


class TimedWaveSink(discord.sinks.WaveSink):
    """WaveSink, který dorovná každou stopu tichem podle reálného času.

    py-cord (od 2.7) ticho mezi promluvami ani před první promluvou nedoplňuje,
    takže bez toho by časové značky i pořadí mluvčích v přepisu nesouhlasily.
    """

    # ponytail: čas příchodu paketů ≈ čas promluvy; jitter pod MIN_GAP se ignoruje

    def __init__(self):
        super().__init__()
        self._start = time.monotonic()
        self._written: dict = {}

    def write(self, data, user):
        pcm = data.pcm if hasattr(data, "pcm") else data
        written = self._written.get(user, 0)
        pad = padding_needed(time.monotonic() - self._start, written, len(pcm))
        if pad:
            super().write(b"\x00" * pad, user)
        super().write(pcm, user)
        self._written[user] = written + pad + len(pcm)
