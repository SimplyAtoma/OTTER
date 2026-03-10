# Coding Conventions

**Analysis Date:** 2026-03-10

## Naming Patterns

**Files:**
- Snake_case for TypeScript source files (e.g., `main.ts`, `renderer.ts`, `preload.ts`)
- Descriptive names aligned with Electron architecture (main process, renderer, preload)

**Functions:**
- camelCase for all functions: `getCssVar()`, `fmtSec()`, `setStatus()`, `mustGetEl()`
- Functions named with action verbs: `setPlayheadIndex()`, `renderTranscript()`, `loadDetailForRange()`
- Named function declarations for top-level utility functions
- Arrow functions used in callbacks and event handlers

**Variables:**
- camelCase for all variables: `audioPath`, `words`, `selectionStart`, `playheadIndex`
- UPPER_SNAKE_CASE for constants: `SEEK_EPS`, `DETAIL_PAD_BEFORE`, `DETAIL_PAD_AFTER`, `WORD_REGION_COLOR`
- Descriptive names for state variables with clear purpose
- Element references suffixed with `El` (e.g., `transcriptEl`, `statusEl`, `logEl`, `btnPlay`, `btnChoose`)
- Button elements prefixed with `btn` (e.g., `btnPlay`, `btnTranscribe`, `btnRegion`)

**Types:**
- PascalCase for type definitions: `TranscriptWord`, `TranscriptResult`, `OtterApi`, `TranscribeSpec`
- Types defined at module scope for reuse across files

## Code Style

**Formatting:**
- ESLint configured in `/home/austinm/development/OTTER/eslint.config.cjs`
- TypeScript ES2020 target with DOM and DOM-worker libraries
- 2-space indentation (inferred from codebase style)
- No dedicated Prettier config; ESLint drives formatting

**Linting:**
- ESLint v9.0.0 with `@eslint/js` and `@typescript-eslint` plugins
- Config file: `eslint.config.cjs` (flat config format)
- Rules include:
  - `@typescript-eslint/no-explicit-any`: set to `off` (allows `any` type usage)
  - Extends recommended ESLint and TypeScript-ESLint rules
  - Ignores: `dist/`, `node_modules/`, `.venv/`, Python site-packages, `otter_py/`, test data, assets

**Run linting:**
```bash
npm run lint              # Lint all src/**/*.ts files
```

## Import Organization

**Order:**
1. Third-party imports (Electron, standard Node.js modules, external libraries)
2. Type imports and interfaces
3. Local utility functions and constants

**Examples from codebase:**
```typescript
// main.ts
import { app, BrowserWindow, dialog, ipcMain, IpcMainInvokeEvent, OpenDialogOptions } from "electron";
import path from "path";
import fs from "fs";
import { spawn } from "child_process";

// Then type definitions
type TranscribeSpec = ...

// Then module-level logic
let win: BrowserWindow | null = null;
```

**Path Aliases:**
- Not used; imports use relative paths and explicit module imports

## Error Handling

**Patterns:**
- Promise-based error handling with `reject()` and `try/catch` blocks
- Descriptive error messages including context: `new Error("ffprobe failed (${code})\n${err}")`
- Type guards for caught errors: `e instanceof Error ? e.message : String(e)`
- Validation errors thrown for invalid input (e.g., path traversal checks)
- Safe error propagation with stack context preservation

**Example from `main.ts`:**
```typescript
child.on("close", (code) => {
  if (code !== 0) return reject(new Error(`ffprobe failed (${code})\n${err}`));
  try {
    const json = JSON.parse(out);
    // ...
  } catch (e) {
    reject(e);
  }
});
```

**Example from `renderer.ts`:**
```typescript
try {
  await loadDetailForRange(rangeStart, rangeEnd);
} catch (err: unknown) {
  console.error("Failed to load detail snippet:", err);
}
```

## Logging

**Framework:** Browser `console` object for renderer; no structured logging framework

**Patterns:**
- `console.error()` for error logging (e.g., UI-level caught exceptions)
- Custom `appendLog()` function in `renderer.ts` for user-visible transcription logs
- Event-driven logging via IPC: transcription process sends `transcribe-log` events with diagnostic output
- Progress updates sent via separate `transcribe-progress` events (numeric percentage)

**Example:**
```typescript
// renderer.ts
function appendLog(msg: string) {
  logEl.textContent += msg;
  logEl.scrollTop = logEl.scrollHeight;
}

// Listen for logs from main process
otter.onTranscribeLog((msg: string) => appendLog(msg));
```

## Comments

**When to Comment:**
- Block comments explain architectural patterns and non-obvious decisions
- Inline comments clarify workarounds and pragmatic PoC choices
- Comments explain timing sensitivities and why specific approaches are used

**JSDoc/TSDoc:**
- Extensive JSDoc comments on all exported functions and IPC handlers
- Parameter descriptions with `@param` tags including type and purpose
- Return type descriptions with `@returns` tags
- Architectural notes in module headers explaining role and responsibilities

**Example from `main.ts`:**
```typescript
/**
 * IPC: Show a native file picker and return the selected audio file path.
 *
 * This prototype intentionally restricts selection to .wav to keep the demo
 * pipeline simple and avoid format compatibility issues in the waveform UI.
 *
 * @returns {Promise<string|null>} Absolute path to the chosen file, or null if canceled.
 */
ipcMain.handle("choose-audio-file", async () => {
  // ...
});
```

## Function Design

**Size:**
- Functions kept small and focused (most 10-50 lines)
- Complex operations split across helper functions
- Utility functions kept pure and side-effect-free where possible

**Parameters:**
- Explicit types for all parameters
- Optional parameters marked with `?` or default values
- Related parameters grouped logically

**Return Values:**
- Explicit return type annotations on all functions
- Promises used for async IPC and file operations
- Union types for flexible return values (e.g., `string | null`)

**Example:**
```typescript
function computeDetailWindow(start: number, end: number) {
  const winStart = Math.max(0, start - DETAIL_PAD_BEFORE);
  const winEnd = Math.max(winStart + 0.05, end + DETAIL_PAD_AFTER);
  detailWinStartAbs = winStart;
  return { winStart, winEnd, winDur: winEnd - winStart };
}
```

## Module Design

**Exports:**
- TypeScript files compiled to CommonJS for main/preload, ES modules for renderer
- Top-level file structure reflects Electron process model: `main.ts`, `preload.ts`, `renderer.ts`
- Explicit exports via `contextBridge.exposeInMainWorld()` in preload

**Barrel Files:**
- Not used; single-responsibility files in small codebase

**Type Exports:**
- Type definitions exported at module scope for use across process boundaries
- Interface types (e.g., `OtterApi`) define IPC contract between renderer and main

## Code Organization Within Files

**renderer.ts structure:**
1. Type definitions (constants, interfaces)
2. Global state variables
3. Utility functions
4. Waveform/interaction logic
5. Detail pane logic
6. Logging UI logic
7. Developer options (spec selection UI)
8. Initialization code

**main.ts structure:**
1. Module header with architecture notes
2. Import statements
3. Type definitions
4. Global state (`win`, `activeProcess`)
5. Window management
6. IPC handlers in logical order (file ops, transcription, audio manipulation)

## TypeScript Configuration

**Target:** ES2020
**Module:** CommonJS (main/preload), default (renderer)
**Lib:** ES2020, DOM
**Strict Mode:** Enabled (`"strict": true`)
**Important Settings:**
- `forceConsistentCasingInFileNames: true`
- `esModuleInterop: true`
- `skipLibCheck: true`

---

*Convention analysis: 2026-03-10*
