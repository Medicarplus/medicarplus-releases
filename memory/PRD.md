# PRD — MediCar Plus (Estat 08/07/2026)


## 🛡️ Sistema BULLETPROOF de publicació (09/07/2026) — 10 CAPES

Impossible que arribi un `.exe` corrupte als clients. Palanca d'emergència remota.

**Capes servidor (backend):**
1. **Manifest SHA-256** — `GET /api/electron/manifest` retorna hashes + mides + validacions de signatura dels 5 fitxers font. Si algun està corrupte al servidor, s'omet del manifest.
2. **Kill switch remot** — `GET /api/electron/update-channel?current_version=X`. Configurable via `/app/backend/electron_channel.json` amb `blocked_versions`, `latest_safe_version`, `rollback_to`.

**Capes local build (a `/app/commercial/electron/`):**
3. **`sync.js` v2** — Descàrrega ATÒMICA: manifest → tmp → SHA verify → signatures → swap. Backup automàtic. Rutes alternatives (index.html cau a `/v2.html` si `/downloads/electron-src/index.html` retorna 404). Exit 3 FATAL si locals corruptes.
4. **`validate-local.js`** — Verifica strings crítiques abans de compilar. Abort exit 3 si en falta cap.
5. **`smoke-test.js`** — Extreu `app.asar` del `.exe` compilat i verifica strings crítiques + mida raonable (>30MB).
6. **`publish-safe.ps1`** — Orquestrador PowerShell 1-comanda: sync → validate → bump → build → smoke → publish → verify-remote. Aborta al primer error.
7. **Verificació remota GitHub API** — Consulta la release publicada per confirmar que hi és.

**Capes client (main.js + index.html):**
8. **Kill switch client-side** (`main.js`) — Consulta `/api/electron/update-channel` abans que autoUpdater instal·li res. Si la versió està bloquejada, cancel·la la descàrrega/instal·lació.
9. **Boot guard** (`index.html`) — Si en 10s no s'ha renderitzat cap element clau, mostra UI de recuperació amb enllaç a reinstalar.
10. **window.onerror global** (`index.html`) — Captura errors JS globals i, si passen abans de renderitzar contingut, mostra UI de recuperació. Cap client veurà mai una finestra en blanc.

**Fitxers rellevants:**
- `/app/backend/routes/electron_manifest.py` (endpoint manifest)
- `/app/backend/routes/electron_channel.py` (endpoint kill switch)
- `/app/backend/electron_channel.json` (opcional, config del kill switch)
- `/app/commercial/electron/sync.js` — descàrrega bulletproof
- `/app/commercial/electron/validate-local.js` — pre-build check
- `/app/commercial/electron/smoke-test.js` — post-build check
- `/app/commercial/electron/publish-safe.ps1` — one-command wrapper
- Tots també servits a `/downloads/electron-src/` perquè l'usuari els pugui baixar

**Ús diari:** `powershell -File publish-safe.ps1` (a la carpeta local de build)

**Emergència:** editar `/app/backend/electron_channel.json` amb la versió dolenta a `blocked_versions` → efecte immediat en tots els clients.


## Estat del sistema

### ✅ COMPLETAT AVUI (dia productiu)

**Domini + Email**
- `medicarplus.es` (IONOS) — 1€/any
- 5 correus: `info@` (Correo Profesional 50GB) + 4 àlies (`suport@`, `factures@`, `marc@`, `no-reply@`)
- SMTP `smtp.ionos.es:587` (TLS) · IMAP `imap.ionos.es:993` (SSL)
- Estat DNS: **Propagant** (24-48h natural)

**Stripe (Test mode operatiu)**
- Compte creat amb `info@medicarplus.es`
- 4 preus configurats: STD_MES (29.90€/mes) · STD_ANY (299.90€/any) · PREMIUM_MES (39.90€/mes) · PREMIUM_ANY (399.90€/any)
- Webhook actiu amb signing secret
- Auto-renovació + auto-cancel · Test provat OK

**GitHub Releases (Auto-updater)**
- Usuari `Medicarplus`, repo privat `medicarplus-releases`
- Personal Access Token (Contents+Actions Read/Write)
- Versions publicades: v2.0.0, v2.0.1
- `electron-updater` integrat a `main.js`
- **v2.0.3** preparat al zip actual amb tots els canvis

**App v2 (Electron)**
- Botó `🌐 medicarplus.es` al header
- Versió visible a la cantonada superior dreta
- Contabilidad dropdown: Libreta · IRPF · Informe anual · Reserva de Cambio
- IRPF % configurable per empresa (input 0-100 + presets 7%/15%/19%)
- Reserva de cambio v2 amb paquets (1c=0,5€, 2c=1€, 5c=2,5€, 10c=4€, 20c=8€, 50c=20€, 1€=25€, 2€=50€) + € manual
- Reserva repercuteix a Saldo Anterior + Caja Física
- Powered by: **MediCar Plus** (no personal)

**Landing page**
- Ruta `/` (React) amb secció Hero, Features, Pricing, FAQ, Contact
- 3 plans (Trial/Standard/Premium)
- Botó **💳 PAGAR CON TARJETA** → checkout Stripe funcional
- Botó **🏦 Transferència bancària** → formulari

**Sistema**
- Tots els emails personals substituïts per `info@medicarplus.es`
- Landing i backend consistents

### ⏳ PENDENT

- Deploy a Emergent (2 clics)
- Canviar DNS A record IONOS → IP Emergent
- Stripe LIVE (quan Marc obri empresa+banc)
- Twilio SMS/WhatsApp (Premium)
- Signatura de codi Windows (~300€/any, opcional)

## Credencials
Vegeu `/app/memory/test_credentials.md`

## Files clau
- `/app/frontend/public/v2.html` — App Electron (obfuscada a electron/index.html)
- `/app/frontend/public/index-guies.html` — Panell mestre amb resum del dia
- `/app/frontend/src/pages/LandingPage.jsx` — Landing amb Stripe integration
- `/app/backend/routes/payments.py` — Stripe subscription endpoints
- `/app/commercial/electron/package.json` — v2.0.3 amb publish → GitHub
- `/app/frontend/public/downloads/medicar-plus-electron.zip` — Zip actualitzat 1.3M

## Changelog recent
- **2026-02-07**: Fix Reserva Cambio (button + reservaCambio helper)
- **2026-02-07**: IRPF % configurable per empresa
- **2026-02-07**: Reserva Cambio v2 amb paquets
- **2026-07-08**: Domini medicarplus.es + 5 correus IONOS
- **2026-07-08**: Stripe Test mode + 4 preus + webhook
- **2026-07-08**: GitHub Releases (v2.0.0, v2.0.1) + auto-updater
- **2026-07-08**: Landing page amb dual CTA (Stripe checkout + transfer)
- **2026-07-08**: v2.0.3 preparat amb versió visible, medicarplus.es link, referències personals eliminades
- **2026-07-08**: Fix sandbox=true bloqueava versió package.json (v2.0.5)
- **2026-07-08**: Badge visual de període de prova (30 dies) amb estats Verd/Taronja/Vermell
- **2026-07-09**: 📥 Botó Importar CSV mogut al costat de "Entradas del día" (secció Tràfic)
- **2026-07-09**: ⚙️ Modal Configuració centralitzat (Idioma + Comprovar versió + Empreses + Suport + Sortir)
- **2026-07-09**: Backend `/api/support/contact` endpoint per tickets amb integració SMTP IONOS
- **2026-07-09**: IPC `check-for-updates` exposat via preload per botó manual al modal
- **2026-07-09**: sync.js auto-download servidor + oneClick installer + `verifyUpdateCodeSignature: false`
- **2026-07-09**: Auto-updater funcional (repo medicarplus-releases PÚBLIC)
- **2026-07-09**: Landing medicarplus.es LIVE via GitHub Pages (repo Medicarplus/medicarplus.es)
- **2026-07-09**: Favicon + logo cotxe integrat a la landing
- **2026-07-09**: Reposicionament: DGT → GIC, "centros de reconocimientos médicos" (no autoescuelas)
- **2026-07-09**: SMTP IONOS actiu (SMTP_PASS al .env) - tickets suport arriben a info@medicarplus.es ✅
- **2026-07-09**: Guia mestre `/guia-publicar-versions.html` amb totes les seccions actualitzades
