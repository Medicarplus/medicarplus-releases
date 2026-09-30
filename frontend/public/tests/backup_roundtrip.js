#!/usr/bin/env node
/**
 * TEST · Backup Round-Trip · Feb 2026
 *
 * Simula un ordenador CON datos reales → crea copia → simula ordenador NUEVO vacío →
 * aplica la restauración → compara byte a byte.
 *
 * OBJETIVO: demostrar que la restauración deja la caja EXACTAMENTE igual que estaba,
 *           sin perder ni un céntimo ni un apunte.
 */

const crypto = require('crypto');

// ═══════════════════════════════════════════════════════════════════════
// 1️⃣ WHITELIST DE 18 CLAVES (copiada literal de v2.html · DATA_LS_KEYS)
// ═══════════════════════════════════════════════════════════════════════
const DATA_LS_KEYS = [
  'caja.v1',
  'caja.cempla.v1',
  'caja.datafono',
  'caja.cempla.datafono',
  'caja.stats.v1',
  'caja.stats.aliases.v1',
  'caja.stats.traffic.overrides.v1',
  'caja.irpf.v1',
  'caja.saldoInicial.trafic.v1',
  'caja.saldoInicial.cempla.v1',
  'caja.reserva.v1',
  'caja.cempla.reserva.v1',
  'caja.cuadre.overrides.v1',
  'caja.config.v1',
  'caja.calendar.history.v1',
  'caja.calendar.status.v1',
  'caja.calendar.urls.v1',
  'caja.count_zero',
  'caja.tarifas.rules.v1',    // 💰 Feb 2026 · reglas de tarifas personalizadas
];

// ═══════════════════════════════════════════════════════════════════════
// 2️⃣ MOCK localStorage (mismo API que en navegador)
// ═══════════════════════════════════════════════════════════════════════
class LocalStorageMock {
  constructor(){ this._m = new Map(); }
  getItem(k){ return this._m.has(k) ? this._m.get(k) : null; }
  setItem(k, v){ this._m.set(k, String(v)); }
  removeItem(k){ this._m.delete(k); }
  clear(){ this._m.clear(); }
  get length(){ return this._m.size; }
  key(i){ return Array.from(this._m.keys())[i]; }
  keysWithPrefix(p){ return Array.from(this._m.keys()).filter(k => k.startsWith(p)); }
}

// ═══════════════════════════════════════════════════════════════════════
// 3️⃣ FUNCIONES DE BACKUP/RESTORE (copiadas literal de v2.html)
// ═══════════════════════════════════════════════════════════════════════
function _readAllDataKeys(ls){
  const out = {};
  for(const k of DATA_LS_KEYS){
    const v = ls.getItem(k);
    if(v !== null && v !== '') out[k] = v;
  }
  return out;
}
function _writeAllDataKeys(ls, map){
  if(!map || typeof map !== 'object') return;
  for(const k of Object.keys(map)){
    if(!DATA_LS_KEYS.includes(k)) continue;
    const v = map[k];
    if(v !== null && v !== undefined && v !== '') {
      ls.setItem(k, typeof v === 'string' ? v : JSON.stringify(v));
    }
  }
}
function _fullBackupData(ls){
  // Lo que envía sendCloudBackup al servidor
  const out = {};
  for(const k of DATA_LS_KEYS){
    const raw = ls.getItem(k);
    if(raw === null || raw === '') continue;
    try { out[k] = JSON.parse(raw); }
    catch(e){ out[k] = raw; }
  }
  return out;
}

// ═══════════════════════════════════════════════════════════════════════
// 4️⃣ FIXTURE · datos realistas del cliente en el ordenador ORIGINAL
// ═══════════════════════════════════════════════════════════════════════
function crearOrdenadorOriginal(){
  const ls = new LocalStorageMock();

  // 📁 caja.v1 · Entradas Empresa 1 (Tráfico) · 3 años, varios días con importes al céntimo
  ls.setItem('caja.v1', JSON.stringify({
    byDate: {
      '2024-03-15': { rows: [
        { id: 'e1', kind: 'TRAF', nombre: 'María López', importe: 145.55, tasa: 91.60, fp: 'E', cat: 'canje', grupo: 'B' },
        { id: 'e2', kind: 'TRAF', nombre: 'Pedro Sanz',  importe: 220.00, tasa: 91.60, fp: 'T', cat: 'inicial', grupo: 'B' },
      ]},
      '2024-06-30': { rows: [
        { id: 'e3', kind: 'PRIV', nombre: 'Ana Fdez',   importe: 80.00,  tasa: 0,     fp: 'B', cat: 'foto' },
      ]},
      '2025-01-10': { rows: [
        { id: 'e4', kind: 'TRAF', nombre: 'Luis Vidal', importe: 350.75, tasa: 91.60, fp: 'E', cat: 'renovacion', grupo: 'B' },
      ]},
      '2025-12-31': { rows: [
        { id: 'e5', kind: 'HABER', nombre: 'Traspaso caja→banco', importe: 500.00, fpago: 'X', concepto: '_internal_toBanco' },
      ]},
      '2026-02-28': { rows: [
        { id: 'e6', kind: 'TRAF', nombre: 'Cliente hoy', importe: 199.99, tasa: 91.60, fp: 'T', cat: 'inicial', grupo: 'B' },
      ]},
    }
  }));

  // 📁 caja.cempla.v1 · Entradas Empresa 2 (Revisiones médicas)
  ls.setItem('caja.cempla.v1', JSON.stringify({
    byDate: {
      '2025-05-20': { rows: [
        { id: 'c1', kind: 'REV', nombre: 'Paciente 1', importe: 45.00, fp: 'E', tipo: 'B' },
      ]},
      '2026-02-10': { rows: [
        { id: 'c2', kind: 'REV', nombre: 'Paciente 2', importe: 60.00, fp: 'T', tipo: 'C' },
      ]},
    }
  }));

  // 📁 Datáfonos manuales por día
  ls.setItem('caja.datafono', JSON.stringify({
    '2024-03-15': 220.00, '2025-01-10': 0, '2026-02-28': 199.99
  }));
  ls.setItem('caja.cempla.datafono', JSON.stringify({
    '2026-02-10': 60.00
  }));

  // 📁 Autoescolas · stats mensuales
  ls.setItem('caja.stats.v1', JSON.stringify({
    data: {
      '2024-01': { 'AUTOESCOLA MARTINEZ': 88, 'AUTOESCOLA COSTA': 45 },
      '2024-02': { 'AUTOESCOLA MARTINEZ': 92, 'AUTOESCOLA COSTA': 51 },
      '2025-08': { 'AUTOESCOLA MARTINEZ': 65, 'AUTOESCOLA COSTA': 33, 'AUTOESCOLA NOVA': 12 },
      '2026-01': { 'AUTOESCOLA MARTINEZ': 41, 'AUTOESCOLA NOVA': 18 },
    }
  }));
  ls.setItem('caja.stats.aliases.v1', JSON.stringify({
    'MARTINEZ_2020': 'AUTOESCOLA MARTINEZ',
    'COSTA_SL':      'AUTOESCOLA COSTA',
  }));
  ls.setItem('caja.stats.traffic.overrides.v1', JSON.stringify({
    '2025-08': { canje: 12, inicial: 33 },
    '2026-01': { renovacion: 41 },
  }));

  // 📁 IRPF · retenciones y trimestres pagados
  ls.setItem('caja.irpf.v1', JSON.stringify({
    months: { '2024-Q1': 155.55, '2024-Q2': 289.90, '2025-Q3': 412.30 },
    quarters: { '2024-Q1': { pagado: true, fecha: '2024-04-20' }, '2024-Q2': { pagado: true, fecha: '2024-07-19' } }
  }));

  // 📁 Saldo Inicial · AMBAS empresas independientes
  ls.setItem('caja.saldoInicial.trafic.v1', JSON.stringify({
    fecha: '2024-01-01', efectivo: 1250.75, banco: 8890.20, cambio: 200.00,
    nota: 'Saldo apertura E1 al empezar con la app'
  }));
  ls.setItem('caja.saldoInicial.cempla.v1', JSON.stringify({
    fecha: '2024-03-01', efectivo: 340.50, banco: 2100.00, cambio: 50.00,
    nota: 'Saldo apertura Empresa 2 - Revisiones'
  }));

  // 📁 Reserva de cambio · monedas y billetes
  ls.setItem('caja.reserva.v1', JSON.stringify({
    'billete_50': 4, 'billete_20': 5, 'billete_10': 3, 'moneda_2': 10, 'moneda_1': 15,
    _bulk_seed: 200.00, _bulk: 200.00
  }));
  ls.setItem('caja.cempla.reserva.v1', JSON.stringify({
    'billete_10': 2, 'moneda_1': 10, _bulk_seed: 50.00, _bulk: 50.00
  }));

  // 📁 Ajustes manuales del Cuadre de Caja
  ls.setItem('caja.cuadre.overrides.v1', JSON.stringify({
    '2025-12': { caja_manual: 3250.15, banco_manual: 12408.90 },
    '2026-01': { caja_manual: 3378.42 }
  }));

  // 📁 Configuración empresa
  ls.setItem('caja.config.v1', JSON.stringify({
    company1: { name: 'CENTRO EL PRAT', nif: 'B12345678', address: 'Av Prat 12' },
    company2: { name: 'CEMPLA REVISIONES', nif: 'B87654321' },
    socios: [ { nombre: 'Juan', pct: 50 }, { nombre: 'María', pct: 50 } ],
    precios: { canje: 145.55, inicial: 220.00, renovacion: 145.55, revision_B: 45.00, revision_C: 60.00 }
  }));

  // 📁 Calendario · historial + status + URLs ICS
  ls.setItem('caja.calendar.history.v1', JSON.stringify({
    '2026-03-05_cli1': { uid: 'cli1', date: '2026-03-05', hora: '10:00', nombre: 'Cliente A' },
    '2026-03-06_cli2': { uid: 'cli2', date: '2026-03-06', hora: '11:30', nombre: 'Cliente B' }
  }));
  ls.setItem('caja.calendar.status.v1', JSON.stringify({
    '2026-03-05_cli1': { s: 'ok', src: 'manual' },
    '2026-03-06_cli2': { s: 'done', src: 'auto' }
  }));
  ls.setItem('caja.calendar.urls.v1', JSON.stringify([
    { name: 'Google Cal E1', url: 'https://calendar.google.com/ics/abc.ics' },
    { name: 'iCloud',        url: 'webcal://p01.icloud.com/xyz.ics' }
  ]));

  // 📁 Toggle Contar 0€
  ls.setItem('caja.count_zero', '1');

  // 💰 Feb 2026 · Reglas de tarifas personalizadas configuradas por el usuario
  //   Son datos críticos que también deben viajar en la copia. Simulamos 3
  //   reglas típicas: Canje, Duplicado, y una tarifa fija (Foto carné).
  ls.setItem('caja.tarifas.rules.v1', JSON.stringify([
    { id:'canje-user',    tipos:['Expedicion','Obtencion'], grupos:['Conduccion'], importeExacto:66.50, resultado:'Canje',      notes:'Regla del centro médico' },
    { id:'duplicado-user',tipos:['Duplicado'],              grupos:[],             importeExacto:25.00, resultado:'Duplicat',  notes:'' },
    { id:'foto-user',     tipos:[],                         grupos:[],             importeExacto:4.00,  resultado:'Foto carné', notes:'Precio fijo del centro' },
    { id:'renov-rango',   tipos:['Renovacion'],             grupos:['Conduccion'], importeMin:78, importeMax:95, resultado:'Renovación B', notes:'Rango de precios reales' },
  ]));

  return ls;
}

// ═══════════════════════════════════════════════════════════════════════
// 5️⃣ TEST · Round-Trip · Original → Backup → Fresh → Restore → Compare
// ═══════════════════════════════════════════════════════════════════════
function md5(s){ return crypto.createHash('md5').update(s).digest('hex'); }

function ejecutarTest(){
  console.log('\n════════════════════════════════════════════════════════════════');
  console.log('   🧪 TEST BACKUP ROUND-TRIP · MediCar Plus');
  console.log('════════════════════════════════════════════════════════════════\n');

  // ── PASO 1: Ordenador ORIGINAL con datos reales ─────────────────────
  const lsOriginal = crearOrdenadorOriginal();
  console.log('📥 PASO 1 · Ordenador ORIGINAL creado con:');
  const clavesOriginales = lsOriginal.keysWithPrefix('caja.');
  console.log(`   → ${clavesOriginales.length} claves DATA en localStorage`);

  // Suma total controlada para validar la contabilidad
  let importesOriginales = 0;
  ['caja.v1', 'caja.cempla.v1'].forEach(k => {
    const s = JSON.parse(lsOriginal.getItem(k) || '{"byDate":{}}');
    Object.values(s.byDate || {}).forEach(day => {
      (day.rows || []).forEach(r => { importesOriginales += (r.importe || 0) + (r.tasa || 0); });
    });
  });
  console.log(`   → Total importes+tasas en entradas: ${importesOriginales.toFixed(2)} €`);

  // Hash de referencia de cada clave
  const hashesOriginales = {};
  for(const k of DATA_LS_KEYS){
    const v = lsOriginal.getItem(k);
    hashesOriginales[k] = v ? md5(v) : null;
  }

  // ── PASO 2: Crear la copia (como si se enviara a la nube) ──────────
  const backupBlob = _fullBackupData(lsOriginal);
  const backupJson = JSON.stringify(backupBlob);
  console.log(`\n💾 PASO 2 · Copia creada:`);
  console.log(`   → ${Object.keys(backupBlob).length} claves incluidas`);
  console.log(`   → Tamaño: ${(backupJson.length / 1024).toFixed(2)} KB`);
  console.log(`   → SHA-256 payload: ${crypto.createHash('sha256').update(backupJson).digest('hex').slice(0, 16)}…`);

  // Simular viaje por HTTP (parse → stringify)
  const backupTransmitido = JSON.parse(backupJson);

  // ── PASO 3: Ordenador NUEVO completamente vacío ─────────────────────
  const lsNuevo = new LocalStorageMock();
  console.log(`\n🆕 PASO 3 · Ordenador NUEVO creado VACÍO (${lsNuevo.length} claves)`);

  // ── PASO 4: Aplicar restauración usando `data` del backup ──────────
  // Simula la ruta del cloud recovery: iterar full.data y setItem cada clave
  Object.entries(backupTransmitido).forEach(([k, v]) => {
    const val = v && v.value != null ? v.value : v;
    lsNuevo.setItem(k, typeof val === 'string' ? val : JSON.stringify(val));
  });
  console.log(`\n↩️  PASO 4 · Restauración aplicada`);
  console.log(`   → ${lsNuevo.length} claves escritas en el ordenador nuevo`);

  // ── PASO 5: Comparar TODO byte a byte ───────────────────────────────
  console.log(`\n🔬 PASO 5 · Comparación byte a byte:\n`);
  let pass = 0, fail = 0;
  const detalles = [];
  for(const k of DATA_LS_KEYS){
    const orig = lsOriginal.getItem(k);
    const rest = lsNuevo.getItem(k);
    const origHash = orig ? md5(orig) : null;
    const restHash = rest ? md5(rest) : null;
    const igual = origHash === restHash;
    if(igual){
      pass++;
      const label = orig ? `md5=${origHash.slice(0,8)}` : '(vacío en ambos)';
      detalles.push({ok:true, k, label});
    } else {
      fail++;
      detalles.push({ok:false, k, orig: origHash, rest: restHash});
    }
  }

  detalles.forEach(d => {
    const nombre = d.k.replace('caja.', '').padEnd(35);
    if(d.ok){
      console.log(`   ✅  ${nombre}  ${d.label}`);
    } else {
      console.log(`   ❌  ${nombre}  ORIGINAL=${d.orig}  RESTAURADO=${d.rest}`);
    }
  });

  // Validación semántica cruzada: recalcular contabilidad
  let importesRestaurados = 0;
  ['caja.v1', 'caja.cempla.v1'].forEach(k => {
    const s = JSON.parse(lsNuevo.getItem(k) || '{"byDate":{}}');
    Object.values(s.byDate || {}).forEach(day => {
      (day.rows || []).forEach(r => { importesRestaurados += (r.importe || 0) + (r.tasa || 0); });
    });
  });

  console.log(`\n════════════════════════════════════════════════════════════════`);
  console.log(`   🧾 VALIDACIÓN CONTABLE`);
  console.log(`════════════════════════════════════════════════════════════════`);
  console.log(`   Total importes+tasas ORIGINAL:    ${importesOriginales.toFixed(2)} €`);
  console.log(`   Total importes+tasas RESTAURADO:  ${importesRestaurados.toFixed(2)} €`);
  console.log(`   Diferencia (debe ser 0.00):        ${(importesRestaurados - importesOriginales).toFixed(2)} €`);
  const contabilidadOK = Math.abs(importesRestaurados - importesOriginales) < 0.001;

  // Validación específica: Saldo Inicial de cada empresa
  console.log(`\n════════════════════════════════════════════════════════════════`);
  console.log(`   🏦 SALDO INICIAL POR EMPRESA (crítico para el usuario)`);
  console.log(`════════════════════════════════════════════════════════════════`);
  const si1O = JSON.parse(lsOriginal.getItem('caja.saldoInicial.trafic.v1'));
  const si1R = JSON.parse(lsNuevo.getItem('caja.saldoInicial.trafic.v1'));
  const si2O = JSON.parse(lsOriginal.getItem('caja.saldoInicial.cempla.v1'));
  const si2R = JSON.parse(lsNuevo.getItem('caja.saldoInicial.cempla.v1'));
  console.log(`   E1 · Original:    fecha=${si1O.fecha} efect=${si1O.efectivo}€ banco=${si1O.banco}€ cambio=${si1O.cambio}€`);
  console.log(`   E1 · Restaurado:  fecha=${si1R.fecha} efect=${si1R.efectivo}€ banco=${si1R.banco}€ cambio=${si1R.cambio}€`);
  console.log(`   E2 · Original:    fecha=${si2O.fecha} efect=${si2O.efectivo}€ banco=${si2O.banco}€ cambio=${si2O.cambio}€`);
  console.log(`   E2 · Restaurado:  fecha=${si2R.fecha} efect=${si2R.efectivo}€ banco=${si2R.banco}€ cambio=${si2R.cambio}€`);
  const saldosOK = (si1O.efectivo === si1R.efectivo && si1O.banco === si1R.banco && si1O.cambio === si1R.cambio &&
                    si2O.efectivo === si2R.efectivo && si2O.banco === si2R.banco && si2O.cambio === si2R.cambio &&
                    si1O.fecha === si1R.fecha && si2O.fecha === si2R.fecha);

  // Validación específica: config (nombres empresa, socios, precios)
  const cfgO = JSON.parse(lsOriginal.getItem('caja.config.v1'));
  const cfgR = JSON.parse(lsNuevo.getItem('caja.config.v1'));
  const configOK = JSON.stringify(cfgO) === JSON.stringify(cfgR);

  // Validación específica: stats autoescolas
  const stO = JSON.parse(lsOriginal.getItem('caja.stats.v1'));
  const stR = JSON.parse(lsNuevo.getItem('caja.stats.v1'));
  const statsOK = JSON.stringify(stO) === JSON.stringify(stR);

  // 💰 Validación específica: reglas de tarifas personalizadas
  console.log(`\n════════════════════════════════════════════════════════════════`);
  console.log(`   💰 TARIFAS PERSONALIZADAS (patrones para clasificar apuntes)`);
  console.log(`════════════════════════════════════════════════════════════════`);
  const tarifasO = JSON.parse(lsOriginal.getItem('caja.tarifas.rules.v1') || '[]');
  const tarifasR = JSON.parse(lsNuevo.getItem('caja.tarifas.rules.v1') || '[]');
  console.log(`   Reglas ORIGINALES:    ${tarifasO.length}`);
  console.log(`   Reglas RESTAURADAS:   ${tarifasR.length}`);
  tarifasO.forEach((r, i) => {
    const rr = tarifasR[i] || {};
    const equal = JSON.stringify(r) === JSON.stringify(rr);
    const detail = `tipos=${(r.tipos||[]).length} grupos=${(r.grupos||[]).length} exacto=${r.importeExacto} rango=${r.importeMin||'-'}..${r.importeMax||'-'} → "${r.resultado}"`;
    console.log(`   ${equal ? '✅' : '❌'}  Regla ${i+1}: ${detail}`);
  });
  const tarifasOK = JSON.stringify(tarifasO) === JSON.stringify(tarifasR);

  console.log(`\n════════════════════════════════════════════════════════════════`);
  console.log(`   📊 RESUMEN FINAL`);
  console.log(`════════════════════════════════════════════════════════════════`);
  console.log(`   🔑 Claves comparadas:                  ${pass} OK · ${fail} FAIL`);
  console.log(`   💰 Contabilidad idéntica:              ${contabilidadOK ? '✅ SÍ' : '❌ NO'}`);
  console.log(`   🏦 Saldos Iniciales E1+E2 idénticos:   ${saldosOK ? '✅ SÍ' : '❌ NO'}`);
  console.log(`   ⚙️  Configuración empresa idéntica:     ${configOK ? '✅ SÍ' : '❌ NO'}`);
  console.log(`   📈 Stats Autoescolas idénticas:        ${statsOK ? '✅ SÍ' : '❌ NO'}`);
  console.log(`   💰 Tarifas personalizadas idénticas:   ${tarifasOK ? '✅ SÍ' : '❌ NO'}`);
  console.log('');

  const todoOK = fail === 0 && contabilidadOK && saldosOK && configOK && statsOK && tarifasOK;
  if(todoOK){
    console.log('   🎉 RESULTADO: TODAS LAS VALIDACIONES PASARON');
    console.log('   → La restauración deja el ordenador IDÉNTICO al original, dato a dato.');
    console.log('');
    process.exit(0);
  } else {
    console.log('   ⚠️  RESULTADO: HAY DIFERENCIAS · revisar los ❌ arriba.');
    console.log('');
    process.exit(1);
  }
}

ejecutarTest();
