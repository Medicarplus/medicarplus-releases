#!/usr/bin/env node
/**
 * 🚨 TEST · Reproduce el bug del usuario "no me aparece nada tras restaurar"
 * 
 * Simula:
 *   1. PC ORIGEN: usuario tiene 3 años de autoescolas + tráfico + IRPF + config...
 *   2. PC ORIGEN hace copia → fichero .json (formato v6+)
 *   3. PC DESTINO ya tiene ALGO en localStorage (aunque sea poco)
 *   4. Usuario restaura la copia en PC DESTINO
 *   5. VERIFICAR: ¿aparecen los datos de la copia?
 */

const path = require('path');
const fs = require('fs');

// ── Mock localStorage ──
class LS {
  constructor(){ this._m = new Map(); }
  getItem(k){ return this._m.has(k) ? this._m.get(k) : null; }
  setItem(k, v){ this._m.set(k, String(v)); }
  removeItem(k){ this._m.delete(k); }
  keys(){ return Array.from(this._m.keys()); }
  clear(){ this._m.clear(); }
}

const DATA_LS_KEYS = [
  'caja.v1','caja.cempla.v1','caja.datafono','caja.cempla.datafono',
  'caja.stats.v1','caja.stats.aliases.v1','caja.stats.traffic.overrides.v1',
  'caja.irpf.v1','caja.saldoInicial.trafic.v1','caja.saldoInicial.cempla.v1',
  'caja.reserva.v1','caja.cempla.reserva.v1','caja.cuadre.overrides.v1',
  'caja.config.v1','caja.calendar.history.v1','caja.calendar.status.v1',
  'caja.calendar.urls.v1','caja.count_zero','caja.tarifas.rules.v1',
];

// ── 1) PC ORIGEN ──
const pcOrigen = new LS();
// Sembrar 3 años de datos reales
const stats2024_2026 = { autoescoles:['AUTO X','AUTO Y','AUTO Z'], data:{} };
for(let y=2024; y<=2026; y++){
  for(let m=1; m<=12; m++){
    stats2024_2026.data[`${y}-${String(m).padStart(2,'0')}`] = { 'AUTO X': 45+m, 'AUTO Y': 30+m, 'AUTO Z': 12+m };
  }
}
pcOrigen.setItem('caja.stats.v1', JSON.stringify(stats2024_2026));
pcOrigen.setItem('caja.config.v1', JSON.stringify({ company1:{name:'CENTRE X'}, company2:{name:'CEMPLA C.B'}, partners:[{name:'M',pct:60}] }));
pcOrigen.setItem('caja.irpf.v1', JSON.stringify({ months:{'2024-01':500,'2025-03':650}, quarters:{'2024-Q1':{pagado:true}} }));
pcOrigen.setItem('caja.saldoInicial.trafic.v1', JSON.stringify({ fecha:'2024-01-01', efectivo:1250.75, banco:8890.20, cambio:200.00 }));
pcOrigen.setItem('caja.tarifas.rules.v1', JSON.stringify([{id:'a',resultado:'Canje',importeExacto:66.5,tipos:['Expedicion'],grupos:['Conduccion']}]));
pcOrigen.setItem('caja.v1', JSON.stringify({ byDate:{'2026-01-15':{rows:[{id:'1',importe:66.5}]}, '2025-05-10':{rows:[{id:'2',importe:145.55}]}} }));

console.log('════ PC ORIGEN sembrado con:');
pcOrigen.keys().forEach(k => console.log(`   ${k}: ${(pcOrigen.getItem(k)||'').length} bytes`));

// ── 2) Simular #btnExport (crea el JSON de la copia v6+) ──
function makeBackupJson(ls){
  const _lsAll = {};
  for(const k of DATA_LS_KEYS){
    const raw = ls.getItem(k);
    if(raw === null || raw === '') continue;
    try { _lsAll[k] = JSON.parse(raw); } catch(e){ _lsAll[k] = raw; }
  }
  return {
    _signature:'MEDICAR-PLUS-BACKUP-V4',
    _createdAt: new Date().toISOString(),
    // Legacy compat (código antiguo puede leerlos)
    cbTrafic: JSON.parse(ls.getItem('caja.v1')||'{"byDate":{}}'),
    cempla: JSON.parse(ls.getItem('caja.cempla.v1')||'{"byDate":{}}'),
    datafono: JSON.parse(ls.getItem('caja.datafono')||'{}'),
    stats: JSON.parse(ls.getItem('caja.stats.v1')||'null'),
    irpf: JSON.parse(ls.getItem('caja.irpf.v1')||'{"months":{},"quarters":{}}'),
    // Nueva mapa completo
    data: _lsAll,
    __origin__: { install_id:'PC-ORIGEN-XYZ', license_key:'MB-MASTER-BRUGULAT-2026-OWNER', exported_at:new Date().toISOString() },
    _v: 6,
  };
}
const backup = makeBackupJson(pcOrigen);
console.log(`\n════ Copia creada: ${JSON.stringify(backup).length} bytes · data keys: ${Object.keys(backup.data).length}`);

// ── 3) PC DESTINO con DATOS PREVIOS ──
// Este es el escenario del usuario: PC destino tenía algo dentro (aunque fuese poco)
const pcDestino_ConDatos = new LS();
pcDestino_ConDatos.setItem('caja.stats.v1', JSON.stringify({autoescoles:['TEST'], data:{'2026-01':{'TEST':1}}}));
pcDestino_ConDatos.setItem('caja.config.v1', JSON.stringify({company1:{name:'VACIO'}}));
pcDestino_ConDatos.setItem('caja.install.id.v1', 'PC-DESTINO-ABC');

console.log(`\n════ PC DESTINO ya tenía: ${pcDestino_ConDatos.keys().length} claves`);

// ── 4) Simular restoreAll(replace=false) — MODO FUSIONAR ──
function restoreAll_current(ls, obj, replace){
  const applied = [];
  const skipped_because_exists = [];
  if(obj.data && typeof obj.data === 'object'){
    for(const k of Object.keys(obj.data)){
      if(!DATA_LS_KEYS.includes(k)) continue;
      const v = obj.data[k];
      if(v === null || v === undefined || v === '') continue;
      if(!replace && ls.getItem(k)){
        skipped_because_exists.push(k);   // ⚠️ AQUÍ ESTÁ EL BUG
        continue;
      }
      ls.setItem(k, typeof v === 'string' ? v : JSON.stringify(v));
      applied.push(k);
    }
  }
  return { applied, skipped_because_exists };
}

console.log('\n════ ESCENARIO A: FUSIONAR (replace=false) sobre PC con datos previos');
const rA = restoreAll_current(pcDestino_ConDatos, backup, false);
console.log(`   ✅ Aplicadas: ${rA.applied.length}  → ${rA.applied.join(', ') || '(ninguna)'}`);
console.log(`   ⚠️ SALTADAS por MERGE porque ya existían: ${rA.skipped_because_exists.length}`);
rA.skipped_because_exists.forEach(k => console.log(`      ❌ ${k} · destino=${(pcDestino_ConDatos.getItem(k)||'').length}b · copia=${JSON.stringify(backup.data[k]).length}b [DATOS COPIA PERDIDOS]`));

// Verificar: ¿aparecen las autoescolas del origen?
const statsRestauradas = JSON.parse(pcDestino_ConDatos.getItem('caja.stats.v1'));
console.log(`\n   → PC DESTINO caja.stats.v1 después de FUSIONAR:`);
console.log(`      autoescoles: ${JSON.stringify(statsRestauradas.autoescoles)}`);
console.log(`      meses de datos: ${Object.keys(statsRestauradas.data||{}).length} (origen tenía 36 meses de 2024-2026)`);
const bug_detectado = Object.keys(statsRestauradas.data||{}).length < 36;
if(bug_detectado){
  console.log(`      🚨 BUG CONFIRMADO: solo aparecen ${Object.keys(statsRestauradas.data||{}).length} meses en lugar de 36. Los datos de 3 años SE PIERDEN al fusionar.`);
}

// ── 5) Escenario B: REEMPLAZAR (replace=true) ──
console.log('\n════ ESCENARIO B: REEMPLAZAR (replace=true) sobre PC con datos previos');
const pcDestino2 = new LS();
pcDestino2.setItem('caja.stats.v1', JSON.stringify({autoescoles:['TEST'], data:{'2026-01':{'TEST':1}}}));
pcDestino2.setItem('caja.config.v1', JSON.stringify({company1:{name:'VACIO'}}));
const rB = restoreAll_current(pcDestino2, backup, true);
console.log(`   ✅ Aplicadas: ${rB.applied.length}  → ${rB.applied.join(', ')}`);
console.log(`   ⚠️ Saltadas: ${rB.skipped_because_exists.length}`);
const statsRest2 = JSON.parse(pcDestino2.getItem('caja.stats.v1'));
console.log(`   → caja.stats.v1: autoescoles=${JSON.stringify(statsRest2.autoescoles)} · ${Object.keys(statsRest2.data||{}).length} meses`);

// ── 6) Escenario C: PC DESTINO VACÍO ──
console.log('\n════ ESCENARIO C: PC destino VACÍO + FUSIONAR');
const pcVacio = new LS();
const rC = restoreAll_current(pcVacio, backup, false);
console.log(`   ✅ Aplicadas: ${rC.applied.length}`);
console.log(`   → Funciona bien cuando el destino está vacío porque no hay conflicto`);

console.log('\n════════════════════════════════════════════════════════════════');
if(bug_detectado){
  console.log('   🚨 CONCLUSIÓN: BUG DEL MERGE MODE (Fusionar)');
  console.log('   → Si el PC destino tiene YA una clave (aunque sea con datos test o vacíos),');
  console.log('     el modo Fusionar la SALTA por completo, perdiendo los datos de la copia.');
  console.log('   → Solución: merge inteligente por tipo de clave (unir contenidos, no saltar).');
  process.exit(1);
} else {
  console.log('   ✅ Todo funcionaría bien');
  process.exit(0);
}
