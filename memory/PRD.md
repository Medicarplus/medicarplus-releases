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
- 28-Oct-2026 · Endpoint `/api/download-demo-video` añadido en `backend/server.py` (`FileResponse` con `Content-Disposition: attachment; filename="medicar-plus-demo.mp4"`). Descarga directa del MP4 para subir a LinkedIn.
- 28-Oct-2026 · Refinamientos narración demo: 00_intro ("Importa, **gestiona**, revisa"), 01_csv ("día **preparado**"), 06_outro reescrito ("**Con MediCar Plus** pasas menos tiempo...") para dar contexto español antes del brand → voz Liam consistente en todo el vídeo. 04_sms + 05_audit regenerados por deriva de tono. Vídeo final 6.2 MB · 101.3 s · timings sincronizados con márgenes +0.02-0.13 s por segmento.
- 28-Oct-2026 · Vídeo demo migrado a Fal.ai ElevenLabs v3 (voz **Liam**, español, stability 0.35 = dinámico/entusiasta). `generate_narration.py` reescrito con integration-proxy Universal Key (submit→poll→download) y filtro CLI por nombre de segmento. Bug sync corregido en `concat_audio`: silencio ahora a 44.1 kHz (antes 24 kHz → metadata rota en el `-c copy`).
- 28-Oct-2026 · Backup Folder Path real: preload Electron expone `webUtils.getPathForFile` → en `v2.html` tras guardar la copia se muestra la ruta OS real de la carpeta elegida y se persiste en `localStorage['caja.backup.lastDir']`. Fallback web mejorado ("la que has elegido en el diálogo del sistema"). Compilado en `commercial/electron/index.html`.
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
