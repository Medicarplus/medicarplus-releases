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
- 28-Oct-2026 · Vídeo demo regenerado con voz Fal.ai ElevenLabs v3 (`Liam`, español, stability 0.35 = tono dinámico/entusiasta). Script `generate_narration.py` migrado de OpenAI TTS a Fal.ai via Emergent Universal Key + integration-proxy (modo Universal Key, submit→poll→download). `SEG_DUR` recalibrado a las nuevas duraciones (00:11.8 / 01:14.8 / 02:16.2 / 03:14.5 / 04:15.6 / 05:11.9 / 06:7.2). Bug de sync corregido en `concat_audio`: la pista de silencio se generaba a 24 kHz mientras los segmentos salían a 44.1 kHz → al concatenar con `-c copy` el `.mp3` final declaraba 101 s pero contenía 147 s de audio desincronizado. Ahora silencio a 44.1 kHz/128 kbps mono, concat limpio. Vídeo final: 5.7 MB, 102.7 s, video+audio alineados.
- 28-Oct-2026 · Vídeo demo regenerado (`/app/frontend/public/demo/medicar_demo.mp4`, 5.4 MB, 95.5 s). Timing audio/vídeo sincronizado (preroll de 3.5 s recortado), modales abriéndose sin pantallas por detrás, Facturación anual + Auditoría con datos variados (3-4 personas con duplicados, no una sola con 14 revisiones).
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
