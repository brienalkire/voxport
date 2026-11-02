"""Importing an adapter without its optional extra names the extra to install."""

import importlib.util

import pytest


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is not None,
    reason="torch is installed, so the kokoro extra is present",
)
def test_kokoro_adapter_without_extra_names_the_extra():
    with pytest.raises(ImportError, match=r"voxport\[kokoro\]"):
        import voxport.tts.kokoro_direct  # noqa: F401


@pytest.mark.skipif(
    importlib.util.find_spec("wyoming") is not None,
    reason="wyoming is installed, so the wyoming extra is present",
)
def test_wyoming_adapter_without_extra_names_the_extra():
    with pytest.raises(ImportError, match=r"voxport\[wyoming\]"):
        import voxport.stt.wyoming_whisper  # noqa: F401
