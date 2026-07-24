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

## Session Feb 23-24, 2026 · Programa de Referits + hardening
**Programa de referits complet (validat 17/17 pytest + FE E2E):**
- Cada llicència PAGADA (STD/PRM) rep un `referral_code` únic `MC-XXXX-XXXX`.
- URL a compartir: `https://medicarplus.es/?ref=CODE` — captura automàtica a sessionStorage.
- Modal Trial de la landing: input opcional "🎁 Código de referido" amb validació en directe + tooltip "?" explicatiu.
- Recompenses via Stripe (idempotents):
  - **Referrer (A)** → cupó `MEDICAR_REFERRAL_2M` (100% off, 2 mesos) aplicat a la subscripció existent.
  - **Referit (B)** → cupó `MEDICAR_REFERRED_1M` (100% off, 1 mes) aplicat al Checkout de B → **visible ABANS de pagar**.
- Trial → Paid: backend revoca doc trial + crea doc paid nou + hereta `referred_by` + genera referral_code + aplica recompensa al referrer.
- Fallback robust: si Stripe falla, s'estén l'`expires_at` de la llicència del referrer 2 mesos i queda registrat per retry.
- Panel `/admin`: nova columna "🎁 Codi referit" amb botó de copiar + badge amb el count de referits.
- Modal `Informació de llicència` del v2.html: bloc morat amb codi + botons "Copiar codi" i "Copiar enllaç" + estadístiques + tooltip "?".

**Bugs fixats durant la implementació:**
- Stripe `discounts` + `allow_promotion_codes` són mútuament exclusius (bug A iter23).
- Trial→Paid path saltava referral_code + reward (bug B iter23).
- Duplicate `id_1` key quan es revoca trial i s'insereix paid amb mateix id (bug C iter24).
- `_doc_to_record` no mapejava els camps nous (referral_code, linked_hwids, etc) (bug D iter24).

**Fitxers claus creats/modificats:**
- `/app/backend/services/referrals.py` (nou)
- `/app/backend/routes/referrals.py` (nou · endpoints `/validate` + `/my-code`)
- `/app/backend/server.py` (webhook capture referred_by + reward apply)
- `/app/backend/routes/payments.py` (conditional discounts / allow_promotion_codes)
- `/app/backend/models/license.py` (nous camps LicenseRecord)
- `/app/backend/routes/licenses.py` (`_doc_to_record` + verify multi-device HWID)
- `/app/backend/routes/trial.py` (captura referred_by)
- `/app/frontend/public/downloads/landing-medicarplus.html` (?ref= + input opcional trial + tooltip)
- `/app/frontend/public/v2.html` (referral block en showLicenseInfo + tooltip + create-subscription amb referred_by)
- `/app/frontend/src/components/admin/AdminDashboard.jsx` (columna "🎁 Codi referit")

**Tests**: iteration_23 (10/10 + 2 bugs found+fixed), iteration_24 (17/17 pass + 2 optional hardening applied).


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



## Session Feb 23, 2026 (P0 Master preview stuck fix)

**Bug fix**: Master Admin quedava "encallat" en simulació Premium després de testejar el flow d'upgrade Trial→Premium. El polling auto-migrava el preview cap al pla remot (PRM al backend) impedint tornar a Trial/Standard manualment.

**Canvis a `/app/frontend/public/v2.html`**:
1. **Nou botó "🔄 Reiniciar pruebas"** al modal de llicència (només visible a MASTER). Neteja `caja.plan.preview.v1`, `caja.plan.preview.autoupg.v1` i `caja.plan.preview.trialkey.v1`. La clau MASTER real i les dades NO es toquen. Confirmació prèvia + toast + reload.
2. **`pollAutoUpgrade` simplificat per MASTER amb preview**: ja NO canvia automàticament el valor del preview quan el backend té un pla superior. Només mostra un toast informatiu (`Webhook OK · Licencia X detectada · tu simulación se mantiene`) una vegada per sessió (via `sessionStorage`). Això permet al MASTER moure's lliurement entre Trial/Std/Prm sense ser arrossegat cap al pla real del backend.
3. Cada clic manual als botons de preview reseteja el flag intern d'auto-upgrade.

**Test**: screenshot tool · botons `btn-reset-preview` i `prev-off` renderitzats correctament al modal.


## Session Feb 23, 2026 (P1 · Twilio BYOA integration)

**Decisió del propietari**: Model **BYOA (Bring Your Own Account)**. Cada centre client configura el seu propi compte Twilio; ells paguen directament a Twilio; MediCar Plus no toca diners. WhatsApp queda ajornat.

**Canvis backend (`/app/backend/routes/sms_campaigns.py`)**:
1. `SmsCampaignCreate` accepta camp opcional `twilio_creds: {sid, token, from}`.
2. `_send_sms(mobile, message, creds=None)` refactoritzat amb prioritat:
   - (1) creds del request (BYOA) → (2) `.env` global (fallback admin) → (3) MOCK.
3. Nou endpoint **`POST /api/sms/test-credentials`**: valida SID+Token cridant Twilio (`accounts(sid).fetch()`) i comprova que el número `from` existeix al compte o és Alphanumeric Sender. Retorna `{ok, account_name, account_status, from_valid, from_kind}` o `{ok:false, reason}`.
4. La resposta de `/campaigns` afegeix `twilio_source: "byoa"|"global"|"mock"` per traçabilitat.
5. La campanya guarda `twilio_used` i `twilio_source` a MongoDB.

**Canvis frontend (`/app/frontend/public/v2.html`)**:
1. Helpers globals: `getTwilioCreds()`, `saveTwilioCreds()`, `clearTwilioCreds()`, `hasTwilioCreds()`. Emmagatzemat a `localStorage['caja.twilio.creds.v1']`.
2. Nou botó **⚙️ Twilio** al header del modal Avisos SMS (obre `openTwilioCfgModal()`).
3. Modal complet de configuració amb 3 camps (SID, Token, From), botó **🔎 Provar credencials** que crida `/test-credentials`, botó **💾 Desar** i botó **🗑 Eliminar credencials**.
4. Banner dinàmic dins el modal SMS: verd (✅ Twilio configurat · Compte propi) o taronja (⚠️ Twilio no configurat · Mode PROVA). Botó "Configurar" al banner mateix.
5. `/campaigns` POST injecta automàticament `twilio_creds` si el client té creds a localStorage.
6. Alert post-campanya ara mostra `(tu cuenta Twilio)`, `(cuenta administrador)` o `(simulación)`.

**Canvis guia client (`/app/frontend/public/guia-client-installacio.html`)**:
- Nova secció **Pas 7 · Enviar SMS als seus pacients (opcional · Twilio)** amb 5 sub-passos: crear compte Twilio → comprar número → copiar credencials → configurar dins l'app → enviar campanya. Costos aproximats + troubleshooting.

**Tests**:
- `curl POST /api/sms/test-credentials` amb fake creds → retorna `credentials_invalid` correctament.
- `curl POST /api/sms/campaigns` amb `twilio_creds` fake → retorna `twilio_source: "byoa"` i `twilio_mode: "real"`.
- Screenshot: `openTwilioCfgModal` exposada globalment, 6 data-testid presents (twilio-sid, twilio-token, twilio-from, twilio-cfg-test, twilio-cfg-save, twilio-cfg-del).

**Data-testids afegits**: `btn-sms-twilio-cfg`, `twilio-sid`, `twilio-token`, `twilio-from`, `twilio-cfg-test`, `twilio-cfg-save`, `twilio-cfg-del`.

**Seguretat**: Credencials mai persistents al backend. Es passen amb cada request via body JSON. localStorage-only al client. El master admin pot continuar usant les creds `.env` si les té definides (fallback automàtic).


## Session Feb 24, 2026 (P0 · Fix Admin Panel login)

**Bug reportat pel client**: Al panell `/admin.html`, després d'introduir el token i clicar "Entrar" no passava res.

**RCA**: Error de sintaxi JS al script inline d'`admin.html`. Línia 366 tenia una cadena JS `'... s\\'ha connectat ...'` on `\\'` es parseja com "un backslash escapat" + "apòstrof que TANCA la cadena", trencant el parsing de la resta del `<script>` sencer. Com que el `<script>` sencer no es carregava, `doLogin` mai es definia i el botó era inert. Confirmat amb `acorn.parse` (error "Missing } in template expression" a línia 242 col 355 del script extret).

**Fix aplicat** (`/app/frontend/public/admin.html` L366): substituït `s\\'ha connectat` per `s\'ha connectat` (escape JS correcte d'un apòstrof dins una cadena delimitada per `'`).

**Verificació**:
- `acorn.parse` sobre el `<script>` extret → `PARSE OK`.
- Playwright: navegació a `/admin.html` + fill token + click → `typeof doLogin === 'function'`, `login.display === 'none'`, `app.display === 'block'`, 11 files a `#tbody`, 0 page errors.
- Screenshot del panell mostra estadístiques i taula de llicències renderitzades correctament.


## Session Feb 24, 2026 (P1 · Adaptive Driving School Extraction + P2 · Manual button in Support Hub)

### P1 · Adaptive Driving School Extraction
Objectiu: quan un client nou importa el seu CSV, l'app ha d'auto-detectar les seves autoescoles, extreure la llista única, normalitzar-la i presentar-la en una UI d'onboarding.

**Canvis** (`/app/frontend/public/v2.html`):
1. Nou store client-side d'aliases: `STATS_ALIAS_KEY='caja.stats.aliases.v1'` + helpers `loadStatsAliases()` / `saveStatsAliases()` mantenen el mapa `{RAW_CODE_UPPER: 'Nom canònic'}` a `localStorage`.
2. `canonicalName(raw)` ara consulta primer el mapa del client i després `STAT_ALIAS` (l'històric hardcoded del propietari Marc Brugulat).
3. `$('#stFile').onchange` refactoritzat:
   - Parseja el CSV mantenint `rawCounts[RAW_UPPER]=total` (abans es col·lapsava directament a canonical).
   - Detecta `newRaws`: codis del CSV que NO són al `STAT_ALIAS`, NO són al mapa de client, i el seu canònic no és a `st.autoescoles`.
   - Si `newRaws.length > 0` → obre modal de revisió `openAutoescoleReview()`.
   - Si `newRaws.length === 0` → aplica import directament (comportament previ).
4. `openAutoescoleReview(newRaws, rawCounts, existingList, onDone)`:
   - Renderitza una taula amb 4 columnes: `Codi CSV` · `Certificats` · `Nom a mostrar` (input editable) · `O fusionar amb…` (dropdown de les autoescoles existents).
   - Copy diferent per primer import (0 autoescoles → "Configura les teves autoescoles") vs imports subseqüents ("Noves autoescoles detectades").
   - Al confirmar, guarda els aliases a `localStorage['caja.stats.aliases.v1']` (persistents entre imports) i executa `onDone()` que reagrupa `sums` pel canònic final i llança el `confirmModal` "Importar {mes} {any}".
5. Sort dels rows per volum descendent (certificats↓) perquè el client vegi primer les autoescoles importants.

**Data-testids afegits**: `ae-review-row-{i}`, `ae-review-name-{i}`, `ae-review-merge-{i}`, `ae-review-cancel`, `ae-review-apply`.

**Verificació E2E** (Playwright):
- CSV amb 3 codis (`AUTOESCOLA_ONE` x2, `AUTOESCOLA_TWO`, `DAINA`) → modal detecta exactament 2 codis nous, `DAINA` filtrat correctament pel `STAT_ALIAS` predefinit.
- Agregació de duplicats OK: `AUTOESCOLA_ONE` = 12+3 = 15.
- Després de renombrar → aliases guardats correctament: `{"AUTOESCOLA_ONE":"Autoescola U","AUTOESCOLA_TWO":"Autoescola Dos"}`.
- Autoescoles afegides i totals correctes al mes: `{"2026-06":{"Autoescola U":15,"Autoescola Dos":8,"A.E.DAINA":5}}`.
- 0 errors JS · `acorn.parse` del `<script>` inline: PARSE OK.

### P2 · Botó Manual al Support Hub
**Canvi**: grid del hub passat de `repeat(3,1fr)` a `repeat(4,1fr)` amb un nou botó `supTabManual` (gradient daurat) que fa `window.open(LIC.MANUAL_URL, '_blank')` per obrir la guia interactiva al navegador per defecte.

**Data-testid afegit**: `sup-tab-manual`.

**Verificació**: Playwright detecta els 4 botons (`sup-tab-manual/bug/remote/phone`); interceptant `window.open` durant el clic al Manual retorna la URL esperada `https://<host>/manual-usuari.html`.


## Session Feb 24, 2026 (Follow-up · STAT_ALIAS gating + GIC template)

### Fix crític · STAT_ALIAS només per al Master Owner
Feedback del propietari: "cada usuari li variaran les autoescoles, ho ha de detectar sol". El mapa hardcoded `STAT_ALIAS` (autoescoles del centre CEMPLA CB de Marc: DAINA, MABEL, M-2, MOLIST, TRÀFIC…) contaminaria les detecions d'altres clients comercials.

**Canvi** (`/app/frontend/public/v2.html`):
- `canonicalName(raw)` ara detecta si l'usuari és MASTER via `lic.type==='MASTER'` o `lic.license_key===LIC.MASTER_KEY`; només aplica `STAT_ALIAS` en aquest cas.
- La detecció de `newRaws` també respecta aquest gate (per clients no-master, un codi que coincideixi amb `STAT_ALIAS` es marca com nou i entra al modal d'onboarding).
- `applyImport` reagrupa `sums` amb la mateixa lògica: aliases del client > STAT_ALIAS (només master) > raw.

**Verificació E2E**:
- Client comercial (`type:'PREMIUM'`, licensa no-master): CSV amb `DAINA;5 · MABEL;8 · TRAFIC;12 · AUTOESCOLA_NOVA;3` → modal mostra els 4 codis (STAT_ALIAS ignorat). ✅
- Master (`type:'MASTER'`, licensa `MB-MASTER-...`): mateix CSV → modal mostra només `AUTOESCOLA_NOVA` (els altres resolts per STAT_ALIAS). ✅

### Plantilla GIC · Descàrrega + guia d'exportació SMS
El programa GIC exporta el llistat de renovacions via <b>Clientes a Revisar</b> aplicant una plantilla `.lst` que defineix les 7 columnes que MediCar Plus espera: `Numero · Nombre · Apellido1 · Apellido2 · Movil · Telefono · FechaRevision`. Fitxer proveït per l'usuari: `F_revision_con_telefono_y_movil.lst` (4898 bytes).

**Canvis**:
1. Plantilla guardada a `/app/frontend/public/downloads/gic-templates/F_revision_con_telefono_y_movil.lst` (accessible via GET `/downloads/gic-templates/F_revision_con_telefono_y_movil.lst`).
2. `v2.html · renderSmsNew()`: afegida secció col·lapsable `<details data-testid="sms-gic-help">` amb els 7 passos numerats (obrir GIC → Clientes a Revisar → dates → Selección → Salida=Listados → carpeta 📂 → carrega plantilla → FICHERO) i botó daurat de descàrrega `data-testid="sms-gic-tpl-download"`.
3. `manual-usuari.html`: nova secció `🖨️ Exportar el listado desde el programa GIC` dins la pestanya SMS amb els mateixos passos i el mateix botó de descàrrega.
4. `guia-client-installacio.html · Pas 7`: callout groc destacat "🖨️ Pas previ · Exportar el llistat des del programa GIC" com a introducció del mòdul SMS.

**Verificació backend** (POST `/api/sms/preview` amb el CSV real de l'usuari `SMS CLIENTS JUNY.csv`, 285 files):
- ✅ 248 vàlids (mòbils normalitzats: espais, punts i guions es netegen bé — `"686 03 95 86"` → `686039586`, `"93-8889301"` → correctament rebutjat com a fix).
- ✅ 31 invàlids (fixes que comencen per 9 correctament detectats).
- ✅ 6 duplicats identificats (per `mobile` normalitzat, no per `name`).
- ✅ UTF-8-sig BOM manejat correctament (`errors='replace'`).
- ✅ Delimitador `;` auto-detectat via `csv.Sniffer`.

**Data-testids afegits**: `sms-gic-help`, `sms-gic-tpl-download`.

**Fitxers modificats**:
- `/app/frontend/public/v2.html` (canonicalName gate, applyImport gate, renderSmsNew ampliat)
- `/app/frontend/public/manual-usuari.html` (secció exportació GIC dins SMS)
- `/app/frontend/public/guia-client-installacio.html` (callout Pas 7)
- `/app/frontend/public/downloads/gic-templates/F_revision_con_telefono_y_movil.lst` (nou fitxer)


## Session Feb 24, 2026 (Follow-up 2 · GIC help card visibility + program pill)

**Feedback del propietari**: (1) "on troben la plantilla que han d'afegir aquí?" — l'ajuda GIC quedava amagada dins un `<details>` col·lapsat; (2) volia que la captura de la pantalla "Clientes a Revisar" fos visible directament dins l'app perquè el client sàpiga on carregar la plantilla; (3) "de moment només GIC, però podríem afegir més programes en el futur i que el client escollís".

**Canvis** (`/app/frontend/public/v2.html · renderSmsNew`):
1. Ajuda GIC ja **no és col·lapsable** — apareix sempre visible amb marc daurat destacat (`border:2px solid #f5b301`, gradient de fons daurat-marronós, ombra), com a primer element del pas de pujar CSV.
2. **Captura del GIC incrustada**: `gic-clientes-a-revisar.png` (58 KB) guardada a `/downloads/gic-templates/` i mostrada dins la targeta amb `cursor:zoom-in` (clic → obre en pestanya nova). El cercle vermell del propietari senyala exactament on carregar el fitxer `.lst`.
3. **Botó de descàrrega prominent**: `📥 Descargar plantilla` en groc gran (13px, padding 10×18, ombra) al capçal de la targeta.
4. **Guia de 5 passos** al costat de la captura (grid 2 columnes) amb els codes `ListadoPorDefecto` i `F_revision_con_telefono_y_movil.lst` destacats.
5. **Callout verd inferior**: "💡 Només cal fer-ho una vegada" + les 7 columnes exportades (`Numero · Nombre · Apellido1 · Apellido2 · Movil · Telefono · FechaRevision`).
6. **Etiqueta d'extensibilitat**: pill `🖥️ Programa usado: GIC` amb text italic petit `(pronto: más programas)` al capçal — deixa el punt d'ancoratge visual per convertir-ho en un `<select>` desplegable quan es donin d'alta més programes (Dr. Sanitas, etc.).

**Canvis** (`/app/frontend/public/manual-usuari.html · pestanya SMS`):
- Mateixa captura `gic-clientes-a-revisar.png` incrustada abans de la llista numerada de 7 passos.
- Botó de descàrrega en callout groc destacat.

**Verificació** (Playwright):
- `data-testid="sms-gic-program-pill"` mostra "🖥️ Programa usado: GIC". ✅
- `data-testid="sms-gic-tpl-download"` href = `/downloads/gic-templates/F_revision_con_telefono_y_movil.lst`. ✅
- `data-testid="sms-gic-screenshot-link"` embedded img src = `/downloads/gic-templates/gic-clientes-a-revisar.png` (HTTP 200 · 58329 bytes). ✅
- `data-testid="sms-gic-help"` bordat daurat (`rgb(245,179,1)`) present. ✅
- Acorn parse: OK · 0 errors JS.

**Backlog futur** (quan calgui):
- Convertir el pill `Programa: GIC` en `<select>` amb opcions: `GIC` (actual), `Dr.Sanitas`, `Clíni-K`, `Altres`. Cada opció renderitza el seu propi bloc d'ajuda + plantilla + captura. Estructura de dades suggerida: `{ gic: { name, tpl_url, screenshot_url, steps: [...] }, ... }` a `LIC.RENEWAL_PROGRAMS`.
- Detecció automàtica al primer CSV import (matching de columnes conegudes) per pre-seleccionar el programa.


## Session Feb 24, 2026 (Follow-up 3 · UI compacta + modal d'ajuda GIC · TOT en castellà)

**Feedback del propietari**: "Fes un interrogant dins per explicar què s'ha de fer amb aquesta plantilla i on copiar-la mostrant la foto — pel client ha de ser fàcil, no vull trucades cada 2×3. I tot en castellà."

**Canvis** (`/app/frontend/public/v2.html · renderSmsNew` + nova `openGicHelpModal`):
1. **Ajuda GIC compactada en una barra horitzontal** amb 3 elements: pill `🖥️ Programa: GIC` + botó rodó `❓` (daurat, 38×38) + botó `📥 Descargar plantilla` (groc gran). Ja no ocupa mig modal.
2. **Nou modal d'ajuda** `openGicHelpModal(tplUrl, imgUrl)`:
   - Capçalera: `🖨️ Cómo aplicar la plantilla en el programa GIC` + subtítol descriptiu + botó `✕`.
   - **Captura del GIC amb fons blanc** (`gic-clientes-a-revisar.png`), cursor:zoom-in per obrir-la en pestanya nova. Caption: "👆 El círculo rojo marca **exactamente** dónde tienes que cargar la plantilla".
   - **Instruccions numerades de 8 passos** (descarregar → obrir GIC → dates → Selección de Ficheros → Salida → carpeta 📂 → FICHERO → pujar CSV).
   - Callout verd: "💡 Solo hay que hacerlo una vez — cada mes solo cambiar fechas y pulsar FICHERO".
   - Footer: botó `Cerrar` + botó `📥 Descargar plantilla` gran.
3. **Localització forçada a castellà**: eliminades totes les cadenes `${isCA ? '...' : '...'}` de la secció GIC. Ara és 100% castellà independentment de l'idioma d'app.

**Data-testids nous**: `sms-gic-help-btn`, `gic-help-close`, `gic-help-screenshot`, `gic-help-cancel`, `gic-help-download`.

**Verificació E2E** (Playwright):
- Barra compacta: pill = `🖥️ Programa: GIC`, botó `❓` present, botó `📥 Descargar plantilla` present. ✅
- Clic al `❓` → modal obre correctament amb captura (`imgSrc` correcte, HTTP 200) i botó de descàrrega (`downloadHref` correcte). ✅
- Clic al `✕` → modal es tanca. ✅
- Acorn parse: OK · 0 errors JS.

**Fitxers modificats**:
- `/app/frontend/public/v2.html` (funció `openGicHelpModal` afegida + `renderSmsNew` refactoritzat compacte)
