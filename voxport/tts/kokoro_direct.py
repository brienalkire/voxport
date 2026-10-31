"""KokoroDirectTTS: in-process Kokoro TTS adapter.

Loads the Kokoro model directly into the calling process (no server, no
network hop) and keeps it resident in memory, favoring simplicity and lower
latency over sharing one server across processes. This is the chosen
approach for all current consumers (podcast generation, loremaster, Home
Assistant); revisit only if resource use across multiple resident processes
becomes a real problem.
"""

import os

# voxport/tts/kokoro_direct.py -> voxport/tts -> voxport -> repo root
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Route the Hugging Face cache to a repo-relative directory rather than the
# user-global default, so a machine's pre-populated cache travels with the
# repo and downloads (where allowed) land somewhere predictable. Harmless
# and useful on any machine, so it's always on. Set before any Kokoro-related
# import.
os.environ.setdefault("HF_HOME", os.path.join(REPO_ROOT, "hf_cache"))

# Offline mode is opt-in, not forced here: only a machine that actually needs
# it (e.g. one behind a firewall that blocks huggingface.co) should set
# HF_HUB_OFFLINE=1 itself, in its own shell/.env — this module never sets it,
# so a machine with normal internet access can still download any voice not
# already in the local hf_cache above.

# In conda/miniforge environments, PyTorch's bundled OpenMP runtime (libomp)
# can collide with Intel's (libiomp5md, pulled in by MKL), causing "OMP Error
# #15" and a failed import. Allowing the duplicate runtime is the standard,
# widely-used workaround for CPU inference. Set before torch is imported
# (Kokoro imports it lazily, inside _build_pipeline below).
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Import torch here, at module import time, before any caller has a chance to
# import numpy/soundfile/kokoro first and pull in Intel's OpenMP (MKL) runtime
# ahead of torch's own. The reverse order breaks torch's DLL resolution on
# Windows/conda with a WinError 127 on shm.dll — importing torch as the very
# first thing this module does, regardless of what a caller does afterward,
# is what makes that safe to rely on from any consumer.
import torch  # noqa: F401

from voxport.tts.base import TTSEngine

# Kokoro produces audio at a fixed 24 kHz sample rate.
SAMPLE_RATE = 24000


class KokoroDirectTTS(TTSEngine):
    """In-process Kokoro TTS, model loaded once per language and reused.

    A single instance may be reused across many `synthesize()` calls —
    pipelines are cached by language code, so a run that mixes accents
    (e.g. an American and a British voice) loads each accent's model at
    most once.
    """

    sample_rate = SAMPLE_RATE

    def __init__(self):
        self._pipelines = {}

    @staticmethod
    def _build_pipeline(lang_code):
        # torch is already imported at module load time (see top of file);
        # Kokoro is safe to import lazily here, on first actual use.
        from kokoro import KPipeline

        # Pass repo_id explicitly to suppress Kokoro's "defaulting repo_id"
        # warning.
        return KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M")

    def _get_pipeline(self, lang_code):
        if lang_code not in self._pipelines:
            print(f"Loading Kokoro model for language '{lang_code}'...")
            self._pipelines[lang_code] = self._build_pipeline(lang_code)
        return self._pipelines[lang_code]

    def synthesize(self, text: str, voice: str, speed: float = 1.0, lang_code: str | None = None):
        """Return synthesized audio for `text` as a single numpy array.

        The accent/language pipeline is derived from the voice's first
        letter ('a' American, 'b' British, ...), matching Kokoro's own
        voice-naming convention, unless `lang_code` pins one explicitly.

        Kokoro automatically splits `text` into natural segments (on
        sentence and paragraph boundaries), so there is no character limit
        to work around; the per-segment audio is concatenated before return.
        """
        import numpy as np

        pipeline = self._get_pipeline(lang_code or voice[0])

        print(f"Generating audio locally with Kokoro (voice={voice}, speed={speed})...")

        segments = []
        generator = pipeline(text, voice=voice, speed=speed)
        for index, (_graphemes, _phonemes, audio) in enumerate(generator, start=1):
            print(f"  Segment {index}...")
            # `audio` may be a torch tensor or a numpy array; normalize to numpy.
            if hasattr(audio, "detach"):
                audio = audio.detach().cpu().numpy()
            else:
                audio = np.asarray(audio)
            segments.append(audio)

        if not segments:
            raise ValueError("Kokoro produced no audio segments for the given text.")

        return np.concatenate(segments)
