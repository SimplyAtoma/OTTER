"""
cache.py

Filesystem cache for OTTER pipeline results.
Keyed by SHA-256 of audio file contents + spec JSON.
Cache location is controlled by OTTER_CACHE_DIR env var,
defaulting to the system temp directory.
"""
import hashlib
import json
import os
import tempfile
from otter_py.util import eprint
from typing import Any, Dict, Optional

def _cache_key(audio_path: str, spec: Dict[str, Any]) -> str:
    h = hashlib.sha256()
    # Hash file contents (not path — path can change, contents shouldn't)
    with open(audio_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    # Hash the spec so different models/settings don't share a cache entry
    h.update(json.dumps(spec, sort_keys=True).encode())
    return h.hexdigest()

def _cache_dir() -> str:
    base = os.environ.get("OTTER_CACHE_DIR") or os.path.join(tempfile.gettempdir(), "otter_cache")
    os.makedirs(base, exist_ok=True)
    return base

def _cache_path(key: str) -> str:
    return os.path.join(_cache_dir(), f"{key}.json")

def _load_cache(key: str) -> Optional[Dict[str, Any]]:
    try:
        with open(_cache_path(key), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def _save_cache(key: str, result: Dict[str, Any]) -> None:
    try:
        with open(_cache_path(key), "w", encoding="utf-8") as f:
            json.dump(result, f)
    except OSError as e:
        eprint(f"WARN: failed to write cache: {e}")