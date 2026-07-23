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

## Testing Status (iteration_16.json + follow-up smoke, Feb 2026)
- Backend: 7/7 pytest PASS (heartbeat, push, pull, device limit, PDF render)
- Frontend: 15+ Playwright PASS + 13/13 i18n PASS + smoke visual gate global (btnStatSms/btnStatCites amb candau)
- No critical bugs.

## Landing subscribe → Stripe
- Botons "Contactar" reemplaçats per "💳 Suscribirse (mensual)" + "Suscribirse anual" a Standard i Premium (data-plan-subscribe=STD_MES/STD_ANY/PREMIUM_MES/PREMIUM_ANY)
- Script client-side crida `POST https://project-helper-47.emergent.host/api/create-checkout` → redirigeix a Stripe Checkout de la sessió creada
- Un cop pagat, webhook Stripe activa la llicència + envia mail automàtic amb .exe, guia i codi (ja existent al backend routes/payments.py)

## Gate Premium GLOBAL (v2.html)
- Handler capture-phase a document que intercepta clics a QUALSEVOL `[data-premium="1"]`
- CSS opacity/🔒 automàtic per elements fora de #utilitiesMenu quan Standard
- Aplicat a Estadísticas SMS (#btnStatSms) i Estadísticas Cites (#btnStatCites)
- Ja aplicat a Utilidades menu (SMS, Cites, IA, Auditoría)

## Iteration 19 (Feb 22, 2026) · Nou logo + Vista prèvia de plans + Guies actualitzades
- **Nou logotip Option 2** (dark squircle rounded amb "M" dourat + "+" verd): SVG font + PNG 16/32/48/180/256 + ICO multi-res per web i electron. Aplicat a `landing-medicarplus.html` (nav + footer), `v2.html` (header d'app) i `assets/icon.ico` per l'Electron .exe.
- **Header renovat opció D→2**: font Manrope 800 en color dourat, subtítol "GESTIÓN DE CENTROS MÉDICOS" (letter-spacing 3.5px).
- **Vista prèvia de plans (MASTER only)**: 4 botons a la modal "Info llicència" (Real / Trial / Standard / Premium). Banner lila permanent quan hi ha preview actiu. Trial-badge respecta l'override.
- Files nous a `/app/frontend/public/` (i còpia a `/downloads/`): `logo-medicarplus.svg`, `favicon.ico`, `favicon-{16,32,48,180,256}.png`, `apple-touch-icon.png`, `android-chrome-{192,512}.png`, `electron-icon.ico`.
- v2.html ara té meta favicon links (svg + ico + apple-touch).

## Iteration 18 (Feb 22, 2026) · Trial automàtic + Post-pago automàtic + Lightbox screenshots

- **NOU endpoint `POST /api/trial/start`** (fitxer `backend/routes/trial.py`): genera llicència TRIAL de 60 dies + envia email amb clau + 2 PDFs (guia + manual). Anti-abús: 1 trial per email, honeypot, consent obligatori.
- **Modal Trial a la landing**: reemplaça el `mailto:` anterior. Botó "🎁 Empezar prueba gratuita" (plan Trial) i badges "Prueba gratuita 60 días" (sota Standard i Premium) obren el modal. Al submit, mostren la clau a pantalla + confirmen l'enviament del mail.
- **Endpoint `/api/payments/subscription/status/{id}` estès**: ara retorna també `license_key`, `install_id`, `expires_at`, `license_ready` (buscant a `db.licenses` via `stripe_subscription_id`) + `download_url` fix.
- **NOVA pàgina `subscription-success.html`**: hostejada al backend Emergent. Rep `?session_id=...` de Stripe, fa poll cada 3s (20 intents = 60s màx), i mostra la clau + botó "📥 Descargar" + confirmació d'email en quan el webhook ha corregut. Redirecció Stripe canviada a aquesta pàgina (no a `/request-license`).
- **API URLs auto-detectats** al landing (`API_BASE`): si el hostname és `medicarplus.es` → producció Emergent, sinó → mateix origin. Elimina el hardcoding que trencava en preview.
- **Lightbox modal de captures** a les targetes "Características": 9 targetes mapejades a les captures de GitHub (`https://medicarplus.es/screenshots/*.jpg`). Afegides 3 targetes noves (Estadísticas, Citas, Auditoría) per aprofitar totes les captures. Etiqueta "🔍 Ver ejemplo" a cada targeta clicable.
- **Botons plans polits**: "Suscribirse anual" ara mostra "🗓️ Pago anual · ahorra 58,90€/78,90€" en una sola línia amb padding uniforme (ja no es trenca lletjament).
- **Sync device_not_authorized** verificat (iteració anterior mantinguda).
- **Webhook Stripe** actualitzat via API a producció (URL definitiva `emergent.host/api/webhook/stripe`).

### Cost temporal del `/api/trial/start`: ~5 segons (genera 2 PDFs via Playwright Chromium). Acceptable · el modal mostra spinner "Generando tu licencia…".

## Next Actions (Feb 22, 2026)
1. **User**: click "Volver a publicar cambios" al panel Emergent → puja a producció: endpoint `/api/trial/start`, `/subscription-success.html`, `payments.py` amb success_url nou, i `/api/payments/subscription/status` estès.
2. **User**: puja el nou `landing-medicarplus.html` a GitHub Pages (segueix la guia del pas anterior o la nova secció "🌐 Publicar canvis a la landing" de la guia general).
3. **Futur backlog**:
   - Twilio SMS real (actualment mocked)
   - Stripe live keys migration
   - Verifactu compliance
   - Domain mapping `medicarplus.es → Emergent Hosting` (elimina pas GitHub Pages manual)
   - Panel de mètriques de subscripcions (MRR, churn, failed_payments) al Admin Dashboard
   - Reminder emails al dia 45/55/59 del trial

## Test Credentials
- MASTER offline: `MB-MASTER-BRUGULAT-2026-OWNER`
- Admin token: `MB-ADMIN-BRUGULAT-2026-4F8E2A1C`
- PRM license (2/2 devices used): `CD-PR8E-D4D8-A71A-2842` + `CD-D299-4E88-1F92-364A`
- **Stripe verificat**: totes 4 variables STRIPE_PRICE_* + STRIPE_API_KEY presents al backend. `/api/payments/subscription/enabled` retorna enabled=true. Els 4 packages (STD_MES, STD_ANY, PREMIUM_MES, PREMIUM_ANY) generen sessions Checkout vàlides (checkout.stripe.com).
- **Landing CHECKOUT_API corregit**: abans apuntava a `/api/create-checkout` (endpoint one-off inexistent com a subscripció); ara apunta a `/api/payments/create-subscription` (correcte).
- **Landing email prompt**: els botons "Suscribirse" ara demanen email via `window.prompt()` abans de crear la sessió Stripe (evita el 422 per customer_email missing).
- **Trust badges (conversion improvement)**: sota els botons Suscribirse de Standard i Premium ara hi ha un badge visible "🎁 Prueba gratuita 60 días • Sin tarjeta" + subline "Cancela cuando quieras · Sin permanencia". data-testid: `landing-std-trial-badge`, `landing-prm-trial-badge`.
- **Sync security hardening**: `/api/sync/push` i `/api/sync/pull` ara requereixen que l'install_id ja tingui entrada a `sync_devices` (via heartbeat previ). Un dispositiu no autoritzat rep 403 `device_not_authorized`. Tanca gap on qualsevol amb la licence_key podia escriure/llegir el cloud state.
- **Tests**: 13/13 backend pytest PASS + 9/9 frontend Playwright PASS. Zero action items.

## Next Actions (Feb 2026)
1. **User**: "Volver a publicar cambios" → push aquestes noves versions al domini de producció.
2. **User**: Copiar el nou `landing-medicarplus.html` a GitHub Pages (`medicarplus.es`) perquè el badge i el CHECKOUT_API arribin al públic.
3. **Future backlog**:
   - Real Twilio API (currently mocked)
   - Stripe live keys migration (currently test mode)
   - Verifactu compliance
   - Domain mapping `app.medicarplus.es` → production
   - Google Search Console for medicarplus.es
   - Reparto socios % configuration UI

## Test Credentials
- MASTER offline: `MB-MASTER-BRUGULAT-2026-OWNER`
- Admin token: `MB-ADMIN-BRUGULAT-2026-4F8E2A1C`
- PRM license (DB, 2/2 devices used): install_ids `CD-PR8E-D4D8-A71A-2842` + `CD-D299-4E88-1F92-364A`

## Session Feb 23, 2026 · Auto-upgrade + Multi-device Premium + Editable email
**Bugs fixats en aquesta sessió (tots verificats per testing agent):**
1. **`/api/trial/start` congelava el navegador** (19s síncrons) → email en background, resposta en 0.25s.
2. **Trial JWT no permetia activació** perquè `sub` era un install_id sintètic (`CD-TRIAL-XXXX`). → Ara `sub` és portable (missing/CD-TRIAL-*/CD-STRIPE-*). Client + servidor accepten JWTs portables i fan bind-on-first-verify.
3. **Missatges d'error en català** → tots reescrits en castellà.
4. **Logo M+ no visible a Electron** (URLs relatives resolien contra `file://`) → script inicial al v2.html que reescriu URLs cap al servidor via `window.API_BASE` quan detecta entorn Electron.
5. **Botó "Powered by" no clicable** (selector `[style*="Powered by"]` no matcheava) → nou id `licSigBox`.
6. **Post-Stripe: pàgina de success mostrava clau per copiar** encara que fos upgrade des de dins l'app → ara detecta `metadata.install_id` real i mostra "Vuelve a MediCar Plus, se está actualizando automáticamente".
7. **Guia de instal·lació 404** (apuntava a GitHub Pages inexistent) → link relatiu `/guia-client-installacio.html`.
8. **Doble consentiment obligatori** al formulari Trial: (a) política privacitat + (b) responsabilitat de dades i copies de seguretat. Nova pàgina legal `/terminos-uso.html`.
9. **Botons de plans plans i grisos** → gradients colorits amb pulse: Trial verd, Standard blau, Premium daurat, anuals daurat/morat. Card Trial 100% clicable.
10. **Badge PREMIUM solapava "Ver ejemplo"** a les targetes utilitats → badge mogut a top-left (era right).
11. **Auto-upgrade de plan**: `/api/licenses/current` nou endpoint + polling v2.html cada 5s (primers 2min) / 30s. Detecta upgrade Stripe i actualitza localStorage + refresca UI + toast. Zero fricció client.
12. **`isPremiumLicense` no reconeixia `plan=PREMIUM`** amb `type=JWT` → ara comprova ambdós camps.
13. **Master + Vista prèvia**: quan es fa polling, si l'usuari és MASTER amb `caja.plan.preview.v1` actiu, l'auto-upgrade actualitza la PREVIEW (no la clau real). Perfecte per testing.
14. **Email de llicència no s'enviava en UPGRADE**: ara `_sync_license_from_subscription` envia email també quan actualitza (`subject_prefix='Pla actualitzat a PREMIUM'`).
15. **Email editable abans del pagament**: nou camp `#upgEmailInput` al modal "Ver planes" pre-omplert amb `localStorage.caja.billing.email.v1`. Validació + persistència entre compres.
16. **Multi-dispositiu Premium**: mateixa clau funciona a 2 ordinadors. `linked_hwids` + `linked_install_ids` a `db.licenses`. Standard/Trial segueixen limitats a 1. `/api/licenses/current` cerca en ambdós arrays.
17. **Claus PREMIUM admin-generades ara portables** (`sub=CD-STRIPE-ADMIN-*`) perquè també funcionin a 2 dispositius (abans només les generades per Stripe eren portables).

**Tests**: iteration_19 (4/4 pass), iteration_20 (4/4 pass), iteration_21 (4 backend + 7 frontend pass).

## Backlog · Feb 23, 2026
1. **Classificació adaptativa d'autoescoles** (P1): quan un client puji el seu arxiu, detectar patrons únics d'autoescoles del seu dataset i presentar la llista per confirmar/ajustar (ara està hardcoded per Daina/Mabel/Rossell/etc del owner).
2. **Twilio SMS real** (P1): actualment mocked.
3. **Domain mapping medicarplus.es → Emergent** (P2): eliminar dependència de GitHub Pages.
4. **Google Search Console** (P2).
5. **Reminder emails** dia 45/55/59 del trial (P2).

