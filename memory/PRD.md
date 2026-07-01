# Caja del Día – PRD

## Original problem statement
Aplicación tipo cuaderno de caja diaria para autoescuela/gestoría de tráfico.
Ampliada para incluir segunda empresa: CEMPLA ESPORT (medicina deportiva).

## Architecture
- Single-file HTML app: `/app/frontend/public/caja_del_dia.html`
- React App.js redirects `/` → `/caja_del_dia.html`
- Data persistence: localStorage
  - `caja.v1` → datos empresa Trànsit
  - `caja.cempla.v1` → datos empresa CEMPLA ESPORT
  - `caja.company` → última empresa activa
- Backend endpoint: `/api/download-app` (force-download del HTML)
- No MongoDB usada (pura app cliente)

## Features implementadas

### Modo Trànsit (tráfico) 🚗
- Importación CSV/Excel del programa de tráfico (Win-1252, `;` delim)
- Manual entry: Tráfico / Privadas / Debe-Haber
- Chips rápidos Debe/Haber: IRPF, Mercadona, Devolució tasa, Honoraris, Foto, Ciclista
- Cierre día completo: bruto, dto, tasas DGT, formas de pago, HABER/DEBE, saldo anterior
- Retorno (tacha entrada), editar, eliminar
- Histórico navegable
- Modal de confirmación (no confirm() del navegador)

### Modo CEMPLA ESPORT (medicina deportiva) 🩺
- Selector top-right: 🚗 Trànsit / 🩺 CEMPLA ESPORT (azul)
- Datos separados totalmente
- Chips con precios auto: Recon C/Dte 40€, Recon C 40€, P.Esforç 77€, Ciclista 40€ (50/50/0), Futbol 36,50€, Bàsquet/Atletisme/Natació/Tennis/Pàdel/Muntanya/Triatló 40€
- "Escriure a mà" → panel editable con Esport, Preu, F.Brugulat%, Cempla%, Dr.Mellado%
- Reparto automático por defecto: 45/45/10 (Ciclista 50/50/0)
- Panel "Repartiment mes actual": Total, F.Brugulat, Cempla, Dr.Mellado, PER CEMPLA-SPORT
- Cierre del día simplificado (sin tráfico, sin tasas DGT)

### Comunes
- Copia de seguridad JSON (con nombre por empresa: COPIA-TRAFIC-... / COPIA-CEMPLA-...)
- Restaurar copia (sustituir o fusionar)
- Imprimir
- Descargar app (botón + endpoint backend)

## Deferred / Backlog
- P2: Recordatorio automático de copia (más de 15 días sin backup)
- P2: Búsqueda por nombre/DNI en histórico
- P3: Gráficos de evolución mensual
- P3: Sincronización en la nube multi-dispositivo
