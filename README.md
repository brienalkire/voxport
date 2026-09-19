# vox_bridge

A shared personal voice toolkit providing TTS (text → speech) and STT
(speech → text) to multiple independent use cases — podcast generation,
the `loremaster` Discord bot, and Home Assistant — without each use case
reimplementing its own integration.

This replaces the standalone `podcast_generator` repo (`tts_podcast.py`).

## Architecture: Ports and Adapters

Two abstract interfaces ("ports"), decoupled from whatever implements them
("adapters"), so swapping an engine later means writing one new adapter,
not touching any call site.

```
TTSEngine.synthesize(text, voice) -> audio
STTEngine.transcribe(audio) -> text
```

- **`KokoroDirectTTS`** — in-process Kokoro call, model loaded once,
  resident in memory. Chosen approach for all current use cases
  (podcast generation, loremaster, Home Assistant), favoring simplicity
  and lower latency over sharing one server across processes.
- **`WyomingWhisperSTT`** — network client to an existing, already-running
  `wyoming-faster-whisper` server (the same one Home Assistant's voice
  pipeline uses). Not built in phase 1 — see Build Priorities below.

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
├── apps/
│   └── podcast/
│       ├── generator.py         — podcast-specific logic (markdown
│       │                          stripping, batch processing, file I/O)
│       ├── inputs/              — .md scripts go here
│       └── outputs/             — generated audio lands here
└── hf_cache/                    — gitignored; local HF cache for offline Kokoro
```

(`vox_bridge/stt/` — `base.py` and `wyoming_whisper.py` — doesn't exist yet;
it's phase 3+, see below.)

## Status

- **Phase 1 (podcast generation): done.** See Usage below.
- **Phase 2 (loremaster voice output): done**, in the sibling `loremaster`
  repo (`bot/main.py`) — added a `voice on`/`voice off` mention toggle that
  joins/leaves the author's current voice channel and speaks replies aloud
  there via `KokoroDirectTTS`, run off the event loop with
  `asyncio.to_thread`. `loremaster` depends on this repo via
  `pip install -e ../vox_bridge` into its bot venv. Requires `ffmpeg` on
  `PATH` for actual playback — not yet installed on this machine.
- **Phase 3+ (`WyomingWhisperSTT`, Home Assistant, STT of any kind):
  not started.**

## Usage — podcast generation

```
pip install -r requirements.txt
```

Populate `hf_cache/` (see "Offline Hugging Face cache" below), then drop
`.md` scripts into `apps/podcast/inputs/` and run:

```
python apps/podcast/generator.py
python apps/podcast/generator.py --voice af_heart --speed 1.1
python apps/podcast/generator.py apps/podcast/inputs/my-script.md --format wav --output episode01.wav
```

A script may set its own voice with a `**Voice:**` line in its header; see
`apps/podcast/generator.py`'s module docstring for full CLI details and
voice precedence rules.

### Offline Hugging Face cache (only needed on a firewalled machine)

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

## Build Priorities

**Phase 1 (done): port podcast generation, and only that.**

Take the existing, working logic from `tts_podcast.py` (from the
`podcast_generator` repo) and split it across the new structure:

- Everything that talks to Kokoro directly (`build_pipeline`,
  `get_pipeline`, `synthesize`) → becomes `KokoroDirectTTS` in
  `vox_bridge/tts/kokoro_direct.py`, implementing the `TTSEngine`
  interface (`synthesize(text, voice) -> audio`). This is the reusable
  part other consumers (loremaster, HA) will import later.
- Everything specific to *podcasts* (markdown stripping, batch mode over
  `inputs/`, file naming, voice-metadata parsing from a script's header,
  MP3/WAV writing) → stays in `apps/podcast/generator.py`, which imports
  and calls `KokoroDirectTTS`, but doesn't know anything about Kokoro
  internals directly.
- End result should behave identically to the current tool from the
  user's perspective: drop `.md` scripts in `apps/podcast/inputs/`, run
  one command, get audio in `apps/podcast/outputs/`. Command-line
  interface, batch/single-file modes, per-script `**Voice:**` metadata,
  and `--voice`/`--speed`/`--format`/`--output` flags should all be
  preserved exactly as they work today.
- **Also fix the offline/firewall issue while porting.** The Kokoro
  model must be able to load from a local, repo-relative Hugging Face
  cache instead of always reaching out to huggingface.co. The user will
  populate `hf_cache/` manually (copying it from a machine where the
  initial download isn't firewalled) — don't try to trigger a live
  download as part of this build.

  (Revised after the initial build: this only needs to *force* offline
  mode — `HF_HUB_OFFLINE=1` — on the specific machine that's actually
  firewalled. The original version of this fix set that unconditionally
  via `os.environ.setdefault`, which turned out to also silently block
  normal downloads on a machine with real internet access. See "Offline
  Hugging Face cache" above for the corrected, opt-in behavior.)

**Explicitly out of scope for phase 1** (deferred, do not build yet):

- `WyomingWhisperSTT` / any STT capability at all
- Any loremaster or Home Assistant integration
- Any script-drop-folder or email-based input pipeline (future
  exploration, not yet designed in detail)
- A shared/Wyoming-mediated TTS server mode (current decision is
  direct-call only; revisit only if resource use becomes a real problem)

**Phase 2 (done): TTS for loremaster.**

Once `KokoroDirectTTS` exists and podcast generation runs through it
cleanly, give the `loremaster` Discord bot voice output as a second
consumer of the same adapter — no new synthesis code, just a new caller.

- `loremaster` imports `KokoroDirectTTS` from `vox_bridge` the same way
  `apps/podcast/generator.py` does.
- New, loremaster-specific work (does not belong in `vox_bridge` itself):
  - Getting synthesized audio *into* a Discord voice channel (discord.py's
    voice client, `PyNaCl` + `ffmpeg`) — this is Discord-specific plumbing,
    not a toolkit concern.
  - A per-server or per-user `/loremaster voice on|off` toggle. Text
    response always posts regardless of the toggle; voice is an optional
    layer on top when enabled.
- Voice *input* for loremaster remains explicitly out of scope (see
  Migration Notes — the earlier bug was almost certainly `discord.py`'s
  immature voice-receive support, not the STT engine choice; if revisited
  later, evaluate `py-cord` first, and route transcription through
  `WyomingWhisperSTT` once that adapter exists in phase 3+, rather than
  writing bespoke STT code in the loremaster repo).

**Phase 3+ (not yet scheduled):** `WyomingWhisperSTT`, Home Assistant
integration, any script-drop-folder or email-based pipeline.

## Migration Notes

- Carry over `requirements.txt` as-is (`kokoro`, `soundfile`, `torch`,
  `numpy`) — no new dependencies needed for phase 1.
- Preserve the Windows/conda OpenMP workaround
  (`KMP_DUPLICATE_LIB_OK`) and the torch-imported-before-kokoro ordering
  — both are load-bearing for existing users on Windows/conda.
- Preserve the existing markdown-stripping rules (headers, `**Key:**`
  metadata lines, horizontal rules, italic-only production notes,
  inline formatting) exactly — this logic is podcast-specific and moves
  to `apps/podcast/generator.py` unchanged in behavior.

## Next Step

Phases 1 and 2 are built (see Status above). Remaining known follow-ups:

- Install `ffmpeg` on PATH so loremaster's voice playback actually works.
- Populate `hf_cache/` with whichever voices get used beyond the two
  (`af_heart`, `am_echo`) currently cached.
- Phase 3+ (`WyomingWhisperSTT`, Home Assistant integration, STT of any
  kind) is not yet scheduled or designed in detail.
