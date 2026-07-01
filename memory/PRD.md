# Caja del Día - PRD

## Original Problem Statement
Aplicación standalone (`caja_del_dia.html`) que sustituye una libreta de contabilidad de 40 años para gestoría con dos negocios (CEMPLA C.B / Tráfico DGT + CEMPLA ESPORT / medicina deportiva).

## Sections
1. **CEMPLA C.B (Tráfico)** - Renovaciones, Duplicados, Certificados, DEBE/HABER
2. **CEMPLA ESPORT** - Revisiones deportivas con splits 45-45-10 personalizables
3. **ESTADÍSTIQUES** - Tabla anual + mensual de autoescoles con import CSV

## Key Features Implemented
- Import CSV/Excel con detección FP automática + auto-detect columna sin cabecera
- Chips rápidos con precios (C.Oficial 20€, Fotos 4€, Certificado 66,50€, Duplicado 25€, deportes 40€)
- Datáfono manual integrado en fila Tarjeta (input +botón ✓)
- Contabilidad doble entrada: HABER auto (todas las entradas) + DEBE auto (tarjeta/transf/bizum → BBVA)
- Separación CAJA FÍSICA / COMPTE BBVA en el resumen
- Auditoría por rango de fechas con detección de clientes repetidos y sospechosos (0€ sin compensación)
- Asesor IA (Gemini + Emergent fallback) con contexto de auditoría automático
- Sistema anti-pérdida 5 capas: localStorage + 5 snapshots + auto-file 3s + auto-file 30min + auto-file al ocultar pestaña
- Restore ultra-tolerante (6 formatos): sustituir o fusionar
- Estadísticas con vista anual/mensual + import CSV mensual con alias (ROSELL/VIC → ROSSELL/VIC, etc.)
- Backup pack: CB + Cempla + Datáfono + Stats en un solo JSON
- Vinculación de archivo persistente (IndexedDB)
- Verificación post-escritura (nunca guarda vacío/corrupto)
- **📖 Llibreta clàssica DEBE/HABER**: Vista de doble columna estil llibre de comptabilitat tradicional (paper de pergamí, fonts serif Georgia, DEBE vermell esquerra / HABER verd dreta) amb filtres per Dia/Setmana/Mes/Any i impressió A4. Cada operació genera un assentament comptable amb comptes PGC (570 Caixa, 572 Bancs, 705 Ingressos, 629 Despeses, 475 Tasa DGT). Verificació de quadrament DEBE=HABER automàtica.

## Changelog reciente
- 2026-02-01: Llibreta rediseñada como libro Debe/Haber clásico (2 columnas, fondo pergamino, tipografía Georgia serif). Fix "€ €" duplicado.

## Backend
- `/api/download-app` - descarga del HTML
- `/api/ai-ask` - endpoint IA con Gemini/Emergent fallback + auditSummary

## Test Coverage
- 13/13 pruebas byte-a-byte de save+restore superadas
- Auditoría detecta caso Juan Pérez (renovación día 5 + trámite 0€ día 12 = SOSPECHOSO)
- IA endpoint responde 200 con source=emergent-key
- All 27 UI buttons + functions verified
