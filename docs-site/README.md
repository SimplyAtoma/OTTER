# OTTER Docs Site

A GitHub Pages website for the [OTTER](https://github.com/OTTER-Capstone-ORG/OTTER) project, built with **React + Vite**.

Live URL (once deployed): `https://otter-capstone-org.github.io/OTTER/`

---

## Quick-start (local dev)

```bash
cd docs-site
npm install
npm run dev        # http://localhost:5173/OTTER/
```

## Production build (local test)

```bash
npm run build
npm run preview    # http://localhost:4173/OTTER/
```

---

## Project Structure

```
docs-site/                   ← Vite / React project root
├── index.html               ← HTML entry point (fonts, meta)
├── vite.config.ts           ← base: '/OTTER/' for GitHub Pages
├── package.json
├── tsconfig.json
├── src/
│   ├── main.tsx             ← ReactDOM root
│   ├── App.tsx              ← Page shell, section ordering
│   ├── App.css              ← Design tokens, shared utilities
│   ├── index.css            ← Global reset, animations
│   └── components/
│       ├── Navbar.tsx/.css          ← Sticky nav with scroll shrink
│       ├── Hero.tsx/.css            ← Full-height hero, waveform visual
│       ├── Features.tsx/.css        ← Feature card grid
│       ├── Architecture.tsx/.css    ← Electron layer diagram
│       ├── PipelineDemo.tsx/.css    ← ★ Interactive pipeline explorer
│       ├── GettingStarted.tsx/.css  ← Install steps with copy buttons
│       └── Footer.tsx/.css

.github/
└── workflows/
    └── deploy-docs.yml      ← GitHub Actions CI/CD
```

---

## Deployment: GitHub Actions

### One-time GitHub Pages setup

1. Go to your repo → **Settings → Pages**.
2. Under **Source**, choose **GitHub Actions**.
3. Save. No branch or folder selection needed — the workflow handles it.

### How it works

```
push to main (docs-site/** changed)
        │
        ▼
  [build job]
  • actions/checkout@v4
  • actions/setup-node@v4  (Node 20, npm cache)
  • npm ci
  • npm run build  →  docs-site/dist/
  • actions/upload-pages-artifact@v3

        │
        ▼
  [deploy job]
  • actions/deploy-pages@v4
  • Sets environment URL in the GitHub deployment
```

Every push to `main` that touches `docs-site/` or the workflow file triggers an automatic redeploy. You can also trigger it manually from the **Actions** tab via `workflow_dispatch`.

### Manual deploy (without CI)

```bash
# Install gh-pages helper once
npm install -g gh-pages

cd docs-site
npm run build
gh-pages -d dist --repo https://github.com/OTTER-Capstone-ORG/OTTER.git
```

---

## Customisation

| What | Where |
|---|---|
| Site base path (repo name) | `vite.config.ts` → `base` |
| Brand colours / fonts | `src/index.css` → `:root` |
| Nav links | `src/components/Navbar.tsx` → `NAV_LINKS` |
| Feature cards | `src/components/Features.tsx` → `FEATURES` |
| Demo preset specs | `src/components/PipelineDemo.tsx` → `PRESET_SPECS` |
| Install steps | `src/components/GettingStarted.tsx` → `STEPS` |

---

## Future: Live In-Browser Demo

`PipelineDemo.tsx` is designed as the extension point for a real demo. To upgrade it:

1. Compile the Python pipeline to WebAssembly (Pyodide or a custom WASM build).
2. Or proxy requests to a hosted inference endpoint.
3. Replace the `runSimulation()` stub with real API calls — the UI state machine (`idle → loading → transcribing → postprocessing → done`) is already wired up.

---

## Tech stack

- [React 18](https://react.dev)
- [Vite 4](https://vitejs.dev)
- [TypeScript 5](https://typescriptlang.org)
- [GitHub Actions](https://docs.github.com/en/actions)
- [GitHub Pages](https://docs.github.com/en/pages)
