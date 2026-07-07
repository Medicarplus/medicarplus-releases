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

## Roadmap
### P1 (imminent)
- Configuració Twilio (usuari ha de crear compte + passar credencials)
- Configuració Stripe live (usuari ha de passar sk_live_)
- Column Telefono al CSV DGT (el proveïdor de trànsit ho ha d'afegir)

### P2
- Admin panel: secció "Configuració de pagaments" (IBAN + Stripe keys editables)
- Admin panel: workflow "Marcar com pagat" per requests de transferència
- Enviament automàtic de JWT per email via Resend

### P3
- GitHub Releases + electron-updater auto-publicació
- Landing page pública MediCar Plus
- Historial d'ingressos + facturació automàtica

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
