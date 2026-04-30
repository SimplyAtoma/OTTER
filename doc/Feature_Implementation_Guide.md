# OTTER Feature Implementation Guide

This document explains how the major OTTER features work in the current proof of concept, with an emphasis on the real code paths in `src/` and `otter_py/`.

It is meant to answer questions like:

- Which file owns a feature?
- What data structure represents the feature internally?
- What sequence of functions runs when a user clicks a button?
- Where are the main extension points for the capstone team?

## 1. System Layout

OTTER is split into three runtime layers:

1. `src/renderer.ts`
   The browser-side UI. It owns transcript rendering, selection, drag/drop reordering, playback state, and editor state.
2. `src/preload.ts`
   The secure bridge that exposes a narrow `window.otter` API to the renderer.
3. `src/main.ts`
   The Electron main process. It owns privileged work such as native dialogs, filesystem access, `ffmpeg`/`ffprobe`, and spawning Python.
4. `otter_py/*.py`
   The local transcription backend. It runs Whisper-family transcription, post-processing, caching, and optional parallel execution for long files.

The core pattern is:

`renderer -> preload -> main -> Python/ffmpeg -> main -> renderer`

That separation is important because the renderer never talks to Node APIs directly.

## 2. Audio Import And Transcription

### What the feature does

This feature lets a user choose a WAV file, transcribe it locally, and stage the transcript in the "pending import" pane before merging it into the main transcript.

### Main renderer flow

The import flow is driven primarily by these functions in `src/renderer.ts`:

- `enqueueTranscription()`
- `runTranscriptionQueue()`
- `transcribePendingImportAudio()`
- `buildPieceTableFromTranscript()`

How it works:

1. The user picks audio through `window.otter.chooseAudioFile()`.
2. The chosen path is stored in `pendingImportAudioPath`.
3. Clicking `Transcribe` snapshots the currently selected pipeline spec and calls `enqueueTranscription("pending-import", ...)`.
4. `runTranscriptionQueue()` guarantees that only one transcription job runs at a time, even if the user queues multiple jobs.
5. `transcribePendingImportAudio()` calls `window.otter.transcribeAudio(...)`.
6. When the result comes back, the transcript words are stored in `pendingImportEditor.words`.
7. `buildPieceTableFromTranscript()` converts the flat transcript into an editable piece-table representation.
8. `renderTranscript(pendingImportEditor)` paints the staged transcript in the UI.

### IPC bridge and main-process flow

The preload bridge for this feature is exposed in `src/preload.ts` under:

- `chooseAudioFile`
- `transcribeAudio`
- `onTranscribeLog`
- `onTranscribeProgress`

The Electron main-process handler is `ipcMain.handle("transcribe-audio", ...)` in `src/main.ts`.

That handler:

1. Rejects overlapping transcriptions with `activeProcess`.
2. Resolves the pipeline spec from either a sample spec file or raw JSON text.
3. Builds the Python environment with `buildPythonWorkerEnv()` so Hugging Face and WhisperX caches land in predictable locations.
4. Picks a Python interpreter with `getPythonPath()`.
5. Spawns `python -m otter_py.transcribe run --audio ...`.
6. Parses stderr for `PROGRESS:<n>` lines and forwards them to the renderer.
7. Parses stdout as one final JSON payload.
8. Resolves `{ cancelled: true }` if the process is cancelled.

### Python pipeline flow

The CLI entry point is `otter_py/transcribe.py`.

Important pieces:

- `read_spec()`
  Loads the pipeline JSON from either `--spec-json` or `--spec-file`.
- `ControlManager`
  Supports pause/resume/cancel on stdin in the Python code path.
- `main()`
  Implements the `list`, `run`, and `clear-cache` commands.

When `run` executes:

1. It emits `PROGRESS:0` to stderr.
2. It loads pipeline components through `load_components()` in `otter_py/pipeline_registry.py`.
3. It validates the audio path.
4. It computes a cache key from audio contents plus spec JSON.
5. It either returns the cached result or runs a pipeline.
6. It writes only machine-readable JSON to stdout.

### Transcribers

OTTER currently has two main transcribers:

- `otter_py/pipelines/transcribers/faster_whisper.py`
  Uses `faster-whisper` and reports progress based on segment end times relative to total audio duration.
- `otter_py/pipelines/transcribers/whisperx_vad.py`
  Uses WhisperX plus forced alignment and Silero VAD. It includes staged progress bridges so the UI does not look frozen during model load, ASR, or alignment.

### Parallel transcription for long audio

If audio is longer than 20 minutes and the selected transcriber is `whisperx_vad`, `transcribe.py` can switch to `otter_py/parallel_transcribe.py`.

That path:

1. Splits audio into overlapping chunks with `_split_audio()`.
2. Transcribes chunks in parallel worker processes with `_transcribe_chunk()`.
3. Merges segments in time order.
4. Runs `_align_segments()` on the merged output.
5. Removes overlap duplicates with `_deduplicate_words()`.

This is an optimization path, not a separate user-visible feature.

### Important limitation

The UI exposes pause/resume buttons, and the Python side supports cooperative control, but the current Electron `transcribe-audio` path is still a one-shot spawned process. In `src/main.ts`, `pause-transcription` and `resume-transcription` currently return `false`, while `cancel-transcription` terminates the child process.

## 3. Transcript Editing Model

### What the feature does

OTTER does not edit audio destructively in place. Instead, it edits a transcript-backed representation of word segments and later derives preview or export audio from that representation.

### Editor panes

The renderer maintains three editor states:

- `importedEditor`
  The main transcript being assembled and edited.
- `pendingImportEditor`
  A staged transcript created from imported audio before it is merged into main.
- `recordedEditor`
  A staged transcript created from microphone recordings.

Each editor uses the `EditorState` type and may contain:

- `audioPath`
- `words`
- `pieceTable`
- `undoStack`
- `redoStack`
- selection state

### Piece table data structure

The key editing feature is the piece table implemented in `src/renderer.ts`.

Relevant types:

- `PieceEntry`
- `Piece`
- `PieceTableData`
- `ViewEntry`

The model works like this:

1. `originalBuffer` stores words produced by ASR.
2. `addBuffer` stores words inserted later from another transcript.
3. `pieces` is an ordered list of spans pointing into those buffers.
4. Each piece has a `status`:
   `active`, `deleted`, `added`, or `moved`.

This is why OTTER can support reversible transcript edits without rewriting the original audio file.

### Core editing helpers

These functions are the heart of transcript editing:

- `buildPieceTableFromTranscript()`
  Creates the initial identity table from ASR output.
- `getViewEntries()`
  Flattens piece-table state into UI-visible entries, including deleted words.
- `getActiveEntries()`
  Returns only non-deleted entries for playback/export.
- `mergePieces()`
  Recombines adjacent compatible pieces to keep the table compact.
- `applyStatusToRange()`
  Splits pieces as needed and changes a word range from one status to another.
- `moveWord()`, `moveRange()`, `moveSelectedIndices()`
  Rebuild the piece order after drag/drop reordering.

### Remove, restore, and reorder

The visible transcript editing actions are mostly status changes:

- Removing words marks them `deleted`.
- Restoring words changes `deleted` back to `active`.
- Appending another transcript creates new `addBuffer` entries and marks those pieces `added`.
- Reordering rebuilds the piece order while preserving references to the original entries.

### Undo/redo

Undo/redo is snapshot-based, not operation-based.

Main functions:

- `snapshotState()`
- `pushUndo()`
- `restoreSnapshot()`
- `performUndo()`
- `performRedo()`

The important detail is that snapshots may include `side` snapshots for another editor pane. This is what makes actions like "append staged transcript into main and then clear the source pane" undoable in one step.

### Selection and interaction modes

Transcript interaction happens in two modes:

- `select`
  Click/drag to select word ranges.
- `move`
  Drag/drop to reorder selected words.

The renderer uses:

- `setSelectedIndices()`
- `setSelectionRange()`
- `renderTranscript()`
- `attachTranscriptPaneDnD()`

`renderTranscript()` is especially important because it attaches the mouse and drag handlers to every word span.

## 4. Transcript Merge Into Main

### What the feature does

Imported and recorded transcripts are intentionally staged first. They do not immediately replace the main transcript.

### Main function

The merge logic lives in `appendEditorToMain()` in `src/renderer.ts`.

It behaves in two modes:

1. If `importedEditor` is empty, the source transcript is promoted into main.
2. If `importedEditor` already exists, the source transcript's active entries are copied into `importedEditor.pieceTable.addBuffer`, then appended as `added` pieces.

This approach preserves provenance:

- original imported words stay in `originalBuffer`
- later merged words stay in `addBuffer`

That split will matter if the capstone team later adds richer edit provenance, source labeling, or smarter export rules.

## 5. Waveforms, Playback, And Synchronization

### What the feature does

The UI keeps transcript text, playback position, and waveform views synchronized.

There are two waveform concepts:

- the main waveform
- the detail waveform

### Main waveform

The main waveform normally reflects the current edited transcript, not just the original imported audio.

That logic is in:

- `refreshMainWavePreviewFromEdits()`
- `loadMainWaveFromPath()`
- `buildPreviewWordTimesFromActiveEntries()`

How it works:

1. The renderer converts active transcript entries into a lightweight EDL payload.
2. It calls `window.otter.renderEditedPreview(...)`.
3. The main process builds a temporary WAV preview from non-muted segments.
4. The renderer loads that generated WAV into WaveSurfer.
5. `previewWordTimes` stores the remapped word timings so playback highlighting still lines up with the edited preview audio.

`previewRefreshToken` makes this last-write-wins so rapid edits do not race and flash the wrong preview.

### Detail waveform

The detail waveform exists to inspect a selected word or range more closely.

Main function:

- `loadDetailForRange()`

How it works:

1. The renderer computes a padded window around the selection with `computeDetailWindow()`.
2. It asks the main process to run `make-snippet`.
3. `src/main.ts` uses `ffmpeg` to create a temporary WAV snippet.
4. The renderer loads that snippet into a second WaveSurfer instance.
5. The selected word range is shown as a region inside the snippet.

This is where OTTER demonstrates that ASR timings are approximate rather than perfectly hand-aligned.

### Playhead versus selection

The renderer keeps playback highlight separate from selection:

- selection is the user's chosen word range
- playhead is the word currently under playback time

That split is handled by helpers like `setPlayheadIndex()` and `setSelectionRange()`.

## 6. Microphone Recording

### What the feature does

The app can record microphone audio in the browser, convert it to WAV, then transcribe it through the same pipeline used for imported files.

### Renderer side

The renderer uses browser APIs such as:

- `navigator.mediaDevices`
- `MediaRecorder`

Important helpers include:

- `refreshMicDeviceList()`
- `initMicDeviceList()`
- `stopMicIfActive()`
- `setRecordingState()`

When recording stops:

1. The captured chunks are combined into a blob.
2. The blob is converted to an `ArrayBuffer`.
3. The renderer calls either `window.otter.saveMicRecording()` or `window.otter.saveMicRecordingAs()`.

### Main-process conversion

In `src/main.ts`:

- `save-mic-recording`
- `save-mic-recording-as`

Both handlers:

1. Write the raw browser-recorded data to disk.
2. Detect a temporary extension from the MIME type.
3. Run `ffmpeg` to convert it to PCM WAV.
4. Return the WAV path back to the renderer.

After that, `transcribeRecordedAudio()` treats the recording the same way as imported audio, except it writes into `recordedEditor`.

## 7. EDL Save, Load, Preview, And Export

### What the feature does

The EDL feature is OTTER's persistence and export layer. It stores transcript edit state as JSON and uses that state to regenerate preview or export audio.

### Save format

The current save format is version 4.

The renderer save handler:

- syncs `breakAfter` from visible words back into piece-table entries
- stores all three editor piece tables
- stores the audio path for each pane

This is done in the `btnSaveEdl` handler in `src/renderer.ts`, which calls `window.otter.saveEdl(...)`.

### Loading and backwards compatibility

The `btnLoadEdl` handler supports:

- version 4
- version 3
- version 2
- version 1

Older formats are upgraded in the renderer using:

- `isEdlV1()`
- `isEdlV2()`
- `convertV1ToV2()`

After loading:

1. Piece tables are restored.
2. `words` arrays are rebuilt from `getViewEntries()`.
3. Waveforms for staged imported or recorded audio are reloaded if their audio paths still exist.
4. The main edited preview waveform is regenerated if the main editor has content.

### Preview rendering

The main-process handler `render-edited-preview` in `src/main.ts`:

1. Parses EDL JSON.
2. Filters out muted segments.
3. Builds an `ffmpeg` `filter_complex` graph using `atrim` and `concat`.
4. Writes a temporary WAV file under the Electron user-data folder.

This preview is disposable and can be regenerated at any time.

### Final export

The `btnSaveEdits` handler exports only active entries from `importedEditor`.

It sends a simpler EDL payload to `window.otter.exportEdlAudio(...)`, and `src/main.ts` again builds an `ffmpeg` `atrim + concat` pipeline, but this time writes to a user-chosen output file.

The key design choice is that OTTER never edits the source WAV directly. Export always creates a new file.

## 8. Pipeline Specs And Developer Experimentation

### What the feature does

OTTER is intentionally built to let developers swap transcription pipelines without changing app code.

### Spec flow

Spec files live in `otter_py/sample_specs/`.

The main-process API exposes:

- `list-spec-files`
- `read-spec-file`

The preload bridge exposes:

- `listSpecFiles()`
- `readSpecFile()`
- `readDefaultSpec()`

The renderer uses those APIs to populate the spec selector and optional custom JSON editor.

### Spec shape

A pipeline spec contains:

- one `transcriber`
- zero or more post-processors

Example shape:

```json
{
  "transcriber": {
    "id": "whisperx_vad",
    "opts": {
      "model": "base",
      "device": "cpu"
    }
  },
  "postprocessors": [
    {
      "id": "clean_word_timings",
      "opts": {
        "tiny_gap_ms": 50
      }
    }
  ]
}
```

`otter_py/pipeline_registry.py` accepts both:

- `post`
- `postprocessors`

### Post-processors

The current built-in post-processors are:

- `clean_word_timings`
  Fixes small overlaps and closes tiny gaps.
- `adjust_short_words`
  Extends very short words leftward for easier interaction.
- `filter_fillers`
  Removes filler words such as `uh` and `um`.
- `filter_low_confidence_words`
  Drops or replaces words below a confidence threshold.

The registry system is decorator-based, so adding new components is mainly a matter of creating a module and registering it.

## 9. Caching And Performance

### Filesystem result cache

`otter_py/cacheUtil.py` implements a disk cache keyed by:

- SHA-256 of the audio file contents
- JSON of the pipeline spec

That means:

- renaming the file does not invalidate the cache
- changing model settings does invalidate the cache

The cache is written atomically with a temp file plus `os.replace()`.

### In-memory model cache

The transcriber modules also use `otter_py/model_cache.py` through `get_or_create(...)`.

That cache is separate from the filesystem result cache:

- filesystem cache avoids rerunning a finished transcription
- model cache avoids reloading model weights during the same Python process lifetime

### Why `worker.py` exists

`otter_py/worker.py` is a persistent worker that can keep models warm across multiple jobs. The current Electron path in `src/main.ts` still launches `otter_py.transcribe` per run, but `worker.py` shows the direction for a future always-on backend.

## 10. Extension Points For The Capstone Team

The safest high-value extension points are:

- Add new transcribers by registering them in `pipeline_registry.py`.
- Add new post-processors that keep the canonical OTTER word format.
- Replace snapshot-based undo with operation-based undo if edit scale grows.
- Expand the EDL schema with richer provenance or speaker data.
- Move Electron from one-shot Python runs to the persistent `worker.py` model.
- Implement real pause/resume by keeping stdin open and routing control messages instead of terminating the process.
- Add true transcript-driven cut/paste/rearrange features on top of the existing piece-table and EDL infrastructure.

## 11. Practical Summary

The most important architectural idea in OTTER is that transcript edits are treated as structured metadata over audio, not as direct waveform edits.

That leads to three core design choices throughout the project:

- transcription produces timestamped word objects
- editing changes piece-table state and EDL state
- preview/export regenerates audio from that state with `ffmpeg`

That model is what makes the current proof of concept coherent, and it is also the best place to build the full capstone project from.
