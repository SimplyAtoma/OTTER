# Testing Patterns

**Analysis Date:** 2026-03-10

## Current Testing Status

**No test framework configured.** The codebase does not include Jest, Vitest, or any automated test setup. This is consistent with a read-only prototype focused on proof-of-concept and feasibility demonstration.

## Test Framework

**Runner:**
- Not implemented; no test infrastructure

**Assertion Library:**
- Not applicable

**Run Commands:**
- No npm test script defined in `package.json`

## Test File Organization

**Location:**
- No test files present in codebase (no `.test.ts`, `.spec.ts` files found)
- Test files would typically be co-located with source files

**Naming:**
- Proposed pattern: `[filename].test.ts` (e.g., `renderer.test.ts`, `main.test.ts`)

**Structure:**
- Not yet established

## Testing Recommendations for Future Implementation

### Unit Tests

**Scope and approach:**
- Utility functions: `getCssVar()`, `fmtSec()`, `shortenFilenameMiddle()`, `normalizeRange()`, `computeDetailWindow()`
- IPC handler behavior: test spawn/file operations in isolation
- State management functions: `setPlayheadIndex()`, `setSelectionRange()`, `updateDetailBounds()`

**Priority areas:**
1. Path safety validation in `readSpecFile()` (path traversal check)
2. Numeric clamping in `makeSnippet()` (safeStart, safeDur)
3. Progress parsing from stderr in transcription (regex matching `^PROGRESS:(\d{1,3})`)
4. JSON parsing error recovery in IPC handlers

### Integration Tests

**Scope and approach:**
- IPC request/response cycle (main ↔ renderer via preload)
- Child process spawning (ffprobe, ffmpeg, Python transcription)
- File I/O operations (reading spec files, generating snippets)
- Event streaming (transcribe-log, transcribe-progress)

**Priority areas:**
1. Transcription process lifecycle: spawn → stream logs → parse JSON → resolve
2. Snippet generation: valid start/duration → ffmpeg spawn → WAV output
3. Audio probing: ffprobe execution → JSON parse → metadata extraction
4. Error handling: process exit codes, signal handling (SIGKILL, SIGSTOP, SIGCONT)

### Manual Testing Recommendations

**Electron-specific areas not easily automated:**
- Window creation and BrowserWindow lifecycle
- Native file picker dialog interaction
- IPC preload bridge isolation
- Audio element behavior in WaveSurfer.js (browser-dependent)
- Context isolation and nodeIntegration=false security model

## Key Areas Without Automated Test Coverage

**High-risk areas to test manually or add automated tests:**

### Path Traversal Prevention
- File: `src/main.ts`, line 306-310
- Function: `readSpecFile()`
- Current protection: `path.basename()` check
- Test: Verify `../../etc/passwd` is rejected, symlink resolution is safe

**Example test pattern:**
```typescript
describe("readSpecFile security", () => {
  it("should reject path traversal attempts", async () => {
    const event = { /* mock */ };
    // This should throw "Invalid spec file name"
    await readSpecFile(event, "../../etc/passwd");
  });

  it("should allow safe filenames", async () => {
    // This should succeed
    await readSpecFile(event, "default_spec.json");
  });
});
```

### Process Signal Handling
- File: `src/main.ts`, line 241-248
- Signals: SIGKILL (cancel), SIGSTOP (pause), SIGCONT (resume)
- Risk: Incorrect signal handling could leave zombie processes or hang UI
- Test: Spawn process, send signals, verify state cleanup

**Example test pattern:**
```typescript
describe("transcription process lifecycle", () => {
  it("should handle SIGKILL gracefully", async () => {
    const result = await transcribeAudio(event, audioPath);
    // Should reject with "transcription cancelled"
  });

  it("should restore after pause/resume", async () => {
    // Pause transcription
    await pauseTranscription();
    // Resume transcription
    await resumeTranscription();
    // Should complete successfully
  });
});
```

### Progress Parsing
- File: `src/main.ts`, line 227-233
- Pattern: `^PROGRESS:(\d{1,3})\s*$`
- Risk: Malformed progress data could fail silently
- Test: Verify parsing of valid/invalid progress lines

**Example test pattern:**
```typescript
describe("progress parsing", () => {
  it("should parse valid PROGRESS lines", () => {
    const lines = ["PROGRESS:25", "PROGRESS:50", "PROGRESS:100"];
    // Each should trigger transcribe-progress event
  });

  it("should skip non-matching lines", () => {
    const lines = ["PROGRESS:abc", "Progress:50", "PROGRESS 50"];
    // None should trigger progress event, only log lines
  });
});
```

### Audio Snippet Generation
- File: `src/main.ts`, line 347-349
- Functions: Clamping safeStart and safeDur
- Risk: Invalid ffmpeg args if bounds checking fails
- Test: Verify clamping behavior and ffmpeg execution

**Example test pattern:**
```typescript
describe("snippet clamping", () => {
  it("should clamp negative start to 0", async () => {
    const path = await makeSnippet(audioPath, -5, 1);
    // ffmpeg should receive -ss 0
  });

  it("should enforce minimum duration", async () => {
    const path = await makeSnippet(audioPath, 0, 0.01);
    // Should clamp to 0.05 seconds minimum
  });
});
```

### Transcript Rendering and Synchronization
- File: `src/renderer.ts`, line 296-348
- Risk: Selection boundaries outside word array bounds, playhead sync lag
- Test: Verify rendering after transcript load, selection bounds checking

**Example test pattern:**
```typescript
describe("transcript rendering", () => {
  it("should handle empty word array", () => {
    renderTranscript([]);
    expect(transcriptEl.children.length).toBe(0);
  });

  it("should cap selection to valid indices", () => {
    renderTranscript(words);
    setSelectionRange(0, words.length + 10); // out of bounds
    // Should clamp to valid range
  });
});
```

## Test Fixture and Factory Patterns

**Recommended fixtures for future tests:**

```typescript
// Mock audio metadata
const mockProbeResult = {
  start_time: 0,
  sample_rate: 48000
};

// Mock transcript
const mockWords = [
  { word: "hello", start: 0.0, end: 0.5 },
  { word: "world", start: 0.5, end: 1.0 }
];

// Mock IPC event
const mockIpcEvent = {
  sender: {
    send: jest.fn()
  }
};

// Mock child process
const mockProcess = {
  stdout: new EventEmitter(),
  stderr: new EventEmitter(),
  on: jest.fn(),
  kill: jest.fn()
};
```

**Location:** Proposed at `src/__fixtures__/` or test file headers

## Coverage Considerations

**Requirements:** None enforced currently

**Current coverage estimate:** ~0% (no tests)

**Target coverage for production:**
- Core utility functions: 100%
- IPC handlers: 80%+ (accounting for Electron runtime)
- Event handlers: 70% (hard to test in-browser without E2E)

## Testing Strategy for Different Code Areas

### Utility Functions (Testable, Pure)
- Location: `src/renderer.ts` lines 109-156 (getCssVar, fmtSec, shortenFilenameMiddle, mustGetEl, normalizeRange, computeDetailWindow)
- Approach: Unit tests with no dependencies
- Tool: Vitest (recommended for modern TS) or Jest

### IPC Handlers (Needs Mocking)
- Location: `src/main.ts` lines 96-381 (all ipcMain.handle calls)
- Approach: Mock spawn/fs/dialog, verify handler logic
- Mocks needed: `child_process.spawn`, `fs`, `electron.dialog`, `electron.app`

### Renderer State Management (Needs DOM)
- Location: `src/renderer.ts` lines 296-348, 174-220, 469-487
- Approach: JSDOM or browser test runner, mock WaveSurfer, test state transitions
- Tool: Vitest with @vitest/ui

### Process Integration (E2E)
- Location: Entire `src/main.ts`
- Approach: Electron's test runner or Playwright integration tests
- Complexity: High; reserved for critical workflows

## Error Scenarios to Test

**File I/O errors:**
- File not found: `readSpecFile()` when spec doesn't exist
- Permission denied: file can't be read
- Disk full: snippet generation fails

**Process errors:**
- ffprobe/ffmpeg not in PATH
- Python transcription script exits with non-zero code
- Subprocess sends malformed progress output
- Process killed/paused during transcription

**Validation errors:**
- Path traversal attempts in `readSpecFile()`
- Negative or NaN duration values in `makeSnippet()`
- Invalid audio file paths

**Type errors:**
- Missing transcript.words in result
- start_time/sample_rate missing from ffprobe JSON
- Malformed spec JSON passed to transcription

---

*Testing analysis: 2026-03-10*
