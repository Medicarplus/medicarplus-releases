# MediCar Plus · PRD (Product Requirements Document)

## 2026-02-25 · Renombrado DEBE/HABER → INGRESO/GASTO + fix doble conteo HABER

**Problema reportado:** el panel "🎯 Resultado" del Informe Anual mostraba `HABER: +0,00 €` de forma persistente, generando confusión.

**A) Fix crítico: DOBLE CONTEO de HABER en Beneficio Neto (bug feb 2026)**
- **Root cause:** desde la fusión "HABER manual → byConcept" (feb 2026), los HABER pasaron a incluirse dentro de `byConcept`, pero la fórmula del panel Resultado y KPI cards seguía haciendo `ingresosBrutos = byConcept + haberTotal`, sumando HABER dos veces.
- **Impacto:** con miles de € de HABER manuales el Beneficio Neto quedaba inflado por ese mismo importe. Con 0 HABER simplemente confundía visualmente.
- **Fix:** eliminado `haberTotal` de la fórmula de KPI cards (`_ingresosBrutosKPI`) y del panel Resultado. Ahora `ingresosBrutos = Σ byConcept` (única fuente de verdad).
- Panel Resultado simplificado: **Ingresos − Gastos = Beneficio** (3 filas en vez de 4).

**B) UX: renombrado global DEBE/HABER → INGRESO/GASTO**
- El usuario pidió terminología no contable: "SI ES MUY LIO PONEMOS INGRESOS I GASTOS EN VEZ DE DEBE HABER".
- Cambios visibles (los valores internos `HABER`/`DEBE` en localStorage siguen igual para compatibilidad):
  - Pestaña "Debe / Haber" → **"Ingresos / Gastos"**
  - Select: "HABER (entra dinero)" → **"INGRESO (entra dinero)"**, "DEBE (sale dinero)" → **"GASTO (sale dinero)"**
  - Botón "+ Añadir Debe/Haber" → **"+ Añadir Ingreso/Gasto"**
  - Badge en libreta: `HABER` → **`INGRESO`**, `DEBE` → **`GASTO`** (mismos colores)
  - Sidebar diaria: "Ingresos manuales (HABER)" → **"Ingresos manuales"**
  - Panel Resultado: filas HABER + DEBE → **Ingresos + Gastos**
  - Subtítulo app: "Cierre diario · … · Debe / Haber" → **"… · Ingresos / Gastos"**
  - i18n `tab_dh` actualizado ES + CA

**C) Auditoría exhaustiva (83 invariantes verificados)**
- Añadidos 11 tests nuevos a `/app/frontend/public/tests/accounting_audit.js`:
  - TEST 15: bug doble conteo detectado y confirmado corregido
  - TEST 16: KPI cards ≡ Resumen Contable ≡ Panel Resultado (3 fuentes = mismo Beneficio)
  - TEST 17: Σ byMonthFacturacion == Σ byConcept (transitividad producción)
  - TEST 18: Σ byMonthGastos == Σ g.gastos (consistencia gastos)
  - TEST 19: HABER "Foto" fusiona con concepto Foto (NO crea fila nueva)
  - TEST 20: caso extremo · todo HABER (12 meses, sin TRAF/PRIV)
  - TEST 21: caso extremo · todo DEBE (año en pérdida absoluta)
  - TEST 22: retornos + traspasos + brutoIRPF + refund tasas ignorados
  - TEST 23: sync PC1↔PC2 · mismo payload → mismo Resultado
  - TEST 24: idempotencia · aggregar N veces == aggregar 1 vez
  - TEST 25: 10.000 entradas con decimales · error acumulado < 0,01€
- Resultado: **83/83 PASS · 14.163 entradas simuladas · 3 años (2024-2026)**

**D) Archivos modificados:**
- `/app/frontend/public/v2.html`: líneas 631, 701, 718, 719, 754, 3461, 3603 (sidebar CB), 7014-7023 (KPI cards), 7408-7422 (Panel Resultado)
- `/app/frontend/public/tests/accounting_audit.js`: +260 líneas de nuevos tests

## 2026-02-08 (parte 4) · Informe Anual: 2 KPIs nuevos + IRPF simplificado + fix cálculos

**A) IRPF Modelo 111 rehecho (solo pagos reales):**
- Antes: mostraba retenciones teóricas (Modelo 111) + pagos + diferencia con "pendiente por ingresar" — confuso.
- Ahora: **SOLO muestra lo que se ha PAGADO a Hacienda** (chip IRPF en DH DEBE). Cada pago trimestral se **reparte proporcionalmente entre trabajadores** según su retención en ese trimestre. Si un pago llega sin retenciones registradas → "(Pagos sin atribuir a trabajador)".
- Si no hay ningún pago → mensaje "Sin pagos IRPF a Hacienda registrados". Retenciones no pagadas no ensucian la vista.

**B) 2 KPI cards nuevos arriba: GASTOS TOTALES + BENEFICIO NETO:**
- Antes: solo 4 KPIs (Facturación, Entradas, Tasas DGT, Media). El usuario se quejaba de que Gastos estaba escondido abajo.
- Ahora: **6 KPIs para E1 (5 para E2)** — se ven de un vistazo Facturación, Entradas, [Tasas DGT], Media, **Gastos totales (rojo)**, **Beneficio neto (verde/rojo)**.

**C) BUG CRÍTICO fixed: cálculos contaminados de `grandTotals.neto`:**
- `computeTotals` resta DEBE de `t.neto` → `grandTotals.neto = ingresos - gastos` (mal etiquetado como "Facturación total").
- Antes las KPI cards y el gráfico mensual mostraban valores negativos cuando los gastos superaban los ingresos, engañando al usuario.
- **Fix**: creado `_totalServiciosKPI = Σ grandTotals.byConcept` + `_totalHaberKPI` + `_totalGastosKPI` como fuentes de verdad separadas. Facturación total ahora es SUMA PURA de servicios + HABER (sin restar DEBE).
- Añadido tracking `grandTotals.byMonthFacturacion` (mensual puro sin DEBE) y `grandTotals.byMonthGastos` (mensual solo DEBE).
- Tabla "Facturación mensual" renombrada a **"Facturación y gastos mensuales"** con 4 columnas: Facturación, Gastos, Beneficio, Entradas. Ahora muestra el neto mensual real.
- Porcentajes de "Facturación por concepto" ahora usan `_totalServiciosKPI` → siempre positivos y suman ~100%.

**Test verificado matemáticamente con datos: 2 renov + foto + HABER 50 + DEBE nómina 800 →**
- Facturación total = 266€ ✅ (200+50+16)
- Gastos = 800€ ✅
- Beneficio = -534€ ✅
- Porcentajes: Renov 92.6% + Foto 7.4% = 100% ✅
- 0 errores JS ✅


## 2026-02-08 (parte 3) · Cuadre de Caja editable a mano (overrides LOCALES)

**Nueva funcionalidad `openCuadreCaja()` (`frontend/public/v2.html`):**
- **Lápiz ✏️ en las 7 cifras del Cuadre**: SALDO ANTERIOR, INGRESOS, GASTOS, SALDO ACTUAL, CAJA FÍSICA, BANCO, SUMA CAJA+BANCO. Al pulsar aparece un `prompt()` con el valor actual pre-cargado.
- **Botón ↺** al lado del ✏️ (solo si hay override activo) → vuelve al valor calculado.
- **Valores editados** se muestran en **amarillo cursivo (#fbbf24 + italic)** para distinguirlos claramente del valor calculado.
- **SALDO ACTUAL y DIFERENCIA se recalculan** automáticamente usando los overrides si existen (fórmula: `saldoAnt + ingresos - gastos - (caja+banco)`).
- **Impresión** respeta los overrides y añade nota al pie: "✏️ Cifras marcadas: ajustadas manualmente en este PC".
- **Storage**: `caja.cuadre.overrides.v1` con estructura `{ comp: { cutoff: { field: value } } }`.

**Sincronización — LOCALES por PC:**
- Añadido prefijo `'caja.cuadre.'` a `SYNC_EXCLUDE_PREFIXES` (línea 251) y a `NON_SYNCABLE_PREFIXES` (línea 12322).
- Los ajustes manuales del gerente NO se envían al PC del trabajador y viceversa (confirmado explícitamente por el usuario).
- Cada PC guarda sus propios ajustes → coherente con la lógica de saldo inicial local.

**Test verificado (screenshot):**
- 7 lápices detectados correctamente.
- Override "999,50 €" en INGRESOS → muestra amarillo cursivo, SALDO ACTUAL pasa de 1700€ → 2699,50€, DIFERENCIA sale +999,50€ REVISAR (rojo). ✅
- `localStorage['caja.cuadre.overrides.v1']` guardado como `{trafic: {'2026-09-08': {ingresos: 999.5}}}` ✅


## 2026-02-08 (parte 2) · Novedades movidas a Configuración + Changelog v2.2.1 orientado al cliente

**Novedades ya no en la barra superior:**
- Botón `#btnWhatsNewMenu` **eliminado** de la barra superior (línea 561 → sustituido por comentario).
- Handler antiguo (`$('#btnWhatsNewMenu').onclick = ...`) convertido en `addEventListener` con optional chaining para no romper.

**Novedades ahora dentro de Configuración:**
- Nuevo bloque en `showConfigWizard()` (después del bloque Sync): sección naranja con icono 🎁, descripción y botón "Ver novedades" (`data-testid="cfg-open-novedades"`).
- Al pulsar → llama a `showWhatsNew(true)` (modo forzado).

**Changelog v2.2.1 (08/02/2026) añadido — orientado al cliente, sin tecnicismos:**
- Cuadre de Caja con pestañas + selector de fecha exacto (destaca los 3 puntos que pidió el usuario)
- Aviso claro de que el Cuadre NO se comparte entre PCs y el Saldo Inicial es siempre local
- Imprimir Cuadre exporta solo la pestaña activa
- Novedades trasladadas a Configuración
- Selector de mes en Informe Anual
- Mejoras IRPF (auto-rellenar trabajadores, columnas SS retiradas, chip IRPF automático)
- Empresa 2 sin Tasas
- Chips deportivos en español
- Sync "Solo un día" por defecto
- Impresiones revisadas
- Debe/Haber limpiado
- Detección Canje automática (66,50€)
- Total: 14 highlights, todos con emoji y frase corta legible.

**Versión bumpeada** a 2.2.1 en el fallback (`_currentAppVersion`).


## 2026-02-08 · Cuadre de Caja: Pestañas por empresa + Selector de fecha exacto

**Cambios en `openCuadreCaja()` (`frontend/public/v2.html`):**
- **Selector `<input type="date">`** (antes `type="month"`): el usuario elige un día concreto y el rango es del **día 1 del mes** hasta el **día seleccionado** (inclusive). `max` limitado a hoy.
- **Pestañas AutoEscola / CEMPLA** (data-testid `cc-tab-e1` / `cc-tab-e2`) — solo aparecen si `CFG.company2.name` está definido. Cada pestaña muestra su empresa **totalmente AISLADA**: SALDO ANTERIOR, INGRESOS, GASTOS, SALDO ACTUAL, CAJA FÍSICA + BANCO y DIFERENCIA propios (nunca se mezclan cifras).
- **No hay totales globales** (antes había SALDO ANTERIOR global y SALDO ACTUAL global que sumaba ambas empresas). Ahora cada pestaña es independiente por decisión de negocio del usuario.
- **Impresión** exporta SOLO la pestaña activa (título incluye nombre de empresa + rango exacto).
- **Sync**: el modal solo LEE `localStorage`, nunca escribe. `caja.saldoInicial.*` sigue en `SYNC_EXCLUDE_PREFIXES` (línea 251) y `NON_SYNCABLE_PREFIXES` (línea 12291), por lo que el saldo anterior mostrado es siempre el LOCAL de cada PC — nunca el del PC emisor de una copia (confirmado explícitamente por el usuario en msg #568).
- Test verificado con screenshots: pestañas cambian de color, cifras se aíslan, fecha 05/02/2026 rinde "DEL 01/02/2026 AL 05/02/2026". ✅


## 2026-02-04 (parte 5) · Selector mensual en Informe Anual + Revisión prints

**Selector mensual añadido en Informe Anual:**
- Nuevo `<select id="arMonth" data-testid="ar-month">` junto al selector de año: opción "Año completo" (default) + 12 meses.
- Firma actualizada: `_buildAnnualReport(year, monthFilterIdx = -1)`.
- Filtro aplicado a nivel de día (`d` en el forEach): si `_monthSuffix` está definido, solo procesa días con prefijo `YYYY-MM`.
- Título dinámico: `Informe anual · 2026` cuando es año completo; `Informe mensual · Agosto 2026` cuando se filtra.
- Test verificado: título cambia correctamente entre año/mes, función se ejecuta sin errores. ✅

**Revisión rápida de prints de estadísticas:**
- **Estadísticas Tráfico** (`openTraficStats`): `@page A4 landscape · margin 10mm` + `page-break-inside:avoid` en tablas. ✅
- **Estadísticas anuales** (`openAnnualReport`): `printVisibleElement` + `@page A4 landscape · margin 6mm`. Modal 900px+ ancho, encaja en landscape. ✅
- **Cuadre de Caja**: `@page A4 landscape · margin 12mm`. Tablas compactas. ✅
- **Estadísticas Empresa 2**: `@page A4 landscape · margin 8mm`. KPIs + tabla mes × tipo. ✅
- **Gastos y Honorarios**: `@page A4 portrait · margin 8mm`. Tablas estrechas por concepto. ✅
- **Gráficas chart**: `printVisibleElement` con extraCss `@page A4 landscape · margin 6mm`. WYSIWYG. ✅
- Los prints principales tienen la configuración correcta. Una revisión visual completa in-app con datos reales del cliente puede requerir ajustes puntuales caso por caso.

Archivo tocado: `frontend/public/v2.html`.



## 2026-02-04 (parte 4) · Cuadre por empresa + Canje 66,50€ + Novedades reubicado

**Cuadre de Caja mejorado:**
- Cada bloque de empresa muestra ahora su **mini-saldo aislado**: `Saldo ant. X → Saldo actual Y` calculado solo con datos de esa empresa (nunca se mezcla con la otra). Los totales globales (SALDO ANTERIOR / SALDO ACTUAL) siguen siendo la suma de ambas.
- Test verificado: E1 saldoAnt=6000, ingresos=194, gastos=200, caja=1194, banc=4800 · E2 saldoAnt=2500, ingresos=50, gastos=0, caja=550, banc=2000. Cero cruces. ✅

**Detección "Canje" automática (virtual, no muta datos):**
- Nueva función `window._effectiveTipo(e)`: devuelve `'Canje'` si `kind==='TRAF' && tipo empieza por 'Expedición' && grupo contiene 'Conducción' && importe===66,50`. En cualquier otro caso devuelve `e.tipo`.
- Aplicada en las 3 agregaciones de stats por tipo (líneas 2281, 2319, 2397). Ahora Canje aparece separado de Expedición en las estadísticas anuales.
- Test verificado: 4/4 casos correctos (positivo + 3 negativos por importe/grupo/tipo distinto). ✅
- También ampliado `_normalizeTipo` para reconocer 'canj' y 'canv' (catalán).

**Novedades reubicada:**
- Botón `🎁 Novedades` movido del menú Contabilidad a la **barra superior** (al lado de ⚙️ Configuración), con estilo naranja destacado.
- Contenido de v2.2.0 actualizado con 11 highlights de todo lo hecho hoy (Cuadre, IRPF Modelo 111, chip IRPF dinámico, Empresa 2 sin tasas, impresión Empresa 2, chips deportivos ES, sync por defecto solo día, chips DH limpiados).

Archivo tocado: `frontend/public/v2.html`.



## 2026-02-04 (parte 3) · Nueva sección "🧮 Cuadre de Caja" (reconciliación mensual multi-empresa)
- Botón nuevo en **Contabilidad → 🧮 Cuadre de Caja** que abre un modal tipo hoja de Excel.
- **Estructura del modal**:
  - Selector de mes (`type=month`) · Botón imprimir · Cierre X
  - Título: `MES DE AGOSTO 2026 (hasta 15/08)` (muestra cutoff)
  - `SALDO ANTERIOR` = cierre del mes previo (caja + banco de ambas empresas al último día del mes anterior + saldo inicial aplicable)
  - Bloque por empresa: `📥 INGRESOS EMPRESA X` (clicable → desglose Tráfico/Revisiones/Otros/DH-Haber) + `📤 GASTOS EMPRESA X` (clicable → desglose agrupado por concepto normalizado: Nómina, Honoraris, Faena, IRPF, Gasto...)
  - `SALDO ACTUAL` = SALDO ANTERIOR + Σ(INGRESOS − GASTOS) por empresa
  - Tabla `💰 CAJA + BANCO real` por empresa (Caja C.B., Caja S.L., BBVA C.B., BBVA S.L.) + `SUMA CAJA + BANCO`
  - Banner de `DIFERENCIA` (verde si `|dif|<0,01€ = ✓ TODO CUADRA`, rojo si hay descuadre)
- **Cutoff inclusivo**: si estamos a 28/08 y miro agosto → suma del 1 al 28/08 (inclusive el propio día 28). Si el mes es pasado, usa fin de mes.
- **Filtros contables aplicados**: excluye `_hnBruto`, `_internal`, `_tasaRefund`, `retorno:true`. Cuenta tasas DGT en ingresos de Empresa 1. Aplica reclasificación datáfono (T→X). Suma internalCaja/internalBanco de los traspasos.
- **Botón imprimir**: usa `printHtml()` con landscape A4, todos los datos en 1-2 páginas, sin cortes.
- Test verificado: saldoAnt 6100€ + ingresos 294,15€ − gastos 150€ = 6244,15€ = caja 1394,15€ + banco 4850€. Diferencia 0€. ✅
- Archivo tocado: `frontend/public/v2.html`.



## 2026-02-04 (parte 2) · Retiradas columnas NET S.S. y TOTAL FINAL de la tabla IRPF
- Tabla IRPF pasa de 10 columnas a 8: `NOM | CERT | €/CERT | BRUT | S.S. | TOTAL | IRPF % | NET | 🗑`.
- Retirado el input `netSS` de la fila y su lógica de habilitar/deshabilitar según S.S.
- Retirada la última columna `TOTAL FINAL` (era NET + NET S.S.).
- Fila de TOTALES MES actualizada: pasa de 9 celdas de totales a 5 (brut, ss, total, irpf, net).
- El objeto `irpfCalc` sigue devolviendo `netSS` y `totalFinal` internamente por compatibilidad (datos antiguos no se pierden).
- Motivo: campo no estándar en nómina española que confundía más que aportaba. Los 4 conceptos que sí importan (BRUT → S.S. → IRPF → NET) siguen bien visibles.
- Archivo tocado: `frontend/public/v2.html`.



## 2026-02-04 · Sync "Solo un día" ahora es el radio por defecto
- **Enviar copia al otro ordenador (Manual)** y **Envío admin a licencia**: por defecto se marca `📅 SOLO UN DÍA` (antes `📋 COPIA TOTAL`).
- El wrap del selector de fecha aparece visible al abrir el modal (`display:block`) para que el usuario elija el día directamente.
- Los estilos de los labels se han invertido: `SOLO UN DÍA` con color/borde de énfasis, `COPIA TOTAL` gris hasta que se seleccione.
- Aplica tanto al panel de sincronización manual entre PCs como al panel admin de envío por licencia.
- Verificado en preview: `Default sync scope: DAY checked`. ✅
- Archivo tocado: `frontend/public/v2.html` (función `_scopeHtml`).



## 2026-02-03 (parte 7) · Simplificación: eliminado chip BRUTO · IRPF section = fuente única

**Decisión de UX del usuario**: dado que el BRUTO no afecta caja/banco/asentamientos, el chip en Debe/Haber sobra. Todo lo de IRPF va DIRECTO en la sección IRPF.

**Cambios:**
- **Retirado** el chip `💼 Honoraris BRUTO (IRPF)` de Debe/Haber. Debe/Haber ahora es más limpio (8 chips).
- **Retirado** el estado temporal `window._pendingBruto` y su lógica en `btnAddDH` (código muerto).
- **Retirada** la variante A de auto-sincronización de BRUT. El BRUT vuelve a ser 100% editable manual en la sección IRPF (como un simple input, con soporte de cert × certPrice si el usuario lo usa).
- **`_getHonorariosWorkersOfMonth`** ahora agrupa por pagos NETOS (Nómina/Honoraris/Faena) del mes, no por brutos. Esto sigue auto-poblando la lista de trabajadores en IRPF section (útil: si has pagado a alguien, aparece automáticamente en IRPF con IRPF DESACTIVADO por defecto).
- **`_getLinkedHonorariosForWorker`** ahora devuelve pagos NETOS del mes (solo informativo, badge 🔔 en la fila IRPF).
- **Badge en fila IRPF**: `🔔 3 pagos neto · 1700€` (referencia visual de lo pagado). No auto-rellena BRUT.
- **Filtros `_hnBruto`** en gastos/ledger/informe se conservan por compatibilidad hacia atrás (entradas antiguas con el flag no se cuentan doblemente).

**Test integral verificado:**
- Nómina Pep 1700€ (neto) → workers list: Pep 1700€ ✅ · linked: 1 pago 1700€ ✅ · caja/banco: byFp.X=-1700 ✅ · gastos total: 1700 ✅
- Sin chip BRUTO ni flag `_hnBruto` en flujo nuevo. Existing legacy entries siguen filtrándose bien.

**Flow definitivo simplificado:**
1. Vas a Debe/Haber → apuntas pagos reales (nómina/honorario/gasto/IRPF/…) → afecta caja/banco.
2. Vas a 📋 IRPF → seleccionas trabajador ya listado (o añades nuevo) → editas BRUT y S.S. → IRPF calcula solo.
3. Cada sección tiene una lógica clara y no se solapan.

Archivo tocado: `frontend/public/v2.html`.



## 2026-02-03 (parte 6) · Auditoría completa: BRUTO nunca aparece donde no debe + unificación Nómina/Honorarios

**Auditoría exhaustiva del programa: BRUTO no cuenta en NADA que sea contable/caja/banco.**

Se corrigieron **7 lugares** que aún contaban entradas `_hnBruto:true`:
1. `renderByConcept` (agrupación por concepto del día) — añadido filtro `_hnBruto`.
2. `computeGastos` (Empresa 2 stats por año/tipo) — añadido filtro.
3. Segundo `computeGastos` (idem en otra ruta de agregación) — añadido filtro.
4. Ledger contable **trafic** (asentamientos "Libreta") — filtro al inicio del `arr.forEach`.
5. Ledger contable **esport** (asentamientos CEMPLA) — filtro al inicio.
6. Informe anual · `grandTotals.gastos` — filtro al inicio del `list.forEach`.
7. Panel Honorarios · Pagos a trabajadores (`_hn_show`) — filtro antes de `_isHonorarioLikeEntry`.
8. Stats admin duplicados (`dhCount`) — filtro añadido.

**Test integral verificado** con datos combinados en el mismo día:
- 100€ tráfico normal + 94,15€ tasa DGT
- 2000€ Honoraris BRUTO Pep (_hnBruto:true)
- 1600€ Nómina Pep (neto)

Resultados: `totalsDebe=1600`, `byFp.X=-1600` (solo neto sale de banco), `byFp.E=100` (tráfico), `totalsBruto=100` (solo facturación), `hnBrutoTotal=2000` (informativo). El bruto NO aparece en gastos, ledger, honorarios ni en byFp. ✅

**Unificación chips Nómina/Honorarios:**
- El chip `💼 Nómina` se ha fusionado con `💼 Honoraris a pagar (neto)`.
- Chip nuevo unificado: `💼 Pago nómina/honorario (neto)` con `data-c="Nómina"` (Nómina matches el regex `_hnMatchKeyword` y sigue apareciendo en la sección IRPF/Honorarios). Cubre tanto empleados (nómina) como profesionales (honorario).
- Tooltip actualizado con ejemplo: "bruto 2000€, IRPF 15% (300€) → aquí apuntas 1700€ netos".

Archivos tocados: `frontend/public/v2.html`.



## 2026-02-03 (parte 5) · Auto-Vincular BRUTO desde Debe/Haber a sección IRPF

**Feature completada:**
- Cuando se apunta un `💼 Honoraris BRUTO (IRPF)` en Debe/Haber de un trabajador que YA está en la sección 📋 IRPF con **IRPF activo**, el campo BRUT de ese trabajador para ese mes se auto-sincroniza con la suma de sus brutos en DH.
- El BRUT queda `readonly` con badge visual "🔗 BRUT sincronizado" púrpura (border #7c3aed, bg #ede9fe) y tooltip que indica "🔗 Sincronizado automáticamente con Debe/Haber · N entradas brutas · X€".
- Si el trabajador está inactivo o no tiene brutos en DH, el BRUT sigue siendo manual (comportamiento anterior).
- Multi-entrada: si añades varios brutos del mismo trabajador en el mismo mes, la suma se actualiza sola.
- Test funcional verificado: 2 brutos de Pep (600€+400€=1000€) → BRUT=1000€ auto, IRPF=150€ (15%), NET=850€. Cero clics manuales.
- Prioridad de fuentes de BRUT:
  1. Auto DH (si hay brutos y trabajador activo) — máxima prioridad
  2. cert × certPrice (auto local dentro de la fila IRPF)
  3. Manual (usuario escribe)
- El botón "📌 Usar como BRUT" ya no aparece cuando el bruto se auto-sincroniza (redundante).

Archivo tocado: `frontend/public/v2.html`.



## 2026-02-03 (parte 4) · Honorarios BRUTO vs NETO + IRPF chip destacado + IRPF Modelo 111 en Informe Anual + Impresión Empresa 2

**Corrección conceptual Informe Anual · IRPF Modelo 111:**
- **Retirado** el "Resumen trimestral (IRPF)" incorrecto que calculaba 15% de la facturación de la empresa (SL/CB paga IS, autónomo tributa por beneficio neto — no un % plano sobre bruto).
- **Añadido** un panel "📋 IRPF Modelo 111 · Retenciones a trabajadores" que muestra desglose Trabajador × Trimestre × Total año, sólo trabajadores con IRPF activo. Se calcula desde la sección 📋 IRPF.
- **Añadido** cotejo "Ingresado a Hacienda (Debe/Haber)": suma pagos DH con flag `_irpfPayment` por trimestre + diferencia con lo retenido teóricamente.
- KPI "TASAS DGT" ocultada en Informe Anual cuando la empresa activa es Empresa 2 (cempla), ya que no tiene tasas.

**Impresión Empresa 2 stats (bug crítico):**
- Botón "🖨️ Imprimir" en `openStatsEmpresa2` no hacía nada (usaba `window.open` bloqueado por Electron).
- Migrado a `printHtml()` con landscape A4, KPIs (TOTAL REVISIONES, TOTAL AÑO, MEDIA MENSUAL, TICKET MEDIO), tabla completa Tipo × Mes, footer con Mejor Mes. Sin cortes.

**Honorarios BRUTO vs NETO (nueva distinción por flag `_hnBruto:true`):**
- **Nuevo chip** `💼 Honoraris BRUTO (IRPF)` (gradient púrpura #7c3aed→#a855f7): crea entrada con `_hnBruto:true`. **NO afecta caja/banco**. Sólo se detecta en la sección 📋 IRPF para calcular el IRPF Modelo 111.
- **Chip existente renombrado** a `💼 Honoraris a pagar (neto)` (gradient azul): entrada estándar que sí afecta caja/banco (dinero real que sale al trabajador después de retención).
- **Chip IRPF actualizado** a `💸 IRPF (pago a Hacienda)` (gradient rojo #dc2626→#f87171 destacado): sólo para el pago trimestral a Hacienda. Se detecta como `_irpfPayment` y marca el trimestre pagado.
- Flag técnico `_pendingBruto` en window: se activa al clicar el chip bruto, tinta el input importe púrpura, y se aplica al añadir. Se resetea automáticamente después de guardar.
- `computeTotals`: skip completo de entradas `_hnBruto` (nuevos contadores `hnBrutoCount`, `hnBrutoTotal` sólo informativos).
- `_getLinkedHonorariosForWorker` / `_getHonorariosWorkersOfMonth`: filtran a `_hnBruto === true` únicamente (solo brutos alimentan IRPF).
- `_cleanWorkerName` extendido: reconoce prefijos "Honoraris bruto", "Nómina bruto", "Sueldo bruto", "bruto" solo.
- Badge visual "💼 BRUTO IRPF" (color púrpura) en la fila de la entrada del día. FP oculto porque no aplica.

**Chips deportivos Empresa 2 traducidos al castellano** (data-label-es/data-label-ca):
- Recon. C/Dte→Recon. C/Dto · P.Esforç→P.Esfuerzo · Futbol→Fútbol · Bàsquet→Baloncesto · Atletisme→Atletismo · Natació→Natación · Tennis→Tenis · Pàdel→Pádel · Muntanya→Montaña · Triatló→Triatlón · Submarinisme→Submarinismo · Handbol→Balonmano · Patinatge→Patinaje · Escriure a mà→Escribir a mano
- Hook en `applyLang()` que actualiza automáticamente todos los `[data-label-ca][data-label-es]` al cambiar idioma.

**Chip antiguo "Devolució tasa DGT" eliminado** (era duplicado del nuevo dinámico `↩ Devolución tasa DGT` con modal).

**Testing verificado con datos simulados:**
- Bruto 600€ Pep + Neto 510€ Pep: `totalsDebe=510`, `totalsByFpX=-510`, `totalsHnBrutoTotal=600`. Caja/banco solo afectados por el neto. ✅
- `_getHonorariosWorkersOfMonth` devuelve `PEP BRUGULAT BORRAS · 600€` (solo bruto). ✅
- Impresión Empresa 2: función usa `printHtml` con landscape, KPIs, sin `window.open`. ✅
- Chips deportivos ES: Fútbol/Baloncesto/Balonmano/Escribir a mano correcto. ✅
- Auto-mark quarter IRPF: detecta 5 formatos ("Q1 2026","T2","Trimestre 3","4T","Hacienda Q1"), descarta "IRPF Pep Brugulat" y "Nomina Pep". ✅

Archivos tocados: `frontend/public/v2.html`.



## 2026-02-03 (parte 3) · IRPF ↔ Debe/Haber vínculo bidireccional
**Modelo aclarado por el usuario:**
- El chip IRPF de Debe/Haber es SOLO para pagos trimestrales a Hacienda (efectivo→banco→Hacienda o transferencia bancaria directa). Nunca por trabajador.
- La tabla IRPF de la sección es solo la CALCULADORA teórica de retenciones. Lo que cuenta contablemente (y en estadísticas) es lo apuntado en Debe/Haber.

**Implementado:**
- Nuevas funciones helper en v2.html: `_normalizeWorkerKey`, `_detectIrpfQuarterPayment`, `_autoMarkIrpfQuarterFromEntry`, `_getLinkedHonorariosForWorker`, `_getHonorariosWorkersOfMonth`.
- **Detección trimestral automática**: al añadir un DH DEBE con concepto tipo "IRPF Q1 2026" / "IRPF T2" / "IRPF Trimestre 3 2025" / "IRPF 4T" / "IRPF Hacienda Q1" → auto-marca el trimestre como pagado en la sección IRPF (con toast confirmando) y guarda `_irpfPayment: 'YYYY-QN'` + `_irpfComp` en la entrada. Idempotente (no reprocesa entradas ya marcadas). Formatos soportados: Q1-Q4, T1-T4, 1T-4T, Trimestre N, ordinales (primer/segundo/tercer/cuarto). Año explícito (20XX) o actual.
- **Auto-población de trabajadores en la tabla IRPF**: al abrir la sección IRPF de un mes, se listan automáticamente todos los trabajadores con honorarios (Nómina/Honoraris/Faena/Sueldo/Salario) DEBE en ese mes, con toggle `active:false` por defecto. Los trabajadores ya añadidos manualmente antes de esta feature quedan `active:true` (retro-compat).
- **Toggle "IRPF activo" por trabajador**: si activo → se calcula IRPF y suma al trimestre. Si inactivo → aparece en la lista greyed out sin cálculo, no cuenta en totales. Cada trabajador independiente. El % IRPF sigue siendo por empresa (input general).
- **Badge 🔔 en cada fila**: muestra `N entradas · X€` de honorarios enlazados del mes. Al pulsar abre popup con detalle (fecha, concepto, importe, FP). No auto-rellena BRUT.
- **Botón "📌 Usar como BRUT"** (visible solo si activo y hay honorarios enlazados): copia el total de honorarios del mes al campo BRUT del trabajador con un clic. Deshabilita cert/certPrice auto.
- **Nuevo panel "📊 IRPF realmente pagado a Hacienda · Año YYYY"** en la sección IRPF: tabla con todos los pagos DH marcados con flag `_irpfPayment` del año actual (fecha, trimestre, importe, FP, concepto) + total YTD. Este es el valor que cuenta contablemente / en estadísticas.
- **Botón "Marcar como ingresado" retirado**: ya no es necesario porque el usuario siempre apunta el ingreso desde el chip IRPF de Debe/Haber y se marca automáticamente. Se sustituye por un aviso informativo verde. El botón "↺ Revertir" se conserva para cambiar de opinión.
- **Chips Debe/Haber Empresa 1 modificados**: eliminados "Mercadona / material" (DEBE) y "Ciclista" (HABER) en tarea anterior.
- **Datalist workers**: añadido bloque de sugerencias fijas para el chip IRPF con Q1..Q4 del año actual y anterior (facilita apuntar "IRPF Q1 2026" con autocompletado).
- Testing: verificado con datos simulados en Chromium — auto-mark quarter=true, agrupación de workers correcta, detección de 5 formatos trimestrales pasa OK y `IRPF Pep Brugulat` correctamente descartado como no-trimestral.

Archivo tocado: `frontend/public/v2.html`.



## 2026-02-03 (parte 2) · Chips Debe/Haber + Verificación separación de empresas
- **Chips eliminados** del panel Debe/Haber (Empresa 1): `Mercadona / material` (DEBE) y `Ciclista` (HABER). Los chips restantes son: IRPF, Devolució tasa DGT, 💼 Honoraris, 💼 Nómina, 💼 Faena externa, 🧾 GASTO, ↩ Devolución (dinámico según empresa), 🔁 Ingreso metálico, 🏦 Retirada del banco, Foto.
- **Verificación separación estricta Empresa 1 ↔ Empresa 2** (todas las claves localStorage confirmadas independientes):
  - Entradas: `caja.v1` vs `caja.cempla.v1`
  - Datáfono: `caja.datafono` vs `caja.cempla.datafono`
  - Reserva cambio: `caja.reserva.v1` vs `caja.cempla.reserva.v1`
  - Saldo inicial: `caja.saldoInicial.trafic.v1` vs `caja.saldoInicial.cempla.v1`
  - IRPF: `caja.irpf.v1` único archivo pero estructura interna `{trafic:{...}, cempla:{...}}` seleccionada por `irpfComp`
  - Stats autoescuelas: sólo aplica a Empresa 1 (Marc Brugulat / CEMPLA CB); Empresa 2 tiene su propia ventana `openStatsEmpresa2` que lee de `caja.cempla.v1`
- **Aclaración chip IRPF ↔ sección 📋 IRPF**: NO están vinculados. El chip IRPF del Debe/Haber genera un simple gasto DEBE en el día (útil para el pago trimestral a Hacienda). La sección 📋 IRPF (Contabilidad → IRPF) es un cuaderno independiente de retenciones trimestrales por trabajador que se rellena manualmente. Recomendación al cliente: escribir el nombre del trabajador tras "IRPF" (ej. "IRPF Pep Brugulat Borras") para trazabilidad en la libreta contable, pero las retenciones oficiales van en la sección IRPF.
- **Manual de usuario actualizado** (`manual-usuari.html` v2.1.16 · 03/02/2026): nueva FAQ sobre chip IRPF vs sección IRPF y sobre separación estricta de empresas con todas las claves de storage documentadas.
- Archivos tocados: `frontend/public/v2.html`, `frontend/public/manual-usuari.html`.



## 2026-02-03 · Empresa 2: eliminar todas las referencias a "Tasas DGT"
- **Chip "↩ Devolución tasa DGT"**: ahora es dinámico. En Empresa 1 sigue diciendo "↩ Devolución tasa DGT"; en Empresa 2 (cempla) muestra sólo "↩ Devolución" y su `title` se adapta al contexto (importe cobrado por revisión/certificado).
- **Modal `openTasaRefund()` unificado**: detecta `currentCompany`. En Empresa 2 busca cualquier ficha con `importe > 0` (no exige `kind==='TRAF'` ni `tasa>0`), la etiqueta del campo cambia de "Tasa" a "Importe" y al guardar reduce `entry.importe` en la ficha original en lugar de `entry.tasa`. El flag `_tasaRefund` se mantiene por compatibilidad con la lógica de compensación de fp existente (evita doble-descuento).
- **Botón de estadísticas de Empresa 2**: ahora usa `<span data-cfg-name="2">` para reflejar el nombre real de la empresa configurada por cada cliente (p.ej. "🏥 Revisiones CEMPLA S.L" en lugar del hardcodeado "Empresa 2"). Vinculado al mecanismo global de `applyCompanyUI()`.
- **Ledger Empresa 2**: concepto de devolución en la libreta contable cambia de "↩ Devolución tasa DGT: …" a "↩ Devolución: …" (asentamiento 708 Devoluciones ventas / 570 o 572 según fp igual que antes).
- Verificación smoke test: `btnStatEmpresa2` → "🏥 Revisiones CEMPLA S.L" ✅ · chip refund → "↩ Devolución" ✅.
- Archivo tocado: `frontend/public/v2.html`.



## 2026-02-28 (parte 6) · Movimientos internos Caja↔Banco + Devolución de tasa DGT
- **3 chips nuevos** en Debe/Haber (funcionan en las 2 empresas):
  - 🟠 **🔁 Ingreso en metálico (Caja→Banco)**: modal con importe/nota. Efecto: Caja−X, Banco+X, facturación 0. Fila resaltada naranja con badge "TRASPASO".
  - 🔵 **🏦 Retirada del banco (Banco→Caja)**: inverso del anterior.
  - 🟡 **↩ Devolución tasa DGT**: modal con buscador por nombre/DNI, muestra entradas del cliente con tasa cobrada. Al guardar: modifica retroactivamente la tasa en la ficha original + entrada informativa amarilla en día actual + libreta contable con asentamiento 708/570 o 708/572 en día devolución. Si fp devolución ≠ fp original, aplica compensación cruzada en byFp para que el dinero real quede coherente sin doble-descuento.
- Asentamientos contables en la Libreta correctos según Plan General Contable ES:
  - Ingreso metálico: **DEBE 572 Banco / HABER 570 Caja**
  - Retirada banco: **DEBE 570 Caja / HABER 572 Banco**
  - Devolución tasa: **DEBE 708 Devoluciones ventas / HABER 570 Caja o 572 Banco (según fp)**
- Nunca tocan la cuenta 705 Ingresos (correcto — no son ventas).
- `computeTotals` extendido con `internalCaja` e `internalBanco` que se aplican al final en renderSummary + `saldoAnteriorPorCuenta` para arrastre correcto al día siguiente.
- Bugs anteriores corregidos:
  - Reserva de cambio no vaciaba con "Vaciar todo" si Saldo inicial la re-sembraba: ahora Vaciar todo también pone `saldoInicial.cambio=0`, y setSaldoInicial ahora limpia `_bulk_seed`/`_bulk` cuando cambio=0.
  - Entradas manuales de Tráfico ahora cuentan en TODAS las estadísticas y desgloses (se quitó el filtro `_csv===true` en 5 sitios).
  - Campo DNI en fila Tráfico manual añadido y usado en fingerprint sync/dedup.
  - Grupos DGT ampliados con "Deportes", concepto ampliado con "Prórroga" y "Recuperación".
- Archivos tocados: `frontend/public/v2.html` (todo).


## 2026-02-28 (parte 5) · 👑 Admin: Comparar con CUALQUIER cliente
- Nuevo bloque ADMIN dentro del Asesor IA (visible sólo para MASTER): selector de cliente + botón "👑 Comparar". Descarga el snapshot de la licencia elegida y pide a la IA un diff contra los datos del admin. Útil para auditar cajas de cualquier cliente.
- Backend: nuevo endpoint `GET /api/sync/admin/other-license-snapshot?admin_license_key=…&target_license_key=…` (auth MASTER-only). Combina `sync_groups` + último backup del mailbox del cliente objetivo. Devuelve `target_client_name/email/plan` para trazabilidad.
- Tests end-to-end pasados:
  - Guard 403 si admin_license_key ≠ MASTER · 404 si target no existe · has_data=False si el cliente no ha subido datos (muestra mensaje amable en frontend).
  - Con datos reales cross-license: la IA identificó los 3 diffs plantados (JUAN faltante, ANA faltante, PEDRO solo en admin) y omitió correctamente el nombre que coincidía en ambos.
- Archivos: `backend/routes/sync.py`, `frontend/public/v2.html`.


## 2026-02-28 (parte 4) · Campo DNI + Historial de consultas IA
- **Campo DNI en Tráfico manual**: nueva columna `DNI` en la fila de entrada de Tráfico (entre Nombre e Importe). Se guarda en mayúsculas y monoespaciado. Al añadir la entrada, el DNI se incluye en el objeto guardado (`e.dni`) y participa en la huella de dedup, los filtros y la búsqueda.
- **Historial de consultas IA (últimas 5)**: nuevo botón "📚 Historial" en el modal del Asesor IA. Guarda automáticamente cada consulta (tanto `💬 Consulta` como `🔍 Comparar con el otro PC`) con timestamp, rango de fechas, pregunta y respuesta completa en localStorage (`caja.ai.history.v1`). Al pulsar en cualquier entrada del historial se muestra la respuesta guardada sin volver a consultar la IA. Botón "🗑️ Vaciar historial" con confirmación.
- Archivo tocado: `frontend/public/v2.html`.


## 2026-02-28 (parte 3) · 🔍 Comparar 2 PCs con IA · Reserva por empresa · Grupos DGT normalizados
- **Asesor IA · Comparar con el otro PC**: nuevo botón en el modal del Asesor IA que descarga el snapshot del otro ordenador de la misma licencia y pide a la IA un análisis diff día por día. La IA identifica entradas que faltan/sobran en cada lado, discrepancias de importe y descuadre por reserva de cambio. Termina con lista de acciones concretas para cuadrar.
  - Backend: nuevo endpoint `GET /api/sync/other-snapshot` que devuelve datos del otro PC. En modo Fusionado usa `sync_groups` (COLL_STATE) filtrando por autores ACTIVOS en `sync_devices` (evita datos huérfanos de installations eliminadas). En modo Independiente cae al último backup del mailbox.
  - Endpoint `POST /api/ai-ask` extendido con `otherData` + `compareMode: true` + `dateRange`. Genera fingerprint por entrada (kind+tipo+grupo+nombre+DNI+importe+tasa) y emite un bloque `🔍 COMPARACIÓN` con `➕ Solo en ESTE PC` / `➖ Solo en el OTRO PC` que la IA usa como base fáctica.
  - Tests end-to-end pasados: 2 PCs Fusionados con datos parcialmente distintos → la IA identificó correctamente los 3 casos plantados (PEDRO faltante, CARLA discrepancia importe, ANA solo en otro PC).
- **Reserva de cambio por empresa**: la clave `caja.reserva.v1` era global. Ahora `cambioKey()` devuelve `caja.reserva.v1` (Empresa 1) o `caja.cempla.reserva.v1` (Empresa 2). Cada empresa tiene su propio cajón físico, no se mezclan. Sync, "empezar de cero" y envío por día actualizados para las 2 claves. Backwards compat: los datos existentes de Empresa 1 permanecen bajo la misma clave.
- **Modal "Detectamos otro ordenador" ya no atrapa**: ahora tiene X, ESC y click fuera para cerrar sin obligar a elegir. Si se descarta, reaparece en el próximo arranque hasta que se elija.
- **Grupos y conceptos DGT completos + normalizador de sinónimos**:
  - Desplegable GRUPO (input+datalist, admite escritura libre): Conducción · Armas · Seguridad · Animales peligrosos · Grúas · Deportes · Marina · Ciclomotor · BTP · Otro.
  - Desplegable CONCEPTO ampliado: Renovación · Prórroga · Obtención · Expedición · Duplicado · Canje · Recuperación · Otro.
  - `_normalizeGrupo()` unifica sinónimos al guardar y al agregar estadísticas: `A. peligrosos`/`Animales P.`/`Animales Peli.` → `Animales peligrosos`; `Náutica`/`Nautica` → `Marina`; `S.P`/`S. privada`/`Seguridad Privada` → `Seguridad`; `Conducir` → `Conducción`; `Gruas` → `Grúas`; etc. Tests: 27/27 casos verificados.
- Archivos tocados: `frontend/public/v2.html`, `backend/routes/sync.py`, `backend/server.py`.


## 2026-02-28 (parte 2) · Deshacer fusión de copia recibida
- **Solicitud**: poder tirar atrás si tras aplicar una copia recibida algo no cuadra, para volver al estado anterior.
- **Solución**: aprovecha el sistema existente `caja.snapshots` (últimas 5 copias automáticas).
  1. Antes de aplicar la copia por sync banner → `pushSnapshot('preSyncApply')`.
  2. Tras aplicar → nuevo modal de éxito con dos botones: **"↩ Deshacer fusión"** (restaura el último snapshot al instante) y **"Aceptar y recargar"**.
  3. Etiqueta nueva "⚠ Antes de fusionar copia recibida" añadida al modal del Historial de copias, para poder deshacer también más tarde desde Configuración.
- Archivo tocado: `frontend/public/v2.html` (bloque `showBackupRestoreBanner` + nuevo helper `_showSyncApplySuccess` + reasonTxt map).


## 2026-02-28 · Fusión de copia sin duplicados por CONTENIDO (max cLocal, cRemoto)
- **Problema reportado por el usuario**: al pasar copia por 2ª vez desde un PC al otro, todas las entradas (Renovaciones/Obtenciones Tráfico, Revisiones, Fotos, ciclistas, etc.) se DUPLICABAN, teniendo el doble de todo. La regla acordada es: nunca duplicar lo que ya existe; sólo añadir lo que falta.
- **Causa raíz**: el motor `_mergeArrays` sólo dedupeaba por `id`. Si la misma ficha (mismo cliente, importe, tipo, fp) se había escrito manualmente en los dos PCs con `uid()` distinto, quedaba duplicada en cada fusión.
- **Solución**: dedup por **HUELLA DE CONTENIDO** (kind+tipo+grupo+nombre+DNI+importe+tasa+descuento+fp+fpTasa) con **conteo**: se conserva `max(cLocal, cRemoto)` por huella. Se aplica a los 3 caminos de fusión:
  1. `_mergeArrays` en el motor sync (usado por `applyBackup` = banner "Aplicar copia" y por `pullNow` del modo Fusionado).
  2. Camino de "Restaurar copia manual" desde fichero JSON (líneas ~6429/6434/6471 de `v2.html`, ahora vía helper local `_mergeArrDedup`).
  3. Cubre Empresa 1 (`caja.v1`), Empresa 2 (`caja.cempla.v1`), entradas CSV DGT (mismo DNI ⇒ misma ficha) y todos los `kind` (TRAF, PRIV, DH).
- **Ejemplos verificados con tests locales**:
  - PC-B 2 fotos + PC-A 4 fotos → resultado **4** (añade 2).
  - PC-B 4 fotos + PC-A 2 fotos → resultado **4** (no toca).
  - Misma copia enviada 2 veces → **no acumula**.
  - Misma Carla creada a mano en ambos PC con id distinto → **1**.
- Archivo tocado: `frontend/public/v2.html` (bloque sync inline + `restoreAll`).
- **Estado**: implementado y probado por agente con casos numéricos. Pendiente de confirmación del usuario tras Deploy y reinicio del `.exe`.


## 2026-02-27 (parte 2) · Sistema de emails cliente refactorizado
- **Bug arreglado**: cliente ya no recibe 3 emails duplicados por cada suscripción Stripe (checkout + subscription.updated + invoice.paid disparaban 1 email cada uno).
- **Regla del dueño aplicada**: cliente SOLO recibe email en estos casos, cada uno con cabecera clara que explica el motivo:
  1. **Activación inicial** (🎉 `reason=activated`) — al comprar/aprobar. Único email con la clave JWT.
  2. **Aviso de caducidad** (⏰ `renewal_reminders.py`) — 7 días antes si NO tiene subscripción activa (Trial o compra puntual).
  3. **Fallo de pago** (⚠️ nuevo `send_payment_failed_email`) — cuando Stripe no puede cobrar. CTA único: "Actualizar mi tarjeta" → hosted_invoice_url de Stripe.
  4. **Cancelación / expiración** (👋 nuevo `send_subscription_canceled_email`) — despedida amable con "hasta cuándo tienes acceso" + link para volver.
- **NO se envía email al cliente** en: renovaciones mensuales (Stripe manda factura), upgrades, downgrades, reactivaciones automáticas.
- **Rediseño visual**: cabecera con emoji grande + título del MOTIVO en primer lugar; datos clave (Plan/Fecha) en formato humano; JWT movido al final en sección "Datos técnicos"; sin Georgia serif, con font system nativo; asunto corregido (era `PREMIUM (PREMIUM)` duplicado).
- **Idempotencia**: campo `last_email_expires_at` en cada licencia. Se marca al enviar cualquier email → cualquier webhook posterior con mismo `expires_at` se salta.
- Archivos tocados: `backend/services/mailer.py`, `backend/services/renewal_reminders.py`, `backend/server.py` (webhook Stripe).
- **Acción manual pendiente del dueño**: activar en Stripe Dashboard → Settings → Emails → "Successful payments" y "Failed payments" para que Stripe mande recibos oficiales automáticos (nosotros solo mandamos avisos amables, no facturas fiscales).


## 2026-02-27 · Panel Maestro unificado (chuleta admin)
- Creado `/app/frontend/public/panel-maestro.html`: 1 solo panel en castellano con 5 tabs (Credenciales · Links · Funciones · Estado · Operativa), buscador cross-tab, credenciales borrosas con hover-to-reveal, botones "Copiar" al portapapeles con feedback visual.
- Sustituye a los 2 antiguos ficheros obsoletos `index-guies.html` y `guia-medicar-plus.html` (última actualización 15/07/2026, en catalán, con URL preview muerta que provocaba pantalla en blanco).
- Los 2 ficheros antiguos se convirtieron en redirects 302 al nuevo `/panel-maestro.html` para no romper bookmarks.
- `v2.html`: sustituidos los 2 botones "🎛️ Panell Mestre" + "📚 Guía Admin" por un único botón "📚 Panel Maestro (Chuleta)".
- Datos vigentes hoy: Trial 60d, URL medicarplus.es (no preview), Stripe TEST activo, credenciales sensibles (LICENSE_SECRET, GITHUB_TOKEN, sk_test) NO expuestas en el HTML.


## Original Problem Statement
Marc Brugulat (Catalonia) is turning a legacy offline HTML cash register app into a commercial Electron desktop app called **MediCar Plus** for medical driver-licence renewal centres in Spain. The product covers:
- HWID-locked license verification
- Web admin panel
- GitHub auto-updater via electron-updater
- Twilio SMS campaigns (currently mocked)
- Stripe subscription integration (test mode)
- Public landing page (medicarplus.es)
- Robust data entry, "Libro de Registro", "Estadísticas", automated email delivery of licenses/manuals, isolated multi-company data, Verifactu compliance, PDF generation

User's preferred language: **Catalan** (UI/code strings in **Spanish**).

## Product Architecture (Feb 2026)

### Frontend
- `frontend/public/v2.html` (~6.7k lines, Vanilla JS main UI)
- `frontend/public/downloads/electron-src/index.html` — **bootstrap loader** that fetches latest v2.html from server each startup; preserves file:// origin so localStorage persists across app updates
- `frontend/public/downloads/electron-src/main.js` — Electron main, `loadFile('index.html')`
- `frontend/public/downloads/electron-src/sync.js` — BUILD-TIME script (npm run release) that pulls latest sources from server + validates
- `frontend/public/downloads/landing-medicarplus.html` — public marketing page
- `frontend/src/components/admin/AdminDashboard.jsx` — Admin panel React component

### Backend (FastAPI + MongoDB via Motor)
- `backend/server.py` — mounts routers, CORS `*`, MONGO_URL from env
- `backend/routes/licenses.py` — /verify, /generate, /admin/*
- `backend/routes/pdf_render.py` — POST /pdf/render (Playwright HTML→PDF, uses system Chrome)
- `backend/routes/sync.py` — NEW: POST /sync/heartbeat, /sync/push, GET /sync/pull for multi-device
- `backend/routes/electron_manifest.py` — /electron/manifest + /electron/download/{filename}
- `backend/services/pdf_builder.py` — reused for guide/manual PDF attachments in emails

### Data Stores
- MongoDB `licenses` — {install_id, license_key(JWT), plan_family, expires_at, stripe_subscription_id, status}
- MongoDB `sync_states` — {_id: sha256(license_key), data: {ls_key: {value, updated_at, author}}, last_updated_at}
- MongoDB `sync_devices` — {license_key_hash, install_id, created_at, last_seen} (max 2 per Premium)
- MongoDB `counters` — atomic sequence for doc numbers

### Deployment
- **Preview** (dev): https://project-helper-47.preview.emergentagent.com
- **Production**: https://project-helper-47.emergent.host (24/7)
- `api-endpoint.json` on GitHub points bootstrap to production URL

## Plans (as of Feb 2026)

| Plan | Price | Devices | Features |
|---|---|---|---|
| **Trial** | Free · 60 days | 1 | Full Premium access (evaluation) |
| **Standard** | 29,90€/mes · 299,90€/año | 1 | Core: CSV DGT, Contabilidad, IRPF, Cierre, PDF, Backup |
| **Premium** | 39,90€/mes · 399,90€/año | 2 sync | Standard + Utilidades (SMS/Citas/IA/Auditoría) + Multi-empresa + Sync automático |

## What's Implemented (Feb 2026)

### Recent (Feb 2026 session)
- ✅ **Descargar PDF** client-side via html2pdf.js@0.10.1 (jsDelivr CDN). Replaces window.print(). WYSIWYG, offline OK, ~300KB PDFs with real content. Fallback: iframe.print() dialog if lib fails.
- ✅ **Plan gating** (STD vs Premium): `isPremiumLicense()` checks MASTER/PRM/PREMIUM/TRIAL. `refreshUtilitiesPremiumUI()` toggles `body[data-not-premium]` attr → CSS shows/hides padlock icons on menu items. Clicking any locked item opens `openPremiumUpgradeModal()`.
- ✅ **Utilidades menu**: 📱 SMS, 📅 Citas, 🤖 IA, 🔎 Auditoría. Badge `⭐🚀` on toggle button for Premium users. Standard sees padlock 🔒.
- ✅ **Auditoría tooltip**: "?" with data-tt="Detecta y encuentra errores más rápidamente, con nombres duplicados o cuotas a 0€ sospechosas..."
- ✅ **Trial 60 days** (was 30) — `AdminDashboard.jsx` line 588 `defaultDays='60'` when plan==='TRIAL'.
- ✅ **Landing page** rewritten: 60d prueba destacada, Utilidades destacadas dins Premium en gradient morat, "2 ordenadores sincronizados" incorporat.
- ✅ **Sync backend** (`routes/sync.py`): heartbeat/push/pull with device tracking. Standard=1 device, Premium=2. LWW per key. sha256 license key hash as _id.
- ✅ **Sync frontend**: 60s cycle, hooks localStorage.setItem, ☁️ indicator, offline resilient (sendBeacon on unload, retry on online/focus). Skips heartbeat for MASTER key (owner).
- ✅ **Auto-upgrade STD→PRM**: Sync heartbeat detects plan change → notifies via `notifyPlanChange` + toast "✨ Plan Premium activado" + refreshes UI immediately without app restart.
- ✅ **Duplicate row removed**: "Saldo anterior" bare row eliminated from sumBox (kept "Saldo anterior caja" only).

### Earlier
- Electron bootstrap → server pulls fresh v2.html each launch (preserves localStorage origin)
- Playwright PDF for guide/manual email attachments
- IONOS SMTP multi-mailbox delivery
- Twilio SMS mock, Google Gemini AI Asesor
- 4-level URL discovery (raw.githubusercontent → jsdelivr → api.github → cached)
- Cierre del día privacy blur, Auto-match Citas ↔ CSV DGT, Statistics per company, corrected DEBE/HABER as expense

## Testing Status (iteration_16.json + follow-up smoke, Feb 2026)
- Backend: 7/7 pytest PASS (heartbeat, push, pull, device limit, PDF render)
- Frontend: 15+ Playwright PASS + 13/13 i18n PASS + smoke visual gate global (btnStatSms/btnStatCites amb candau)
- No critical bugs.

## Landing subscribe → Stripe
- Botons "Contactar" reemplaçats per "💳 Suscribirse (mensual)" + "Suscribirse anual" a Standard i Premium (data-plan-subscribe=STD_MES/STD_ANY/PREMIUM_MES/PREMIUM_ANY)
- Script client-side crida `POST https://project-helper-47.emergent.host/api/create-checkout` → redirigeix a Stripe Checkout de la sessió creada
- Un cop pagat, webhook Stripe activa la llicència + envia mail automàtic amb .exe, guia i codi (ja existent al backend routes/payments.py)

## Gate Premium GLOBAL (v2.html)
- Handler capture-phase a document que intercepta clics a QUALSEVOL `[data-premium="1"]`
- CSS opacity/🔒 automàtic per elements fora de #utilitiesMenu quan Standard
- Aplicat a Estadísticas SMS (#btnStatSms) i Estadísticas Cites (#btnStatCites)
- Ja aplicat a Utilidades menu (SMS, Cites, IA, Auditoría)

## Iteration 19 (Feb 22, 2026) · Nou logo + Vista prèvia de plans + Guies actualitzades
- **Nou logotip Option 2** (dark squircle rounded amb "M" dourat + "+" verd): SVG font + PNG 16/32/48/180/256 + ICO multi-res per web i electron. Aplicat a `landing-medicarplus.html` (nav + footer), `v2.html` (header d'app) i `assets/icon.ico` per l'Electron .exe.
- **Header renovat opció D→2**: font Manrope 800 en color dourat, subtítol "GESTIÓN DE CENTROS MÉDICOS" (letter-spacing 3.5px).
- **Vista prèvia de plans (MASTER only)**: 4 botons a la modal "Info llicència" (Real / Trial / Standard / Premium). Banner lila permanent quan hi ha preview actiu. Trial-badge respecta l'override.
- Files nous a `/app/frontend/public/` (i còpia a `/downloads/`): `logo-medicarplus.svg`, `favicon.ico`, `favicon-{16,32,48,180,256}.png`, `apple-touch-icon.png`, `android-chrome-{192,512}.png`, `electron-icon.ico`.
- v2.html ara té meta favicon links (svg + ico + apple-touch).

## Iteration 18 (Feb 22, 2026) · Trial automàtic + Post-pago automàtic + Lightbox screenshots

- **NOU endpoint `POST /api/trial/start`** (fitxer `backend/routes/trial.py`): genera llicència TRIAL de 60 dies + envia email amb clau + 2 PDFs (guia + manual). Anti-abús: 1 trial per email, honeypot, consent obligatori.
- **Modal Trial a la landing**: reemplaça el `mailto:` anterior. Botó "🎁 Empezar prueba gratuita" (plan Trial) i badges "Prueba gratuita 60 días" (sota Standard i Premium) obren el modal. Al submit, mostren la clau a pantalla + confirmen l'enviament del mail.
- **Endpoint `/api/payments/subscription/status/{id}` estès**: ara retorna també `license_key`, `install_id`, `expires_at`, `license_ready` (buscant a `db.licenses` via `stripe_subscription_id`) + `download_url` fix.
- **NOVA pàgina `subscription-success.html`**: hostejada al backend Emergent. Rep `?session_id=...` de Stripe, fa poll cada 3s (20 intents = 60s màx), i mostra la clau + botó "📥 Descargar" + confirmació d'email en quan el webhook ha corregut. Redirecció Stripe canviada a aquesta pàgina (no a `/request-license`).
- **API URLs auto-detectats** al landing (`API_BASE`): si el hostname és `medicarplus.es` → producció Emergent, sinó → mateix origin. Elimina el hardcoding que trencava en preview.
- **Lightbox modal de captures** a les targetes "Características": 9 targetes mapejades a les captures de GitHub (`https://medicarplus.es/screenshots/*.jpg`). Afegides 3 targetes noves (Estadísticas, Citas, Auditoría) per aprofitar totes les captures. Etiqueta "🔍 Ver ejemplo" a cada targeta clicable.
- **Botons plans polits**: "Suscribirse anual" ara mostra "🗓️ Pago anual · ahorra 58,90€/78,90€" en una sola línia amb padding uniforme (ja no es trenca lletjament).
- **Sync device_not_authorized** verificat (iteració anterior mantinguda).
- **Webhook Stripe** actualitzat via API a producció (URL definitiva `emergent.host/api/webhook/stripe`).

### Cost temporal del `/api/trial/start`: ~5 segons (genera 2 PDFs via Playwright Chromium). Acceptable · el modal mostra spinner "Generando tu licencia…".

## Next Actions (Feb 22, 2026)
1. **User**: click "Volver a publicar cambios" al panel Emergent → puja a producció: endpoint `/api/trial/start`, `/subscription-success.html`, `payments.py` amb success_url nou, i `/api/payments/subscription/status` estès.
2. **User**: puja el nou `landing-medicarplus.html` a GitHub Pages (segueix la guia del pas anterior o la nova secció "🌐 Publicar canvis a la landing" de la guia general).
3. **Futur backlog**:
   - Twilio SMS real (actualment mocked)
   - Stripe live keys migration
   - Verifactu compliance
   - Domain mapping `medicarplus.es → Emergent Hosting` (elimina pas GitHub Pages manual)
   - Panel de mètriques de subscripcions (MRR, churn, failed_payments) al Admin Dashboard
   - Reminder emails al dia 45/55/59 del trial

## Test Credentials
- MASTER offline: `MB-MASTER-BRUGULAT-2026-OWNER`
- Admin token: `MB-ADMIN-BRUGULAT-2026-4F8E2A1C`
- PRM license (2/2 devices used): `CD-PR8E-D4D8-A71A-2842` + `CD-D299-4E88-1F92-364A`
- **Stripe verificat**: totes 4 variables STRIPE_PRICE_* + STRIPE_API_KEY presents al backend. `/api/payments/subscription/enabled` retorna enabled=true. Els 4 packages (STD_MES, STD_ANY, PREMIUM_MES, PREMIUM_ANY) generen sessions Checkout vàlides (checkout.stripe.com).
- **Landing CHECKOUT_API corregit**: abans apuntava a `/api/create-checkout` (endpoint one-off inexistent com a subscripció); ara apunta a `/api/payments/create-subscription` (correcte).
- **Landing email prompt**: els botons "Suscribirse" ara demanen email via `window.prompt()` abans de crear la sessió Stripe (evita el 422 per customer_email missing).
- **Trust badges (conversion improvement)**: sota els botons Suscribirse de Standard i Premium ara hi ha un badge visible "🎁 Prueba gratuita 60 días • Sin tarjeta" + subline "Cancela cuando quieras · Sin permanencia". data-testid: `landing-std-trial-badge`, `landing-prm-trial-badge`.
- **Sync security hardening**: `/api/sync/push` i `/api/sync/pull` ara requereixen que l'install_id ja tingui entrada a `sync_devices` (via heartbeat previ). Un dispositiu no autoritzat rep 403 `device_not_authorized`. Tanca gap on qualsevol amb la licence_key podia escriure/llegir el cloud state.
- **Tests**: 13/13 backend pytest PASS + 9/9 frontend Playwright PASS. Zero action items.

## Next Actions (Feb 2026)
1. **User**: "Volver a publicar cambios" → push aquestes noves versions al domini de producció.
2. **User**: Copiar el nou `landing-medicarplus.html` a GitHub Pages (`medicarplus.es`) perquè el badge i el CHECKOUT_API arribin al públic.
3. **Future backlog**:
   - Real Twilio API (currently mocked)
   - Stripe live keys migration (currently test mode)
   - Verifactu compliance
   - Domain mapping `app.medicarplus.es` → production
   - Google Search Console for medicarplus.es
   - Reparto socios % configuration UI

## Test Credentials
- MASTER offline: `MB-MASTER-BRUGULAT-2026-OWNER`
- Admin token: `MB-ADMIN-BRUGULAT-2026-4F8E2A1C`
- PRM license (DB, 2/2 devices used): install_ids `CD-PR8E-D4D8-A71A-2842` + `CD-D299-4E88-1F92-364A`

## Session Feb 23-24, 2026 · Programa de Referits + hardening
**Programa de referits complet (validat 17/17 pytest + FE E2E):**
- Cada llicència PAGADA (STD/PRM) rep un `referral_code` únic `MC-XXXX-XXXX`.
- URL a compartir: `https://medicarplus.es/?ref=CODE` — captura automàtica a sessionStorage.
- Modal Trial de la landing: input opcional "🎁 Código de referido" amb validació en directe + tooltip "?" explicatiu.
- Recompenses via Stripe (idempotents):
  - **Referrer (A)** → cupó `MEDICAR_REFERRAL_2M` (100% off, 2 mesos) aplicat a la subscripció existent.
  - **Referit (B)** → cupó `MEDICAR_REFERRED_1M` (100% off, 1 mes) aplicat al Checkout de B → **visible ABANS de pagar**.
- Trial → Paid: backend revoca doc trial + crea doc paid nou + hereta `referred_by` + genera referral_code + aplica recompensa al referrer.
- Fallback robust: si Stripe falla, s'estén l'`expires_at` de la llicència del referrer 2 mesos i queda registrat per retry.
- Panel `/admin`: nova columna "🎁 Codi referit" amb botó de copiar + badge amb el count de referits.
- Modal `Informació de llicència` del v2.html: bloc morat amb codi + botons "Copiar codi" i "Copiar enllaç" + estadístiques + tooltip "?".

**Bugs fixats durant la implementació:**
- Stripe `discounts` + `allow_promotion_codes` són mútuament exclusius (bug A iter23).
- Trial→Paid path saltava referral_code + reward (bug B iter23).
- Duplicate `id_1` key quan es revoca trial i s'insereix paid amb mateix id (bug C iter24).
- `_doc_to_record` no mapejava els camps nous (referral_code, linked_hwids, etc) (bug D iter24).

**Fitxers claus creats/modificats:**
- `/app/backend/services/referrals.py` (nou)
- `/app/backend/routes/referrals.py` (nou · endpoints `/validate` + `/my-code`)
- `/app/backend/server.py` (webhook capture referred_by + reward apply)
- `/app/backend/routes/payments.py` (conditional discounts / allow_promotion_codes)
- `/app/backend/models/license.py` (nous camps LicenseRecord)
- `/app/backend/routes/licenses.py` (`_doc_to_record` + verify multi-device HWID)
- `/app/backend/routes/trial.py` (captura referred_by)
- `/app/frontend/public/downloads/landing-medicarplus.html` (?ref= + input opcional trial + tooltip)
- `/app/frontend/public/v2.html` (referral block en showLicenseInfo + tooltip + create-subscription amb referred_by)
- `/app/frontend/src/components/admin/AdminDashboard.jsx` (columna "🎁 Codi referit")

**Tests**: iteration_23 (10/10 + 2 bugs found+fixed), iteration_24 (17/17 pass + 2 optional hardening applied).


**Bugs fixats en aquesta sessió (tots verificats per testing agent):**
1. **`/api/trial/start` congelava el navegador** (19s síncrons) → email en background, resposta en 0.25s.
2. **Trial JWT no permetia activació** perquè `sub` era un install_id sintètic (`CD-TRIAL-XXXX`). → Ara `sub` és portable (missing/CD-TRIAL-*/CD-STRIPE-*). Client + servidor accepten JWTs portables i fan bind-on-first-verify.
3. **Missatges d'error en català** → tots reescrits en castellà.
4. **Logo M+ no visible a Electron** (URLs relatives resolien contra `file://`) → script inicial al v2.html que reescriu URLs cap al servidor via `window.API_BASE` quan detecta entorn Electron.
5. **Botó "Powered by" no clicable** (selector `[style*="Powered by"]` no matcheava) → nou id `licSigBox`.
6. **Post-Stripe: pàgina de success mostrava clau per copiar** encara que fos upgrade des de dins l'app → ara detecta `metadata.install_id` real i mostra "Vuelve a MediCar Plus, se está actualizando automáticamente".
7. **Guia de instal·lació 404** (apuntava a GitHub Pages inexistent) → link relatiu `/guia-client-installacio.html`.
8. **Doble consentiment obligatori** al formulari Trial: (a) política privacitat + (b) responsabilitat de dades i copies de seguretat. Nova pàgina legal `/terminos-uso.html`.
9. **Botons de plans plans i grisos** → gradients colorits amb pulse: Trial verd, Standard blau, Premium daurat, anuals daurat/morat. Card Trial 100% clicable.
10. **Badge PREMIUM solapava "Ver ejemplo"** a les targetes utilitats → badge mogut a top-left (era right).
11. **Auto-upgrade de plan**: `/api/licenses/current` nou endpoint + polling v2.html cada 5s (primers 2min) / 30s. Detecta upgrade Stripe i actualitza localStorage + refresca UI + toast. Zero fricció client.
12. **`isPremiumLicense` no reconeixia `plan=PREMIUM`** amb `type=JWT` → ara comprova ambdós camps.
13. **Master + Vista prèvia**: quan es fa polling, si l'usuari és MASTER amb `caja.plan.preview.v1` actiu, l'auto-upgrade actualitza la PREVIEW (no la clau real). Perfecte per testing.
14. **Email de llicència no s'enviava en UPGRADE**: ara `_sync_license_from_subscription` envia email també quan actualitza (`subject_prefix='Pla actualitzat a PREMIUM'`).
15. **Email editable abans del pagament**: nou camp `#upgEmailInput` al modal "Ver planes" pre-omplert amb `localStorage.caja.billing.email.v1`. Validació + persistència entre compres.
16. **Multi-dispositiu Premium**: mateixa clau funciona a 2 ordinadors. `linked_hwids` + `linked_install_ids` a `db.licenses`. Standard/Trial segueixen limitats a 1. `/api/licenses/current` cerca en ambdós arrays.
17. **Claus PREMIUM admin-generades ara portables** (`sub=CD-STRIPE-ADMIN-*`) perquè també funcionin a 2 dispositius (abans només les generades per Stripe eren portables).

**Tests**: iteration_19 (4/4 pass), iteration_20 (4/4 pass), iteration_21 (4 backend + 7 frontend pass).

## Backlog · Feb 23, 2026
1. **Classificació adaptativa d'autoescoles** (P1): quan un client puji el seu arxiu, detectar patrons únics d'autoescoles del seu dataset i presentar la llista per confirmar/ajustar (ara està hardcoded per Daina/Mabel/Rossell/etc del owner).
2. **Twilio SMS real** (P1): actualment mocked.
3. **Domain mapping medicarplus.es → Emergent** (P2): eliminar dependència de GitHub Pages.
4. **Google Search Console** (P2).
5. **Reminder emails** dia 45/55/59 del trial (P2).



## Session Feb 23, 2026 (P0 Master preview stuck fix)

**Bug fix**: Master Admin quedava "encallat" en simulació Premium després de testejar el flow d'upgrade Trial→Premium. El polling auto-migrava el preview cap al pla remot (PRM al backend) impedint tornar a Trial/Standard manualment.

**Canvis a `/app/frontend/public/v2.html`**:
1. **Nou botó "🔄 Reiniciar pruebas"** al modal de llicència (només visible a MASTER). Neteja `caja.plan.preview.v1`, `caja.plan.preview.autoupg.v1` i `caja.plan.preview.trialkey.v1`. La clau MASTER real i les dades NO es toquen. Confirmació prèvia + toast + reload.
2. **`pollAutoUpgrade` simplificat per MASTER amb preview**: ja NO canvia automàticament el valor del preview quan el backend té un pla superior. Només mostra un toast informatiu (`Webhook OK · Licencia X detectada · tu simulación se mantiene`) una vegada per sessió (via `sessionStorage`). Això permet al MASTER moure's lliurement entre Trial/Std/Prm sense ser arrossegat cap al pla real del backend.
3. Cada clic manual als botons de preview reseteja el flag intern d'auto-upgrade.

**Test**: screenshot tool · botons `btn-reset-preview` i `prev-off` renderitzats correctament al modal.


## Session Feb 23, 2026 (P1 · Twilio BYOA integration)

**Decisió del propietari**: Model **BYOA (Bring Your Own Account)**. Cada centre client configura el seu propi compte Twilio; ells paguen directament a Twilio; MediCar Plus no toca diners. WhatsApp queda ajornat.

**Canvis backend (`/app/backend/routes/sms_campaigns.py`)**:
1. `SmsCampaignCreate` accepta camp opcional `twilio_creds: {sid, token, from}`.
2. `_send_sms(mobile, message, creds=None)` refactoritzat amb prioritat:
   - (1) creds del request (BYOA) → (2) `.env` global (fallback admin) → (3) MOCK.
3. Nou endpoint **`POST /api/sms/test-credentials`**: valida SID+Token cridant Twilio (`accounts(sid).fetch()`) i comprova que el número `from` existeix al compte o és Alphanumeric Sender. Retorna `{ok, account_name, account_status, from_valid, from_kind}` o `{ok:false, reason}`.
4. La resposta de `/campaigns` afegeix `twilio_source: "byoa"|"global"|"mock"` per traçabilitat.
5. La campanya guarda `twilio_used` i `twilio_source` a MongoDB.

**Canvis frontend (`/app/frontend/public/v2.html`)**:
1. Helpers globals: `getTwilioCreds()`, `saveTwilioCreds()`, `clearTwilioCreds()`, `hasTwilioCreds()`. Emmagatzemat a `localStorage['caja.twilio.creds.v1']`.
2. Nou botó **⚙️ Twilio** al header del modal Avisos SMS (obre `openTwilioCfgModal()`).
3. Modal complet de configuració amb 3 camps (SID, Token, From), botó **🔎 Provar credencials** que crida `/test-credentials`, botó **💾 Desar** i botó **🗑 Eliminar credencials**.
4. Banner dinàmic dins el modal SMS: verd (✅ Twilio configurat · Compte propi) o taronja (⚠️ Twilio no configurat · Mode PROVA). Botó "Configurar" al banner mateix.
5. `/campaigns` POST injecta automàticament `twilio_creds` si el client té creds a localStorage.
6. Alert post-campanya ara mostra `(tu cuenta Twilio)`, `(cuenta administrador)` o `(simulación)`.

**Canvis guia client (`/app/frontend/public/guia-client-installacio.html`)**:
- Nova secció **Pas 7 · Enviar SMS als seus pacients (opcional · Twilio)** amb 5 sub-passos: crear compte Twilio → comprar número → copiar credencials → configurar dins l'app → enviar campanya. Costos aproximats + troubleshooting.

**Tests**:
- `curl POST /api/sms/test-credentials` amb fake creds → retorna `credentials_invalid` correctament.
- `curl POST /api/sms/campaigns` amb `twilio_creds` fake → retorna `twilio_source: "byoa"` i `twilio_mode: "real"`.
- Screenshot: `openTwilioCfgModal` exposada globalment, 6 data-testid presents (twilio-sid, twilio-token, twilio-from, twilio-cfg-test, twilio-cfg-save, twilio-cfg-del).

**Data-testids afegits**: `btn-sms-twilio-cfg`, `twilio-sid`, `twilio-token`, `twilio-from`, `twilio-cfg-test`, `twilio-cfg-save`, `twilio-cfg-del`.

**Seguretat**: Credencials mai persistents al backend. Es passen amb cada request via body JSON. localStorage-only al client. El master admin pot continuar usant les creds `.env` si les té definides (fallback automàtic).


## Session Feb 24, 2026 (P0 · Fix Admin Panel login)

**Bug reportat pel client**: Al panell `/admin.html`, després d'introduir el token i clicar "Entrar" no passava res.

**RCA**: Error de sintaxi JS al script inline d'`admin.html`. Línia 366 tenia una cadena JS `'... s\\'ha connectat ...'` on `\\'` es parseja com "un backslash escapat" + "apòstrof que TANCA la cadena", trencant el parsing de la resta del `<script>` sencer. Com que el `<script>` sencer no es carregava, `doLogin` mai es definia i el botó era inert. Confirmat amb `acorn.parse` (error "Missing } in template expression" a línia 242 col 355 del script extret).

**Fix aplicat** (`/app/frontend/public/admin.html` L366): substituït `s\\'ha connectat` per `s\'ha connectat` (escape JS correcte d'un apòstrof dins una cadena delimitada per `'`).

**Verificació**:
- `acorn.parse` sobre el `<script>` extret → `PARSE OK`.
- Playwright: navegació a `/admin.html` + fill token + click → `typeof doLogin === 'function'`, `login.display === 'none'`, `app.display === 'block'`, 11 files a `#tbody`, 0 page errors.
- Screenshot del panell mostra estadístiques i taula de llicències renderitzades correctament.


## Session Feb 24, 2026 (P1 · Adaptive Driving School Extraction + P2 · Manual button in Support Hub)

### P1 · Adaptive Driving School Extraction
Objectiu: quan un client nou importa el seu CSV, l'app ha d'auto-detectar les seves autoescoles, extreure la llista única, normalitzar-la i presentar-la en una UI d'onboarding.

**Canvis** (`/app/frontend/public/v2.html`):
1. Nou store client-side d'aliases: `STATS_ALIAS_KEY='caja.stats.aliases.v1'` + helpers `loadStatsAliases()` / `saveStatsAliases()` mantenen el mapa `{RAW_CODE_UPPER: 'Nom canònic'}` a `localStorage`.
2. `canonicalName(raw)` ara consulta primer el mapa del client i després `STAT_ALIAS` (l'històric hardcoded del propietari Marc Brugulat).
3. `$('#stFile').onchange` refactoritzat:
   - Parseja el CSV mantenint `rawCounts[RAW_UPPER]=total` (abans es col·lapsava directament a canonical).
   - Detecta `newRaws`: codis del CSV que NO són al `STAT_ALIAS`, NO són al mapa de client, i el seu canònic no és a `st.autoescoles`.
   - Si `newRaws.length > 0` → obre modal de revisió `openAutoescoleReview()`.
   - Si `newRaws.length === 0` → aplica import directament (comportament previ).
4. `openAutoescoleReview(newRaws, rawCounts, existingList, onDone)`:
   - Renderitza una taula amb 4 columnes: `Codi CSV` · `Certificats` · `Nom a mostrar` (input editable) · `O fusionar amb…` (dropdown de les autoescoles existents).
   - Copy diferent per primer import (0 autoescoles → "Configura les teves autoescoles") vs imports subseqüents ("Noves autoescoles detectades").
   - Al confirmar, guarda els aliases a `localStorage['caja.stats.aliases.v1']` (persistents entre imports) i executa `onDone()` que reagrupa `sums` pel canònic final i llança el `confirmModal` "Importar {mes} {any}".
5. Sort dels rows per volum descendent (certificats↓) perquè el client vegi primer les autoescoles importants.

**Data-testids afegits**: `ae-review-row-{i}`, `ae-review-name-{i}`, `ae-review-merge-{i}`, `ae-review-cancel`, `ae-review-apply`.

**Verificació E2E** (Playwright):
- CSV amb 3 codis (`AUTOESCOLA_ONE` x2, `AUTOESCOLA_TWO`, `DAINA`) → modal detecta exactament 2 codis nous, `DAINA` filtrat correctament pel `STAT_ALIAS` predefinit.
- Agregació de duplicats OK: `AUTOESCOLA_ONE` = 12+3 = 15.
- Després de renombrar → aliases guardats correctament: `{"AUTOESCOLA_ONE":"Autoescola U","AUTOESCOLA_TWO":"Autoescola Dos"}`.
- Autoescoles afegides i totals correctes al mes: `{"2026-06":{"Autoescola U":15,"Autoescola Dos":8,"A.E.DAINA":5}}`.
- 0 errors JS · `acorn.parse` del `<script>` inline: PARSE OK.

### P2 · Botó Manual al Support Hub
**Canvi**: grid del hub passat de `repeat(3,1fr)` a `repeat(4,1fr)` amb un nou botó `supTabManual` (gradient daurat) que fa `window.open(LIC.MANUAL_URL, '_blank')` per obrir la guia interactiva al navegador per defecte.

**Data-testid afegit**: `sup-tab-manual`.

**Verificació**: Playwright detecta els 4 botons (`sup-tab-manual/bug/remote/phone`); interceptant `window.open` durant el clic al Manual retorna la URL esperada `https://<host>/manual-usuari.html`.


## Session Feb 24, 2026 (Follow-up · STAT_ALIAS gating + GIC template)

### Fix crític · STAT_ALIAS només per al Master Owner
Feedback del propietari: "cada usuari li variaran les autoescoles, ho ha de detectar sol". El mapa hardcoded `STAT_ALIAS` (autoescoles del centre CEMPLA CB de Marc: DAINA, MABEL, M-2, MOLIST, TRÀFIC…) contaminaria les detecions d'altres clients comercials.

**Canvi** (`/app/frontend/public/v2.html`):
- `canonicalName(raw)` ara detecta si l'usuari és MASTER via `lic.type==='MASTER'` o `lic.license_key===LIC.MASTER_KEY`; només aplica `STAT_ALIAS` en aquest cas.
- La detecció de `newRaws` també respecta aquest gate (per clients no-master, un codi que coincideixi amb `STAT_ALIAS` es marca com nou i entra al modal d'onboarding).
- `applyImport` reagrupa `sums` amb la mateixa lògica: aliases del client > STAT_ALIAS (només master) > raw.

**Verificació E2E**:
- Client comercial (`type:'PREMIUM'`, licensa no-master): CSV amb `DAINA;5 · MABEL;8 · TRAFIC;12 · AUTOESCOLA_NOVA;3` → modal mostra els 4 codis (STAT_ALIAS ignorat). ✅
- Master (`type:'MASTER'`, licensa `MB-MASTER-...`): mateix CSV → modal mostra només `AUTOESCOLA_NOVA` (els altres resolts per STAT_ALIAS). ✅

### Plantilla GIC · Descàrrega + guia d'exportació SMS
El programa GIC exporta el llistat de renovacions via <b>Clientes a Revisar</b> aplicant una plantilla `.lst` que defineix les 7 columnes que MediCar Plus espera: `Numero · Nombre · Apellido1 · Apellido2 · Movil · Telefono · FechaRevision`. Fitxer proveït per l'usuari: `F_revision_con_telefono_y_movil.lst` (4898 bytes).

**Canvis**:
1. Plantilla guardada a `/app/frontend/public/downloads/gic-templates/F_revision_con_telefono_y_movil.lst` (accessible via GET `/downloads/gic-templates/F_revision_con_telefono_y_movil.lst`).
2. `v2.html · renderSmsNew()`: afegida secció col·lapsable `<details data-testid="sms-gic-help">` amb els 7 passos numerats (obrir GIC → Clientes a Revisar → dates → Selección → Salida=Listados → carpeta 📂 → carrega plantilla → FICHERO) i botó daurat de descàrrega `data-testid="sms-gic-tpl-download"`.
3. `manual-usuari.html`: nova secció `🖨️ Exportar el listado desde el programa GIC` dins la pestanya SMS amb els mateixos passos i el mateix botó de descàrrega.
4. `guia-client-installacio.html · Pas 7`: callout groc destacat "🖨️ Pas previ · Exportar el llistat des del programa GIC" com a introducció del mòdul SMS.

**Verificació backend** (POST `/api/sms/preview` amb el CSV real de l'usuari `SMS CLIENTS JUNY.csv`, 285 files):
- ✅ 248 vàlids (mòbils normalitzats: espais, punts i guions es netegen bé — `"686 03 95 86"` → `686039586`, `"93-8889301"` → correctament rebutjat com a fix).
- ✅ 31 invàlids (fixes que comencen per 9 correctament detectats).
- ✅ 6 duplicats identificats (per `mobile` normalitzat, no per `name`).
- ✅ UTF-8-sig BOM manejat correctament (`errors='replace'`).
- ✅ Delimitador `;` auto-detectat via `csv.Sniffer`.

**Data-testids afegits**: `sms-gic-help`, `sms-gic-tpl-download`.

**Fitxers modificats**:
- `/app/frontend/public/v2.html` (canonicalName gate, applyImport gate, renderSmsNew ampliat)
- `/app/frontend/public/manual-usuari.html` (secció exportació GIC dins SMS)
- `/app/frontend/public/guia-client-installacio.html` (callout Pas 7)
- `/app/frontend/public/downloads/gic-templates/F_revision_con_telefono_y_movil.lst` (nou fitxer)


## Session Feb 24, 2026 (Follow-up 2 · GIC help card visibility + program pill)

**Feedback del propietari**: (1) "on troben la plantilla que han d'afegir aquí?" — l'ajuda GIC quedava amagada dins un `<details>` col·lapsat; (2) volia que la captura de la pantalla "Clientes a Revisar" fos visible directament dins l'app perquè el client sàpiga on carregar la plantilla; (3) "de moment només GIC, però podríem afegir més programes en el futur i que el client escollís".

**Canvis** (`/app/frontend/public/v2.html · renderSmsNew`):
1. Ajuda GIC ja **no és col·lapsable** — apareix sempre visible amb marc daurat destacat (`border:2px solid #f5b301`, gradient de fons daurat-marronós, ombra), com a primer element del pas de pujar CSV.
2. **Captura del GIC incrustada**: `gic-clientes-a-revisar.png` (58 KB) guardada a `/downloads/gic-templates/` i mostrada dins la targeta amb `cursor:zoom-in` (clic → obre en pestanya nova). El cercle vermell del propietari senyala exactament on carregar el fitxer `.lst`.
3. **Botó de descàrrega prominent**: `📥 Descargar plantilla` en groc gran (13px, padding 10×18, ombra) al capçal de la targeta.
4. **Guia de 5 passos** al costat de la captura (grid 2 columnes) amb els codes `ListadoPorDefecto` i `F_revision_con_telefono_y_movil.lst` destacats.
5. **Callout verd inferior**: "💡 Només cal fer-ho una vegada" + les 7 columnes exportades (`Numero · Nombre · Apellido1 · Apellido2 · Movil · Telefono · FechaRevision`).
6. **Etiqueta d'extensibilitat**: pill `🖥️ Programa usado: GIC` amb text italic petit `(pronto: más programas)` al capçal — deixa el punt d'ancoratge visual per convertir-ho en un `<select>` desplegable quan es donin d'alta més programes (Dr. Sanitas, etc.).

**Canvis** (`/app/frontend/public/manual-usuari.html · pestanya SMS`):
- Mateixa captura `gic-clientes-a-revisar.png` incrustada abans de la llista numerada de 7 passos.
- Botó de descàrrega en callout groc destacat.

**Verificació** (Playwright):
- `data-testid="sms-gic-program-pill"` mostra "🖥️ Programa usado: GIC". ✅
- `data-testid="sms-gic-tpl-download"` href = `/downloads/gic-templates/F_revision_con_telefono_y_movil.lst`. ✅
- `data-testid="sms-gic-screenshot-link"` embedded img src = `/downloads/gic-templates/gic-clientes-a-revisar.png` (HTTP 200 · 58329 bytes). ✅
- `data-testid="sms-gic-help"` bordat daurat (`rgb(245,179,1)`) present. ✅
- Acorn parse: OK · 0 errors JS.

**Backlog futur** (quan calgui):
- Convertir el pill `Programa: GIC` en `<select>` amb opcions: `GIC` (actual), `Dr.Sanitas`, `Clíni-K`, `Altres`. Cada opció renderitza el seu propi bloc d'ajuda + plantilla + captura. Estructura de dades suggerida: `{ gic: { name, tpl_url, screenshot_url, steps: [...] }, ... }` a `LIC.RENEWAL_PROGRAMS`.
- Detecció automàtica al primer CSV import (matching de columnes conegudes) per pre-seleccionar el programa.


## Session Feb 24, 2026 (Follow-up 3 · UI compacta + modal d'ajuda GIC · TOT en castellà)

**Feedback del propietari**: "Fes un interrogant dins per explicar què s'ha de fer amb aquesta plantilla i on copiar-la mostrant la foto — pel client ha de ser fàcil, no vull trucades cada 2×3. I tot en castellà."

**Canvis** (`/app/frontend/public/v2.html · renderSmsNew` + nova `openGicHelpModal`):
1. **Ajuda GIC compactada en una barra horitzontal** amb 3 elements: pill `🖥️ Programa: GIC` + botó rodó `❓` (daurat, 38×38) + botó `📥 Descargar plantilla` (groc gran). Ja no ocupa mig modal.
2. **Nou modal d'ajuda** `openGicHelpModal(tplUrl, imgUrl)`:
   - Capçalera: `🖨️ Cómo aplicar la plantilla en el programa GIC` + subtítol descriptiu + botó `✕`.
   - **Captura del GIC amb fons blanc** (`gic-clientes-a-revisar.png`), cursor:zoom-in per obrir-la en pestanya nova. Caption: "👆 El círculo rojo marca **exactamente** dónde tienes que cargar la plantilla".
   - **Instruccions numerades de 8 passos** (descarregar → obrir GIC → dates → Selección de Ficheros → Salida → carpeta 📂 → FICHERO → pujar CSV).
   - Callout verd: "💡 Solo hay que hacerlo una vez — cada mes solo cambiar fechas y pulsar FICHERO".
   - Footer: botó `Cerrar` + botó `📥 Descargar plantilla` gran.
3. **Localització forçada a castellà**: eliminades totes les cadenes `${isCA ? '...' : '...'}` de la secció GIC. Ara és 100% castellà independentment de l'idioma d'app.

**Data-testids nous**: `sms-gic-help-btn`, `gic-help-close`, `gic-help-screenshot`, `gic-help-cancel`, `gic-help-download`.

**Verificació E2E** (Playwright):
- Barra compacta: pill = `🖥️ Programa: GIC`, botó `❓` present, botó `📥 Descargar plantilla` present. ✅
- Clic al `❓` → modal obre correctament amb captura (`imgSrc` correcte, HTTP 200) i botó de descàrrega (`downloadHref` correcte). ✅
- Clic al `✕` → modal es tanca. ✅
- Acorn parse: OK · 0 errors JS.

**Fitxers modificats**:
- `/app/frontend/public/v2.html` (funció `openGicHelpModal` afegida + `renderSmsNew` refactoritzat compacte)


## Session Feb 24, 2026 (Bug fix P0 · Web purchase flow mostrava "upgrade" incorrectament)

**Bug reportat pel propietari**: Va provar de comprar la subscripció mensual des d'un ordinador nou, sense l'app instal·lada, via web (`medicarplus.es`). Després de pagar amb Stripe, la pàgina de retorn (`subscription-success.html`) mostrava incorrectament el bloc "Tu plan se está actualizando automáticamente · Vuelve a la ventana de MediCar Plus" — però el client no tenia cap app oberta i necessitava (a) la URL de descàrrega i (b) la clau visible per copiar.

**RCA**:
- El webhook Stripe (`backend/server.py L281`) genera un install_id placeholder `CD-STRIPE-{sub_id[:16]}` quan la metadata del checkout NO porta install_id (compra des de la web).
- La funció `_isRealInstallId()` a `subscription-success.html` només detectava com a placeholder els que començaven per `CD-STRIPE-PENDING-` o `CD-TRIAL-PENDING-`.
- Resultat: `CD-STRIPE-SUB_1TESTABCD12` era considerat "real install_id" → codi ramificava incorrectament per la branca d'UPGRADE.

**Fix aplicat** (`/app/frontend/public/subscription-success.html · _isRealInstallId`):
- Ampliada la detecció: ara qualsevol install_id que comenci per `CD-STRIPE-` o `CD-TRIAL-` es considera placeholder del backend.
- Els install_ids reals de l'app (`v2.html · getInstallId()`) són `CD-XXXX-XXXX-XXXX-XXXX` (hex random), MAI comencen amb aquests prefixos.

**Verificació E2E** (Playwright · rutes interceptades):
- Web purchase (`install_id: "CD-STRIPE-SUB_..."`, metadata buida): ✅ mostra `newClientBox` amb clau visible + Copiar + Descargar + Guía + 3 passos.
- Upgrade des de l'app (`install_id: "CD-A1B2-C3D4-E5F6-7890"`, metadata real): ✅ continua mostrant `upgradeBox`.

**Impacte**: Bug present en producció (`https://project-helper-47.emergent.host`). Fix aplicat a preview; cal **redesplegament** perquè els nous compradors web vegin la UI correcta.

**Fitxer modificat**: `/app/frontend/public/subscription-success.html` (funció `_isRealInstallId`)


## Session Feb 24, 2026 (Fix ràpid · z-index modal ajuda GIC + Verifactu ajornat)

**Bug reportat**: Al mòdul SMS, clicar el botó `❓` obria el modal d'ajuda **darrere** del modal SMS pare — la captura del GIC quedava tapada.

**RCA**: El modal SMS pare té `z-index: 10000` (inline a `#smsModal.style`), però el modal d'ajuda usa la classe `.modal-back` amb `z-index: 1000`. Diferència de 10× → l'ajuda quedava enterrada.

**Fix** (`/app/frontend/public/v2.html · openGicHelpModal`): sobreescrit `back.style.zIndex='100000'` (10× per sobre del SMS modal). Verificat via `elementFromPoint()` — el punt central de la captura ara pertany al modal d'ajuda. ✅

**Verifactu ajornat**: El propietari ha demanat deixar la configuració Verifactu pel futur (no sap encara si obrirà empresa o farà autònom). Reverits els canvis a `/app/backend/routes/payments.py` — es manté només el `tax_id_collection={"enabled": True}` que ja hi era abans (permet als clients introduir el seu NIF/CIF al checkout, apareix a les factures Stripe generades).


## Session Feb 24, 2026 (Follow-up · Guia GitHub Pages actualitzada · només 1 fitxer)

**Petició del propietari**: Actualitzar la guia de client al GitHub Pages (`medicarplus.es/guia-client-installacio.html`) perquè inclogui el nou pas 7 SMS amb la plantilla GIC.

**Canvis**:
1. `/app/frontend/public/guia-client-installacio.html · L196`: rutes de descàrrega canviades a URLs **absolutes** (`https://project-helper-47.emergent.host/downloads/gic-templates/F_revision_con_telefono_y_movil.lst`) → així només cal pujar 1 fitxer HTML al GitHub, sense necessitat de replicar la carpeta `downloads/gic-templates/`.
2. Creat `/app/GUIA_ACTUALITZAR_GUIA_SMS_GITHUB.md` amb passos pas-a-pas (3 min): descarregar del preview → pujar al repo `Medicarplus/medicarplus.es` → verificar a `medicarplus.es/guia-client-installacio.html`. Inclou troubleshooting per problemes comuns (cache, ruta absoluta, tipus de guardat HTML).

**Verificació**:
- URL absoluta al fitxer HTML apunta a producció (`project-helper-47.emergent.host/downloads/gic-templates/F_revision_con_telefono_y_movil.lst`) → HTTP 200 · 4898 bytes. ✅
- Callout groc del Pas 7 renderitza correctament amb els 6 passos i el botó daurat "📥 Descarregar plantilla GIC".
- El botó funcionarà idènticament des de `medicarplus.es/guia-client-installacio.html` (GitHub Pages) i des de `project-helper-47.emergent.host/guia-client-installacio.html`.


## Session Feb 24, 2026 (Bug fix P0 · "Asistencia remota" · Error enviando per email buit)

**Bug reportat**: Al Support Hub → "Asistencia remota", omplir només telèfon + descripció (sense email) mostrava "⚠️ Error enviando" i no arribava res a Discord. Present tant a preview com a **producció**.

**RCA**: `RemoteAssistPayload.email: Optional[EmailStr] = None` — Pydantic v2 rebutja `""` (cadena buida) enviada pel frontend amb "value is not a valid email address: An email address must have an @-sign" → retornava 422 → el frontend mostrava toast d'error genèric.

**Fix** (`/app/backend/routes/support.py`): afegit `@field_validator("email", mode="before")` que converteix `""` o whitespace-only a `None` abans que Pydantic validi el format. Emails vàlids no s'alteren.

**Verificat**: 
- Payload amb `email:""` → `{ok:true, discord_sent:true}` ✅
- Payload amb email vàlid → continua funcionant ✅

**⚠️ IMPORTANT**: Bug present a producció. Cal **redesplegar** perquè els clients puguin sol·licitar assistència remota sense email.


## Session Feb 24, 2026 (Anti-abuse investigat + badge visibility al panell admin)

**Reportat**: Marc no rebia alertes Discord quan provava múltiples trials amb `marcbrugulat@hotmail.com` a producció.

**Diagnosi**:
- Test E2E al preview: 2 crides consecutives al mateix email → 2n trial correctament marca `flags=['email idèntic','mateixa IP','mateixa empresa']` → **Discord webhook retorna HTTP 204** (success).
- Conclusió: **producció executa versió antiga sense anti-abuse**. Cal redesplegar.

**Millora afegida com a segona font de veritat al panell admin**:
- `models/license.py · LicenseRecord`: nou camp `abuse_flags: Optional[list[str]] = None`.
- `routes/licenses.py · _doc_to_record`: propaga `abuse_flags` a la resposta de `GET /api/licenses`.
- `admin.html`: 
  1. Badge taronja `⚠️ N FLAGS` a la columna Centre/Email de cada fila flagged, amb tooltip complet al hover (data-testid `abuse-flag-badge-{install_id}`).
  2. Al modal "Detall" nova entrada `⚠️ Senyals d'abús` amb `<ul>` desglossant els flags.

**Verificat visualment** (Playwright): la llicència `CD-TRIAL-PENDING-F056105` mostra `⚠️ 3 FLAGS` amb tooltip complet ("email idèntic · mateixa IP · mateixa empresa").

**⚠️ Cal redesplegar producció** perquè l'anti-abuse funcioni a `.host` i el badge apareixi al panel admin de prod.


## Session Feb 24, 2026 (Traducció · guia-client-installacio.html català → castellà)

**Reportat pel propietari**: El PDF `guia-instalacion-medicar-plus.pdf` que reben els clients al comprar/subscriure's estava en català. Ha d'estar en castellà per coherència amb el públic objectiu.

**RCA**: El PDF es genera dinàmicament des de `/app/frontend/public/guia-client-installacio.html` (referenciat a `mailer.py L38 · GUIDE_ATTACHMENTS`). El fitxer HTML tenia `<html lang="ca">` i tot el contingut en català heretat del propietari.

**Fix**: Reescrita `guia-client-installacio.html` (459 línies) 100% en castellà (`lang="es"`) + creada versió catalana `guia-client-installacio-ca.html` a partir del git log per preservar la traducció catalana. Selector d'idioma afegit al capçal de les dues versions amb pill daurada per l'idioma actual i botó/enllaç per l'altre.

**Data-testids**: `lang-switcher`, `lang-current`, `lang-switch-ca`, `lang-switch-es`.

**Verificat E2E** (Playwright):
- Pàgina per defecte castellana → `lang="es"`, H1 "Cómo instalar MediCar Plus", pill = "🇪🇸 Castellano".
- Clic al botó "🇦🇩 Català" → navega a `/guia-client-installacio-ca.html` → `lang="ca"`, H1 "Com instal·lar MediCar Plus".
- Clic al botó "🇪🇸 Castellano" → torna a la versió per defecte.
- Selector amb classe `no-print`: no apareix al PDF generat via `downloadAsPDF()`.

**⚠️ IMPORTANT**: Cal **redesplegar producció** i **pujar 2 fitxers a GitHub Pages** (castellà i català):
1. `guia-client-installacio.html` (castellà, per defecte, ja pujat un cop però ara amb selector)
2. `guia-client-installacio-ca.html` (nou fitxer català)


---

## 🔤 [28-Feb-2026] Traducción total al Español del módulo IRPF + auditoría global (v2.html)

**Problem**: El usuario reportó ("eres idiota de campeonato") que el módulo IRPF seguía apareciendo en catalán aunque el resto de la aplicación ya se había traducido al español. Todo el `Sobre IRPF`, el `Resumen trimestral`, y los diálogos de confirmación/toasts estaban con cadenas catalanas hardcodeadas.

**Fix aplicado** (`/app/frontend/public/v2.html`):
- IRPF modal (líneas 2762-3180): traducidos botón `Tancar → Cerrar`, `Resum trimestral → Resumen trimestral`, `Ingressat el/Import → Ingresado el/Importe`, `SOBRE IRPF` completo (título, subtítulo, párrafo, cabeceras DATA/IMPORT/NOTA → FECHA/IMPORTE/NOTA, `Cap retirada encara → Ninguna retirada todavía`, `TOTAL AL SOBRE → TOTAL EN EL SOBRE`, `Ja tens prou / Encara falta → Ya tienes bastante / Aún falta`, `Pendent Hisenda/Diferència → Pendiente Hacienda/Diferencia`).
- Confirmodals y toasts internos IRPF: `Marcar q com a ingressat`, `Segur que vols revertir`, `Esborrar retirada`, `Sí, esborrar`, `Import ha de ser > 0`, `Afegit al sobre` → todos con versión española directa (con branch `currentLang==='ca'` fallback preservada).
- `monthLabel` IRPF: nombres de meses ahora usan `['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic']` cuando lang=es.
- Print header IRPF: `Retenció → Retención`.
- Libro Diario (accounting rows generation, líneas 2469-2578): `Assentament del dia → Asiento del día`, `Total en Caixa → Total en Caja`, `QUADRA/NO QUADRA → CUADRA/NO CUADRA`, `Diferència → Diferencia`, `Balanç per comptes → Balance por cuentas`, `Compte → Cuenta`.
- Chip HABER (línea 431): `Ingresso en metàl·lic → Ingreso en metálico`.
- Buscador (línea 6406): `Cap resultat per → Ningún resultado para`, `RESULTAT(S) → RESULTADO(S)`.
- Validación del wizard `showConfigWizard` (línea 7757): `Has d'omplir el nom de l'Empresa 1 → Debes rellenar el nombre de la Empresa 1`, y validación de socios `La suma dels % dels socis és ... → La suma de los % de los socios es ...`.

**Verificación**: 
- Sintaxis JS: `node -e` sobre todos los `<script>` → `ALL SCRIPTS PARSE OK`.
- Screenshot Playwright del modal IRPF con datos de prueba: renderiza 100% en Español (Cerrar, Resumen trimestral, Sobre IRPF, Añadir persona, Marcar como ingresado a Hacienda, etc).
- Búsqueda automatizada de 27 palabras catalanas en `document.body.innerText` con modal IRPF abierto → **0 coincidencias**.

**Recordatorio para el usuario**: Ejecutar **Redeploy a producción** para que estos cambios (más los anti-abuse, backups V4, traducciones previas de "Libreta"/"Estadísticas"/"Programa Referidos") lleguen a `project-helper-47.emergent.host`.


### [28-Feb-2026] · Extensión P2 · CHANGELOG + Cuentas contables al Español

**Cambios**:
1. **CHANGELOG interno de Novedades**: versiones 2.1.0, 2.1.1, 2.1.2 y 2.1.3 traducidas del catalán al español (todos los highlights). Las versiones 2.0.25-2.0.69 ya estaban en español desde antes.
2. **Cuentas contables del Libro Diario** (`v2.html` líneas 2469-2572):
   - `570 Caixa` → `570 Caja`
   - `572 Banc / Banc (Bizum) / Banc (Transf)` → `572 Banco / Banco (Bizum) / Banco (Transf)`
   - `705 Ingressos serveis / serveis mèdics / tasas` → `705 Ingresos servicios / servicios médicos / tasas`
   - `629 Despeses` → `629 Otros servicios` (nomenclatura PGC estándar España)
   - Conceptos autogenerados: `Ingrés manual → Ingreso manual`, `Despesa → Gasto`, `Servei - X → Servicio - X`, `Reclassificació · Efectiu ↔ Datàfon manual → Reclasificación · Efectivo ↔ Datáfono manual`.
   - Todas las referencias de bucketing (`bucket['570 Caja']` etc.) actualizadas consistentemente para evitar KeyError en las agregaciones diarias.

**Verificación**: JS parse OK, screenshot Playwright del modal "¿Qué hay de nuevo?" muestra texto 100% español, auditoría automatizada de 45+ palabras catalanas devuelve **0 coincidencias**.


---

## 🔐 [28-Feb-2026] · Login ADMINISTRADOR (second Master path) + Botón "Panel Licencias"

### 1. Login `ADMINISTRADOR` + contraseña (paralelo a la MASTER key)
- **UX**: enlace `🔐 ¿Eres administrador?` bajo el botón ACTIVAR LICENCIA en la pantalla de activación. Al hacer clic despliega campos Usuario + Contraseña.
- **Usuario**: `ADMINISTRADOR` (case-insensitive). **Contraseña**: `Mbrugulat24` (case-sensitive).
- **Backend**: `/app/backend/routes/auth_admin.py` · `POST /api/auth/admin-login`. Bcrypt cost 12 · comparación constante-time · brute-force 5 intentos/15min por IP (in-memory).
- **Env vars** en `/app/backend/.env`: `ADMIN_LOGIN_USERNAME`, `ADMIN_LOGIN_PASSWORD_HASH`.
- **Ambas vías funcionan en paralelo** (MASTER key + ADMINISTRADOR login).

### 2. Botón "🎛️ Panel Licencias" en modal 🔐 Información de licencia
- Aparece sólo cuando `lic.type === 'MASTER'`, dentro del bloque VISTA PREVIA DE PLAN.
- Abre `/admin.html` en pestaña nueva con `#token=<ADMIN_TOKEN>` en el hash → auto-login instantáneo (`admin.html` lee y limpia el hash al DOMContentLoaded). El fragmento URL no llega al servidor.

### Verificación (curl + Playwright)
- `POST /api/auth/admin-login` responde correctamente 200/401/429.
- Flujo E2E Playwright: rellenar `administrador` + `Mbrugulat24` → click submit → localStorage guarda la licencia MASTER → app recarga en modo owner.

### Rotación futura de la contraseña
`python -c "import bcrypt;print(bcrypt.hashpw(b'NUEVA_PASS', bcrypt.gensalt()).decode())"` → sustituir `ADMIN_LOGIN_PASSWORD_HASH` en `.env` → `sudo supervisorctl restart backend`.


---

## 🪗 [29-Jul-2026] · Modo acordeón en menú superior (v2.html)

### Problema
Los 4 desplegables superiores (Copias de seguridad, Contabilidad, Estadísticas, Utilidades) podían quedar abiertos simultáneamente, ensuciando la vista.

### Solución
- Añadido helper `closeTopMenus(exceptId)` en `v2.html` (~línea 2364) que cierra los 3 menús no seleccionados.
- Los 4 handlers de toggle (`#btnBackupToggle`, `#btnAccountingToggle`, `#btnStatsToggle`, `#btnUtilitiesToggle`) llaman a `closeTopMenus()` antes de abrir el suyo → solo un menú visible a la vez.

### Verificación
Playwright automatizado con licencia MASTER inyectada: los 4 pasos (Contabilidad → Estadísticas → Utilidades → Copias de seguridad) confirman `ACCORDION OK ✅` — al abrir uno, los otros 3 quedan `display:none`.

---

## 📧 [29-Jul-2026] · Notificación email al admin cuando pago Stripe falle/recupere (P1)

### Objetivo
Alertar al admin **automáticamente** por email cuando un cliente entra en rojo (pago fallido) y cuando se recupera al verde, sin necesidad de mirar el panel.

### Implementación
- **`backend/services/admin_notifier.py`** (nuevo)
  - `notify_payment_failed(...)` → email 🚨 rojo con importe, install_id, contador intentos fallidos, enlace hosted_invoice_url y CTA al panel.
  - `notify_payment_recovered(...)` → email ✅ verde con datos del cobro exitoso.
  - Ambos usan `services.mailer._send_smtp` (IONOS ya configurado).
  - Formatos en español (`29,90 €`, fechas UTC legibles).
- **`backend/server.py`** — hooks dentro del webhook Stripe:
  - `invoice.payment_failed` → tras `payment_health="red"`, dispara `notify_payment_failed`. Marca `payments.admin_notified_failed=true` para **idempotencia** (Stripe reintenta el webhook).
  - `invoice.paid` → si la licencia estaba en rojo o tenía `failed_invoices_count > 0`, resetea a 0 y dispara `notify_payment_recovered`. Marca `payments.admin_notified_recovered=true`.
- **Env** (`backend/.env`):
  - `ADMIN_NOTIFY_EMAIL=info@medicarplus.es`
  - `ADMIN_PANEL_URL=https://medicarplus.es/admin.html`

### Verificación
- **Unit tests** (`tests/test_admin_notifier.py`): 4/4 pasan — recipient, subject, cuerpo HTML, override de env, fallback si SMTP no configurado.
- **E2E** (`tests/test_stripe_payment_notifications_e2e.py`): pasos A y B pasan — 1 email al fallar, idempotencia en reintentos del webhook, 1 email al recuperar, `failed_invoices_count` vuelve a 0.



---

## 🔎 [30-Jul-2026] · Panel Admin · Diagnóstico Instalaciones + Buscador Pagos

### Instalaciones · Resumen de BD (diagnóstico)
Cuando el admin ve pocos resultados y sospecha filtros ocultos, ahora tiene:
- **Endpoint nuevo** `GET /api/admin/installations/debug/summary` → devuelve `total_in_db`, `active`, `revoked`, `with_linked_email`, `platforms` (electron/web), `last_24h` (nuevas + activas), y `recent_10` heartbeats.
- **Cabecera del panel Instalaciones**: nuevo banner con `📊 Total en BD: N · 🟢 activas · 🚫 revocadas · 🖥 Electron · 🌐 Web · 🆕 24h · 👁 activas 24h`.
- **Logging mejorado** en `POST /api/install/track`: cada heartbeat se registra con `logger.info` (NEW vs existing + IP + platform + seen_count) → visible en logs de Emergent para debug de clientes con firewall.

### Pagos · Buscador global (P1 completada)
Antes había que scrollear los "Últimos 10 pagos". Ahora:
- **Endpoint nuevo** `GET /api/admin/payments/search?q=...` → busca por `email`, `install_id`, `client_name`, `company_name`, `license_key`, `id`, `stripe_subscription_id`, `invoice_id`. Devuelve **tarjeta enriquecida por cliente** con: totales, contador facturas, `failed_count`, salud, plan, y lista COMPLETA de invoices (paid + failed/open).
- **Input** `🔎 Buscar por email, install_id, nombre, apellidos…` en la cabecera de Pagos. Debounced 350ms.
- **Render** tarjeta con nombre, email, install_id, total pagado grande, badge `⚠️ N fallidos` si aplica, tabla de facturas con enlace directo a Stripe (`hosted_url`).

### Verificación
- Curl `GET /api/admin/payments/search?q=recovery` → 200, devuelve cliente con 2 invoices.
- Curl `GET /api/admin/installations/debug/summary` → 200, devuelve totales correctos.
- Screenshot Playwright: buscador Pagos + resumen Instalaciones renderizan correctamente en admin.html.


---

## 🔔 [30-Jul-2026] · Panel Notificaciones + verificación auto-renewal Stripe

### Nueva colección `notifications` + feed en admin panel
- **Backend** `routes/admin_notifications.py`: helper `create_notification()` + endpoints `GET /api/admin/notifications`, `/badge`, `POST /{id}/read`, `/mark-all-read`, `DELETE /{id}`, `/cleanup?days=90`. Tipos: `install_new`, `payment_failed` (critical), `payment_recovered`, `subscription_canceled` (warning), `plan_upgrade`, `plan_downgrade`.
- **Hooks automáticos** en `server.py` (webhooks Stripe) e `installations.py` (heartbeat). Idempotencia via `dedupe_key` (invoice_id / sub_id / install_id).
- **Frontend `admin.html`**: botón `🔔 Notificaciones` en cabecera con badge rojo pulsante (`pulse-critical`) cuando hay críticas sin leer. Panel fixed top-right con auto-refresh 60s.
- **Fixes UX de la misma iteración**:
  - `plan_family || plan || '?'` — resuelve el "?" que aparecía en todas las filas.
  - Badge dispositivos `N/M dispositivos` en vez de `#N de M`.
  - Modal `showDevicesModal(license_jti)` al click en badge: tabla con rol/install_id/última conexión/IP/estado/acciones.

### Verificación auto-renewal Stripe
- **`tests/test_stripe_autorenewal_e2e.py`**: simula renovación mensual (+30d) y anual (+365d) llamando directamente a `_sync_license_from_subscription()` con dos payloads Stripe consecutivos. Confirma que `expires_at` y JWT `exp` claim se actualizan correctamente en ambos casos.
- **📧 Facturas por email**: gestionadas 100% por Stripe Dashboard → Settings → Emails. Recordarle al usuario activar "Email customers about successful payments" y "failed payments".


---

## 🚀 [30-Jul-2026] · Guía de Migración TEST → LIVE creada

Marc confirma que **seguimos en TEST** hasta tener datos fiscales completos (~Oct 2026).
Toda la configuración actual y el paso a paso LIVE están en:

📄 **`/app/memory/STRIPE_LIVE_MIGRATION_GUIDE.md`** ← consultar antes de tocar Stripe LIVE

Incluye:
- Estado actual TEST (price_ids, webhook secret, emails activados en Dashboard)
- Precondiciones (datos fiscales, IBAN, backup DB)
- 17 pasos ordenados: crear productos LIVE → nuevo webhook secret → actualizar `.env` prod → deploy → verificación E2E con dinero real
- Sección Verifactu (aplicación posterior 2027)
- Avisos críticos: NO confundir preview/prod, price_ids distintos test/live, install_ids no migrables automáticamente

**Estado a día de hoy**:
- ✅ Toggles Stripe Dashboard activados por Marc en TEST: "Pagos correctos" + "Reembolsos"
- ⏳ Pendiente Marc en Billing → Automations: fallos de pago + Smart Retries + recordatorios
- ✅ Nuestro backend maneja correctamente TODOS los eventos webhook (validado E2E)


---

## 🔎 [26-Feb-2026] · Buscador Global con Sinónimos + Fix Honorarios

### Buscador Global de Operaciones (Contabilidad → 🔎 Buscar operaciones)
- Nueva función `openBuscadorOperaciones()` en `v2.html` con sistema de **matching por dimensiones semánticas**:
  - `FLOW`: INGRESO (ingreso/entrada/cobro/haber/abono) vs GASTO (gasto/despesa/pago/debe/cargo/compra)
  - `FP`: EFECTIVO (metálico/cash) · BANCO (tarjeta/transferencia/TPV) · BIZUM · OTROS_FP (cheque/talón)
  - `CONCEPT`: HONORARIOS · IRPF · IVA · MATERIAL · TASAS · DGT · LUZ · AGUA · ALQUILER · GESTORIA · SEGURO
  - `SERVICE`: RENOVACION · DUPLICADO · CANJE · CAMBIO · CICLOMOTOR · MEDICAR · CEMPLA
- **Semántica**: OR intra-dimensión (efectivo O banco) · AND entre dimensiones (ingreso Y efectivo)
- Normalización con `NFD` (elimina acentos), tolera mayúsculas y frases multi-palabra ("paga trabajador")
- Coincidencia semántica adicional por estructura: INGRESO matchea TRAF/PRIV/HABER · EFECTIVO matchea `fp='E'` · etc.
- UI muestra la interpretación detectada como chips (ej: `FLOW: INGRESO · FP: EFECTIVO o BANCO`)
- Rango de fechas obligatorio · resultados ordenados por fecha desc · suma total de importes
- Data-testids: `buscador-global-modal`, `-query`, `-from`, `-to`, `-run`, `-close`, `-results`, `-count`

### Fix Honorarios (Panel `openHonorariosPanel`)
- **Bug detectado**: la detección anterior buscaba `e.concepto === 'Honoraris'` pero el campo real es `e.nombre` → panel nunca detectaba nada.
- Nueva función `_isHonorarioLikeEntry(e)` que reconoce cualquier DH con importe > 0 cuyo `nombre/tipo/concepto/grupo` contenga: `honorari`, `honorario`, `honoraris`, `nomina`, `sueldo`, `salario`, `salari`, `paga trabajador`, `pago empleado`, `empleado`.
- `_cleanWorkerName()` limpia el prefijo (ej: "Nomina Pep Brugulat" → "Pep Brugulat") para agrupar correctamente por trabajador.

### Testing E2E
Playwright script con dataset de 8 entradas cubre 5 escenarios (todos ✅):
- `ingreso efectivo` → 2 · `metalico` → 3 · `ingreso efectivo banco` → 6 · `gasto banco` → 1 · Panel Honorarios agrupa Nomina+Sueldo+Honoraris en 2 trabajadores.


---

## 💼 [26-Feb-2026] · Honorarios: Selector de mes + Faenas externas + Imprimir

### Panel Honorarios ampliado
- **Selector de mes** en la cabecera con todas las opciones de meses con datos + "📆 Todos los meses". Por defecto abre en el mes actual.
- **Categorías detectadas** (con colores propios): `NOMINA` (verde) · `SUELDO` (cian) · `SALARIO` (violeta) · `HONORARIO` (dorado) · `FAENA_EXT` (naranja).
- **Faenas externas** ahora reconoce: `faena`, `faena externa`, `feina externa`, `jornal`, `jornales`, `colaborador`, `freelance`, `autónomo`, `externa`, `subcontrata`, `trabajo externo`.
- **Chips resumen por categoría** en la parte superior (ej: "Sueldo · 1 pago · 1400 €").
- **Tabla trabajadores** ahora muestra badge de tipo (Nómina/Sueldo/Faena externa) junto al nombre.
- **Detalle mensual** con badge coloreado por categoría en cada fila.
- Diccionario `_HN_KEYWORDS` centralizado con función `_hnMatchKeyword()` para clasificar cualquier entrada.
- `_cleanWorkerName()` ampliado para retirar prefijos "faena externa", "jornal", "colaborador", "autónomo", etc.

### Impresión
- Botón `🖨️ Imprimir` que llama a `printVisibleElement(modal, {...})` con CSS específico:
  - Oculta controles interactivos (`.no-print, select, button`)
  - Fuerza fondo blanco y texto negro sobre tabla legible
  - Título dinámico: `Honorarios · <mes seleccionado>` o `Honorarios · Todo el histórico`
  - Consistente con IRPF, Libro de Registro, Estadísticas Tráfico.

### Sincronización con Buscador Global
- Categoría HONORARIOS del diccionario `CAJA_SEARCH_DIMENSIONS.CONCEPT` ampliada con los mismos sinónimos de faenas externas → una búsqueda como "faena externa" o "jornal" en el Buscador devuelve todos los pagos relacionados.

### Testing E2E validado
- Enero 2026: 3130€ (4 pagos · Sueldo/Nómina/2 Faenas externas) ✅
- Febrero 2026: 1920€ (3 pagos · Honorario + 2 Faenas externas) ✅
- Todos los meses: 6250€ ✅
- Búsqueda "faena externa" en Buscador Global: 8 resultados ✅
- Botón Imprimir presente y activable ✅


---

## 🧠 [26-Feb-2026] · Autocompletar Trabajador en Debe/Haber

### Autocompletado nativo con `<datalist>`
- Nuevo `<datalist id="dh-workers-datalist">` conectado al input `#dh-concepto`.
- Función `_getKnownWorkers()` extrae nombres únicos limpios de trabajadores desde todas las entradas históricas honorario-like (DH con nombre/tipo/concepto que contenga: honorari · nomina · sueldo · salario · jornal · faena · colaborador · autónomo · etc.).
- Función `refreshWorkersDatalist()` genera opciones combinadas: `Nómina <Worker>`, `Sueldo <Worker>`, `Salario <Worker>`, `Honoraris <Worker>`, `Faena externa <Worker>` + los nombres raw para sugerencia libre.
- Refresco automático en 4 momentos:
  1. Al cargar la app (setTimeout 500ms)
  2. Al hacer clic en la pestaña "Debe/Haber"
  3. Al hacer focus en el input concepto
  4. Después de añadir una nueva entrada DH (`saveState`)

### UX mejorado en chips
- Al hacer clic en un chip de trabajador (Honoraris/Nómina/Faena externa), el input se rellena con `<keyword> ` (con espacio final) y recibe foco al final del texto → el navegador muestra automáticamente las sugerencias del datalist filtradas por ese prefijo.
- Otros chips (IRPF, Material, etc.) mantienen el comportamiento anterior (foco al importe directamente).

### Testing E2E validado
- 4 trabajadores detectados de dataset histórico ✅
- 24 opciones datalist (4 workers × 5 prefijos + 4 raw) ✅
- Chip "Nómina" → input="Nómina ", tipo=DEBE, foco correcto ✅
- Al añadir "Juan Rodriguez" el datalist se actualiza automáticamente ✅


---

## 📥 [26-Feb-2026] · Fix Import CSV Estadísticas Autoescuelas

### Bug crítico solucionado
- **Silent failure en Electron**: la función usaba `prompt()` del navegador para pedir el mes, pero Electron lo tiene deshabilitado por defecto → el usuario clicaba "Importar CSV", subía el archivo, y "no pasaba nada".
- **Parser rígido**: sólo aceptaba `;` como separador. CSVs con `,` fallaban silenciosamente.

### Solución implementada en `openStats('autos')`
1. **Selector `#stImportMonth` visible en la toolbar** (data-testid `st-import-month`), aparece junto al botón "Importar CSV" con clase `st-autos-only` (solo visible en la sección Autoescuelas). Default = mes actual.
2. **Autodetección de separador**: analiza la primera línea del CSV y detecta si usa `;`, `,` o `\t` automáticamente.
3. **Encoding fallback mejorado**: prueba UTF-8 primero, si falla o detecta `�` cae a Windows-1252 (los CSVs exportados desde Excel/Access suelen ser cp1252).
4. **Mensaje de error más útil**: si el CSV no contiene filas válidas, indica el formato esperado `"CODIGO";"TOTAL"`.

### Testing E2E con CSV real (Junio 2026 · 30 filas)
- 613 certificados totales ✅ (exacto)
- 24 autoescuelas detectadas ✅
- STAT_ALIAS mapea automáticamente para MASTER users (TRÀFIC, MABEL→A.E.MABEL, DAINA→A.E.DAINA, etc.)
- Agregación de códigos duplicados funciona (PARTICULAR ×4 → suma 64)
- Datos guardados en `caja.stats.v1` bajo la key `2026-06`
- Botón data-yes del confirmModal ejecuta `doApply()` correctamente


---

## 📈 [26-Feb-2026] · Edit inline + Gráfico Evolución Autoescuelas + Print CSS

### Fixes UX en Estadísticas Autoescuelas
1. **Edit inline reemplazando `prompt()`** (que no funciona en Electron):
   - Click en celda → aparece `<input type="number">` con foco y select automático
   - Enter/blur guarda · Escape cancela · Tab avanza a la siguiente celda
   - Colores destacados (borde amarillo #f5b301) para indicar edición activa
2. **Botón `+ Autoescuela` con modal custom** (elimina `prompt()`): input dedicado con validación de duplicados, botón cancelar/añadir, Enter=confirmar, Escape=cerrar.
3. **`Vaciar todo` migrado a `confirmModal`** (elimina `confirm()` nativo — más consistente y con estilo).

### 📈 Gráfico de evolución mensual (nuevo)
- Botón `📈 Gráfico` en la toolbar (solo sección Autoescuelas)
- SVG nativo (sin Chart.js) · dibujado a partir de `st.data[year-MM]`
- **Selector Top 3/6/10/20/Todas** (por default Top 6 = las más frecuentes del año)
- **Leyenda clicable**: toggle línea on/off + muestra colores + total anual por autoescuela
- **Eje Y auto-escalado** (máximo redondeado a decenas) · 5 gridlines
- **Etiquetas de valor** en cada punto (solo si >0) del color de la serie
- **12 meses** en eje X (Ene-Dic abreviados)
- **Tooltip SVG nativo** (`<title>`) en cada punto: "AUTOESCUELA · Mes: valor"
- **Botón Imprimir** con CSS específico para papel

### Print CSS reforzado (aplica a tabla principal + gráfico)
- Oculta botones/selects/inputs/toggles al imprimir
- Fondo blanco + texto negro + bordes grises legibles
- Tabla: `border-collapse:collapse`, thead con fondo `#eee`, tfoot con `#ddd`
- Landscape 8mm de margen
- Grafico: SVG con `fill:#000` para texto para preservar el color de líneas visible

### Testing E2E validado
- Edit inline guarda 99€ en celda ✅
- Modal +Autoescuela añade "TEST NUEVA ESCUELA" ✅
- Import CSV 613 certificados ✅ 
- Gráfico Top 6 dibuja 6 polylines + 6 legend items ✅
- Toggle leyenda decrementa a 5 líneas ✅
- Top 3 filtra a 3 líneas ✅
- Botón Imprimir del gráfico presente ✅


---

## 2026-02 · Panel de Gastos + Clasificación Bulletproof (DONE)

### Objetivo
Separar de forma inequívoca **Gastos del centro** (luz, agua, alquiler, papel, batas, seguros…) de **Honorarios** (pagos a trabajadores). Ambos son DEBE en la pestaña Debe/Haber pero deben contabilizarse en paneles distintos para que "los números salgan bien".

### Cambios en `v2.html`

1. **Nuevo chip rojo "🧾 GASTO"** en `#chips-dh` (línea 437):
   - `background:#4c0519; border-color:#dc2626; color:#fecaca; font-weight:700`
   - `data-role="gasto"` para trigger de comportamiento especial
   - Prefija el input con `Gasto: ` (con espacio) y enfoca el campo

2. **Chips Honoraris / Nómina / Faena externa en AZUL BRILLANTE** (antes rojos):
   - `background:#0c2340; border-color:#38bdf8; color:#7dd3fc`
   - Con emoji 💼 para distinción visual instantánea

3. **Función `_hasExplicitGastoMarker(e)`**: detecta prefijo `Gasto:` en el nombre (regex `/^gasto\s*[:\-·]/`).

4. **Regla determinista en `_isGastoEntry`**:
   - Si tiene marca explícita `Gasto:` → SIEMPRE es Gasto (gana sobre keywords)
   - Fallback: detección por keywords (LUZ, AGUA, GAS, ALQUILER, TELEFONO, INTERNET, GESTORIA, SEGURO, MATERIAL, IRPF, IVA, TASAS, MANTENIMIENTO, COMBUSTIBLE, BANCO_COM)
   - Categoría `OTROS` para gastos explícitos sin keyword conocido

5. **Exclusión mutua en `_isHonorarioLikeEntry`**:
   - Si tiene marca explícita `Gasto:` → NUNCA es honorario (aunque contenga "Nómina", "Sueldo", etc.)

### Casos edge validados E2E
| Concepto | Va a | Regla |
|---|---|---|
| `Gasto: Factura Endesa` | Gastos (LUZ) | Explícito + keyword |
| `Gasto: Reparación tejado` | Gastos (OTROS) | Explícito sin keyword |
| `Gasto: Nómina Endesa` | Gastos (LUZ) | **Explícito gana** aunque contenga "Nómina" |
| `Recibo agua Sorea` | Gastos (AGUA) | Solo keyword |
| `Nomina Maria Lopez` | Honorarios | Solo keyword honorario |
| `Honoraris Pep Garcia` | Honorarios | Solo keyword honorario |

### Testing
- 10/10 assertions pasan (validación headless via `page.evaluate` con datos ficticios).
- Verificación visual de chips en pestaña Debe/Haber ✅.

## 2026-02 (b) · Detección universal de gastos + Asesor IA con rango (DONE)

### 1. Keyword universal "OTROS"
Nuevo grupo de keywords que atrapa cualquier concepto genérico de gasto: `factura`, `recibo`, `gasto`, `despesa`, `despeses`, `pago proveedor`, `proveedor`, `compra`, `compras`. Así si el usuario escribe `Factura X` sin categoría específica → detectado como Gasto (categoría OTROS).

### 2. Asesor IA · Selector de rango de fechas
- **Nuevos inputs**: `Desde` / `Hasta` / `Descuadre` (grid 3 columnas)
- **Filtrado front-end**: si el usuario define rango, `filterByDate()` corta los datos localmente antes de enviarlos → menos tokens, más rápido, más preciso
- **Audit summary limitado al rango**: `computeAudit(dFrom,dTo)` usa el rango del usuario (o últimos 12 meses si no)
- **Prompt enriquecido**: se añade `[Rango solicitado: X → Y]` a la pregunta para que la IA lo tenga presente
- **Payload nuevo**: `dateRange:{from,to}` (opcional) enviado al backend

### 3. Casos de uso soportados
- *"Del 1/7 al 31/7 me faltan 4€, ¿puedes repasar?"* → filtra solo julio y busca candidatos que sumen 4€
- *"Busca duplicados esta semana"* → rango últimos 7 días
- *"¿Qué gastos he tenido este mes?"* → rango mes en curso
- *"Encuentra días con caja rara"* → sin rango = todo el histórico


## 2026-02 (c) · Botón "🔎 Repasar día (IA)" en Cierre del día (DONE)

### Objetivo
Acceso 1-clic al Asesor IA con el día actual pre-rellenado. Elimina la fricción de tener que ir a Utilidades → Asesor IA → escribir fechas → escribir pregunta.

### Implementación
- **Botón violeta gradient** (`data-testid="btn-review-day-ai"`) en el header del panel Cierre del día, al lado del toggle de privacidad
- **Handler delegado en document**: al pulsar, llama `#btnAiAsk.click()` y luego pre-rellena:
  - `#aiFrom` = `currentDate` (día visible)
  - `#aiTo` = `currentDate` (día visible)
  - `#aiQ` = template con la fecha en formato humano + nº de entradas del día + instrucciones de auditoría típicas
- Pone el foco al final del textarea para que el usuario pueda añadir contexto o pulsar Preguntar directamente

### Validado E2E
- Botón visible con texto correcto ✅
- Click abre Asesor IA ✅
- Desde/Hasta = fecha en curso ISO ✅
- Pregunta contiene "Repasa el día DD/MM/YYYY (X entradas)" ✅



## 2026-02 (d) · 3 bugs críticos del cliente arreglados (DONE)

### 1. Botón "Verificar" ya no se queda pensando
Rewrite del handler con `try/catch/finally` → el botón siempre se re-habilita.

### 2. Extensión de trial se sincroniza al cliente
- Backend `/verify`: si DB `expires_at` > JWT `exp`, re-emite JWT nuevo y lo devuelve como `new_key`
- Modelo: `LicenseVerifyResponse.new_key: Optional[str]`
- Frontend: detecta `new_key`, `saveLicense()` con nueva `expires`, `location.reload()`
- Aplica también al verify silencioso en `isLicenseActive()`

### 3. Modal de licencia 100% en español
Traducidas todas las cadenas hardcoded catalanas + `toLocaleDateString('es-ES')`.

### 4. Endpoint reenvío instalador (nuevo)
- `POST /api/admin/licenses/{key}/resend-download` (con `override_email` opcional)
- Envía HTML desde `info@medicarplus.es` con enlace + Install ID + Clave
- Botón "📩 Reenviar programa" por licencia en `admin.html`

### Validación E2E
- Backend curl: 7/7 tests pasan
- Frontend Playwright: modal español + verify aplica new_key (25/9→24/12/2026) ✅
- Endpoint reenvío: 401 sin auth, 404 licencia fantasma ✅

### Pendiente (usuario)
Subir `MediCarPlus-Setup.exe` compilado a `/app/frontend/public/downloads/` para que el enlace `https://medicarplus.es/downloads/MediCarPlus-Setup.exe` funcione.


## 2026-02 (e) · 4 mejoras completas del sistema de licencias (DONE)

### 1. Página de descargas · `/app/frontend/public/downloads/index.html`
- Landing bonita en español con branding MediCar Plus
- Botón principal → GitHub Releases (`github.com/Medicarplus/medicarplus-releases/releases/latest`)
- Instrucciones paso a paso (5 steps) de reinstalación
- Sección "¿Perdiste tu clave?" con mailto:info@medicarplus.es
- Warning HWID binding + soporte

### 2. Panel admin rediseñado · `admin.html openDetail()`
- Cabecera con nombre grande + estado con emoji semáforo (🟢🟡🟠🔴⚫) + expiración destacada con contador de días
- Grid `[+7d] [+15d] [+30d] [+90d] [+1año] [-7d] [⚙ Personalizado]` con gradients por color
- Botones "Reenviar programa" · "Copiar clave" · "Copiar Install ID" grandes
- Datos técnicos y SMS en `<details>` colapsables (no ensucian)
- Panel principal traducido: "Total licencias", "Activas", "Todos los estados", "Sin conexiones", "Hace Xd", "Detalle", "Salir"…

### 3. Email automático al extender trial · `licenses.py adjust_trial_days()`
- Al hacer +X días desde admin, se envía HTML formateado al `client_email` desde `info@medicarplus.es` (IONOS SMTP)
- Contenido: nueva fecha destacada + instrucciones "1) Abrir app 2) Pulsar 🔐 3) Pulsar Verificar ahora"
- Response del endpoint incluye `email_notified: bool` para feedback en admin
- Alert del admin ahora muestra "📧 Hemos avisado al cliente por email"

### 4. Verify Auto al abrir modal · `v2.html showLicenseInfo()`
- Al abrir el modal de licencia (candado), lanza `verifyOnline()` en background automáticamente
- Banner animado "Comprobando actualizaciones..." con spinner CSS
- Si detecta `new_key` → aplica silenciosamente + banner verde "✅ Licencia actualizada" + reload a los 2s
- Si server responde OK sin cambios → banner verde "✅ Al día" y desaparece
- Si server rechaza → banner rojo con motivo
- Si sin conexión → banner naranja "Trabajando offline"
- Robusto: nunca bloquea la UI

### Testing E2E (todos pasan)
- Página descargas: 4/4 checks (título, instrucciones, GitHub link, contacto)
- Modal admin rediseñado: 8/8 checks (Ficha, nombre, estado, +30d, +1año, Reenviar, Datos técnicos, SMS)
- Extend con email: `email_notified: true`, `new_expires_at: 2026-10-25`
- Verify auto: banner aparece + reemplaza con `new_key` si cambia

## 2026-02 (f) · Panel admin: filas, referidos, empresas (DONE)

### 1. Rediseño de filas de tabla · `admin.html applyFilters()`
- 10 columnas → 6 columnas (Cliente · Plan/Estado · Expira · Actividad · SMS · Acciones)
- Cada fila con `border-left:4px solid ${sem.color}` (semáforo lateral)
- Semáforo emoji + nombre grande en gold Georgia serif + email + install_id acortado + botón `📋` inline
- Click en la fila entera abre `openDetail()` (con hover background)
- Días restantes con color según urgencia (rojo <7, naranja <30, verde >30)
- Botón "Detalle" con gradient gold prominente

### 2. Sección "Programa de referidos" · `openDetail()`
- 3 tarjetas grandes: **Ha traído N personas · Meses ganados · Ahorro estimado €** (asumiendo 15€/mes)
- Código propio (con botón copiar) + quién le invitó (`referred_by`)
- Últimas 5 recompensas con email + meses añadidos + fecha
- Data leída de `l.referral_rewards[]` (ya guardado por el sistema de referidos existente)

### 3. Sección "Empresas y datos del cliente" · `openDetail()`
- Muestra `Empresa 1` y `Empresa 2` (o "No usa segunda empresa" si solo tiene una)
- Indica **📊 Usa 1 sola / 2 empresas**
- Metadata técnica: plataforma (electron/web), versión app, locale
- Timestamp de última sincronización

### 4. Sincronización client_meta · verify endpoint
- Frontend `verifyOnline()` ahora envía `client_meta` con `company1_name`, `company2_name`, `uses_two_companies`, `app_version`, `platform`, `locale`
- Backend model `LicenseVerify.client_meta: Optional[dict]`
- Endpoint verify sanea (máx 20 campos, strings ≤500 chars) y persiste en `licenses.client_meta` + `client_meta_updated_at`
- Se sincroniza automáticamente en cada verify (auto + manual)

### Testing E2E
- Backend curl: client_meta persiste tras verify ✅ + `client_meta_updated_at` timestamp ✅
- Frontend playwright: modal muestra Empresa 1, Empresa 2, "Usa 2 empresas", referidos, código, meses ganados, emails recompensa ✅
- Tabla: filas rediseñadas visuales OK ✅

- Panel admin ES: 8/10 palabras esperadas, 0 catalán restante


## 2026-02 (g) · Chat bidireccional cliente ↔ admin (DONE)

### 1. Buscador con botón
- Botón `🔎 Buscar` con gradient dorado + botón `✕` limpiar · ejecuta al Enter

### 2. Chat de soporte bidireccional
**Backend** (`routes/admin_support.py`): 
- Admin: `send-support`, `support-history` (con `unread_count`), `mark-read`
- Público: `POST /api/support/client-message` (autenticado por install_id + license_key)
- Colección `support_messages` con `direction`, `read_by_admin_at`
- Notifica al admin por email cuando llega inbound

**Frontend v2.html**: Botón "💬 Contactar Soporte" (violet gradient) en modal licencia
**Frontend admin.html**:
- `SUPPORT_UNREAD_CACHE` precargado en `loadLicenses()` con todas las cuentas
- **Badge 🔔 N con animación pulse** en fila tabla + botón detalle
- `openSupportChat()` con historial + auto-`mark-read` al abrir + envío
- Estilos: inbound (gold border) vs outbound (blue border)

### 3. Seguridad

## 2026-02 (h) · Bandeja unificada + Adjuntos + DNI search (DONE)

### 1. Búsqueda por DNI en Estadísticas Autoescuelas
Buscador `citesSearch` (v2.html): 
- Nueva función `_normDni()` que quita espacios, guiones, puntos y pasa a mayúsculas
- Detecta patrón DNI/NIE (`[XYZ]?\d{5,8}[A-Z]?`) y busca normalizando el texto de origen
- Placeholder actualizado: "Buscar por nombre, DNI, NIE (ej: 12345678A · X1234567Z · García)"
- Tests node.js: 8/8 pasan (con y sin guiones/puntos, nombre normal, NIE)

### 2. Bandeja unificada de mensajes
Backend endpoint: `GET /api/admin/licenses/inbox-unified?unread_only=true|false&limit=100`
- Devuelve `messages[]` con `client_name`, `client_email`, `plan`, `subject`, `body` (preview 400 chars), `has_attachments`, `attachments_count`, `sent_at`, `unread`
- Devuelve `total_unread` global (independiente del filtro)
- Cross-join con licenses para enriquecer con datos del cliente

Frontend admin:
- Botón "📨 Bandeja" en topbar (violet gradient) con badge `🔔 N` pulsante
- Modal 900px con 2 tabs: "No leídos" (por defecto) · "Todos los recibidos"
- Botón ↻ Refrescar
- `refreshInboxBadge()` llamado en `loadLicenses()` para actualizar el contador global
- Click en un item → abre `openSupportChat` del cliente correspondiente

### 3. Adjuntos de imagen (cliente → admin)
Backend (`admin_support.py`):
- Campo `attachments: Optional[List[str]]` en `ClientSupportMessageBody`
- Validación: máx 3 imágenes, cada una <2.8MB base64, formato `data:image/…`
- Guardado en `support_messages.attachments`

Frontend v2.html (`Contactar Soporte`):
- Botón `📎 Adjuntar captura` con `<input type="file" accept="image/*" multiple>`
- Función `_compressImage()`: usa Canvas para redimensionar a máx 1400px + JPEG 75% calidad
- Preview 60×60 con botón ✕ para quitar cada una
- Envía en el payload `attachments: [b64...]`

Frontend admin.html (`openSupportChat`):
- Thumbnails 120×80 clicables (abren en tamaño completo en nueva pestaña)
- Icono 📎 con contador en la lista del inbox unificado

### Testing E2E (todos pasan)
Backend curl 8/8:
- Crear licencia · enviar mensaje con adjunto · enviar sin adjunto · inbox unread=2 con `attachments_count=1` · historial con adjunto 867b · mark-read=2 · inbox unread=0 · all_inbox=4

Visual: modal Bandeja abre con tabs, badge en topbar, empty state correcto en modal

Endpoint público valida: install_id existe · status=active · license_key coincide → 401 si no

### Testing E2E (8/8 pasan)
Crear trial → Cliente envía 2 msgs → Admin ve unread=2 → Admin responde → mark-read=2 → Historial 3 msgs unread=0 → Seguridad 401


---

## Feb 26, 2026 — Fixes rápidos post-deploy

### 🐛 FIX: "Reenviar programa por email" → "Sesión caducada" falso positivo
**Causa**: `admin.html` línea 345 leía el token de `localStorage.getItem('adminTok')` mientras que todo el resto del panel usa `sessionStorage.getItem('mcp.admin.token')`. El botón siempre abortaba antes de hacer la llamada.
**Fix**: cambiado el getter en `resendInstaller()` para usar el mismo storage que el resto (`sessionStorage.getItem('mcp.admin.token')`).
**Test**: Playwright login + monkey-patch fetch → `X-Admin-Token` se envía correctamente y llega a "✅ Enviado correctamente". Bug NO reproducible.

### ✨ Buscador `#searchClient` del panel Tráfico ahora acepta DNI
**Contexto**: usuario pidió buscar por DNI en el input de la parte superior del panel Tráfico (donde se sube el CSV DGT). Anteriormente sólo buscaba por nombre/tipo/grupo.
**Cambios en `frontend/public/v2.html`**:
1. `importTrafficRows` — nueva detección de columna DNI/NIE/NIF/DOCUMENTO en el CSV DGT; guarda `e.dni` en la entrada.
2. `initClientSearch` — añade `normDni()` (quita espacios, guiones, puntos, mayúsculas), busca en `e.dni` y también en `nombre` cuando la query parece un DNI/NIE.
3. Placeholder actualizado: "🔍 Buscar por nombre, apellido o DNI…" (width 260px).
4. Badge 🪪 con highlight amarillo cuando hay match.
**Tests Playwright (4/4 OK)**: `12.345.678-A` → GARCIA · `X1234567Z` → MARTINEZ · `garcia` sigue funcionando (regresión OK) · DNI parcial `12345` encuentra ambos.

### 🐛 FIX: Panel Notificaciones — "Marcar leída" no funcionaba + faltaba opción Borrar
**Causa raíz**: El botón "Marcar leída" estaba `position:absolute; top:8px; right:8px`, solapado visualmente con el timestamp del mismo item. El usuario clicaba pensando que era la fecha y no había feedback claro. Además no existían botones de borrar.
**Cambios**:
1. Backend `admin_notifications.py`: nuevos endpoints `POST /admin/notifications/delete-all-read` y `POST /admin/notifications/delete-all`.
2. Frontend `admin.html`:
   - Cabecera del panel: 3 botones bien visibles → `✔ Marcar todas leídas`, `🗑 Borrar leídas`, `🗑 Borrar todas` (rojo, doble confirmación).
   - `renderNotifItem`: los botones per-item ahora están en una **fila propia** al final del item (no absolute), con border-top dashed separador. Incluye `✔ Marcar leída` y `🗑 Borrar` (65px, altamente clicable).
   - `markNotifRead()` / `deleteNotif()`: feedback visual (btn.disabled=true, texto '…') y alert on error.
   - data-testids añadidos: `btn-notif-mark-all-read`, `btn-notif-delete-read`, `btn-notif-delete-all`, `notif-item`, `btn-notif-mark-read`, `btn-notif-delete`.
**Test Playwright**: 27 items renderizados, todos con ambos botones visibles (89×21 y 65×21). Click Marcar → badge 27→26. Click Borrar → badge 26→25. Todos los endpoints backend curl OK.


### ✨ Filtros en Panel Notificaciones
**Backend** `admin_notifications.py`:
- Nuevo mapping `_CATEGORY_TYPES`: `instalaciones` → [install_new], `pagos` → [payment_failed, payment_recovered], `avisos` → [subscription_canceled, plan_upgrade, plan_downgrade].
- `GET /admin/notifications` acepta `category` y `read_state` (`unread`|`read`|null). Compatibilidad hacia atrás con `unread_only`.

**Frontend** `admin.html`:
- Nuevos dropdowns bajo la cabecera del panel: `Todos los tipos | 🆕 Instalaciones | 💳 Pagos | ⚠️ Avisos` y `Leídas y no leídas | 📬 Solo no leídas | 📖 Solo leídas`.
- Contador de resultados en vivo alineado a la derecha ("N resultados").
- Empty state contextual cuando hay filtros aplicados.
- `loadNotifList()` construye query con URLSearchParams y renderiza en `#notifListInner` (nuevo contenedor).
- data-testids: `notif-filter-category`, `notif-filter-read`.

**Test Playwright**: 22 instalaciones + 2 pagos + 2 avisos = 26 total (coincide con badge); "Solo leídas" → 1 (sin botón Marcar); "Solo no leídas" → 26 (todas con Marcar).

### ✨ Backfill DNI no destructivo en re-importación CSV DGT
Cambio mínimo en `importTrafficRows` (`v2.html`): la lógica de dedupe pasa de `list.some(...)` a `list.find(...)`. Cuando encuentra duplicado, si `!dup.dni && e.dni` → asigna solo el DNI. Nada más se modifica.
- Contador nuevo `backfilled` mostrado en el toast final (🪪 X DNI rellenado(s) en entradas antiguas).
- Test lógico E2E (Playwright evaluate): entrada antigua sin DNI recibe DNI ✓ · entrada que ya tenía DNI intacta ✓ · entrada manual intacta ✓ · IDs preservados ✓ · nueva entrada añadida ✓ · nada borrado.
- Uso práctico: usuario vuelve a subir CSVs antiguos → DNIs se rellenan automáticamente, sin duplicar filas ni borrar nada.


### ✨ Auto-limpieza silenciosa de notificaciones (30 días)
**Backend** `admin_notifications.py`:
- `_maybe_auto_cleanup()` helper: throttle 24h, elimina docs con `read:true` y `created_at < now-30d`.
- Estado persistente en la propia collection: `{_id:"_meta", last_cleanup_at, last_cleanup_deleted}` (sobrevive reinicios del servidor).
- Trigger: se dispara en `GET /admin/notifications/badge` (que el admin auto-refresca cada 60s). Zero-config, sin cron.
- Excluye `_meta` de list / badge / delete-all vía `type:{$exists:true}` filter.
- Silent-fail: si algo va mal, sólo log warning, nunca rompe la respuesta.

**Test E2E**: insertados 4 docs sintéticos (2 leídas+45d, 1 no-leída+45d, 1 leída+5d), forzado `last_cleanup_at` a -48h, disparado badge → resultado: las 2 leídas viejas borradas, las otras 2 preservadas, `meta.last_cleanup_deleted=2`. Throttle validado: segundo badge no re-dispara.


### ✨ Bandeja Unificada: filtro por cliente + Marcar No Leído
**Backend** `admin_support.py`:
- `/inbox-unified` ahora incluye `msg_id` (string ObjectId) en cada mensaje.
- Nuevo sub-router `POST /admin/support/messages/{msg_id}/mark-unread` (limpia `read_by_admin_at` con `$unset`).
- Nuevo `POST /admin/support/messages/{msg_id}/mark-read` (individual, distinto del bulk por licencia). Ambos con validación ObjectId → 400 si malformado.
- `server.py`: `build_support_router` ahora devuelve 3 routers, montados con prefix `/api`.

**Frontend** `admin.html`:
- Cabecera del modal Bandeja: nuevo `<select id="inboxClientFilter">` populado dinámicamente desde los mensajes cargados (`install_id → client_name (count)`), ordenado alfabéticamente.
- Filtro por cliente es 100% client-side (no re-fetch, filtra el cache `lastMessages`) → respuesta instantánea.
- Cada item ahora tiene su acción abajo-derecha:
  - Si unread → `✔ Marcar leído` (verde)
  - Si read → `📬 Marcar no leído` (borde púrpura)
- Funciones `markMsgRead(msgId, btn)` y `markMsgUnread(msgId, btn)` con feedback visual (disabled + '…') y refresh del badge inbox.
- Empty state contextual cuando hay cliente filtrado sin mensajes.

**Tests E2E**:
- Curl: `msg_id` presente ✓ · mark-unread eleva `total_unread` a 1 ✓ · mark-read revierte ✓ · invalid ID → HTTP 400 ✓.
- Playwright: 3 opciones en el filtro (correcto, agrupa por install_id) · seleccionar cliente reduce items 4→2 ✓ · click "Marcar no leído" actualiza badge 0→🔔 1 ✓ · click "Marcar leído" revierte.


### 🐛 FIX: Stripe checkout falla ("Error creando la sesión de pago")
**Causa raíz**: el backend (`payments.py:177`) tenía `customer_email: str` (obligatorio) en el modelo `CreateSubscriptionBody`, pero el frontend `LandingPage.jsx` NO enviaba ese campo. Respuesta 422 → `data.url` undefined → alerta genérica.
**Fix**: `handleStripeCheckout()` ahora hace `window.prompt("📧 email de facturación")` antes del POST, con validación regex de email. También muestra `data.detail` cuando hay error del backend (mejor debug para el cliente). Backend intacto.
**Test**: curl con email → sesión Stripe creada correctamente, `checkout.stripe.com/...` URL válida devuelta.

### ✨ Landing page: 4 mejoras
1. **PROVA → PRUEBA**: 2 CTAs de la landing (`COMENZAR PRUEBA GRATIS`, `EMPEZAR PRUEBA GRATIS`) + RequestLicensePage.
2. **Trial 30 → 60 días**: sincronizado con backend `TRIAL_DAYS=60`. Ubicaciones actualizadas: cabecera precios, features del plan TRIAL, FAQ, CTA final, RequestLicensePage (subtitle + period + summary).
3. **Nueva feature "📈 Estadísticas avanzadas"**: mockup SVG completo con gráfico de barras por mes (JUL 448 / AGO 164), gráfico de tipos (EXPED 251, RENOV 351, PERIO 1, PRORR 3, RECUP 6), 4 KPIs (612 entradas, 37.250€, 5.727,19€ tasas, 42.977,19€ total) y tabla mensual. Marca "MEDICAR" como pidió el usuario.
4. **Nueva feature "📅 Calendario de citas integrado"**: mockup con 4 citas del día (Joan García 09:00 CONFIRMADA, Marta Serra 09:30 EN CURSO, etc), tabs (Hoy/Semana/Calendarios), buscador por DNI, y badge "🔔 4 citas hoy · Al importar CSV se marca quién vino".


### ✨ Editar datos cliente + sync automático (Feb 26, 2026)
**Backend `licenses.py`**:
- Nuevo modelo top-level `UpdateContactBody` con 5 campos opcionales (client_name, client_email, contact_name, phone, tax_id).
- `PATCH /api/licenses/{install_id}/contact` (admin): actualiza solo campos enviados, cadena vacía borra, None no toca. Guarda `contact_updated_at`. Audit log. Devuelve licencia completa.
- `verify_license` extendido con `_CONTACT_MAP` (12 aliases ES+EN): cuando el cliente envía `client_meta` con `company_name/empresa`, `contact_name/persona_contacto`, `phone/telefono/teléfono`, `tax_id/nif/cif`, `email/client_email` → se propaga a campos top-level de la licencia automáticamente.

**Frontend `admin.html`**:
- Botón "✏️ Editar" en el bloque "📇 Datos del formulario" de la ficha detalle.
- Modal custom (max-width 520px, gradient dorado, overflow-y auto) con inputs para 5 campos + botón "💾 GUARDAR CAMBIOS" con feedback disabled+"⏳" + cierre automático y refresh de la ficha.

**Test iteration_29.json**: 10/10 backend + 100% frontend · Confirmado: PATCH funciona, cadena vacía borra, propagación de client_meta con aliases funciona, modal frontend guarda y refresca correctamente. 0 issues.



### 🔗 Sync Multi-PC · E2E validado (Feb 2026)
**Feature completa y probada exhaustivamente**. Permite hasta 2 ordenadores por licencia (Premium/Trial/MASTER) compartiendo datos en tiempo real (linked · autosync 30s) o vía copia manual (independent). La fusión es **siempre aditiva**: nunca sustituye ni borra los datos del receptor. Ideal para gerente (revisa/ve) + secretaria (introduce datos).

**Bugs resueltos en esta iteración**:
- FIX #1 · `v2.html:10729-10733` — initSync ahora acepta `lic.license_key || lic.key` (antes fallaba silenciosamente para MASTER, dejando `mcSync` sin inicializar).
- FIX #2 · `backend/routes/sync.py:38-56` — MASTER key sintética (`MASTER_KEY = "MB-MASTER-BRUGULAT-2026-OWNER"`) reconocida como Premium sin necesidad de estar en DB. Mismo bypass que en cliente `isPremiumLicense()`.

**Resultados de test**:
- Backend API (`test_sync_multipc.py`): **71/71 pasa** (18 escenarios: 2 PCs Premium, TRIAL con 2 PCs, PC3 rechazado, cambio de modo, push/pull con merge, last-write-wins, backup upsert, backup consumido, Standard bloqueado, flujo Secretaria+Gerente mismo día sin duplicados, multi-empresa preservada).
- Merge cliente (`test_sync_client_merge.js`): **29/29 pasa** (10 escenarios: byDate mismo día IDs distintos, IDs repetidos con updated_at, multi-empresa con `_mtime`, arrays sin id, byDate anidado, idempotencia, volumen 1000 entradas <100ms).
- UI E2E (`iteration_34.json`): **7/7 pasa** (getStatus sin TypeError, heartbeat MASTER HTTP 200, modal Sync abre, sync-btn-linked toast, sync-btn-independent toast, sync-send-backup con label, simulación PC2 detecta peers + pending backup).

**Comportamiento verificado clave**:
- ✅ La copia manual (`Enviar Copia` desde Configuración) siempre **FUSIONA** en el receptor, nunca sustituye. Texto en modal receptor: "Se hará fusión sin duplicados: solo se añadirá lo que TÚ no tengas. Nada se sobrescribe."
- ✅ Multi-empresa: cada key `caja.byDate.empresa{N}.v1` y `caja.config.empresa{N}.v1` se fusiona por su cuenta sin mezclar datos entre empresas.
- ✅ Datos que sólo están en un PC → se conservan tras merge.
- ✅ IDs duplicados → gana el `updated_at` más reciente (LWW por entrada, no por array entero).

**Archivos clave**:
- `/app/backend/routes/sync.py` (~400 líneas) — endpoints `/api/sync/{heartbeat,push,pull,mode,status,backup/send,backup/pending,backup/consume}`.
- `/app/frontend/public/sync-client.js` (~205 líneas) — cliente completo con `_mergeSnapshots`, `_mergeArrays`, `_mergeByDate`, autosync polling.
- `/app/frontend/public/v2.html:10723-10800` — integración UI (onboarding modal, badge, `openSyncSettings`, banner de copia pendiente).
- `/app/backend/tests/test_sync_multipc.py` + `/app/backend/tests/test_sync_client_merge.js` — 100/100 tests unit.


### 🐛 FIX CRÍTICO Sync en PC local (file://) · Jun 2026 (iteration_37)
**Síntoma real del usuario**: En su PC (Electron/.exe carga v2.html vía file://) los botones "Configurar sync" y "Enviar copia" mostraban "Sincronización cargando · No se pudo conectar con el servidor", aunque todo funcionaba en preview.
**Causa raíz**: `_apiBase()` (v2.html ~10893) devolvía `window.REACT_APP_BACKEND_URL || location.origin`. En file:// eso es `file://` → todas las llamadas /api/sync/* morían. En preview funcionaba porque location.origin ES el backend (por eso los tests anteriores no lo detectaron).
**Fix**: `_apiBase()` ahora usa location.origin SOLO bajo http(s); si no, `getApiBase()` (window.API_BASE > override caja.apibase.override.v1 > caché > https://project-helper-47.emergent.host). Mismo fix en las 2 llamadas admin (list-licenses, push-to-license) líneas ~11000/~11039.
**Nuevo endpoint**: `POST /api/sync/admin/reset-devices` {admin_license_key, target_license_key, install_id?} — solo MASTER, libera slots de dispositivos (soporte a clientes que cambian de PC).
**Testing (iteration_37)**: backend 7/7 pytest, frontend 3/3 Playwright (MASTER con bloque admin + 30 clientes en dropdown, cliente PREMIUM sin bloque admin + envío copia OK, modal amable sin licencia). Simulación file:// con Playwright validada por main agent (modal abre, dropdown carga).
**⚠️ PENDIENTE POST-DEPLOY**: 1) El usuario debe REDESPLEGAR para que su .exe reciba el v2.html corregido. 2) Tras el deploy, limpiar dispositivo fantasma TESTPC1 de la licencia MASTER en producción: `curl -X POST https://project-helper-47.emergent.host/api/sync/admin/reset-devices -H "Content-Type: application/json" -d '{"admin_license_key":"MB-MASTER-BRUGULAT-2026-OWNER","target_license_key":"MB-MASTER-BRUGULAT-2026-OWNER","install_id":"TESTPC1"}'`

### ⭐ Favoritos Admin en desplegable de clientes · Jun 2026
- Botón estrella (☆/⭐, data-testid=admin-fav-toggle) junto al select admin (admTarget) en el modal Sync Multi-PC.
- Favoritos se guardan en localStorage `caja.sync.admfavs.v1` (solo local: excluido de ambos motores de sync — prefijo caja.sync. en el cliente inline + añadido a NON_SYNCABLE del motor heartbeat 60s).
- Render con optgroups: "⭐ FAVORITOS" arriba, "TODOS LOS CLIENTES" debajo. Selección se mantiene al marcar/quitar.
- Testeado E2E en simulación file:// (como el .exe): añadir → optgroup arriba → persiste al reabrir modal → quitar → limpio. Todo OK.

### ✅ Deploy a producción verificado + limpieza slots · Jun 2026
- Producción (project-helper-47.emergent.host) confirmada con el fix _apiBase() y Favoritos Admin.
- Slots MASTER liberados en producción vía reset-devices (removed:2 — incluía TESTPC1 fantasma). Los PCs reales del usuario se re-registran solos al abrir la app.
- list-licenses en producción devuelve 15 clientes reales para el desplegable admin.

### 🗑️ Botón "Empezar de cero" en Configuración · Jun 2026
- Nueva sección naranja en ⚙️ Configuración (antes de "Salir/Cambiar licencia"), botón data-testid=btn-reset-data. Bilingüe CA/ES.
- Doble confirmación: confirm() + prompt escribiendo BORRAR (acepta minúsculas). Palabra incorrecta → no toca nada.
- BORRA (solo este PC): caja.v1, caja.cempla.v1, caja.datafono, caja.cempla.datafono, caja.reserva.v1, caja.saldoInicial.* (prefijo), caja.stats.v1, caja.stats.traffic.overrides.v1, caja.irpf.v1, timestamps de sync (caja.__sync_*).
- CONSERVA: licencia, config empresas (caja.config.v1), caja.company, idioma, twilio, notif, favoritos admin, flag seed stats (caja.stats.seed.2026.jan-may — NO borrar o re-seedearía datos demo).
- Al ejecutar pasa el PC a modo Independiente (mcSync.setMode('independent') + stopAutosync + modeChosen) para que la nube/otro PC no devuelvan los datos viejos a ESTE PC (elección del usuario: solo borra local).
- Nota: tras reload, loadCambio() re-crea caja.reserva.v1 como {"_v":2} (migración interna) — vacía, 0 €, benigno.
- Testeado E2E en file:// (3 rondas Playwright): palabra incorrecta no borra; BORRAR borra todo; licencia/config/favoritos intactos; app arranca limpia con empresa conservada.

### 🐛 FIX: prompt() no existe en Electron (botón Empezar de cero "no hacía nada") · Jun 2026
- Síntoma: en el .exe, tras Aceptar el confirm(), no pasaba nada. Causa: window.prompt() lanza excepción en Electron (no soportado) → el handler async moría en silencio.
- Fix: diálogo propio askResetWord() (overlay z-index 100000, input data-testid=reset-word-input, botones reset-word-confirm/reset-word-cancel, Enter/Escape). alert() y confirm() SÍ funcionan en Electron; SOLO prompt() no. No hay más usos de prompt() en v2.html (verificado con grep).
- REGLA PARA FUTURO: NUNCA usar window.prompt() en esta app; usar diálogos propios.
- Marcador de versión: la esquina superior derecha ahora muestra 'v{ver} · 01.09' (HTML_BUILD, línea ~9076) para diagnosticar caché vieja del bootstrap del .exe. Actualizar HTML_BUILD (dd.mm) en cambios importantes.
- Nota bootstrap .exe: descarga v2.html fresco de producción al arrancar (api-endpoint.json en GitHub Medicarplus/medicarplus-releases apunta a project-helper-47.emergent.host); si falla la descarga usa caché localStorage medicar.boot.v2html.cache.v1 en silencio → siempre pedir al usuario cerrar/abrir la app tras un deploy.
- Testeado E2E file:// con prompt() anulado (simulando Electron): diálogo aparece, palabra mal no borra, BORRAR+Enter borra todo conservando licencia/config.

### 🛡️ Empezar de cero: nunca sobrescribir la copia anterior · Jun 2026
- Contexto: btnExport (💾 Guardar copia) recuerda el archivo elegido en IndexedDB ('caja-io' → kv → 'backupHandle') y escribe SIEMPRE encima del mismo archivo.
- Fix: el flujo "Empezar de cero" ahora llama clearStoredHandle() → la próxima copia abre el selector con nombre nuevo medicar_copia_<hoy>.json y NO toca la copia pre-borrado.
- Mensaje resetDone actualizado avisando de ello (CA/ES).
- Testeado E2E file://: handle 'MARC-COPIA-CAJA-2026-07-22.json' presente antes → None tras el borrado, datos wipeados OK.

### 🐛 FIX definitivo diálogo BORRAR (teclado muerto en Electron) · Jun 2026
- Síntoma: en el .exe no se podía escribir en el input de BORRAR. Causa REAL: bug conocido de Electron — tras un confirm()/alert() NATIVO la ventana pierde el foco de teclado y los inputs no reciben teclas.
- REGLA CRÍTICA: en el flujo de reset (y preferiblemente en toda la app) NO usar confirm(), alert() ni prompt() nativos. Usar overlays propios.
- Nuevo flujo: UNA sola ventana propia (showResetDialog) con aviso + input + botones; error de palabra inline (#resetDlgErr) sin alert; éxito con modal verde propio (showResetDone → OK → reload). Input grande, cursor:text, foco con reintentos (60/250/600ms) y re-enfoque en pointerdown sobre cualquier zona del recuadro que no sea botón.
- data-testids: reset-word-input, reset-word-confirm, reset-word-cancel, reset-word-error, reset-done-ok.
- HTML_BUILD subido a '02.09' (esquina superior derecha) para verificar que el usuario recibe esta versión.
- Testeado E2E file:// con window.confirm/alert/prompt anulados para lanzar excepción: tecleo real por teclado, clic en esquina del campo, clic fuera re-enfoca, palabra mal → error inline sin borrar, BORRAR+Enter → wipe + modal verde + reload limpio. 6/6 OK.

### 🔒 Saldo Anterior 100% aislado en TODAS las vías de sync · Jun 2026
- Pregunta del usuario: al fusionar/enviar copia, el "Saldo anterior" (caja.saldoInicial.*.v1) NO debe mezclarse entre PCs. Auditoría completa:
  - Cliente inline (fusión + copias manuales + admin push): ya excluía en SALIDA (SYNC_EXCLUDE_PREFIXES). AÑADIDO filtro también en ENTRADA: pullNow filtra cloudSnap y applyBackup filtra backupData con _isSyncable (la nube podía tener saldos antiguos de antes del fix).
  - Motor 60s (heartbeat): BUG REAL — isSyncable solo excluía claves exactas; saldoInicial y caja.apibase.* SÍ viajaban. Añadido NON_SYNCABLE_PREFIXES = ['caja.saldoInicial.','caja.install.','caja.sync.','caja.license.','caja.plan.preview.','caja.apibase.'] (aplica en captura markKeyChanged, en collectLocalChanges y en applyRemote — entrada y salida).
  - Copia a archivo (medicar_copia_*.json): nunca incluyó saldoInicial ✓.
- SÍ viajan: entradas byDate (fusión aditiva por id), caja.reserva.v1 (cajón único, gana _mtime más reciente), stats, irpf, datafono.
- Testeado E2E file://: hook no marca saldoInicial/apibase pero sí caja.v1/reserva; applyBackup con saldo remoto 9999 → saldo local 500 intacto, entradas remota+local fusionadas, reserva fusionada. 2/2 OK.

### 📨 Aviso de copia pendiente: siempre la más nueva + hora correcta · Jun 2026
- Problema usuario: pospuso una copia vieja, envió la buena, y el aviso parecía mostrar solo la vieja. Causas reales:
  1. _iso() en sync.py devolvía datetimes de Mongo SIN zona horaria (naive UTC) → el aviso mostraba la hora 2h atrasada en España → la copia nueva parecía vieja. FIX: _iso añade tzinfo UTC si es naive (afecta también last_seen de peers).
  2. El receptor solo consultaba el buzón 1 vez al arrancar (setTimeout 1500ms). FIX: además setInterval cada 60s → si llega una copia con la app abierta, avisa en <1 min.
- Mejoras del banner (clase .bk-restore-banner): muestra tiempo relativo ("hace X min", data-testid=backup-banner-reltime), nota "siempre se muestra la más reciente", dedupe (si hay banner viejo abierto se sustituye), snooze en memoria (_bkSnoozedId: "Más tarde" no re-avisa de ESA copia, pero sí de una más nueva). data-testids: backup-banner-apply, backup-banner-later.
- Backend ya garantizaba 1 sola copia por remitente (replace_one upsert) y orden desc.
- Testeado E2E preview: 2 envíos consecutivos → pending=1 solo la BUENA con created_at+00:00; banner en receptor muestra BUENA con "hace 1 min", aplicar fusiona (importe 99 presente) y no reaparece. Interval 60s no testeado en vivo (lógica trivial).

### 🐛 FIX botón "Aplicar copia" + blindaje escritura sync · Jun 2026 (iteration_38)
- Reporte: en el PC receptor "Aplicar copia (fusionar)" no hacía nada. Fixes de raíz:
  1. _syncWrite (v2.html ~258, expuesto como mcSync.safeWrite): string plano → setItem raw; objeto → JSON.stringify. Antes TODO iba con stringify → 'cempla' quedaba '"cempla"' y caja.apibase.* se corrompía con comillas (rompía las llamadas API tras aplicar). Usado en bkApply y en onIncoming del modo Fusionado.
  2. SYNC_EXCLUDE_PREFIXES += 'caja.apibase.', 'caja.__sync' (cliente inline, entrada Y salida) + snapshot del admin. Un emisor ya no puede pisar la URL de conexión del receptor (probado con URL "maliciosa").
  3. bkApply defensivo: try/catch, botón '⏳ Aplicando…', error visible (data-testid=backup-apply-error), consume tolerante a fallos (no bloquea la aplicación de datos). El botón nunca queda muerto en silencio.
- REGLA: al escribir claves recibidas por sync usar SIEMPRE mcSync.safeWrite, nunca JSON.stringify directo.
- Testing: iteration_38 100% (pytest 8/8: upsert por remitente, tz +00:00, consume, admin push x3, 403/404, reset-devices; Playwright: integridad post-aplicar 5/5 — company sin comillas, apibase intacta, saldo local 500 intacto, reserva LWW 350, fusión ambas fechas). Test file: /app/backend/tests/test_iter38_backup_pending_admin.py

### 💰 Retirar cambio = TRASPASO a caja (no resta del saldo) + fix retirada · Jun 2026
- Lógica de negocio confirmada por usuario: sacar dinero del cajón de cambio hacia la caja es un traspaso interno → reserva baja, CAJA FÍSICA/saldo NO cambian.
- BUG arreglado: en _cambioBulkOp modo remove solo restaba de data[d.k] (paquetes); si el dinero estaba en '€ manual' (d.k+'_m', típico tras repartir Saldo Inicial) no restaba NADA. Ahora resta en euros: primero paquetes, luego € manual, con tope en lo disponible (capped → aviso 'ajustado al disponible').
- Nuevo acumulador o._toCaja en caja.reserva.v1: € traspasados a caja. traspasoCambio() (v2.html ~5658) se suma en: resCambio de renderSummary (cajaC/cajaCB/Saldo anterior caja, línea ~3140) y #saldoAntNum (~3397). Sincroniza con el resto del objeto reserva (LWW _mtime).
- UI: línea '🔁 Traspasado a caja: X € (sigue en tu CAJA FÍSICA, no se resta del saldo)' en el modal Reserva (data-testid=cambio-traspaso-line). 'Vaciar todo' conserva _toCaja. 'Empezar de cero' sí lo borra (reset completo).
- Denominaciones clave: monedas c1,c2,c5,c10,c20,c50,e1,e2 (por PAQUETES, pack=€/paq; e2=50€/paq) + '_m' manual €; billetes b5,b10,b20,b50 (unidades).
- Testeado E2E file:// (3 tests): retiro 50€ → reserva 300/caja 350 intacta; retiro 100€ del manual; retiro con tope. CAJA FÍSICA y saldo idénticos antes/después en todos.

### 💰 FIX total reserva no bajaba al retirar (caso Saldo inicial / _bulk_seed) · Jun 2026
- Síntoma usuario: retirar restaba de las casillas pero el TOTAL GUARDAT no bajaba. Causa: saveCambio recalcula _bulk = _bulk_seed − suma(denoms); al restar de denoms sin bajar el seed, el dinero "volvía" al pendiente de repartir → total invariable.
- Fix (HTML_BUILD 03.09): en retirar, (1) orden de descuento: paquetes → € manual → _bulk (pendiente de repartir, funciona aunque NO haya casillas rellenas); (2) _bulk_seed -= movedEur (para que el recálculo de saveCambio cuadre); (3) data._bulk = bulkPool restante; (4) _toCaja += movedEur (traspaso automático a CAJA FÍSICA).
- Testeado E2E file:// 2 casos: todo en _bulk (350→300, traspaso 50, caja física constante) y mixto (e2:1 paq + bulk; retiro 100 → 50 del paquete + 50 del bulk, total 250). PENDIENTE: usuario debe hacer Deploy (verificar esquina · 03.09).

### 📊 Dos líneas de saldo anterior en el resumen (Tráfico C+B) · Jun 2026
- Sustituida la línea única 'Saldo anterior caja' por DOS lado a lado:
  1. 'Saldo anterior caja + cambio (todo el efectivo)' = saCC.caja + traspasoCambio() + reservaCambio() (data-testid=saldo-ant-caja-cambio)
  2. 'Saldo solo caja (sin cajón de cambio)' = saCC.caja + traspasoCambio() (data-testid=saldo-ant-solo-caja)
- En renderSummary: resCambio desglosado en cajonCambio + traspCaja. Tooltips explicativos en ambas.
- Testeado E2E file://: saldo inicial 1200 + traspaso 50 + cajón 300 → 1550/1250 correctos.

### ↩ Devolver a cambio desde caja (deshacer traspaso) · Jun 2026
- Tercer botón azul '↩ Devolver a cambio (desde caja)' (data-testid=cambio-return-btn) junto a Añadir/Retirar + botón inline en la línea de traspaso (cambio-devolver-btn). Ambos abren _cambioBulkOp modo 'return'.
- Lógica return: suma piezas al cajón (data[d.k]+=q), _bulk_seed += retEur (para que saveCambio no absorba la devolución), _toCaja -= retEur. TOPE: no se puede devolver más que _toCaja (toast de aviso, no aplica nada). Con _toCaja=0 el botón avisa y no abre modal.
- CAJA FÍSICA constante en la operación (el dinero solo cambia de sitio). Testeado E2E: traspaso 100 → devuelvo 50 → reserva 294,74→344,74, traspaso 50, intento de devolver 100 con 50 → rechazado, caja física idéntica.

### 🐛 FIX "(remote || []).forEach is not a function" al aplicar copia · Jun 2026
- Causa: caja.datafono / caja.cempla.datafono son mapas {fecha: importe(número)}. _isByDateShape los detecta como byDate → _mergeByDate → _mergeArrays sobre NÚMEROS → crash. Solo ocurría si AMBOS PCs tenían datáfono (tests previos no lo cubrían).
- Fix: (1) _mergeByDate: si el valor de una fecha no es array → escalar: gana lo local, si falta entra lo remoto; (2) _mergeArrays coerciona no-arrays a []; (3) _mergeSnapshots con try/catch POR CLAVE (una clave corrupta nunca rompe la fusión completa; fallback conserva lo local).
- Testeado E2E file://: admin push con datafono en ambos lados → sin error, entradas fusionadas, datafono por día (local gana en conflicto, remoto entra en días nuevos), cempla.datafono entra, reserva LWW, saldo inicial intacto, banner cierra. PENDIENTE deploy usuario (marker 03.09).

### 💳 Datáfono/VISA manual descuenta del Efectivo visible · Jun 2026
- CAJA FÍSICA/CUENTA BANCO ya reclasificaban vía delta, pero la casilla '💵 Efectivo' mostraba el bruto sin descontar → parecía que la VISA no hacía nada.
- Fix: Efectivo muestra el NETO (efShown − delta) en ambas empresas (data-testid efectivo-neto-cb / efectivo-neto-c) + etiqueta gris '(−X € a tarjeta)' cuando hay reclasificación.
- Testeado E2E: entrada 100€ efectivo + datáfono manual 60 → Efectivo 40,00 (−60,00 a tarjeta), CAJA FÍSICA 40, CUENTA BANCO 60.

### ✅ Verificación VISA en saldos acumulados · Jun 2026
- Confirmado (sin cambios de código necesarios): saldoAnteriorPorCuenta ya reclasifica el datáfono de días previos (delta=df−autoT por día). Los 3 apartados (saldo ant. caja+cambio, saldo solo caja, CAJA FÍSICA) y CUENTA BANCO reflejan la VISA correctamente.
- Test numérico E2E: ayer 100€ E + df 60 + cajón 300 + traspaso 50 → 390/90/390/60/450 todos exactos.

### 💼 Facturación anual privada (Admin) — Feb 2026
- **Objetivo**: el admin ve en el panel `/admin.html` (detalle de cada cliente) la facturación anual del cliente en **horquillas** (+10K, +50K, +100K, +900K, +1.1M…) con **blur por defecto** que solo se revela al pasar el ratón. Discreción absoluta: el cliente NO sabe que su facturación se envía · va silenciosa piggybackeando en el ping diario de licencia.
- **Cliente (v2.html · `verifyOnline`)**: recorre `caja.v1` + `caja.cempla.v1` (byDate), agrupa por año, aplica reglas contables Informe Anual (skip retorno, DH+_hnBruto/_internal/_tasaRefund/DEBE; HABER suma importe; entradas normales `(importe−descuento)+tasa`), envía `facturacion_stats:{by_year:{"2024":152340,...}}` dentro del body del `/api/licenses/verify`. Solo años con importe > 0.
- **Backend (`LicenseVerify` + `verify_license`)**: nuevo campo opcional `facturacion_stats`. Sanitización: solo enteros positivos, año 2000-2100. **Merge** con lo existente en la licencia → conserva años pasados incluso si el cliente ya no los envía.
- **Panel admin (`admin.html` · openDetail)**: nueva sección `<details data-testid="details-facturacion">` **💼 Facturación anual (privada)** entre Referidos y Datos técnicos. Grid de tarjetas 1 por año (borde dorado si es año actual), cifra desenfocada `filter:blur(8px)` que se revela onmouseenter. Bucket: <100K → +10K steps; 100K-1M → +100K steps; ≥1M → +X.XM. Comparativa año más reciente vs anterior (delta % también desenfocado) con 📈 mejorando (verde) / 📉 bajando (rojo). Banner amarillo de discreción.
- **Verificado E2E**: verify sin stats → OK (baseline); verify con {2023,2024,2025} → guarda los 3; verify posterior con solo {2025:95000} → merge conserva 2023+2024 y actualiza 2025; verify con basura (año 1900, 3000, "abc", -100) → rechazados; solo se acepta {2026:50000}. Enriched devuelve `facturacion_by_year` + `facturacion_updated_at`. Panel muestra 4 cards con blur/hover, trend "2026 vs 2025" rojo bajando, timestamp de última actualización.

### 🛡️ Cloud Backup Automático + Auditoría Contable — Feb 2026

**Cloud backup daily (Capa 1 blindaje)**:
- Backend `/api/sync/cloudbackup/{send,list,get}` con rotación automática (últimas 30 copias por install_id · MAX 2MB por copia)
- Frontend piggyback en el ping diario de licencia → `mcSync.sendCloudBackup()` silencioso cada ≥20h
- **Recuperación automática al arrancar**: si localStorage está vacío + hay copias en la nube → modal ofrece restaurar el último snapshot
- **Estado visible**: al abrir menú "Copias de seguridad" muestra "☁️ ✅ hace 3h · 09/02/2026 08:15"
- Flag `caja.cloud.recovery.skipped` previene loop del modal si el usuario declina
- Solo Premium (verificado backend)

**Auditoría contable exhaustiva** (`/app/frontend/public/tests/accounting_audit.js`):
- 14 tests · 47 invariantes verificados · 3 años sintéticos (2024-26 · 14.163 entradas)
- Cubre: conservación de dinero, transitividad Σdías=Σmeses=Σaños, categorización ingresos Emp1 (5 fijas), categorización gastos (auditoría cero pérdida), beneficio neto = ing-gas, traspasos internos NO alteran físico total, retornos NO cuentan, fotos PRIV+HABER unifican, canjes 66,50€ regla exacta, byFp/debeByFp segregation, datáfono reclassify sin pérdida, cuadre acumulado CAJA+BANCO, recuento entradas conservado, aislamiento Emp1/Emp2
- Ejecutar: `node /app/frontend/public/tests/accounting_audit.js`
- Resultado: **47/47 PASS**

### ☁️ Panel Admin — Envío Manual de Copias Históricas al Cliente (Feb 2026)
- **Backend**: 2 endpoints admin nuevos protegidos con X-Admin-Token o MASTER key:
  - `GET /api/sync/admin/cloudbackup/list?target_install_id=X` → lista 30 copias del cliente
  - `POST /api/sync/admin/cloudbackup/push` (body: target_license_key + target_install_id + backup_id) → copia el snapshot histórico al buzón pending del cliente para que lo vea al abrir la app
- **Admin panel** (`/admin.html` → detalle cliente): nueva sección `<details data-testid="details-cloud-backups">` "☁️ COPIAS EN LA NUBE · soporte al cliente · envía cualquiera de las 30". Tabla ordenada por fecha con columnas [Fecha·hora · Etiqueta · Tamaño · Claves · Acción]. Fila más reciente destacada con badge "MÁS RECIENTE". Cada fila con botón "📤 Enviar" individual → confirma → push a pending buzón del cliente.
- **UX**: la función `window._loadCloudBackupsForAdmin(iid, lkey)` lee el data-testid del `<details>` en `ontoggle`, hace fetch lazy (solo cuando el admin lo abre), renderiza tabla con 30 filas. `data-loaded='1'` evita recarga si se cierra/reabre.
- **Verificado E2E**: admin auth 403 sin token · listar devuelve 30 items · push envía copia histórica concreta (backup_id=X) → pending mailbox del cliente muestra "📩 Copia enviada por soporte (del DD/MM/YYYY HH:MM)".
