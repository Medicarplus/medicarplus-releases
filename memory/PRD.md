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
- 2026-02-07: **Fase 7 completada** — Build script d'obfuscació JS a `/app/commercial/build/obfuscate.js` amb `javascript-obfuscator`. Regenera `commercial/electron/index.html` amb: string array base64 (MASTER_KEY + VERIFY_URL amagats de Ctrl+F), identifierNamesGenerator hexadecimal, selfDefending anti-tampering, splitStrings. JS creix 2.6x (154→398 KB) però la lògica és opaca. Testejat E2E: MASTER + JWT + servidor verify + app completa carrega sense errors. `BUILD_INSTRUCTIONS.md` actualitzat amb el nou pas 3.5.
- 2026-02-07: **Fase 8 completada** — Multi-client: modal "Configuració inicial" post-llicència, `CFG.company1.name` / `CFG.company2.name` a localStorage, botó ⚙️ al header. Eliminats tots els "CEMPLA C.B / CEMPLA ESPORT" hardcoded (14 llocs). Chips sense preus prefixats. Metges + splits F.Brugulat/Cempla/Dr.Mellado eliminats del formulari + panell d'ingressos.
- 2026-02-07: **Fase 9 (Auditoria comercial) completada** — Hardening seguretat + RGPD + UX centres mèdics:
  - **Backend:** eliminat fallback hardcoded `EMERGENT_LLM_KEY` (C7). Índexs MongoDB creats a l'startup (C3): licenses{install_id, id-unique, status+created_at}, license_requests{install_id+status, status+created_at}, audit_logs{target+timestamp}. Rate limiter global slowapi (300/min per IP). Nova col·lecció `audit_logs` amb totes les accions admin (generate/revoke/delete/export/approve). Endpoint `DELETE /api/licenses/{install_id}` (RGPD C6) i `GET /api/licenses/{install_id}/export` (RGPD C5). Camp `consent` obligatori + honeypot `website` al `POST /api/licenses/requests` (C4, I8).
  - **Frontend:** nova pàgina pública `/privacy` amb 9 seccions RGPD completes. Portal públic `/request-license` amb checkbox obligatori de consentiment (submit deshabilitat fins marcar) + camp honeypot invisible.
  - **v2.html:** nou botó **🧾 Arqueig** al header. Modal d'arqueig fi de dia amb comparativa "efectiu teòric vs físic" i alerta visual quadrat/sobra/falta (dades pràctiques que administratives fan cada dia).
  - Tests: 24/24 pytest passing + smoke E2E OK.

## Test Coverage
- iteration_1: bug detectado (Cannot set properties of null) → root cause: línia 781 `$('#btnDownloadApp').onclick` (elemento inexistente) → FIXED
- iteration_2: fixes validados, 0 pageerrors. Regressión detectada btnClearDay borrado por applyLang() → FIXED (data-i18n en span interno + guard `children.length===0`)
- Todos los botones del header con handler onclick asignado
- Llibreta con balance por cuenta y toggle empresa verificado en ambos idiomas
- Persistencia F5 verificada
- **License server**: 8/8 pytest tests passing (`backend/tests/test_licenses.py`) — generate/verify/revoke/perpetual/regenerate/list/detail/auth
- **License requests + Admin panel (iteration_5)**: 24/24 pytest + 25/25 E2E Playwright. Cobreix: 401 sense token, format Install ID validation, duplicate pending 409, mailer graceful fallback amb RESEND_API_KEY buida, revoke marca REVOCADA i desactiva botons, aprovació auto-copia JWT.
- **v2.html obfuscat (Fase 7)**: smoke test manual — MASTER key desbloqueja, JWT amb verificació online funciona, `plan`/`centre` guardats des del servidor, 0 pageerrors, 0 warnings.

## Roadmap
- **Follow-up**: quan tinguis el compte Resend a punt, omplir `RESEND_API_KEY` i `SENDER_EMAIL` al `.env` i l'aprovació enviarà emails automàticament sense canvis de codi
- **Follow-up**: quan tinguis un domini definitiu, substituir `VERIFY_URL` a v2.html (`/app/frontend/public/v2.html` és la font; re-executar `node /app/commercial/build/obfuscate.js` sincronitza `commercial/electron/index.html`) i re-empaquetar l'Electron
- **Follow-up post-build**: signatura digital del `.exe` amb certificat Sectigo/Comodo (~90€/any) per evitar avís SmartScreen a Windows
- **Backlog**: rate limiting a `/api/licenses/verify`, exportació CSV de llicències, dashboard de mètriques (verify_count per client), plantilla d'email personalitzable, auto-update amb `electron-updater`

## Known Limitations
- `showSaveFilePicker` (File System Access API) solo funciona en Chrome/Edge. Firefox/Safari usan `<a download>` fallback automático (ya implementado).
