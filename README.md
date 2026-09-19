# vox_bridge

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
  `wyoming-faster-whisper` server (the same one Home Assistant's voice
  pipeline uses). Not built yet — see Status below.

## Consumers

Each of these is its own repo, checked out as a sibling of this one, and
depends on `vox_bridge` via `pip install -e ../vox_bridge`:

- **`podcast_generator`** — CLI (and, soon, scheduled-task "drop folder")
  podcast script → audio conversion. The original app this toolkit's TTS
  side was extracted from.
- **`loremaster`** — Discord game-assistant bot; a `voice on`/`voice off`
  mention toggle speaks replies aloud via `KokoroDirectTTS`.
- **Home Assistant integration** — not started. Motivates the
  `WyomingWhisperSTT` adapter specifically (Home Assistant already runs a
  `wyoming-faster-whisper` server as part of its own voice pipeline).

## Repo Structure

```
vox_bridge/
├── README.md
├── requirements.txt
├── pyproject.toml               — makes `vox_bridge` pip-installable
│                                  (editable) for out-of-repo consumers
├── .gitignore                  — excludes hf_cache/, __pycache__, etc.
├── vox_bridge/                  — the shared, importable toolkit
│   └── tts/
│       ├── base.py              — TTSEngine interface
│       └── kokoro_direct.py     — KokoroDirectTTS adapter
└── hf_cache/                    — gitignored; local HF cache for offline Kokoro
```

(`vox_bridge/stt/` — `base.py` and `wyoming_whisper.py` — doesn't exist yet.)

## Status

- **TTS (`KokoroDirectTTS`): done.** Two consumers wired up:
  - `podcast_generator` (CLI usage — see that repo's README).
  - `loremaster` (`bot/main.py`'s voice toggle, run off the event loop via
    `asyncio.to_thread`). Requires `ffmpeg` on `PATH` — installed on this
    machine via `winget install --id Gyan.FFmpeg -e`. Not yet live-tested
    against a real Discord voice connection.
- **STT (`WyomingWhisperSTT`), Home Assistant integration: not started.**

## Offline Hugging Face cache (only needed on a firewalled machine)

`KokoroDirectTTS` always routes the Hugging Face cache to a repo-relative
`hf_cache/` (`HF_HOME`), which is harmless and useful everywhere — it keeps
a machine's downloaded weights bundled with the repo instead of scattered
in the user-global cache. **Offline mode itself is opt-in, not forced**:
`kokoro_direct.py` never sets `HF_HUB_OFFLINE` — on a machine with normal
internet access, an uncached voice just downloads into `hf_cache/` on first
use, same as vanilla Hugging Face behavior.

If you're on a machine where huggingface.co is actually firewalled (this
is why the fix exists — one of Brien's two machines, not necessarily this
one), set `HF_HUB_OFFLINE=1` yourself in that machine's own shell profile
or a `.env` you source before running — vox_bridge honors it if already
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

## History

This toolkit started as a straight extraction from `podcast_generator`'s
`tts_podcast.py`: the Kokoro-specific calls became `KokoroDirectTTS`
(implementing the new `TTSEngine` interface) behind this repo's
`vox_bridge/tts/`, while podcast-specific logic (markdown stripping, batch
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

## Next Step

- Live-test loremaster's voice toggle against a real Discord voice channel
  (`ffmpeg` is installed and on PATH now, so the remaining gap is just
  actually trying it).
- `WyomingWhisperSTT` and Home Assistant integration are not yet scheduled
  or designed in detail.
