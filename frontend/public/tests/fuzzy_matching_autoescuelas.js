// 🧠 Oct 2026 · Test fuzzy matching · casos reales clarificados por el usuario
//   REGLAS:
//    · MOLIST (sola) ≠ MOLIST CALLDETENES (dos SEDES distintas · NO fusionar)
//    · MOLIST (CALLDETENES) == MOLIST(CALLDETENES) == MLIST(CALLDETENES) (variantes · SÍ fusionar)
//    · AVANSA == AVANÇA (tildes · SÍ fusionar)
//    · AVANÇADA · se trata manualmente (podría ser otra autoescuela)
//    · A.E.DAINA == DAINA (prefijo A.E. quitado · SÍ fusionar)

const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync('/app/frontend/public/v2.html', 'utf8');
const start = html.indexOf('function _normalizeAutoName');
const end   = html.indexOf('const canonicalName');
const sandbox = { console, module: {} };
vm.runInContext(`${html.slice(start,end)}\nmodule.exports = { _normalizeAutoName, _similarity, _bestMatch, _levDist };`,
  vm.createContext(sandbox));
const { _normalizeAutoName, _similarity, _bestMatch } = sandbox.module.exports;

let ok = 0, fail = 0;
function check(cond, label, extra){
  if(cond){ ok++; console.log('  ✅', label); }
  else    { fail++; console.error('  ❌', label, extra||''); }
}

console.log('\n🧠 FUSIONAR (deben matchear)');
const SI = [
  ['MOLIST (CALLDETENES)', 'MOLIST(CALLDETENES)'],
  ['MLIST(CALLDETENES)',   'MOLIST(CALLDETENES)'],
  ['MLIST (CALLDETENES)',  'MOLIST(CALLDETENES)'],
  ['A.E.DAINA',            'DAINA'],
  ['A.E.M-2',              'M2'],
  ['A.E.MABEL',            'MABEL'],
  ['AVANSA',               'AVANÇA'],
  ['ROSELL',               'ROSSELL'],
  ['LLUÇANES',             'LLUÇANÈS'],
];
for(const [a,b] of SI){
  const s = _similarity(a,b);
  check(s >= 0.80, `"${a}" ↔ "${b}" = ${(s*100).toFixed(0)}%`);
}

console.log('\n🧠 NO FUSIONAR (son autoescuelas DIFERENTES)');
const NO = [
  ['MOLIST',               'MOLIST(CALLDETENES)'],  // ← CLAVE: sedes distintas
  ['MOLIST (CALLDETENES)', 'MOLIST'],
  ['DAINA',                'TRÀFIC'],
  ['CANJE',                'TARADELL'],
  ['FERRER',               'CARRERA'],
  ['AVANÇADA',             'MOLIST'],
];
for(const [a,b] of NO){
  const s = _similarity(a,b);
  check(s < 0.80, `"${a}" ↔ "${b}" = ${(s*100).toFixed(0)}% (NO fusiona)`);
}

console.log('\n🧠 CASO REAL del usuario · _bestMatch con lista existente');
const existentes = ['TARADELL','TERÇOL','TRÀFIC','TUNEU','MOLIST','MOLIST CALLDETENES','DAINA','MABEL','AVANÇA','M-2','SARRIÀ','LLUÇANÈS','HOY-VOY'];

// MOLIST(CALLDETENES) debe ir a MOLIST CALLDETENES, NO a MOLIST
let m = _bestMatch('MOLIST(CALLDETENES)', existentes);
check(m && m.name === 'MOLIST CALLDETENES', `"MOLIST(CALLDETENES)" → "${m?.name}" (${m?Math.round(m.score*100):0}%)`);

// MLIST(CALLDETENES) idem
m = _bestMatch('MLIST(CALLDETENES)', existentes);
check(m && m.name === 'MOLIST CALLDETENES', `"MLIST(CALLDETENES)" → "${m?.name}" (${m?Math.round(m.score*100):0}%)`);

// MABEL debe ir a MABEL exacta
m = _bestMatch('MABEL', existentes);
check(m && m.name === 'MABEL', `"MABEL" → "${m?.name}" (${m?Math.round(m.score*100):0}%)`);

// LLUÇANES → LLUÇANÈS (tildes)
m = _bestMatch('LLUÇANES', existentes);
check(m && m.name === 'LLUÇANÈS', `"LLUÇANES" → "${m?.name}" (${m?Math.round(m.score*100):0}%)`);

// SARRIO (typo) → SARRIÀ
m = _bestMatch('SARRIO', existentes);
check(m && m.name === 'SARRIÀ', `"SARRIO" → "${m?.name}" (${m?Math.round(m.score*100):0}%)`);

// A.E.M-2 → M-2
m = _bestMatch('A.E.M-2', existentes);
check(m && m.name === 'M-2', `"A.E.M-2" → "${m?.name}" (${m?Math.round(m.score*100):0}%)`);

// M2 (sin guión) → M-2
m = _bestMatch('M2', existentes);
check(m && m.name === 'M-2', `"M2" → "${m?.name}" (${m?Math.round(m.score*100):0}%)`);

// Caso NEGATIVO · texto nuevo no debería fusionarse
m = _bestMatch('CENTRO NUEVO MADRID', existentes);
check(!m, `"CENTRO NUEVO MADRID" → no sugerido (correcto)`);

console.log('\n' + '='.repeat(70));
console.log(`📊 RESULTADO · ${ok} OK · ${fail} FAIL`);
console.log('='.repeat(70));
if (fail) process.exit(1);
console.log('🧠 Fuzzy matching ajustado · respeta sedes distintas · fusiona typos');
process.exit(0);
