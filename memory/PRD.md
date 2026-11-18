# MediCar Plus · Product Requirements (PRD)

## Original Problem Statement
Full-stack POS and management application for medical driver-license centers.
- Zero bugs in accounting logic and data persistence.
- Flawless offline-to-cloud device syncing.
- Strict Data Integrity.
- PDF generation.
- Electron desktop app auto-updated via electron-updater + GitHub Releases.

## Architecture
- Monolithic Vanilla JS frontend inside `/app/frontend/public/v2.html` (~20k lines).
- Electron wrapper in `/app/commercial/electron/`.
- FastAPI backend in `/app/backend/` + MongoDB.
- GitHub Actions workflow for Windows installer builds.
- Separate prototype lab at `/app/tramitacion-lab/` (NOT deployed with MediCar).

## Changelog
- **2026-11-18 (tarde v2) · Refinamiento Detector**:
  - ❌ Eliminados los botones inline `➕ Etiquetar`/`✏️ Editar` y mini-modal rápido (podían llevar a categorizar descuentos puntuales). La declaración de tarifas ocurre SOLO en Configuración → Precios, que es la fuente de verdad.
  - ✅ Banner actualizado: ahora tiene botón directo **⚙️ Configurar precios** que abre `openTariffsEditor` y texto más claro distinguiendo tarifa fija vs descuento puntual.
  - ✅ Mantenida la detección automática (⚠️ N precios detectados por fila + badge 🏷️ cuando matchea una regla declarada).
- **2026-11-18 (tarde) · Detector de tarifas**:
  - **Auto-detección de variantes** en `_trafBuildDetail`: calcula `variantCount` por (tipo+grupo) y marca ⚠️ las filas que pertenecen a un servicio con 2+ precios distintos.
  - **Banner inteligente** 🤖 arriba del desglose: "Hemos detectado X precios que podrían tener una tarifa especial". Solo aparece si realmente hay algo por etiquetar.
  - **Nueva columna ETIQUETA** con botón `➕ Etiquetar` (fila sin etiqueta) o `✏️ Editar` (fila etiquetada) · mini-modal con tipo/grupo/precio precargados que crea/edita/elimina la regla en `caja.tarifas.rules.v1` con 1 clic. Match insensible a tildes para no duplicar reglas.
  - **Plataforma 100% universal**: nunca hardcodea precios ni centros. Al importar su CSV, cualquier cliente ve sus propias combinaciones y las etiqueta en segundos.
- **2026-11-18 · Estadísticas Tráfico + Desglose**:
  - Nueva **matriz de carnets de Conducción** al final de Estadísticas → Tráfico (vista anual y mensual). Filas = Clase (B, C1, D…) · Columnas = Expedición / Renovación / Recuperación · cada una subdividida en Normal / Profesional. Fila/columna de totales + KPIs. Solo cuenta entradas del grupo Conducción. Mientras el CSV de GIC no incluya las columnas nuevas de clase+profesional, muestra placeholder (fichas antiguas inalteradas).
  - Nuevo **badge 🏷️ en Desglose profesional** (`_trafBuildDetail`/`_trafDetailBlockHtml`): cuando una entrada hace match con una regla de tarifa personalizada (`caja.tarifas.rules.v1`) y el nombre resultado difiere del tipo base, se muestra la etiqueta de la regla debajo del tipo (p.ej. "+70 años", "Nocturno"). Elimina la sensación de duplicados cuando hay precios legítimamente distintos por edad/convenio.
  - Añadida pre-validación tag↔package.json en `.github/workflows/release.yml` para evitar fallos silenciosos tipo v2.3.3.
- **2026-11-17 · CI/CD fix**: Bumped `commercial/electron/package.json` to **2.3.4**. Root cause of silent 1m 11s failure: package.json mismatch con tag.
- **2026-11-09 · Round 2 (after user feedback)**:
  - Modal Editar entrada: added **TIPO** dropdown (Renovación/Expedición/Canje/Duplicado/Prórroga/Recuperación/Revisión/Periódica/Inicial/Obtención) alongside Grupo and Concepto. Only for TRAF entries.
  - AI prompt: REMOVED hardcoded "66,50€ Expedición Conducción = Canje" default. The AI now reads EACH user's `caja.tarifas.rules.v1` from their own localStorage. If no rules exist, the AI is informed and is more cautious. No server-side assumptions.
- **2026-11-09 · Round 1**: 4 CSV/AI/UI bug fixes (bank transactions mis-classification, edit fields, AI pricing rules injection, Grupo column in detail modals).

## Pending backlog
- **P1**: Export "Honorarios y Gastos" to Excel (.xlsx).
- **P2**: Burn-in Spanish subtitles on MP4 demo video.
- **P2**: Excel export for monthly Cuadre de Caja.
- **P2**: "Posponer 30 días" for inactive-client warnings.
- **P2**: Alerta Trimestre IRPF.
- **P2**: iMac `.dmg` installer.
- **P2**: Migrate Stripe to LIVE mode.
- **P3**: WhatsApp Business API integration.

## Critical rules
- **NEVER refactor `v2.html`** — use search_replace only.
- Always run `node commercial/build/obfuscate.js` after any JS edit in `v2.html`.
- `/app/tramitacion-lab/` lives in parallel and must NOT be mixed with MediCar.
- NEVER hardcode a specific user's business rules in the app (e.g., "66,50€ = Canje"). Each client has their own `caja.tarifas.rules.v1` in localStorage.
