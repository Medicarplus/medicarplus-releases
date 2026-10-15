# MediCar Plus · PRD

## Original Problem Statement
POS + gestión integral para autoescuelas / centros médicos (TRÀFIC + CEMPLA). Zero bugs en contabilidad y persistencia. Doble entrada, PDFs, sync offline↔cloud, data integrity estricta. La "Reserva de Cambio" debe ser libremente editable sin asientos ocultos.

## Idioma
Usuario: Español (es).

## Core Rules
- `v2.html` monolítico. Nunca refactorizar. Siempre `search_replace` + `node commercial/build/obfuscate.js` después.
- "Saldo Inicial" es ESTRICTAMENTE LOCAL por PC. Nunca se sincroniza.
- Reserva de cambio: edición manual, sin asientos automáticos ocultos.
- Dashboard "Caja física (sin cajón)" / "Reserva de cambio" / "CAJA FÍSICA TOTAL" ⇒ **estado físico EN VIVO**, no cambia al navegar días pasados (Oct 2026).

## Implementado — últimos cambios
- 15-Oct-2026 · Fix dashboard: las 3 líneas de caja física ahora reflejan el estado físico actual en tiempo real (independientes del día visualizado). Compilado en `commercial/electron/index.html`.
- 15-Oct-2026 · Botón "🔍 Diagnóstico" en modal Cambio para desglose día-por-día.

## Roadmap
### P1
- Exportar "Honorarios y Gastos" a Excel (.xlsx).
- Vídeo demo de 30 s en landing.

### P2
- Excel Cuadre mensual.
- "Posponer 30 días" para avisos de clientes inactivos.
- Historial de copias aplicadas (fecha + remitente) en panel sync.
- Alerta trimestre IRPF no marcado como pagado.
- Instalador `.dmg` con electron-builder.
- Migrar Stripe a LIVE.

### P3
- WhatsApp Business API.

## Integraciones
- OpenAI/Claude vía Emergent LLM Key.
- Stripe (requiere clave de usuario).
- LabsMobile SMS (clave de usuario).

## Build
Siempre tras tocar `v2.html`: `node commercial/build/obfuscate.js`.
