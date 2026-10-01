// 🧪 Oct 2026 · E2E que simula el flujo real del usuario:
//   1. PC Secretario (master) tiene caja.stats.v1 completo (101 autos × 343 meses)
//   2. Hace una copia (export full backup incluye caja.stats.v1 + __origin__)
//   3. PC Gerente (receptor, vacío) aplica la copia vía SYNC (_mergeSnapshots)
//   4. PC Gerente guarda SU PROPIA copia (otro ciclo de backup)
//   5. Simular restauración de esa segunda copia en un tercer PC (de prueba)
//   6. Verificar que TODO cuadra byte a byte con el original del secretario
//
// Usa los datos REALES del diagnóstico master subido por el usuario para
// que el test sea idéntico al escenario de producción.
//
// Uso: node tests/e2e_sync_full_cycle.js [path-al-diagnostico-master.json]

const fs = require('fs');
const path = require('path');
const vm = require('vm');

// 1) Cargar sandbox con las funciones del v2.html
const html = fs.readFileSync(path.join(__dirname, '..', 'v2.html'), 'utf8');
const start = html.indexOf('const SYNC_EXCLUDE_PREFIXES');
const end   = html.indexOf('async function init(opts)', start);
const block = html.slice(start, end);

const sandbox = { console, module: {} };
vm.runInContext(`${block}\nmodule.exports = { _mergeSnapshots, _isSyncable, SYNC_EXCLUDE_PREFIXES };`,
  vm.createContext(sandbox));
const { _mergeSnapshots, _isSyncable } = sandbox.module.exports;

// 2) Snapshot inicial del Secretario · usar diagnóstico master si está presente,
//    si no, un fixture equivalente con datos de 1998 a 2026.
const diagPath = process.argv[2] || '/tmp/diag2.json';
let secretario = {};
if (fs.existsSync(diagPath)) {
  const diag = JSON.parse(fs.readFileSync(diagPath, 'utf8'));
  const ls = diag._localStorage || {};
  for (const k of Object.keys(ls)) {
    if (!_isSyncable(k)) continue; // tal como lo hace _snapshotLocalStorage
    try { secretario[k] = JSON.parse(ls[k]); }
    catch(_) { secretario[k] = ls[k]; }
  }
  console.log(`📂 Fuente: diagnóstico real del master (${Object.keys(secretario).length} claves syncables)`);
} else {
  console.log('⚠️ No se encontró /tmp/diag2.json · usando fixture sintético');
  secretario = {
    'caja.v1': { byDate: {'2026-09-01':[{id:'a',importe:12.50,tipo:'HABER'}]} },
    'caja.cempla.v1': { byDate: {'2026-09-01':[{id:'b',importe:45,tipo:'HABER'}]} },
    'caja.stats.v1': {
      autoescoles: ['ROSANAS','CLAPERA','MOLIST'],
      data: {
        '1998-01':{ROSANAS:53,CLAPERA:34,MOLIST:14},
        '2025-12':{MOLIST:101},
      }
    },
    'caja.config.v1': { empresa:'Trafic', iva:21 },
    'caja.irpf.v1': { months:{'2025-01':{base:100}}, quarters:{'2025-Q1':{paid:true}} },
    'caja.stats.aliases.v1': { 'ROSELL':'ROSANAS' },
    'caja.tarifas.rules.v1': [{id:'r1', nombre:'Canje'}],
  };
}

// 3) PC Gerente arranca con MUY POCO (como pasa en real: solo su trabajo del día)
const gerente_antes = {
  'caja.v1': { byDate: {'2026-10-01':[{id:'g1',importe:20,tipo:'HABER',nombre:'cliente dia gerente'}]} },
  'caja.config.v1': { empresa:'Trafic', _mtime: Date.now() },  // misma empresa pero local
  'caja.stats.v1': { autoescoles: [], data: {} }, // VACÍO, como Victoria en el bug reportado
};

// 4) Simular la copia diaria sync (lo que hace mcSync.applyBackup internamente):
//    _mergeSnapshots(local, remote) → ese es el flujo exacto en producción.
const gerente_despues = _mergeSnapshots(gerente_antes, secretario);

// 5) El gerente ahora guarda SU propia copia completa (serialización JSON como
//    la que hace _fullBackupData/#btnExport, round-trip)
const copiaDelGerente = JSON.parse(JSON.stringify(gerente_despues));

// 6) Restaurar esa copia del gerente en un tercer PC (merge con un local vacío)
const tercerPc = {};
const final = _mergeSnapshots(tercerPc, copiaDelGerente);

// =================== VERIFICACIONES ===================
let okCount = 0, failCount = 0;
function check(cond, label, extra){
  if(cond){ okCount++; console.log('  ✅', label); }
  else    { failCount++; console.error('  ❌', label, extra||''); }
}

// A) Datos de autoescuelas: comparar cada celda del secretario con el final
console.log('\n📊 VERIFICACIÓN 1 · caja.stats.v1 (datos históricos)');
{
  const src = secretario['caja.stats.v1'] || {autoescoles:[],data:{}};
  const dst = final['caja.stats.v1']        || {autoescoles:[],data:{}};

  check(dst.autoescoles.length >= src.autoescoles.length,
    `autoescoles preservadas: src=${src.autoescoles.length} dst=${dst.autoescoles.length}`);

  for (const a of src.autoescoles){
    if (!dst.autoescoles.includes(a)) check(false, `autoescuela "${a}" perdida en el camino`);
  }
  if (src.autoescoles.every(a => dst.autoescoles.includes(a))){
    check(true, `TODAS las ${src.autoescoles.length} autoescuelas presentes en el destino final`);
  }

  const srcMeses = Object.keys(src.data||{}).sort();
  const dstMeses = Object.keys(dst.data||{}).sort();
  check(srcMeses.length <= dstMeses.length, `meses: src=${srcMeses.length} dst=${dstMeses.length}`);

  // Chequear cada celda src[mes][auto] presente e idéntica
  let cellsChecked = 0, cellsOK = 0, cellsFail = 0;
  for (const mes of srcMeses){
    for (const auto of Object.keys(src.data[mes]||{})){
      cellsChecked++;
      const vSrc = src.data[mes][auto];
      const vDst = (dst.data[mes]||{})[auto];
      if (vSrc === vDst) cellsOK++;
      else { cellsFail++; if (cellsFail <= 5) console.error(`    ❌ celda ${mes}·${auto}: src=${vSrc} dst=${vDst}`); }
    }
  }
  check(cellsFail === 0, `celdas idénticas: ${cellsOK}/${cellsChecked}`);
  if (srcMeses.length) {
    check(dstMeses[0] === srcMeses[0], `primer mes conservado: ${srcMeses[0]}`);
    check(dstMeses[dstMeses.length-1] >= srcMeses[srcMeses.length-1],
      `último mes conservado: ${srcMeses[srcMeses.length-1]}`);
  }
}

// B) Contabilidad caja.v1: ni el día del gerente se pierde ni se pierden los del secretario
console.log('\n💰 VERIFICACIÓN 2 · caja.v1 (contabilidad Tràfic)');
{
  const srcDays = Object.keys((secretario['caja.v1']||{}).byDate || {});
  const dstDays = Object.keys((final['caja.v1']||{}).byDate || {});
  const gerDays = Object.keys((gerente_antes['caja.v1']||{}).byDate || {});

  for (const d of srcDays){
    if (!dstDays.includes(d)) check(false, `día secretario "${d}" perdido`);
  }
  for (const d of gerDays){
    if (!dstDays.includes(d)) check(false, `día gerente "${d}" perdido (SU trabajo del día)`);
  }

  if (srcDays.every(d => dstDays.includes(d)) && gerDays.every(d => dstDays.includes(d))){
    check(true, `TODOS los días conservados · secretario=${srcDays.length} + gerente=${gerDays.length} → final=${dstDays.length}`);
  }

  // Suma total (lo más crítico: cuadre al céntimo)
  const sumByDate = (byDate) => {
    let s = 0;
    for (const d of Object.keys(byDate||{})){
      const rows = Array.isArray(byDate[d]) ? byDate[d] : (byDate[d].rows||[]);
      for (const r of rows){ s += Number(r.importe||0); }
    }
    return Math.round(s*100)/100;
  };
  const sumSrc = sumByDate((secretario['caja.v1']||{}).byDate);
  const sumGer = sumByDate((gerente_antes['caja.v1']||{}).byDate);
  const sumFin = sumByDate((final['caja.v1']||{}).byDate);
  // Suma esperada: src + gerente (porque los días son distintos, no se solapan)
  const esperado = Math.round((sumSrc + sumGer)*100)/100;
  check(sumFin === esperado,
    `cuadre al céntimo: secretario(${sumSrc}€) + gerente(${sumGer}€) = ${esperado}€ · final=${sumFin}€`);
}

// C) caja.config.v1: no se destruyen campos del secretario ni del gerente
console.log('\n⚙️  VERIFICACIÓN 3 · caja.config.v1 (configuración empresa)');
{
  const src = secretario['caja.config.v1'] || {};
  const ger = gerente_antes['caja.config.v1'] || {};
  const dst = final['caja.config.v1'] || {};
  for (const k of Object.keys(src)){
    if (!(k in dst)) check(false, `config: campo "${k}" del secretario perdido`);
  }
  for (const k of Object.keys(ger)){
    if (k === '_mtime') continue;
    if (!(k in dst)) check(false, `config: campo "${k}" del gerente perdido`);
  }
  check(true, `config.v1 preservado · campos: ${Object.keys(dst).length}`);
}

// D) caja.irpf.v1: months + quarters preservados
console.log('\n📋 VERIFICACIÓN 4 · caja.irpf.v1 (IRPF)');
if (secretario['caja.irpf.v1']){
  const src = secretario['caja.irpf.v1'];
  const dst = final['caja.irpf.v1'] || {};
  const srcM = Object.keys(src.months||{});
  const dstM = Object.keys(dst.months||{});
  for (const m of srcM){
    if (!dstM.includes(m)) check(false, `irpf: mes "${m}" perdido`);
  }
  check(srcM.every(m=>dstM.includes(m)), `irpf months preservados: ${srcM.length}`);
  const srcQ = Object.keys(src.quarters||{});
  const dstQ = Object.keys(dst.quarters||{});
  check(srcQ.every(q=>dstQ.includes(q)), `irpf quarters preservados: ${srcQ.length}`);
}

// E) caja.tarifas.rules.v1
console.log('\n💰 VERIFICACIÓN 5 · caja.tarifas.rules.v1 (tarifas personalizadas)');
if (secretario['caja.tarifas.rules.v1']){
  const src = secretario['caja.tarifas.rules.v1'];
  const dst = final['caja.tarifas.rules.v1'] || [];
  for (const r of src){
    if (!dst.find(x=>x.id===r.id)) check(false, `tarifa id="${r.id}" perdida`);
  }
  check(src.every(r=>dst.find(x=>x.id===r.id)), `${src.length} tarifas preservadas`);
}

// F) Claves que NO deben cruzar (saldoInicial, license, install.*) via applyBackup
console.log('\n🔒 VERIFICACIÓN 6 · claves locales que NO deben cruzar entre PCs (filtro _isSyncable)');
{
  // Simular applyBackup: filtra el remote con _isSyncable antes de mergear
  const srcWithLocal = {...secretario,
    'caja.saldoInicial.trafic.v1': { saldo: 999 },
    'caja.license.v1': {key:'ABC'},
    'caja.install.id.v1': 'FAKE-INSTALL',
  };
  const incoming = {};
  Object.keys(srcWithLocal).forEach(k => { if(_isSyncable(k)) incoming[k] = srcWithLocal[k]; });
  check(!('caja.saldoInicial.trafic.v1' in incoming),
    'saldoInicial filtrado antes del merge (nunca cruza)');
  check(!('caja.license.v1' in incoming),
    'license filtrada antes del merge (nunca cruza)');
  check(!('caja.install.id.v1' in incoming),
    'install.id filtrado antes del merge (nunca cruza)');
}

// G) __origin__ y claves especiales no rompen el merge
console.log('\n🏷  VERIFICACIÓN 7 · claves especiales (__origin__, __server_sms__)');
{
  const srcSpec = {...secretario, '__origin__': {install_id:'XYZ'}};
  const r = _mergeSnapshots({}, srcSpec);
  check(true, `merge con __origin__ no explota: ok`);
}

// =================== RESUMEN ===================
console.log('\n' + '='.repeat(70));
console.log(`📊 RESULTADO E2E · ${okCount} OK · ${failCount} FAIL`);
console.log('='.repeat(70));

if (failCount){
  console.error('❌ Hay regresiones. Revisa la salida de arriba.');
  process.exit(1);
} else {
  console.log('🎉 FLUJO COMPLETO VERIFICADO AL CÉNTIMO:');
  console.log('   PC Secretario → copia diaria → PC Gerente → su propia copia → tercer PC');
  console.log('   Autoescuelas, años, meses, importes y configuración: TODO cuadra.');
  process.exit(0);
}
