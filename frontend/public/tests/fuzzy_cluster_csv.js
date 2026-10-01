// =============================================================================
// Oct 2026 · Tests de la nueva lógica fuzzy + pre-clustering CSV + dedup
// Caso real del usuario (CSV con typos de MOLIST):
//   MOLIST(CALLDETENES)=5 · MOLIST (CALLDETENES)=1 · MLIST(CALLDETENES)=1
//   Deben agruparse en UN solo MOLIST(CALLDETENES)=7
//   PERO: MOLIST (sola)=1 debe quedar APARTE (sede distinta)
// =============================================================================
const assert = require('assert');

// -- Copia 1:1 de las funciones en v2.html --
function _normalizeAutoName(s){
  return String(s||'')
    .toUpperCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g,'')
    .replace(/^A\.?E\.?\s*[-·.]?\s*/,'')
    .replace(/[^A-Z0-9]/g,'')
    .replace(/S/g,'C');
}
function _levDist(a, b){
  const m = a.length, n = b.length;
  if(m === 0) return n;
  if(n === 0) return m;
  const dp = Array.from({length: m+1}, () => new Array(n+1).fill(0));
  for(let i = 0; i <= m; i++) dp[i][0] = i;
  for(let j = 0; j <= n; j++) dp[0][j] = j;
  for(let i = 1; i <= m; i++){
    for(let j = 1; j <= n; j++){
      dp[i][j] = (a[i-1] === b[j-1])
        ? dp[i-1][j-1]
        : 1 + Math.min(dp[i-1][j-1], dp[i-1][j], dp[i][j-1]);
    }
  }
  return dp[m][n];
}
function _similarity(a, b){
  const na = _normalizeAutoName(a), nb = _normalizeAutoName(b);
  if(!na || !nb) return 0;
  if(na === nb) return 1;
  const [sh, lo] = na.length <= nb.length ? [na,nb] : [nb,na];
  if(lo.startsWith(sh)){
    const extra = lo.length - sh.length;
    if(sh.length <= 3) return 0.95;
    if(extra <= 3)      return 0.92;
  }
  const dist = _levDist(na, nb);
  const maxLen = Math.max(na.length, nb.length);
  return maxLen === 0 ? 0 : (1 - (dist / maxLen));
}

// =============================================================================
// TEST 1 · Casuística completa de similitud
// =============================================================================
(function test1(){
  const cases = [
    ['MABEL', 'A.E.MABEL', true, 'prefijo A.E. idéntico'],
    ['DAINA', 'A.E.DAINA', true, 'prefijo A.E. idéntico'],
    ['M2', 'A.E.M-2 (CENTELLES)', true, 'nombre corto prefijo'],
    ['M2', 'M-2', true, 'guion ignorado'],
    ['LLUÇANES', 'LLUCANÈS', true, 'cedilla/tildes'],
    ['AVANÇA', 'AVANÇADA', true, '+2 letras feminino'],
    ['AVANSADA', 'AVANÇA', true, 'S≡Ç fonética catalana'],
    ['AVANSA', 'AVANÇA', true, 'S≡Ç idéntico tras normalizar'],
    ['MOLIST(CALLDETENES)', 'MOLIST (CALLDETENES)', true, 'espacio y paréntesis'],
    ['MOLIST (CALLDETENES)', 'MLIST(CALLDETENES)', true, 'typo Levenshtein'],
    ['MLIST(CALLDETENES)', 'MOLIST(CALLDETENES)', true, 'typo Levenshtein'],
    ['SARRIO', 'SARRIÓ', true, 'tilde en Ó'],
    ['ROSSELL', 'ROSELL', true, 'doble letra'],
    // No deben fusionar:
    ['MOLIST', 'MOLIST CALLDETENES', false, 'sedes distintas'],
    ['MOLIST', 'MOLIST(CALLDETENES)', false, 'sedes distintas'],
    ['DAINA', 'DAINA CENTRO', false, 'sedes distintas'],
    ['CARRERA', 'CLAPERA', false, 'nombres distintos'],
    ['TUNEU', 'TERÇOL', false, 'nombres distintos'],
  ];
  let pass=0, fail=0;
  for(const [a,b,shouldMatch,desc] of cases){
    const sc = _similarity(a,b);
    const matched = sc >= 0.80;
    const ok = matched === shouldMatch;
    const marker = ok?'✓':'✗';
    const sym = shouldMatch?'≡':'≠';
    console.log(`  ${marker} ${a.padEnd(22)} ${sym} ${b.padEnd(25)} sim=${sc.toFixed(2)}  ${desc}`);
    if(ok)pass++; else fail++;
  }
  console.log(`\n  TEST 1 · ${pass} pass · ${fail} fail`);
  assert.strictEqual(fail, 0, 'Todos los casos de similitud deben pasar');
  console.log('✅ TEST 1 OK');
})();

// =============================================================================
// TEST 2 · Pre-clustering CSV (función _clusterRaws)
// =============================================================================
function clusterRaws(rawCounts){
  const keys=Object.keys(rawCounts).sort((a,b)=>(rawCounts[b]||0)-(rawCounts[a]||0));
  const parent={}; keys.forEach(k=>parent[k]=k);
  const find=(x)=>{ while(parent[x]!==x){ parent[x]=parent[parent[x]]; x=parent[x]; } return x; };
  for(let i=0;i<keys.length;i++){
    for(let j=i+1;j<keys.length;j++){
      const a=keys[i], b=keys[j];
      if(find(a)===find(b))continue;
      if(_similarity(a,b)>=0.80){
        const ra=find(a), rb=find(b);
        const [winner,loser] = (rawCounts[ra]||0) >= (rawCounts[rb]||0) ? [ra,rb] : [rb,ra];
        parent[loser]=winner;
      }
    }
  }
  const clustered={};
  for(const k of keys){
    const canon=find(k);
    clustered[canon]=(clustered[canon]||0)+(rawCounts[k]||0);
  }
  return clustered;
}

(function test2(){
  // Simula el CSV del usuario
  const rawCounts = {
    'SARRIO': 3,
    'MOLIST(CALLDETENES)': 5,
    'MOLIST': 1,
    'CONNECT': 7,
    'HOY-VOY': 35,
    'CLAPERA': 4,
    'OSONA': 2,
    'RECUPERACIO': 3,
    'CARRERA': 2,
    'TARADELL': 5,
    'MANLLEU': 1,
    'MOLIST (CALLDETENES)': 1,
    'M2': 3,
    'TUNEU': 3,
    'MLIST(CALLDETENES)': 1,
    'TERÇOL': 1,
    'PARTICULAR': 36, // ya sumado por CSV reader
  };
  const clustered = clusterRaws(rawCounts);
  console.log('\n  CSV clustered:');
  for(const [k,v] of Object.entries(clustered).sort((a,b)=>b[1]-a[1])){
    console.log(`    ${k.padEnd(25)} = ${v}`);
  }
  // Debe quedar MOLIST(CALLDETENES)=7 (5+1+1) y MOLIST=1 APARTE
  const canonMolistC = Object.keys(clustered).find(k => k.replace(/[^A-Z0-9]/gi,'').toUpperCase()==='MOLISTCALLDETENES');
  assert.ok(canonMolistC, 'debe existir cluster MOLIST(CALLDETENES)');
  assert.strictEqual(clustered[canonMolistC], 7, 'MOLIST(CALLDETENES) total debe ser 5+1+1=7');
  assert.strictEqual(clustered['MOLIST'], 1, 'MOLIST sola debe quedar aparte con 1');
  // SARRIO no se funde con nada (único)
  assert.strictEqual(clustered['SARRIO'], 3);
  // PARTICULAR se mantiene
  assert.strictEqual(clustered['PARTICULAR'], 36);
  console.log('\n✅ TEST 2 OK · Pre-clustering CSV correcto');
})();

// =============================================================================
// TEST 3 · CSV con duplicados masivos (caso edge con todos los tipos)
// =============================================================================
(function test3(){
  const rawCounts = {
    'MABEL': 15,
    'A.E.MABEL': 10,       // debe sumar con MABEL
    'DAINA': 6,
    'A.E DAINA': 2,         // debe sumar con DAINA
    'AVANÇA': 10,
    'AVANÇADA': 1,          // debe sumar con AVANÇA
    'AVANSADA': 1,          // debe sumar con AVANÇA (fonética)
    'LLUÇANES': 5,
    'LLUCANÈS': 2,          // debe sumar con LLUÇANES
    'MOLIST': 1,
    'MOLIST CALLDETENES': 3, // sede distinta, NO suma con MOLIST
  };
  const clustered = clusterRaws(rawCounts);
  console.log('\n  Caso masivo clustered:');
  for(const [k,v] of Object.entries(clustered).sort((a,b)=>b[1]-a[1])){
    console.log(`    ${k.padEnd(25)} = ${v}`);
  }
  // Buscar clusters por normalización
  const findCluster = (want) => {
    const target = _normalizeAutoName(want);
    for(const k of Object.keys(clustered)){
      if(_normalizeAutoName(k) === target) return [k, clustered[k]];
    }
    return null;
  };
  const [,mabelTot] = findCluster('MABEL');
  const [,dainaTot] = findCluster('DAINA');
  const [,avancaTot] = findCluster('AVANÇA');
  const [,llucTot] = findCluster('LLUÇANES');
  assert.strictEqual(mabelTot, 25, 'MABEL+A.E.MABEL = 15+10 = 25');
  assert.strictEqual(dainaTot, 8, 'DAINA+A.E DAINA = 6+2 = 8');
  assert.strictEqual(avancaTot, 12, 'AVANÇA+AVANÇADA+AVANSADA = 10+1+1 = 12');
  assert.strictEqual(llucTot, 7, 'LLUÇANES+LLUCANÈS = 5+2 = 7');
  assert.strictEqual(clustered['MOLIST'], 1, 'MOLIST sola queda con 1');
  assert.strictEqual(clustered['MOLIST CALLDETENES'], 3, 'MOLIST CALLDETENES queda con 3');
  console.log('\n✅ TEST 3 OK · Todos los duplicados agrupados sin perder certs');
})();

console.log('\n🎉 Todos los tests Fuzzy + Pre-clustering CSV pasan.');
