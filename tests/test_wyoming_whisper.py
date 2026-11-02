"""WyomingWhisperSTT against a fake in-process Wyoming server.

transcribe() runs its own event loop via asyncio.run(), so the fake server
runs on a separate event loop in a background thread.
"""

import asyncio
import threading

import numpy as np
import pytest

pytest.importorskip("wyoming")

from wyoming.asr import Transcribe, Transcript  # noqa: E402
from wyoming.audio import AudioChunk, AudioStart, AudioStop  # noqa: E402
from wyoming.event import async_read_event, async_write_event  # noqa: E402

from voxport.stt.wyoming_whisper import (  # noqa: E402
    CHUNK_SAMPLES,
    SAMPLE_RATE,
    WyomingWhisperSTT,
)


class FakeWyomingServer:
    """Records the events a client sends; replies with a transcript, or
    closes the connection without one if `reply` is None."""

    def __init__(self, reply="hello world"):
        self.reply = reply
        self.events = []
        self.port = None
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        asyncio.set_event_loop(self._loop)
        server = self._loop.run_until_complete(
            asyncio.start_server(self._handle, "127.0.0.1", 0)
        )
        self.port = server.sockets[0].getsockname()[1]
        self._ready.set()
        self._loop.run_forever()
        server.close()
        self._loop.run_until_complete(server.wait_closed())
        self._loop.close()

    async def _handle(self, reader, writer):
        while True:
            event = await async_read_event(reader)
            if event is None:
                break
            self.events.append(event)
            if AudioStop.is_type(event.type):
                if self.reply is not None:
                    await async_write_event(Transcript(text=self.reply).event(), writer)
                break
        writer.close()

    def __enter__(self):
        self._thread.start()
        self._ready.wait(timeout=5)
        return self

    def __exit__(self, *exc):
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

    def of_type(self, cls):
        return [cls.from_event(e) for e in self.events if cls.is_type(e.type)]


def received_audio(server):
    return np.frombuffer(
        b"".join(chunk.audio for chunk in server.of_type(AudioChunk)), dtype=np.int16
    )


def test_returns_transcript_text():
    with FakeWyomingServer(reply="hello world") as server:
        stt = WyomingWhisperSTT(host="127.0.0.1", port=server.port)
        assert stt.transcribe(np.zeros(1600, dtype=np.int16)) == "hello world"


def test_sends_events_in_protocol_order():
    with FakeWyomingServer() as server:
        WyomingWhisperSTT(host="127.0.0.1", port=server.port).transcribe(
            np.zeros(1600, dtype=np.int16)
        )
    types = [e.type for e in server.events]
    assert Transcribe.is_type(types[0])
    assert AudioStart.is_type(types[1])
    assert AudioStop.is_type(types[-1])
    assert len(types) > 3
    assert all(AudioChunk.is_type(t) for t in types[2:-1])


def test_sends_language_and_audio_format():
    with FakeWyomingServer() as server:
        WyomingWhisperSTT(host="127.0.0.1", port=server.port).transcribe(
            np.zeros(1600, dtype=np.int16), language="en"
        )
    assert server.of_type(Transcribe)[0].language == "en"
    start = server.of_type(AudioStart)[0]
    assert (start.rate, start.width, start.channels) == (SAMPLE_RATE, 2, 1)


def test_int16_audio_is_sent_unchanged_in_chunks():
    audio = np.arange(-2500, 2500, dtype=np.int16)  # 5000 samples
    with FakeWyomingServer() as server:
        WyomingWhisperSTT(host="127.0.0.1", port=server.port).transcribe(audio)
    chunks = server.of_type(AudioChunk)
    assert len(chunks) == -(-len(audio) // CHUNK_SAMPLES)  # ceiling division
    assert all(len(c.audio) <= CHUNK_SAMPLES * 2 for c in chunks)
    np.testing.assert_array_equal(received_audio(server), audio)


def test_float_audio_is_clipped_and_converted_to_int16():
    audio = np.array([0.0, 0.5, -0.5, 1.0, -1.0, 2.0, -2.0], dtype=np.float32)
    with FakeWyomingServer() as server:
        WyomingWhisperSTT(host="127.0.0.1", port=server.port).transcribe(audio)
    np.testing.assert_array_equal(
        received_audio(server),
        np.array([0, 16383, -16383, 32767, -32767, 32767, -32767], dtype=np.int16),
    )


def test_server_closing_without_transcript_raises():
    with FakeWyomingServer(reply=None) as server:
        stt = WyomingWhisperSTT(host="127.0.0.1", port=server.port)
        with pytest.raises(ConnectionError):
            stt.transcribe(np.zeros(1600, dtype=np.int16))
