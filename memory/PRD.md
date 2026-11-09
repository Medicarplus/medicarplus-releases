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
- Monolithic Vanilla JS frontend inside `/app/frontend/public/v2.html` (~19.9k lines).
- Electron wrapper in `/app/commercial/electron/` (main.js, preload.js, assets/).
- FastAPI backend in `/app/backend/` with MongoDB persistence.
- GitHub Actions workflow at `/app/.github/workflows/release.yml` builds Windows installer + portable on `v*` tag push.
- Dynamic download routes: `/api/download/latest-installer` redirects to the latest GitHub Release asset.
- Separate prototype lab at `/app/tramitacion-lab/` (standalone HTML, NOT deployed with MediCar).

## Changelog
- **2026-11-09**: 4 bug-fixes requested by user, applied in a single session:
  1. **CSV category classifier**: "LIQUIDACION DE INTERESES BBVA" and similar (INTERESSOS / COMISS / DESPESES + bank names) were mis-classified as "Indemnizaciones / Despidos". Moved bank-interest/comissions detection ABOVE indemnización check, expanded pattern to cover Spanish bank names (BBVA, Santander, CaixaBank, Sabadell, Kutxa, Ibercaja, Openbank, Unicaja, Bankinter, Bankia). Removed bare `liquidaci` trigger from indemnización (only matches with labor keywords now).
  2. **CSV entry edit modal**: Added editable fields for `Concepto` (text) and `Grupo` (dropdown with Conducción/Armas/Marina/Seguridad/Animales Peligrosos/Deportes/Grúas/Grúa Torre/Grúa Móvil). Only visible for TRAF entries.
  3. **AI review ignored user's price rules**: When calling the Asesor IA (`#aiSend`), the user's custom `caja.tarifas.rules.v1` are now serialized and injected into the prompt so the AI does not flag as "possible error" a price that already matches a user-configured rule (e.g., Expedición + Conducción + 66,50€ = Canje).
  4. **Missing Grupo column**: Added Grupo badge in `showRevisionesDetail` and `showOtrosDetail` modals so each entry shows its Conducción/Marina/Armas/Animales Pel. category next to its Tipo.
- Compiled via `node commercial/build/obfuscate.js` → `/app/commercial/electron/index.html` (3.1 MB output).
- **2026-02-xx (v2.2.9)**: Restored classic "M+" icon, filled canvas.
- **2026-02-xx (v2.2.7)**: Added manual backup "open folder" behavior.

## Pending backlog
- **P1**: Export "Honorarios y Gastos" to Excel (.xlsx) in addition to the existing PDF.
- **P2**: Burn-in Spanish subtitles on MP4 demo video using ElevenLabs timestamps.
- **P2**: Excel export for monthly Cuadre de Caja.
- **P2**: "Posponer 30 días" for inactive-client warnings.
- **P2**: History of applied copies (date + sender) in sync panel.
- **P2**: Alerta Trimestre IRPF.
- **P2**: iMac `.dmg` installer.
- **P2**: Migrate Stripe to LIVE mode.
- **P3**: WhatsApp Business API integration.

## Critical rules
- **NEVER refactor `v2.html`** — use search_replace only.
- Always run `node commercial/build/obfuscate.js` after any JS edit in `v2.html`.
- `/app/tramitacion-lab/` lives in parallel and must NOT be mixed with MediCar.
