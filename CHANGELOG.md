# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/).

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

[0.1.0]: https://github.com/brienalkire/vox_bridge/releases/tag/v0.1.0
