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

## Changelog
- 2026-02-01: Llibreta rediseñada como libro Debe/Haber clásico (pergamino, Georgia serif). Selector empresa dentro modal. Balanç per comptes con saldos PGC. Fix crítico cascada 'Cannot set properties of null' (referencia a #btnDownloadApp inexistente que rompía handlers IA/Auditoría/Restaurar). Añadido commutador ES/CA con data-i18n. applyLang() protegido para no borrar hijos.

## Test Coverage
- iteration_1: bug detectado (Cannot set properties of null) → root cause: línia 781 `$('#btnDownloadApp').onclick` (elemento inexistente) → FIXED
- iteration_2: fixes validados, 0 pageerrors. Regressión detectada btnClearDay borrado por applyLang() → FIXED (data-i18n en span interno + guard `children.length===0`)
- Todos los botones del header con handler onclick asignado
- Llibreta con balance por cuenta y toggle empresa verificado en ambos idiomas
- Persistencia F5 verificada

## Known Limitations
- `showSaveFilePicker` (File System Access API) solo funciona en Chrome/Edge. Firefox/Safari usan `<a download>` fallback automático (ya implementado).
