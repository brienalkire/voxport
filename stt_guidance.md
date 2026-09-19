# STT Guidance — vox_bridge Problem 1
### Standalone build instructions for a Claude Code session. Companion to `vox_bridge_design_spec_v2.md` — read that first for context, but this file is the actual task list.

**Scope: this session only.** Build `STTEngine` + `WyomingWhisperSTT` in
`vox_bridge`, and get a local Wyoming Whisper server running to test
against. **Do not touch Loremaster or make any decision about Loremaster
voice input** — that's a separate, deferred decision (see "Problem 2" in
the design spec), explicitly out of scope here.

---

## Step 0 — Verify Docker is actually working before anything else

Docker was installed months ago and hasn't been used recently, so don't
assume it works. Check before writing any code:

```bash
docker --version
docker info
```

- If `docker --version` fails or `docker info` errors out (can't connect
  to the Docker daemon), Docker Desktop likely isn't running — start it
  first (Windows: launch Docker Desktop from the Start menu, wait for it
  to report "running").
- If Docker Desktop itself needs updating, that's a manual step outside
  this session, the update goes through Docker Desktop's own UI (or a
  fresh installer from docker.com), not something to script around. If
  `docker info` still fails after Docker Desktop is confirmed running,
  stop and flag this back rather than trying to work around it — don't
  spend time debugging a broken Docker install as part of this task.
- Once `docker info` succeeds cleanly, proceed.

## Step 1 — Run the Wyoming Faster Whisper container

```bash
docker run -d --name whisper --restart unless-stopped -p 10300:10300 ^
  -v C:\wyoming-data:/data rhasspy/wyoming-faster-whisper ^
  --model tiny-int8 --language en
```

(Note: `^` is the Windows cmd line-continuation character; if running
this from Git Bash or PowerShell, adjust to that shell's continuation
syntax, or just put it on one line.)

Confirm it started and is healthy:

```bash
docker ps          # should show "whisper" as Up
docker logs whisper # should show it finished loading the model, no errors
```

Use `tiny-int8` for now — fast, low-accuracy, sufficient for proving the
adapter works end-to-end. Don't upgrade the model size as part of this
task; that's a separate, later tuning step once transcription quality
actually matters.

## Step 2 — Confirm the server is reachable

Before writing the adapter, verify port 10300 is actually answering,
e.g. a simple TCP connection test or the `wyoming` package's own client
example, so a later adapter bug isn't confused with a server that never
came up.

## Step 3 — Build `STTEngine` (the interface)

In `vox_bridge/stt/base.py`, define the abstract interface, matching the
existing `TTSEngine` pattern already in `vox_bridge/tts/base.py`:

```python
STTEngine.transcribe(audio) -> text
```

Keep it as minimal and symmetric with `TTSEngine` as the existing
codebase's style suggests — check `vox_bridge/tts/base.py` for the exact
conventions (typing, docstring style, etc.) and mirror them.

## Step 4 — Build `WyomingWhisperSTT` (the adapter)

In `vox_bridge/stt/wyoming_whisper.py`, implement `STTEngine` as a
network client to the Wyoming server from Step 1, using the plain
`wyoming` Python package (add it to `requirements.txt`). This is a
network client only — no model loading, no local Whisper install, all
transcription work happens on the server.

Default connection target: `localhost:10300` (configurable, since this
will eventually point at different hardware once a dedicated home server
exists — don't hardcode the host).

## Step 5 — Test end-to-end

Write a small, throwaway test (a short audio clip in, expected text out)
that exercises `WyomingWhisperSTT` against the running container. This
doesn't need to be a full test suite, just proof the plumbing works
before calling this done.

## Explicitly out of scope for this session

- Anything involving Loremaster or Discord
- Home Assistant integration itself
- Upgrading the Whisper model size
- Moving the Docker container to different/dedicated hardware
- Any decision about voice input anywhere — this session only proves the
  vox_bridge-side adapter works against a local test server

Ask before adding anything not listed above.
