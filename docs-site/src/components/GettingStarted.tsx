import { useState } from 'react'
import './GettingStarted.css'

const STEPS = [
  {
    n: '01',
    title: 'Clone the repository',
    code: `git clone https://github.com/OTTER-Capstone-ORG/OTTER.git
cd OTTER`,
  },
  {
    n: '02',
    title: 'Install Node dependencies',
    code: `npm install`,
  },
  {
    n: '03',
    title: 'Set up Python environment',
    code: `python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install pydash faster-whisper whisperx`,
  },
  {
    n: '04',
    title: 'Install FFmpeg',
    code: `# macOS (Homebrew)
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg`,
  },
  {
    n: '05',
    title: 'Launch the app',
    note: 'Make sure your Python virtual environment is active first.',
    code: `npm start`,
  },
]

const REQUIREMENTS = [
  { label: 'Node.js', version: 'v18+', icon: '🟩' },
  { label: 'Python', version: '3.10+', icon: '🐍' },
  { label: 'FFmpeg', version: 'latest', icon: '🎞' },
  { label: 'Electron', version: '^35.7.5', icon: '⚡' },
  { label: 'faster-whisper', version: 'latest', icon: '🔊' },
  { label: 'whisperx', version: 'latest', icon: '📝' },
]

export default function GettingStarted() {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null)

  function copy(text: string, idx: number) {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedIdx(idx)
      setTimeout(() => setCopiedIdx(null), 1800)
    })
  }

  return (
    <section className="section getting-started" id="getting-started">
      <div className="getting-started__header">
        <p className="section-label">Setup guide</p>
        <h2 className="section-title">Get up and running</h2>
        <p className="section-body">
          OTTER runs entirely on your local machine. You'll need Node.js, Python, and FFmpeg before starting.
        </p>
      </div>

      {/* Requirements */}
      <div className="getting-started__reqs">
        <p className="getting-started__reqs-title">Requirements</p>
        <div className="getting-started__reqs-grid">
          {REQUIREMENTS.map(r => (
            <div key={r.label} className="getting-started__req">
              <span className="getting-started__req-icon">{r.icon}</span>
              <span className="getting-started__req-label">{r.label}</span>
              <span className="badge badge-muted">{r.version}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Steps */}
      <div className="getting-started__steps">
        {STEPS.map((step, i) => (
          <div key={step.n} className="getting-started__step">
            <div className="getting-started__step-num">{step.n}</div>
            <div className="getting-started__step-body">
              <h3 className="getting-started__step-title">{step.title}</h3>
              {step.note && (
                <p className="getting-started__step-note">⚠ {step.note}</p>
              )}
              <div className="getting-started__code-block">
                <button
                  className="getting-started__copy-btn"
                  onClick={() => copy(step.code, i)}
                  aria-label="Copy code"
                >
                  {copiedIdx === i ? (
                    <>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                      Copied
                    </>
                  ) : (
                    <>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                        <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                      </svg>
                      Copy
                    </>
                  )}
                </button>
                <pre><code>{step.code}</code></pre>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Usage notes */}
      <div className="getting-started__usage card">
        <h3 className="getting-started__usage-title">Using the app</h3>
        <ol className="getting-started__usage-list">
          <li>Click <strong>Choose Audio…</strong> and select a <code>.wav</code> file (PCM WAV recommended).</li>
          <li>Click <strong>Transcribe</strong> and watch progress stream in real time.</li>
          <li>Click any word in the transcript to seek the audio cursor to that word.</li>
          <li><strong>Shift-click</strong> to extend the selection across a range of words.</li>
          <li>Use the detail waveform view to fine-tune word boundary alignment.</li>
          <li>Open <strong>Developer Tools</strong> to inspect pipeline logs and swap JSON specs.</li>
        </ol>
        <div className="getting-started__tip">
          <span className="getting-started__tip-icon">💡</span>
          <p>
            Need to convert audio? Use FFmpeg:{' '}
            <code>ffmpeg -y -i input.aifc -c:a pcm_s16le -ac 1 output.wav</code>
          </p>
        </div>
      </div>
    </section>
  )
}
