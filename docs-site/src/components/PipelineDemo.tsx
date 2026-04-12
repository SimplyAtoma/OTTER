import { useState } from 'react'
import './PipelineDemo.css'

const PRESET_SPECS = [
  {
    id: 'fast',
    label: 'Fast (small model)',
    spec: {
      transcriber: {
        id: 'faster_whisper',
        opts: { model: 'small', device: 'cpu', compute_type: 'int8' },
      },
      postprocessors: [
        { id: 'clean_word_timings', opts: { tiny_gap_ms: 300.0 } },
      ],
    },
  },
  {
    id: 'accurate',
    label: 'Accurate (medium model)',
    spec: {
      transcriber: {
        id: 'faster_whisper',
        opts: { model: 'medium', device: 'cpu', compute_type: 'float16' },
      },
      postprocessors: [
        { id: 'adjust_short_words', opts: { max_len: 0.3, min_extend: 0.1 } },
        { id: 'clean_word_timings', opts: { tiny_gap_ms: 300.0 } },
      ],
    },
  },
  {
    id: 'vad',
    label: 'WhisperX + VAD',
    spec: {
      transcriber: {
        id: 'whisperx_vad',
        opts: { model: 'base', device: 'cpu' },
      },
      postprocessors: [
        { id: 'adjust_short_words', opts: { max_len: 0.3, min_extend: 0.1 } },
        { id: 'clean_word_timings', opts: { tiny_gap_ms: 200.0 } },
      ],
    },
  },
]

type SimWord = { text: string; start: number; end: number }

const DEMO_TRANSCRIPT: SimWord[] = [
  { text: 'The', start: 0.00, end: 0.18 },
  { text: 'quick', start: 0.20, end: 0.52 },
  { text: 'brown', start: 0.55, end: 0.88 },
  { text: 'fox', start: 0.90, end: 1.10 },
  { text: 'jumps', start: 1.15, end: 1.55 },
  { text: 'over', start: 1.58, end: 1.85 },
  { text: 'the', start: 1.88, end: 2.00 },
  { text: 'lazy', start: 2.05, end: 2.45 },
  { text: 'dog', start: 2.48, end: 2.80 },
]

type Stage = 'idle' | 'loading' | 'transcribing' | 'postprocessing' | 'done'

const STAGE_LABELS: Record<Stage, string> = {
  idle: '',
  loading: 'Loading model…',
  transcribing: 'Transcribing audio…',
  postprocessing: 'Running post-processors…',
  done: 'Complete',
}

export default function PipelineDemo() {
  const [selectedPreset, setSelectedPreset] = useState(PRESET_SPECS[0])
  const [customJson, setCustomJson] = useState('')
  const [useCustom, setUseCustom] = useState(false)
  const [stage, setStage] = useState<Stage>('idle')
  const [progress, setProgress] = useState(0)
  const [selectedRange, setSelectedRange] = useState<[number, number] | null>(null)
  const [jsonError, setJsonError] = useState('')
  const [playhead, setPlayhead] = useState(0)

  function validateJson(val: string) {
    if (!val.trim()) { setJsonError(''); return true }
    try { JSON.parse(val); setJsonError(''); return true }
    catch { setJsonError('Invalid JSON'); return false }
  }

  function runSimulation() {
    if (useCustom && !validateJson(customJson)) return
    setStage('loading')
    setProgress(0)
    setSelectedRange(null)
    setPlayhead(0)

    const stages: [Stage, number, number][] = [
      ['loading', 0, 600],
      ['transcribing', 15, 1800],
      ['postprocessing', 80, 700],
      ['done', 100, 0],
    ]

    let elapsed = 0
    stages.forEach(([s, p, delay]) => {
      setTimeout(() => {
        setStage(s)
        setProgress(p)
        if (s === 'transcribing') {
          // Animate progress bar from 15→80
          let pct = 15
          const ticker = setInterval(() => {
            pct += 2
            setProgress(Math.min(pct, 79))
            if (pct >= 79) clearInterval(ticker)
          }, 40)
        }
      }, elapsed)
      elapsed += delay
    })
  }

  function handleWordClick(idx: number, e: React.MouseEvent) {
    if (stage !== 'done') return
    if (e.shiftKey && selectedRange) {
      setSelectedRange([Math.min(selectedRange[0], idx), Math.max(selectedRange[1] ?? idx, idx)])
    } else {
      setSelectedRange([idx, idx])
      setPlayhead(DEMO_TRANSCRIPT[idx].start)
    }
  }

  const spec = useCustom ? customJson : JSON.stringify(selectedPreset.spec, null, 2)

  return (
    <section className="section pipeline-demo" id="demo">
      <p className="section-label">Interactive Demo</p>
      <h2 className="section-title">Explore the pipeline</h2>
      <p className="section-body">
        Choose a preset configuration or write your own JSON spec below, then run the simulated transcription pipeline to see how OTTER processes audio.
        {' '}<span className="pipeline-demo__future-note">
          ✦ Full in-browser audio processing coming in a future release
        </span>
      </p>

      <div className="pipeline-demo__layout">
        {/* ── Left: Config panel ── */}
        <div className="pipeline-demo__config card">
          <div className="pipeline-demo__config-header">
            <span className="pipeline-demo__config-title">Pipeline Spec</span>
            <div className="pipeline-demo__toggle">
              <button
                className={`pipeline-demo__toggle-btn${!useCustom ? ' active' : ''}`}
                onClick={() => setUseCustom(false)}
              >Preset</button>
              <button
                className={`pipeline-demo__toggle-btn${useCustom ? ' active' : ''}`}
                onClick={() => setUseCustom(true)}
              >Custom</button>
            </div>
          </div>

          {!useCustom ? (
            <div className="pipeline-demo__presets">
              {PRESET_SPECS.map(p => (
                <button
                  key={p.id}
                  className={`pipeline-demo__preset-btn${selectedPreset.id === p.id ? ' active' : ''}`}
                  onClick={() => setSelectedPreset(p)}
                >
                  {p.label}
                </button>
              ))}
            </div>
          ) : (
            <div className="pipeline-demo__custom">
              <textarea
                className={`pipeline-demo__textarea${jsonError ? ' error' : ''}`}
                value={customJson}
                onChange={e => { setCustomJson(e.target.value); validateJson(e.target.value) }}
                placeholder={JSON.stringify(PRESET_SPECS[0].spec, null, 2)}
                rows={12}
                spellCheck={false}
              />
              {jsonError && <p className="pipeline-demo__json-error">{jsonError}</p>}
            </div>
          )}

          <pre className="pipeline-demo__json-preview">
            <code>{spec}</code>
          </pre>

          <button
            className="btn btn-primary pipeline-demo__run-btn"
            onClick={runSimulation}
            disabled={stage === 'loading' || stage === 'transcribing' || stage === 'postprocessing'}
          >
            {stage === 'idle' || stage === 'done'
              ? <>▶ Run Simulation</>
              : <><span className="pipeline-demo__spinner" /> {STAGE_LABELS[stage]}</>
            }
          </button>
        </div>

        {/* ── Right: Output panel ── */}
        <div className="pipeline-demo__output card">
          {/* Progress */}
          <div className="pipeline-demo__progress-row">
            <span className="pipeline-demo__stage-label">
              {stage === 'idle' ? 'Ready' : STAGE_LABELS[stage]}
            </span>
            <span className="pipeline-demo__pct">{progress}%</span>
          </div>
          <div className="pipeline-demo__progress-bar">
            <div
              className="pipeline-demo__progress-fill"
              style={{ width: `${progress}%`, transition: progress === 0 ? 'none' : 'width 0.3s ease' }}
            />
          </div>

          {/* Waveform mock */}
          <div className="pipeline-demo__waveform" aria-hidden="true">
            {Array.from({ length: 56 }, (_, i) => {
              const wordIdx = DEMO_TRANSCRIPT.findIndex(
                w => i / 56 >= w.start / 3 && i / 56 < w.end / 3
              )
              const isInRange =
                selectedRange !== null &&
                wordIdx >= selectedRange[0] &&
                wordIdx <= selectedRange[1]
              const isPlayhead = Math.abs(i / 56 - playhead / 3) < 0.015

              return (
                <div
                  key={i}
                  className={`pipeline-demo__wbar${stage === 'done' ? ' active' : ''}${isInRange ? ' selected' : ''}${isPlayhead ? ' playhead' : ''}`}
                  style={{
                    height: `${Math.max(10, Math.abs(Math.sin(i * 0.45 + 0.8) * 40 + Math.cos(i * 0.2) * 18) + 6)}px`,
                    animationDelay: `${(i % 10) * 0.12}s`,
                  }}
                />
              )
            })}
          </div>

          {/* Transcript */}
          <div className="pipeline-demo__transcript">
            {stage === 'idle' && (
              <p className="pipeline-demo__transcript-placeholder">
                Run the simulation to generate a transcript…
              </p>
            )}
            {(stage === 'loading' || stage === 'transcribing' || stage === 'postprocessing') && (
              <div className="pipeline-demo__processing">
                {stage === 'transcribing' &&
                  DEMO_TRANSCRIPT.slice(0, Math.floor((progress - 15) / 65 * DEMO_TRANSCRIPT.length)).map((w, i) => (
                    <span key={i} className="pipeline-demo__word appearing">{w.text} </span>
                  ))
                }
                {stage !== 'transcribing' && <span className="pipeline-demo__ellipsis">···</span>}
              </div>
            )}
            {stage === 'done' && (
              <>
                <p className="pipeline-demo__hint">
                  Click a word to seek · Shift-click to extend selection
                </p>
                <div className="pipeline-demo__words">
                  {DEMO_TRANSCRIPT.map((w, i) => {
                    const inRange = selectedRange && i >= selectedRange[0] && i <= selectedRange[1]
                    return (
                      <button
                        key={i}
                        className={`pipeline-demo__word-btn${inRange ? ' selected' : ''}`}
                        onClick={e => handleWordClick(i, e)}
                      >
                        <span className="pipeline-demo__word-text">{w.text}</span>
                        <span className="pipeline-demo__word-time">{w.start.toFixed(2)}s</span>
                      </button>
                    )
                  })}
                </div>
                {selectedRange && (
                  <div className="pipeline-demo__selection-info">
                    <span className="badge badge-amber">
                      Selected: "{DEMO_TRANSCRIPT.slice(selectedRange[0], selectedRange[1] + 1).map(w => w.text).join(' ')}"
                    </span>
                    <span className="pipeline-demo__selection-range">
                      {DEMO_TRANSCRIPT[selectedRange[0]].start.toFixed(2)}s –{' '}
                      {DEMO_TRANSCRIPT[selectedRange[1]].end.toFixed(2)}s
                    </span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
