# MediCar Plus · PRD (Product Requirements Document)

## Original Problem Statement
Marc Brugulat (Catalonia) is turning a legacy offline HTML cash register app into a commercial Electron desktop app called **MediCar Plus** for medical driver-licence renewal centres in Spain. The product covers:
- HWID-locked license verification
- Web admin panel
- GitHub auto-updater via electron-updater
- Twilio SMS campaigns (currently mocked)
- Stripe subscription integration (test mode)
- Public landing page (medicarplus.es)
- Robust data entry, "Libro de Registro", "Estadísticas", automated email delivery of licenses/manuals, isolated multi-company data, Verifactu compliance, PDF generation

User's preferred language: **Catalan** (UI/code strings in **Spanish**).

## Product Architecture (Feb 2026)

### Frontend
- `frontend/public/v2.html` (~6.7k lines, Vanilla JS main UI)
- `frontend/public/downloads/electron-src/index.html` — **bootstrap loader** that fetches latest v2.html from server each startup; preserves file:// origin so localStorage persists across app updates
- `frontend/public/downloads/electron-src/main.js` — Electron main, `loadFile('index.html')`
- `frontend/public/downloads/electron-src/sync.js` — BUILD-TIME script (npm run release) that pulls latest sources from server + validates
- `frontend/public/downloads/landing-medicarplus.html` — public marketing page
- `frontend/src/components/admin/AdminDashboard.jsx` — Admin panel React component

### Backend (FastAPI + MongoDB via Motor)
- `backend/server.py` — mounts routers, CORS `*`, MONGO_URL from env
- `backend/routes/licenses.py` — /verify, /generate, /admin/*
- `backend/routes/pdf_render.py` — POST /pdf/render (Playwright HTML→PDF, uses system Chrome)
- `backend/routes/sync.py` — NEW: POST /sync/heartbeat, /sync/push, GET /sync/pull for multi-device
- `backend/routes/electron_manifest.py` — /electron/manifest + /electron/download/{filename}
- `backend/services/pdf_builder.py` — reused for guide/manual PDF attachments in emails

### Data Stores
- MongoDB `licenses` — {install_id, license_key(JWT), plan_family, expires_at, stripe_subscription_id, status}
- MongoDB `sync_states` — {_id: sha256(license_key), data: {ls_key: {value, updated_at, author}}, last_updated_at}
- MongoDB `sync_devices` — {license_key_hash, install_id, created_at, last_seen} (max 2 per Premium)
- MongoDB `counters` — atomic sequence for doc numbers

### Deployment
- **Preview** (dev): https://project-helper-47.preview.emergentagent.com
- **Production**: https://project-helper-47.emergent.host (24/7)
- `api-endpoint.json` on GitHub points bootstrap to production URL

## Plans (as of Feb 2026)

| Plan | Price | Devices | Features |
|---|---|---|---|
| **Trial** | Free · 60 days | 1 | Full Premium access (evaluation) |
| **Standard** | 29,90€/mes · 299,90€/año | 1 | Core: CSV DGT, Contabilidad, IRPF, Cierre, PDF, Backup |
| **Premium** | 39,90€/mes · 399,90€/año | 2 sync | Standard + Utilidades (SMS/Citas/IA/Auditoría) + Multi-empresa + Sync automático |

## What's Implemented (Feb 2026)

### Recent (Feb 2026 session)
- ✅ **Descargar PDF** client-side via html2pdf.js@0.10.1 (jsDelivr CDN). Replaces window.print(). WYSIWYG, offline OK, ~300KB PDFs with real content. Fallback: iframe.print() dialog if lib fails.
- ✅ **Plan gating** (STD vs Premium): `isPremiumLicense()` checks MASTER/PRM/PREMIUM/TRIAL. `refreshUtilitiesPremiumUI()` toggles `body[data-not-premium]` attr → CSS shows/hides padlock icons on menu items. Clicking any locked item opens `openPremiumUpgradeModal()`.
- ✅ **Utilidades menu**: 📱 SMS, 📅 Citas, 🤖 IA, 🔎 Auditoría. Badge `⭐🚀` on toggle button for Premium users. Standard sees padlock 🔒.
- ✅ **Auditoría tooltip**: "?" with data-tt="Detecta y encuentra errores más rápidamente, con nombres duplicados o cuotas a 0€ sospechosas..."
- ✅ **Trial 60 days** (was 30) — `AdminDashboard.jsx` line 588 `defaultDays='60'` when plan==='TRIAL'.
- ✅ **Landing page** rewritten: 60d prueba destacada, Utilidades destacadas dins Premium en gradient morat, "2 ordenadores sincronizados" incorporat.
- ✅ **Sync backend** (`routes/sync.py`): heartbeat/push/pull with device tracking. Standard=1 device, Premium=2. LWW per key. sha256 license key hash as _id.
- ✅ **Sync frontend**: 60s cycle, hooks localStorage.setItem, ☁️ indicator, offline resilient (sendBeacon on unload, retry on online/focus). Skips heartbeat for MASTER key (owner).
- ✅ **Auto-upgrade STD→PRM**: Sync heartbeat detects plan change → notifies via `notifyPlanChange` + toast "✨ Plan Premium activado" + refreshes UI immediately without app restart.
- ✅ **Duplicate row removed**: "Saldo anterior" bare row eliminated from sumBox (kept "Saldo anterior caja" only).

### Earlier
- Electron bootstrap → server pulls fresh v2.html each launch (preserves localStorage origin)
- Playwright PDF for guide/manual email attachments
- IONOS SMTP multi-mailbox delivery
- Twilio SMS mock, Google Gemini AI Asesor
- 4-level URL discovery (raw.githubusercontent → jsdelivr → api.github → cached)
- Cierre del día privacy blur, Auto-match Citas ↔ CSV DGT, Statistics per company, corrected DEBE/HABER as expense

## Testing Status (iteration_16.json, Feb 2026)
- **Backend**: 7/7 pytest PASS (heartbeat, push, pull, device limit, PDF render) — iteration_15
- **Frontend**: 15+ Playwright checks PASS + i18n fix verificat 13/13 (Datàfon→Datáfono, Banc→Banco, Entesos→Entendido, popup castellà, syncIndicator top-right)
- No critical bugs.
- **Fixed post-testing** (iteration_16 minor findings): CAJA FÍSICA/CUENTA BANCO + branca 'cempla' Banco also wrapped with L() for future CA-cempla users.

## Next Actions
1. **User**: "Volver a publicar cambios" on Emergent panel → push all Feb 2026 changes to production
2. **User (optional)**: Recompile .exe with `npm run release` to bake in new bootstrap (though existing .exe with bootstrap already pulls latest v2.html)
3. **Future backlog**:
   - Real Twilio API (currently mocked)
   - Stripe live keys (currently test)
   - Verifacti / Verifactu compliance
   - Domain mapping `app.medicarplus.es` → production
   - Google Search Console for medicarplus.es
   - Reparto socios % configuration UI (currently backend-only)

## Test Credentials
- MASTER offline: `MB-MASTER-BRUGULAT-2026-OWNER`
- Admin token: `MB-ADMIN-BRUGULAT-2026-4F8E2A1C`
