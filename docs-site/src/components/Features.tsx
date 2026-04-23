import './Features.css'

const FEATURES = [
  {
    icon: '🔒',
    title: 'Fully Local & Private',
    body: 'Audio and transcripts never leave your machine. No cloud APIs, no data residency concerns. Whisper runs entirely on your CPU.',
    badge: 'Privacy-first',
    badgeType: 'amber',
  },
  {
    icon: '⏱',
    title: 'Word-Level Timestamps',
    body: 'Every word is pinned to an exact sample offset in the WAV file. Click any word in the transcript to seek the audio cursor there instantly.',
    badge: 'Sample-accurate',
    badgeType: 'teal',
  },
  {
    icon: '〰️',
    title: 'Synchronized Waveform',
    body: 'A live waveform view scrolls with playback. A secondary detail pane lets you fine-tune word boundaries at sample resolution.',
    badge: 'Visual editing',
    badgeType: 'teal',
  },
  {
    icon: '🛠',
    title: 'Pluggable Pipeline',
    body: 'Drop a JSON spec into otter_py/sample_specs to swap transcribers and post-processors at runtime — no recompile needed.',
    badge: 'Extensible',
    badgeType: 'amber',
  },
  {
    icon: '🔤',
    title: 'Transcript-Driven Navigation',
    body: 'During playback the active word highlights automatically. Shift-click extends a selection across a range of words for bulk operations.',
    badge: 'UX concept',
    badgeType: 'muted',
  },
  {
    icon: '⚡',
    title: 'Streaming Progress',
    body: 'Transcription progress streams back to the UI over Electron IPC in real time — no blocking spinner, no mystery wait.',
    badge: 'Responsive',
    badgeType: 'muted',
  },
]

export default function Features() {
  return (
    <section className="section features" id="features">
      <div className="features__header">
        <p className="section-label">What it does</p>
        <h2 className="section-title">Designed for audio editors<br />who think in text</h2>
        <p className="section-body">
          The proof-of-concept demonstrates the core mechanisms needed for a full transcript-based audio editor — all without a single outbound network request.
        </p>
      </div>

      <div className="features__grid">
        {FEATURES.map((f, i) => (
          <div
            key={f.title}
            className="card features__card animate-fade-up"
            style={{ animationDelay: `${0.05 * i}s` }}
          >
            <div className="features__icon">{f.icon}</div>
            <div className={`badge badge-${f.badgeType} features__badge`}>{f.badge}</div>
            <h3 className="features__card-title">{f.title}</h3>
            <p className="features__card-body">{f.body}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
