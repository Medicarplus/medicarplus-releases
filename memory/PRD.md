# MediCar Plus · Product Requirements (PRD)

## Original Problem Statement
Full-stack POS and management application for medical driver-license centers (MediCar Plus).
- Zero bugs in accounting logic and data persistence.
- Flawless offline-to-cloud device syncing (`_mergeSnapshots`).
- Strict Data Integrity (all math and round-trips must pass automated invariants).
- PDF generation (daily cash close, honorarios, etc.).
- Playwright + ffmpeg pipeline that generates landing page demo videos.
- Electron desktop app (`.exe`) auto-updated via electron-updater + GitHub Releases.
- Manual backup feature that shows the real OS folder path where the file was saved.

## Architecture
- Monolithic Vanilla JS frontend inside `/app/frontend/public/v2.html` (~19.8k lines).
- Electron wrapper in `/app/commercial/electron/` (main.js, preload.js, assets/).
- FastAPI backend in `/app/backend/` with MongoDB persistence.
- GitHub Actions workflow at `/app/.github/workflows/release.yml` builds Windows installer + portable on `v*` tag push.
- Dynamic download routes: `/api/download/latest-installer` redirects to the latest GitHub Release asset.

## Changelog (recent)
- **2026-02-xx (v2.2.8)**: Restored the classic "M+" icon (gold M + green plus on dark navy squircle) rendered from `/app/frontend/public/logo-medicarplus.svg` into `/app/commercial/electron/assets/icon.ico` + `icon.png`. No functional changes. Version bumped in `/app/commercial/electron/package.json`.
- **2026-02-xx (v2.2.7)**: Added manual backup "open folder" behavior; workflow moved to repo root; standard `GITHUB_TOKEN` permissions.

## Pending backlog
- **P1**: Export "Honorarios y Gastos" to Excel (.xlsx) in addition to the existing PDF (button `#btnHonorarios` in `v2.html`).
- **P2**: Burn-in Spanish subtitles on MP4 demo video using ElevenLabs timestamps.
- **P2**: Short samples of other ElevenLabs voices (Charlie, Brian, Will) for demo-video comparison.
- **P2**: Excel export for monthly Cuadre de Caja.
- **P2**: "Posponer 30 días" button for inactive-client warnings.
- **P2**: History of applied copies (date + sender) in the sync panel.
- **P2**: Alerta Trimestre — warn on app open if a past IRPF quarter isn't marked as paid.
- **P2**: iMac `.dmg` installer via electron-builder.
- **P2**: Migrate Stripe to LIVE mode.
- **P3**: WhatsApp Business API integration.

## Critical rules
- **NEVER refactor `v2.html`** (modularization breaks Electron caching and sync).
- Always use `search_replace` for `v2.html` edits.
- Always run `node commercial/build/obfuscate.js` after any JS edit in `v2.html`.
- The user is non-technical and gets anxious about data loss — reassure, don't jargon.
