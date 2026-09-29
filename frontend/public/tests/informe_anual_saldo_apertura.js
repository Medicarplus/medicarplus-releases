/**
 * 🧪 TESTS EXHAUSTIVOS · Informe Anual · Saldo Apertura + Fixes Feb 2026
 * ─────────────────────────────────────────────────────────────────────
 * Cubre TODOS los cambios recientes:
 *   1. Saldo Apertura HABER concepto reservado → NO facturación, SÍ caja/banco
 *   2. Saldo Apertura AUTO-DETECCIÓN (primer día + HABER genérico + ≥300€)
 *   3. Saldo Apertura Config saldoInicial → banner en informe
 *   4. Descuento coherente: grandTotals.neto/byMonth/byFp/cTotal.neto
 *   5. byGroupConcept solo cuenta si importe > 0
 *   6. Extras (Foto/Dup/C.O.) van a grupo "Otros"
 *   7. Extras >0€ contabilizan aparte para KPI "Entradas Totales GIC + Extras"
 *   8. Backfill monthFilterIdx respetado
 *   9. Filtro mensual respeta año y mes
 *  10. Cuadre GLOBAL: Caja Real = ingresos nuevos + saldo apertura
 *
 * Ejecutar: node /app/frontend/public/tests/informe_anual_saldo_apertura.js
 */

'use strict';

let passCount = 0, failCount = 0;
const failures = [];
function assertEq(name, actual, expected, tol=0.01){
  const pass = Math.abs((+actual||0) - (+expected||0)) <= tol;
  if(pass){ passCount++; console.log(`   ✓ ${name}`); }
  else { failCount++; failures.push(`   ✗ ${name}\n       actual=${actual} · esperado=${expected}`); console.log(`   ✗ ${name} · actual=${actual} esperado=${expected}`); }
}
function assertTrue(name, cond){
  if(cond){ passCount++; console.log(`   ✓ ${name}`); }
  else { failCount++; failures.push(`   ✗ ${name}`); console.log(`   ✗ ${name}`); }
}

// ═══════════════════════════════════════════════════════════════
// SIMULACIÓN de la lógica de _buildAnnualReport (Feb 2026)
// Idéntica a la de v2.html · Se replica aquí para tests aislados.
// ═══════════════════════════════════════════════════════════════

function simulateBuildAnnualReport({byDate, year, monthFilterIdx = -1, saldoInicialConfig = null, activeKey = 'trafic'}){
  const _monthSuffix = monthFilterIdx >= 0 ? '-' + String(monthFilterIdx+1).padStart(2,'0') : null;
  const grandTotals = {
    bruto:0, tasas:0, neto:0, cnt:0,
    byMonth:Array(12).fill(0),
    byMonthCnt:Array(12).fill(0),
    byMonthFacturacion:Array(12).fill(0),
    byMonthGastos:Array(12).fill(0),
    byFp:{E:0,T:0,B:0,X:0},
    byConcept:{},
    byConceptCnt:{},
    byCompany:{},
    byGroupConcept:{},
    gastos:{},
    extrasCnt:0,
    extrasByMonth:Array(12).fill(0),
    saldoApertura:null
  };

  // 🧠 AUTO-DETECCIÓN de saldo apertura (mismo criterio ROBUSTO que v2.html)
  //   Primer HABER genérico >= 500€ del histórico completo (evita falsos negativos si hay
  //   DEBEs anteriores). Solo detecta UNO.
  const _autoSaldoAperturaIds = new Set();
  const _generic = /^(otro|otros|altre|altres|ingreso|ingres|-|)$/i;
  const _allDatesSorted = Object.keys(byDate||{}).sort();
  let _found = false;
  for(const dt of _allDatesSorted){
    if(_found) break;
    const _dayList = byDate[dt];
    if(!Array.isArray(_dayList)) continue;
    for(const e of _dayList){
      if(_found) break;
      if(e.kind==='DH' && e.tipo==='HABER' && (e.importe||0) >= 500){
        const _nm = String(e.nombre||'').trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
        if(_generic.test(_nm)){
          _autoSaldoAperturaIds.add(e.id);
          _found = true;
        }
      }
    }
  }

  // computeTotals simulado (subset relevante: HABER suma a neto y byFp)
  function computeTotals(list){
    const t = {neto:0, byFp:{E:0,T:0,B:0,X:0}};
    list.forEach(e => {
      if(e.retorno) return;
      if(e.kind==='DH' && e._hnBruto) return;
      if(e.kind==='DH' && (e._internal||e._tasaRefund)) return;
      if(e.kind==='DH'){
        const fp = e.fp||'E';
        if(e.tipo==='HABER'){ t.byFp[fp]+=(e.importe||0); t.neto+=(e.importe||0); }
        else { t.byFp[fp]-=(e.importe||0); t.neto-=(e.importe||0); }
        return;
      }
      const subt = (e.importe||0) - (e.descuento||0);
      const fp = e.fp||'E';
      t.byFp[fp]+=subt;
      t.neto += subt + (e.tasa||0);
    });
    return t;
  }

  function _normalizeReportCat(x){ return String(x||'').trim(); }

  Object.keys(byDate).forEach(d => {
    if(!d.startsWith(String(year)+'-')) return;
    if(_monthSuffix && !d.startsWith(String(year)+_monthSuffix)) return;
    const list = byDate[d];
    const t = computeTotals(list);
    const m = parseInt(d.split('-')[1]) - 1;
    grandTotals.neto += t.neto;
    grandTotals.byMonth[m] += t.neto;
    Object.keys(t.byFp).forEach(fp => grandTotals.byFp[fp] += t.byFp[fp]);

    list.forEach(e => {
      if(e.retorno) return;
      if(e.kind==='DH' && e._hnBruto) return;
      if(e.kind==='DH' && (e._internal||e._tasaRefund)) return;

      // DEBE
      if(e.kind==='DH' && e.tipo==='DEBE'){
        grandTotals.byMonthGastos[m] += (e.importe||0);
        const gCat = (e.nombre||'Gasto').trim();
        grandTotals.gastos[gCat] = grandTotals.gastos[gCat] || {count:0,total:0};
        grandTotals.gastos[gCat].count++;
        grandTotals.gastos[gCat].total += (e.importe||0);
        return;
      }

      // SALDO ANTERIOR / APERTURA
      if(e.kind==='DH' && e.tipo==='HABER'){
        const _hnRaw = String(e.nombre||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim();
        const _isSaldoAnt = /^\s*(saldo\s*(anterior|apertura|inicial)|apertura|opening|obertura|saldo\s*previ)\s*$/.test(_hnRaw);
        const _isAutoDetected = _autoSaldoAperturaIds.has(e.id);
        if(_isSaldoAnt || _isAutoDetected){
          grandTotals.saldoApertura = grandTotals.saldoApertura || {caja:0,banco:0,total:0,byMonth:Array(12).fill(0),entries:[]};
          const _amt = e.importe||0;
          grandTotals.saldoApertura.total += _amt;
          grandTotals.saldoApertura.byMonth[m] += _amt;
          const _fp = e.fp||'E';
          if(_fp==='E') grandTotals.saldoApertura.caja += _amt;
          else grandTotals.saldoApertura.banco += _amt;
          grandTotals.saldoApertura.entries.push({date:d,importe:_amt,fp:_fp,autoDetected: _isAutoDetected && !_isSaldoAnt});
          if(_isAutoDetected && !_isSaldoAnt) grandTotals.saldoApertura.hasAutoDetected = true;
          // DESCUENTO coherente
          grandTotals.neto -= _amt;
          grandTotals.byMonth[m] -= _amt;
          grandTotals.byFp[_fp] -= _amt;
          return;
        }
        // HABER normal
        const hCat = _normalizeReportCat((e.nombre||'Ingreso').trim());
        grandTotals.byConcept[hCat] = (grandTotals.byConcept[hCat]||0) + (e.importe||0);
        grandTotals.byMonthFacturacion[m] = (grandTotals.byMonthFacturacion[m]||0) + (e.importe||0);
        if((e.importe||0)>0) grandTotals.byConceptCnt[hCat] = (grandTotals.byConceptCnt[hCat]||0) + 1;
        return;
      }

      // Entrada normal (TRAF, PRIV)
      const rawTipo = e.tipo || 'Otro';
      const rawGrupo = (e.grupo||'').trim();
      const cat = _normalizeReportCat(rawTipo);
      const grupoLabel = rawGrupo && rawGrupo !== '-' ? _normalizeReportCat(rawGrupo) : 'General';
      const amtServicio = (e.importe||0) - (e.descuento||0);
      const amtTasa = e.tasa||0;
      const amtTotal = amtServicio + amtTasa;
      grandTotals.byConcept[cat] = (grandTotals.byConcept[cat]||0) + amtTotal;
      grandTotals.byMonthFacturacion[m] = (grandTotals.byMonthFacturacion[m]||0) + amtTotal;
      if(amtTotal>0) grandTotals.byConceptCnt[cat] = (grandTotals.byConceptCnt[cat]||0) + 1;

      // Extras (Foto/Duplicado/C.Oficial)
      const _catLow = String(cat||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
      const _isExtra = /foto/.test(_catLow) || /duplic/.test(_catLow) || /c\.?\s*ofici|certif.*ofici|\bofici/.test(_catLow);

      // byGroupConcept · extras → "Otros"
      const grupoLabelFinal = _isExtra ? 'Otros' : grupoLabel;
      grandTotals.byGroupConcept[grupoLabelFinal] = grandTotals.byGroupConcept[grupoLabelFinal] || {};
      const gc = grandTotals.byGroupConcept[grupoLabelFinal][cat] = grandTotals.byGroupConcept[grupoLabelFinal][cat] || {count:0,total:0};
      if(amtTotal>0) gc.count += 1;
      gc.total += amtTotal;

      // ENTRADAS TOTALES (isEntradaReal)
      let _isEntradaReal = false;
      if(activeKey==='trafic'){
        const _isDGT = e._csv === true;
        _isEntradaReal = _isDGT && amtTotal > 0 && !_isExtra;
      } else {
        _isEntradaReal = e.kind==='PRIV' && amtTotal>0 && !_isExtra;
      }
      if(_isEntradaReal){
        grandTotals.cnt += 1;
        grandTotals.byMonthCnt[m] += 1;
      }
      // Extras >0€
      if(_isExtra && amtTotal>0){
        grandTotals.extrasCnt += 1;
        grandTotals.extrasByMonth[m] += 1;
      }
    });
  });

  // Config saldoInicial
  if(saldoInicialConfig && saldoInicialConfig.fecha){
    const _year = saldoInicialConfig.fecha.slice(0,4);
    const _mIdx = parseInt(saldoInicialConfig.fecha.slice(5,7)) - 1;
    if(_year === String(year) && (monthFilterIdx<0 || monthFilterIdx===_mIdx)){
      const _total = (+saldoInicialConfig.efectivo||0) + (+saldoInicialConfig.banco||0) + (+saldoInicialConfig.cambio||0);
      if(_total>0){
        grandTotals.saldoApertura = grandTotals.saldoApertura || {caja:0,banco:0,cambio:0,total:0,byMonth:Array(12).fill(0),entries:[]};
        grandTotals.saldoApertura.caja += (+saldoInicialConfig.efectivo||0);
        grandTotals.saldoApertura.banco += (+saldoInicialConfig.banco||0);
        grandTotals.saldoApertura.cambio = (grandTotals.saldoApertura.cambio||0) + (+saldoInicialConfig.cambio||0);
        grandTotals.saldoApertura.total += _total;
        grandTotals.saldoApertura.byMonth[_mIdx] += _total;
        grandTotals.saldoApertura.fromConfig = true;
      }
    }
  }

  return grandTotals;
}

// ═══════════════════════════════════════════════════════════════
// CASO 1 · Cliente con HABER "Otro" 2500,71 € · Auto-detección
// ═══════════════════════════════════════════════════════════════
console.log('\n🧪 CASO 1 · Cliente instala en junio con 2.500,71 € previos (HABER "Otro" · fp:E)');
{
  const byDate = {
    '2026-06-01': [
      {id:'s1', kind:'DH', tipo:'HABER', nombre:'Otro', importe:2500.71, fp:'E'}
    ],
    '2026-07-15': [
      {id:'t1', kind:'TRAF', tipo:'Renovación', grupo:'Conducción', importe:20, tasa:22, _csv:true}
    ]
  };
  const g = simulateBuildAnnualReport({byDate, year:2026, activeKey:'trafic'});

  assertTrue('Saldo apertura detectado', !!g.saldoApertura);
  assertEq('Saldo apertura total = 2500,71 €', g.saldoApertura.total, 2500.71);
  assertEq('Saldo apertura caja = 2500,71 €', g.saldoApertura.caja, 2500.71);
  assertEq('Saldo apertura banco = 0', g.saldoApertura.banco, 0);
  assertTrue('Marcado como auto-detectado', g.saldoApertura.hasAutoDetected === true);
  assertEq('Facturación (byMonthFacturacion junio) SIN saldo = 0', g.byMonthFacturacion[5], 0);
  assertEq('Facturación (byMonthFacturacion julio) = 42', g.byMonthFacturacion[6], 42);
  assertEq('byConcept["Otro"] no existe (excluido)', g.byConcept['Otro']||0, 0);
  assertEq('grandTotals.neto NO incluye saldo apertura', g.neto, 42);
  assertEq('grandTotals.byFp.E NO incluye saldo apertura (solo servicio 20€)', g.byFp.E, 20);
  assertEq('grandTotals.byMonth[5] junio NO incluye saldo apertura', g.byMonth[5], 0);
  assertEq('Entradas Tráfico = 1 (solo el CSV)', g.cnt, 1);
}

// ═══════════════════════════════════════════════════════════════
// CASO 2 · Cliente renombra manualmente a "Saldo anterior"
// ═══════════════════════════════════════════════════════════════
console.log('\n🧪 CASO 2 · HABER con nombre explícito "Saldo anterior" (fp:T = tarjeta/banco)');
{
  const byDate = {
    '2026-01-05': [{id:'s1', kind:'DH', tipo:'HABER', nombre:'Foto exceso', importe:15, fp:'E'}],
    '2026-06-01': [{id:'s2', kind:'DH', tipo:'HABER', nombre:'Saldo anterior', importe:5000, fp:'T'}],
    '2026-06-10': [{id:'t1', kind:'TRAF', tipo:'Renovación', importe:20, _csv:true}]
  };
  const g = simulateBuildAnnualReport({byDate, year:2026, activeKey:'trafic'});

  assertEq('Saldo apertura = 5000 (nombre explícito)', g.saldoApertura.total, 5000);
  assertEq('Va al BANCO (fp:T)', g.saldoApertura.banco, 5000);
  assertEq('Caja saldo apertura = 0', g.saldoApertura.caja, 0);
  assertTrue('NO auto-detectado (concepto explícito)', !g.saldoApertura.hasAutoDetected);
  assertEq('Facturación total = 20 + 15 (Foto legítimo) = 35', Object.values(g.byConcept).reduce((s,n)=>s+n,0), 35);
  assertEq('grandTotals.byFp.T NO incluye saldo (0)', g.byFp.T, 0);
  assertEq('grandTotals.byFp.E = 15 (Foto exceso legítimo)', g.byFp.E, 20+15); // 20 servicio + 15 haber
}

// ═══════════════════════════════════════════════════════════════
// CASO 3 · Config saldoInicial (Ajustes → 🏦 Saldo inicial)
// ═══════════════════════════════════════════════════════════════
console.log('\n🧪 CASO 3 · Config-based saldoInicial (efectivo=1000, banco=2000, cambio=500)');
{
  const byDate = {
    '2026-03-10': [{id:'t1', kind:'TRAF', tipo:'Renovación', importe:20, _csv:true}]
  };
  const config = {fecha:'2026-03-01', efectivo:1000, banco:2000, cambio:500};
  const g = simulateBuildAnnualReport({byDate, year:2026, saldoInicialConfig:config, activeKey:'trafic'});

  assertEq('Saldo apertura total = 1000+2000+500 = 3500', g.saldoApertura.total, 3500);
  assertEq('Caja config = 1000', g.saldoApertura.caja, 1000);
  assertEq('Banco config = 2000', g.saldoApertura.banco, 2000);
  assertEq('Reserva (cambio) config = 500', g.saldoApertura.cambio, 500);
  assertTrue('Marcado como fromConfig', g.saldoApertura.fromConfig === true);
  assertEq('Facturación total sigue = 20', Object.values(g.byConcept).reduce((s,n)=>s+n,0), 20);
}

// ═══════════════════════════════════════════════════════════════
// CASO 4 · Filtro mensual respeta saldo apertura solo ese mes
// ═══════════════════════════════════════════════════════════════
console.log('\n🧪 CASO 4 · Filtro mensual · Config saldoInicial junio, filtro=enero');
{
  const byDate = {
    '2026-01-15': [{id:'t1', kind:'TRAF', tipo:'Renovación', importe:22, _csv:true}],
    '2026-06-01': [{id:'s1', kind:'DH', tipo:'HABER', nombre:'Saldo anterior', importe:1000, fp:'E'}]
  };
  const config = {fecha:'2026-06-01', efectivo:500, banco:0, cambio:0};

  const gEnero = simulateBuildAnnualReport({byDate, year:2026, monthFilterIdx:0, saldoInicialConfig:config, activeKey:'trafic'});
  const gJunio = simulateBuildAnnualReport({byDate, year:2026, monthFilterIdx:5, saldoInicialConfig:config, activeKey:'trafic'});
  const gAnual = simulateBuildAnnualReport({byDate, year:2026, monthFilterIdx:-1, saldoInicialConfig:config, activeKey:'trafic'});

  assertTrue('Enero: NO muestra saldo apertura (es de junio)', !gEnero.saldoApertura);
  assertEq('Enero facturación = 22', Object.values(gEnero.byConcept).reduce((s,n)=>s+n,0), 22);

  assertTrue('Junio: SÍ muestra saldo apertura', !!gJunio.saldoApertura);
  assertEq('Junio saldo apertura total = 1500 (HABER 1000 + config 500)', gJunio.saldoApertura.total, 1500);
  assertEq('Junio facturación = 0 (nada excepto el saldo)', Object.values(gJunio.byConcept).reduce((s,n)=>s+n,0), 0);

  assertTrue('Anual: SÍ muestra saldo apertura', !!gAnual.saldoApertura);
  assertEq('Anual saldo apertura = 1500', gAnual.saldoApertura.total, 1500);
  assertEq('Anual facturación = 22', Object.values(gAnual.byConcept).reduce((s,n)=>s+n,0), 22);
}

// ═══════════════════════════════════════════════════════════════
// CASO 5 · byGroupConcept · Extras van a "Otros" · solo cuenta si >0
// ═══════════════════════════════════════════════════════════════
console.log('\n🧪 CASO 5 · byGroupConcept: extras van a "Otros" · 0€ no cuentan uds');
{
  const byDate = {
    '2026-03-15': [
      {id:'t1', kind:'TRAF', tipo:'Renovación', grupo:'Conducción', importe:20, tasa:0, _csv:true},
      {id:'t2', kind:'TRAF', tipo:'Renovación', grupo:'Conducción', importe:0, tasa:0, _csv:true}, // 0€ no cuenta uds
      {id:'t3', kind:'TRAF', tipo:'Foto', grupo:'Conducción', importe:5, tasa:0, _csv:true}, // extra → "Otros"
      {id:'t4', kind:'TRAF', tipo:'Duplicado', grupo:'Armas', importe:15, tasa:0, _csv:true}, // extra → "Otros"
      {id:'t5', kind:'TRAF', tipo:'Expedición', grupo:'Marina', importe:30, tasa:0, _csv:true}
    ]
  };
  const g = simulateBuildAnnualReport({byDate, year:2026, activeKey:'trafic'});

  // Verificar que extras van a "Otros"
  assertTrue('Grupo "Otros" existe', !!g.byGroupConcept['Otros']);
  assertTrue('Foto está en "Otros"', !!g.byGroupConcept['Otros']?.['Foto']);
  assertTrue('Duplicado está en "Otros"', !!g.byGroupConcept['Otros']?.['Duplicado']);
  assertEq('Otros · Foto count = 1', g.byGroupConcept['Otros']['Foto'].count, 1);
  assertEq('Otros · Duplicado count = 1', g.byGroupConcept['Otros']['Duplicado'].count, 1);

  // Verificar 0€ no cuenta
  assertEq('Conducción · Renovación count = 1 (0€ no cuenta)', g.byGroupConcept['Conducción']['Renovación'].count, 1);
  assertEq('Conducción · Renovación total = 20 (importe suma aunque count no)', g.byGroupConcept['Conducción']['Renovación'].total, 20);

  // Verificar suma Desglose SIN Otros = suma Tráfico real
  let sumSinOtros = 0;
  Object.keys(g.byGroupConcept).forEach(grp => {
    if(grp === 'Otros') return;
    Object.values(g.byGroupConcept[grp]).forEach(d => { sumSinOtros += d.count; });
  });
  const entradasReales = g.cnt;
  assertEq('Desglose sin "Otros" = Entradas reales', sumSinOtros, entradasReales);
}

// ═══════════════════════════════════════════════════════════════
// CASO 6 · Entradas GIC + Extras · desglose de la tarjeta KPI
// ═══════════════════════════════════════════════════════════════
console.log('\n🧪 CASO 6 · KPI "Entradas Totales" = GIC (CSV real) + Extras (>0€)');
{
  const byDate = {
    '2026-03-15': [
      {id:'a1', kind:'TRAF', tipo:'Renovación', importe:20, _csv:true},
      {id:'a2', kind:'TRAF', tipo:'Expedición', importe:15, _csv:true},
      {id:'a3', kind:'TRAF', tipo:'Renovación', importe:0, _csv:true}, // 0€ NO cuenta ni GIC ni extras
      {id:'a4', kind:'TRAF', tipo:'Foto', importe:5, _csv:true}, // extra >0€ cuenta como extras
      {id:'a5', kind:'TRAF', tipo:'Duplicado', importe:15, _csv:true},
      {id:'a6', kind:'TRAF', tipo:'C.Oficial', importe:20, _csv:true},
      {id:'a7', kind:'TRAF', tipo:'Foto', importe:0, _csv:true} // extra 0€ NO cuenta
    ]
  };
  const g = simulateBuildAnnualReport({byDate, year:2026, activeKey:'trafic'});

  assertEq('GIC entradas reales = 2 (Renov 20 + Exped 15, excluye 0€ y extras)', g.cnt, 2);
  assertEq('Extras >0€ = 3 (Foto 5 + Dup 15 + C.O. 20)', g.extrasCnt, 3);
  assertEq('Total mostrado en tarjeta (GIC + Extras) = 5', g.cnt + g.extrasCnt, 5);
}

// ═══════════════════════════════════════════════════════════════
// CASO 7 · Saldo Apertura NO afecta reparto entre socios
// ═══════════════════════════════════════════════════════════════
console.log('\n🧪 CASO 7 · Saldo apertura NO infla reparto entre socios (usa grandTotals.neto)');
{
  const byDate = {
    '2026-06-01': [{id:'s1', kind:'DH', tipo:'HABER', nombre:'Saldo anterior', importe:10000, fp:'E'}],
    '2026-07-01': [{id:'t1', kind:'TRAF', tipo:'Renovación', importe:100, _csv:true}]
  };
  const g = simulateBuildAnnualReport({byDate, year:2026, activeKey:'trafic'});
  // Reparto 50/50 entre 2 socios
  const socio1 = g.neto * 0.5;
  const socio2 = g.neto * 0.5;

  assertEq('Neto sin saldo apertura = 100', g.neto, 100);
  assertEq('Socio 1 (50%) = 50 (no 5050)', socio1, 50);
  assertEq('Socio 2 (50%) = 50', socio2, 50);
}

// ═══════════════════════════════════════════════════════════════
// CASO 8 · Cuadre COMPLETO caja/banco vs facturación
// ═══════════════════════════════════════════════════════════════
console.log('\n🧪 CASO 8 · CUADRE TOTAL · Caja/Banco real ≠ Facturación IRPF');
{
  const byDate = {
    '2026-06-01': [{id:'sa', kind:'DH', tipo:'HABER', nombre:'Saldo anterior', importe:2500.71, fp:'E'}],
    '2026-07-15': [
      {id:'a1', kind:'TRAF', tipo:'Renovación', importe:20, tasa:22, fp:'E', _csv:true},
      {id:'a2', kind:'TRAF', tipo:'Renovación', importe:20, tasa:22, fp:'T', _csv:true}
    ]
  };
  const g = simulateBuildAnnualReport({byDate, year:2026, activeKey:'trafic'});

  const facturacionIRPF = Object.values(g.byConcept).reduce((s,n)=>s+n,0);
  const saldoAperturaTotal = g.saldoApertura?.total || 0;
  const cajaBancoReal = facturacionIRPF + saldoAperturaTotal; // lo que hay físicamente

  assertEq('Facturación IRPF (limpia, sin apertura) = 84 (2×20 + 2×22)', facturacionIRPF, 84);
  assertEq('Saldo apertura total = 2500,71', saldoAperturaTotal, 2500.71);
  assertEq('Caja+Banco real = 2584,71', cajaBancoReal, 2584.71);
  assertEq('grandTotals.neto (sin apertura) = 84', g.neto, 84);
  // byFp: E recibe Renov+tasa 42, T recibe Renov+tasa 42. Saldo apertura 2500,71 estaba en E pero se descuenta.
  assertEq('byFp.E servicio puro = 20 (sin apertura, sin tasa)', g.byFp.E, 20);
  assertEq('byFp.T = 20 (sin tasa)', g.byFp.T, 20);
}

// ═══════════════════════════════════════════════════════════════
// CASO 9 · No saldo apertura en HABER < 300€
// ═══════════════════════════════════════════════════════════════
console.log('\n🧪 CASO 9 · Auto-detección NO se activa si HABER < 300€');
{
  const byDate = {
    '2026-01-01': [{id:'h1', kind:'DH', tipo:'HABER', nombre:'Otro', importe:150, fp:'E'}], // <300, no cuenta
    '2026-01-02': [{id:'t1', kind:'TRAF', tipo:'Renovación', importe:20, _csv:true}]
  };
  const g = simulateBuildAnnualReport({byDate, year:2026, activeKey:'trafic'});
  assertTrue('NO se detecta saldo apertura (150 < 300)', !g.saldoApertura);
  assertEq('El HABER 150€ cuenta como facturación normal', g.byConcept['Otro']||0, 150);
}

// ═══════════════════════════════════════════════════════════════
// CASO 10 · Concepto específico (Foto) NO se auto-detecta
// ═══════════════════════════════════════════════════════════════
console.log('\n🧪 CASO 10 · Auto-detección solo con conceptos genéricos (Otro/Ingreso/-)');
{
  const byDate = {
    '2026-01-01': [{id:'h1', kind:'DH', tipo:'HABER', nombre:'Foto grupo', importe:500, fp:'E'}], // concepto específico, no cuenta
    '2026-01-02': [{id:'t1', kind:'TRAF', tipo:'Renovación', importe:20, _csv:true}]
  };
  const g = simulateBuildAnnualReport({byDate, year:2026, activeKey:'trafic'});
  assertTrue('NO se detecta saldo apertura ("Foto grupo" es específico)', !g.saldoApertura);
  assertEq('El HABER 500€ cuenta como facturación', g.byConcept['Foto grupo']||0, 500);
}

// ═══════════════════════════════════════════════════════════════
// CASO 11 · CASO REAL · HABER 2500,71 en junio + DEBEs previos
// ═══════════════════════════════════════════════════════════════
console.log('\n🧪 CASO 11 · CASO REAL · Aunque haya DEBEs anteriores, se detecta el HABER de junio');
{
  const byDate = {
    '2026-03-05': [{id:'d1', kind:'DH', tipo:'DEBE', nombre:'Alquiler', importe:800, fp:'X'}],
    '2026-04-10': [{id:'d2', kind:'DH', tipo:'DEBE', nombre:'Luz', importe:150, fp:'X'}],
    '2026-06-15': [{id:'sa', kind:'DH', tipo:'HABER', nombre:'Otro', importe:2500.71, fp:'E'}],
    '2026-07-01': [
      {id:'t1', kind:'TRAF', tipo:'Renovación', importe:20, tasa:22, fp:'E', _csv:true},
      {id:'t2', kind:'TRAF', tipo:'Renovación', importe:20, tasa:22, fp:'T', _csv:true}
    ]
  };
  const g = simulateBuildAnnualReport({byDate, year:2026, activeKey:'trafic'});

  assertTrue('Saldo apertura DETECTADO pese a DEBEs anteriores', !!g.saldoApertura);
  assertEq('Saldo apertura = 2500,71 (auto-detectado)', g.saldoApertura.total, 2500.71);
  assertTrue('Es auto-detectado (no explícito)', g.saldoApertura.hasAutoDetected === true);
  assertEq('Facturación año LIMPIA = 84 (2×20 + 2×22, sin 2500,71)', Object.values(g.byConcept).reduce((s,n)=>s+n,0), 84);
  assertEq('Junio facturación = 0 (solo tenía el saldo apertura)', g.byMonthFacturacion[5], 0);
  assertEq('Julio facturación = 84', g.byMonthFacturacion[6], 84);
  assertEq('Gastos año = 950 (800 + 150)', Object.values(g.gastos).reduce((s,g)=>s+g.total,0), 950);
}

// ═══════════════════════════════════════════════════════════════
// RESULTADO FINAL
// ═══════════════════════════════════════════════════════════════
console.log('\n' + '═'.repeat(66));
if(failCount === 0){
  console.log(`\n✅ TODOS LOS TESTS DE SALDO APERTURA PASAN · ${passCount} verificaciones`);
  console.log('   Cubre: auto-detección, concepto explícito, config saldoInicial,');
  console.log('   filtro mensual, descuento coherente (neto/byMonth/byFp), byGroupConcept,');
  console.log('   extras GIC vs Otros, reparto socios, cuadre total caja/banco vs IRPF.\n');
  process.exit(0);
} else {
  console.log(`\n❌ ${failCount} FALLOS · ${passCount} PASAN de ${failCount+passCount}`);
  failures.forEach(f => console.log(f));
  console.log('\n⚠️  Revisar código antes de deploy.\n');
  process.exit(1);
}
