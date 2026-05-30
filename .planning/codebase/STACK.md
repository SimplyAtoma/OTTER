# Technology Stack

**Analysis Date:** 2026-03-10

## Languages

**Primary:**
- TypeScript 5.4.5 - Main Electron application (main process, preload bridge, renderer UI)
- Python 3.10+ - Transcription pipeline and ASR processing

**Secondary:**
- JavaScript (compiled output from TypeScript)
- HTML5 - Static UI shell
- CSS3 - Styling and layout

## Runtime

**Environment:**
- Node.js v18+ (recommended for npm builds and Electron)
- Python 3.10+ (for transcription pipeline)

**Desktop Runtime:**
- Electron 35.7.5 - Desktop application framework (pinned for security advisory)

**Package Managers:**
- npm - Node dependencies
- pip - Python dependencies
- Lockfile: `package-lock.json` present

## Frameworks

**Core:**
- Electron 35.7.5 - Desktop application framework managing main process, renderer, and native dialogs
- WaveSurfer.js 7.8.6 - Audio waveform visualization and playback library
- Regions plugin (WaveSurfer) - Visual word boundary editing in detail waveform

**Build/Dev:**
- TypeScript 5.4.5 - Compilation target ES2020
- ESLint 9.0.0 - Code linting
- @typescript-eslint/eslint-plugin 8.0.0 - TypeScript linting rules
- @typescript-eslint/parser 8.0.0 - TypeScript parsing for ESLint
- @eslint/js 9.0.0 - ESLint configuration

**Testing:**
- Not detected

## Key Dependencies

**Critical:**
- electron 35.7.5 - Provides main/renderer process boundary, IPC, native dialogs, file I/O
- wavesurfer.js 7.8.6 - Audio visualization and playback; browser-based, requires ArrayBuffer input
- faster-whisper (Python) - Local ASR engine with word-level timestamps and configurable model sizes
- whisperx (Python) - Alternative ASR engine with Silero VAD and alignment support
- pydash (Python) - Utility library used for deep object property access in transcription pipeline

**Infrastructure:**
- FFmpeg - Installed externally; used for audio inspection (ffprobe) and snippet extraction (ffmpeg)
- ffmpeg (child_process spawn) - Called via command line for audio operations

## Configuration

**Environment:**
- Configuration via command-line arguments and JSON pipeline specs
- Python virtual environment: `.venv/` with expected structure `.venv/bin/python3`
- Fallback to system `python3` on PATH if `.venv` not present
- No environment variables required; all config passed explicitly or via JSON files

**Build:**
- `tsconfig.base.json` - Base TypeScript compiler options (target ES2020, strict mode enabled, sourceMap enabled)
- `tsconfig.main.json` - Configuration for main/preload compilation to CommonJS (Node context)
- `tsconfig.renderer.json` - Configuration for renderer compilation to ES modules (browser context)
- `eslint.config.cjs` - ESLint flat config (v9.0.0 format); ignores node_modules, dist/, .venv/, otter_py/, test_data/, assets/

**Scripts:**
- `npm run build` - Compiles TypeScript from `src/` to `dist/` using both main and renderer configs
- `npm start` - Runs build then launches Electron
- `npm run lint` - Runs ESLint on `src/**/*.ts`

## Platform Requirements

**Development:**
- Node.js v18+ (npm v9+)
- Python 3.10+ with pip
- TypeScript 5.4.5+
- FFmpeg (on system PATH)
- Virtual environment setup: `python3 -m venv .venv` then activate before running

**Production:**
- Electron 35.7.5 (currently outputs to `dist/` and runs via `npm start`)
- Python 3.10+ runtime with installed ML packages
- FFmpeg binary on system PATH
- PCM WAV audio format only (prototype limitation)

**Security Note:**
- Electron 35.7.5 pinned to address moderate security advisory in earlier versions
- Context isolation enabled (`contextIsolation: true`)
- Node integration disabled (`nodeIntegration: false`)
- Preload script serves as single point of controlled access from renderer to main process

---

*Stack analysis: 2026-03-10*
