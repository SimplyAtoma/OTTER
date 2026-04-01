"""Utility functions for OTTER."""
from contextlib import redirect_stdout
import sys
import time
import threading


def eprint(*args, **kwargs) -> None:
    """Print to stderr (keeps stdout reserved for machine-readable JSON)."""
    print(*args, file=sys.stderr, **kwargs)

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
