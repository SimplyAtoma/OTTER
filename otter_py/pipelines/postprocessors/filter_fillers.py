"""
Post-processor: Filter Filler Words

Removes common filler words (e.g. "uh", "um") from the word list.
Optionally only removes them if their confidence is below a threshold.
"""

from __future__ import annotations
from typing import Any, Dict, List, Tuple
from otter_py.pipeline_registry import register_postprocessor, Word
from otter_py.otter_debug import dbg, DebugLevel

DEFAULT_FILLERS = ["uh", "um", "hmm", "mm", "mhm", "hm", "ugh"]

@register_postprocessor(
    id="filter_fillers",
    label="Filter filler words",
    description="Removes filler words (uh, um, hmm, etc.) from the transcript, optionally gated by confidence.",
    options_schema={
        "type": "object",
        "properties": {
            "fillers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of filler words to remove (lowercase, no punctuation).",
                "default": DEFAULT_FILLERS,
            },
            "min_conf": {
                "type": ["number", "null"],
                "description": "If set, only remove fillers with confidence below this threshold.",
                "default": None,
            },
        },
        "additionalProperties": False,
    },
)
def filter_fillers(
    words: List[Word],
    opts: Dict[str, Any],
    ctx: Dict[str, Any],
) -> Tuple[List[Word], Dict[str, Any]]:
    if not words:
        return [], {"removed": 0}

    raw_fillers = opts.get("fillers", DEFAULT_FILLERS) or DEFAULT_FILLERS
    filler_set = {f.lower().strip() for f in raw_fillers}
    min_conf = opts.get("min_conf", None)
    if min_conf is not None:
        min_conf = float(min_conf)

    out: List[Word] = []
    removed = 0

    for w in words:
        text = w.get("word", "").lower().strip().strip(".,!?")
        if text in filler_set:
            # If min_conf is set, only remove if confidence is below threshold
            if min_conf is not None:
                conf = w.get("conf", None)
                if conf is not None and float(conf) >= min_conf:
                    out.append(dict(w))
                    continue
            dbg(f"filter_fillers: removing '{w['word']}'", DebugLevel.VERBOSE)
            removed += 1
        else:
            out.append(dict(w))

    return out, {"removed": removed, "filler_set": sorted(filler_set)}