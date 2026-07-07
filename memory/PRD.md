# MediCar Plus — Product Requirements

## Original problem statement
Transició d'una app HTML offline estable ("Caja del Día") a una app comercial d'escriptori Electron anomenada "MediCar Plus" per a centres mèdics (revisions DGT). Necessita: llicència (offline + JWT online), panel admin web, obfuscació JS i wrapper Electron per Windows.

## Users / Personas
- **Owner (Marc Brugulat Lopez)**: usa la v1 (caja_del_dia.html) intacta per la seva gestoria.
- **Clients comercials**: reben la v2 (MediCar Plus) amb llicència, wizard i branding personalitzable.

## Core requirements
1. **v1 intacta** — `caja_del_dia.html` no es toca mai.
2. **v2 = còpia exacta de v1** + capa comercial mínima:
   - Títol "MediCar Plus"
   - Gate de llicència (JWT/MASTER)
   - Wizard de nom d'empresa (2 empreses)
   - Botó ⚙️ per re-editar noms
3. Backend FastAPI + MongoDB: emet/verifica JWT, rate-limit (slowapi), audits.
4. Admin panel React + portal públic `/request-license`.
5. Obfuscació JS abans de packaging Electron.
6. Electron builder amb auto-updater (`electron-updater`) preparat.

## Implemented (2026-07-07 fork)
- ✅ **Reset v2 = v1** — v2.html reconstruïda com a còpia exacta de v1 amb capes comercials
- ✅ Preus dels chips preservats + splits configurables
- ✅ Wizard: 2 empreses obligatòries + socis opcionals (0-5, % validats a 100)
- ✅ Tots els noms hardcoded eliminats
- ✅ Neteja automàtica `commercialCleanupV3()` de metges pre-cargats a localStorage
- ✅ Popup "Datàfon manual" clicable amb explicació visual
- ✅ Botó 🔓 Logout al header
- ✅ Cercador de clients per nom/cognom al costat de "Deure/Haver" amb resultats en dropdown i navegació al dia
- ✅ Botó 📱 Avisos SMS/WhatsApp: import CSV DGT, plantilla amb variables {NOM}{DNI}{DATA_CADUCITAT}{ADRECA}, preview, canals SMS+WhatsApp, exportar CSV, enviar via Twilio
- ✅ Backend `/api/notifications/send` amb Twilio (SMS + WhatsApp), retorna resultat per contacte
- ✅ **Theme "Colorful Pill"**: botons arrodonits, gradients suaus als panells, hover amb elevation, focus animats, scrollbar personalitzada
- ✅ ZIP Electron regenerat (616 KB, `/api/download-electron`)

## Previous session work
- Admin panel React + `/request-license` portal
- v2 amb JWT + re-check 15 dies
- `javascript-obfuscator` config
- slowapi rate-limiting, MongoDB indexes, GDPR consent, honeypot
- `electron-updater` preparat
- Icona MediCar Plus generada via Gemini Nano

## Roadmap
### P1
- GitHub Releases + `electron-updater` publicació automàtica

### P2
- Stripe Checkout per automatitzar generació de llicències
- Landing page pública de "MediCar Plus"
- Integració Resend per email automàtic de la clau

## Architecture
```
/app
├── frontend/public/
│   ├── caja_del_dia.html      # v1 ORIGINAL (NO TOCAR)
│   └── v2.html                # MediCar Plus source (comercial)
├── frontend/src/               # React admin panel + public license request
├── commercial/
│   ├── build/obfuscate.js     # v2.html → electron/index.html
│   └── electron/              # main.js, package.json, assets, index.html (obf)
├── backend/
│   ├── server.py
│   └── routes/licenses.py     # POST /verify, /generate; GET /download-electron
```

## Key credentials
- Master offline: `MB-MASTER-BRUGULAT-2026-OWNER`

## MongoDB schemas
- `licenses`: `{install_id, license_key, client_name, email, plan, status, created_at, expires_at, verify_count, last_verified_at}`
- `license_requests`: `{install_id, client_name, email, phone, nif, status, created_at}`
