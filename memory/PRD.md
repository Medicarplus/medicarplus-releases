# Caja del Día - PRD

## Original Problem Statement
Aplicació standalone (`caja_del_dia.html`) que substitueix una llibreta de comptabilitat de 40 anys, per gestoria amb dues empreses: CEMPLA C.B (tràfic DGT) i CEMPLA ESPORT (revisions mèdiques esportives). L'app s'obre offline en un únic fitxer HTML, tota la lògica és Vanilla JS + `localStorage`.

## Sections
1. **CEMPLA C.B (Tráfico)** - Renovaciones, Duplicados, Certificados, DEBE/HABER
2. **CEMPLA ESPORT** - Revisiones deportivas con splits 45-45-10 personalizables
3. **ESTADÍSTIQUES** - Tabla anual + mensual de autoescoles con import CSV
4. **📖 LLIBRETA (nueva)** - Llibro clásico DEBE/HABER + Balanç per comptes

## Key Features Implemented
- Import CSV/Excel con detección FP automática + auto-detect columna sin cabecera
- Chips rápidos con precios (C.Oficial 20€, Fotos 4€, Certificado 66,50€, Duplicado 25€, deportes 40€)
- Datáfono manual integrado en fila Tarjeta (input +botón ✓)
- Contabilidad doble entrada: HABER auto + DEBE auto (tarjeta/transf/bizum → BBVA)
- Separación CAJA FÍSICA / COMPTE BBVA en el resumen
- Auditoría por rango de fechas con detección de clientes repetidos y sospechosos
- Asesor IA (Gemini + Emergent LLM fallback) con contexto de auditoría automático
- Sistema anti-pérdida 5 capas: localStorage + 5 snapshots + auto-file 3s + auto-file 30min + auto-file al ocultar pestaña
- Restore ultra-tolerante (6 formatos JSON): sustituir o fusionar
- Estadísticas con vista anual/mensual + import CSV mensual con alias
- Backup pack: CB + Cempla + Datáfono + Stats en un solo JSON
- Vinculación de archivo persistente (IndexedDB) File System Access API
- Verificación post-escritura (nunca guarda vacío/corrupto)
- **📖 Llibreta clàssica DEBE/HABER**: Vista de doble columna estil llibre de comptabilitat tradicional (pergamí, Georgia serif, DEBE vermell / HABER verd) amb: filtres Dia/Setmana/Mes/Any, **selector d'empresa integrat** (CEMPLA C.B verd ↔ CEMPLA ESPORT blau), **Balanç per comptes** amb comptes PGC (570, 572, 705, 629, 475) i caixes finals Caixa + Bancs, impressió A4 amb balanç
- **🌐 Commutador d'idioma ES ↔ CA** al header amb sistema data-i18n (~35 strings traduïts: header, tabs, form labels, section titles, dropdowns, empty states). Preferència a `localStorage['caja.lang']`.

## Backend
- `/api/download-app` - descarga del HTML
- `/api/ai-ask` - endpoint IA con Gemini/Emergent LLM fallback + auditSummary
- **License server (Fase 4 · 2026-02-07)**:
  - `POST /api/licenses/generate` (admin) — HS256 JWT, durada configurable, plans (STD/PREMIUM/TRIAL/MASTER)
  - `POST /api/licenses/verify` (public) — valida JWT + install_id, marca `last_verified_at` i `verify_count`
  - `POST /api/licenses/revoke` (admin) — passa a `status=revoked`, guarda raó
  - `GET /api/licenses` + `GET /api/licenses/{install_id}` (admin)
  - Auth admin: capçalera `X-Admin-Token` = `LICENSE_ADMIN_TOKEN`
  - MongoDB collection: `licenses`
  - Compat total amb Master Key offline (`v2.html` continua funcionant sense servidor)
- **License requests + Admin panel (Fase 5 · 2026-02-07)**:
  - `POST /api/licenses/requests` (públic) — el client demana llicència des del portal
  - `GET /api/licenses/requests` (admin) — llista + comptador de pendents
  - `POST /api/licenses/requests/{id}/approve` (admin) — genera llicència + email opcional via Resend + retorna JWT
  - `POST /api/licenses/requests/{id}/reject` (admin) — marca com a rebutjada
  - Portal públic React a `/request-license` (sense preus, format Install ID validat client-side)
  - Panell admin React a `/admin` amb login per X-Admin-Token, stats (Total/Actives/Revocades/Expirades/**Pendents**), taula amb Copy JWT + Revoke, aprovació amb auto-copy JWT
  - Mailer opcional: `RESEND_API_KEY` buida ⇒ es genera la llicència igualment i l'admin l'envia manualment

## Changelog
- 2026-02-01: Llibreta rediseñada como libro Debe/Haber clásico (pergamino, Georgia serif). Selector empresa dentro modal. Balanç per comptes con saldos PGC. Fix crítico cascada 'Cannot set properties of null' (referencia a #btnDownloadApp inexistente que rompía handlers IA/Auditoría/Restaurar). Añadido commutador ES/CA con data-i18n. applyLang() protegido para no borrar hijos.
- 2026-02-07: **Fase 4 completada** — License server FastAPI + MongoDB con JWT. Nueva estructura `/app/backend/routes/` + `/app/backend/models/`. 8 tests pytest passing.
- 2026-02-07: **Fase 5 completada** — Admin panel + portal públic. Backend afegeix 4 endpoints (requests/approve/reject). React `/admin` (login gate + dashboard amb stats + taula amb Copy JWT/Revoke + tab de sol·licituds amb Approve/Reject) i `/request-license` (formulari públic). Resend mailer amb graceful fallback. 24/24 pytest OK + 25/25 E2E OK.
- 2026-02-07: **Fase 6 completada** — `v2.html` accepta 3 formats de clau (MASTER offline · JWT verificable online · MB-XXXX legacy). Nou input textarea (JWTs són llargs, no majúsculing automàtic). Activació JWT contacta `VERIFY_URL` (font de veritat) i degrada elegantment offline. Re-check periòdic cada 15 dies invalidat si el servidor diu revoked/expired. Botó "↻ Verificar ara" al modal d'info. Nou link "Demana-la aquí" al portal públic. Els 3 fitxers `/app/frontend/public/v2.html`, `/app/commercial/caja_del_dia_v2.html` i `/app/commercial/electron/index.html` sincronitzats (mateix MD5). Smoke tests E2E OK: MASTER + JWT + 3 casos de rebuig.

## Test Coverage
- iteration_1: bug detectado (Cannot set properties of null) → root cause: línia 781 `$('#btnDownloadApp').onclick` (elemento inexistente) → FIXED
- iteration_2: fixes validados, 0 pageerrors. Regressión detectada btnClearDay borrado por applyLang() → FIXED (data-i18n en span interno + guard `children.length===0`)
- Todos los botones del header con handler onclick asignado
- Llibreta con balance por cuenta y toggle empresa verificado en ambos idiomas
- Persistencia F5 verificada
- **License server**: 8/8 pytest tests passing (`backend/tests/test_licenses.py`) — generate/verify/revoke/perpetual/regenerate/list/detail/auth
- **License requests + Admin panel (iteration_5)**: 24/24 pytest + 25/25 E2E Playwright. Cobreix: 401 sense token, format Install ID validation, duplicate pending 409, mailer graceful fallback amb RESEND_API_KEY buida, revoke marca REVOCADA i desactiva botons, aprovació auto-copia JWT.

## Roadmap
- **Fase 7 (P2)**: Ofuscació JS de `v2.html` amb `javascript-obfuscator`
- **Follow-up**: quan tinguis el compte Resend a punt, omplir `RESEND_API_KEY` i `SENDER_EMAIL` al `.env` i l'aprovació enviarà emails automàticament sense canvis de codi
- **Follow-up**: quan tinguis un domini definitiu, substituir `VERIFY_URL` a v2.html (3 llocs: `/app/frontend/public/v2.html`, `/app/commercial/caja_del_dia_v2.html`, `/app/commercial/electron/index.html`) i re-empaquetar l'Electron

## Known Limitations
- `showSaveFilePicker` (File System Access API) solo funciona en Chrome/Edge. Firefox/Safari usan `<a download>` fallback automático (ya implementado).
