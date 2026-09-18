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
├── .gitignore                  — excludes hf_cache/, __pycache__, etc.
├── vox_bridge/                  — the shared, importable toolkit
│   ├── tts/
│   │   ├── base.py              — TTSEngine interface
│   │   └── kokoro_direct.py     — KokoroDirectTTS adapter
│   └── stt/
│       ├── base.py              — STTEngine interface (phase 2+)
│       └── wyoming_whisper.py   — WyomingWhisperSTT adapter (phase 2+, not built yet)
├── apps/
│   └── podcast/
│       ├── generator.py         — podcast-specific logic (markdown
│       │                          stripping, batch processing, file I/O)
│       ├── inputs/              — .md scripts go here
│       └── outputs/             — generated audio lands here
└── hf_cache/                    — gitignored; local HF cache for offline Kokoro
```

## Build Priorities

**Phase 1 (this build): port podcast generation, and only that.**

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
  model must load from a local, repo-relative Hugging Face cache rather
  than reaching out to huggingface.co every run. Set both of these
  early in the module, before any Kokoro-related import, consistent
  with the existing `KMP_DUPLICATE_LIB_OK` pattern already in the script:
  ```python
  os.environ.setdefault("HF_HOME", os.path.join(SCRIPT_DIR, "hf_cache"))
  os.environ.setdefault("HF_HUB_OFFLINE", "1")
  ```
  The user will populate `hf_cache/` manually (copying it from a machine
  where the initial download isn't firewalled) — don't try to trigger a
  live download as part of this build.

**Explicitly out of scope for phase 1** (deferred, do not build yet):

- `WyomingWhisperSTT` / any STT capability at all
- Any loremaster or Home Assistant integration
- Any script-drop-folder or email-based input pipeline (future
  exploration, not yet designed in detail)
- A shared/Wyoming-mediated TTS server mode (current decision is
  direct-call only; revisit only if resource use becomes a real problem)

**Phase 2 (next, after phase 1 is working): TTS for loremaster.**

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

Open this repo in Claude Code, with the old `podcast_generator` repo
(`tts_podcast.py`, `requirements.txt`) available for reference, and use
a prompt along these lines:

> Read README.md. I'm porting an existing working script, tts_podcast.py
> (attached/referenced), into this repo's new structure. Split its logic
> per the "Build Priorities" section: pull the Kokoro-specific calls into
> vox_bridge/tts/kokoro_direct.py as a KokoroDirectTTS class implementing
> a TTSEngine interface (define that interface in vox_bridge/tts/base.py
> first), and keep everything podcast-specific in apps/podcast/generator.py,
> which imports and uses KokoroDirectTTS. Preserve all existing
> command-line behavior exactly. Also add the HF_HOME/HF_HUB_OFFLINE
> environment variable fix described in the README. Do not build
> anything listed under "Explicitly out of scope." Ask before adding
> anything not covered here.
