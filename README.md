# OTTER Read-Only Proof of Concept
***Open Text Transcription Editing Resource***

<img src="assets/icon.png" width="35%" alt="OTTER icon"> <img src="assets/Screenshot1.png" width="50%" align="right" alt="OTTER screenshot">
## Overview

This repository contains a Proof of Concept (PoC) for OTTER, the **O**pen **T**ext **T**ranscription **E**diting **R**esource. It is for use with CSUMB Computer Science Capstone Program.

OTTER uses an automatic speech recognition (ASR) model to allow users to edit audio files by editing text rather than solely via waveform editors.

The PoC demonstrates how text transcription, audio playback, and timeline synchronization can work together with no cloud services or closed-source dependencies. It is implemented as a local desktop app using Electron, with a JavaScript-based UI and a locally invoked transcription backend. Audio and text never leave the user's computer so it remains private.

It exists to:

+ Ground discussions in a working system
+ Demonstrate feasibility
+ Demonstrate concrete mechanisms that can be used
+ Highlight real technical tradeoffs

It is:

+ **Not** able to make any edits whatsoever - not even adjusting the word-to-audio mapping
+ **Not** thoroughly tested or documented
+ **Not** production-ready code!

## Scope

### What This Prototype Demonstrates

The purpose of this application is to demonstrate:

+ Transcription
	+ Transcription runs locally; no cloud services are required.
	+ Transcription  generates word-level timestamps
	+ Transcription uses a Whisper-family model to produce word timings.
	+ Transcription progress is streamed from whisper wrapper back to front end.
+ UI Concepts
	+ Transcript-driven navigation
	+ Clicking a word in the transcript seeks the audio to that word.
	+ Playback highlights the current word in the transcript.
	+ Audio is displayed using a waveform view synchronized with playback.
	+ Waveform visualization to fine-tune selections
+ Architecture
	+ Electron architecture
	+ Separation of concerns between:
		+ Main process (file access, process spawning)
		+ Renderer (UI)
		+ Preload (secure IPC boundary)
	+ Local Whisper-based ASR
	+ Flexible pipeline for transcription process
	+ Transcription results are cached on disk (keyed by audio content and pipeline spec); override with `--no-cache` or clear via `clear-cache` (see CLI below).
	+ For long audio (~20+ minutes), the `whisperx_vad` transcriber can use a parallel execution path; other transcribers stay single-process.
	+ The Python worker supports cooperative pause, resume, and cancel over stdin (used by the Electron UI during transcription).

### What This Prototype Intentionally Does Not Do

To keep the focus clear, this prototype does not attempt to:

+ Perform transcript-based editing (cut, paste, rearrange)
+ Persist projects or edits
+ Handle multiple speakers (diarization)
+ Support all audio formats
+ Package into a self-contained application
+ Provide a polished end-user experience

These are deliberate omissions and are appropriate topics for the full capstone project. Additional documentation lives under [`doc/`](doc/) (for example [`UnderstandingElectron.md`](doc/UnderstandingElectron.md) and [`User_Stories.md`](doc/User_Stories.md)).

### Languages

The PoC app is written in TypeScript and runs in Electron, while the transcription pipeline is written in Python.

Key details:

+ TypeScript sources live in `src/` and compile to `dist/` during `npm start`.
+ The Electron main and preload scripts compile to CommonJS (Node context).
+ The renderer compiles to ES modules (browser context) to avoid `exports`/`require` issues.
+ The Python pipeline runs as a separate process and communicates with Electron over IPC.

### Supported Audio Format

For simplicity and accurate word-level seeking, this prototype only supports PCM WAV audio.

Why:

+ WAV provides sample-accurate seeking
+ Avoids codec delays and frame-based imprecision
+ Keeps synchronization logic simple and predictable

Students are encouraged to explore broader format support (e.g., MP3, AAC, normalization pipelines) as part of the capstone. In the mean time, audio files can be converted to an acceptable WAV format using ffmpeg:

```
 ffmpeg -y -i input.aifc -c:a pcm_s16le -ac 1 output.wav
```

In this example we converted a format commonly produced by Apple devices into a standard WAV file.

## Installing, Launching, and Using the PoC

### Requirements

+ Node.js (v18+ recommended)
+ Python 3.10+
+ [Electron](https://www.electronjs.org)
+ [faster-whisper](https://pypi.org/project/faster-whisper/) for text transcription
+ [whisperx](https://pypi.org/project/whisperx/) for text transcription (often brings in PyTorch and related deps)
+ [pydash](https://pypi.org/project/pydash/)
+ [soundfile](https://pypi.org/project/soundfile/) (audio duration and I/O in the pipeline runner)
+ [NumPy](https://numpy.org/) (used by the parallel WhisperX path)
+ [FFmpeg](https://ffmpeg.org):
	+ Used for audio inspection and (optionally) format normalization
	+ Also used indirectly by waveform rendering and audio decoding
	+ Must be available on the system PATH

**Security note:** Electron is pinned to `^35.7.5` to address a moderate security advisory affecting earlier versions. Newer versions may be used at the discretion of the Capstone team.


### Installation & Running

1. Clone the repository (use your fork or upstream URL as appropriate)

	```
	git clone https://github.com/Austin-Metke/OTTER.git
	cd OTTER
	```

2. Install Node dependencies

	```
	npm install
	```

3. Set up Python environment

	```
	python3 -m venv .venv
	```

	Activate the venv: on macOS/Linux use `source .venv/bin/activate`; on Windows use `.venv\Scripts\activate`.

	```
	pip install pydash faster-whisper whisperx soundfile numpy
	```

	(`whisperx` and `faster-whisper` pull in their own stacks; install errors usually mean a missing system library or incompatible Python—see those projects’ docs.)

4. Install `ffmpeg`

   ```
   # This is system dependent. For example, on the mac you can use homebrew:
   brew install ffmpeg
   ```
   
5. Run the app

    **NOTE**: This PoC is not a cleanly packaged app. Run it from a shell where the Python virtual environment is already active, or ensure `python`/`python3` on your PATH can import `otter_py` (the Electron main process prefers `.venv` when present: `Scripts\python.exe` on Windows, `bin/python3` on Unix).

	```
	npm start
	```

    The `npm start` command compiles the TypeScript sources into `dist/` before launching Electron.


### Using the PoC

1.	Click Choose Audio… and select a WAV file.
1.	Click Transcribe to generate a transcript.
1. Press Play in the main waveform area to hear audio starting at the cursor.
1.	Clicking a word in the transcript will:
  + Move the cursor in the main audio waveform
  + Display a detail view of the audio around the selected range (a single word by default)
1. Shift-click extends the selection to create a range of words.
1. Use the detail view to fine-tune the mapping to the selected range
1. During playback, a separate playhead highlight moves word-by-word and does not change the selection.
1. Developer Tools
    + Use the Developer Tools to look at the log from the transcription pipeline
	+ Select a preset from `otter_py/sample_specs` (every `.json` file in that folder is listed) or enter a custom pipeline specification.
	+ When no preset is selected, `default_spec.json` is used (currently `whisperx_vad` plus several post-processors—see that file).

### Transcription CLI (Python)

The Electron app invokes the pipeline as a module from the repo root:

`python -m otter_py.transcribe <command>`

- `list` — print registered transcribers and post-processors (JSON on stdout).
- `run --audio <path> (--spec-file <path> | --spec-json '<json>')` — run a pipeline; progress lines go to stderr as `PROGRESS:NN`.
- `run ... --no-cache` — bypass the filesystem cache.
- `run ... --emit-meta` — emit full `{ words, meta }` instead of trimming to words plus `language`.
- `clear-cache` — delete cached pipeline results (cache lives under the system temp dir, or set `OTTER_CACHE_DIR`).

By default, `run` prints JSON on stdout with `words` and a detected `language` string (metadata is otherwise omitted for a smaller payload). The app parses this the same way.

## Architectural Notes

The system is broken into two primary components: the app and the transcription pipeline. As discussed, the app uses Electron as its basis. Please see [Understanding Electron](doc/UnderstandingElectron.md) for more details on how the app is organized.

The Electron sources are written in TypeScript under `src/` and compiled to `dist/` during `npm start`.
Main and preload compile to CommonJS (Node context), while the renderer compiles to ES modules (browser context). This avoids `exports`/`require` issues in the renderer.

The transcription pipeline is a separate process implemented in Python. The app spins up the transcription pipeline as needed, and communicates with it using [Electron IPC](https://www.electronjs.org/docs/latest/tutorial/ipc).

The app exposes a panel where developers can choose pre-existing pipeline configurations or enter a new one on the fly. This makes experimentation simpler and also allows developers to work in parallel on new pipeline components.

Even with good transcription and post-processing, transcript timing is treated as approximate, not sample-perfect. Minor timing nudges may be required for perceptually clean playback. This reflects real-world constraints of speech recognition systems and learning the limits of this technology is part of the Capstone process.

### Transcription Pipeline

The transcription pipeline consists of a primary transcription step followed by zero or more post-processing steps which may improve accuracy of the transcript and / or alignment of the transcript to the audio. There is a collection of different transcribers and post-processors available and more will be added as part of the Capstone project. For a given run, the pipeline accepts a JSON structure that describes which transcription component to use and which post-processors to apply in which order, with parameters for each. The post-processor list may use the key `"postprocessors"` (as in the sample specs) or `"post"` (canonical alias); both are accepted.

The following components are provided as part of the PoC:

+ Transcription
	+ **faster_whisper**: An implementation using the `faster-whisper` package. Many parameters may be set using the pipeline configuration with no code changes needed. For example, the model size may be changed.
	+ **whisperx_vad**: An implementation using the `whisperx` package along with the `Silero` aligner. Again, many options may be specified including model size.
+ Post-processing
	+ **clean_word_timings**: Normalizes adjacent word boundaries to remove small overlaps and close tiny gaps. This improves selection/playback behavior by ensuring word boundaries are tight and consistent.
	+ **adjust_short_words**: Heuristic pass that expands very short words by extending their start time leftward, without overlapping the previous word.
	+ **filter_fillers**: Removes common filler words (e.g. "uh", "um"), optionally only when confidence is below a threshold.
	+ **filter_low_confidence_words**: Removes or replaces words below a confidence threshold (words without scores can be kept or dropped per options).

The following JSON structure illustrates a pipeline configuration that uses the `faster_whisper` transcriber followed by the `adjust_short_words` and `clean_word_timings` post-processors.

```
{
  "transcriber": {
    "id": "faster_whisper",
    "opts": {
      "model": "small",
      "device": "cpu",
      "compute_type": "int8"
    }
  },
  "postprocessors": [
    {
      "id": "adjust_short_words",
      "opts": {
        "max_len": 0.30,
        "min_extend": 0.10
      }
    },
    {
      "id": "clean_word_timings",
      "opts": {
        "tiny_gap_ms": 300.0
      }
    }
  ]
}
```

Additional transcription modules and post-processors may be designed, implemented, and added as options for the transcription pipeline.  For example, other post processors may analyze the audio waveform to look for clean separations between words to help align the transcript. Another example would be a new transcriber that supported whisper integrated with [MFA](https://montreal-forced-aligner.readthedocs.io/en/latest/index.html).

Also, new collections of parameters will emerge from careful tuning of the pipeline. These specifications will be used in the production implementation to provide optimal transcription results.

## TypeScript Context

TypeScript is a superset of JavaScript. That means every valid JavaScript program is valid TypeScript, but TypeScript adds static types and tooling that can catch mistakes before you run the code. TypeScript ultimately compiles to JavaScript, so changes in `src/` must be recompiled to take effect. The `npm start` command does this automatically before launching Electron. The resulting JavaScript code lives in `dist/`.

Why we use TypeScript here:

+ It makes the code easier to understand and refactor as the project grows.
+ It catches common errors (wrong property names, wrong argument types) at compile time.
+ It improves editor tooling (autocomplete, go-to-definition, inline documentation).

Special considerations for Electron in this project:

+ Safety:
	+ We use `strict: true` so TypeScript is a strong correctness tool, not just a hint system.
	+ We use ESLint to keep style consistent and catch common mistakes early.
	+ Run `npm run lint` to check for issues.

+ Runtime Contexts:
	+ Electron has two different runtime contexts: Node and the Browser
	+ The main/preload scripts run in Node, while the renderer runs in the browser.
	+ We compile main/preload to CommonJS for Node
	+ We compile the renderer to ES modules for the browser.
	+ Connecting the Contexts:
		+ The renderer should not import Node modules directly. Instead, it talks to the main process through `window.otter` (the preload bridge).
		+ TypeScript types for `window.otter` are declared in the renderer so the browser code knows what APIs exist.


## License

This project is licensed under the [MIT License](LICENSE).

You are free to use, modify, and distribute this project under the terms of the MIT license. See the [LICENSE](LICENSE) file for more details.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
