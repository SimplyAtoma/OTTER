import './Footer.css'

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer__inner">
        <div className="footer__brand">
          <span className="footer__logo">🦦 OTTER</span>
          <p className="footer__tagline">
            Open Text Transcription Editing Resource<br />
            CSUMB Computer Science Capstone
          </p>
          <span className="badge badge-amber footer__license">MIT License</span>
        </div>

        <div className="footer__links">
          <div className="footer__links-col">
            <p className="footer__links-title">Project</p>
            <a href="#features" className="footer__link">Features</a>
            <a href="#architecture" className="footer__link">Architecture</a>
            <a href="#demo" className="footer__link">Demo</a>
            <a href="#getting-started" className="footer__link">Get Started</a>
          </div>
          <div className="footer__links-col">
            <p className="footer__links-title">Resources</p>
            <a
              href="https://github.com/OTTER-Capstone-ORG/OTTER"
              target="_blank"
              rel="noopener noreferrer"
              className="footer__link"
            >GitHub Repository</a>
            <a
              href="https://github.com/OTTER-Capstone-ORG/OTTER/blob/main/README.md"
              target="_blank"
              rel="noopener noreferrer"
              className="footer__link"
            >README</a>
            <a
              href="https://github.com/OTTER-Capstone-ORG/OTTER/blob/main/LICENSE"
              target="_blank"
              rel="noopener noreferrer"
              className="footer__link"
            >License</a>
            <a
              href="https://github.com/OTTER-Capstone-ORG/OTTER/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="footer__link"
            >Issues</a>
          </div>
        </div>
      </div>

      <div className="footer__bottom">
        <p className="footer__copy">
          © {new Date().getFullYear()} OTTER Capstone ORG · Released under the MIT License
        </p>
        <p className="footer__built">
          Built with React + Vite · Deployed on GitHub Pages
        </p>
      </div>
    </footer>
  )
}
