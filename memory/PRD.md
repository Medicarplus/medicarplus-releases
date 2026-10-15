# MediCar Plus · PRD

## Original Problem Statement
Full-stack POS/management app for driving schools (TRÀFIC) and medical centers (CEMPLA).
Core principle: **ZERO bugs in accounting + perfect historical data integrity + flawless offline-to-cloud sync.**

## Architecture
- Monolith Vanilla JS (`/app/frontend/public/v2.html`, ~18.8k lines).
- FastAPI + MongoDB backend.
- Electron desktop (built via `commercial/build/obfuscate.js` → `commercial/electron/index.html`).
- Per-company independent data spaces (`trafic` / `cempla`).
- Multi-PC sync (push/pull snapshots + merge byDate idempotent).

## Reserva de Cambio · Arquitectura (Feb 2026, consolidada)
**Modelo día-a-día (FORWARD):**
- Saldo Inicial `si`: `{fecha, efectivo, banco, cambio, nota}` configurado al arrancar el programa (LOCAL por PC, no sincronizado).
- Traspasos dated: cada movimiento Caja↔Reserva o Banco↔Reserva se guarda como asiento `DH _internal` con `_transferDir` en `byDate[fecha]`.
- Reserva histórica al cierre del día X = `si.cambio + Σ(traspasos dated banco_to_reserva + caja_to_reserva − reserva_to_caja, con fecha ∈ [si.fecha, X])`.
- Reserva al INICIO del día X = Σ con fecha ∈ [si.fecha, X−1] (= cierre día anterior).
- Fechas < `si.fecha` → 0 €.
- Fallback (sin si configurado): fórmula hacia atrás (`now − laterNet`).

**Funciones:**
- `resCambioAtEndOfDate(date)` → fin del día `date`.
- `resCambioAtStartOfDate(date)` → inicio del día `date` (= fin del anterior).
- `reservaCambio()` → estado FÍSICO actual (denominaciones + bulk pendiente); solo para el modal.

**Beneficios:**
- Días pasados son INMUTABLES ante cambios en la reserva actual.
- Sync PC↔PC no "contamina" el histórico aunque `caja.reserva.v1` cambie por LWW.
- Siempre se puede explicar día a día: "el cambio sube/baja porque hay un asiento dated que mueve dinero DE/HACIA caja o banco".

## Changelog (reciente)
### 2026-10-15
- ✅ **FIX CRÍTICO reserva histórica**: `resCambioAtEndOfDate` ahora usa fórmula FORWARD basada en Saldo Inicial, no `reservaCambio() global − futuro`. Resuelve el bug donde 31/08/2026 mostraba 436,74 € (reserva actual) en vez de 344,74 € (saldo inicial).
- ✅ Nuevo `resCambioAtStartOfDate(date)` para el saldo anterior visualizado.
- ✅ `renderSaldoAnterior()` fijado para usar `resCambioAtStartOfDate(currentDate)`.
- ✅ Test automatizado (`/app/frontend/public/tests/test_reserva_historica_sync.js`) · 23/23 asserts OK incluyendo el caso real del usuario.
- ✅ Compilado al Electron (`commercial/electron/index.html`).

### Previo
- Twilio hidden; LabsMobile sole SMS provider (per-company Sender IDs).
- `_mergeSnapshots` idempotente, `_filterSnapshotByDay` para "Solo día".
- Doble empresa (TRÀFIC/CEMPLA) con datos aislados.

## P0 Pending
- [ ] Verificación por el usuario del fix 31/08/2026 → 344,74 € (requiere reinicio Electron en AMBOS PCs).

## P1 Backlog
- [ ] Export Honorarios y Gastos a Excel (.xlsx), botón `#btnHonorarios`.
- [ ] Vídeo demo 30 s en landing page.
- [ ] Reconciliación visual: si `reservaCambio()` (físico) ≠ `resCambioAtEndOfDate(hoy)` (calculado), avisar al usuario y proponer crear asiento de ajuste dated.

## P2 Backlog
- Excel export Cuadre de Caja mensual.
- Botón "Posponer 30 días" para avisos de cliente inactivo.
- Historial de copias aplicadas (fecha + remitente) en panel sync.
- Alerta trimestre IRPF pendiente al abrir la app.
- Instalador `.dmg` iMac via electron-builder.
- Migrar Stripe a LIVE mode.

## P3
- WhatsApp Business API.

## Credenciales de prueba
Ver `/app/memory/test_credentials.md`.
