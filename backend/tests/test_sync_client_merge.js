/**
 * Test unitario del sync-client.js (merge cliente-side)
 * Simula 2 PCs con múltiples empresas y datos reales.
 */
const fs = require('fs');
const path = require('path');

// Cargar sync-client.js en un contexto simulado
const scriptPath = path.join(__dirname, '..', '..', 'frontend', 'public', 'sync-client.js');
const scriptSrc = fs.readFileSync(scriptPath, 'utf8');
global.window = global;
global.localStorage = {
  _data: {},
  get length() { return Object.keys(this._data).length; },
  key(i) { return Object.keys(this._data)[i]; },
  getItem(k) { return this._data[k] || null; },
  setItem(k, v) { this._data[k] = String(v); },
  clear() { this._data = {}; }
};
eval(scriptSrc);
const merge = window.mcSync._mergeSnapshots;

let pass = 0, fail = 0;
const ok = (c, m) => { if(c){ console.log('  ✓', m); pass++; } else { console.log('  ✗', m); fail++; } };

console.log('\n═══ TEST MERGE CLIENT · sync-client.js ═══\n');

// ══ Escenario 1: Merge de byDate con la misma fecha, diferentes IDs ══
console.log('▸ Escenario 1: Merge byDate con misma fecha, diferentes IDs');
{
  const pc1 = {
    'caja.byDate.v1': {
      '2026-04-06': [
        { id: 'rev-001', kind: 'REV', amount: 50 },
        { id: 'rev-002', kind: 'REV', amount: 75 }
      ]
    }
  };
  const pc2 = {
    'caja.byDate.v1': {
      '2026-04-06': [
        { id: 'gasto-001', kind: 'GAS', amount: -20 },
        { id: 'gasto-002', kind: 'GAS', amount: -35 }
      ]
    }
  };
  const merged = merge(pc1, pc2);
  const day = merged['caja.byDate.v1']['2026-04-06'];
  ok(day.length === 4, `4 entradas mismo día (got ${day.length})`);
  const ids = day.map(e => e.id);
  ok(ids.includes('rev-001') && ids.includes('gasto-002'), 'todos los IDs presentes');
  ok(new Set(ids).size === 4, 'IDs únicos sin duplicados');
}

// ══ Escenario 2: Merge con IDs repetidos, gana el más reciente ══
console.log('\n▸ Escenario 2: IDs repetidos → gana el más reciente');
{
  const pc1 = { 'caja.byDate.v1': { '2026-04-06': [
    { id: 'rev-001', amount: 50, updated_at: '2026-04-06T09:00:00Z' }
  ]}};
  const pc2 = { 'caja.byDate.v1': { '2026-04-06': [
    { id: 'rev-001', amount: 999, updated_at: '2026-04-06T14:00:00Z' }
  ]}};
  const merged = merge(pc1, pc2);
  const day = merged['caja.byDate.v1']['2026-04-06'];
  ok(day.length === 1, `Solo 1 entrada (dedup por ID) (got ${day.length})`);
  ok(day[0].amount === 999, `Gana el más reciente: 999 (got ${day[0].amount})`);
}

// ══ Escenario 3: Multi-empresa (varias claves de config) ══
console.log('\n▸ Escenario 3: Multi-empresa (config, revisiones, trafico por empresa)');
{
  const pc1 = {
    'caja.config.empresa1.v1': { name: 'Autoescuela Norte', cif: 'B123', _mtime: 1000 },
    'caja.byDate.empresa1.v1': { '2026-04-01': [{ id: 'e1-A', amount: 100 }] },
    'caja.config.empresa2.v1': { name: 'Autoescuela Sur', cif: 'B456', _mtime: 2000 },
    'caja.byDate.empresa2.v1': { '2026-04-01': [{ id: 'e2-A', amount: 200 }] }
  };
  const pc2 = {
    'caja.config.empresa1.v1': { name: 'Autoescuela Norte MOD', cif: 'B123', _mtime: 3000 },  // más reciente
    'caja.byDate.empresa1.v1': { '2026-04-01': [{ id: 'e1-B', amount: 150 }] },
    'caja.config.empresa3.v1': { name: 'Autoescuela Este', cif: 'B789', _mtime: 1500 }         // sólo en PC2
  };
  const merged = merge(pc1, pc2);
  ok(merged['caja.config.empresa1.v1'].name === 'Autoescuela Norte MOD', 'Empresa1 config: más reciente gana (mtime 3000)');
  ok(merged['caja.config.empresa2.v1'].name === 'Autoescuela Sur', 'Empresa2 config: sólo en PC1 → preservada');
  ok(merged['caja.config.empresa3.v1'].name === 'Autoescuela Este', 'Empresa3 config: sólo en PC2 → añadida');
  const e1day = merged['caja.byDate.empresa1.v1']['2026-04-01'];
  ok(e1day.length === 2, `Empresa1 día → 2 entradas (fusión) (got ${e1day.length})`);
  const e1ids = e1day.map(e => e.id);
  ok(e1ids.includes('e1-A') && e1ids.includes('e1-B'), 'Ambas empresas preservan datos');
}

// ══ Escenario 4: Datos sólo en un PC (no borra, sólo añade) ══
console.log('\n▸ Escenario 4: Datos sólo en un PC → añadidos, no borrados');
{
  const pc1 = {
    'caja.trafico.v1': [{ id: 't-01' }, { id: 't-02' }],
    'caja.revisiones.v1': [{ id: 'r-01' }]
  };
  const pc2 = {
    'caja.trafico.v1': [{ id: 't-01' }, { id: 't-03' }],  // t-02 no está en pc2, pero se conserva
    'caja.revisiones.v1': []
  };
  const merged = merge(pc1, pc2);
  const trafIds = merged['caja.trafico.v1'].map(e => e.id);
  ok(trafIds.length === 3, `Trafico 3 entradas (t-01,t-02,t-03) (got ${trafIds.length}: ${trafIds.join(',')})`);
  ok(trafIds.includes('t-02'), 'PC1 t-02 preservado aunque no esté en PC2');
  ok(new Set(trafIds).size === 3, 'IDs únicos');
  const revs = merged['caja.revisiones.v1'];
  ok(revs.length === 1 && revs[0].id === 'r-01', 'Revisión de PC1 preservada aunque PC2 tenga array vacío');
}

// ══ Escenario 5: Merge múltiples días distintos (byDate) ══
console.log('\n▸ Escenario 5: Merge byDate con días distintos');
{
  const pc1 = { 'caja.byDate.v1': {
    '2026-04-01': [{ id: 'd1-A' }],
    '2026-04-02': [{ id: 'd2-A' }]
  }};
  const pc2 = { 'caja.byDate.v1': {
    '2026-04-02': [{ id: 'd2-B' }],   // añade al mismo día
    '2026-04-03': [{ id: 'd3-A' }]    // día nuevo
  }};
  const merged = merge(pc1, pc2);
  const bd = merged['caja.byDate.v1'];
  ok(Object.keys(bd).length === 3, `3 días distintos (got ${Object.keys(bd).length})`);
  ok(bd['2026-04-01'].length === 1 && bd['2026-04-01'][0].id === 'd1-A', 'Día 1 sólo PC1 preservado');
  ok(bd['2026-04-02'].length === 2, `Día 2 fusionado (2 entradas) (got ${bd['2026-04-02'].length})`);
  ok(bd['2026-04-03'].length === 1 && bd['2026-04-03'][0].id === 'd3-A', 'Día 3 sólo PC2 preservado');
}

// ══ Escenario 6: Config con _mtime (last-write-wins) ══
console.log('\n▸ Escenario 6: Config con _mtime → last-write-wins');
{
  const pc1 = { 'caja.license.v1': { key: 'AAA', _mtime: 5000 } };
  const pc2 = { 'caja.license.v1': { key: 'BBB', _mtime: 3000 } };
  const merged = merge(pc1, pc2);
  ok(merged['caja.license.v1'].key === 'AAA', `PC1 más reciente gana (got ${merged['caja.license.v1'].key})`);

  const pc1b = { 'caja.plan.v1': { plan: 'STD', _mtime: 1000 } };
  const pc2b = { 'caja.plan.v1': { plan: 'PRM', _mtime: 9999 } };
  const mb = merge(pc1b, pc2b);
  ok(mb['caja.plan.v1'].plan === 'PRM', 'PC2 más reciente gana');
}

// ══ Escenario 7: Idempotente (merge dos veces con los mismos datos NO añade duplicados) ══
console.log('\n▸ Escenario 7: Idempotente (merge repetido no duplica)');
{
  const pc1 = { 'caja.byDate.v1': { '2026-05-01': [
    { id: 'x-1', amount: 10 },
    { id: 'x-2', amount: 20 }
  ]}};
  const pc2 = { 'caja.byDate.v1': { '2026-05-01': [
    { id: 'x-2', amount: 20 },
    { id: 'x-3', amount: 30 }
  ]}};
  const m1 = merge(pc1, pc2);
  const m2 = merge(m1, pc2);      // volver a mergear
  const m3 = merge(m2, m1);       // mergear consigo mismo
  const day = m3['caja.byDate.v1']['2026-05-01'];
  ok(day.length === 3, `3 entradas totales (got ${day.length})`);
  const ids = day.map(e => e.id);
  ok(new Set(ids).size === 3, `IDs únicos: ${ids.join(',')}`);
}

// ══ Escenario 8: Datos SIN id (arrays de strings/numbers) ══
console.log('\n▸ Escenario 8: Arrays sin id (edge case)');
{
  const pc1 = { 'caja.notas.v1': [{ text: 'nota1' }, { text: 'nota2' }] };
  const pc2 = { 'caja.notas.v1': [{ text: 'nota3' }] };
  const merged = merge(pc1, pc2);
  const notas = merged['caja.notas.v1'];
  ok(notas.length === 3, `Sin id → preserva todos (got ${notas.length})`);
}

// ══ Escenario 9: Formato con .byDate anidado ══
console.log('\n▸ Escenario 9: Objeto con .byDate anidado');
{
  const pc1 = { 'caja.libro.v1': {
    version: 1, byDate: { '2026-01-01': [{ id: 'a' }] }
  }};
  const pc2 = { 'caja.libro.v1': {
    version: 1, byDate: { '2026-01-01': [{ id: 'b' }], '2026-01-02': [{ id: 'c' }] }
  }};
  const merged = merge(pc1, pc2);
  const libro = merged['caja.libro.v1'];
  ok(Object.keys(libro.byDate).length === 2, `2 días en byDate (got ${Object.keys(libro.byDate).length})`);
  ok(libro.byDate['2026-01-01'].length === 2, 'día 01 fusionado');
  ok(libro.byDate['2026-01-02'].length === 1, 'día 02 añadido');
}

// ══ Escenario 10: Volumen grande (500 entradas por día) ══
console.log('\n▸ Escenario 10: Volumen grande (500 entradas)');
{
  const pc1arr = [], pc2arr = [];
  for(let i=0; i<500; i++){ pc1arr.push({ id: `p1-${i}`, amount: i }); }
  for(let i=0; i<500; i++){ pc2arr.push({ id: `p2-${i}`, amount: i }); }
  // 50 con el mismo id que PC1 pero valor distinto
  for(let i=0; i<50; i++){ pc2arr.push({ id: `p1-${i}`, amount: 99999, updated_at: '2099-01-01T00:00:00Z' }); }
  const pc1 = { 'caja.big.v1': { '2026-06-01': pc1arr } };
  const pc2 = { 'caja.big.v1': { '2026-06-01': pc2arr } };
  const t0 = Date.now();
  const merged = merge(pc1, pc2);
  const t1 = Date.now();
  const day = merged['caja.big.v1']['2026-06-01'];
  ok(day.length === 1000, `1000 entradas únicas (got ${day.length})`);
  ok(t1 - t0 < 100, `Merge <100ms (took ${t1-t0}ms)`);
  const overwritten = day.find(e => e.id === 'p1-0');
  ok(overwritten.amount === 99999, 'Los 50 IDs conflictivos → gana el updated_at más reciente');
}

// ══ Summary ══
console.log(`\n═══════════════════════════════════`);
if(fail === 0) console.log(`✅ TODOS PASAN · ${pass}/${pass+fail}`);
else console.log(`❌ FALLAN ${fail}/${pass+fail}`);
console.log(`═══════════════════════════════════\n`);
process.exit(fail === 0 ? 0 : 1);
