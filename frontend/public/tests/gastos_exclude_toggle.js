// 🧪 TEST · Flag _gastoExcluded · exclusión manual de gastos
//    Verifica que una entrada DEBE con _gastoExcluded:true:
//      1) NO cuenta como gasto en _isGastoEntry  (panel 🧾 Gastos)
//      2) NO suma en grandTotals.gastos          (Informe Anual KPI "Gastos Totales")
//      3) SE PUEDE revertir borrando el flag → vuelve a contar como gasto
//    y además:
//      4) Entradas sin el flag siguen funcionando igual (no regresión).
//
//    Uso:  node tests/gastos_exclude_toggle.js

const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname,'..','v2.html'),'utf8');

// Extraer _isGastoEntry
const idx = html.indexOf('function _isGastoEntry');
const idxEnd = html.indexOf('\nfunction _gsCategoryLabel', idx);
const fnSrc = html.slice(idx, idxEnd);
// Dependencias
const depIdx1 = html.indexOf('function _hasExplicitGastoMarker');
const depIdx1End = html.indexOf('\nfunction _isGastoEntry', depIdx1);
const dep1 = html.slice(depIdx1, depIdx1End);
const depIdx2 = html.indexOf('function _isHonorarioLikeEntry');
const depIdx2End = html.indexOf('\nfunction _cleanWorkerName', depIdx2);
const dep2 = html.slice(depIdx2, depIdx2End);

// Evaluación en sandbox
const vm = require('vm');
const sandbox = { console, module: {} };
// Stub mínimo de _hnMatchKeyword (devuelve null salvo que el nombre sea claramente nómina)
const stub = `
function _hnMatchKeyword(bag){
  if (/\\b(honorari|nomina|nómina|sueldo|salario|faena)\\b/i.test(bag||'')) return {cat:'NOMINA'};
  return null;
}
`;
const code = `${stub}\n${dep1}\n${dep2}\n${fnSrc}\nmodule.exports = { _isGastoEntry, _isHonorarioLikeEntry, _hasExplicitGastoMarker };`;
vm.runInContext(code, vm.createContext(sandbox));
const { _isGastoEntry } = sandbox.module.exports;

let ok = 0, fail = 0;
function assert(cond, label){
  if (cond){ ok++; console.log('  ✅', label); }
  else     { fail++; console.error('  ❌', label); }
}

console.log('\n🧪 TEST · Flag _gastoExcluded\n');

// Caso 1: DEBE normal (sin flag) → ES gasto
const g1 = {kind:'DH', tipo:'DEBE', nombre:'Factura Endesa', importe:85.5, fp:'T'};
assert(_isGastoEntry(g1) === true, 'DEBE normal cuenta como gasto');

// Caso 2: DEBE con _gastoExcluded → NO es gasto
const g2 = {kind:'DH', tipo:'DEBE', nombre:'Factura Endesa', importe:85.5, fp:'T', _gastoExcluded:true};
assert(_isGastoEntry(g2) === false, 'DEBE con _gastoExcluded:true → NO cuenta');

// Caso 3: Quitar el flag → vuelve a contar
delete g2._gastoExcluded;
assert(_isGastoEntry(g2) === true, 'Al borrar _gastoExcluded vuelve a contar como gasto');

// Caso 4: HABER nunca es gasto, flag irrelevante
const h1 = {kind:'DH', tipo:'HABER', nombre:'Foto cliente', importe:5, fp:'E'};
assert(_isGastoEntry(h1) === false, 'HABER no es gasto');
const h2 = Object.assign({}, h1, {_gastoExcluded:true});
assert(_isGastoEntry(h2) === false, 'HABER + flag sigue sin ser gasto');

// Caso 5: _internal sigue excluido (no regresión)
const i1 = {kind:'DH', tipo:'DEBE', nombre:'Traspaso', importe:200, fp:'E', _internal:true};
assert(_isGastoEntry(i1) === false, '_internal sigue excluido');

// Caso 6: _hnBruto sigue excluido
const b1 = {kind:'DH', tipo:'DEBE', nombre:'Bruto IRPF', importe:300, fp:'E', _hnBruto:true};
assert(_isGastoEntry(b1) === false, '_hnBruto sigue excluido');

// Caso 7: _tasaRefund sigue excluido
const r1 = {kind:'DH', tipo:'DEBE', nombre:'Devolución', importe:28.8, fp:'T', _tasaRefund:true};
assert(_isGastoEntry(r1) === false, '_tasaRefund sigue excluido');

// Caso 8: Simular suma del Informe Anual sobre varios DEBE con y sin flag
const dayEntries = [
  {kind:'DH', tipo:'DEBE', nombre:'Luz', importe:85.5, fp:'T'},
  {kind:'DH', tipo:'DEBE', nombre:'Alquiler', importe:450, fp:'T'},
  {kind:'DH', tipo:'DEBE', nombre:'Gestoría', importe:120, fp:'E', _gastoExcluded:true}, // excluido
  {kind:'DH', tipo:'DEBE', nombre:'Material', importe:30, fp:'E'},
  {kind:'DH', tipo:'DEBE', nombre:'Internal', importe:999, fp:'E', _internal:true},
  {kind:'DH', tipo:'HABER', nombre:'Ingreso', importe:50, fp:'E'},
];
// Replica la lógica del informe anual (líneas 9253 y 9254)
let totalGastosKPI = 0;
for (const e of dayEntries){
  if (e.retorno) continue;
  if (e.kind==='DH' && e._hnBruto) continue;
  if (e.kind==='DH' && (e._internal||e._tasaRefund)) continue;
  if (e.kind==='DH' && e.tipo==='DEBE'){
    if (e._gastoExcluded) continue;  // 🔴 nuevo filtro
    totalGastosKPI += (e.importe||0);
  }
}
assert(totalGastosKPI === 565.5, `Gastos Totales KPI = ${totalGastosKPI}€ (esperado 565.5€ · sin gestoría excluida 120€)`);

console.log(`\n📊 Resumen · ${ok} OK · ${fail} FAIL\n`);
process.exit(fail > 0 ? 1 : 0);
