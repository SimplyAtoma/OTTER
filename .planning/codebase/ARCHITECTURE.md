# Architecture

**Analysis Date:** 2026-03-10

## Pattern Overview

**Overall:** Electron IPC-based Desktop Application with Pluggable Python Transcription Pipeline

**Key Characteristics:**
- Strict process separation: Main (Node.js) ↔ Renderer (Browser) via IPC, Preload bridge
- Two-tier backend: Renderer UI + Main process for OS/command execution
- Pluggable ASR pipeline: Registry-based transcriber and post-processor components
- Audio-first interaction: Waveform visualization (WaveSurfer) drives transcript navigation
- Proof-of-concept scope: Read-only interaction, no destructive editing, no state persistence

## Layers

**Electron Main Process:**
- Purpose: OS-level operations, process management, privileged access
- Location: `src/main.ts`
- Contains: Window creation, IPC handlers, child process spawning (ffmpeg, ffprobe, Python), file dialogs
- Depends on: Electron API, Node.js child_process, fs, path
- Used by: Preload script via IPC

**Preload / IPC Bridge:**
- Purpose: Security boundary enforcer, explicit API surface for renderer
- Location: `src/preload.ts`
- Contains: contextBridge.exposeInMainWorld call, wrapper functions around ipcRenderer.invoke/on
- Depends on: Electron IPC, fs (for ArrayBuffer conversion)
- Used by: Renderer process via window.otter

**Renderer / UI Process:**
- Purpose: User interface, audio visualization, transcript interaction, state management
- Location: `src/renderer.ts`, `index.html`
- Contains: DOM manipulation, WaveSurfer event handlers, transcript rendering, playback logic
- Depends on: window.otter API, WaveSurfer.js, DOM APIs
- Used by: End user interaction

**Python Transcription Pipeline:**
- Purpose: ASR and post-processing with pluggable components
- Location: `otter_py/` directory
- Contains: Pipeline registry, transcriber implementations, post-processor implementations
- Depends on: faster-whisper, whisperx, pydash
- Used by: Main process via spawn(), configured by specs in otter_py/sample_specs/

## Data Flow

**Audio Load Flow:**

1. User clicks "Choose Audio…" (renderer)
2. Renderer calls `window.otter.chooseAudioFile()` → IPC to main.ts
3. Main process shows native file picker, returns path to renderer
4. Renderer calls `window.otter.readFileAsArrayBuffer(path)` → preload reads file as ArrayBuffer
5. Renderer loads blob into WaveSurfer instance
6. Renderer calls `window.otter.probeAudio(path)` to get metadata (ffprobe via main)

**Transcription Flow:**

1. User clicks "Transcribe" (renderer)
2. Renderer calls `window.otter.transcribeAudio(audioPath, spec)` via IPC
3. Main spawns Python subprocess: `python -m otter_py.transcribe run --audio ... --spec-file ...`
4. Python pipeline:
   - Loads spec (JSON selecting transcriber + post-processors)
   - Calls registered transcriber (e.g., faster_whisper or whisperx_vad)
   - Pipes result through each registered post-processor in order
   - Emits progress lines to stderr: `PROGRESS:NN`
5. Main process:
   - Captures stderr, parses PROGRESS lines, forwards via `event.sender.send("transcribe-progress", pct)`
   - Captures stdout (JSON result), parses on process exit
   - Resolves IPC promise with parsed result
6. Renderer:
   - Listens to `window.otter.onTranscribeProgress()` for UI updates
   - Listens to `window.otter.onTranscribeLog()` for log output
   - Receives final result, renders transcript as clickable words

**Transcript-Waveform Synchronization:**

1. User clicks a word in transcript
2. Renderer updates selection state, seeks WaveSurfer to word.start time
3. Renderer calls `window.otter.makeSnippet(audioPath, winStart, winDur)` to create focused WAV
4. Main uses ffmpeg to extract PCM snippet: `ffmpeg -ss START -t DUR -i audio.wav snippet.wav`
5. Renderer loads snippet into detail WaveSurfer instance
6. Renderer creates/updates WaveSurfer Region highlighting word boundaries in detail view
7. WaveSurfer fires "timeupdate" during playback → renderer updates playhead word highlight

**State Management:**

- Audio path: Stored as renderer global `audioPath`
- Transcript words: Stored as renderer global `words: TranscriptWord[]`
- Selection state: `selectionStart`, `selectionEnd`, `selectionAnchor` (for shift-click range)
- Playhead index: `playheadIndex` (visual indicator of current word during playback)
- Detail window: `detailWinStartAbs` (absolute time of detail snippet start)
- Region playback: `regionStopTimer` (wall-clock timer for bounded region playback)

## Key Abstractions

**Word (Canonical Representation):**
- Purpose: Uniform interface for transcript data across all pipeline stages
- Examples: `otter_py/pipeline_registry.py` (Word TypedDict)
- Pattern: Dict with fields: word (string), start (float seconds), end (float seconds), extras allowed

**TranscriptWord (Renderer Type):**
- Purpose: Typed representation of word data for UI operations
- Examples: `src/renderer.ts` line 46-51
- Pattern: TypedDict extending Word, used for array iteration, index lookup

**IPC Channel (Async RPC):**
- Purpose: Request-response pattern for main ↔ renderer communication
- Examples: All handlers in `src/main.ts` using `ipcMain.handle(...)`
- Pattern: Async functions registered by name, called via `ipcRenderer.invoke(name, ...args)`

**IPC Event Stream (One-way Emit):**
- Purpose: Streaming updates from main to renderer without blocking on response
- Examples: `transcribe-progress`, `transcribe-log` events in main.ts
- Pattern: Main sends via `event.sender.send(channel, data)`, renderer listens via `ipcRenderer.on()`

**Pipeline Spec (Configuration):**
- Purpose: JSON configuration selecting transcriber and post-processors with options
- Examples: `otter_py/sample_specs/*.json`, `src/renderer.ts` lines 724-729
- Pattern: `{ transcriber: { id: "...", opts: {...} }, post: [{ id: "...", opts: {...} }, ...] }`

**Pluggable Component (Transcriber/Post-Processor):**
- Purpose: Self-describing component with registration metadata and implementation
- Examples: `otter_py/pipelines/transcribers/faster_whisper.py`, postprocessors
- Pattern: Function decorated with @register_transcriber or @register_postprocessor, includes options_schema

## Entry Points

**Main Application Entry:**
- Location: `src/main.ts` (main process entry)
- Triggers: Electron app ready event
- Responsibilities: Create BrowserWindow, load index.html, setup IPC handlers, manage application lifecycle

**Renderer Entry:**
- Location: `dist/renderer.js` (compiled from `src/renderer.ts`)
- Triggers: Browser loads index.html
- Responsibilities: DOM setup, WaveSurfer initialization, event listener attachment, initial UI state

**Python CLI Entry:**
- Location: `otter_py/transcribe.py` (command-line entry point)
- Triggers: Main process spawns via `python -m otter_py.transcribe run/list`
- Responsibilities: Parse CLI args, load pipeline spec, execute pipeline, emit JSON to stdout

**Pipeline Component Discovery:**
- Location: `otter_py/pipeline_registry.py` (load_components() function)
- Triggers: transcribe.py calls load_components() on startup
- Responsibilities: Import transcriber/post-processor modules, trigger decorator registration

## Error Handling

**Strategy:** Layered error handling with explicit error propagation

**Patterns:**

- **IPC Error Propagation:** Main process errors reject IPC promise, renderer catches in try-catch
  - Example: `src/main.ts` ffprobe handler line 142-143 (code !== 0 rejects)
  - Renderer displays error in status area or log

- **Python Process Errors:** stderr lines starting with "ERROR:" are parsed, stdout corruption triggers JSON parse error
  - Example: `src/main.ts` transcribe handler lines 251-260
  - Error message reconstructed from stderr for user display

- **Signal-based Interruption:** Process killed with SIGKILL/SIGSTOP converted to user-facing error
  - Example: `src/main.ts` lines 241-247 (on close, check signal field)

- **File Access Validation:** Path traversal prevented via path.basename() check
  - Example: `src/main.ts` read-spec-file handler lines 307-310
  - Safety enforced before fs operations

- **UI Error Display:** Status element shows error class, log area shows detailed messages
  - Example: `src/renderer.ts` setStatus(msg, "error") calls
  - Errors are human-readable and actionable

## Cross-Cutting Concerns

**Logging:**
- Main approach: Diagnostic output to stderr (not stdout, which is reserved for JSON)
- Renderer pattern: Two IPC event streams for logs and progress
  - `transcribe-log`: Multi-line messages displayed in #log element
  - `transcribe-progress`: Numeric percentage for progress bar
- Python convention: stderr for human-readable output, stdout for machine-readable JSON only
  - Example: `otter_py/transcribe.py` lines 43-45 (eprint function)

**Validation:**
- Spec validation: Pipeline registry validates transcriber/post-processor IDs at runtime
  - Example: `otter_py/pipeline_registry.py` lines 196-199, 223-224
- Audio file validation: ffprobe probes before transcription, ffmpeg validates format
- Spec safety: Renderer prevents path traversal via basename checks on spec filenames
  - Example: `src/main.ts` lines 307-310

**Authentication:**
- Not applicable: Local read-only prototype with no auth layer

**Performance:**
- Waveform rendering: WaveSurfer.js handles HTML5 Canvas visualization
- Transcript interaction: Linear scan for playhead update (noted in code as PoC limitation)
  - Example: `src/renderer.ts` lines 409-413 (note about binary search)
- Detail snippet: ffmpeg extracts short snippet to keep DOM manageable
  - Example: `src/main.ts` make-snippet handler (stored in app.getPath("userData"))
- Pipeline execution: Context dict passes progress callback to pipeline components
  - Example: `otter_py/transcribe.py` lines 104-107 (progress callback)

---

*Architecture analysis: 2026-03-10*
