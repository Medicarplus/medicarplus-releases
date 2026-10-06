// 🧪 FEB 2026 · E2E REAL contra backend productivo
//
// Simula el flujo COMPLETO que pide el usuario:
//   1. ADMIN (MASTER key) genera un snapshot RICO (TRÀFIC + CEMPLA + 7 años de autoescuelas,
//      IRPF, tarifas, chips, blacklist, saldos, reservas, config, calendarios…)
//   2. ADMIN sube ese snapshot al CLOUD con /api/sync/cloudbackup/send (gzip + sha256).
//   3. ADMIN hace PUSH de esa copia histórica al buzón del CLIENTE con
//      /api/sync/admin/cloudbackup/push.
//   4. CLIENTE consulta /api/sync/backup/pending → ve la copia esperando.
//   5. CLIENTE descarga + descomprime la copia, simula applyBackup (_mergeSnapshots)
//      sobre un localStorage VACÍO (restauración limpia) y GUARDA.
//   6. CLIENTE llama a /api/sync/backup/consume para marcar aplicada.
//   7. VERIFICACIÓN BYTE-A-BYTE: cada clave del snapshot original debe aparecer
//      idéntica en el estado restaurado del cliente. También SHA-256 total.
//   8. BONUS: _mergeSnapshots sobre un CLIENTE CON DATOS NUEVOS debe preservar
//      ambos lados (los apuntes del día del cliente + histórico del admin).
//
// Uso: node tests/e2e_envio_cliente_restaura_todo.js
//      (debe correr desde /app)

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');
const zlib = require('zlib');

// === Config ===
const API_BASE = (process.env.REACT_APP_BACKEND_URL
  || fs.readFileSync('/app/frontend/.env','utf8').match(/REACT_APP_BACKEND_URL=(.+)/)[1]).trim();
const MASTER_KEY = 'MB-MASTER-BRUGULAT-2026-OWNER';
const ADMIN_INSTALL = 'TEST-ADMIN-' + Date.now();
// Cliente destino: usamos otra MASTER-style licence sintética a través de un alta real
const CLIENT_LICENSE_KEY = 'MB-E2E-CLIENT-' + Date.now();
const CLIENT_INSTALL = 'TEST-CLIENT-' + Date.now();

console.log('🌐 API:', API_BASE);
console.log('👑 Admin install:', ADMIN_INSTALL);
console.log('👤 Client install:', CLIENT_INSTALL);

// === Carga sandbox de v2.html para _mergeSnapshots y _isSyncable ===
const html = fs.readFileSync(path.join(__dirname, '..', 'v2.html'), 'utf8');
const start = html.indexOf('const SYNC_EXCLUDE_PREFIXES');
const end   = html.indexOf('async function init(opts)', start);
const block = html.slice(start, end);
const sandbox = { console, module: {} };
vm.runInContext(`${block}\nmodule.exports = { _mergeSnapshots, _isSyncable };`,
  vm.createContext(sandbox));
const { _mergeSnapshots, _isSyncable } = sandbox.module.exports;

// === HTTP helpers ===
async function http(method, pathUrl, body, headers) {
  const url = API_BASE + pathUrl;
  const init = { method, headers: Object.assign({'Content-Type':'application/json'}, headers||{}) };
  if (body !== undefined) init.body = JSON.stringify(body);
  const r = await fetch(url, init);
  const text = await r.text();
  let json; try { json = JSON.parse(text); } catch(_) { json = { _raw: text }; }
  if (!r.ok) {
    console.error('❌ HTTP', r.status, method, pathUrl, '→', json);
    throw new Error(`HTTP ${r.status} on ${method} ${pathUrl}: ${JSON.stringify(json)}`);
  }
  return json;
}

// === Snapshot RICO del admin: cubre TODO el abanico de claves ===
function makeRichSnapshot(){
  const trafic = { byDate: {} };
  const cempla = { byDate: {} };
  const datafonoT = {}; const datafonoC = {};
  // 10 días con 3-4 apuntes cada uno en cada empresa
  for (let i = 1; i <= 10; i++){
    const d = `2026-01-${String(i).padStart(2,'0')}`;
    trafic.byDate[d] = [
      { id:`t${i}a`, importe: 45.50 + i, tipo:'HABER', nombre:'MARTINEZ', concepto:'Renovación', fp:'EFECTIVO', tasa:28.80 },
      { id:`t${i}b`, importe: 12.00, tipo:'HABER', nombre:'LOPEZ', concepto:'Duplicado', fp:'TARJETA', tasa:0 },
      { id:`t${i}c`, importe: 180.00, tipo:'HABER', nombre:'ROSANAS', concepto:'Autoescuela', fp:'TRANSFERENCIA', tasa:0 },
    ];
    cempla.byDate[d] = [
      { id:`c${i}a`, importe: 50 + i, tipo:'HABER', nombre:'GARCIA', concepto:'Revisión', fp:'EFECTIVO' },
      { id:`c${i}b`, importe: 25,     tipo:'DEBER', nombre:'Gasto material', concepto:'Material', fp:'EFECTIVO' },
    ];
    datafonoT[d] = 100 + i*5;
    datafonoC[d] = 50 + i*2;
  }
  // caja.stats.v1 · 7 años × 12 meses × 5 autoescuelas
  const autos = ['ROSANAS','CLAPERA','MOLIST','TER','VALLES'];
  const statsData = {};
  for (let y = 2019; y <= 2026; y++){
    for (let m = 1; m <= 12; m++){
      const key = `${y}-${String(m).padStart(2,'0')}`;
      statsData[key] = {};
      autos.forEach((a, idx) => { statsData[key][a] = (y - 2019) * 10 + m + idx; });
    }
  }
  return {
    'caja.v1': trafic,
    'caja.cempla.v1': cempla,
    'caja.datafono': datafonoT,
    'caja.cempla.datafono': datafonoC,
    'caja.stats.v1': { autoescoles: autos.slice(), data: statsData },
    'caja.stats.aliases.v1': { 'ROSELL':'ROSANAS', 'MOLI':'MOLIST' },
    'caja.stats.traffic.overrides.v1': { '2024-05': { TER: 7 } },
    'caja.irpf.v1': {
      months: {
        '2025-01':{base:1200, retencion:15},
        '2025-02':{base:1100, retencion:15},
        '2025-12':{base:1300, retencion:15},
      },
      quarters: {
        '2025-Q1':{paid:true, date:'2025-04-15'},
        '2025-Q2':{paid:true, date:'2025-07-15'},
        '2025-Q4':{paid:false},
      }
    },
    'caja.saldoInicial.trafic.v1': { fecha:'2026-01-01', saldo: 1500.75 },
    'caja.saldoInicial.cempla.v1': { fecha:'2026-01-01', saldo: 420.00 },
    'caja.reserva.v1': 300.00,
    'caja.cempla.reserva.v1': 150.00,
    'caja.cuadre.overrides.v1': { '2026-01-05': { adjust: -2.50, note:'propina' } },
    'caja.config.v1': {
      empresa:'MediCar Plus TRÀFIC',
      empresa2:'CEMPLA Revisions',
      iva:21,
      socios:[{nombre:'Marc', pct:50},{nombre:'Victoria', pct:50}],
      e2TabTitle: 'Revisions esportives',
    },
    'caja.calendar.history.v1': [
      {id:'ev1', fecha:'2026-02-01 10:00', nombre:'LLOPIS', tel:'600112233', asistio:true},
      {id:'ev2', fecha:'2026-02-01 11:00', nombre:'MARTI',  tel:'600445566', asistio:false},
    ],
    'caja.calendar.status.v1': { 'ev1':'ok', 'ev2':'no_show' },
    'caja.calendar.urls.v1': [
      {url:'https://calendar.google.com/webcal/privado1.ics', label:'Agenda Marc'},
      {url:'https://calendar.google.com/webcal/privado2.ics', label:'Agenda Vicky'},
    ],
    'caja.count_zero': true,
    'caja.tarifas.rules.v1': [
      {id:'r1', nombre:'Canje', patron:'canje', importe:28.80},
      {id:'r2', nombre:'Duplicado', patron:'duplicado', importe:22.70},
      {id:'r3', nombre:'Renovación', patron:'reno', importe:45.50},
    ],
    'caja.cambio.history.v1': [
      {ts: 1706000000000, delta: +50, nota:'ajuste'},
      {ts: 1706100000000, delta: -20, nota:'retirado'},
    ],
    'caja.notif.template.v1': 'Hola {nombre}, cita el {fecha} a las {hora}.',
    'caja.notif.settings.v1': {activo:true, hora:'09:00'},
    'caja.chips.custom.v1': [
      {id:'ch1', label:'Material clínico', tipo:'gasto', importe:15.0, empresa:2},
      {id:'ch2', label:'Dieta', tipo:'gasto', importe:12.5, empresa:1},
    ],
    'caja.fuzzy.blacklist.v1': [
      {a:'TER', b:'TERÇOL'},
      {a:'MOLIST', b:'MOLINA'},
    ],
  };
}

function sha256Of(obj){
  return crypto.createHash('sha256').update(JSON.stringify(obj, Object.keys(obj).sort())).digest('hex');
}
function deepEqual(a, b){ return JSON.stringify(a) === JSON.stringify(b); }
function stableStringify(obj){
  const sort = (o)=> {
    if (o === null || typeof o !== 'object' || Array.isArray(o)) return o;
    const out = {}; for (const k of Object.keys(o).sort()) out[k] = sort(o[k]);
    return out;
  };
  return JSON.stringify(sort(obj));
}

async function createClientLicense(){
  // Insertamos licencia PRM directamente en Mongo via endpoint admin (si no existe,
  // creamos uno sintético usando la API de licencias). Para no depender de otros
  // endpoints, insertamos vía ejecución directa de mongosh.
  const { execSync } = require('child_process');
  const insertCmd = `db.licenses.insertOne({
    license_key: '${CLIENT_LICENSE_KEY}',
    license_key_hash: '${crypto.createHash('sha256').update(CLIENT_LICENSE_KEY).digest('hex')}',
    install_id: '${CLIENT_INSTALL}',
    status: 'active',
    plan: 'PRM',
    plan_family: 'PRM',
    client_email: 'cliente-e2e@test.local',
    client_name: 'Cliente E2E · ${CLIENT_INSTALL.slice(-6)}',
    created_at: new Date(),
  })`;
  execSync(`mongosh test_database --quiet --eval "${insertCmd.replace(/"/g,'\\"')}"`);
  console.log('✅ Licencia cliente creada en Mongo:', CLIENT_LICENSE_KEY.slice(0,20)+'…');
}

async function cleanupClientLicense(){
  const { execSync } = require('child_process');
  try{
    execSync(`mongosh test_database --quiet --eval "db.licenses.deleteOne({license_key:'${CLIENT_LICENSE_KEY}'})"`);
    const lkh = crypto.createHash('sha256').update(CLIENT_LICENSE_KEY).digest('hex');
    execSync(`mongosh test_database --quiet --eval "db.sync_cloud_backups.deleteMany({license_key_hash:'${lkh}'})"`);
    execSync(`mongosh test_database --quiet --eval "db.sync_backups.deleteMany({license_key_hash:'${lkh}'})"`);
    execSync(`mongosh test_database --quiet --eval "db.sync_devices.deleteMany({license_key_hash:'${lkh}'})"`);
    const adminLkh = crypto.createHash('sha256').update(MASTER_KEY).digest('hex');
    execSync(`mongosh test_database --quiet --eval "db.sync_cloud_backups.deleteMany({license_key_hash:'${adminLkh}', install_id:'${ADMIN_INSTALL}'})"`);
    execSync(`mongosh test_database --quiet --eval "db.sync_devices.deleteMany({license_key_hash:'${adminLkh}', install_id:'${ADMIN_INSTALL}'})"`);
    console.log('🧹 Datos de test limpiados');
  }catch(e){ console.warn('cleanup warn:', e.message); }
}

// === MAIN ===
let okCount = 0, failCount = 0;
function assert(cond, label, extra){
  if (cond){ okCount++; console.log('  ✅', label); }
  else      { failCount++; console.error('  ❌', label, extra||''); }
}

(async () => {
  console.log('\n' + '='.repeat(72));
  console.log('🚀 TEST E2E · ADMIN envía → CLIENTE restaura → verifica byte a byte');
  console.log('='.repeat(72));

  await createClientLicense();

  try {
    // -- 1) ADMIN crea snapshot rico y sube al cloud --
    console.log('\n📸 Paso 1 · Admin genera snapshot rico (TRÀFIC + CEMPLA + 7 años)');
    const original = makeRichSnapshot();
    const originalSha = sha256Of(original);
    console.log(`   • ${Object.keys(original).length} claves · sha256=${originalSha.slice(0,16)}…`);
    console.log(`   • TRÀFIC: ${Object.keys(original['caja.v1'].byDate).length} días`);
    console.log(`   • CEMPLA: ${Object.keys(original['caja.cempla.v1'].byDate).length} días`);
    console.log(`   • Autoescuelas: ${original['caja.stats.v1'].autoescoles.length} × ${Object.keys(original['caja.stats.v1'].data).length} meses`);

    console.log('\n☁️  Paso 2 · Admin sube snapshot (gzip + sha256) a /sync/cloudbackup/send');
    // Compresión gzip (igual que hace CompressionStream en el cliente)
    const gz = zlib.gzipSync(Buffer.from(JSON.stringify(original)), { level: 6 });
    const gzB64 = gz.toString('base64');
    const sendRes = await http('POST', '/api/sync/cloudbackup/send', {
      license_key: MASTER_KEY,
      install_id: ADMIN_INSTALL,
      label: 'E2E rich admin snapshot',
      data: {},
      data_gz_b64: gzB64,
    });
    assert(sendRes.ok === true, 'upload cloud backup ok');
    assert(!!sendRes.backup_id, 'backup_id devuelto');
    assert(sendRes.compression_ratio >= 1, 'compression_ratio registrado · ratio='+sendRes.compression_ratio);
    assert(!!sendRes.payload_sha256, 'payload_sha256 devuelto por backend');
    const adminBackupId = sendRes.backup_id;
    console.log(`   • raw=${sendRes.size_bytes}B stored=${sendRes.size_bytes_stored}B ratio=${sendRes.compression_ratio}x`);

    // -- 2) Admin descarga la copia y la verifica contra el original --
    console.log('\n🔎 Paso 3 · Admin descarga su propia copia y verifica round-trip gzip');
    const getRes = await http('GET',
      `/api/sync/cloudbackup/get?license_key=${encodeURIComponent(MASTER_KEY)}&install_id=${encodeURIComponent(ADMIN_INSTALL)}&backup_id=${encodeURIComponent(adminBackupId)}`);
    const roundtripSha = sha256Of(getRes.data);
    assert(roundtripSha === originalSha, 'round-trip SHA-256 idéntico (gzip → store → descomprimir)', `orig=${originalSha.slice(0,10)} rt=${roundtripSha.slice(0,10)}`);

    // -- 3) ADMIN hace PUSH al cliente --
    console.log('\n📨 Paso 4 · Admin envía la copia al cliente vía /sync/admin/cloudbackup/push');
    const pushRes = await http('POST',
      `/api/sync/admin/cloudbackup/push?admin_license_key=${encodeURIComponent(MASTER_KEY)}`,
      {
        target_license_key: CLIENT_LICENSE_KEY,
        target_install_id: ADMIN_INSTALL,  // el install_id en sync_cloud_backups es del ADMIN
        backup_id: adminBackupId,
        label: 'Copia de rescate E2E',
      });
    assert(pushRes.ok === true, 'push al buzón del cliente ok');
    assert(!!pushRes.backup_id, 'nuevo backup_id en buzón del cliente');
    const mailboxBackupId = pushRes.backup_id;

    // -- 4) CLIENTE ve pending --
    console.log('\n📥 Paso 5 · Cliente consulta /sync/backup/pending');
    const pending = await http('GET',
      `/api/sync/backup/pending?license_key=${encodeURIComponent(CLIENT_LICENSE_KEY)}&install_id=${encodeURIComponent(CLIENT_INSTALL)}`);
    assert(pending.count >= 1, `pending.count = ${pending.count} (≥1)`);
    const found = (pending.pending || []).find(p => p.backup_id === mailboxBackupId);
    assert(!!found, 'copia enviada aparece en pending del cliente');
    assert(found.from_install_id && found.from_install_id.startsWith('admin:'),
      `remitente marcado como admin · from=${found && found.from_install_id}`);
    assert(found.data && Object.keys(found.data).length === Object.keys(original).length,
      `data integrada · keys=${found && Object.keys(found.data||{}).length} vs original=${Object.keys(original).length}`);

    // -- 5) CLIENTE restaura en PC vacío (merge({}, incoming)) --
    console.log('\n♻️  Paso 6 · Cliente aplica la copia sobre localStorage VACÍO (restauración de RESCATE del admin)');
    // 🔑 Simula applyBackup({...}, {fullRestore:true}) tal como el banner del cliente lo hará
    //    cuando detecta from_admin:true. Rescate completo: NO filtra claves locales.
    assert(found.from_admin === true, 'backend marca from_admin=true en pending');
    const incoming = {};
    for (const k of Object.keys(found.data)){
      if (!k || typeof k !== 'string') continue;
      if (k.startsWith('__')) continue;
      if (k.startsWith('caja.install.') || k.startsWith('caja.license.') ||
          k.startsWith('caja.apibase.') || k.startsWith('caja.plan.preview.') ||
          k.startsWith('caja.sync.') || k.startsWith('caja.__sync')) continue;
      incoming[k] = found.data[k];  // fullRestore: deja pasar irpf, saldoInicial, cuadre
    }
    const emptyLocal = {};
    const restored = _mergeSnapshots(emptyLocal, incoming);

    // Comparar byte a byte cada clave con el original (modo rescate: TODO cuadra)
    const expectedRestore = {};
    for (const k of Object.keys(original)){
      if (!k || typeof k !== 'string') continue;
      if (k.startsWith('__')) continue;
      if (k.startsWith('caja.install.') || k.startsWith('caja.license.') ||
          k.startsWith('caja.apibase.') || k.startsWith('caja.plan.preview.') ||
          k.startsWith('caja.sync.') || k.startsWith('caja.__sync')) continue;
      expectedRestore[k] = original[k];
    }

    // Clave crítica: cuentas de días, apuntes y stats cell-by-cell
    const restoredSha = sha256Of(restored);
    const expectedSha = sha256Of(expectedRestore);
    assert(restoredSha === expectedSha,
      'SHA-256 del snapshot restaurado = SHA-256 del original (rescate completo del admin)',
      `restored=${restoredSha.slice(0,10)} expected=${expectedSha.slice(0,10)}`);

    // Cuadre al céntimo
    const sumBy = (byDate)=> {
      let s = 0;
      for (const d of Object.keys(byDate||{})){
        for (const r of (byDate[d]||[])) s += Number(r.importe||0);
      }
      return Math.round(s*100)/100;
    };
    const sumOrigT = sumBy(original['caja.v1'].byDate);
    const sumRestT = sumBy(restored['caja.v1'].byDate);
    assert(sumOrigT === sumRestT, `cuadre TRÀFIC · orig=${sumOrigT}€ · restaurado=${sumRestT}€`);
    const sumOrigC = sumBy(original['caja.cempla.v1'].byDate);
    const sumRestC = sumBy(restored['caja.cempla.v1'].byDate);
    assert(sumOrigC === sumRestC, `cuadre CEMPLA · orig=${sumOrigC}€ · restaurado=${sumRestC}€`);

    // Autoescuelas celda a celda
    let cellsOK = 0, cellsFail = 0;
    const srcStats = original['caja.stats.v1'];
    const dstStats = restored['caja.stats.v1'] || {autoescoles:[], data:{}};
    for (const mes of Object.keys(srcStats.data||{})){
      for (const a of Object.keys(srcStats.data[mes])){
        const v1 = srcStats.data[mes][a];
        const v2 = (dstStats.data[mes]||{})[a];
        if (v1 === v2) cellsOK++; else cellsFail++;
      }
    }
    assert(cellsFail === 0, `celdas autoescuelas idénticas · OK=${cellsOK} FAIL=${cellsFail}`);

    // Config, IRPF, tarifas, chips, blacklist, calendar — comparación exacta
    const criticalKeys = [
      'caja.config.v1','caja.irpf.v1','caja.tarifas.rules.v1',
      'caja.chips.custom.v1','caja.fuzzy.blacklist.v1',
      'caja.calendar.history.v1','caja.calendar.urls.v1',
      'caja.saldoInicial.trafic.v1','caja.saldoInicial.cempla.v1',
      'caja.reserva.v1','caja.cempla.reserva.v1',
      'caja.cuadre.overrides.v1','caja.stats.aliases.v1',
      'caja.notif.template.v1','caja.notif.settings.v1',
      'caja.datafono','caja.cempla.datafono','caja.count_zero',
      'caja.cambio.history.v1',
    ];
    for (const k of criticalKeys){
      // 🔑 Modo rescate del admin: TODAS las claves se restauran (incluidas las "locales"
      //    irpf, saldoInicial, cuadre.overrides). Solo install/license/apibase/sync NO.
      const eq = deepEqual(original[k], restored[k]);
      assert(eq, `clave "${k}" idéntica tras restaurar`,
        eq ? '' : `orig=${stableStringify(original[k]).slice(0,80)} rest=${stableStringify(restored[k]||null).slice(0,80)}`);
    }

    // -- 6) CLIENTE marca consumida --
    console.log('\n✅ Paso 7 · Cliente llama /sync/backup/consume');
    const consRes = await http('POST','/api/sync/backup/consume',{
      license_key: CLIENT_LICENSE_KEY, install_id: CLIENT_INSTALL, backup_id: mailboxBackupId,
    });
    assert(consRes.ok === true, 'consume ok');

    const pendingAfter = await http('GET',
      `/api/sync/backup/pending?license_key=${encodeURIComponent(CLIENT_LICENSE_KEY)}&install_id=${encodeURIComponent(CLIENT_INSTALL)}`);
    const stillThere = (pendingAfter.pending||[]).some(p => p.backup_id === mailboxBackupId);
    assert(!stillThere, 'copia ya no aparece en pending tras consume');

    // -- 7) BONUS: merge con cliente que YA TIENE datos nuevos --
    console.log('\n🧬 Paso 8 · BONUS · merge con datos propios del cliente del mismo día');
    const clientLocalBefore = {
      'caja.v1': { byDate: { '2026-02-15': [{id:'x1', importe:99.99, tipo:'HABER', nombre:'MI CLIENTE NUEVO'}] } },
      'caja.config.v1': { empresa:'MediCar Plus TRÀFIC', ultimo_cambio:'2026-02-15' },
    };
    const mergedWithLocal = _mergeSnapshots(clientLocalBefore, incoming);
    // El día nuevo del cliente debe persistir
    assert(!!(mergedWithLocal['caja.v1'].byDate['2026-02-15']), 'día del cliente (2026-02-15) preservado');
    // Los días del admin también
    for (const d of Object.keys(original['caja.v1'].byDate)){
      assert(!!(mergedWithLocal['caja.v1'].byDate[d]), `día admin ${d} preservado`);
    }
    const sumMergedT = sumBy(mergedWithLocal['caja.v1'].byDate);
    const expectedMerged = Math.round((sumOrigT + 99.99)*100)/100;
    assert(sumMergedT === expectedMerged, `cuadre merge · esperado=${expectedMerged}€ · obtenido=${sumMergedT}€`);

    // -- 8) Resumen --
    console.log('\n' + '='.repeat(72));
    console.log(`📊 RESULTADO · ${okCount} OK · ${failCount} FAIL`);
    console.log('='.repeat(72));

  } finally {
    await cleanupClientLicense();
  }

  if (failCount > 0){
    console.error('\n❌ HAY FALLOS. Revisa arriba.');
    process.exit(1);
  }
  console.log('\n🎉 ÉXITO · El cliente recibe la copia del admin y restaura ABSOLUTAMENTE TODO byte a byte.');
  console.log('   TRÀFIC + CEMPLA + 7 años de autoescuelas + IRPF + tarifas + chips + blacklist + calendarios + saldos.');
  process.exit(0);
})().catch(e => {
  console.error('\n💥 Error fatal:', e);
  cleanupClientLicense().finally(() => process.exit(2));
});
