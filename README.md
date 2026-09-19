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
  Wyoming-protocol Whisper server (e.g. `rhasspy/wyoming-whisper` — the
  same kind of server Home Assistant's voice pipeline uses). No model
  loading here; all transcription happens server-side.

## Consumers

Each of these is its own repo, checked out as a sibling of this one, and
depends on `vox_bridge` via `pip install -e ../vox_bridge`:

- **`podcast_generator`** — CLI and scheduled-task "drop folder" podcast
  script → audio conversion. The original app this toolkit's TTS side was
  extracted from.
- **`loremaster`** — Discord game-assistant bot; a `voice on`/`voice off`
  mention toggle speaks replies aloud via `KokoroDirectTTS`.
- **`loremaster` voice input** — not started. `WyomingWhisperSTT` exists,
  but wiring it into loremaster (and the discord.py voice-receive question
  that comes with it) is an explicit separate decision — see History.
- **Home Assistant integration** — not started. Motivates the
  `WyomingWhisperSTT` adapter specifically (Home Assistant already runs a
  Wyoming Whisper server as part of its own voice pipeline).

## Repo Structure

```
vox_bridge/
├── README.md
├── LICENSE
├── pyproject.toml               — makes `vox_bridge` pip-installable
│                                  (editable) for out-of-repo consumers;
│                                  also the single source of dependencies
├── .gitignore                  — excludes hf_cache/, __pycache__, etc.
├── vox_bridge/                  — the shared, importable toolkit
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
- **STT (`WyomingWhisperSTT`): built, not wired into any consumer yet.**
  Verified against a real local Wyoming Whisper server (see "Running a
  Wyoming Whisper server" below) — synthesized a phrase with
  `KokoroDirectTTS`, resampled it, and transcribed it back correctly
  through this adapter. No consumer (loremaster, Home Assistant) uses it
  yet; that's a deliberately separate decision.

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

`STTEngine` and `WyomingWhisperSTT` were added deliberately scoped to this
repo only — no loremaster changes, no Home Assistant integration, no
decision about voice-input UX anywhere. That's intentional: loremaster
voice *input* (as opposed to the voice *output* it already has) needs its
own design pass, since discord.py has historically lacked real voice-
receive support (an earlier loremaster attempt hit exactly this, per
project notes — `py-cord`, a discord.py fork, is the suggested thing to
evaluate if that's revisited).

## Roadmap

- Wiring `WyomingWhisperSTT` into a consumer — loremaster voice input or
  Home Assistant — isn't scheduled or designed in detail yet. Both are
  real open questions, not just "connect the adapter": loremaster's
  depends on discord.py/py-cord's voice-receive capabilities, and Home
  Assistant's depends on where the always-on Wyoming server actually ends
  up living.
- The local Docker test container is exactly that — a test fixture. It's
  not meant to be the permanent server; a dedicated always-on machine is
  the eventual target, whenever that exists.

## License

[MIT](LICENSE)
