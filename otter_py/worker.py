#!/usr/bin/env python3
"""
otter_py.worker
---------------

Persistent transcription worker process for Electron.

Why:
- Electron used to spawn a fresh Python process per transcription. That defeats
  in-memory model caching (see otter_py.model_cache) and makes repeated runs
  feel like they are "downloading" / reloading models.
- This worker stays alive so model objects can be reused across jobs.

Protocol (stdin, JSON lines):
- Run a transcription job:
    {"type":"run","audio_path":"...","spec_file":"..."}  OR
    {"type":"run","audio_path":"...","spec_json":"{...}"}
    Optional: {"no_cache": true, "emit_meta": false}
- Control current job:
    {"type":"pause"} | {"type":"resume"} | {"type":"cancel"} | {"type":"ping"}

Outputs:
- Progress/logs to STDERR (including "PROGRESS:NN" and "CONTROL:*")
- Final result JSON to STDOUT as a single line per job
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
from typing import Any, Dict, Optional

from otter_py.cacheUtil import _cache_key, _load_cache, _save_cache
from otter_py.exceptions import TranscriptionCancelled
from otter_py.util import eprint, run_with_stdout_redirect


class JobController:
    def __init__(self) -> None:
        self._paused = threading.Event()
        self._cancelled = threading.Event()

    def pause(self) -> None:
        self._paused.set()
        eprint("CONTROL:PAUSED")

    def resume(self) -> None:
        self._paused.clear()
        eprint("CONTROL:RESUMED")

    def cancel(self) -> None:
        self._cancelled.set()
        self._paused.clear()
        eprint("CONTROL:CANCELLING")

    def checkpoint(self) -> None:
        if self._cancelled.is_set():
            raise TranscriptionCancelled("Transcription cancelled")
        while self._paused.is_set():
            if self._cancelled.is_set():
                raise TranscriptionCancelled("Transcription cancelled while paused")
            time.sleep(0.1)
        if self._cancelled.is_set():
            raise TranscriptionCancelled("Transcription cancelled")

    def progress_wrapper(self, fn):
        def wrapped(pct: int) -> None:
            fn(pct)
        return wrapped


def _read_spec(spec_json: Optional[str], spec_file: Optional[str]) -> Dict[str, Any]:
    if spec_json and spec_file:
        raise ValueError("Provide only one of spec_json or spec_file")
    if spec_file:
        with open(spec_file, "r", encoding="utf-8") as f:
            return json.load(f)
    if spec_json:
        return json.loads(spec_json)
    raise ValueError("Missing pipeline spec")


def main() -> int:
    eprint("INFO:otter worker starting")
    msg_q: queue.Queue[Dict[str, Any]] = queue.Queue()

    def reader() -> None:
        for raw in sys.stdin:
            line = raw.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                eprint(f"WARN:invalid json: {line}")
                continue
            if isinstance(msg, dict):
                msg_q.put(msg)
            else:
                eprint(f"WARN:expected object msg, got {type(msg).__name__}")

    threading.Thread(target=reader, daemon=True).start()

    running = False
    controller: Optional[JobController] = None

    def _emit_meta_payload(result: Dict[str, Any], emit_meta: bool) -> Dict[str, Any]:
        if emit_meta:
            return result
        from pydash import get as deep_get

        language = deep_get(result, "meta.transcriber.meta.language", default=None)
        if language is None:
            eprint("WARN: could not extract language from meta, defaulting to 'unknown'")
            language = "unknown"
        result.pop("meta", None)
        result["language"] = language
        return result

    def _run_job(
        audio_path: str,
        spec_json: Optional[str],
        spec_file: Optional[str],
        no_cache: bool,
        emit_meta: bool,
        job_controller: JobController,
    ) -> None:
        eprint("PROGRESS:0")
        eprint("INFO:Initializing pipeline components...")
        from otter_py.pipeline_registry import load_components, run_pipeline

        load_components()
        spec = _read_spec(spec_json, spec_file)

        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        def progress(pct: int) -> None:
            eprint(f"PROGRESS:{pct}")

        ctx: Dict[str, Any] = {
            "progress": job_controller.progress_wrapper(progress),
            "control": job_controller,
            "checkpoint": job_controller.checkpoint,
            "wait_if_paused": job_controller.checkpoint,
            "throw_if_cancelled": job_controller.checkpoint,
        }

        cache_key = _cache_key(audio_path, spec)
        cached = None if no_cache else _load_cache(cache_key)

        if cached is not None:
            job_controller.checkpoint()
            eprint("INFO:cache hit, skipping pipeline execution")
            result = cached
        else:
            eprint("INFO:cache miss, running pipeline")
            job_controller.checkpoint()
            result = run_with_stdout_redirect(lambda: run_pipeline(audio_path=audio_path, spec=spec, ctx=ctx))
            job_controller.checkpoint()
            _save_cache(cache_key, result)

        result = _emit_meta_payload(result, emit_meta)
        json.dump(result, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()

    while True:
        msg = msg_q.get()
        mtype = msg.get("type")

        # control messages
        if mtype in ("pause", "resume", "cancel", "ping"):
            if mtype == "ping":
                eprint("CONTROL:PONG")
                continue
            if not running or controller is None:
                # ignore control when idle
                continue
            if mtype == "pause":
                controller.pause()
            elif mtype == "resume":
                controller.resume()
            elif mtype == "cancel":
                controller.cancel()
            continue

        if mtype != "run":
            eprint(f"WARN:unknown message type: {mtype!r}")
            continue

        if running:
            # One job at a time: respond with error JSON line.
            json.dump({"error": "Busy", "message": "Worker is already running a job"}, sys.stdout)
            sys.stdout.write("\n")
            sys.stdout.flush()
            continue

        audio_path = msg.get("audio_path")
        spec_file = msg.get("spec_file")
        spec_json = msg.get("spec_json")
        no_cache = bool(msg.get("no_cache", False))
        emit_meta = bool(msg.get("emit_meta", False))

        if not isinstance(audio_path, str) or not audio_path:
            json.dump({"error": "SpecError", "message": "Missing audio_path"}, sys.stdout)
            sys.stdout.write("\n")
            sys.stdout.flush()
            continue

        running = True
        controller = JobController()

        try:
            _run_job(
                str(audio_path),
                spec_json if isinstance(spec_json, str) else None,
                spec_file if isinstance(spec_file, str) else None,
                no_cache,
                emit_meta,
                controller,
            )
        except TranscriptionCancelled as e:
            json.dump({"error": "Cancelled", "message": str(e)}, sys.stdout)
            sys.stdout.write("\n")
            sys.stdout.flush()
        except Exception as e:
            json.dump({"error": type(e).__name__, "message": str(e)}, sys.stdout)
            sys.stdout.write("\n")
            sys.stdout.flush()
        finally:
            running = False
            controller = None


if __name__ == "__main__":
    raise SystemExit(main())

