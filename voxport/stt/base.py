"""STTEngine port: the interface every speech-to-text adapter implements.

Callers depend only on this interface, not on any particular engine's
internals, so swapping the underlying engine later means writing one new
adapter, not touching any call site.
"""

from abc import ABC, abstractmethod


class STTEngine(ABC):
    """Transcribes speech to text."""

    #: Sample rate, in Hz, `transcribe()` expects the input audio at.
    sample_rate: int

    @abstractmethod
    def transcribe(self, audio) -> str:
        """Return the transcribed text for `audio`.

        `audio` is a 1-D numpy array of audio samples at `self.sample_rate`.
        A concrete adapter may accept additional, engine-specific keyword
        arguments beyond this minimal signature — callers that don't need
        them can ignore this possibility entirely.
        """
        raise NotImplementedError
