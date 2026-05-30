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

import importlib
import os
import re
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


class _RegexSentenceSplitter:
    """Fallback sentence splitter for offline environments missing NLTK punkt_tab."""

    _sentence_break = re.compile(r".+?(?:[.!?]+(?:\s+|$)|$)", re.DOTALL)

    def span_tokenize(self, text: str):
        for match in self._sentence_break.finditer(text):
            start, end = match.span()
            chunk = match.group(0)
            leading_ws = len(chunk) - len(chunk.lstrip())
            trailing_ws = len(chunk) - len(chunk.rstrip())
            start += leading_ws
            end -= trailing_ws
            if start == end:
                continue
            yield start, end
        if text and not self._sentence_break.search(text):
            yield 0, len(text)


def _install_whisperx_punkt_fallback() -> None:
    """Prevent WhisperX from hard-failing when punkt_tab is unavailable offline."""
    alignment = importlib.import_module("whisperx.alignment")
    if getattr(alignment, "_otter_punkt_fallback_installed", False):
        return

    original_nltk_load = alignment.nltk_load

    def safe_nltk_load(resource_name: str, *args: Any, **kwargs: Any):
        try:
            return original_nltk_load(resource_name, *args, **kwargs)
        except LookupError:
            if "tokenizers/punkt_tab/" not in resource_name:
                raise
            dbg(
                "NLTK punkt_tab resource is unavailable; using OTTER's built-in sentence splitter fallback.",
                DebugLevel.WARNING,
            )
            return _RegexSentenceSplitter()

    alignment.nltk_load = safe_nltk_load
    alignment._otter_punkt_fallback_installed = True


def _optional_env_path(*names: str) -> Optional[str]:
    """First non-empty env var among `names`, expanded (~user); else None."""
    for name in names:
        raw = os.environ.get(name)
        if raw is None or not str(raw).strip():
            continue
        return os.path.expanduser(str(raw).strip())
    return None


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
    interval = float(os.environ.get("OTTER_WHISPERX_ASR_PROGRESS_TICK_SEC", "3"))
    lo, hi = 16, 69
    tick = 0
    while not stop.wait(timeout=interval):
        elapsed = time.time() - start
        frac = min(1.0, elapsed / max_s) if max_s > 0 else 1.0
        pct = lo + int(frac * (hi - lo))
        pct = min(pct, hi)
        if pct >= hi - 1:
            pct = hi - 1 + (tick % 2)
        tick += 1
        emit(pct)


def _model_load_progress_bridge(emit: Any, stop: threading.Event) -> None:
    """
    While WhisperX ASR weights load (first run may download for a long time),
    creep progress from ~2% toward ~9% so the UI does not sit at 0%.
    Once saturated at 9%, alternate 8/9 each tick — repeating PROGRESS:9 does not
    move a <progress> element, so the bar looked frozen during long load_model().
    """
    lo, hi = 2, 9
    interval = float(os.environ.get("OTTER_WHISPERX_MODEL_LOAD_TICK_SEC", "3"))
    max_s = float(os.environ.get("OTTER_WHISPERX_MODEL_LOAD_BRIDGE_SEC", "3600"))
    start = time.time()
    tick = 0
    while not stop.wait(timeout=interval):
        elapsed = time.time() - start
        frac = min(1.0, elapsed / max_s) if max_s > 0 else 1.0
        pct = lo + int(frac * (hi - lo))
        pct = min(pct, hi)
        if pct >= hi:
            pct = hi - 1 + (tick % 2)
        tick += 1
        emit(pct)


def _align_load_progress_bridge(emit: Any, stop: threading.Event) -> None:
    """While the alignment model loads, creep ~71% toward ~74%."""
    lo, hi = 71, 74
    interval = float(os.environ.get("OTTER_WHISPERX_ALIGN_LOAD_TICK_SEC", "3"))
    max_s = float(os.environ.get("OTTER_WHISPERX_ALIGN_LOAD_BRIDGE_SEC", "600"))
    start = time.time()
    tick = 0
    while not stop.wait(timeout=interval):
        elapsed = time.time() - start
        frac = min(1.0, elapsed / max_s) if max_s > 0 else 1.0
        pct = lo + int(frac * (hi - lo))
        pct = min(pct, hi)
        if pct >= hi:
            pct = hi - 1 + (tick % 2)
        tick += 1
        emit(pct)


def _align_run_progress_bridge(emit: Any, stop: threading.Event) -> None:
    """While whisperx.align() runs (can be slow), creep ~76% toward ~94%."""
    lo, hi = 76, 94
    interval = float(os.environ.get("OTTER_WHISPERX_ALIGN_RUN_TICK_SEC", "3"))
    max_s = float(os.environ.get("OTTER_WHISPERX_ALIGN_RUN_BRIDGE_SEC", "600"))
    start = time.time()
    tick = 0
    while not stop.wait(timeout=interval):
        elapsed = time.time() - start
        frac = min(1.0, elapsed / max_s) if max_s > 0 else 1.0
        pct = lo + int(frac * (hi - lo))
        pct = min(pct, hi)
        if pct >= hi:
            pct = hi - 1 + (tick % 2)
        tick += 1
        emit(pct)


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
    That cache is in-memory for this Python process only. On-disk weights are shared
    via WhisperX/HF when OTTER_WHISPERX_DOWNLOAD_ROOT / HF_HOME / OTTER_ALIGN_MODEL_DIR match the CLI.
    """

    dbg("Entered transcribe_whisperx_vad")

    import whisperx  # local import: optional dependency
    _install_whisperx_punkt_fallback()

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

    # Same env vars WhisperX / faster-whisper respect — keeps disk cache aligned with CLI.
    download_root = _optional_env_path(
        "OTTER_WHISPERX_DOWNLOAD_ROOT",
        "WHISPERX_DOWNLOAD_ROOT",
    )

    # High-signal diagnostics: helps confirm we're using the expected cache dirs.
    dbg(
        "WhisperX cache env: "
        f"HF_HOME={os.environ.get('HF_HOME')!r} | "
        f"HUGGINGFACE_HUB_CACHE={os.environ.get('HUGGINGFACE_HUB_CACHE')!r} | "
        f"TRANSFORMERS_CACHE={os.environ.get('TRANSFORMERS_CACHE')!r} | "
        f"OTTER_WHISPERX_DOWNLOAD_ROOT={os.environ.get('OTTER_WHISPERX_DOWNLOAD_ROOT')!r} | "
        f"WHISPERX_DOWNLOAD_ROOT={os.environ.get('WHISPERX_DOWNLOAD_ROOT')!r}",
        DebugLevel.WARNING,
    )
    dbg(
        f"WhisperX ASR opts: model={model_name!r} device={device!r} compute_type={compute_type!r} "
        f"download_root={download_root!r}",
        DebugLevel.WARNING,
    )
    asr_key = (
        "whisperx_asr",
        model_name,
        device,
        compute_type,
        "silero",
        download_root,
    )

    def load_asr():
        kw: Dict[str, Any] = {
            "device": device,
            "compute_type": compute_type,
            "vad_method": "silero",
        }
        if download_root:
            kw["download_root"] = download_root
        return whisperx.load_model(model_name, **kw)

    dbg(
        "Loading WhisperX ASR model (first run may download weights; this can take several minutes).",
        DebugLevel.WARNING,
    )
    dbg(
        f"Stage: loading ASR model '{model_name}' on {device} ({compute_type}).",
        DebugLevel.WARNING,
    )
    dbg(
        "Load runs on the worker main thread (Whisper/ctranslate2 can misbehave when loaded from a thread pool on Windows).",
        DebugLevel.WARNING,
    )
    model_load_stop = threading.Event()
    model_load_thread = threading.Thread(
        target=_model_load_progress_bridge,
        args=(emit, model_load_stop),
        daemon=True,
    )
    model_load_thread.start()
    try:
        # Do not wrap load_model in run_in_thread_with_timeout: PyTorch/ctranslate2 model init
        # in a ThreadPool worker has been observed to hang indefinitely on Windows.
        asr_model = get_or_create(asr_key, load_asr)
    finally:
        model_load_stop.set()

    dbg(
        "WhisperX ASR model ready (in-memory LRU may reuse it in this process).",
        DebugLevel.WARNING,
    )
    emit(10)

    call_ctx_checkpoint(ctx)
    dbg("Stage: decoding audio into WhisperX input format.", DebugLevel.WARNING)
    audio = whisperx.load_audio(audio_path)
    emit(15)

    dbg(
        f"Stage: running ASR with batch_size={batch_size} and language={language or 'auto-detect'}.",
        DebugLevel.WARNING,
    )
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

    dbg(
        f"Stage: ASR complete with {len(asr_segments)} segment(s); alignment language={lang_for_align!r}.",
        DebugLevel.WARNING,
    )
    emit(70)

    if not lang_for_align:
        raise RuntimeError(
            "WhisperX did not return a language; cannot select alignment model. "
            "Provide opts.language (e.g., 'en') or use audio with detectable speech."
        )

    align_model_dir = _optional_env_path("OTTER_ALIGN_MODEL_DIR", "HF_HOME")
    align_key = (
        "whisperx_align",
        lang_for_align,
        device,
        align_model_override,
        align_model_dir,
    )

    def load_align():
        kw: Dict[str, Any] = {
            "language_code": lang_for_align,
            "device": device,
            "model_name": align_model_override,
        }
        if align_model_dir:
            kw["model_dir"] = align_model_dir
        return whisperx.load_align_model(**kw)

    dbg("Stage: loading alignment model for word-level timestamps.", DebugLevel.WARNING)
    align_load_stop = threading.Event()
    align_load_thread = threading.Thread(
        target=_align_load_progress_bridge,
        args=(emit, align_load_stop),
        daemon=True,
    )
    align_load_thread.start()
    try:
        align_model, align_metadata = get_or_create(align_key, load_align)
    finally:
        align_load_stop.set()

    emit(75)

    call_ctx_checkpoint(ctx)
    dbg("Stage: running forced alignment for word timings.", DebugLevel.WARNING)
    align_run_stop = threading.Event()
    align_run_thread = threading.Thread(
        target=_align_run_progress_bridge,
        args=(emit, align_run_stop),
        daemon=True,
    )
    align_run_thread.start()
    try:
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
    finally:
        align_run_stop.set()

    emit(95)
    dbg("Stage: converting aligned segments into OTTER word objects.", DebugLevel.WARNING)

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
    dbg(
        f"Stage: transcription finished with {len(words_out)} word(s).",
        DebugLevel.WARNING,
    )

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
