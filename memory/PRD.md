# PRD — MediCar Plus (Estat 08/07/2026)

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
