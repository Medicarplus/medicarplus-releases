#!/usr/bin/env node
/**
 * 💰 TEST · Sistema de Tarifas Personalizadas
 * ────────────────────────────────────────────
 * Verifica que:
 *   1. Sin reglas → app se comporta como siempre (fallback histórico Canje 66,50€)
 *   2. Con la regla por defecto (seed) → Canje se detecta igual
 *   3. Con reglas custom propias → clasifica según lo definido
 *   4. Regla MÁS específica gana sobre menos específica
 *   5. Variantes de idioma (Expedición vs Expedició) matchean
 *   6. Rangos de importe funcionan
 *   7. Reglas sin criterios NO capturan todo por error
 *   8. Backup/restore de las reglas es lossless
 *
 * Cómo se ejecuta:
 *   node /app/frontend/public/tests/tariff_rules.js
 */

const path = require('path');
const fs = require('fs');

// ── SIMULACIÓN DEL ENTORNO BROWSER ──
const storage = {};
global.localStorage = {
  getItem: (k) => (k in storage ? storage[k] : null),
  setItem: (k, v) => { storage[k] = String(v); },
  removeItem: (k) => { delete storage[k]; },
  clear: () => { for(const k in storage) delete storage[k]; },
};
global.window = { _appDebug: {} };

// ── CARGAR LAS FUNCIONES DEL v2.html EN EL SCOPE ──
const html = fs.readFileSync(path.resolve(__dirname, '../v2.html'), 'utf8');
// Extraer los tres helpers + _effectiveTipo
const startMarker = 'window._getTariffRules = function()';
const endMarker = 'return e.tipo;\n};';
const s = html.indexOf(startMarker);
const e = html.indexOf(endMarker, s) + endMarker.length;
if(s < 0 || e < startMarker.length){
  console.error('❌ No he podido localizar los helpers de tarifas en v2.html');
  process.exit(1);
}
const code = html.slice(s, e);
eval(code); // define window._getTariffRules, _saveTariffRules, _matchTariffRule, _effectiveTipo

// ── ASSERT UTILS ──
let OK = 0, FAIL = 0;
function check(cond, label){
  if(cond){ OK++; console.log('  ✅ ' + label); }
  else { FAIL++; console.log('  ❌ ' + label); }
}
function reset(){ storage['caja.tarifas.rules.v1'] = undefined; delete storage['caja.tarifas.rules.v1']; }

// ── ENTRADAS DE PRUEBA ──
const entryCanjeReal = { kind:'TRAF', tipo:'Expedición', grupo:'Conducción', importe:66.50, nombre:'Cliente A' };
const entryCanjeCA   = { kind:'TRAF', tipo:'Expedició',  grupo:'Conducció',  importe:66.50, nombre:'Client B' };
const entryRenov     = { kind:'TRAF', tipo:'Renovación', grupo:'Conducción', importe:80.00, nombre:'Cliente C' };
const entryExped100  = { kind:'TRAF', tipo:'Expedición', grupo:'Conducción', importe:100.00, nombre:'Cliente D' };
const entryDuplic    = { kind:'TRAF', tipo:'Duplicado',  grupo:'Ciclomotor', importe:25.00, nombre:'Cliente E' };
const entryReview    = { kind:'REVI', tipo:'Prueba de esfuerzo', importe:60.00, nombre:'Deportista X' };

// ═══════════════════════════════════════════════════════════════════
console.log('\n🧪 TEST 1 · Sin reglas configuradas → funciona el fallback histórico');
console.log('════════════════════════════════════════════════════════════════');
reset();
// Al llamar _getTariffRules() por primera vez, hace seed automático con la regla histórica.
// Para simular "sin ninguna regla" borramos manualmente después del seed.
window._getTariffRules(); // seed
window._saveTariffRules([]); // borrar todas
check(window._matchTariffRule(entryCanjeReal) === null, 'sin reglas → matchTariffRule devuelve null');
check(window._effectiveTipo(entryCanjeReal) === 'Canje', 'fallback: 66,50€ Exped+Conduc → Canje');
check(window._effectiveTipo(entryCanjeCA) === 'Canje', 'fallback: variantes catalán (Expedició/Conducció) → Canje');
check(window._effectiveTipo(entryExped100) === 'Expedición', 'fallback: mismo tipo/grupo pero importe distinto → NO se reclasifica');
check(window._effectiveTipo(entryRenov) === 'Renovación', 'fallback: otro tipo → NO se reclasifica');

// ═══════════════════════════════════════════════════════════════════
console.log('\n🧪 TEST 2 · Regla SEED por defecto (primer boot) → Canje detectado');
console.log('════════════════════════════════════════════════════════════════');
reset();
const seed = window._getTariffRules();
check(Array.isArray(seed) && seed.length === 1, 'seed inicial crea 1 regla');
check(seed[0].resultado === 'Canje', 'seed → resultado="Canje"');
check(Math.abs(seed[0].importeExacto - 66.50) < 0.001, 'seed → importeExacto=66.50');
check(window._matchTariffRule(entryCanjeReal) === 'Canje', 'seed clasifica 66,50€ Exped Conduc como Canje');
check(window._matchTariffRule(entryCanjeCA) === 'Canje', 'seed clasifica variantes catalán como Canje');
check(window._matchTariffRule(entryRenov) === null, 'seed NO clasifica renovación 80€');

// ═══════════════════════════════════════════════════════════════════
console.log('\n🧪 TEST 3 · Regla custom del CENTRO A: canje a 80€ + Conducción');
console.log('════════════════════════════════════════════════════════════════');
reset();
window._saveTariffRules([{
  id: 'canje-centro-a', tipos:['Expedición','Expedició'], grupos:['Conducción','Conducció'],
  importeExacto: 80.00, importeMin: null, importeMax: null, resultado: 'Canje',
}]);
check(window._matchTariffRule({kind:'TRAF',tipo:'Expedición',grupo:'Conducción',importe:80.00}) === 'Canje',
      'Centro A: 80€ Exped Conduc → Canje');
check(window._matchTariffRule(entryCanjeReal) === null,
      'Centro A: 66,50€ NO es canje (regla dice 80€)');
check(window._effectiveTipo(entryCanjeReal) === 'Canje',
      'Fallback histórico sigue detectando 66,50€ como Canje (compat retroactiva)');

// ═══════════════════════════════════════════════════════════════════
console.log('\n🧪 TEST 4 · Regla con RANGO (57-63€ como Reposición)');
console.log('════════════════════════════════════════════════════════════════');
reset();
window._saveTariffRules([{
  id: 'reposicion', tipos:['Renovación','Renov'], grupos:['Conducción'],
  importeExacto: null, importeMin: 57, importeMax: 63, resultado: 'Reposición',
}]);
check(window._matchTariffRule({kind:'TRAF',tipo:'Renovación',grupo:'Conducción',importe:60}) === 'Reposición',
      'rango 57-63: 60€ Renov Conduc → Reposición');
check(window._matchTariffRule({kind:'TRAF',tipo:'Renovación',grupo:'Conducción',importe:57}) === 'Reposición',
      'rango límite inferior 57€ inclusive');
check(window._matchTariffRule({kind:'TRAF',tipo:'Renovación',grupo:'Conducción',importe:63}) === 'Reposición',
      'rango límite superior 63€ inclusive');
check(window._matchTariffRule({kind:'TRAF',tipo:'Renovación',grupo:'Conducción',importe:64}) === null,
      'rango: 64€ fuera del rango → null');
check(window._matchTariffRule({kind:'TRAF',tipo:'Renovación',grupo:'Conducción',importe:56}) === null,
      'rango: 56€ fuera del rango → null');

// ═══════════════════════════════════════════════════════════════════
console.log('\n🧪 TEST 5 · Regla MÁS específica gana (importe exacto > rango)');
console.log('════════════════════════════════════════════════════════════════');
reset();
window._saveTariffRules([
  { id: 'r1', tipos:['Expedición'], grupos:[], importeMin: 60, importeMax: 70, resultado: 'Trámite general' },
  { id: 'r2', tipos:['Expedición'], grupos:['Conducción'], importeExacto: 66.50, resultado: 'Canje' },
]);
check(window._matchTariffRule(entryCanjeReal) === 'Canje',
      'especificidad: regla con importe exacto + grupo GANA sobre rango sin grupo');
check(window._matchTariffRule({kind:'TRAF',tipo:'Expedición',grupo:'Ciclomotor',importe:65}) === 'Trámite general',
      'la regla menos específica sí actúa cuando la específica no matchea');

// ═══════════════════════════════════════════════════════════════════
console.log('\n🧪 TEST 6 · Regla solo por importe (sin tipo ni grupo) → tarifa fija');
console.log('════════════════════════════════════════════════════════════════');
reset();
window._saveTariffRules([
  { id: 'foto', tipos:[], grupos:[], importeExacto: 4.00, resultado: 'Foto carné' },
]);
check(window._matchTariffRule({kind:'TRAF',tipo:'Otro',grupo:'',importe:4.00}) === 'Foto carné',
      'solo importe: 4€ → Foto carné (sin importar tipo/grupo)');
check(window._matchTariffRule({kind:'TRAF',tipo:'Otro',grupo:'',importe:5.00}) === null,
      'solo importe: 5€ ≠ 4€ → null');

// ═══════════════════════════════════════════════════════════════════
console.log('\n🧪 TEST 7 · Regla VACÍA (sin ningún criterio) NO captura nada');
console.log('════════════════════════════════════════════════════════════════');
reset();
window._saveTariffRules([{ id: 'vacia', tipos:[], grupos:[], resultado: 'X' }]);
check(window._matchTariffRule(entryCanjeReal) === null,
      'regla sin criterios: no aplica jamás (evita capturas por accidente)');
check(window._matchTariffRule({kind:'TRAF',tipo:'A',grupo:'B',importe:0}) === null,
      'regla sin criterios: importe 0€ tampoco captura');

// ═══════════════════════════════════════════════════════════════════
console.log('\n🧪 TEST 8 · Backup/Restore de reglas es lossless');
console.log('════════════════════════════════════════════════════════════════');
reset();
const originalRules = [
  { id: 'a', tipos:['Expedición'], grupos:['Conducción'], importeExacto: 66.50, resultado: 'Canje' },
  { id: 'b', tipos:['Renov','Renovación'], grupos:['Conducción'], importeMin: 80, importeMax: 100, resultado: 'Renov especial' },
  { id: 'c', tipos:[], grupos:[], importeExacto: 25, resultado: 'Duplicado' },
];
window._saveTariffRules(originalRules);
const serialized = storage['caja.tarifas.rules.v1'];
check(serialized && serialized.length > 100, 'reglas serializadas a JSON');
// Simular restore
storage['caja.tarifas.rules.v1'] = serialized;
const restored = window._getTariffRules();
check(restored.length === 3, 'restaurar → 3 reglas recuperadas');
check(restored[0].resultado === 'Canje' && Math.abs(restored[0].importeExacto - 66.50) < 0.001, 'regla A intacta');
check(restored[1].tipos.length === 2 && restored[1].importeMin === 80 && restored[1].importeMax === 100, 'regla B rango intacto');
check(restored[2].importeExacto === 25 && restored[2].resultado === 'Duplicado', 'regla C intacta');
// Verificar comportamiento post-restore
check(window._matchTariffRule(entryCanjeReal) === 'Canje', 'post-restore: 66,50€ → Canje');
check(window._matchTariffRule({kind:'TRAF',tipo:'Renovación',grupo:'Conducción',importe:90}) === 'Renov especial', 'post-restore: 90€ renov → Renov especial');

// ═══════════════════════════════════════════════════════════════════
console.log('\n🧪 TEST 9 · Validación en _saveTariffRules (limpia campos inválidos)');
console.log('════════════════════════════════════════════════════════════════');
reset();
window._saveTariffRules([
  { id: 'valida', tipos:['A'], grupos:[], importeExacto: 10, resultado: 'X' },
  { id: 'sin-resultado', tipos:['B'], grupos:[], importeExacto: 20, resultado: '   ' }, // se descarta
  { id: 'con-strings-vacios', tipos:['','C',' '], grupos:[' '], importeExacto: 30, resultado: 'Y' }, // strings vacíos se limpian
]);
const cleaned = window._getTariffRules();
check(cleaned.length === 2, 'regla sin resultado descartada · 2 reglas guardadas de 3 propuestas');
const y = cleaned.find(r => r.resultado === 'Y');
check(y && y.tipos.length === 1 && y.tipos[0] === 'C', 'strings vacíos filtrados de tipos');
check(y && y.grupos.length === 0, 'grupo solo con espacios filtrado (queda []);');

// ═══════════════════════════════════════════════════════════════════
console.log('\n🧪 TEST 10 · Caso real: importar CSV con mezcla de operaciones');
console.log('════════════════════════════════════════════════════════════════');
reset();
window._saveTariffRules([
  { id: 'canje', tipos:['Expedicion'], grupos:['Conduccion'], importeExacto: 66.50, resultado: 'Canje' },
  { id: 'foto', tipos:[], grupos:[], importeExacto: 4, resultado: 'Foto carné' },
  { id: 'co', tipos:['Certificado'], grupos:[], importeExacto: 20, resultado: 'Certificado Oficial' },
]);
const csvBatch = [
  { kind:'TRAF', tipo:'Expedición', grupo:'Conducción', importe:66.50, nombre:'Juan Pérez' },
  { kind:'TRAF', tipo:'Renovación', grupo:'Conducción', importe:80.00, nombre:'Ana García' },
  { kind:'TRAF', tipo:'Otro',       grupo:'',           importe:4.00,  nombre:'Foto Luis' },
  { kind:'TRAF', tipo:'Certificado',grupo:'',           importe:20.00, nombre:'C.O. María' },
  { kind:'TRAF', tipo:'Expedició',  grupo:'Conducció',  importe:66.50, nombre:'Pere Ferrer' },  // catalán
  { kind:'TRAF', tipo:'Duplicado',  grupo:'Ciclomotor', importe:25.00, nombre:'Roger Puig' },
];
const expected = ['Canje','Renovación','Foto carné','Certificado Oficial','Canje','Duplicado'];
const actual = csvBatch.map(e => window._effectiveTipo(e));
check(JSON.stringify(actual) === JSON.stringify(expected), `CSV real reclasifica correctamente: ${JSON.stringify(actual)}`);

// Contadores agregados por tipo (como hace la app en las stats)
const counts = {};
for(const e of csvBatch){
  const t = window._effectiveTipo(e);
  counts[t] = (counts[t]||0)+1;
}
check(counts['Canje'] === 2, `agregado: 2 Canjes (recibió ${counts['Canje']})`);
check(counts['Foto carné'] === 1, `agregado: 1 Foto carné`);
check(counts['Certificado Oficial'] === 1, `agregado: 1 CO`);
check(counts['Renovación'] === 1 && counts['Duplicado'] === 1, 'agregado: renov + duplicado sin tocar');

// ═══════════════════════════════════════════════════════════════════
console.log('\n🧪 TEST 11 · Match POR RAÍZ · escribir sin tildes vale para CA+ES');
console.log('════════════════════════════════════════════════════════════════');
reset();
// El usuario escribe UNA sola palabra sin tildes por regla · debe matchear
// tanto la castellana como la catalana automáticamente (misma raíz).
window._saveTariffRules([
  { id: 'canje',      tipos:['Expedicion'],  grupos:['Conduccion'],  importeExacto: 66.50, resultado: 'Canje' },
  { id: 'renov',      tipos:['Renovacion'],  grupos:['Conduccion'],  importeMin: 78, importeMax: 100, resultado: 'Renov Cond' },
  { id: 'recup',      tipos:['Recuperacion'], grupos:[],             importeMin: 100, importeMax: 300, resultado: 'Recuperación' },
  { id: 'duplic',     tipos:['Duplicado'],   grupos:[],              importeExacto: 25, resultado: 'Duplicat' },
  { id: 'ciclomotor', tipos:[],              grupos:['Ciclomotor'],  importeMin: 50, importeMax: 100, resultado: 'Trámite ciclo' },
]);

// A) EXPEDICIÓN (es) + EXPEDICIÓ (ca) con Conducción/Conducció
check(window._matchTariffRule({kind:'TRAF',tipo:'Expedición',grupo:'Conducción',importe:66.50}) === 'Canje',
      'raíz: "Expedicion" regla ↔ "Expedición" (es) → Canje');
check(window._matchTariffRule({kind:'TRAF',tipo:'Expedició',grupo:'Conducció',importe:66.50}) === 'Canje',
      'raíz: "Expedicion" regla ↔ "Expedició" (ca) → Canje (misma raíz expedicio)');
check(window._matchTariffRule({kind:'TRAF',tipo:'EXPEDICION',grupo:'CONDUCCION',importe:66.50}) === 'Canje',
      'raíz: mayúsculas también matchean');

// B) RENOVACIÓN (es) + RENOVACIÓ (ca)
check(window._matchTariffRule({kind:'TRAF',tipo:'Renovación',grupo:'Conducción',importe:80}) === 'Renov Cond',
      'raíz: "Renovacion" regla ↔ "Renovación" (es) → Renov Cond');
check(window._matchTariffRule({kind:'TRAF',tipo:'Renovació',grupo:'Conducció',importe:80}) === 'Renov Cond',
      'raíz: "Renovacion" regla ↔ "Renovació" (ca) → Renov Cond');

// C) RECUPERACIÓN (es) + RECUPERACIÓ (ca)
check(window._matchTariffRule({kind:'TRAF',tipo:'Recuperación',grupo:'Conducción',importe:150}) === 'Recuperación',
      'raíz: "Recuperacion" ↔ "Recuperación" (es)');
check(window._matchTariffRule({kind:'TRAF',tipo:'Recuperació',grupo:'Conducció',importe:150}) === 'Recuperación',
      'raíz: "Recuperacion" ↔ "Recuperació" (ca)');

// D) DUPLICADO (es) + DUPLICAT (ca)
check(window._matchTariffRule({kind:'TRAF',tipo:'Duplicado',grupo:'',importe:25}) === 'Duplicat',
      'raíz: "Duplicado" (es) matchea la regla');
check(window._matchTariffRule({kind:'TRAF',tipo:'Duplicat',grupo:'',importe:25}) === 'Duplicat',
      'raíz: "Duplicado" regla ↔ "Duplicat" (ca) → Duplicat (raíz común "duplica")');

// E) GRUPO CICLOMOTOR (mismo nombre en ambos idiomas)
check(window._matchTariffRule({kind:'TRAF',tipo:'Renovación',grupo:'Ciclomotor',importe:60}) === 'Trámite ciclo',
      'grupo: "Ciclomotor" matchea');

// F) NO matchea si son palabras distintas de raíz diferente
check(window._matchTariffRule({kind:'TRAF',tipo:'Certificado',grupo:'Conducción',importe:66.50}) === null,
      'raíz: "Certificado" NO comparte raíz con "Expedicion" → null');
// La entrada "Expedición Ciclomotor 66,50€" NO matchea la regla Canje (grupo Ciclomotor ≠ Conduccion)
// pero SÍ matchea la regla "ciclomotor" (grupo=Ciclomotor + importe 66,50 dentro del rango 50-100).
check(window._matchTariffRule({kind:'TRAF',tipo:'Expedición',grupo:'Ciclomotor',importe:66.50}) === 'Trámite ciclo',
      'raíz: Expedición Ciclomotor 66,50€ NO es canje pero sí Trámite ciclo (matchea la regla más apropiada)');

// G) Mezcla realista del CSV con solo raíces sin tildes
const mixedCA_ES = [
  { kind:'TRAF', tipo:'Expedición',   grupo:'Conducción',  importe:66.50 }, // Canje
  { kind:'TRAF', tipo:'Expedició',    grupo:'Conducció',   importe:66.50 }, // Canje (ca)
  { kind:'TRAF', tipo:'Renovación',   grupo:'Conducción',  importe:80.00 }, // Renov Cond
  { kind:'TRAF', tipo:'Renovació',    grupo:'Conducció',   importe:85.00 }, // Renov Cond (ca)
  { kind:'TRAF', tipo:'Recuperació',  grupo:'',            importe:200.00 }, // Recuperación
  { kind:'TRAF', tipo:'Duplicat',     grupo:'',            importe:25.00 }, // Duplicat
  { kind:'TRAF', tipo:'Renovación',   grupo:'Ciclomotor',  importe:65.00 }, // Trámite ciclo
];
const results = mixedCA_ES.map(e => window._matchTariffRule(e));
const expectedMixed = ['Canje','Canje','Renov Cond','Renov Cond','Recuperación','Duplicat','Trámite ciclo'];
check(JSON.stringify(results) === JSON.stringify(expectedMixed),
      `CSV mixto CA+ES con reglas sin tildes: ${JSON.stringify(results)}`);

// ═══════════════════════════════════════════════════════════════════
console.log('\n🧪 TEST 12 · Espacios, mayúsculas, guiones y puntos no importan');
console.log('════════════════════════════════════════════════════════════════');
reset();
window._saveTariffRules([
  { id:'canje', tipos:['Expedicion'], grupos:['Conduccion'], importeExacto:66.50, resultado:'Canje' },
]);
check(window._matchTariffRule({kind:'TRAF',tipo:'  EXPEDICIÓN  ',grupo:'CONDUCCIÓN',importe:66.50}) === 'Canje',
      'trim: espacios sobrantes al inicio/fin no importan');
check(window._matchTariffRule({kind:'TRAF',tipo:'expedicion',grupo:'conduccion',importe:66.50}) === 'Canje',
      'mayus/minus: todo lowercase también matchea');
check(window._matchTariffRule({kind:'TRAF',tipo:'Exped.',grupo:'Conduc.',importe:66.50}) === 'Canje',
      'abreviaturas con punto: "Exped." matchea gracias a prefijo común');
check(window._matchTariffRule({kind:'TRAF',tipo:'Expedicio-B',grupo:'Conducció-A2',importe:66.50}) === 'Canje',
      'guiones y sufijos: la raíz se detecta igual');

// ═══════════════════════════════════════════════════════════════════
console.log('\n🧪 TEST 13 · Regla del CENTRO MÉDICO (owner) sigue funcionando igual');
console.log('════════════════════════════════════════════════════════════════');
reset();
// El seed inicial que el owner ya tiene configurado en su centro
const ownerRule = window._getTariffRules(); // debe hacer seed
check(ownerRule.length === 1 && ownerRule[0].resultado === 'Canje', 'seed default = 1 regla Canje');
// Verificamos con los CSV reales que le llegan al owner
const ownerCsv = [
  { kind:'TRAF', tipo:'Expedició',  grupo:'Conducció',  importe:66.50, nombre:'JORDI FONT' },
  { kind:'TRAF', tipo:'Expedició',  grupo:'Conducció',  importe:66.50, nombre:'MARIA SOLE' },
  { kind:'TRAF', tipo:'Renovació',  grupo:'Conducció',  importe:80.00, nombre:'PERE MAS' },
  { kind:'TRAF', tipo:'Expedició',  grupo:'Ciclomotor', importe:66.50, nombre:'ARNAU RIU' }, // NO es canje (ciclomotor)
  { kind:'TRAF', tipo:'Obtenció',   grupo:'Conducció',  importe:66.50, nombre:'CLARA ROIG' }, // Sí es canje (obtenció alt)
];
const ownerResults = ownerCsv.map(e => window._effectiveTipo(e));
const ownerExpected = ['Canje','Canje','Renovació','Expedició','Canje'];
check(JSON.stringify(ownerResults) === JSON.stringify(ownerExpected),
      `Owner CSV clasificado bien: ${JSON.stringify(ownerResults)}`);

// ═══════════════════════════════════════════════════════════════════
console.log('\n═══════════════════════════════════════════════════════════════════');
console.log(`   📊 RESULTADO: ${OK} OK · ${FAIL} FAIL`);
console.log('═══════════════════════════════════════════════════════════════════');
if(FAIL === 0){
  console.log('   🎉 SISTEMA DE TARIFAS PERSONALIZADAS · 100% FUNCIONAL');
  process.exit(0);
} else {
  console.log(`   ⚠️  ${FAIL} test(s) fallaron — revisar arriba`);
  process.exit(1);
}
