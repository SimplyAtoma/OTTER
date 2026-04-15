import './Architecture.css'

const LAYERS = [
  {
    label: 'Renderer (Browser)',
    color: 'amber',
    items: ['UI Components (TypeScript)', 'Waveform View', 'Transcript Panel', 'window.otter bridge'],
  },
  {
    label: 'Preload (IPC Boundary)',
    color: 'teal',
    items: ['contextBridge expose', 'Secure API surface', 'Type declarations'],
  },
  {
    label: 'Main Process (Node)',
    color: 'muted',
    items: ['File I/O', 'Process spawning', 'IPC handlers', 'Electron lifecycle'],
  },
  {
    label: 'Python Pipeline',
    color: 'muted',
    items: ['faster-whisper ASR', 'whisperx VAD', 'Post-processors', 'JSON spec loader'],
  },
]

export default function Architecture() {
  return (
    <section className="section architecture" id="architecture">
      <div className="architecture__layout">
        <div className="architecture__text">
          <p className="section-label">How it works</p>
          <h2 className="section-title">Clean separation<br />of concerns</h2>
          <p className="section-body">
            OTTER uses Electron's three-process model — main, preload, and renderer — with a strict IPC boundary so the UI never touches the filesystem directly. The Python transcription pipeline runs as a child process and streams results back through IPC.
          </p>
          <ul className="architecture__list">
            <li>
              <span className="architecture__bullet" />
              TypeScript sources in <code>src/</code> compile to <code>dist/</code>
            </li>
            <li>
              <span className="architecture__bullet" />
              Main/preload → CommonJS (Node context)
            </li>
            <li>
              <span className="architecture__bullet" />
              Renderer → ES Modules (Browser context)
            </li>
            <li>
              <span className="architecture__bullet" />
              Python pipeline ↔ Electron over stdin/stdout IPC
            </li>
          </ul>
        </div>

        <div className="architecture__diagram">
          {LAYERS.map((layer, i) => (
            <div key={layer.label} className={`arch-layer arch-layer--${layer.color}`}>
              <div className="arch-layer__label">{layer.label}</div>
              <div className="arch-layer__items">
                {layer.items.map(item => (
                  <span key={item} className="arch-layer__item">{item}</span>
                ))}
              </div>
              {i < LAYERS.length - 1 && (
                <div className="arch-layer__arrow">↕ IPC</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
