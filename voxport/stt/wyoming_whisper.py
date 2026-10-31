"""WyomingWhisperSTT: network client to a running Wyoming Whisper server.

Unlike `KokoroDirectTTS` (in-process, model resident in the calling
process), this is a network client by design — no model loading, no local
Whisper install, all transcription work happens on the server. That
matches the actual use case: Home Assistant's own voice pipeline already
runs a Wyoming Whisper server, so this adapter talks to the same kind of
server rather than duplicating it.
"""

import asyncio

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient

from voxport.stt.base import STTEngine

# Wyoming Whisper servers expect 16-bit mono PCM at 16 kHz.
SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # bytes per sample (16-bit)
CHANNELS = 1

# Audio is streamed to the server in chunks rather than one giant payload.
CHUNK_SAMPLES = 1024


class WyomingWhisperSTT(STTEngine):
    """Speech-to-text via a Wyoming-protocol Whisper server (e.g.
    `rhasspy/wyoming-whisper`) — the same kind of server Home Assistant's
    own voice pipeline talks to.

    Connects fresh for each `transcribe()` call; the server keeps its
    model resident, not this client. Host/port are configurable (not
    hardcoded) since this will eventually point at different hardware —
    a dedicated always-on machine, rather than localhost — once that
    exists.
    """

    sample_rate = SAMPLE_RATE

    def __init__(self, host: str = "localhost", port: int = 10300):
        self.host = host
        self.port = port

    def transcribe(self, audio, language: str | None = None) -> str:
        """Return the transcribed text for `audio`.

        `audio` is a 1-D numpy array at `self.sample_rate` — int16 samples,
        or float samples in [-1, 1] (auto-converted to int16).

        This runs its own asyncio event loop internally (the Wyoming
        client library is async-only) — call it from a worker thread
        (`asyncio.to_thread`) when calling from code that already has an
        event loop running, the same way `KokoroDirectTTS.synthesize()` is
        called from loremaster's bot.
        """
        return asyncio.run(self._transcribe_async(audio, language))

    async def _transcribe_async(self, audio, language):
        import numpy as np

        audio = np.asarray(audio)
        if np.issubdtype(audio.dtype, np.floating):
            audio = np.clip(audio, -1.0, 1.0)
            audio = (audio * 32767).astype(np.int16)
        elif audio.dtype != np.int16:
            audio = audio.astype(np.int16)
        audio_bytes = audio.tobytes()

        async with AsyncTcpClient(self.host, self.port) as client:
            await client.write_event(Transcribe(language=language).event())
            await client.write_event(
                AudioStart(rate=self.sample_rate, width=SAMPLE_WIDTH, channels=CHANNELS).event()
            )

            chunk_bytes = CHUNK_SAMPLES * SAMPLE_WIDTH
            for offset in range(0, len(audio_bytes), chunk_bytes):
                chunk = audio_bytes[offset:offset + chunk_bytes]
                await client.write_event(
                    AudioChunk(rate=self.sample_rate, width=SAMPLE_WIDTH,
                               channels=CHANNELS, audio=chunk).event()
                )

            await client.write_event(AudioStop().event())

            while True:
                event = await client.read_event()
                if event is None:
                    raise ConnectionError(
                        "Wyoming server closed the connection without sending a transcript."
                    )
                if Transcript.is_type(event.type):
                    return Transcript.from_event(event).text
