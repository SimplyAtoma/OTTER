"""
OTTER PoC - Transcriber component: faster-whisper

Wraps faster-whisper's WhisperModel.transcribe() into the OTTER pipeline interface.

Key behaviors:
- Returns a word list: [{"word": str, "start": float, "end": float}, ...]
- Emits progress updates (0..100) if ctx contains a callable: ctx["progress"](pct:int)
- Supports VAD filtering and configurable model/device/compute_type
- Caches WhisperModel instances in a module-level LRU (see otter_py.model_cache)
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional

from otter_py.model_cache import get_or_create
from otter_py.otter_debug import dbg, DebugLevel
from otter_py.pipeline_registry import register_transcriber
from otter_py.util import call_ctx_checkpoint, validate_audio_input_path

Word = Dict[str, Any]


@register_transcriber(
    id="faster_whisper",
    label="faster-whisper (local)",
    description="Local transcription via faster-whisper with word timestamps and optional VAD.",
    options_schema={
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "description": "Model size/name (e.g. tiny, base, small, medium, large-v3).",
                "default": "base",
            },
            "device": {
                "type": "string",
                "description": "Device for inference (cpu, cuda).",
                "default": "cpu",
            },
            "compute_type": {
                "type": "string",
                "description": "Compute type (e.g. int8, int8_float16, float16).",
                "default": "int8",
            },
            "vad_filter": {
                "type": "boolean",
                "description": "Enable built-in VAD filter to reduce non-speech.",
                "default": True,
            },
            "beam_size": {
                "type": "integer",
                "description": "Beam size for decoding (quality vs speed).",
                "default": 5,
                "minimum": 1,
                "maximum": 10,
            },
        },
        "additionalProperties": False,
    },
)
def transcribe_faster_whisper(
    audio_path: str,
    opts: Dict[str, Any],
    ctx: Dict[str, Any],
) -> Tuple[List[Word], Dict[str, Any]]:
    """
    Pipeline transcriber entry point.

    Args:
      audio_path: Path to audio on disk.
      opts: Transcriber options (validated by UI/schema ideally).
      ctx: Context dict. ctx["progress"] receives percent updates (wraps checkpoint).
           ctx["checkpoint"] is optional; also invoked explicitly around long-running work.

    Returns:
      (words, meta)
        words: list of Word dicts with word/start/end
        meta: language, duration, and any useful info for debugging/analysis
    """
    # Local import so the module can still be imported even if deps aren't installed yet.
    from faster_whisper import WhisperModel

    model_name = str(opts.get("model", "base"))
    device = str(opts.get("device", "cpu"))
    compute_type = str(opts.get("compute_type", "int8"))
    vad_filter = bool(opts.get("vad_filter", True))
    try:
        beam_size = int(opts.get("beam_size", 5))
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"transcriber opts['beam_size'] must be an integer, got {opts.get('beam_size')!r}"
        ) from e
    if not (1 <= beam_size <= 10):
        raise ValueError(
            f"transcriber opts['beam_size'] must be between 1 and 10, got {beam_size}"
        )

    progress_cb = ctx.get("progress")
    if not callable(progress_cb):
        progress_cb = None

    last_pct = -1

    def emit_pct(pct: int) -> None:
        nonlocal last_pct
        if progress_cb is None:
            return
        pct = max(0, min(100, int(pct)))
        if pct == last_pct:
            return
        try:
            progress_cb(pct)
            last_pct = pct
        except Exception as ex:
            dbg(f"progress callback failed: {ex}", DebugLevel.WARN)

    cache_key = ("faster_whisper", model_name, device, compute_type)

    def load_model():
        return WhisperModel(model_name, device=device, compute_type=compute_type)

    model = get_or_create(cache_key, load_model)

    validate_audio_input_path(audio_path)

    call_ctx_checkpoint(ctx)

    # Run transcription with word timestamps enabled.
    segments, info = model.transcribe(
        audio_path,
        word_timestamps=True,
        vad_filter=vad_filter,
        beam_size=beam_size,
    )

    total: Optional[float] = float(info.duration) if getattr(info, "duration", None) else None
    words_out: List[Word] = []

    # Progress semantics:
    # - faster-whisper gives segment end-times; we approximate progress as seg.end / total duration.
    emit_pct(0)

    for seg in segments:
        call_ctx_checkpoint(ctx)
        if total and getattr(seg, "end", None) is not None:
            pct = int(min(99, (float(seg.end) / total) * 100))
            emit_pct(pct)

        seg_words = getattr(seg, "words", None)
        if seg_words:
            for w in seg_words:
                # w.word often includes a leading space depending on tokenizer;
                # keep it as-is for now (UI can normalize spacing) OR strip if you prefer.
                words_out.append(
                    {
                        "word": w.word,
                        "start": float(w.start),
                        "end": float(w.end),
                    }
                )

    emit_pct(100)

    meta: Dict[str, Any] = {
        "engine": "faster_whisper",
        "model": model_name,
        "device": device,
        "compute_type": compute_type,
        "vad_filter": vad_filter,
        "beam_size": beam_size,
        "language": getattr(info, "language", None),
        "duration": float(info.duration) if getattr(info, "duration", None) else None,
    }

    return words_out, meta