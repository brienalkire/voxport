# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/).

## [0.5.0] - 2026-11-01

`KokoroDirectTTS` progress messages move from `print()` to `logging`, so
apps decide whether they appear.

### Changed
- **Breaking (output):** `KokoroDirectTTS` reports progress through `logging` (the
  `voxport.tts.kokoro_direct` logger) instead of `print()`: model loads
  and each synthesis at INFO, per-segment progress at DEBUG. Python
  hides messages below WARNING by default, so these lines no longer
  appear unless the app enables them, e.g.
  `logging.getLogger("voxport").setLevel(logging.INFO)` after its own
  `logging.basicConfig(...)`.

### Added
- Tests for `KokoroDirectTTS` using stand-in `torch` and `kokoro`
  modules: segment concatenation, one pipeline per language, the
  `lang_code` override, logging, and the empty-output error. They run in
  CI without the 2 GB torch download.

## [0.4.0] - 2026-11-01

First public release, and the first on PyPI (`pip install voxport`).
Adapter dependencies become optional extras, so installs pull in only
what they use.

### Added
- Tests (`tests/`): the two interfaces, `WyomingWhisperSTT` against a
  fake in-process Wyoming server, and the missing-extra import errors.
- GitHub Actions CI: tests on Python 3.10–3.14 (Linux) and 3.12
  (Windows), a run without extras, and a package build checked with
  `twine check --strict`.
- A publish workflow: pushing a version tag tests and builds the
  package, publishes it to PyPI via Trusted Publishing, and creates the
  GitHub release from this changelog.
- Package metadata for PyPI: description, author, keywords, classifiers
  and project links.

### Changed
- **Breaking:** adapter dependencies are now optional extras, so an
  install only pulls in what it uses. The base install has just the
  interfaces and numpy; `voxport[kokoro]` adds Kokoro and torch for
  `KokoroDirectTTS`, `voxport[wyoming]` adds wyoming for
  `WyomingWhisperSTT`, and `voxport[all]` adds both. Consumers must
  reinstall with the extra they need (e.g.
  `pip install -e "../voxport[all]"`).
- **Breaking:** `soundfile` is no longer a dependency. voxport never used
  it; consumers that write audio files must install it themselves.
- Importing an adapter without its extra raises an `ImportError` naming
  the extra to install, instead of a bare `ModuleNotFoundError`.
- `KokoroDirectTTS` uses the repo-root `hf_cache/` folder as `HF_HOME`
  only if that folder already exists; otherwise Hugging Face's standard
  cache is used. Before, it always pointed `HF_HOME` next to the source
  code, which for a regular (non-editable) install meant inside
  `site-packages`. Existing checkouts that already have `hf_cache/` are
  unaffected.
- README rewritten for a public audience: `pip install` with extras, a
  "Writing your own adapter" example, step-by-step offline use, and an
  OS-neutral Docker command for the Whisper server.
- Building now requires setuptools 77+, the first version that accepts
  the `license = "MIT"` expression already in `pyproject.toml`.

### Removed
- `stt_guidance.md`, the task list the STT side was built from. That
  work is recorded under 0.2.0 below.

## [0.3.0] - 2026-10-31

Renames the project from `vox_bridge` to `voxport`. No functional changes.

### Changed
- **Breaking:** the package and import name is now `voxport`
  (`from voxport.tts.kokoro_direct import KokoroDirectTTS`). Consumers
  must update their imports and reinstall (`pip uninstall vox_bridge`,
  then `pip install -e ../voxport`).
- Distribution name in `pyproject.toml` is now `voxport`; the GitHub repo
  moves to `brienalkire/voxport`.

### Why
- Preparing for an eventual PyPI release. `vox-bridge` can't be used
  there: an unrelated `voxbridge` project already exists, and PyPI
  rejects names that differ only by `-`, `_` or `.`. "port" also matches
  the toolkit's ports-and-adapters design.

## [0.2.0] - 2026-09-19

Adds the STT side of the toolkit: an `STTEngine` port and one working
adapter, `WyomingWhisperSTT`. Library-only — no consumer wiring yet (see
Notes).

### Added
- `STTEngine` interface (`vox_bridge/stt/base.py`), mirroring `TTSEngine`:
  `transcribe(audio) -> str`.
- `WyomingWhisperSTT` (`vox_bridge/stt/wyoming_whisper.py`) — a network
  client to a running [Wyoming](https://github.com/OHF-Voice/wyoming)
  protocol Whisper server (e.g. `rhasspy/wyoming-whisper`), the same kind
  of server Home Assistant's own voice pipeline talks to. Unlike
  `KokoroDirectTTS`, this adapter does no local model loading — all
  transcription happens server-side. Host/port are configurable
  (`localhost:10300` default), not hardcoded, since this will eventually
  point at dedicated hardware rather than a local test container.
- `wyoming` added as a dependency (`pyproject.toml`).

### Verified
- A local `rhasspy/wyoming-whisper` Docker container (`tiny-int8` model),
  tested via a round trip through this repo's own `KokoroDirectTTS`:
  synthesized a known phrase, resampled 24kHz → 16kHz, transcribed it back
  through `WyomingWhisperSTT`, and confirmed the text matched.

### Notes
- Corrects a wrong image name in the build guidance this was implemented
  from (`rhasspy/wyoming-faster-whisper`, which doesn't exist) — the real
  image is `rhasspy/wyoming-whisper`.
- Deliberately out of scope for this release: any loremaster wiring, any
  Home Assistant integration, and any decision about voice input UX
  anywhere. This release only proves the vox_bridge-side adapter works
  against a real server.

## [0.1.0] - 2026-09-19

Initial release: a `TTSEngine` port/adapter toolkit with one working
adapter, `KokoroDirectTTS`.

### Added
- `TTSEngine` interface (`vox_bridge/tts/base.py`) and `KokoroDirectTTS`
  (`vox_bridge/tts/kokoro_direct.py`), an in-process Kokoro TTS adapter
  with the model loaded once and kept resident in memory, ported from a
  standalone script (`podcast_generator`'s original `tts_podcast.py`).
- Repo-relative Hugging Face cache (`hf_cache/`, via `HF_HOME`) so a
  machine's downloaded model weights travel with the repo. Offline mode
  (`HF_HUB_OFFLINE`) is opt-in — only set by a machine that actually needs
  it — rather than forced by this package.
- Packaged as an editable-installable library (`pyproject.toml`) for
  sibling consumer repos (`pip install -e ../vox_bridge`).
- Two working consumers: `podcast_generator` (CLI / scheduled "drop
  folder" script-to-audio conversion) and `loremaster` (a Discord bot's
  `voice on`/`voice off` spoken-reply toggle).

### Fixed
- Windows/conda OpenMP DLL conflict (`KMP_DUPLICATE_LIB_OK`) and a
  torch-vs-numpy/MKL import-order bug, both handled once inside this
  package (at `kokoro_direct.py` import time) so no consumer needs to
  reproduce the workaround itself.

[0.5.0]: https://github.com/brienalkire/voxport/releases/tag/v0.5.0
[0.4.0]: https://github.com/brienalkire/voxport/releases/tag/v0.4.0
[0.3.0]: https://github.com/brienalkire/voxport/releases/tag/v0.3.0
[0.2.0]: https://github.com/brienalkire/voxport/releases/tag/v0.2.0
[0.1.0]: https://github.com/brienalkire/voxport/releases/tag/v0.1.0
