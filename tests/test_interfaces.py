"""The TTSEngine and STTEngine ports: abstract, and usable via subclassing."""

import numpy as np
import pytest

from voxport.stt.base import STTEngine
from voxport.tts.base import TTSEngine


def test_tts_engine_is_abstract():
    with pytest.raises(TypeError):
        TTSEngine()


def test_stt_engine_is_abstract():
    with pytest.raises(TypeError):
        STTEngine()


def test_tts_subclass_works():
    class SilenceTTS(TTSEngine):
        sample_rate = 16000

        def synthesize(self, text, voice, speed=1.0):
            return np.zeros(self.sample_rate, dtype=np.float32)

    audio = SilenceTTS().synthesize("hello", "any-voice")
    assert audio.shape == (16000,)


def test_stt_subclass_works():
    class EchoSTT(STTEngine):
        sample_rate = 16000

        def transcribe(self, audio):
            return f"{len(audio)} samples"

    assert EchoSTT().transcribe(np.zeros(5)) == "5 samples"


def test_subclass_missing_method_is_rejected():
    class Incomplete(TTSEngine):
        sample_rate = 16000

    with pytest.raises(TypeError):
        Incomplete()
