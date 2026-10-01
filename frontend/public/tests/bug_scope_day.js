// 🧪 Oct 2026 · El bug EXACTO reportado por el usuario:
//   Envía copia "Solo día 01/10/2026" al gerente · banner llega vacío
//
//   Causa: _filterSnapshotByDay descartaba todo excepto caja.v1/cempla/datafono/reserva
//   → las autoescuelas (caja.stats.v1 · 101 autos × 343 meses · 1998-2026) se perdían
//
//   Fix: ahora SOLO caja.v1/cempla/datafono se filtran por día; el resto viaja entero.

const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync('/app/frontend/public/v2.html', 'utf8');
const start = html.indexOf('function _filterSnapshotByDay');
const end   = html.indexOf('async function sendBackup', start);
const sandbox = { console, module: {} };
vm.runInContext(`${html.slice(start,end)}\nmodule.exports = { _filterSnapshotByDay };`,
  vm.createContext(sandbox));
const { _filterSnapshotByDay } = sandbox.module.exports;

// Cargar diagnóstico master real
const diag = JSON.parse(fs.readFileSync('/tmp/diag2.json', 'utf8'));
const snap = {};
for (const k of Object.keys(diag._localStorage)){
  try { snap[k] = JSON.parse(diag._localStorage[k]); }
  catch(_) { snap[k] = diag._localStorage[k]; }
}

let ok = 0, fail = 0;
function check(cond, label, extra){
  if(cond){ ok++; console.log('  ✅', label); }
  else    { fail++; console.error('  ❌', label, extra||''); }
}

console.log('\n🧪 Enviar "Solo día 2026-09-30" (scope=day) con mi diagnóstico master real:');
const filtered = _filterSnapshotByDay(snap, '2026-09-30');

// 1) Datos del DÍA concreto deben estar
const v1Days = Object.keys((filtered['caja.v1']||{}).byDate||{});
check(v1Days.length === 1 && v1Days[0] === '2026-09-30', `caja.v1 solo tiene el día enviado: ${v1Days.join(',')}`);
const cmpDays = Object.keys((filtered['caja.cempla.v1']||{}).byDate||{});
check(cmpDays.length <= 1, `caja.cempla.v1 solo el día (o 0 si no hay apuntes): ${cmpDays.join(',')||'0'}`);

// 2) 🎯 LAS AUTOESCUELAS DEBEN ESTAR COMPLETAS (bug reportado por el usuario)
const stats = filtered['caja.stats.v1'];
check(stats && stats.autoescoles && stats.autoescoles.length === 101,
  `AUTOESCUELAS: ${stats?.autoescoles?.length || 0} (esperado: 101)`);
check(stats && stats.data && Object.keys(stats.data).length === 343,
  `MESES histórico: ${Object.keys(stats?.data||{}).length} (esperado: 343)`);
const years = new Set(Object.keys(stats?.data||{}).map(m=>m.split('-')[0]));
check(years.size === 29, `AÑOS cubiertos: ${years.size} · ${[...years].sort()[0]} → ${[...years].sort().pop()}`);

// 3) El resto de datos históricos/configuración deben estar
check(filtered['caja.irpf.v1'] !== undefined, 'IRPF (meses + trimestres) viaja');
check(filtered['caja.tarifas.rules.v1'] !== undefined || !snap['caja.tarifas.rules.v1'], 'Tarifas Canje viajan');
check(filtered['caja.config.v1'] !== undefined, 'Configuración empresa viaja');
check(filtered['caja.stats.aliases.v1'] !== undefined, 'Aliases autoescuelas viajan');
check(filtered['caja.reserva.v1'] !== undefined, 'Reserva Tràfic viaja');
check(filtered['caja.cempla.reserva.v1'] !== undefined, 'Reserva Cempla viaja');

// 4) __preview__ debe ser calculable después del filtro
const pv_autoescoles = stats?.autoescoles?.length || 0;
const pv_months      = Object.keys(stats?.data||{}).length;
const pv_trafic      = (filtered['caja.v1']?.byDate?.['2026-09-30'] || []).length;
const pv_cempla      = (filtered['caja.cempla.v1']?.byDate?.['2026-09-30'] || []).length;
console.log('\n📦 Preview que verá Victoria en su banner:');
console.log(`   🚘 ${pv_autoescoles} autoescuelas`);
console.log(`   📅 ${pv_months} meses (${years.size} años)`);
console.log(`   💰 ${pv_trafic} apuntes Tràfic del día`);
console.log(`   🩺 ${pv_cempla} apuntes Cempla del día`);
check(pv_autoescoles > 0 && pv_months > 0, 'Banner mostrará contenido (NO vacío como antes)');

console.log('\n' + '='.repeat(70));
console.log(`📊 RESULTADO · ${ok} OK · ${fail} FAIL`);
console.log('='.repeat(70));
if (fail){ process.exit(1); }
console.log('🛡  FIX VERIFICADO: "Solo día" ahora pasa autoescuelas + histórico + configuración.');
process.exit(0);
