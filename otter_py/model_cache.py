"""
Module-level LRU cache for heavy ASR / alignment models.

Not stored on pipeline ctx so lifetime is explicit: bounded by max entries,
oldest evicted on insert. Thread-safe for parallel transcription workers.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from typing import Any, Callable, Hashable, TypeVar

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
