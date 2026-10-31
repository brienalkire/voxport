# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/).

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

[0.3.0]: https://github.com/brienalkire/voxport/releases/tag/v0.3.0
[0.2.0]: https://github.com/brienalkire/voxport/releases/tag/v0.2.0
[0.1.0]: https://github.com/brienalkire/voxport/releases/tag/v0.1.0
