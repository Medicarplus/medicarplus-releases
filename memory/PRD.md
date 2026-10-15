# MediCar Plus · PRD

## Original problem statement
POS y app de gestión para autoescuelas y centros médicos (TRÀFIC + CEMPLA). Zero bugs en contabilidad, PDF/Excel exports, sync offline→cloud, integridad estricta de datos.

## Stack
- Frontend monolítico: `/app/frontend/public/v2.html` (~18.7k líneas) + manual (`manual-usuari.html`)
- Backend: FastAPI + MongoDB (`/app/backend/routes/*`)
- Desktop: Electron wrapper (`/app/commercial/electron/index.html` ofuscado)
- Integraciones: Stripe, LabsMobile SMS, OpenAI/Claude (Emergent LLM Key)

## Últimas sesiones

### Feb 2026 · Retirada Twilio + aislamiento 2 empresas + fix descuadre reserva
1. **Twilio retirado del UI**: display:none en tab, default LabsMobile forzado, auto-cleanup one-time credenciales
2. **Separación empresas en campañas SMS**: field `company` + filtro backend + frontend auto-scope. Campañas antiguas sin company se ven en ambas (compat).
3. **LabsMobile credenciales por empresa con herencia**: username/token compartidos por defecto, pero sobrescribibles por empresa. Sender SIEMPRE específico por empresa.
4. **5 capas de guardado LabsMobile**: autosave 500ms + blur + validate button + modal close + pre-flight rescue
5. **Fix handler ⚡ "Usar nombre del centro" LabsMobile** (antes no funcionaba)
6. **Banner LabsMobile reconoce config correctamente** (antes decía "SMS no configurados" aunque lo estaba)
7. **Guía LabsMobile completa en manual de usuario** (sin Twilio tras retirada)
8. **🐛 FIX descuadre -340€ "CAJA FÍSICA CON RESERVA + BANCO"**: 
   - Asientos manuales `caja_to_reserva`/`banco_to_reserva`/`reserva_to_caja` no actualizaban `caja.reserva.v1`
   - `computeTotals` ahora compensa cuando `_reservaSynced` no está presente
   - Modal "Reserva de cambio" marca sus asientos con `_reservaSynced:true` para evitar doble compensación
9. **Etiquetas renombradas**: "Saldo anterior caja + cambio" → "🟢 Caja física" + "💰 Reserva de cambio" + "Saldo total efectivo"
10. **TOTAL label explícito**: "(caja + reserva de cambio + banco)"

## Backlog pendiente
- **P1** · Export Excel (.xlsx) de "Honorarios y Gastos" (botón `#btnHonorarios`)
- **P1** · Vídeo demo 30s en landing
- **P2** · Export Excel Cuadre de Caja mensual
- **P2** · "Posponer 30 días" para clientes inactivos
- **P2** · Historial de copias aplicadas en panel sync
- **P2** · Alerta IRPF trimestre no pagado al abrir
- **P2** · Instalador `.dmg` iMac con electron-builder
- **P2** · Migrar Stripe a LIVE mode
- **P2** · Flujo CNMC Alias Registry (obligatorio Sep 2026)
- **P2** · Chequeo pre-envío de saldo LabsMobile (bloqueo si contactos > SMS disponibles)
- **P3** · WhatsApp Business API

## Reglas críticas
- **NO refactorizar** `v2.html` — usar `search_replace` siempre
- Avisar al usuario tras cambios UI: `Ctrl + Shift + R` o reiniciar Electron
- Zero regresiones: correr tests Node en `/app/frontend/public/tests/`
- Prefijar rutas backend con `/api`
- **Twilio queda oculto en UI** pero código permanece
- Backup/restore separado por empresa; auto-descubrimiento `caja.*` no excluidas

## Files of reference
- `/app/frontend/public/v2.html` (monolito, no refactorizar)
- `/app/frontend/public/manual-usuari.html`
- `/app/backend/routes/sms_campaigns.py`
- `/app/commercial/build/obfuscate.js` (regenerar tras cambios v2.html)
