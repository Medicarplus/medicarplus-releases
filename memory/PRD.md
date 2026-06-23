# Caja del Día – PRD

## Original problem statement (es)
> "ESTO ES LO QUE LLEVO HECHO, AYUDAME A ACABARLO" – PDF "Seguimiento de Proceso (3).pdf"

Aplicación tipo cuaderno de caja diaria de una autoescuela / gestoría de tráfico.
El usuario quería terminar una HTML SPA autocontenida en localStorage.

## Architecture decision
- Single-file HTML app served from `/app/frontend/public/caja_del_dia.html`
- React App.js redirects `/` → `/caja_del_dia.html`
- Data persistence: `localStorage` (key `caja.v1`, `{byDate: {YYYY-MM-DD: [...entries]}}`)
- No backend used (MongoDB / FastAPI untouched, default boilerplate)

## CSV format (programa de tráfico)
Encoding: Windows-1252 (auto-detect UTF-8 fallback)
Delimiter: `;`  Quotes: `"`  Decimal: `,`  Date: `dd/mm/yyyy`
Columns: FECHA;DNI;NOMBRE;APELLIDO1;APELLIDO2;NÚMERO;TIPO;GRUPO;IMPORTE;FP;COBRADO;TASA;FP
FP codes: E=Efectivo, T=Tarjeta, B=Bizum, X=Transferencia

## What's been implemented (2026-01)
- CSV import (robust quoted-CSV parser, encoding auto-detect, dedup vs previous imports)
- Manual entry: 3 tabs
  - Tráfico (Renovación / Expedición / Duplicado / Canje)
  - Privadas (Revisión privada / Certificado / Duplicado / Informe / Psicotécnico)
  - Debe/Haber libre (concepto libre, HABER suma / DEBE resta)
- Cierre del día: bruto, descuentos, tasas DGT, totales por forma de pago, Haber/Debe, saldo anterior arrastrado, TOTAL caja
- Resumen por concepto (agrupado)
- Histórico navegable (clic en fecha = ir, papelera = borrar día)
- Retorno (toggle): tacha la fila y la excluye del total. Reactivable.
- Editar/Eliminar entradas
- Navegación por días (←/→/Hoy/calendario)
- Export/Import JSON (backup)
- Print-friendly (oculta toolbar y muestra solo tabla + resumen)
- Robust number parsing: acepta "66,50", "66.50", "1.234,56", "1,234.56"

## Backlog / future
- P1: Importar automáticamente desde carpeta compartida (File System Access API)
- P2: Sincronización en la nube (multi-dispositivo)
- P2: Edición inline (sin prompts)
- P3: Gráficos de evolución mensual
- P3: Exportar a PDF directamente
