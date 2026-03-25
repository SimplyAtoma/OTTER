"""
parallel_transcribe.py

Splits long audio into overlapping chunks and transcribes them in parallel
using multiple processes. Chunks are stitched back together by deduplicating
words in the overlap regions.

Only used when audio exceeds a minimum duration threshold (default: 20 min).
"""

from __future__ import annotations

import concurrent.futures
import math
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import whisperx

from otter_py.util import eprint

Word = Dict[str, Any]

# Chunk and overlap durations in seconds
DEFAULT_CHUNK_S = 300       # 5 min chunks
DEFAULT_OVERLAP_S = 10      # 10s overlap to avoid cutting words at boundaries
SAMPLE_RATE = 16000


def _transcribe_chunk(
    chunk: np.ndarray,
    chunk_start: float,
    model_name: str,
    device: str,
    compute_type: str,
    language: Optional[str],
    batch_size: int,
) -> List[Dict[str, Any]]:
    """
    Worker function: runs in a separate process.
    Loads its own model instance and transcribes one chunk.
    Returns segments with times offset by chunk_start.
    """
    model = whisperx.load_model(
        model_name,
        device=device,
        compute_type=compute_type,
        vad_method="silero",
    )
    result = model.transcribe(chunk, batch_size=batch_size, language=language)
    segments = result.get("segments", []) or []

    # Offset all timestamps by chunk start
    for seg in segments:
        seg["start"] += chunk_start
        seg["end"] += chunk_start
        for w in seg.get("words", []):
            if "start" in w:
                w["start"] += chunk_start
            if "end" in w:
                w["end"] += chunk_start

    return segments


def _split_audio(
    audio: np.ndarray,
    chunk_s: float,
    overlap_s: float,
) -> List[Tuple[np.ndarray, float]]:
    """Split audio into overlapping chunks. Returns (chunk_array, start_time_s) pairs."""
    chunk_samples = int(chunk_s * SAMPLE_RATE)
    overlap_samples = int(overlap_s * SAMPLE_RATE)
    step = chunk_samples - overlap_samples

    chunks = []
    pos = 0
    while pos < len(audio):
        chunk = audio[pos: pos + chunk_samples]
        start_s = pos / SAMPLE_RATE
        chunks.append((chunk, start_s))
        pos += step

    return chunks


def _deduplicate_words(words: List[Word], overlap_s: float) -> List[Word]:
    """
    Remove duplicate words introduced by overlapping chunks.
    Words are considered duplicates if they have the same text and
    their start times are within the overlap window of each other.
    Keeps the word with the higher confidence score when duplicates exist.
    """
    if not words:
        return []

    deduped: List[Word] = [words[0]]
    for w in words[1:]:
        prev = deduped[-1]
        same_text = w.get("word", "").strip().lower() == prev.get("word", "").strip().lower()
        time_close = abs(w.get("start", 0) - prev.get("start", 0)) < overlap_s

        if same_text and time_close:
            # Keep whichever has higher confidence
            w_conf = w.get("conf", 0.0) or 0.0
            prev_conf = prev.get("conf", 0.0) or 0.0
            if w_conf > prev_conf:
                deduped[-1] = w
        else:
            deduped.append(w)

    return deduped


def _align_segments(
    segments: List[Dict],
    audio: np.ndarray,
    language: str,
    device: str,
    align_model_override: Optional[str],
) -> List[Word]:
    """Run forced alignment on merged segments to get word-level timestamps."""
    align_model, align_metadata = whisperx.load_align_model(
        language_code=language,
        device=device,
        model_name=align_model_override,
    )
    aligned = whisperx.align(
        segments, align_model, align_metadata,
        audio, device, return_char_alignments=False,
    )
    words_out: List[Word] = []
    for seg in aligned.get("segments", []) or []:
        for w in seg.get("words", []) or []:
            if "word" in w and "start" in w and "end" in w:
                words_out.append({
                    "word": w["word"],
                    "start": float(w["start"]),
                    "end": float(w["end"]),
                    **({"conf": float(w["score"])} if w.get("score") is not None else {}),
                })
    return words_out


def transcribe_parallel(
    audio_path: str,
    opts: Dict[str, Any],
    ctx: Dict[str, Any],
    chunk_s: float = DEFAULT_CHUNK_S,
    overlap_s: float = DEFAULT_OVERLAP_S,
) -> Tuple[List[Word], Dict[str, Any]]:
    """
    Entry point for parallel transcription of long audio.

    Splits audio into chunks, transcribes in parallel, merges and aligns.
    """
    progress_cb = ctx.get("progress") if callable(ctx.get("progress")) else None

    def emit(p: int) -> None:
        if progress_cb:
            progress_cb(max(0, min(100, int(p))))

    model_name = str(opts.get("model", "base"))
    device = str(opts.get("device", "cpu"))
    compute_type = str(opts.get("compute_type", "int8"))
    language: Optional[str] = opts.get("language", None)
    batch_size = int(opts.get("batch_size", 4))
    align_model_override: Optional[str] = opts.get("align_model", None)
    # Use fewer workers on CPU to avoid memory exhaustion
    max_workers = int(opts.get("max_workers", 2 if device == "cpu" else 4))

    emit(0)
    audio = whisperx.load_audio(audio_path)
    emit(5)

    chunks = _split_audio(audio, chunk_s, overlap_s)
    eprint(f"INFO:parallel: splitting into {len(chunks)} chunks")

    # Transcribe chunks in parallel
    all_segments: List[List[Dict]] = [None] * len(chunks)
    progress_per_chunk = 60 / len(chunks)

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _transcribe_chunk,
                chunk, start,
                model_name, device, compute_type,
                language, batch_size,
            ): i
            for i, (chunk, start) in enumerate(chunks)
        }
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            i = futures[future]
            try:
                all_segments[i] = future.result()
            except Exception as e:
                eprint(f"ERROR:parallel chunk {i} failed: {e}")
                all_segments[i] = []
            completed += 1
            emit(5 + int(completed * progress_per_chunk))

    emit(65)

    # Merge all segments in order
    merged_segments = []
    for segs in all_segments:
        merged_segments.extend(segs or [])
    merged_segments.sort(key=lambda s: s.get("start", 0))

    # Detect language from first successful chunk if not specified
    detected_lang = language or (
        merged_segments[0].get("language") if merged_segments else None
    )
    if not detected_lang:
        raise RuntimeError("Could not detect language from any chunk.")

    emit(70)

    # Align merged segments
    try:
        words = _align_segments(
            merged_segments, audio, detected_lang,
            device, align_model_override,
        )
    except Exception as e:
        eprint(f"WARN:alignment failed ({e}), using segment-level words")
        words = []
        for seg in merged_segments:
            for w in seg.get("words", []):
                if "word" in w:
                    words.append({
                        "word": w["word"],
                        "start": float(w.get("start", seg["start"])),
                        "end": float(w.get("end", seg["end"])),
                    })

    emit(90)

    # Deduplicate words from overlapping regions
    words.sort(key=lambda w: w.get("start", 0))
    words = _deduplicate_words(words, overlap_s)

    emit(100)

    meta = {
        "engine": "whisperx_parallel",
        "model": model_name,
        "device": device,
        "compute_type": compute_type,
        "language": detected_lang,
        "chunks": len(chunks),
        "chunk_s": chunk_s,
        "overlap_s": overlap_s,
        "max_workers": max_workers,
        "words": len(words),
    }

    return words, meta