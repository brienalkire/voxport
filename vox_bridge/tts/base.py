"""TTSEngine port: the interface every text-to-speech adapter implements.

Callers depend only on this interface, not on any particular engine's
internals, so swapping the underlying engine later means writing one new
adapter, not touching any call site.
"""

from abc import ABC, abstractmethod


class TTSEngine(ABC):
    """Synthesizes speech from text."""

    #: Sample rate, in Hz, of the audio returned by `synthesize()`.
    sample_rate: int

    @abstractmethod
    def synthesize(self, text: str, voice: str, speed: float = 1.0):
        """Return synthesized audio for `text` spoken in `voice`.

        Returns a 1-D numpy array of audio samples at `self.sample_rate`.
        """
        raise NotImplementedError
