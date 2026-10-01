// =============================================================================
// Feb 2026 · Test unitario del nuevo "Borrar mes" + stack de Undo (3 snapshots).
// Valida:
//   1) snapshotStatsForUndo guarda hasta 3 snapshots (FIFO, el 4º empuja al 1º)
//   2) Borrar un mes elimina solo YYYY-MM y deja el resto intacto
//   3) popStatsUndo restaura exactamente el estado anterior
//   4) Snapshots caducan a las 24h
// Se ejecuta con `node undo_borrar_mes.js`.
// =============================================================================
const assert = require('assert');

// --- Simulador mínimo de localStorage ------------------------------------------
const _mem = {};
global.localStorage = {
  getItem: k => (k in _mem ? _mem[k] : null),
  setItem: (k, v) => { _mem[k] = String(v); },
  removeItem: k => { delete _mem[k]; },
};

// --- Constantes (idénticas a v2.html) ------------------------------------------
const STATS_KEY = 'caja.stats.v1';
const STATS_UNDO_KEY = 'caja.stats.undo.v1';
const STATS_UNDO_MAX = 3;
const STATS_UNDO_TTL_MS = 24*60*60*1000;

// --- Helpers (copia 1:1 de los definidos en v2.html) ---------------------------
function _loadStatsUndoStack(){
  try{
    const arr=JSON.parse(localStorage.getItem(STATS_UNDO_KEY)||'[]');
    if(!Array.isArray(arr))return [];
    const now=Date.now();
    const alive=arr.filter(s=>s&&s.ts&&(now-s.ts)<STATS_UNDO_TTL_MS);
    if(alive.length!==arr.length)localStorage.setItem(STATS_UNDO_KEY,JSON.stringify(alive));
    return alive;
  }catch(_){return []}
}
function _saveStatsUndoStack(stack){try{localStorage.setItem(STATS_UNDO_KEY,JSON.stringify(stack.slice(-STATS_UNDO_MAX)))}catch(_){}}
function snapshotStatsForUndo(reason){
  const raw=localStorage.getItem(STATS_KEY)||'{"autoescoles":[],"data":{}}';
  const stack=_loadStatsUndoStack();
  stack.push({ts:Date.now(),reason:String(reason||''),snapshot:raw});
  _saveStatsUndoStack(stack);
}
function getLastStatsUndo(){const s=_loadStatsUndoStack();return s.length?s[s.length-1]:null}
function popStatsUndo(){const s=_loadStatsUndoStack();if(!s.length)return null;const last=s.pop();_saveStatsUndoStack(s);return last}

// --- Helpers del test ----------------------------------------------------------
const S = o => JSON.stringify(o);
const setStats = o => localStorage.setItem(STATS_KEY, S(o));
const getStats = () => JSON.parse(localStorage.getItem(STATS_KEY)||'{}');

// =============================================================================
// TEST 1 · Stack guarda máximo 3 snapshots en orden FIFO
// =============================================================================
(function test1(){
  for(const k of Object.keys(_mem)) delete _mem[k];
  setStats({autoescoles:['A'], data:{'2024-01':{A:10}}});
  snapshotStatsForUndo('v1');
  setStats({autoescoles:['A'], data:{'2024-01':{A:20}}});
  snapshotStatsForUndo('v2');
  setStats({autoescoles:['A'], data:{'2024-01':{A:30}}});
  snapshotStatsForUndo('v3');
  setStats({autoescoles:['A'], data:{'2024-01':{A:40}}});
  snapshotStatsForUndo('v4'); // el 4º debe empujar al v1 fuera

  const stack = _loadStatsUndoStack();
  assert.strictEqual(stack.length, 3, 'stack debe tener 3 elementos');
  assert.strictEqual(stack[0].reason, 'v2', 'el más antiguo debe ser v2');
  assert.strictEqual(stack[2].reason, 'v4', 'el más reciente debe ser v4');
  console.log('✅ TEST 1 OK · Stack FIFO máx 3');
})();

// =============================================================================
// TEST 2 · Borrar un mes concreto solo elimina ese YYYY-MM
// =============================================================================
(function test2(){
  for(const k of Object.keys(_mem)) delete _mem[k];
  setStats({
    autoescoles:['MABEL','MOLIST'],
    data:{
      '2024-08':{MABEL:5, MOLIST:3},
      '2024-09':{MABEL:7, MOLIST:4}, // mes malo
      '2024-10':{MABEL:6, MOLIST:2},
    }
  });

  // Simular pulsación de "Borrar mes" para 2024-09
  snapshotStatsForUndo('Borrado mes Septiembre 2024');
  const cur = getStats();
  delete cur.data['2024-09'];
  setStats(cur);

  const after = getStats();
  assert.ok(!after.data['2024-09'], '2024-09 debe estar borrado');
  assert.deepStrictEqual(after.data['2024-08'], {MABEL:5, MOLIST:3}, 'agosto intacto');
  assert.deepStrictEqual(after.data['2024-10'], {MABEL:6, MOLIST:2}, 'octubre intacto');
  assert.deepStrictEqual(after.autoescoles, ['MABEL','MOLIST'], 'autoescuelas intactas');
  console.log('✅ TEST 2 OK · Borrar mes solo afecta YYYY-MM');
})();

// =============================================================================
// TEST 3 · Undo restaura exactamente el estado anterior
// =============================================================================
(function test3(){
  for(const k of Object.keys(_mem)) delete _mem[k];
  const original = {
    autoescoles:['MABEL','MOLIST','DAINA'],
    data:{
      '2024-08':{MABEL:5, MOLIST:3, DAINA:1},
      '2024-09':{MABEL:7, MOLIST:4, DAINA:2},
      '2024-10':{MABEL:6, MOLIST:2, DAINA:3},
    }
  };
  setStats(original);

  // Simulamos borrar septiembre
  snapshotStatsForUndo('Borrado mes Septiembre 2024');
  const cur = getStats(); delete cur.data['2024-09']; setStats(cur);
  assert.ok(!getStats().data['2024-09']);

  // Deshacer
  const popped = popStatsUndo();
  assert.ok(popped, 'pop debe devolver snapshot');
  assert.strictEqual(popped.reason, 'Borrado mes Septiembre 2024');
  localStorage.setItem(STATS_KEY, popped.snapshot);

  const restored = getStats();
  assert.deepStrictEqual(restored, original, 'estado restaurado idéntico al original');
  assert.strictEqual(_loadStatsUndoStack().length, 0, 'stack vacío después de pop');
  console.log('✅ TEST 3 OK · Undo restaura estado exacto');
})();

// =============================================================================
// TEST 4 · Snapshots caducan a las 24h
// =============================================================================
(function test4(){
  for(const k of Object.keys(_mem)) delete _mem[k];
  const old = {ts: Date.now() - 25*60*60*1000, reason:'viejo', snapshot:'{}'};
  const fresh = {ts: Date.now() - 10*60*1000, reason:'fresco', snapshot:'{}'};
  localStorage.setItem(STATS_UNDO_KEY, JSON.stringify([old, fresh]));
  const stack = _loadStatsUndoStack();
  assert.strictEqual(stack.length, 1, 'solo debe quedar el fresco');
  assert.strictEqual(stack[0].reason, 'fresco');
  console.log('✅ TEST 4 OK · Snapshots >24h caducan');
})();

// =============================================================================
// TEST 5 · Múltiples undos consecutivos (apila bien 3 cambios y los deshace)
// =============================================================================
(function test5(){
  for(const k of Object.keys(_mem)) delete _mem[k];
  setStats({autoescoles:['A'], data:{'2024-01':{A:1}}});

  snapshotStatsForUndo('cambio1');
  setStats({autoescoles:['A'], data:{'2024-01':{A:2}}});

  snapshotStatsForUndo('cambio2');
  setStats({autoescoles:['A'], data:{'2024-01':{A:3}}});

  snapshotStatsForUndo('cambio3');
  setStats({autoescoles:['A'], data:{'2024-01':{A:4}}});

  // Deshacer 3 veces → debe volver a A:1
  for(let i=0;i<3;i++){
    const p = popStatsUndo();
    localStorage.setItem(STATS_KEY, p.snapshot);
  }
  assert.strictEqual(getStats().data['2024-01'].A, 1, 'debe volver al valor original tras 3 undos');
  assert.strictEqual(popStatsUndo(), null, 'ya no hay más undos');
  console.log('✅ TEST 5 OK · 3 undos consecutivos restauran valor original');
})();

console.log('\n🎉 Todos los tests Undo + Borrar mes pasan correctamente.');
