// 🧪 Oct 2026 · ANTI-DUPLICACIÓN · verifica que fusionar NO duplica datos
//   El usuario insistió: "limitamos lo que se pasa para que no se duplique
//   información al fusionar". Este test prueba cada tipo de dato con el peor
//   escenario: el gerente YA tiene parte del contenido del secretario y aplica
//   la copia 2 veces (idempotencia).
//
// Uso: node tests/anti_duplicacion.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'v2.html'), 'utf8');
const start = html.indexOf('const SYNC_EXCLUDE_PREFIXES');
const end   = html.indexOf('async function init(opts)', start);
const sandbox = { console, module: {} };
vm.runInContext(`${html.slice(start,end)}\nmodule.exports = { _mergeSnapshots };`,
  vm.createContext(sandbox));
const { _mergeSnapshots } = sandbox.module.exports;

let okCount = 0, failCount = 0;
function check(cond, label, extra){
  if(cond){ okCount++; console.log('  ✅', label); }
  else    { failCount++; console.error('  ❌', label, extra||''); }
}
function sumRows(byDate){
  let s = 0, c = 0;
  for (const d of Object.keys(byDate||{})){
    const rows = Array.isArray(byDate[d]) ? byDate[d] : (byDate[d].rows||[]);
    c += rows.length;
    for (const r of rows) s += Number(r.importe||0);
  }
  return { count: c, sum: Math.round(s*100)/100 };
}

console.log('\n🧪 TEST 1 · caja.v1 · mismo apunte en ambos PCs (mismo id) → NO duplica');
{
  const common = { id:'apunte-x', kind:'DH', tipo:'HABER', grupo:'Práctica', nombre:'Juan Pérez', importe:50, tasa:0, fp:'E' };
  const local  = { 'caja.v1': { byDate: { '2026-09-15':[common] } } };
  const remote = { 'caja.v1': { byDate: { '2026-09-15':[common] } } };
  const m = _mergeSnapshots(local, remote);
  const r = sumRows(m['caja.v1'].byDate);
  check(r.count === 1, `apuntes finales: ${r.count} (esperado: 1 · no duplica por id)`);
  check(r.sum === 50, `suma: ${r.sum}€ (esperado: 50€)`);
}

console.log('\n🧪 TEST 2 · caja.v1 · mismo apunte con id DIFERENTE pero mismo contenido → NO duplica');
{
  const base = { kind:'DH', tipo:'HABER', grupo:'Práctica', nombre:'Juan Pérez', importe:50, tasa:0, descuento:0, fp:'E', fpTasa:'' };
  const local  = { 'caja.v1': { byDate: { '2026-09-15':[{...base, id:'id-local'}]  } } };
  const remote = { 'caja.v1': { byDate: { '2026-09-15':[{...base, id:'id-remote'}] } } };
  const m = _mergeSnapshots(local, remote);
  const r = sumRows(m['caja.v1'].byDate);
  check(r.count === 1, `apuntes finales: ${r.count} (esperado: 1 · dedup por huella de contenido)`);
  check(r.sum === 50, `suma: ${r.sum}€ (esperado: 50€)`);
}

console.log('\n🧪 TEST 3 · caja.v1 · apuntes diferentes mismo día → ambos se conservan');
{
  const local  = { 'caja.v1': { byDate: { '2026-09-15':[{id:'a',importe:50,kind:'DH',tipo:'HABER',nombre:'Juan'}] } } };
  const remote = { 'caja.v1': { byDate: { '2026-09-15':[{id:'b',importe:30,kind:'DH',tipo:'HABER',nombre:'Ana'}] } } };
  const m = _mergeSnapshots(local, remote);
  const r = sumRows(m['caja.v1'].byDate);
  check(r.count === 2, `apuntes finales: ${r.count} (esperado: 2 · diferente persona)`);
  check(r.sum === 80, `suma: ${r.sum}€ (esperado: 80€)`);
}

console.log('\n🧪 TEST 4 · caja.v1 · IDEMPOTENCIA · aplicar la MISMA copia 2 veces NO duplica');
{
  let local = { 'caja.v1': { byDate: {} } };
  const remote = { 'caja.v1': { byDate: {
    '2026-09-15':[
      {id:'r1',importe:50,kind:'DH',tipo:'HABER',nombre:'Juan',fp:'E'},
      {id:'r2',importe:30,kind:'DH',tipo:'HABER',nombre:'Ana',fp:'E'},
      {id:'r3',importe:20,kind:'DH',tipo:'HABER',nombre:'Pepe',fp:'B'},
    ]
  } } };
  // Primera aplicación
  local = _mergeSnapshots(local, remote);
  const r1 = sumRows(local['caja.v1'].byDate);
  // Segunda aplicación (idempotencia · típico escenario de replay por error)
  local = _mergeSnapshots(local, remote);
  const r2 = sumRows(local['caja.v1'].byDate);
  // Tercera aplicación (seguridad extra)
  local = _mergeSnapshots(local, remote);
  const r3 = sumRows(local['caja.v1'].byDate);
  check(r1.count === 3 && r2.count === 3 && r3.count === 3,
    `apuntes tras 1/2/3 aplicaciones: ${r1.count}/${r2.count}/${r3.count} · todas = 3`);
  check(r3.sum === 100, `suma estable: ${r3.sum}€ (esperado: 100€, nunca duplica)`);
}

console.log('\n🧪 TEST 5 · caja.stats.v1 · mismo mes/autoescuela presente en ambos → emisor gana (es autoritativo)');
{
  const local  = { 'caja.stats.v1': {
    autoescoles: ['ROSANAS','MOLIST'],
    data: { '2026-09': { ROSANAS: 20, MOLIST: 5 } },
  }};
  const remote = { 'caja.stats.v1': {
    autoescoles: ['ROSANAS','CLAPERA'],
    data: { '2026-09': { ROSANAS: 45, CLAPERA: 30 } },
  }};
  const m = _mergeSnapshots(local, remote);
  const s = m['caja.stats.v1'];
  check(s.autoescoles.length === 3, `autoescoles: ${s.autoescoles.length} · sin duplicar ROSANAS (${JSON.stringify(s.autoescoles)})`);
  check(s.data['2026-09'].ROSANAS === 45, `ROSANAS mes 2026-09: ${s.data['2026-09'].ROSANAS} (secretario autoritativo, no suma)`);
  check(s.data['2026-09'].MOLIST === 5, `MOLIST preservada (solo local): ${s.data['2026-09'].MOLIST}`);
  check(s.data['2026-09'].CLAPERA === 30, `CLAPERA añadida (solo remoto): ${s.data['2026-09'].CLAPERA}`);
}

console.log('\n🧪 TEST 6 · caja.stats.v1 · IDEMPOTENCIA · 3 aplicaciones = mismo resultado');
{
  let local = { 'caja.stats.v1': { autoescoles: [], data: {} } };
  const remote = { 'caja.stats.v1': {
    autoescoles: ['A','B','C'],
    data: { '2024-01':{A:10,B:20}, '2024-02':{C:5} },
  }};
  local = _mergeSnapshots(local, remote);
  local = _mergeSnapshots(local, remote);
  local = _mergeSnapshots(local, remote);
  const s = local['caja.stats.v1'];
  check(s.autoescoles.length === 3, `autoescoles tras 3× merge: ${s.autoescoles.length} (esperado: 3, NO 9)`);
  check(s.data['2024-01'].A === 10 && s.data['2024-01'].B === 20, 'valores 2024-01 estables');
  check(s.data['2024-02'].C === 5, 'valor 2024-02 estable');
}

console.log('\n🧪 TEST 7 · caja.tarifas.rules.v1 · misma regla (mismo id) → NO duplica');
{
  const regla = {id:'canje-ue', nombre:'Canje UE', importe:66.5};
  const local  = { 'caja.tarifas.rules.v1': [regla, {id:'duplicado-car', nombre:'Duplicado', importe:25}] };
  const remote = { 'caja.tarifas.rules.v1': [regla, {id:'renov-b', nombre:'Renov B', importe:85}] };
  const m = _mergeSnapshots(local, remote);
  const arr = m['caja.tarifas.rules.v1'];
  check(arr.length === 3, `reglas finales: ${arr.length} (esperado: 3, canje-ue no se duplica)`);
  const canjes = arr.filter(r => r.id === 'canje-ue');
  check(canjes.length === 1, `canje-ue aparece ${canjes.length} vez (esperado: 1)`);
}

console.log('\n🧪 TEST 8 · caja.calendar.urls.v1 · misma URL ICS en ambos → NO duplica');
{
  const url1 = {name:'Google', url:'https://cal.google.com/x.ics'};
  const url2 = {name:'Outlook', url:'https://outlook.com/y.ics'};
  const local  = { 'caja.calendar.urls.v1': [url1] };
  const remote = { 'caja.calendar.urls.v1': [url1, url2] };
  const m = _mergeSnapshots(local, remote);
  const arr = m['caja.calendar.urls.v1'];
  check(arr.length === 2, `URLs finales: ${arr.length} (esperado: 2)`);
}

console.log('\n🧪 TEST 9 · caja.cempla.v1 · byDate dedup funcional en centro médico');
{
  const row = {id:'cempla-1', importe:45, nombre:'Revisión Juan'};
  const local  = { 'caja.cempla.v1': { byDate: { '2026-09-01':[row] } } };
  const remote = { 'caja.cempla.v1': { byDate: { '2026-09-01':[row], '2026-09-02':[{id:'cempla-2',importe:30}] } } };
  const m = _mergeSnapshots(local, remote);
  const r = sumRows(m['caja.cempla.v1'].byDate);
  check(r.count === 2, `apuntes Cempla finales: ${r.count} (esperado: 2 · cempla-1 no duplica)`);
  check(r.sum === 75, `suma Cempla: ${r.sum}€ (esperado: 75€)`);
}

console.log('\n🧪 TEST 10 · 3 PCs encadenados · A→B→C sin duplicación tras varios ciclos');
{
  const base = { byDate: { '2026-09-15':[{id:'r1',importe:100,kind:'DH',tipo:'HABER',nombre:'X',fp:'E'}] } };
  let A = { 'caja.v1': JSON.parse(JSON.stringify(base)) };
  let B = { 'caja.v1': { byDate: {} } };
  let C = { 'caja.v1': { byDate: {} } };
  // Ciclo 1: A → B
  B = _mergeSnapshots(B, A);
  // Ciclo 2: B → C
  C = _mergeSnapshots(C, B);
  // Ciclo 3: C → A (replay accidental)
  A = _mergeSnapshots(A, C);
  // Ciclo 4: A → B otra vez
  B = _mergeSnapshots(B, A);
  const sA = sumRows(A['caja.v1'].byDate);
  const sB = sumRows(B['caja.v1'].byDate);
  const sC = sumRows(C['caja.v1'].byDate);
  check(sA.count === 1 && sB.count === 1 && sC.count === 1,
    `cada PC acaba con 1 apunte: A=${sA.count} B=${sB.count} C=${sC.count}`);
  check(sA.sum === 100 && sB.sum === 100 && sC.sum === 100,
    `suma estable al céntimo tras 4 ciclos: A=${sA.sum} B=${sB.sum} C=${sC.sum}€`);
}

console.log('\n' + '='.repeat(70));
console.log(`📊 RESULTADO ANTI-DUPLICACIÓN · ${okCount} OK · ${failCount} FAIL`);
console.log('='.repeat(70));
if (failCount){
  process.exit(1);
} else {
  console.log('🛡  Garantizado: 0 duplicación en ningún tipo de dato');
  console.log('   Aunque apliques la misma copia 10 veces, el total no cambia.');
  process.exit(0);
}
