# voxport

A shared personal voice toolkit providing TTS (text → speech) and STT
(speech → text) to multiple independent use cases, without each one
reimplementing its own integration. This repo is a pure library — it has
no application/CLI code of its own; everything that actually *does*
something with voice lives in a separate consumer repo that depends on
this one.

## Architecture: Ports and Adapters

Two abstract interfaces ("ports"), decoupled from whatever implements them
("adapters"), so swapping an engine later means writing one new adapter,
not touching any call site.

```
TTSEngine.synthesize(text, voice) -> audio
STTEngine.transcribe(audio) -> text
```

- **`KokoroDirectTTS`** — in-process Kokoro call, model loaded once,
  resident in memory. Chosen approach for all current use cases,
  favoring simplicity and lower latency over sharing one server across
  processes.
- **`WyomingWhisperSTT`** — network client to an existing, already-running
  Wyoming-protocol Whisper server (e.g. `rhasspy/wyoming-whisper` — the
  same kind of server Home Assistant's voice pipeline uses). No model
  loading here; all transcription happens server-side.

## Installation

Requires Python 3.10+. Clone this repo as a sibling of the consumer repo,
then install it in editable mode from the consumer's environment:

```
pip install -e "../voxport[all]"
```

The base install only includes the interfaces (and numpy). Each adapter's
dependencies are an optional extra, so you install only what you use:

| Extra | Adds | For |
|---|---|---|
| `kokoro` | Kokoro, torch (~2 GB) | `KokoroDirectTTS` |
| `wyoming` | wyoming | `WyomingWhisperSTT` |
| `all` | both of the above | everything |

For example, `pip install -e "../voxport[wyoming]"` for speech-to-text
only. Importing an adapter without its extra raises an `ImportError`
naming the extra to install. To pin a consumer to a tagged release
instead of the working tree, check out that tag first (e.g.
`git checkout v0.2.0`).

`soundfile` (used in the examples below to write WAV files) isn't a
dependency of voxport; install it yourself if you need it.

Not installed by this repo:
- `WyomingWhisperSTT` needs a running Wyoming Whisper server — see
  "Running a Wyoming Whisper server" below.
- Kokoro's first run downloads model weights and spaCy's `en_core_web_sm`
  — see "Offline Hugging Face cache" below if that machine is firewalled.

## Usage

### Text → speech

```python
import soundfile as sf
from voxport.tts.kokoro_direct import KokoroDirectTTS

tts = KokoroDirectTTS()  # reuse one instance; models load once per accent
audio = tts.synthesize("Hello from voxport.", voice="af_heart", speed=1.0)
sf.write("hello.wav", audio, tts.sample_rate)  # 24 kHz mono
```

The voice name's first letter picks the accent (`a` American, `b` British,
...), following Kokoro's naming; pass `lang_code=` to override.

### Speech → text

```python
from voxport.stt.wyoming_whisper import WyomingWhisperSTT

stt = WyomingWhisperSTT(host="localhost", port=10300)  # the defaults
text = stt.transcribe(audio_16k, language="en")
```

`audio_16k` is a 1-D numpy array at `stt.sample_rate` (16 kHz mono),
either int16 or float in [-1, 1]. Resample first if your source differs
(Kokoro output is 24 kHz; Discord audio is 48 kHz stereo).

### From async code

Both calls block, and `transcribe()` runs its own event loop internally,
so call them from a worker thread inside an already-running loop:

```python
audio = await asyncio.to_thread(tts.synthesize, text, "bm_george")
text = await asyncio.to_thread(stt.transcribe, audio_16k, "en")
```

## Consumers

Each of these is its own repo, checked out as a sibling of this one, and
depends on `voxport` via an editable install with the extras it needs:

- **`podcast_generator`** — CLI and scheduled-task "drop folder" podcast
  script → audio conversion. The original app this toolkit's TTS side was
  extracted from.
- **`loremaster`** — Discord game-assistant bot. Speaks replies aloud via
  `KokoroDirectTTS`, and listens for wake-word voice questions in a voice
  channel via `WyomingWhisperSTT` (py-cord voice receive plus webrtcvad
  utterance detection, all on loremaster's side).
- **Home Assistant integration** — not started. Motivates the
  `WyomingWhisperSTT` adapter specifically (Home Assistant already runs a
  Wyoming Whisper server as part of its own voice pipeline).

## Repo Structure

```
voxport/
├── README.md
├── LICENSE
├── CHANGELOG.md                — per-release notes (also the GitHub
│                                  release notes)
├── stt_guidance.md             — build guidance the STT side was
│                                  implemented from
├── pyproject.toml               — makes `voxport` pip-installable
│                                  (editable) for out-of-repo consumers;
│                                  also the single source of dependencies
├── .gitignore                  — excludes hf_cache/, __pycache__, etc.
├── voxport/                     — the shared, importable toolkit
│   ├── tts/
│   │   ├── base.py              — TTSEngine interface
│   │   └── kokoro_direct.py     — KokoroDirectTTS adapter
│   └── stt/
│       ├── base.py              — STTEngine interface
│       └── wyoming_whisper.py   — WyomingWhisperSTT adapter
└── hf_cache/                    — gitignored; local HF cache for offline Kokoro
```

## Status

- **TTS (`KokoroDirectTTS`): built and in use** by two consumers:
  - `podcast_generator` — CLI usage, see that repo's README.
  - `loremaster` — a Discord bot's `voice on`/`voice off` toggle, run off
    the event loop via `asyncio.to_thread`. Voice playback additionally
    requires `ffmpeg` on `PATH` (not installed by this repo).
- **STT (`WyomingWhisperSTT`): built and in use** by `loremaster`'s voice
  input. Originally verified against a real local Wyoming Whisper server
  (see "Running a Wyoming Whisper server" below) — synthesized a phrase
  with `KokoroDirectTTS`, resampled it, and transcribed it back correctly
  through this adapter. Home Assistant doesn't use it yet.

## Offline Hugging Face cache (only needed on a firewalled machine)

By default, Kokoro's model weights and voice packs download to Hugging
Face's standard cache (`~/.cache/huggingface`, or wherever `HF_HOME`
points). When running from a source checkout, you can instead keep the
cache inside the repo: create an `hf_cache/` folder at the repo root
(it's gitignored) and `KokoroDirectTTS` will use it as `HF_HOME`, unless
you've already set `HF_HOME` yourself. That keeps a machine's downloaded
weights bundled with the checkout, so they can be copied to another one.
**Offline mode itself is opt-in, not forced**: `kokoro_direct.py` never
sets `HF_HUB_OFFLINE` — on a machine with normal internet access, an
uncached voice just downloads on first use, same as vanilla Hugging Face
behavior.

If you're on a machine where huggingface.co is actually firewalled (this
is why the fix exists — one of Brien's two machines, not necessarily this
one), set `HF_HUB_OFFLINE=1` yourself in that machine's own shell profile
or a `.env` you source before running — voxport honors it if already
set, it just won't set it for you. Then populate `hf_cache/` by copying an
existing cache from a machine where the initial download wasn't blocked
(Hugging Face's standard `hub/models--<org>--<name>/...` layout). With
`HF_HUB_OFFLINE=1` set, **only voices whose `.pt` file is present in that
cache will work** — an uncached voice fails with a Hub connection error
instead of a live download.

**A second, separate network dependency this does *not* cover, on either
machine:** Kokoro's English phonemizer (via `misaki`) pulls in spaCy's
`en_core_web_sm` model on first use, downloaded from a GitHub release URL,
not from Hugging Face — so `HF_HUB_OFFLINE` doesn't touch it, and it will
still try to reach the network on a machine that has never run it before.
It only downloads once per Python environment (cached in `site-packages`
after that), so this only bites a *fresh* venv on the firewalled machine.
Install it ahead of time there, while online (e.g. by copying the venv, or
running this once somewhere unrestricted first):
```
python -m spacy download en_core_web_sm
```

## Running a Wyoming Whisper server (for testing)

`WyomingWhisperSTT` is a network client — it needs something to talk to.
For local testing, run [`rhasspy/wyoming-whisper`](https://github.com/rhasspy/wyoming-faster-whisper)
in Docker (Docker Desktop must actually be running first — check with
`docker info`, not just `docker --version`):

```
docker run -d --name whisper --restart unless-stopped -p 10300:10300 -v C:\wyoming-data:/data rhasspy/wyoming-whisper --model tiny-int8 --language en
```

**The image is `rhasspy/wyoming-whisper`, not `wyoming-faster-whisper`**
(that name doesn't exist on Docker Hub — easy mistake since it matches
the GitHub repo name) — confirmed against the project's own README.
`docker logs whisper` should show `Ready` once the model's loaded;
`docker ps` should show it `healthy`. `tiny-int8` is small/fast/low-
accuracy, fine for proving the plumbing works — swap to a larger model
only once transcription quality actually matters for a real use case.

`WyomingWhisperSTT(host="localhost", port=10300)` are the defaults;
override both when pointing at different hardware later (a dedicated
always-on machine, rather than a local container).

## History

This toolkit started as a straight extraction from `podcast_generator`'s
`tts_podcast.py`: the Kokoro-specific calls became `KokoroDirectTTS`
(implementing the new `TTSEngine` interface) behind this repo's
`voxport/tts/`, while podcast-specific logic (markdown stripping, batch
processing, voice metadata) briefly lived here too, in an `apps/podcast/`
folder, before being moved back out into `podcast_generator`'s own repo as
that app's `generator.py` — restoring the same "toolkit + independent
consumer repos" shape used for `loremaster` and (eventually) Home
Assistant. `loremaster` then became the second consumer, adding a
`voice on`/`voice off` mention toggle on top of the same `KokoroDirectTTS`
adapter — no new synthesis code, just a new caller.

Along the way: the original offline-Kokoro fix forced `HF_HUB_OFFLINE=1`
unconditionally, which turned out to silently block normal downloads on a
machine with real internet access (this one) — see "Offline Hugging Face
cache" above for the corrected, opt-in version.

`STTEngine` and `WyomingWhisperSTT` were added deliberately scoped to this
repo only — no loremaster changes, no Home Assistant integration, no
decision about voice-input UX anywhere. That's intentional: loremaster
voice *input* (as opposed to the voice *output* it already has) needs its
own design pass, since discord.py has historically lacked real voice-
receive support (an earlier loremaster attempt hit exactly this, per
project notes — `py-cord`, a discord.py fork, is the suggested thing to
evaluate if that's revisited). That design pass later happened in
loremaster itself: it moved to a pinned py-cord commit for voice receive
and now uses `WyomingWhisperSTT` for wake-word voice input — still with no
loremaster-specific code in this repo.

In v0.3.0 the project was renamed from `vox_bridge` to `voxport`, ahead of
an eventual PyPI release (`vox-bridge` collides with an unrelated
`voxbridge` package there). Older changelog entries keep the old paths.

## Roadmap

- Home Assistant integration isn't scheduled or designed in detail yet.
  It depends on where the always-on Wyoming server actually ends up
  living.
- The local Docker test container is exactly that — a test fixture. It's
  not meant to be the permanent server; a dedicated always-on machine is
  the eventual target, whenever that exists.

## License

[MIT](LICENSE)
