import './Hero.css'

export default function Hero() {
  return (
    <section className="hero" aria-label="OTTER introduction">
      {/* Background grid */}
      <div className="hero__grid" aria-hidden="true" />

      {/* Glow orb */}
      <div className="hero__orb" aria-hidden="true" />

      <div className="hero__content">
        <div className="animate-fade-up delay-1">
          <span className="badge badge-amber hero__badge">
            <span className="hero__badge-dot" />
            Capstone Research Project · CSUMB CS
          </span>
        </div>

        <h1 className="hero__title animate-fade-up delay-2">
          Edit audio by<br />
          <span className="hero__title-accent">editing text</span>
        </h1>

        <p className="hero__subtitle animate-fade-up delay-3">
          OTTER — <strong>O</strong>pen <strong>T</strong>ext <strong>T</strong>ranscription <strong>E</strong>diting <strong>R</strong>esource — is a local-first desktop app that uses automatic speech recognition to synchronize audio waveforms with editable transcripts. No cloud, no data leaks.
        </p>

        <div className="hero__actions animate-fade-up delay-4">
          <a
            href="#getting-started"
            className="btn btn-primary"
          >
            Get Started
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7"/>
            </svg>
          </a>
          <a
            href="https://github.com/OTTER-Capstone-ORG/OTTER"
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-ghost"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
            </svg>
            View on GitHub
          </a>
        </div>

        {/* Waveform illustration */}
        <div className="hero__waveform animate-fade-up delay-5" aria-hidden="true">
          <div className="hero__waveform-track">
            {Array.from({ length: 80 }, (_, i) => (
              <div
                key={i}
                className="hero__bar"
                style={{
                  height: `${Math.max(12, Math.abs(Math.sin(i * 0.4 + 1.2) * 48 + Math.cos(i * 0.17) * 24) + 8)}px`,
                  animationDelay: `${(i % 12) * 0.08}s`,
                  opacity: i > 18 && i < 42 ? 1 : 0.35,
                }}
              />
            ))}
          </div>
          <div className="hero__waveform-label">
            <span className="hero__transcript-word">The</span>
            <span className="hero__transcript-word hero__transcript-word--active">quick</span>
            <span className="hero__transcript-word">brown</span>
            <span className="hero__transcript-word">fox</span>
            <span className="hero__transcript-word">jumps</span>
            <span className="hero__transcript-word">over</span>
            <span className="hero__cursor" />
          </div>
        </div>
      </div>

      {/* Stats strip */}
      <div className="hero__stats animate-fade-up delay-5">
        {[
          { value: '100%', label: 'Local & Private' },
          { value: 'Whisper', label: 'ASR Engine' },
          { value: 'Word-level', label: 'Timestamps' },
          { value: 'MIT', label: 'License' },
        ].map(stat => (
          <div key={stat.label} className="hero__stat">
            <span className="hero__stat-value">{stat.value}</span>
            <span className="hero__stat-label">{stat.label}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
