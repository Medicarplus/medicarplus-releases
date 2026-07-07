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
- ✅ **Reset v2 = v1** — v2.html reconstruïda com a còpia exacta de v1 amb només 3 mods:
  - Títol MediCar Plus + i18n
  - `data-cfg-name` a les tabs + override de CFG a `applyCompanyUI`, Llibreta, IRPF, Estadístiques, Assessor IA
  - Bloc de llicència + wizard (280 línies) appended al final
- ✅ Preus dels chips preservats (C.Oficial 20€, Certificado 66.5€, Duplicado 25€, splits 45-45-10, etc.)
- ✅ Repartiments F.Brugulat/Cempla/Dr.Mellado preservats
- ✅ Obfuscador arregla `</script>` bleeding (línia 99 de `obfuscate.js`)
- ✅ ZIP Electron regenerat i disponible a `/api/download-electron`

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
