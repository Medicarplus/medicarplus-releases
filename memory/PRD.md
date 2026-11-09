# MediCar Plus · Product Requirements (PRD)

## Original Problem Statement
Full-stack POS and management application for medical driver-license centers.
- Zero bugs in accounting logic and data persistence.
- Flawless offline-to-cloud device syncing.
- Strict Data Integrity.
- PDF generation.
- Electron desktop app auto-updated via electron-updater + GitHub Releases.

## Architecture
- Monolithic Vanilla JS frontend inside `/app/frontend/public/v2.html` (~20k lines).
- Electron wrapper in `/app/commercial/electron/`.
- FastAPI backend in `/app/backend/` + MongoDB.
- GitHub Actions workflow for Windows installer builds.
- Separate prototype lab at `/app/tramitacion-lab/` (NOT deployed with MediCar).

## Changelog
- **2026-11-09 · Round 2 (after user feedback)**:
  - Modal Editar entrada: added **TIPO** dropdown (Renovación/Expedición/Canje/Duplicado/Prórroga/Recuperación/Revisión/Periódica/Inicial/Obtención) alongside Grupo and Concepto. Only for TRAF entries.
  - AI prompt: REMOVED hardcoded "66,50€ Expedición Conducción = Canje" default. The AI now reads EACH user's `caja.tarifas.rules.v1` from their own localStorage. If no rules exist, the AI is informed and is more cautious. No server-side assumptions.
- **2026-11-09 · Round 1**: 4 CSV/AI/UI bug fixes (bank transactions mis-classification, edit fields, AI pricing rules injection, Grupo column in detail modals).

## Pending backlog
- **P1**: Export "Honorarios y Gastos" to Excel (.xlsx).
- **P2**: Burn-in Spanish subtitles on MP4 demo video.
- **P2**: Excel export for monthly Cuadre de Caja.
- **P2**: "Posponer 30 días" for inactive-client warnings.
- **P2**: Alerta Trimestre IRPF.
- **P2**: iMac `.dmg` installer.
- **P2**: Migrate Stripe to LIVE mode.
- **P3**: WhatsApp Business API integration.

## Critical rules
- **NEVER refactor `v2.html`** — use search_replace only.
- Always run `node commercial/build/obfuscate.js` after any JS edit in `v2.html`.
- `/app/tramitacion-lab/` lives in parallel and must NOT be mixed with MediCar.
- NEVER hardcode a specific user's business rules in the app (e.g., "66,50€ = Canje"). Each client has their own `caja.tarifas.rules.v1` in localStorage.
