"""KokoroDirectTTS with fake `torch` and `kokoro` modules.

The real ones need torch (~2 GB) and the Kokoro model, so these tests
substitute stand-ins in sys.modules and import the adapter fresh against
them. monkeypatch restores sys.modules and the environment afterward.
"""

import importlib
import logging
import sys
import types

import numpy as np
import pytest

MODULE = "voxport.tts.kokoro_direct"


class FakeTensor:
    """Mimics the torch tensor methods the adapter uses."""

    def __init__(self, values):
        self._values = np.asarray(values, dtype=np.float32)

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self._values


@pytest.fixture
def kokoro(monkeypatch, tmp_path):
    """Import the adapter against fake torch/kokoro; return (module, built)."""
    built = []  # (lang_code, repo_id) for each KPipeline constructed

    class FakeKPipeline:
        def __init__(self, lang_code, repo_id):
            built.append((lang_code, repo_id))

        def __call__(self, text, voice, speed):
            # Two segments: one tensor, one plain list.
            yield ("g1", "p1", FakeTensor([0.1, 0.2]))
            yield ("g2", "p2", [0.3])

    fake_kokoro = types.ModuleType("kokoro")
    fake_kokoro.KPipeline = FakeKPipeline

    monkeypatch.setitem(sys.modules, "torch", types.ModuleType("torch"))
    monkeypatch.setitem(sys.modules, "kokoro", fake_kokoro)
    monkeypatch.delitem(sys.modules, MODULE, raising=False)
    # The module sets these with setdefault at import; pre-set them so the
    # real environment is left untouched.
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    monkeypatch.setenv("KMP_DUPLICATE_LIB_OK", "TRUE")

    yield importlib.import_module(MODULE), built

    # monkeypatch.delitem only restores keys that existed beforehand, so
    # drop the fake-backed module explicitly; otherwise later tests would
    # get it from sys.modules instead of a real import.
    sys.modules.pop(MODULE, None)
    tts_package = sys.modules.get("voxport.tts")
    if tts_package is not None and hasattr(tts_package, "kokoro_direct"):
        delattr(tts_package, "kokoro_direct")


def test_concatenates_segments(kokoro):
    module, _ = kokoro
    audio = module.KokoroDirectTTS().synthesize("Hello.", voice="af_heart")
    np.testing.assert_allclose(audio, [0.1, 0.2, 0.3])
    assert module.KokoroDirectTTS.sample_rate == 24000


def test_pipeline_built_once_per_language(kokoro):
    module, built = kokoro
    tts = module.KokoroDirectTTS()
    tts.synthesize("One.", voice="af_heart")
    tts.synthesize("Two.", voice="am_adam")
    tts.synthesize("Three.", voice="bm_george")
    assert [lang for lang, _ in built] == ["a", "b"]


def test_lang_code_overrides_voice_prefix(kokoro):
    module, built = kokoro
    module.KokoroDirectTTS().synthesize("Hola.", voice="af_heart", lang_code="e")
    assert built[0][0] == "e"


def test_progress_is_logged_not_printed(kokoro, caplog, capsys):
    module, _ = kokoro
    with caplog.at_level(logging.DEBUG, logger="voxport"):
        module.KokoroDirectTTS().synthesize("Hello.", voice="af_heart", speed=1.2)

    records = [(r.name, r.levelno, r.getMessage()) for r in caplog.records]
    assert (MODULE, logging.INFO, "Loading Kokoro model for language 'a'...") in records
    assert (
        MODULE,
        logging.INFO,
        "Generating audio locally with Kokoro (voice=af_heart, speed=1.2)...",
    ) in records
    assert [m for _, lvl, m in records if lvl == logging.DEBUG] == [
        "Segment 1...",
        "Segment 2...",
    ]
    assert capsys.readouterr().out == ""


def test_no_segments_raises(kokoro, monkeypatch):
    module, _ = kokoro
    monkeypatch.setattr(
        sys.modules["kokoro"].KPipeline, "__call__", lambda self, text, voice, speed: iter(())
    )
    with pytest.raises(ValueError):
        module.KokoroDirectTTS().synthesize("", voice="af_heart")
