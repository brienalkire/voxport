# voxport

Small Python interfaces for text-to-speech and speech-to-text, with
swappable engine adapters. Your code calls one method,
`synthesize()` or `transcribe()`, and never touches an engine's API
directly, so switching engines means changing one line where the adapter
is created.

```
TTSEngine.synthesize(text, voice) -> audio
STTEngine.transcribe(audio) -> text
```

Included adapters:

- **`KokoroDirectTTS`**: runs the [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M)
  TTS model in your own process. The model loads once and stays in
  memory, with no server and no network hop.
- **`WyomingWhisperSTT`**: a client for a [Wyoming](https://github.com/OHF-Voice/wyoming)
  protocol Whisper server, the same kind of server Home Assistant's voice
  pipeline uses. It loads no model itself; transcription happens on the
  server.

voxport is a library only: it has no command-line tool or app of its
own. It is pre-1.0, so the API may still change between minor versions
(see the [changelog](https://github.com/brienalkire/voxport/blob/main/CHANGELOG.md)).

## Installation

Requires Python 3.10+. Each adapter's dependencies are an optional
extra, so you install only what you use:

```
pip install "voxport[kokoro]"    # KokoroDirectTTS
pip install "voxport[wyoming]"   # WyomingWhisperSTT
pip install "voxport[all]"       # both
```

| Extra | Adds | For |
|---|---|---|
| `kokoro` | Kokoro, torch (about 2 GB) | `KokoroDirectTTS` |
| `wyoming` | wyoming | `WyomingWhisperSTT` |
| `all` | both of the above | everything |

A plain `pip install voxport` includes only the interfaces and numpy.
Importing an adapter without its extra raises an `ImportError` that
names the extra to install.

Things voxport doesn't install for you:

- `WyomingWhisperSTT` needs a running Wyoming Whisper server. See
  [Running a Wyoming Whisper server](#running-a-wyoming-whisper-server).
- On first use, Kokoro downloads its model weights and voice packs from
  Hugging Face, and spaCy's `en_core_web_sm` English model. See
  [Offline use](#offline-use) for machines that can't reach those.
- `soundfile`, used in the examples below to write WAV files.

## Usage

### Text to speech

```python
import soundfile as sf
from voxport.tts.kokoro_direct import KokoroDirectTTS

tts = KokoroDirectTTS()  # reuse one instance; models load once per accent
audio = tts.synthesize("Hello from voxport.", voice="af_heart", speed=1.0)
sf.write("hello.wav", audio, tts.sample_rate)  # 24 kHz mono
```

`synthesize()` returns a 1-D numpy array. The first letter of the voice
name picks the accent (`a` American, `b` British, ...), following
Kokoro's voice naming; pass `lang_code=` to override it. Kokoro splits
long text into segments itself, so there is no length limit.

### Speech to text

```python
from voxport.stt.wyoming_whisper import WyomingWhisperSTT

stt = WyomingWhisperSTT(host="localhost", port=10300)  # the defaults
text = stt.transcribe(audio_16k, language="en")
```

`audio_16k` is a 1-D numpy array of mono audio at `stt.sample_rate`
(16 kHz), either int16 samples or floats in [-1, 1]. Resample first if
your audio has a different rate; Kokoro's output, for example, is
24 kHz. Each call opens a new connection to the server.

### From async code

Both calls block, and `transcribe()` runs its own asyncio event loop, so
from code that already has a running loop, call them in a worker thread:

```python
audio = await asyncio.to_thread(tts.synthesize, text, "bm_george")
text = await asyncio.to_thread(stt.transcribe, audio_16k, "en")
```

## Writing your own adapter

An adapter subclasses `TTSEngine` or `STTEngine`, sets `sample_rate`,
and implements the one abstract method:

```python
import numpy as np
from voxport.tts.base import TTSEngine

class SilenceTTS(TTSEngine):
    """A toy engine: one second of silence, whatever the text."""

    sample_rate = 16000

    def synthesize(self, text: str, voice: str, speed: float = 1.0):
        return np.zeros(self.sample_rate, dtype=np.float32)
```

Code written against `TTSEngine` works with `SilenceTTS` and
`KokoroDirectTTS` unchanged. Adapters may accept extra, engine-specific
keyword arguments (like `KokoroDirectTTS`'s `lang_code`), as long as the
base signature still works.

## Offline use

By default, Kokoro's weights and voice packs download to Hugging Face's
standard cache (`~/.cache/huggingface`, or wherever `HF_HOME` points).
To run on a machine that can't reach huggingface.co:

1. On a machine with internet access, synthesize once with each voice
   you plan to use, so the model and those voice packs are cached.
2. Copy that cache to the offline machine, keeping Hugging Face's
   `hub/models--<org>--<name>/...` layout, and point `HF_HOME` at it.
3. Set `HF_HUB_OFFLINE=1` on the offline machine. voxport never sets
   this for you. With it set, only voices already in the cache work; an
   uncached voice fails with a Hub connection error instead of
   downloading.

Kokoro's English phonemizer also needs spaCy's `en_core_web_sm` model,
which downloads from GitHub, not Hugging Face, so `HF_HUB_OFFLINE`
doesn't cover it. It downloads once per Python environment, so install
it while online:

```
python -m spacy download en_core_web_sm
```

**Repo-local cache (source checkouts only).** If you run voxport from a
clone, you can keep the cache inside it instead: create an `hf_cache/`
folder at the repo root (it's gitignored) and `KokoroDirectTTS` uses it
as `HF_HOME`, unless you've set `HF_HOME` yourself. That makes the
cache easy to copy along with the checkout.

## Running a Wyoming Whisper server

`WyomingWhisperSTT` needs a server to talk to. For local testing, the
easiest option is the [`rhasspy/wyoming-whisper`](https://github.com/rhasspy/wyoming-faster-whisper)
Docker image:

```
docker run -d --name whisper --restart unless-stopped -p 10300:10300 -v wyoming-data:/data rhasspy/wyoming-whisper --model tiny-int8 --language en
```

The image is named `rhasspy/wyoming-whisper`, even though its GitHub
repo is `wyoming-faster-whisper`. `docker logs whisper` shows `Ready`
once the model has loaded. `tiny-int8` is small and fast but not very
accurate; use a larger model when transcription quality matters.

If you already run Home Assistant with its Whisper add-on, you can point
`WyomingWhisperSTT` at that server's host and port instead.

## Development

```
git clone https://github.com/brienalkire/voxport.git
cd voxport
pip install -e ".[all]"
```

## License

[MIT](https://github.com/brienalkire/voxport/blob/main/LICENSE)
