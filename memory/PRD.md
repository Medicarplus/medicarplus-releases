# MediCar Plus · PRD

## Original problem statement
POS y app de gestión para autoescuelas y centros médicos (TRÀFIC + CEMPLA). Zero bugs en contabilidad, PDF/Excel exports, sync offline→cloud (`_mergeSnapshots`), integridad estricta de datos. Monolito Vanilla JS en `v2.html` (~18.5k líneas) envuelto en Electron, backend FastAPI + MongoDB. Idioma del usuario: Español/Catalán.

## Stack
- Frontend monolítico: `/app/frontend/public/v2.html` + manual (`manual-usuari.html`) + landing (React).
- Backend: FastAPI + MongoDB (`/app/backend/routes/*`).
- Desktop: Electron wrapper → `/app/commercial/electron/index.html` (ofuscado desde `v2.html`).
- Integraciones: Stripe, Twilio, LabsMobile, OpenAI/Claude (Emergent LLM Key).

## What's implemented
- Doble contabilidad TRÀFIC + CEMPLA independientes
- Sync offline↔cloud (`_mergeSnapshots`) con tests de regresión
- SMS Campañas multi-proveedor (Twilio + LabsMobile + Mock)
- Auto-detector Twilio senders (`/api/sms/twilio/senders`)
- Validador LabsMobile credenciales + saldo (`/api/sms/labsmobile/validate`)
- Export PDF Honorarios, Cuadre, Libro Registro
- Panel admin, licencias con `_synthetic_master`, dispositivos
- Manual de usuario interactivo con buscador y 8 pestañas
- **[Feb 2026]** Guía LabsMobile paso a paso añadida al manual (sección 🔔 Avisos SMS)

## Backlog (prioridad)
- **P1** · Export Excel (.xlsx) de "Honorarios y Gastos" (botón `#btnHonorarios`)
- **P1** · Vídeo demo 30s en landing
- **P2** · Export Excel Cuadre de Caja mensual
- **P2** · "Posponer 30 días" para clientes inactivos
- **P2** · Historial de copias aplicadas en panel sync
- **P2** · Alerta IRPF trimestre no pagado al abrir
- **P2** · Instalador `.dmg` iMac con electron-builder
- **P2** · Migrar Stripe a LIVE mode
- **P2** · Selector de remitentes guardados (favoritos) LabsMobile + Twilio
- **P3** · WhatsApp Business API

## Reglas críticas
- **NO refactorizar** `v2.html` — usar `search_replace` siempre
- Avisar al usuario tras cambios UI: `Ctrl + Shift + R` o reinicio Electron
- Zero regresiones: correr tests Node en `/app/frontend/public/tests/` ante cambios de lógica/sync
- Prefijar rutas backend con `/api`
- Credenciales solo en `.env`

## Files of reference
- `/app/frontend/public/v2.html` (monolito, no refactorizar)
- `/app/frontend/public/manual-usuari.html` (manual con guía LabsMobile)
- `/app/backend/routes/sms_campaigns.py`
- `/app/commercial/build/obfuscate.js`

## Last session
- Añadida guía completa LabsMobile al manual de usuario (6 pasos + troubleshooting + comparativa Twilio) · Feb 2026
