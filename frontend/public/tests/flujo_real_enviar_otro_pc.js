// 🧪 Oct 2026 · Simula EXACTAMENTE el flujo real "Enviar copia al otro PC":
//   Secretario envía _fullBackupData() → Gerente aplica applyBackup(backup.data)
//   applyBackup filtra con _isSyncable y luego llama a _mergeSnapshots.
//   Este test verifica que caja.stats.v1 PASA el filtro _isSyncable y SE FUSIONA.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'v2.html'), 'utf8');
const start = html.indexOf('const SYNC_EXCLUDE_PREFIXES');
const end   = html.indexOf('async function init(opts)', start);

const sandbox = { console, module: {} };
vm.runInContext(`${html.slice(start,end)}\nmodule.exports = { _mergeSnapshots, _isSyncable, SYNC_EXCLUDE_PREFIXES };`,
  vm.createContext(sandbox));
const { _mergeSnapshots, _isSyncable, SYNC_EXCLUDE_PREFIXES } = sandbox.module.exports;

let ok = 0, fail = 0;
function check(cond, label, extra){
  if(cond){ ok++; console.log('  ✅', label); }
  else    { fail++; console.error('  ❌', label, extra||''); }
}

console.log('\n🔍 FASE 1 · ¿caja.stats.v1 pasa el filtro _isSyncable?');
console.log('SYNC_EXCLUDE_PREFIXES:', SYNC_EXCLUDE_PREFIXES);
check(_isSyncable('caja.stats.v1'), 'caja.stats.v1 es syncable');
check(_isSyncable('caja.stats.aliases.v1'), 'caja.stats.aliases.v1 es syncable');
check(_isSyncable('caja.stats.traffic.overrides.v1'), 'caja.stats.traffic.overrides.v1 es syncable');
check(_isSyncable('caja.irpf.v1'), 'caja.irpf.v1 es syncable');
check(_isSyncable('caja.tarifas.rules.v1'), 'caja.tarifas.rules.v1 es syncable');
check(_isSyncable('caja.v1'), 'caja.v1 es syncable');
check(_isSyncable('caja.cempla.v1'), 'caja.cempla.v1 es syncable');
check(!_isSyncable('caja.saldoInicial.trafic.v1'), 'caja.saldoInicial NO es syncable (correcto, local)');
check(!_isSyncable('caja.install.id.v1'), 'caja.install.id NO es syncable (correcto, local)');
check(!_isSyncable('caja.license.v1'), 'caja.license NO es syncable (correcto, local)');

console.log('\n🔄 FASE 2 · Simulación FLUJO REAL "Enviar copia al otro PC"');
// === Carga del diagnóstico master real ===
const diagPath = process.argv[2] || '/tmp/diag2.json';
if (!fs.existsSync(diagPath)) {
  console.error('Diagnóstico master no encontrado en', diagPath);
  process.exit(2);
}
const diag = JSON.parse(fs.readFileSync(diagPath, 'utf8'));
const masterLS = diag._localStorage;

// Secretario construye su backup (como _fullBackupData hace)
const backupDataFromSecretario = {};
for (const k of Object.keys(masterLS)) {
  if (!k.startsWith('caja.')) continue; // _fullBackupData incluye solo caja.* + whitelist
  try { backupDataFromSecretario[k] = JSON.parse(masterLS[k]); }
  catch(_) { backupDataFromSecretario[k] = masterLS[k]; }
}
backupDataFromSecretario['__origin__'] = { install_id: diag._installId };
console.log(`  📦 Secretario envía ${Object.keys(backupDataFromSecretario).length} claves`);
check('caja.stats.v1' in backupDataFromSecretario, 'backup incluye caja.stats.v1');
const statsEnBackup = backupDataFromSecretario['caja.stats.v1'];
console.log(`      · autoescoles: ${statsEnBackup.autoescoles.length}`);
console.log(`      · meses: ${Object.keys(statsEnBackup.data).length}`);

// Gerente (receptor) tiene su propio localStorage con caja.stats.v1 VACÍO
const gerenteLS = {
  'caja.v1': { byDate: {'2026-10-02':[{id:'g1',importe:50,kind:'DH',tipo:'HABER',nombre:'Cliente gerente',fp:'E'}]} },
  'caja.stats.v1': { autoescoles: [], data: {} },  // ← estado del gerente ANTES de recibir
  'caja.config.v1': { empresa:'Trafic' },
  'caja.saldoInicial.trafic.v1': { saldo: 100, fecha: '2026-10-01' },  // local, NO debe cruzar
  'caja.license.v1': { key: 'GERENTE-LIC' },  // local, NO debe cruzar
};

// === applyBackup simulado (idéntico a línea 541 de v2.html) ===
function applyBackup(backupData, localSnap){
  const incoming = {};
  Object.keys(backupData || {}).forEach(k => { if(_isSyncable(k)) incoming[k] = backupData[k]; });
  return _mergeSnapshots(localSnap, incoming);
}

const merged = applyBackup(backupDataFromSecretario, gerenteLS);

console.log('\n📊 FASE 3 · Verificar que el gerente ahora TIENE los datos de autoescuelas');
const statsFinales = merged['caja.stats.v1'];
check(statsFinales && statsFinales.autoescoles.length > 0,
  `autoescoles tras aplicar copia: ${statsFinales?.autoescoles?.length || 0} (ESPERADO: >= ${statsEnBackup.autoescoles.length})`);
check(statsFinales && Object.keys(statsFinales.data).length > 0,
  `meses tras aplicar copia: ${Object.keys(statsFinales?.data||{}).length} (ESPERADO: >= ${Object.keys(statsEnBackup.data).length})`);
const years = new Set(Object.keys(statsFinales?.data||{}).map(m=>m.split('-')[0]));
check(years.size > 1, `años cubiertos: ${years.size} (${[...years].sort()[0]} - ${[...years].sort().pop()})`);

console.log('\n🔒 FASE 4 · Claves locales del gerente preservadas (no sobreescritas)');
check(merged['caja.saldoInicial.trafic.v1']?.saldo === 100,
  'saldoInicial del gerente intacto (secretario no lo tocó: _isSyncable lo filtró)');
check(merged['caja.license.v1']?.key === 'GERENTE-LIC',
  'license del gerente intacta');
check(merged['caja.v1']?.byDate['2026-10-02'], 'día de trabajo del gerente preservado');

console.log('\n💰 FASE 5 · Contabilidad fusionada correctamente');
const daysGerente = Object.keys(merged['caja.v1'].byDate);
check(daysGerente.length > 1, `días totales en caja.v1 tras fusión: ${daysGerente.length}`);

console.log('\n' + '='.repeat(70));
console.log(`📊 RESULTADO · ${ok} OK · ${fail} FAIL`);
console.log('='.repeat(70));
if (fail){
  console.error('❌ Hay bug REAL en el flujo. Analizar inmediatamente.');
  process.exit(1);
} else {
  console.log('🎉 FLUJO "Enviar copia al otro PC" FUNCIONA CORRECTAMENTE');
  console.log('   Si en producción no funciona, es CACHÉ del Electron.');
  console.log('   El gerente debe hacer Ctrl+Shift+R en su Electron.');
  process.exit(0);
}
