#!/usr/bin/env python3
"""
generator.py

Convert markdown podcast scripts into spoken-word audio files, using
`KokoroDirectTTS` from `vox_bridge` for the actual speech synthesis. No API
key is required and no data leaves your machine.

The script reads a markdown file, strips markdown formatting, the metadata
header block, and non-spoken section labels (e.g. OPENING, PART ONE, CLOSING),
then synthesizes speech locally and saves the result as an audio file.

Batch mode (default):
    Place one or more `.md` scripts in the `inputs/` subdirectory and run the
    script with no arguments. Every script is converted and the audio is
    written to the `outputs/` subdirectory using the same base filename.

        python generator.py
        python generator.py --voice af_heart --speed 1.1

    Both `inputs/` and `outputs/` are resolved relative to this script's
    location, and `outputs/` is created automatically.

Single-file mode:
    Pass a path to one script to convert just that file. The audio still lands
    in `outputs/` by default, or wherever `--output` points.

        python generator.py inputs/my-script.md
        python generator.py my-script.md --format wav --output episode01.wav

Per-script voice:
    A script may choose its own voice with a metadata line anywhere in its
    header, e.g.

        **Voice:** af_heart

    Voice precedence is: a `--voice` given on the command line (applies to the
    whole run) overrides everything; otherwise a script's `**Voice:**` line is
    used; otherwise the default voice. The `--lang` accent code is derived
    automatically from the voice's first letter unless you pass `--lang`.

Requirements:
    - Python 3.x
    - The `kokoro` and `soundfile` packages:  pip install -r requirements.txt
    - Recommended: espeak-ng installed on your system for best pronunciation
      of unusual words and numbers (see the instructions file for details).
    - For MP3 output: either a recent `soundfile`/libsndfile build with MP3
      support, or `ffmpeg` available on your PATH. WAV needs neither.
    - The first run requires a populated `hf_cache/` at the repo root (see
      the repo README) since the model loads offline.

Defaults:
    Voice: am_onyx  (American male; deep and authoritative)
    Language: derived from the voice (a = American, b = British)
    Speed: 1.0
    Format: mp3
"""

import argparse
import glob
import os
import sys
import re

# Make the `vox_bridge` package importable regardless of current working
# directory, without requiring it to be pip-installed first.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

DEFAULT_VOICE = "am_onyx"
DEFAULT_SPEED = 1.0
DEFAULT_FORMAT = "mp3"
FORMAT_CHOICES = ["mp3", "wav"]

# Input scripts are read from `inputs/` and audio is written to `outputs/`,
# both resolved relative to this file so the tool works regardless of the
# current working directory.
INPUT_DIR = os.path.join(SCRIPT_DIR, "inputs")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "outputs")

# A selection of Kokoro voices. The first letter is the language/accent
# ('a' American, 'b' British), the second is gender ('m' male, 'f' female).
# This list drives the --help text and the choices check; see the Kokoro
# documentation for the full, current voice list.
VOICE_CHOICES = [
    # American male
    "am_onyx", "am_adam", "am_echo", "am_eric", "am_fenrir",
    "am_liam", "am_michael", "am_puck",
    # American female
    "af_heart", "af_bella", "af_nova", "af_sarah", "af_sky",
    "af_nicole", "af_aoede", "af_kore",
    # British male
    "bm_george", "bm_lewis", "bm_daniel", "bm_fable",
    # British female
    "bf_emma", "bf_isabella", "bf_alice", "bf_lily",
]

# A per-script voice line, e.g.  **Voice:** af_heart  (case-insensitive key).
# This line is also stripped from the spoken text by strip_markdown() because
# it matches the general **Key:** metadata pattern.
voice_meta_pattern = re.compile(
    r"^\s*\*\*\s*Voice\s*:\s*\*\*\s*([A-Za-z]{2}_[A-Za-z0-9]+)\s*$",
    re.IGNORECASE,
)


def parse_voice_metadata(raw_text):
    """Return the voice named in a `**Voice:** <voice>` line, or None.

    The first such line in the script wins.
    """
    for line in raw_text.splitlines():
        match = voice_meta_pattern.match(line)
        if match:
            return match.group(1)
    return None


def resolve_voice(raw_text, cli_voice):
    """Pick the voice for one script.

    Precedence: an explicit --voice (whole run) > the script's **Voice:** line
    > the built-in default. Raises ValueError if a script names an unknown
    voice.
    """
    if cli_voice:
        return cli_voice

    meta_voice = parse_voice_metadata(raw_text)
    if meta_voice:
        if meta_voice not in VOICE_CHOICES:
            raise ValueError(
                f"script requests unknown voice '{meta_voice}'. Valid voices: "
                f"{', '.join(VOICE_CHOICES)}."
            )
        return meta_voice

    return DEFAULT_VOICE


def strip_markdown(raw_text):
    """Strip markdown formatting, metadata, and section labels from the script.

    Returns clean prose suitable for text-to-speech: only the words that
    should actually be spoken aloud.
    """
    lines = raw_text.splitlines()
    cleaned_lines = []

    # A metadata line looks like:  **Author:** Brien Alkire
    metadata_pattern = re.compile(r"^\s*\*\*[^*]+:\*\*")
    # A horizontal rule:  ---  or  ***  or  ___  (3 or more)
    hrule_pattern = re.compile(r"^\s*([-*_])\1{2,}\s*$")
    # A line that is entirely italic, e.g.  *End of script.*  (production note)
    italic_only_pattern = re.compile(r"^\s*\*[^*]+\*\s*$")

    for line in lines:
        stripped = line.strip()

        # Drop blank lines for now; paragraph breaks are reconstructed later.
        if not stripped:
            cleaned_lines.append("")
            continue

        # Stop at end-of-script marker so trailing notes/appendices are not spoken.
        if italic_only_pattern.match(stripped):
            break

        # Drop markdown headers (#, ##, ###, ...). In these scripts the
        # section labels (OPENING, PART ONE, CLOSING, etc.) are headers,
        # so this also removes the spoken-aloud section labels.
        if stripped.startswith("#"):
            continue

        # Drop horizontal rules.
        if hrule_pattern.match(stripped):
            continue

        # Drop metadata key/value lines (Author, Date, Version, Voice, etc.).
        if metadata_pattern.match(stripped):
            continue

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Strip inline markdown formatting from the remaining prose.
    # Bold + italic markers.
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)   # **bold**
    text = re.sub(r"__([^_]+)__", r"\1", text)         # __bold__
    text = re.sub(r"\*([^*]+)\*", r"\1", text)          # *italic*
    text = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", text)  # _italic_
    # Inline code: `code` -> code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Links: [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Collapse runs of blank lines into a single blank line, and trim.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def write_audio(full_audio, out_path, fmt, sample_rate):
    """Write `full_audio` to `out_path` in the requested format.

    WAV is written directly. MP3 is attempted via libsndfile's native encoder
    first, falling back to converting a temporary WAV with ffmpeg.
    """
    import soundfile as sf

    if fmt == "wav":
        sf.write(out_path, full_audio, sample_rate)
        return

    # MP3: try libsndfile's native MP3 encoder first.
    try:
        sf.write(out_path, full_audio, sample_rate, format="MP3")
        return
    except Exception:  # noqa: BLE001 - libsndfile may lack MP3 support
        pass

    # Fall back to writing a WAV and converting with ffmpeg.
    import shutil
    import subprocess
    import tempfile

    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "Could not write MP3: the installed libsndfile lacks MP3 support "
            "and ffmpeg was not found on PATH. Install ffmpeg, or rerun with "
            "--format wav."
        )

    fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        sf.write(tmp_wav, full_audio, sample_rate)
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_wav, out_path],
            check=True, capture_output=True,
        )
    finally:
        try:
            os.remove(tmp_wav)
        except OSError:
            pass


def resolve_jobs(args):
    """Return a list of (input_path, output_path) tuples to process.

    With no positional argument, every `*.md` file in `inputs/` is queued.
    With a path argument, only that single file is queued. Output paths land
    in `outputs/` by default; `--output` overrides that in single-file mode.
    """
    fmt = args.response_format

    if args.input_path:
        inputs = [args.input_path]
    else:
        if not os.path.isdir(INPUT_DIR):
            raise FileNotFoundError(
                f"No input file given and the inputs directory does not exist: "
                f"{INPUT_DIR}\nCreate it and add one or more .md scripts, or "
                f"pass a script path directly."
            )
        inputs = sorted(glob.glob(os.path.join(INPUT_DIR, "*.md")))
        if not inputs:
            raise FileNotFoundError(
                f"No .md scripts found in {INPUT_DIR}. Add one or more .md "
                f"files there, or pass a script path directly."
            )

    jobs = []
    for input_path in inputs:
        # Honor --output only when converting a single explicitly named file.
        if args.output and args.input_path and len(inputs) == 1:
            output_path = args.output
        else:
            base = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(OUTPUT_DIR, base + "." + fmt)
        jobs.append((input_path, output_path))

    return jobs


def process_job(engine, input_path, output_path, args):
    """Convert a single script to audio. Raises on any failure."""
    with open(input_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    voice = resolve_voice(raw_text, args.voice)
    # The accent code must match the voice; derive it from the voice's first
    # letter unless the caller pinned one with --lang.
    lang_code = args.lang_code if args.lang_code else voice[0]

    cleaned = strip_markdown(raw_text)
    if not cleaned.strip():
        raise ValueError("no spoken text found after stripping the markdown.")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    full_audio = engine.synthesize(cleaned, voice, speed=args.speed, lang_code=lang_code)
    write_audio(full_audio, output_path, args.response_format, engine.sample_rate)


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="generator.py",
        description="Convert markdown podcast scripts into spoken-word audio "
                    "files using Kokoro, a free local TTS model. With no "
                    "argument, converts every .md script in the inputs/ "
                    "directory and writes the audio to outputs/.",
    )
    parser.add_argument(
        "input_path",
        metavar="input_script.md",
        nargs="?",
        default=None,
        help="Optional path to a single markdown script. If omitted, every "
             ".md file in the inputs/ directory is converted.",
    )
    parser.add_argument(
        "--voice",
        choices=VOICE_CHOICES,
        default=None,
        metavar="VOICE",
        help=f"Kokoro voice for the whole run, overriding any per-script "
             f"**Voice:** line (default: the script's own voice, or "
             f"{DEFAULT_VOICE}). The accent is derived from the voice's first "
             f"letter ('a' American, 'b' British) unless --lang is given.",
    )
    parser.add_argument(
        "--lang",
        dest="lang_code",
        default=None,
        help="Language/accent code ('a' American English, 'b' British "
             "English). Defaults to the first letter of the chosen voice.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=DEFAULT_SPEED,
        help=f"Speaking rate multiplier (default: {DEFAULT_SPEED}; "
             "e.g. 0.9 slower, 1.1 faster).",
    )
    parser.add_argument(
        "--format",
        dest="response_format",
        choices=FORMAT_CHOICES,
        default=DEFAULT_FORMAT,
        help=f"Audio output format (default: {DEFAULT_FORMAT}).",
    )
    parser.add_argument(
        "--output",
        metavar="output_file",
        default=None,
        help="Output file path. Only used in single-file mode; ignored when "
             "converting the whole inputs/ directory. Defaults to "
             "outputs/<script-name>.<format>.",
    )
    return parser.parse_args(argv[1:])


def main(argv):
    args = parse_args(argv)

    try:
        # Import vox_bridge.tts.kokoro_direct first: it sets the env vars and
        # imports torch in the order required to avoid a Windows/conda DLL
        # conflict (see that module for why) — importing soundfile/numpy
        # ahead of it here would undo that.
        from vox_bridge.tts.kokoro_direct import KokoroDirectTTS
        import soundfile  # noqa: F401
        import numpy  # noqa: F401
    except ImportError:
        print("Error: required packages are not installed. Install them with: "
              " pip install -r requirements.txt", file=sys.stderr)
        return 1

    if args.output and not args.input_path:
        print("Note: --output is ignored in batch mode; audio is written to "
              "outputs/ using each script's name.", file=sys.stderr)

    try:
        jobs = resolve_jobs(args)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Validate up front that any explicitly named single file actually exists.
    if args.input_path and not os.path.isfile(args.input_path):
        print(f"Error: file not found: {args.input_path}", file=sys.stderr)
        return 1

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Found {len(jobs)} script(s) to convert.")

    # A single engine instance is reused across every script in the run;
    # KokoroDirectTTS caches its pipeline by language, so the model loads at
    # most once per accent used in the run.
    engine = KokoroDirectTTS()

    succeeded = []
    failed = []
    for input_path, output_path in jobs:
        print(f"\n=== {os.path.basename(input_path)} -> {output_path} ===")
        try:
            process_job(engine, input_path, output_path, args)
        except Exception as exc:  # noqa: BLE001 - keep going on the next script
            print(f"Error converting {input_path}: {exc}", file=sys.stderr)
            failed.append(input_path)
            continue
        print(f"Saved audio to: {output_path}")
        succeeded.append(output_path)

    print(f"\nDone. {len(succeeded)} succeeded, {len(failed)} failed.")
    if failed:
        for path in failed:
            print(f"  Failed: {path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
