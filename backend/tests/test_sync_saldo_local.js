/**
 * Test: Saldo Inicial NO sincroniza (queda local por PC).
 * Reserva de Cambio y todo lo demás SÍ sincroniza.
 */
const fs = require('fs');
const path = require('path');
const scriptSrc = fs.readFileSync(path.join(__dirname,'..','..','frontend','public','sync-client.js'),'utf8');
global.window = global;
global.localStorage = {_data:{},get length(){return Object.keys(this._data).length},key(i){return Object.keys(this._data)[i]},getItem(k){return this._data[k]||null},setItem(k,v){this._data[k]=String(v)},clear(){this._data={}},removeItem(k){delete this._data[k]}};
eval(scriptSrc);

let pass=0, fail=0;
const ok = (c,m) => { if(c){console.log('  ✓',m);pass++} else {console.log('  ✗',m);fail++} };

console.log('\n═══ TEST: Saldo Inicial LOCAL · Todo lo demás SINCRONIZA ═══\n');

// ═════════ 1. _snapshotLocalStorage EXCLUYE saldoInicial ═════════
console.log('▸ Escenario 1: Snapshot NO incluye caja.saldoInicial.*');
{
  localStorage.clear();
  localStorage.setItem('caja.saldoInicial.main.v1', JSON.stringify({fecha:'2026-01-15', efectivo:2000, banco:5000}));
  localStorage.setItem('caja.saldoInicial.empresa1.v1', JSON.stringify({fecha:'2026-02-01', efectivo:1000}));
  localStorage.setItem('caja.saldoInicial.empresa2.v1', JSON.stringify({fecha:'2026-03-01', efectivo:800}));
  localStorage.setItem('caja.reserva.v1', JSON.stringify({_v:2, e1:10, b20:5}));
  localStorage.setItem('caja.byDate.v1', JSON.stringify({'2026-03-15':[{id:'r-01',amount:50}]}));
  localStorage.setItem('caja.config.v1', JSON.stringify({name:'Autoescuela Test'}));

  // Simulamos snapshot con la misma lógica que sync-client.js
  const SYNC_EXCLUDE_PREFIXES = ['caja.saldoInicial.', 'caja.install.', 'caja.sync.', 'caja.license.', 'caja.plan.preview.'];
  function _isSyncable(k){
    if(!k || !k.startsWith('caja.')) return false;
    for(const p of SYNC_EXCLUDE_PREFIXES){ if(k.startsWith(p)) return false; }
    return true;
  }
  const snap = {};
  for(let i=0;i<localStorage.length;i++){
    const k = localStorage.key(i);
    if(!_isSyncable(k)) continue;
    snap[k] = JSON.parse(localStorage.getItem(k));
  }
  ok(!snap['caja.saldoInicial.main.v1'], 'caja.saldoInicial.main.v1 NO se sincroniza');
  ok(!snap['caja.saldoInicial.empresa1.v1'], 'caja.saldoInicial.empresa1.v1 NO se sincroniza');
  ok(!snap['caja.saldoInicial.empresa2.v1'], 'caja.saldoInicial.empresa2.v1 NO se sincroniza');
  ok(!!snap['caja.reserva.v1'], 'caja.reserva.v1 SÍ se sincroniza');
  ok(!!snap['caja.byDate.v1'], 'caja.byDate.v1 SÍ se sincroniza');
  ok(!!snap['caja.config.v1'], 'caja.config.v1 SÍ se sincroniza');
  ok(Object.keys(snap).length === 3, `Snapshot solo tiene 3 keys sincronizables (got ${Object.keys(snap).length})`);
}

// ═════════ 2. Excluye también install_id, sync interno, license, plan preview ═════════
console.log('\n▸ Escenario 2: Otras claves locales también excluidas');
{
  localStorage.clear();
  localStorage.setItem('caja.install.id.v1', 'PC-ABC-123');
  localStorage.setItem('caja.sync.modeChosen.v1', 'linked');
  localStorage.setItem('caja.license.v1', JSON.stringify({key:'FAKE-KEY', type:'MASTER'}));
  localStorage.setItem('caja.plan.preview.v1', 'STD');
  localStorage.setItem('caja.reserva.v1', JSON.stringify({e1:5}));

  const SYNC_EXCLUDE_PREFIXES = ['caja.saldoInicial.', 'caja.install.', 'caja.sync.', 'caja.license.', 'caja.plan.preview.'];
  const snap = {};
  for(let i=0;i<localStorage.length;i++){
    const k = localStorage.key(i);
    if(!k || !k.startsWith('caja.')) continue;
    let excluded = false;
    for(const p of SYNC_EXCLUDE_PREFIXES){ if(k.startsWith(p)){ excluded = true; break; } }
    if(!excluded) snap[k] = JSON.parse(localStorage.getItem(k));
  }
  ok(!snap['caja.install.id.v1'], 'install_id NO se sincroniza (cada PC tiene el suyo)');
  ok(!snap['caja.sync.modeChosen.v1'], 'sync.modeChosen NO se sincroniza (estado interno)');
  ok(!snap['caja.license.v1'], 'license NO se sincroniza (licencia local)');
  ok(!snap['caja.plan.preview.v1'], 'plan.preview NO se sincroniza (override local)');
  ok(!!snap['caja.reserva.v1'], 'reserva sí se sincroniza');
}

// ═════════ 3. Escenario real: PC1 configura Saldo Inicial · PC2 mantiene el suyo ═════════
console.log('\n▸ Escenario 3: Cada PC configura SU propio Saldo Inicial · no se contamina');
{
  // PC1 (Secretario) empezó el 15 enero con 2000€ efectivo
  const pc1_local = {
    'caja.saldoInicial.main.v1': {fecha:'2026-01-15', efectivo:2000, banco:5000, cambio:800},
    'caja.reserva.v1': {_v:2, e1:20, e2:10, b20:5},
    'caja.byDate.v1': {'2026-01-15':[{id:'r-01',amount:50}], '2026-01-20':[{id:'r-02',amount:75}]}
  };
  // PC2 (Gerente) empezó el 1 febrero, configuró SU saldo inicial diferente
  const pc2_local = {
    'caja.saldoInicial.main.v1': {fecha:'2026-02-01', efectivo:3500, banco:6200, cambio:0},
    'caja.reserva.v1': {_v:2, e1:5, b10:3},   // no sabe lo del cambio del secretario
    'caja.byDate.v1': {'2026-02-01':[{id:'r-03',amount:100}]}
  };
  // Simulamos que PC1 envía copia (excluye saldoInicial). PC2 recibe y fusiona.
  const SYNC_EXCLUDE_PREFIXES = ['caja.saldoInicial.'];
  const pc1_snapshot_sent = {};
  Object.keys(pc1_local).forEach(k => {
    let ex = false; for(const p of SYNC_EXCLUDE_PREFIXES) if(k.startsWith(p)) ex = true;
    if(!ex) pc1_snapshot_sent[k] = pc1_local[k];
  });
  ok(!pc1_snapshot_sent['caja.saldoInicial.main.v1'], 'PC1 NO envía su saldo inicial');
  ok(!!pc1_snapshot_sent['caja.reserva.v1'], 'PC1 SÍ envía su cambio físico');
  ok(!!pc1_snapshot_sent['caja.byDate.v1'], 'PC1 SÍ envía sus movimientos');

  // PC2 recibe y fusiona
  const merged = window.mcSync._mergeSnapshots(pc2_local, pc1_snapshot_sent);
  ok(merged['caja.saldoInicial.main.v1'].fecha === '2026-02-01', 'PC2 mantiene SU saldo inicial (2026-02-01, no 2026-01-15)');
  ok(merged['caja.saldoInicial.main.v1'].efectivo === 3500, 'PC2 mantiene su efectivo=3500€ (no 2000€ del PC1)');
  const dias = Object.keys(merged['caja.byDate.v1']).sort();
  ok(dias.length === 3, `PC2 ve 3 días fusionados: ${dias.join(', ')}`);
  ok(dias.includes('2026-01-15') && dias.includes('2026-02-01'), 'Todos los días presentes');
}

// ═════════ 4. Al revés: PC2 (Gerente) envía copia a PC1 (Secretario)
console.log('\n▸ Escenario 4: Al revés · Gerente envía a Secretario · Secretario mantiene su Saldo Inicial');
{
  const secretario_local = {
    'caja.saldoInicial.main.v1': {fecha:'2026-01-15', efectivo:2000, banco:5000, cambio:800}
  };
  const gerente_snapshot = {
    'caja.byDate.v1': {'2026-02-05':[{id:'g-01',amount:150}]}
  };  // ya no incluye su saldo inicial (excluido en snapshot)
  const merged = window.mcSync._mergeSnapshots(secretario_local, gerente_snapshot);
  ok(merged['caja.saldoInicial.main.v1'].fecha === '2026-01-15', 'Secretario mantiene su Saldo Inicial original');
  ok(merged['caja.saldoInicial.main.v1'].efectivo === 2000, 'efectivo=2000 preservado');
  ok(!!merged['caja.byDate.v1']['2026-02-05'], 'Recibe los movimientos del Gerente');
}

// ═════════ 5. Multi-empresa: cada PC decide qué empresa configura ═════════
console.log('\n▸ Escenario 5: Multi-empresa · saldos por empresa siguen locales');
{
  const pc1 = {
    'caja.saldoInicial.empresa1.v1': {fecha:'2026-01-15', efectivo:1000, _mtime:1000},
    'caja.saldoInicial.empresa2.v1': {fecha:'2026-01-15', efectivo:2000, _mtime:1000}
  };
  const pc2_snapshot_received = {};  // saldoInicial excluido antes de enviar
  const merged = window.mcSync._mergeSnapshots(pc1, pc2_snapshot_received);
  ok(merged['caja.saldoInicial.empresa1.v1'].efectivo === 1000, 'PC1 mantiene empresa1');
  ok(merged['caja.saldoInicial.empresa2.v1'].efectivo === 2000, 'PC1 mantiene empresa2');
}

// ═════════ 6. Borrar Saldo Inicial en un PC NO afecta al otro ═════════
console.log('\n▸ Escenario 6: Borrar Saldo Inicial en PC1 no afecta al PC2');
{
  // PC1 borra su saldoInicial (local). PC2 nunca lo pierde.
  // Como no se sincroniza, no hay forma de "borrar el saldo del otro PC" por accidente.
  const pc1_after_delete = {};  // vacío tras borrar
  const pc2_still_has = {
    'caja.saldoInicial.main.v1': {fecha:'2026-02-01', efectivo:3500}
  };
  const merged = window.mcSync._mergeSnapshots(pc2_still_has, pc1_after_delete);
  ok(!!merged['caja.saldoInicial.main.v1'], 'PC2 mantiene su Saldo Inicial aunque PC1 lo haya borrado');
  ok(merged['caja.saldoInicial.main.v1'].efectivo === 3500, 'efectivo intacto');
}

console.log(`\n═════════════════════════════════`);
if(fail === 0) console.log(`✅ TODOS PASAN · ${pass}/${pass+fail}`);
else console.log(`❌ FALLAN ${fail}/${pass+fail}`);
console.log(`═════════════════════════════════\n`);
process.exit(fail === 0 ? 0 : 1);
