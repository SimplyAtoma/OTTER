"""
Post-processor: Filter Low Confidence Words

Drops or replaces words whose confidence score falls below a threshold.
Words without a confidence score are kept by default (configurable).
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from otter_py.pipeline_registry import register_postprocessor, Word
from otter_py.otter_debug import dbg, DebugLevel

@register_postprocessor(
    id="filter_low_confidence",
    label="Filter low confidence words",
    description="Removes or replaces words below a confidence threshold.",
    options_schema={
        "type": "object",
        "properties": {
            "min_conf": {
                "type": "number",
                "description": "Words with confidence below this are removed/replaced.",
                "default": 0.4,
            },
            "replace_with": {
                "type": ["string", "null"],
                "description": "Replace low-confidence words with this string, or null to remove entirely.",
                "default": None,
            },
            "keep_unscored": {
                "type": "boolean",
                "description": "If true, keep words that have no confidence score.",
                "default": True,
            },
        },
        "additionalProperties": False,
    },
)
def filter_low_confidence(
    words: List[Word],
    opts: Dict[str, Any],
    ctx: Dict[str, Any],
) -> Tuple[List[Word], Dict[str, Any]]:
    if not words:
        return [], {"removed": 0, "replaced": 0}

    min_conf = float(opts.get("min_conf", 0.4))
    replace_with: Optional[str] = opts.get("replace_with", None)
    keep_unscored = bool(opts.get("keep_unscored", True))

    out: List[Word] = []
    removed = 0
    replaced = 0

    for w in words:
        conf = w.get("conf", None)

        if conf is None:
            # No confidence score
            if keep_unscored:
                out.append(dict(w))
            else:
                dbg(f"filter_low_confidence: removing unscored '{w['word']}'", DebugLevel.DETAIL)
                removed += 1
            continue

        if float(conf) < min_conf:
            dbg(f"filter_low_confidence: conf={conf:.2f} < {min_conf} for '{w['word']}'", DebugLevel.DETAIL)
            if replace_with is not None:
                # Replace word text but keep timestamps
                replacement = dict(w)
                replacement["word"] = replace_with
                out.append(replacement)
                replaced += 1
            else:
                removed += 1
        else:
            out.append(dict(w))

    return out, {
        "min_conf": min_conf,
        "removed": removed,
        "replaced": replaced,
        "keep_unscored": keep_unscored,
    }