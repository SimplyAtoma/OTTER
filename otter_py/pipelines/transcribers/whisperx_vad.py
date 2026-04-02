"""
OTTER PoC - Transcriber component: WhisperX + Silero VAD

WhisperX pipeline (typical):
  1) ASR pass -> segments (coarse timestamps)
  2) Forced alignment -> word-level timestamps (more precise)

This component returns OTTER's canonical word list:
  [{"word": str, "start": float, "end": float, ...}, ...]

PoC choices:
- We force VAD to Silero via vad_method="silero".
  This avoids the pyannote-based VAD code path that can trigger PyTorch
  2.6+ "weights_only" checkpoint loading issues (OmegaConf allowlisting).
- We keep the option surface minimal and stable: model/device/compute_type,
  language (optional), batch_size, and optional align_model override.

Notes:
- WhisperX is heavier than faster-whisper (extra alignment model + deps).
- Progress reporting is approximate but useful for UI.
"""

from __future__ import annotations

import os
import threading
import time
import warnings
from typing import Any, Dict, List, Optional, Tuple

from otter_py.model_cache import get_or_create
from otter_py.otter_debug import DebugLevel, dbg
from otter_py.pipeline_registry import register_transcriber
from otter_py.util import (
    call_ctx_checkpoint,
    run_in_thread_with_timeout,
    validate_audio_input_path,
)

Word = Dict[str, Any]


def _safe_int(opts: Dict[str, Any], key: str, default: int, lo: int, hi: int) -> int:
    raw = opts.get(key, default)
    try:
        v = int(raw)
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"transcriber opts[{key!r}] must be an integer, got {raw!r}"
        ) from e
    if not (lo <= v <= hi):
        raise ValueError(
            f"transcriber opts[{key!r}] must be between {lo} and {hi}, got {v}"
        )
    return v


def _asr_progress_bridge(emit: Any, stop: threading.Event) -> None:
    """While ASR runs, nudge progress from ~16% toward ~69% so the bar does not look stuck."""
    start = time.time()
    max_s = float(os.environ.get("OTTER_WHISPERX_ASR_PROGRESS_BRIDGE_SEC", "1800"))
    interval = float(os.environ.get("OTTER_WHISPERX_ASR_PROGRESS_TICK_SEC", "8"))
    lo, hi = 16, 69
    while not stop.wait(timeout=interval):
        elapsed = time.time() - start
        frac = min(1.0, elapsed / max_s) if max_s > 0 else 1.0
        pct = lo + int(frac * (hi - lo))
        emit(min(pct, hi))


@register_transcriber(
    id="whisperx_vad",
    label="WhisperX + Silero VAD (local)",
    description="WhisperX transcription + forced alignment for word-level timestamps, using Silero VAD segmentation.",
    options_schema={
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "description": "Whisper/WhisperX ASR model name (e.g., base, small, medium, large-v2, large-v3).",
                "default": "base",
            },
            "device": {
                "type": "string",
                "description": "Device for inference (cpu, cuda, mps depending on install).",
                "default": "cpu",
            },
            "compute_type": {
                "type": "string",
                "description": "Compute type (e.g., int8, float16).",
                "default": "int8",
            },
            "language": {
                "type": ["string", "null"],
                "description": "Force language code (e.g., 'en') or null to auto-detect.",
                "default": None,
            },
            "batch_size": {
                "type": "integer",
                "description": "Batch size for WhisperX ASR. Higher can be faster but uses more memory.",
                "default": 8,
                "minimum": 1,
                "maximum": 64,
            },
            "align_model": {
                "type": ["string", "null"],
                "description": "Optional alignment model override (model_name passed to whisperx.load_align_model).",
                "default": None,
            },
        },
        "additionalProperties": False,
    },
)
def transcribe_whisperx_vad(
    audio_path: str,
    opts: Dict[str, Any],
    ctx: Dict[str, Any],
) -> Tuple[List[Word], Dict[str, Any]]:
    """
    Transcriber entry point for the OTTER pipeline system.

    ctx:
      - ctx["progress"] (callable): called with integer pct 0..100 (wraps checkpoint)
      - ctx["checkpoint"] (callable): optional; pause/cancel between heavy steps

    Models are cached at module scope (LRU, see otter_py.model_cache), not on ctx.
    """

    dbg("Entered transcribe_whisperx_vad")

    import whisperx  # local import: optional dependency

    warnings.filterwarnings(
        "ignore",
        message=".*torchaudio\\._backend\\.list_audio_backends has been deprecated.*",
        category=UserWarning,
    )

    progress_cb = ctx.get("progress") if callable(ctx.get("progress")) else None

    def emit(p: int) -> None:
        pct = max(0, min(100, int(p)))
        if not progress_cb:
            return
        try:
            progress_cb(pct)
        except Exception as ex:
            dbg(f"progress callback failed: {ex}", DebugLevel.WARNING)

    model_name = str(opts.get("model", "base"))
    device = str(opts.get("device", "cpu"))
    compute_type = str(opts.get("compute_type", "int8"))
    language: Optional[str] = opts.get("language", None)
    batch_size = _safe_int(opts, "batch_size", 8, 1, 64)
    align_model_override: Optional[str] = opts.get("align_model", None)

    if language is None:
        dbg(
            "language not set in opts; alignment language comes from ASR detection "
            "(may fail on silence or non-speech).",
            DebugLevel.WARNING,
        )

    asr_timeout = float(os.environ.get("OTTER_WHISPERX_ASR_TIMEOUT_SEC", "3600"))
    align_timeout = float(os.environ.get("OTTER_WHISPERX_ALIGN_TIMEOUT_SEC", "600"))

    validate_audio_input_path(audio_path)

    emit(0)

    asr_key = ("whisperx_asr", model_name, device, compute_type, "silero")

    def load_asr():
        return whisperx.load_model(
            model_name,
            device=device,
            compute_type=compute_type,
            vad_method="silero",
        )

    asr_model = get_or_create(asr_key, load_asr)

    emit(10)

    call_ctx_checkpoint(ctx)
    audio = whisperx.load_audio(audio_path)
    emit(15)

    bridge_stop = threading.Event()
    bridge_thread = threading.Thread(
        target=_asr_progress_bridge,
        args=(emit, bridge_stop),
        daemon=True,
    )
    bridge_thread.start()
    try:
        result = run_in_thread_with_timeout(
            lambda: asr_model.transcribe(
                audio,
                batch_size=batch_size,
                language=language,
            ),
            timeout_sec=asr_timeout,
            timeout_message=f"WhisperX ASR timed out after {asr_timeout:g}s",
        )
    finally:
        bridge_stop.set()

    call_ctx_checkpoint(ctx)
    asr_segments = result.get("segments", []) or []
    detected_lang = result.get("language", None)
    lang_for_align = language or detected_lang

    emit(70)

    if not lang_for_align:
        raise RuntimeError(
            "WhisperX did not return a language; cannot select alignment model. "
            "Provide opts.language (e.g., 'en') or use audio with detectable speech."
        )

    align_key = ("whisperx_align", lang_for_align, device, align_model_override)

    def load_align():
        return whisperx.load_align_model(
            language_code=lang_for_align,
            device=device,
            model_name=align_model_override,
        )

    align_model, align_metadata = get_or_create(align_key, load_align)

    emit(75)

    call_ctx_checkpoint(ctx)
    aligned = run_in_thread_with_timeout(
        lambda: whisperx.align(
            asr_segments,
            align_model,
            align_metadata,
            audio,
            device,
            return_char_alignments=False,
        ),
        timeout_sec=align_timeout,
        timeout_message=f"WhisperX alignment timed out after {align_timeout:g}s",
    )

    emit(95)

    words_out: List[Word] = []
    for seg in aligned.get("segments", []) or []:
        for w in seg.get("words", []) or []:
            if "word" in w and "start" in w and "end" in w:
                words_out.append(
                    {
                        "word": w["word"],
                        "start": float(w["start"]),
                        "end": float(w["end"]),
                        **(
                            {"conf": float(w["score"])}
                            if "score" in w and w["score"] is not None
                            else {}
                        ),
                    }
                )

    emit(100)

    meta: Dict[str, Any] = {
        "engine": "whisperx",
        "vad_method": "silero",
        "model": model_name,
        "device": device,
        "compute_type": compute_type,
        "language": lang_for_align,
        "batch_size": batch_size,
        "align_model_override": align_model_override,
        "segments": len(asr_segments),
        "words": len(words_out),
    }

    return words_out, meta
