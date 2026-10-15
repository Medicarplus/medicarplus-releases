# MediCar Plus · PRD

## Original problem statement
POS y app de gestión para autoescuelas y centros médicos (TRÀFIC + CEMPLA). Zero bugs en contabilidad, PDF/Excel exports, sync offline→cloud (`_mergeSnapshots`), integridad estricta de datos. Monolito Vanilla JS en `v2.html` (~18.5k líneas) envuelto en Electron, backend FastAPI + MongoDB. Idioma usuario: Español/Catalán.

## Stack
- Frontend monolítico: `/app/frontend/public/v2.html` + manual (`manual-usuari.html`) + landing (React).
- Backend: FastAPI + MongoDB (`/app/backend/routes/*`).
- Desktop: Electron wrapper → `/app/commercial/electron/index.html`.
- Integraciones: Stripe, LabsMobile (SMS único), OpenAI/Claude (Emergent LLM Key).

## What's implemented
- Doble contabilidad TRÀFIC + CEMPLA independientes
- Sync offline↔cloud (`_mergeSnapshots`) con tests de regresión
- SMS Campañas vía **LabsMobile** (único proveedor desde Feb 2026)
- Validador LabsMobile credenciales + saldo (`/api/sms/labsmobile/validate`)
- Export PDF Honorarios, Cuadre, Libro Registro
- Panel admin, licencias con `_synthetic_master`, dispositivos
- Manual de usuario interactivo con buscador y 8 pestañas · incluye guía paso-a-paso LabsMobile
- **[Feb 2026]** **Twilio retirado del UI** (código conservado, no roto). Auto-cleanup one-time de credenciales Twilio al abrir la app.

## Backlog (prioridad)
- **P1** · Export Excel (.xlsx) de "Honorarios y Gastos" (botón `#btnHonorarios`)
- **P1** · Vídeo demo 30s en landing
- **P2** · Export Excel Cuadre de Caja mensual
- **P2** · "Posponer 30 días" para clientes inactivos
- **P2** · Historial de copias aplicadas en panel sync
- **P2** · Alerta IRPF trimestre no pagado al abrir
- **P2** · Instalador `.dmg` iMac con electron-builder
- **P2** · Migrar Stripe a LIVE mode
- **P2** · Flujo CNMC Alias Registry (obligatorio Sep 2026) desde panel LabsMobile
- **P3** · WhatsApp Business API

## Reglas críticas
- **NO refactorizar** `v2.html` — usar `search_replace` siempre
- Avisar al usuario tras cambios UI: `Ctrl + Shift + R` o reinicio Electron
- Zero regresiones: correr tests Node en `/app/frontend/public/tests/`
- Prefijar rutas backend con `/api`
- Credenciales solo en `.env`
- **Twilio queda oculto pero el código permanece** — si se necesita reactivar, quitar `display:none` del `tabByoa`

## Files of reference
- `/app/frontend/public/v2.html` (monolito, no refactorizar)
- `/app/frontend/public/manual-usuari.html` (manual con guía LabsMobile única)
- `/app/backend/routes/sms_campaigns.py` (endpoints Twilio+LabsMobile · Twilio ya no se llama)
- `/app/commercial/build/obfuscate.js`

## Last session (Feb 2026)
- Retirado Twilio del UI: pestaña oculta, default = LabsMobile, pre-flight forzado
- Auto-cleanup one-time de credenciales Twilio (`caja.twilio.cleanup.done.v1`)
- Manual depurado: eliminada guía Twilio Alpha Sender completa + referencias dispersas
- Smoke test OK · provider migrado a labsmobile · 0 refs Twilio en manual
