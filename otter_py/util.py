"""Utility functions for OTTER."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from contextlib import redirect_stdout
import os
import sys
import threading
import time
from typing import Any, Callable, Dict, Optional, TypeVar

T = TypeVar("T")


def eprint(*args, **kwargs) -> None:
    """Print to stderr (keeps stdout reserved for machine-readable JSON)."""
    kwargs.setdefault("flush", True)
    print(*args, file=sys.stderr, **kwargs)


def call_ctx_checkpoint(ctx: Optional[Dict[str, Any]]) -> None:
    """
    Invoke ctx['checkpoint'] when provided by transcribe.py (ControlManager).

    Call between long-running steps so pause/cancel can run even when no
    PROGRESS line is emitted.
    """
    if not ctx:
        return
    fn = ctx.get("checkpoint")
    if callable(fn):
        fn()


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


def validate_audio_input_path(
    audio_path: str,
    *,
    max_bytes: Optional[int] = None,
) -> None:
    """
    Ensure the file exists and is not larger than max_bytes (default from
    OTTER_MAX_AUDIO_BYTES, or 500 MiB).
    """
    limit = max_bytes
    if limit is None:
        limit = int(os.environ.get("OTTER_MAX_AUDIO_BYTES", str(500 * 1024 * 1024)))
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    sz = os.path.getsize(audio_path)
    if sz > limit:
        raise ValueError(
            f"Audio file size ({sz} bytes) exceeds maximum ({limit} bytes)"
        )


def run_in_thread_with_timeout(
    fn: Callable[[], T],
    *,
    timeout_sec: float,
    timeout_message: str,
) -> T:
    """Run fn() in a single-worker pool and enforce a wall-clock timeout."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        try:
            return fut.result(timeout=timeout_sec)
        except FuturesTimeout:
            raise RuntimeError(timeout_message) from None


def _start_elapsed_timer() -> threading.Event:
    stop_event = threading.Event()
    start = time.time()

    def _tick():
        while not stop_event.wait(timeout=1.0):
            elapsed = time.time() - start
            m = int(elapsed // 60)
            s = int(elapsed % 60)
            eprint(f"ELAPSED:{m:02d}:{s:02d}")

    threading.Thread(target=_tick, daemon=True).start()
    return stop_event
