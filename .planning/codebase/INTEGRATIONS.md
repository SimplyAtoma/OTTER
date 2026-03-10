# External Integrations

**Analysis Date:** 2026-03-10

## APIs & External Services

**Speech Recognition (ASR):**
- **faster-whisper** - Local speech-to-text with word-level timestamps
  - Python package: `faster_whisper`
  - Implementation: `src/main.ts` spawns Python subprocess; `otter_py/pipelines/transcribers/faster_whisper.py` handles model loading and transcription
  - Model caching: Models cached in context across pipeline runs to avoid reloading
  - Configuration: Model size (tiny, base, small, medium, large-v3), device (cpu/cuda), compute_type (int8, int8_float16, float16), VAD filter, beam size

- **whisperx** - Alternative ASR with Silero VAD and forced alignment
  - Python package: `whisperx`
  - Implementation: `otter_py/pipelines/transcribers/whisperx_vad.py`
  - Used for improved word boundary alignment

**Audio Processing Tools:**
- **FFmpeg** - System binary (external dependency)
  - Invoked by: `src/main.ts` via `child_process.spawn()`
  - Commands used:
    - `ffprobe` - Audio metadata extraction (sample rate, start time, stream info)
    - `ffmpeg` - Audio snippet extraction for detail waveform view
  - Expected on system PATH; no environment variable configuration needed

## Data Storage

**Databases:**
- Not used

**File Storage:**
- Local filesystem only - No cloud storage
- Audio files: Loaded from user-selected path via native file dialog
- Audio snippets: Generated via ffmpeg to `app.getPath("userData")/snippets/` directory (development and production compatible)
- Pipeline specs: JSON files in `otter_py/sample_specs/` directory; read-only in prototype

**Caching:**
- Model cache: In-memory dictionary in Python context (`_model_cache`) keyed by (model_name, device, compute_type)
- No persistent cache between app restarts

## Authentication & Identity

**Auth Provider:**
- Custom (none required) - All processing is local and offline
- No authentication required for any operations
- Security boundary enforced via Electron's context isolation and preload bridge

## Monitoring & Observability

**Error Tracking:**
- None detected

**Logs:**
- stderr → event stream: Python transcription process writes progress (`PROGRESS:NN` lines) and diagnostic output to stderr
- stderr captured in `src/main.ts` and emitted as IPC events: `transcribe-progress` and `transcribe-log`
- Log display: Renderer captures via `window.otter.onTranscribeLog()` and `onTranscribeProgress()` callbacks, displays in `#log` element
- Development console: Browser DevTools accessible via Electron (developer tools button in UI)

## CI/CD & Deployment

**Hosting:**
- Desktop application (Electron) - Runs locally with no network requirement
- No cloud deployment; prototype state

**CI Pipeline:**
- None detected

## Environment Configuration

**Required env vars:**
- None required; all configuration is explicit
- Python virtual environment activation recommended before running (`.venv` is checked automatically, falls back to system `python3`)

**Secrets location:**
- No secrets required in this prototype
- All processing is local and offline

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## IPC (Inter-Process Communication)

**Main ↔ Renderer Bridge (via Preload):**

Location: `src/preload.ts` exposes `window.otter` API

| Handler | Direction | Purpose |
|---------|-----------|---------|
| `choose-audio-file` | Main | Native file dialog for WAV audio selection |
| `transcribe-audio` | Main | Spawn Python transcription pipeline; stream logs/progress |
| `probe-audio` | Main | Query audio metadata via ffprobe |
| `make-snippet` | Main | Extract audio snippet via ffmpeg for detail view |
| `cancel-transcription` | Main | Send SIGTERM to active transcription process |
| `pause-transcription` | Main | Send SIGSTOP to active transcription process |
| `resume-transcription` | Main | Send SIGCONT to paused transcription process |
| `list-spec-files` | Main | List available pipeline specs from `otter_py/sample_specs/` |
| `read-spec-file` | Main | Read a single pipeline spec JSON file (with path traversal protection) |
| `transcribe-log` | Renderer | Event: diagnostic log line from transcription process |
| `transcribe-progress` | Renderer | Event: progress percentage (0-100) from transcription process |

## Python Pipeline System

**Architecture:**
- Single transcriber + ordered post-processors (configurable via JSON spec)
- Registry-based discovery: transcribers and post-processors register at import time

**Available Transcribers:**
- `faster_whisper` - Faster Whisper with VAD, configurable model/device/compute
- `whisperx_vad` - WhisperX with Silero VAD for better alignment

**Available Post-Processors:**
- `adjust_short_words` - Expand very short words left without overlapping previous word
- `clean_word_timings` - Normalize word boundaries to remove tiny gaps/overlaps

**Spec Format (JSON):**
```json
{
  "transcriber": {
    "id": "faster_whisper",
    "opts": {
      "model": "small",
      "device": "cpu",
      "compute_type": "int8",
      "vad_filter": true,
      "beam_size": 5
    }
  },
  "postprocessors": [
    {
      "id": "adjust_short_words",
      "opts": { "max_len": 0.30, "min_extend": 0.10 }
    },
    {
      "id": "clean_word_timings",
      "opts": { "tiny_gap_ms": 300.0 }
    }
  ]
}
```

**Invocation:**
- `python3 -m otter_py.transcribe list` - List all components with option schemas
- `python3 -m otter_py.transcribe run --audio <path> --spec-file <spec.json>` - Run pipeline with file-based spec
- `python3 -m otter_py.transcribe run --audio <path> --spec-json '{"transcriber": {...}, ...}'` - Run with inline JSON spec

**I/O Contract:**
- stdin: None
- stdout: Machine-readable JSON only (result words array or {words, meta})
- stderr: Progress lines (`PROGRESS:NN`), diagnostic logs, errors (`ERROR:ExceptionType:message`)

---

*Integration audit: 2026-03-10*
