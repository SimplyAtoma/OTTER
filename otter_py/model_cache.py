"""
Module-level LRU cache for heavy ASR / alignment models (in-memory, this process only).

This is **not** the Hugging Face / faster-whisper weight directory on disk. It only keeps
loaded Python objects (pipelines, models) alive between pipeline runs **within the same
Python process** so you do not reload weights from disk every transcription.

Weight files are still managed by WhisperX / HF (see OTTER_WHISPERX_DOWNLOAD_ROOT, HF_HOME).

Not stored on pipeline ctx so lifetime is explicit: bounded by max entries,
oldest evicted on insert. Thread-safe for parallel transcription workers.

Never use print() to stdout here — stdout is reserved for JSON when running under transcribe.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from typing import Any, Callable, Dict, Hashable, List, TypeVar

T = TypeVar("T")

_default_max = int(os.environ.get("OTTER_MAX_CACHED_MODELS", "4"))
_lock = threading.Lock()
_cache: OrderedDict[Hashable, Any] = OrderedDict()


def configure_max_entries(max_entries: int) -> None:
    """For tests only: set max cache size and clear."""
    global _default_max
    _default_max = max(1, max_entries)
    with _lock:
        _cache.clear()


def get_or_create(key: Hashable, factory: Callable[[], T]) -> T:
    """
    Return cached value for key, or call factory() to create it.
    Evicts LRU entries when over capacity. Factory runs outside the lock
    so slow loads don't block other threads; duplicate loads for the same
    key are rare and last writer wins.
    """
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]  # type: ignore[return-value]

    created = factory()

    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]  # type: ignore[return-value]
        while len(_cache) >= _default_max and _cache:
            _cache.popitem(last=False)
        _cache[key] = created
        return created


def cache_stats() -> Dict[str, Any]:
    """Return snapshot of in-memory LRU state (for debugging / UI)."""
    with _lock:
        return {
            "entries": len(_cache),
            "max_entries": _default_max,
            "keys": _serialize_keys(list(_cache.keys())),
        }


def _serialize_keys(keys: List[Hashable]) -> List[Any]:
    """Make keys JSON-friendly for logging (tuples stay as lists of scalars)."""
    out: List[Any] = []
    for k in keys:
        if isinstance(k, tuple):
            out.append([_serialize_keys_item(x) for x in k])
        else:
            out.append(_serialize_keys_item(k))
    return out


def _serialize_keys_item(x: Any) -> Any:
    if x is None:
        return None
    if isinstance(x, (str, int, float, bool)):
        return x
    return repr(x)
