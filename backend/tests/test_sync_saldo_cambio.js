/**
 * Test específico: Saldo Inicial + Reserva de Cambio se sincronizan bien.
 * Simula al Secretario (PC1) trabajando y al Gerente (PC2) recibiendo.
 */
const fs = require('fs');
const path = require('path');
const scriptSrc = fs.readFileSync(path.join(__dirname,'..','..','frontend','public','sync-client.js'),'utf8');
global.window = global;
global.localStorage = {_data:{},get length(){return Object.keys(this._data).length},key(i){return Object.keys(this._data)[i]},getItem(k){return this._data[k]||null},setItem(k,v){this._data[k]=String(v)},clear(){this._data={}}};
eval(scriptSrc);
const merge = window.mcSync._mergeSnapshots;

let pass=0, fail=0;
const ok = (c,m) => { if(c){console.log('  ✓',m);pass++} else {console.log('  ✗',m);fail++} };

console.log('\n═══ SALDO INICIAL + RESERVA DE CAMBIO · Sync Secretario→Gerente ═══\n');

// ═════════ 1. Gerente VIRGEN (nunca abrió Saldo/Cambio) — Secretario le manda todo
console.log('▸ Escenario 1: Gerente virgen · Secretario le pasa Saldo + Cambio + datos día');
{
  const secretario = {
    'caja.saldoInicial.main.v1': {fecha:'2026-01-15', efectivo:2000, banco:5000, cambio:800, _mtime:1000},
    'caja.reserva.v1': {_v:2, e1:10, e2:5, b20:3, _mtime:1000},
    'caja.byDate.v1': {'2026-01-15':[
      {id:'e-01', kind:'REV', amount:50, tipo:'B'},
      {id:'e-02', kind:'GAS', amount:-30, concepto:'Papelería'}
    ]}
  };
  const gerente = {};  // virgen
  const merged = merge(gerente, secretario);
  ok(!!merged['caja.saldoInicial.main.v1'], 'Gerente recibe Saldo Inicial');
  ok(merged['caja.saldoInicial.main.v1'].efectivo === 2000, `efectivo=2000 (got ${merged['caja.saldoInicial.main.v1'].efectivo})`);
  ok(merged['caja.saldoInicial.main.v1'].cambio === 800, 'cambio inicial 800€ presente');
  ok(!!merged['caja.reserva.v1'], 'Gerente recibe la Reserva de Cambio completa');
  ok(merged['caja.reserva.v1'].e1 === 10, '10 monedas de 1€');
  ok(merged['caja.reserva.v1'].b20 === 3, '3 billetes de 20€');
  ok(merged['caja.byDate.v1']['2026-01-15'].length === 2, 'Datos del día pasan');
}

// ═════════ 2. Ambos tocan Cambio · gana el más reciente (LWW por _mtime)
console.log('\n▸ Escenario 2: Ambos tocan Cambio · gana el más reciente');
{
  const secretario = { 'caja.reserva.v1': {_v:2, e1:20, e2:10, b20:5, _mtime:3000} };  // más reciente
  const gerente    = { 'caja.reserva.v1': {_v:2, e1:5,  e2:2,  b20:1, _mtime:1500} };  // más antiguo
  const merged = merge(gerente, secretario);
  ok(merged['caja.reserva.v1'].e1 === 20, `Gana el reciente: e1=20 (got ${merged['caja.reserva.v1'].e1})`);
  ok(merged['caja.reserva.v1'].b20 === 5, 'b20=5 del más reciente');

  // Al revés: Gerente es el más reciente (raro pero posible)
  const secretarioViejo = { 'caja.reserva.v1': {_v:2, e1:5, _mtime:1000} };
  const gerenteFresco   = { 'caja.reserva.v1': {_v:2, e1:99, _mtime:9999} };
  const m2 = merge(gerenteFresco, secretarioViejo);
  ok(m2['caja.reserva.v1'].e1 === 99, `Al revés: Gerente reciente gana e1=99 (got ${m2['caja.reserva.v1'].e1})`);
}

// ═════════ 3. Secretario añade monedas · Gerente añade billetes · SIN LWW se pierden datos
// NOTA: cambio es un objeto, no un array. LWW hace que "gane el más reciente" completo.
// Esto es correcto: los cambios físicos los lleva UN SOLO ordenador (el Secretario).
console.log('\n▸ Escenario 3: Escenario real · Secretario lleva el Cambio, Gerente solo lee');
{
  const secretario = { 'caja.reserva.v1': {_v:2, e1:15, c50:8, b10:4, _mtime:5000} };
  const gerente    = { 'caja.reserva.v1': {_v:2, _mtime:1000} };  // gerente abrió una vez, no cambió nada
  const merged = merge(gerente, secretario);
  ok(merged['caja.reserva.v1'].e1 === 15, 'Gerente recibe todas las monedas del Secretario');
  ok(merged['caja.reserva.v1'].c50 === 8, 'c50=8');
  ok(merged['caja.reserva.v1'].b10 === 4, 'b10=4');
}

// ═════════ 4. Multi-empresa · Saldo Inicial por empresa
console.log('\n▸ Escenario 4: Multi-empresa · Cada empresa mantiene su Saldo Inicial');
{
  const secretario = {
    'caja.saldoInicial.empresa1.v1': {fecha:'2026-01-01', efectivo:1000, _mtime:2000},
    'caja.saldoInicial.empresa2.v1': {fecha:'2026-01-01', efectivo:3000, _mtime:2000},
    'caja.reserva.v1': {_v:2, e1:12, _mtime:2000}
  };
  const gerente = {
    'caja.saldoInicial.empresa1.v1': {fecha:'2026-01-01', efectivo:500, _mtime:1000},  // antigua
  };
  const merged = merge(gerente, secretario);
  ok(merged['caja.saldoInicial.empresa1.v1'].efectivo === 1000, `Empresa1 se actualiza (got ${merged['caja.saldoInicial.empresa1.v1'].efectivo})`);
  ok(merged['caja.saldoInicial.empresa2.v1'].efectivo === 3000, 'Empresa2 (nueva) llega');
  ok(!!merged['caja.reserva.v1'], 'Cambio también llega');
  ok(merged['caja.reserva.v1'].e1 === 12, 'Cambio.e1=12');
}

// ═════════ 5. Flujo real completo · Secretario mete todo el día · Gerente actualiza y ve todo
console.log('\n▸ Escenario 5: DÍA REAL · Secretario mete revisiones+gastos+monedas · Gerente ve todo');
{
  const secretario = {
    'caja.saldoInicial.main.v1': {fecha:'2026-03-01', efectivo:2000, banco:5000, cambio:800, _mtime:1000},
    'caja.reserva.v1': {_v:2, e1:20, e2:10, c50:15, b10:8, b20:5, _mtime:5000},
    'caja.byDate.v1': {
      '2026-03-15': [
        {id:'r-01', kind:'REV', amount:50, updated_at:'2026-03-15T09:00:00Z'},
        {id:'r-02', kind:'REV', amount:75, updated_at:'2026-03-15T10:30:00Z'},
        {id:'r-03', kind:'REV', amount:60, updated_at:'2026-03-15T12:00:00Z'},
        {id:'g-01', kind:'GAS', amount:-25, updated_at:'2026-03-15T14:00:00Z'}
      ]
    }
  };
  const gerente = {};  // gerente arranca el PC por la tarde y hace pull
  const merged = merge(gerente, secretario);
  ok(!!merged['caja.saldoInicial.main.v1'], 'Gerente ve Saldo Inicial');
  const rsv = merged['caja.reserva.v1'];
  ok(rsv.e1===20 && rsv.b20===5, `Gerente ve TODAS las denominaciones (e1=${rsv.e1},b20=${rsv.b20})`);
  const dia = merged['caja.byDate.v1']['2026-03-15'];
  ok(dia.length === 4, `Gerente ve 4 movimientos del día (got ${dia.length})`);
  const ids = dia.map(e=>e.id);
  ok(ids.includes('r-01') && ids.includes('g-01'), 'Todos los IDs presentes');
}

// ═════════ 6. Segunda copia · secretario cambia el Cambio · gerente aplica de nuevo · no duplica
console.log('\n▸ Escenario 6: Secretario envía DOS copias · Gerente aplica ambas · idempotente');
{
  let gerente = {};
  // Copia 1: al mediodía
  const c1 = {
    'caja.reserva.v1': {_v:2, e1:10, e2:5, _mtime:5000},
    'caja.byDate.v1': {'2026-03-15':[{id:'r-01',amount:50}, {id:'r-02',amount:75}]}
  };
  gerente = merge(gerente, c1);
  ok(gerente['caja.reserva.v1'].e1 === 10, '1ª copia: e1=10');
  ok(gerente['caja.byDate.v1']['2026-03-15'].length === 2, '1ª copia: 2 movimientos');

  // Copia 2: al final del día · secretario añadió más monedas y otro movimiento
  const c2 = {
    'caja.reserva.v1': {_v:2, e1:15, e2:5, b10:3, _mtime:9000},
    'caja.byDate.v1': {'2026-03-15':[
      {id:'r-01',amount:50}, {id:'r-02',amount:75}, {id:'r-03',amount:60}, {id:'g-01',amount:-25}
    ]}
  };
  gerente = merge(gerente, c2);
  ok(gerente['caja.reserva.v1'].e1 === 15, '2ª copia: e1 actualizado a 15 (LWW)');
  ok(gerente['caja.reserva.v1'].b10 === 3, '2ª copia: b10=3 añadido');
  ok(gerente['caja.byDate.v1']['2026-03-15'].length === 4, `2ª copia: 4 movimientos totales (got ${gerente['caja.byDate.v1']['2026-03-15'].length})`);
  const ids2 = gerente['caja.byDate.v1']['2026-03-15'].map(e=>e.id);
  ok(new Set(ids2).size === 4, 'Sin duplicados de r-01 ni r-02');
}

console.log(`\n═════════════════════════════════`);
if(fail === 0) console.log(`✅ TODOS PASAN · ${pass}/${pass+fail}`);
else console.log(`❌ FALLAN ${fail}/${pass+fail}`);
console.log(`═════════════════════════════════\n`);
process.exit(fail === 0 ? 0 : 1);
