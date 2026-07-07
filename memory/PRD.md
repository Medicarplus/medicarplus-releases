# MediCar Plus — Product Requirements Document

## Original problem statement
Transició d'una app HTML offline estable ("Caja del Día") a una app comercial d'escriptori Electron anomenada "MediCar Plus" per a centres mèdics (revisions DGT), amb sistema de llicències (offline + JWT online), panel admin web, obfuscació JS i integracions de pagament + comunicació.

## Users / Personas
- **Owner (M.Brugulat Lopez)** — usa v1 (caja_del_dia.html) intacta per la seva gestoria personal
- **Clients comercials** — reben v2 (MediCar Plus) amb llicència JWT, wizard configurable

## Implemented (2026-07-07 fork)
- ✅ **v2 = còpia exacta de v1** amb capa comercial (llicència + wizard + logout + cercador)
- ✅ Preus i splits configurables via wizard (opcional 0-5 socis)
- ✅ Neteja automàtica `commercialCleanupV3` de metges pre-cargats
- ✅ Botó 🚪 SORTIR corporatiu, contacte `brugulatmarc@gmail.com`
- ✅ **Mòdul SMS/WhatsApp** (v1 + v2) — import CSV DGT amb Nom+Apellido1+Apellido2, afegir manual, plantilla amb variables, exportar CSV o enviar via Twilio
- ✅ **Historial SMS** amb filtre per data + paginació (fins 5000 registres)
- ✅ Backend Twilio (`/api/notifications/send`, `/api/notifications/history`) — retorna 503 si no configurat
- ✅ **Cercador de clients** (v1 + v2) al costat de "Deure/Haver"
- ✅ **Formulari públic llicència** amb targetes de preus, toggle mensual/anual, Install ID opcional
- ✅ **Stripe Checkout** (backend) via emergentintegrations — packages STD_MES/STD_ANY/PREMIUM_MES/PREMIUM_ANY
- ✅ **Theme "Colorful Pill"** aplicat a v1 i v2
- ✅ Testing: 43/43 backend pytest passing + frontend ~95%
- ✅ Guia HTML completa a `/guia-medicar-plus.html`

## Implemented (2026-07-07 · segona sessió · fork continuat)
- ✅ **Stripe Subscriptions preparat en mode Test** (Opció A recurrent)
  - `POST /api/payments/create-subscription` (mode=subscription via stripe SDK 14.4.1)
  - `GET /api/payments/subscription/enabled` (feature-flag: només actiu quan STRIPE_PRICE_* configurat)
  - `GET /api/payments/subscription/status/{session_id}` (polling)
  - `GET /api/payments/subscription/list` (admin)
  - Webhook `/api/webhook/stripe` amplia gestió d'events: `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated/.deleted`
  - Auto-renewal JWT: on `invoice.paid` → `expires_at = current_period_end`; on `cancel/unpaid` → llicència `revoked`
  - Nova col·lecció Mongo `subscriptions` (stripe_subscription_id, stripe_customer_id, install_id, status, current_period_end)
  - `.env` amb variables buides: `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_STD_MES/ANY`, `STRIPE_PRICE_PREMIUM_MES/ANY`
  - Guia HTML pas-a-pas: `/guia-stripe-setup.html`
- ✅ **Auto-updates GitHub Actions** (Fase 10)
  - Workflow `/app/commercial/electron/.github/workflows/release.yml` — build Windows NSIS + portable + publish a GitHub Releases al fer tag `v*`
  - main.js + package.json ja tenien electron-updater configurat
  - Guia HTML pas-a-pas: `/guia-github-releases.html`
- ✅ **Guies noves refetes** (`guia-medicar-plus.html` admin + `guia-client-installacio.html` client) amb estat actual del sistema
- ✅ **🔒 HWID Lock anti-pirateig** — sistema complet per evitar que un client copiï el JWT a un altre PC
  - `preload.js` genera HWID Electron via SHA-256(hostname + platform + arch + memòria + primera MAC no-virtual)
  - Frontend v2.html: `_getHwid()` prioritza `window.appInfo.hwid` (Electron), fallback fingerprint navegador
  - Backend `LicenseVerify` accepta camp opcional `hwid`
  - Verify: 1a activació fa `hwid_lock` binding automàtic; verifies posteriors amb HWID diferent retornen `ok:false, hwid_mismatch:true` amb missatge en català
  - Admin endpoint `POST /api/licenses/{install_id}/reset-hwid` per canvi legítim de PC
  - LicenseRecord model amplia: `hwid_lock`, `hwid_locked_at`, `hwid_reset_count`, `hwid_last_reset_at`
  - Admin UI: nou botó 🔓 (taronja) per desbloquejar HWID amb tooltip mostrant HWID actual + comptador resets
  - ZIP Electron regenerat amb preload.js nou (629 KB)
  - Tots 8 tests curl passen: binding, re-verify, block PC pirata, reset, re-binding, block antic

## Roadmap
### P1 (imminent — bloquejat per usuari)
- Constituir empresa + obrir Stripe account → llavors seguir `/guia-stripe-setup.html` (Price IDs, webhook, sk_live)
- Configuració Twilio (usuari ha de crear compte + passar credencials)
- Column Telefono al CSV DGT (el proveïdor de trànsit ho ha d'afegir)

### P2
- Admin panel: secció "Configuració de pagaments" (IBAN + Stripe keys editables)
- Botó "Pagar amb targeta" al formulari públic de sol·licitud (només visible quan `/api/payments/subscription/enabled` retorna `enabled:true`)
- Portal Stripe self-service per clients (canvi de targeta, veure factures)
- Enviament automàtic de JWT per email via Resend

### P3
- Landing page pública MediCar Plus
- Historial d'ingressos + facturació automàtica
- Suport crypto (USDC/stablecoins) via Stripe crypto

## Architecture
```
/app
├── frontend/public/
│   ├── caja_del_dia.html   # v1 (personal, intacta funcionalment; +visual +SMS +cercador)
│   ├── v2.html             # v2 comercial (llicència + wizard + SMS + cercador)
│   └── guia-medicar-plus.html # guia usuari
├── frontend/src/pages/     # RequestLicensePage (targetes preus) + AdminPage
├── commercial/
│   ├── build/obfuscate.js
│   └── electron/           # main.js, package.json, index.html (obf), assets
├── backend/
│   ├── server.py
│   └── routes/
│       ├── licenses.py     # JWT + requests admin
│       ├── notifications.py # Twilio SMS/WhatsApp + history
│       └── payments.py      # Stripe Checkout
```

## Key credentials (in `/app/memory/test_credentials.md`)
- Master v2: `MB-MASTER-BRUGULAT-2026-OWNER`
- Admin: `MB-ADMIN-BRUGULAT-2026-4F8E2A1C`
- Stripe: `sk_test_emergent` (mode test)
- Twilio: NO configurat

## MongoDB collections
- `licenses`, `license_requests`, `audit_log` — sistema llicències
- `sms_history` — historial d'enviaments massius (indefinit)
- `payment_transactions` — transaccions Stripe (idempotents)
