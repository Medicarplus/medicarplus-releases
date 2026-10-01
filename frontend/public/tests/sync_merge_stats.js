// 🧪 Oct 2026 · Verifica que la fusión de copia diaria entre PCs (sync linked)
//    fusiona correctamente caja.stats.v1 (datos de autoescuelas por mes/año)
//    y NO los pierde cuando el PC receptor tiene el valor vacío.
//
//    Regresión: antes el merger caía en el fallback por _mtime y como caja.stats.v1
//    no tiene _mtime, ganaba el local (receptor) aunque estuviera vacío → se perdían
//    años de histórico.
//
// Uso: node tests/sync_merge_stats.js

const fs = require('fs');
const path = require('path');

// Cargar v2.html y extraer las funciones que necesitamos (es monolito)
const html = fs.readFileSync(path.join(__dirname, '..', 'v2.html'), 'utf8');

// Buscar bloque que contiene _mergeSnapshots y helpers
const start = html.indexOf('const SYNC_EXCLUDE_PREFIXES');
const end   = html.indexOf('async function init(opts)', start);
if (start < 0 || end < 0) { console.error('No pude localizar bloque _mergeSnapshots en v2.html'); process.exit(2); }
const block = html.slice(start, end);

// Simular globals mínimos
const sandbox = { console, module: {} };
const code = `
  ${block}
  module.exports = { _mergeSnapshots, _mergeStatsV1, _mergeIrpfV1, _mergeArrayByField };
`;
const vm = require('vm');
const ctx = vm.createContext(sandbox);
vm.runInContext(code, ctx);
const { _mergeSnapshots, _mergeStatsV1, _mergeIrpfV1, _mergeArrayByField } = sandbox.module.exports;

let failed = 0;
function assert(cond, label, extra){
  if(cond){ console.log('  ✅', label); }
  else    { console.error('  ❌', label, extra || ''); failed++; }
}

console.log('\n🧪 TEST 1 · caja.stats.v1 · receptor vacío + emisor con 343 meses de 1998-2026');
{
  const local  = { 'caja.stats.v1': { autoescoles: [], data: {} } };
  const remote = { 'caja.stats.v1': {
    autoescoles: ['ROSANAS','CLAPERA','MOLIST'],
    data: {
      '1998-01': { ROSANAS: 53, CLAPERA: 34, MOLIST: 14 },
      '1998-02': { ROSANAS: 61, CLAPERA: 29 },
      '2025-12': { MOLIST: 101 },
    }
  }};
  const merged = _mergeSnapshots(local, remote);
  const s = merged['caja.stats.v1'];
  assert(s.autoescoles.length === 3, 'autoescoles.length === 3', s.autoescoles);
  assert(Object.keys(s.data).length === 3, 'data has 3 months', Object.keys(s.data));
  assert(s.data['1998-01'].ROSANAS === 53, "data['1998-01'].ROSANAS === 53", s.data['1998-01']);
  assert(s.data['2025-12'].MOLIST === 101, "data['2025-12'].MOLIST === 101");
}

console.log('\n🧪 TEST 2 · caja.stats.v1 · receptor y emisor con datos distintos (merge real)');
{
  const local  = { 'caja.stats.v1': {
    autoescoles: ['ROSANAS','NUEVA'],
    data: {
      '2026-09': { ROSANAS: 10, NUEVA: 5 },
      '2026-10': { NUEVA: 2 },
    }
  }};
  const remote = { 'caja.stats.v1': {
    autoescoles: ['ROSANAS','CLAPERA'],
    data: {
      '1998-01': { ROSANAS: 53, CLAPERA: 34 },
      '2026-09': { CLAPERA: 20 }, // mismo mes, autoescuela diferente
    }
  }};
  const merged = _mergeSnapshots(local, remote);
  const s = merged['caja.stats.v1'];
  assert(s.autoescoles.includes('ROSANAS') && s.autoescoles.includes('CLAPERA') && s.autoescoles.includes('NUEVA'),
    'autoescoles unidas sin duplicar', s.autoescoles);
  assert(s.autoescoles.length === 3, 'autoescoles.length === 3 (sin duplicar ROSANAS)');
  assert(s.data['1998-01'].ROSANAS === 53, 'mes 1998-01 traído del remoto');
  assert(s.data['2026-09'].ROSANAS === 10 && s.data['2026-09'].CLAPERA === 20 && s.data['2026-09'].NUEVA === 5,
    'mes 2026-09 fusionado (3 autoescuelas en el mismo mes)', s.data['2026-09']);
  assert(s.data['2026-10'].NUEVA === 2, 'mes 2026-10 preservado del local');
}

console.log('\n🧪 TEST 3 · caja.irpf.v1 · fusión de months + quarters');
{
  const local  = { 'caja.irpf.v1': {
    months:   { '2025-01': { base: 100 } },
    quarters: { '2025-Q1': { paid: true } },
  }};
  const remote = { 'caja.irpf.v1': {
    months:   { '2024-12': { base: 200 } },
    quarters: { '2024-Q4': { paid: true } },
  }};
  const merged = _mergeSnapshots(local, remote);
  const i = merged['caja.irpf.v1'];
  assert(Object.keys(i.months).length === 2, 'months fusionados: 2 entradas');
  assert(Object.keys(i.quarters).length === 2, 'quarters fusionados: 2 entradas');
  assert(i.months['2025-01'].base === 100 && i.months['2024-12'].base === 200, 'months preservados correctamente');
}

console.log('\n🧪 TEST 4 · caja.calendar.urls.v1 · array dedup por url');
{
  const local  = { 'caja.calendar.urls.v1': [{name:'A', url:'x1'}, {name:'B', url:'x2'}] };
  const remote = { 'caja.calendar.urls.v1': [{name:'C', url:'x2'}, {name:'D', url:'x3'}] };
  const merged = _mergeSnapshots(local, remote);
  const arr = merged['caja.calendar.urls.v1'];
  assert(arr.length === 3, 'array fusionado dedup por url: 3 items', arr);
  assert(arr.find(x=>x.url==='x1') && arr.find(x=>x.url==='x2') && arr.find(x=>x.url==='x3'), 'urls x1 x2 x3 presentes');
}

console.log('\n🧪 TEST 5 · caja.tarifas.rules.v1 · array dedup por id');
{
  const local  = { 'caja.tarifas.rules.v1': [{id:'r1', val:1}, {id:'r2', val:2}] };
  const remote = { 'caja.tarifas.rules.v1': [{id:'r2', val:99}, {id:'r3', val:3}] };
  const merged = _mergeSnapshots(local, remote);
  const arr = merged['caja.tarifas.rules.v1'];
  assert(arr.length === 3, 'array fusionado dedup por id: 3 items', arr);
  const r2 = arr.find(x=>x.id==='r2');
  assert(r2 && r2.val === 2, 'r2 preservado del local (first-wins)', r2);
}

console.log('\n🧪 TEST 6 · Objeto plano sin _mtime (regresión genérica)');
{
  const local  = { 'caja.config.v1': { empresa1: 'Trafic' } };
  const remote = { 'caja.config.v1': { empresa2: 'Cempla' } };
  const merged = _mergeSnapshots(local, remote);
  const c = merged['caja.config.v1'];
  assert(c.empresa1 === 'Trafic' && c.empresa2 === 'Cempla', 'deep-merge superficial preserva ambos campos', c);
}

console.log('\n🧪 TEST 7 · caja.v1 · byDate sigue mergeando correctamente');
{
  const local  = { 'caja.v1': { byDate: { '2026-09-01': [{id:'a', importe:10}] } } };
  const remote = { 'caja.v1': { byDate: { '2026-09-02': [{id:'b', importe:20}] } } };
  const merged = _mergeSnapshots(local, remote);
  const v = merged['caja.v1'];
  assert(v.byDate['2026-09-01'] && v.byDate['2026-09-02'], 'byDate: ambos días presentes');
}

console.log('\n🧪 TEST 8 · caja.stats.v1 presente SOLO en remoto (emisor), no en local');
{
  const local  = {};
  const remote = { 'caja.stats.v1': { autoescoles: ['X'], data: {'2000-05': {X: 7}} } };
  const merged = _mergeSnapshots(local, remote);
  const s = merged['caja.stats.v1'];
  assert(s && s.autoescoles[0] === 'X' && s.data['2000-05'].X === 7, 'trae el stats.v1 remoto completo');
}

console.log('\n🧪 TEST 9 · caja.stats.v1 presente SOLO en local, no en remoto');
{
  const local  = { 'caja.stats.v1': { autoescoles: ['Y'], data: {'2010-11': {Y: 3}} } };
  const remote = {};
  const merged = _mergeSnapshots(local, remote);
  const s = merged['caja.stats.v1'];
  assert(s && s.autoescoles[0] === 'Y' && s.data['2010-11'].Y === 3, 'preserva el stats.v1 local');
}

if(failed){
  console.error(`\n❌ ${failed} tests fallidos`); process.exit(1);
}else{
  console.log('\n🎉 Todos los tests de sync_merge_stats pasaron'); process.exit(0);
}
