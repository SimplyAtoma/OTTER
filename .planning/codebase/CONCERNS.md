# Codebase Concerns

**Analysis Date:** 2026-03-10

## Security Considerations

**Electron Sandbox Disabled:**
- Issue: `src/main.ts` line 61 has `sandbox: false` in BrowserWindow config
- Files: `src/main.ts`
- Impact: This disables the Electron sandbox, which is a fundamental security layer. If renderer is compromised, attacker gains full system access.
- Current mitigation: Uses `contextIsolation: true` and `nodeIntegration: false`, and restricts direct Node access via preload bridge
- Recommendations:
  - Change `sandbox: false` to `sandbox: true` if possible
  - If sandbox must be disabled, audit all IPC handlers for input validation (especially `read-spec-file` with path construction, `transcribe-audio` with file paths)
  - Ensure all user inputs are validated before passing to child processes (ffmpeg, ffprobe, Python)

**Path Traversal Risk (Low):**
- Issue: `src/main.ts` line 307-315 implements basic path traversal protection with `path.basename()` for spec files
- Files: `src/main.ts`
- Impact: Existing protection prevents `../../etc/passwd` attacks on spec file reads. However, no validation exists for other file paths.
- Safe modification: Keep current pattern but extend to all file operations

**IPC Command Injection Risk (Audio Paths):**
- Issue: `src/main.ts` passes user-selected audio paths directly to `ffprobe` (line 135) and `ffmpeg` (line 369) child processes
- Files: `src/main.ts` (lines 135, 369)
- Impact: Audio file paths come from `dialog.showOpenDialog()`, which should be trusted OS-level selection, but filenames with special characters could interact unexpectedly with ffmpeg/ffprobe CLI parsing
- Safe modification: Quote all file paths when building spawn arguments, or use array form of spawn which avoids shell interpretation

## Performance Bottlenecks

**Linear Search in Playback Update (O(n)):**
- Problem: `src/renderer.ts` line 410 uses a linear loop to find the current word based on playback time
- Files: `src/renderer.ts`
- Cause: Every `timeupdate` event (fires frequently during playback) triggers a full scan of the words array
- Improvement path:
  - Use binary search: `words` array is time-sorted, so find current word in O(log n)
  - Cache last found index and check neighbors first for small jumps
  - For PoC with small transcripts (<5000 words) this is acceptable, but blocks scaling

**Snippet Generation on Every Word Selection:**
- Problem: `src/renderer.ts` line 249 calls `otter.makeSnippet()` every time a word is selected
- Files: `src/renderer.ts`
- Cause: No caching of generated snippets; each word click triggers ffmpeg execution
- Improvement path:
  - Cache snippets by window range to avoid regeneration for adjacent words
  - Implement cleanup to avoid unlimited disk usage in `app.getPath("userData")/snippets`
  - For typical usage this is manageable, but repetitive clicking is slow

**Large Audio Files Not Streamed:**
- Problem: `src/renderer.ts` line 652 loads entire audio file via `readFileAsArrayBuffer()`
- Files: `src/renderer.ts`, `src/preload.ts`
- Cause: WaveSurfer is loaded with full blob, limiting to available system RAM
- Improvement path:
  - For files >100MB, implement streaming/chunked loading
  - Current PoC assumes typical interview recordings (<30 min, <500MB)

## Fragile Areas

**WaveSurfer Region Playback State Machine:**
- Why fragile: `src/renderer.ts` lines 489-525 document why the region playback logic is complex and fragile
- Files: `src/renderer.ts` (lines 540-585)
- Specific issues:
  - Wall-clock `setTimeout` for region stop is not audio-time accurate
  - WaveSurfer v7 media integration unreliable for bounded region playback
  - Multiple interdependent handlers (play, pause, finish, timeupdate) can interfere
  - Seeking after region play doesn't always restart audio cleanly
- Safe modification: Do NOT simplify without extensive re-testing across:
  - Repeated plays of same region
  - Switching between region and full playback
  - Playing near end of snippet
  - Fast word selections in sequence

**Detail Waveform Loading Race Condition (Potential):**
- Problem: `src/renderer.ts` lines 265-269 attach event handler before calling load
- Files: `src/renderer.ts`
- Risk: In theory, if `load()` completes synchronously in rare cases, the "ready" handler won't fire
- Mitigation: Comment explains intent; handler is attached BEFORE load for safety
- Safe fix: Verify handler attachment occurs synchronously before async load

**Async Error Handling in Click Handlers:**
- Problem: `src/renderer.ts` line 307 has click handler with `async` and `try/catch`, but errors logged to `appendLog()` UI
- Files: `src/renderer.ts`
- Risk: UI can become unresponsive if error occurs during long-running snippet generation; no timeout enforcement
- Safe modification: Add abort controller or timeout wrapper around `loadDetailForRange()` calls

**Global State in Renderer:**
- Problem: `src/renderer.ts` uses global variables: `audioPath`, `words`, `selectionStart/End`, `playheadIndex`, `detailWinStartAbs`, `detailRegion`, `regionStopTimer`
- Files: `src/renderer.ts` (lines 99-530)
- Impact: Makes refactoring difficult; state transitions not centralized; selecting word while transcription in progress could cause inconsistency
- Safe modification: Consider state machine pattern or React-like component model if PoC becomes production

## Test Coverage Gaps

**No Unit Tests:**
- What's not tested: Any function in `src/renderer.ts` or `src/main.ts`
- Files: All source files
- Risk: Refactoring transcription pipeline or fixing WaveSurfer integration could break existing behavior silently
- Priority: Medium - PoC quality, but critical paths (audio playback, word selection, transcription result parsing) should have integration tests

**No Python Unit Tests:**
- What's not tested: Post-processor logic in `otter_py/pipelines/postprocessors/`
- Files: `otter_py/pipelines/postprocessors/adjust_short_words.py`, `otter_py/pipelines/postprocessors/clean_word_timings.py`
- Risk: Changes to word timing adjustments could corrupt transcripts silently. Edge cases (< 3 words, overlapping boundaries) are not explicitly tested
- Priority: High - these directly affect user-facing word timing precision

**No Integration Tests for Transcription Pipeline:**
- What's not tested: Full pipeline from audio file → transcriber → post-processors → JSON output
- Files: `otter_py/transcribe.py`, `otter_py/pipeline_registry.py`
- Risk: Spec format changes, option validation, or error propagation issues undetected until runtime
- Priority: Medium - PoC assumes correct specs, but production should validate schemas

**No E2E Tests:**
- What's not tested: Full application flow (load audio → transcribe → playback → word selection → snippet generation)
- Risk: Interaction between Electron main/renderer, ffmpeg integration, Python subprocess lifecycle
- Priority: High for production; acceptable for PoC

## Known Bugs / Workarounds

**Whisper Alignment Timestamps Approximate:**
- Symptoms: Word boundaries from ASR are ±100ms off real audio boundaries
- Files: `otter_py/pipelines/transcribers/faster_whisper.py`, `otter_py/pipelines/transcribers/whisperx_vad.py`, `src/renderer.ts` line 389-405
- Trigger: Any transcription; especially visible in fast-spoken segments
- Workaround: Detail waveform with editable regions (line 482) allows manual boundary adjustment; 10ms bias (line 389) helps UI sync
- Root cause: ASR models output tokens with uncertain boundaries; forced alignment improves precision but remains approximate

**PyTorch/WhisperX Deprecation Warnings:**
- Symptoms: Stderr contains warnings about `torchaudio._backend.list_audio_backends`
- Files: `otter_py/pipelines/transcribers/whisperx_vad.py` lines 97-102
- Trigger: Using WhisperX transcriber
- Workaround: Filter suppressed at source; not actionable without upstream fix
- Root cause: TorchAudio deprecation; WhisperX depends on old API

**Pause/Resume Signal Handling:**
- Symptoms: `pause-transcription` and `resume-transcription` IPC handlers signal SIGSTOP/SIGCONT to Python subprocess
- Files: `src/main.ts` lines 276-290
- Current behavior: Signals work on Unix-like systems; Windows doesn't support SIGSTOP/SIGCONT
- Risk: Feature doesn't work on Windows; no error feedback to user
- Priority: Low for PoC (Unix-focused development), high for cross-platform release

## Scaling Limits

**Current capacity:**
- Typical 30-minute interview: ~3500 words
- Word timing array: ~20KB JSON
- Detail snippets: ~5MB each
- UI rendering: Linear in word count

**Limit where it breaks:**
- Audio files >4GB: Can't load into memory as ArrayBuffer
- Transcripts >50k words: Linear search becomes noticeably slow; DOM rendering sluggish
- Concurrent detail snippets: Unlimited snippets accumulate in `userData/snippets` without cleanup

**Scaling path:**
- Stream audio playback instead of full load
- Implement virtual scrolling for transcript
- Add snippet cache eviction policy
- Use IndexedDB or SQLite for large transcript storage

## Unhandled Error Cases

**Missing Audio File After Selection:**
- Problem: If user selects audio file, then it's deleted/moved before transcription starts, error occurs in Python subprocess
- Files: `otter_py/transcribe.py` line 100 checks existence, but only at transcription start
- Impact: User sees generic error; could add retry or file validation before returning from choose dialog

**Invalid Spec JSON:**
- Problem: User pastes invalid JSON into custom spec textarea; sent directly to Python subprocess
- Files: `src/renderer.ts` line 726 trusts `specJsonEl.value`
- Impact: Crashes transcription with parsing error; no client-side validation
- Fix: Add JSON.parse check in renderer before sending spec

**Subprocess Timeout:**
- Problem: Long-running transcription (large audio + large model) has no timeout; if process hangs, UI is stuck
- Files: `src/main.ts` line 211-263
- Risk: User can't cancel stuck process; only kill app
- Fix: Add timeout wrapper (e.g., 30 min) and auto-reject if exceeded

**Snippet ffmpeg Failure (Rare):**
- Problem: If ffmpeg is not installed or audio file is corrupted, `make-snippet` IPC fails
- Files: `src/main.ts` line 369-381
- Impact: User clicks word, detail pane doesn't load; error logged but doesn't propagate clearly to UI
- Fix: Better error UI instead of just error log

## Dependencies at Risk

**Electron 35.7.5:**
- Risk: Electron major versions have breaking changes; 35.x should be stable, but sandbox behavior may shift
- Migration path: Monitor Electron releases; test sandbox re-enabling in next major version

**WaveSurfer 7.8.6:**
- Risk: v7 is current; v8 would have major API changes. Regions plugin behavior documented as fragile
- Migration path: Monitor WaveSurfer releases; v8 may simplify region playback API

**Faster-Whisper & WhisperX:**
- Risk: Both depend on PyTorch ecosystem; version mismatches common
- Current issue: WhisperX filters deprecation warnings that indicate downstream API drift
- Migration path: Pin versions in requirements; consider moving to Whisper.cpp for cross-platform compatibility

**pydash (deep_get):**
- Risk: Single-function dependency; could be eliminated with simple Python code
- Impact: Low; reduces surface area by removing import
- Migration: Replace `deep_get(result, "meta.transcriber.meta.language")` with `result.get("meta", {}).get("transcriber", {}).get("meta", {}).get("language")`

## Missing Critical Features

**No Destructive Editing:**
- Problem: UI explicitly read-only; can't save modified transcripts
- Blocks: Capstone project requirements
- Note: By design for PoC; fundamental architecture needed for full version

**No Project Persistence:**
- Problem: Closing app discards transcript and all state
- Blocks: Practical usage beyond demo
- Note: Intentional for PoC; requires database/project file format

**No Batch Processing:**
- Problem: Can only transcribe one file at a time
- Blocks: Multi-file workflows
- Note: Would require worker pool and progress aggregation

**No Multi-Language Metadata Preservation:**
- Problem: Detected language extracted but not stored in transcript
- Files: `otter_py/transcribe.py` lines 117-119
- Impact: Language info lost after export
- Fix: Include language in output word list or metadata dict

---

*Concerns audit: 2026-03-10*
