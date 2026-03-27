#!/usr/bin/env python3
"""
transcribe.py

CLI wrapper for the OTTER PoC pipeline system.

This script is meant to be called from Electron (main process), and communicates
results via STDOUT (JSON). Diagnostic output (progress, logs) goes to STDERR.

Supported commands:
  - list: print available transcribers and post-processors (with option schemas)
  - run:  execute a pipeline spec on an audio file and print resulting word array

Examples:
  python3 -m otter_py.transcribe list
  python3 -m otter_py.transcribe run --audio /path/to.wav --spec-file spec.json
  python3 -m otter_py.transcribe run --audio /path/to.wav --spec-json '{"transcriber": {...}, "post": [...]}'

The pipeline JSON uses a top-level "post" array for post-processors (each entry: id + opts).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional
from contextlib import redirect_stdout
from pydash import get as deep_get
from otter_py.util import eprint, _start_elapsed_timer
from otter_py.cacheUtil import _cache_key, _cache_dir,  _load_cache, _save_cache

def run_with_stdout_redirect(fn):
    """
    Run `fn()` with stdout redirected to stderr.

    Rationale:
      Many ML/audio libraries print informational messages to stdout.
      Our contract is that stdout is reserved for machine-readable JSON.
      Redirecting stdout to stderr prevents accidental corruption of JSON output.
    """
    with redirect_stdout(sys.stderr):
        return fn()

def _coerce_pipeline_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Canonical pipeline spec uses `post` for the ordered list of post-processors.
    Legacy alias `postprocessors` is accepted and normalized to `post`.
    """
    if "postprocessors" in spec:
        if "post" in spec:
            raise ValueError("Provide only one of 'post' or 'postprocessors'")
        spec = dict(spec)
        spec["post"] = spec.pop("postprocessors")
    return spec


def read_spec(spec_json: Optional[str], spec_file: Optional[str]) -> Dict[str, Any]:
    """Load the pipeline spec from a JSON string or file."""
    if spec_json and spec_file:
        raise ValueError("Provide only one of --spec-json or --spec-file")

    if spec_file:
        with open(spec_file, "r", encoding="utf-8") as f:
            return _coerce_pipeline_spec(json.load(f))

    if spec_json:
        return _coerce_pipeline_spec(json.loads(spec_json))

    raise ValueError("Missing pipeline spec. Provide --spec-json or --spec-file")

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="OTTER PoC transcription pipeline runner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List available transcribers and post-processors")

    p_run = sub.add_parser("run", help="Run a pipeline spec on an audio file")
    p_run.add_argument("--audio", required=True, help="Path to input audio file")
    p_run.add_argument("--spec-json", help="Pipeline spec as JSON string")
    p_run.add_argument("--spec-file", help="Path to pipeline spec JSON file")
    p_run.add_argument("--no-cache", action="store_true", help="Skip cache and overwrite cached result")
    p_clear = sub.add_parser("clear-cache", help="Delete all cached results (for testing/debugging)") 

    # Optional: let Electron ask for meta too (debug)
    p_run.add_argument("--emit-meta", action="store_true", help="Emit {words, meta} instead of just words[]")

    args = parser.parse_args(argv)

    # Ensure repo root is on sys.path when invoked as a script (not as -m).
    # This makes 'import py....' work more reliably.
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.dirname(here)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    if args.cmd == "list":
        from otter_py.pipeline_registry import load_components, list_components
        load_components()  # ensure components are loaded before listing
        data = list_components()
        json.dump(data, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.cmd == "run":
        from otter_py.pipeline_registry import load_components, run_pipeline
        load_components()  # ensure components are loaded before running
        try:
            spec = read_spec(args.spec_json, args.spec_file)
        except (ValueError, json.JSONDecodeError) as e:
            eprint(f"ERROR:SpecError:{e}")
            return 1

        audio_path = args.audio
        if not os.path.exists(audio_path):
            eprint(f"ERROR:FileNotFoundError:Audio file not found: {audio_path}")
            return 1

        # Progress callback for Electron:
        # - emit "PROGRESS:NN" lines to stderr (easy to parse, keeps stdout clean)
        def progress(pct: int) -> None:
            eprint(f"PROGRESS:{pct}")

        ctx: Dict[str, Any] = {"progress": progress}
        cache_key = _cache_key(audio_path, spec)
        cached = None if args.no_cache else _load_cache(cache_key)
        # Run the pipeline with stdout redirected to stderr so that any library
        # chatter (e.g. WhisperX notices) can't corrupt our JSON output channel.
        if cached is not None:
            eprint("INFO:cache hit, skipping pipeline execution")
            result = cached
        else:
            eprint("INFO:cache miss, running pipeline")
            try:
                import soundfile as sf
                duration = sf.info(audio_path).duration
                eprint(f"INFO:audio duration is {duration:.2f} seconds")
            except Exception:
                duration = 0
            PARALLEL_THRESHOLD =  20 * 60 # seconds; if audio is longer than this, warn about potential parallel execution
            use_parallel = duration > PARALLEL_THRESHOLD
            timer = _start_elapsed_timer()

            try:
                if use_parallel:
                    from otter_py.parallel_transcribe import transcribe_parallel
                    eprint(f"INFO:audio duration exceeds {PARALLEL_THRESHOLD/60:.0f} minutes, enabling parallel execution (if supported by transcriber)")
                    from otter_py.pipeline_registry import _POSTS
                    import time

                    t_opts =(spec.get("transcriber") or {}).get("opts") or {}
                    words, t_meta = run_with_stdout_redirect(
                        lambda: transcribe_parallel(audio_path=audio_path, opts=t_opts, ctx=ctx)
                    )

                    post_meta = []
                    for post_spec in spec.get("post") or []:
                        p_id = post_spec.get("id")
                        p_opts = post_spec.get("opts") or {}
                        if p_id and p_id in _POSTS:
                            eprint(f"INFO:running post-processor {p_id} with opts {p_opts}")
                            p0 = time.time()
                            words, p_meta = run_with_stdout_redirect(
                                lambda: _POSTS[p_id]["fn"](words,p_opts,ctx))
                            post_meta.append({
                                "id": p_id, 
                                "opts": p_opts, 
                                "runtime": round(time.time() - p0, 3),
                                "meta": p_meta or {}
                                })
                    result = {
                        "words": words,
                        "meta": {
                            "transcriber": {
                                "id": "whisperx_parallel",
                                "opts": t_opts,
                                "meta": t_meta
                            },
                            "post": post_meta
                        }
                    }
                else:
                    result = run_with_stdout_redirect(
                        lambda: run_pipeline(audio_path=audio_path, spec=spec, ctx=ctx)
                    )
            except Exception as e:
                eprint(f"ERROR:{type(e).__name__}:{e}")
                json.dump({"error": type(e).__name__, "message": str(e)}, sys.stdout)
                sys.stdout.write("\n")
                return 1
            finally:
                timer.set()  # stop the elapsed timer thread
            _save_cache(cache_key, result)

        # Emit machine-readable JSON ONLY on stdout (no extra logs, progress, or library chatter).
        if not args.emit_meta:
            language = deep_get(result, "meta.transcriber.meta.language", default=None)
            if language is None:
                eprint("WARN: could not extract language from meta, defaulting to 'unknown'")
                language = "unknown"
            result.pop("meta", None)
            result["language"] = language
        json.dump(result, sys.stdout)

        sys.stdout.write("\n")
        return 0

    if args.cmd == "clear-cache":
        # For testing/debugging: clear the cache directory
        cache = _cache_dir()
        deleted = 0
        for f in os.listdir(cache):
            if f.endswith(".json"):
                try:
                    os.remove(os.path.join(cache, f))
                    deleted += 1
                except OSError as e:
                    eprint(f"WARN: failed to remove cache file {f}: {e}")
        json.dump({"deleted": deleted, "cache_dir": cache}, sys.stdout)
        sys.stdout.write("\n")
        return 0
    parser.error("Unhandled command")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise  # let normal exits through
    except Exception as ex:
        json.dump({"error": type(ex).__name__, "message": str(ex)}, sys.stdout)
        sys.stdout.write("\n")
        sys.exit(1)  # clean exit, no traceback