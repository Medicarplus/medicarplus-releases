#!/usr/bin/env node
/**
 * 🎯 TEST INTEGRAL · "Todo lo que haya en la app debe estar en la copia"
 *
 * Reproduce el escenario del usuario: PC con datos en MUCHAS claves diferentes
 * (whitelist + claves NUEVAS + estadísticas SMS + citas + tarifas + histórico),
 * hace copia, restaura en PC vacío, y verifica que TODO aparece.
 */

class LS {
  constructor(){ this._m = new Map(); }
  getItem(k){ return this._m.has(k) ? this._m.get(k) : null; }
  setItem(k, v){ this._m.set(k, String(v)); }
  removeItem(k){ this._m.delete(k); }
  get length(){ return this._m.size; }
  key(i){ return Array.from(this._m.keys())[i]; }
  clear(){ this._m.clear(); }
}

const DATA_LS_KEYS = [
  'caja.v1','caja.cempla.v1','caja.datafono','caja.cempla.datafono',
  'caja.stats.v1','caja.stats.aliases.v1','caja.stats.traffic.overrides.v1',
  'caja.irpf.v1','caja.saldoInicial.trafic.v1','caja.saldoInicial.cempla.v1',
  'caja.reserva.v1','caja.cempla.reserva.v1','caja.cuadre.overrides.v1',
  'caja.config.v1','caja.calendar.history.v1','caja.calendar.status.v1',
  'caja.calendar.urls.v1','caja.count_zero','caja.tarifas.rules.v1',
  'caja.cambio.history.v1','caja.notif.template.v1','caja.notif.settings.v1',
  'caja.twilio.mode.v1','caja.twilio.medicar.sender.v1',
  'caja.stats.seed.2026.jan-may','caja.stats.pollution.cleaned.v1','caja.stats.backfill.loaded.v1',
];
const BACKUP_EXCLUDE_KEYS = [
  'caja.install.id.v1','caja.install.v1',
  'caja.license.v1','caja.license.v3','caja.license.lastcheck.v1',
  'caja.geminiKey','caja.twilio.creds.v1',
  'caja.apibase.v1','caja.apibase.ts.v1','caja.apibase.appver.v1','caja.apibase.override.v1',
  'caja.cloud.recovery.skipped','caja.cloudbackup.last.v1','caja.cloudbackup.pending.v1',
  'caja.snapshots','caja.ai.history.v1',
  'caja.master.ever.v1','caja.plan.preview.v1','caja.sync.modeChosen.v1','caja.aiOnboardSeen',
  'caja.lang','caja.company','caja.referral.received.v1','caja.billing.email.v1',
  'caja.last_seen_version','caja.calendar.cache.v1','caja.calendar.seen_uids.v1','caja.calendar.unread.v1',
];

// ── Simulación del PC ORIGEN con TODO tipo de datos, incluyendo claves NUEVAS ──
const pcOrigen = new LS();

// A) Datos "clásicos"
pcOrigen.setItem('caja.v1', JSON.stringify({byDate:{
  '2026-09-01':{rows:[{id:'a',importe:66.5,tipo:'Expedicion',grupo:'Conduccion'}]},
  '2026-09-15':{rows:[{id:'b',importe:145.55,tipo:'Renovacion',grupo:'Conduccion'}]},
}}));
pcOrigen.setItem('caja.cempla.v1', JSON.stringify({byDate:{'2026-06-30':{rows:[]}, '2026-07-01':{rows:[{id:'c',importe:60}]}}}));
pcOrigen.setItem('caja.datafono', JSON.stringify({'2026-09-01':1977.55,'2026-09-02':1946.23}));
pcOrigen.setItem('caja.stats.v1', JSON.stringify({
  autoescoles:['TRÀFIC','PARTICULAR','CANJE','HOY-VOY','ROSSELL','CONNECT'],
  data:{
    '2024-01':{'TRÀFIC':45,'PARTICULAR':30,'ROSSELL':12},
    '2024-02':{'TRÀFIC':50,'PARTICULAR':32,'ROSSELL':15},
    '2025-06':{'TRÀFIC':60,'HOY-VOY':25,'CONNECT':8},
    '2026-01':{'TRÀFIC':70,'CANJE':20,'ROSSELL':18},
  }
}));
pcOrigen.setItem('caja.stats.aliases.v1', JSON.stringify({'TRÀFIC':'TRÀFIC','MABEL':'MABEL'}));
pcOrigen.setItem('caja.irpf.v1', JSON.stringify({trafic:{months:{'2026-09':{totalCertificats:394,entries:[]}}}}));
pcOrigen.setItem('caja.saldoInicial.trafic.v1', JSON.stringify({fecha:'2026-09-01',efectivo:6911.07,banco:32021.44,cambio:294.74}));
pcOrigen.setItem('caja.saldoInicial.cempla.v1', JSON.stringify({fecha:'2026-09-01',efectivo:594.11,banco:6714.41,cambio:0}));
pcOrigen.setItem('caja.reserva.v1', JSON.stringify({e1:0,e2:2,c50:0,c20:0,_bulk:96.74}));
pcOrigen.setItem('caja.config.v1', JSON.stringify({company1:{name:'CEMPLA C.B'},company2:{name:'CEMPLA S.L.'}}));

// B) Nuevas claves (que antes NO estaban en whitelist)
pcOrigen.setItem('caja.cambio.history.v1', JSON.stringify([{ts:1791000000000,delta:50,note:'test'}]));
pcOrigen.setItem('caja.notif.template.v1', 'Hola {nombre}, recordatori cita {data}');
pcOrigen.setItem('caja.notif.settings.v1', JSON.stringify({activo:true,hora:'09:00'}));
pcOrigen.setItem('caja.twilio.mode.v1', 'medicar');
pcOrigen.setItem('caja.twilio.medicar.sender.v1', 'MediCar');
pcOrigen.setItem('caja.stats.backfill.loaded.v1', '1730000000000');

// C) Citas
pcOrigen.setItem('caja.calendar.history.v1', JSON.stringify({'evt1':{summary:'Consulta X','date':'2026-01-15'}}));
pcOrigen.setItem('caja.calendar.status.v1', JSON.stringify({'2026-01-15_evt1':{s:'ok',src:'manual'}}));
pcOrigen.setItem('caja.calendar.urls.v1', JSON.stringify([{name:'Google',url:'https://cal.g/xyz.ics'}]));

// D) Tarifas
pcOrigen.setItem('caja.tarifas.rules.v1', JSON.stringify([{id:'canje',tipos:['Expedicion'],grupos:['Conduccion'],importeExacto:66.5,resultado:'Canje'}]));

// E) Clave "desconocida" que ni siquiera está en whitelist (pero es `caja.*` y no excluida)
pcOrigen.setItem('caja.mi.futuro.dato.v1', JSON.stringify({miDatoFuturo:'este dato ni siquiera está en la whitelist pero se debe copiar'}));

// F) Claves EXCLUIDAS que NO deben viajar
pcOrigen.setItem('caja.install.id.v1', 'PC-ORIGEN-XYZ');
pcOrigen.setItem('caja.license.v1', JSON.stringify({key:'MB-MASTER-XXX'}));
pcOrigen.setItem('caja.geminiKey', 'api-key-secreta');
pcOrigen.setItem('caja.snapshots', JSON.stringify([{ts:1,data:'basura'}]));

console.log(`✅ PC ORIGEN sembrado con ${pcOrigen.length} claves (${DATA_LS_KEYS.filter(k=>pcOrigen.getItem(k)).length} whitelist + 1 desconocida + 4 excluidas)`);

// ── Simular _readAllDataKeys con auto-descubrimiento ──
function readAll(ls){
  const out = {};
  for(const k of DATA_LS_KEYS){
    const v = ls.getItem(k);
    if(v !== null && v !== '') out[k] = v;
  }
  for(let i = 0; i < ls.length; i++){
    const k = ls.key(i);
    if(!k || !k.startsWith('caja.')) continue;
    if(k in out) continue;
    if(BACKUP_EXCLUDE_KEYS.includes(k)) continue;
    const v = ls.getItem(k);
    if(v !== null && v !== '') out[k] = v;
  }
  return out;
}

const copia = readAll(pcOrigen);
console.log(`\n📦 COPIA generada con ${Object.keys(copia).length} claves`);
Object.keys(copia).sort().forEach(k => {
  const sz = (copia[k]||'').length;
  console.log(`   · ${k}: ${sz} bytes`);
});

// ── Verificaciones ──
let OK = 0, FAIL = 0;
const check = (cond, label) => { if(cond){OK++;console.log(`  ✅ ${label}`);}else{FAIL++;console.log(`  ❌ ${label}`);} };

console.log(`\n🔍 VERIFICACIONES:`);
check('caja.stats.v1' in copia, 'Autoescolas incluidas');
check('caja.v1' in copia && JSON.parse(copia['caja.v1']).byDate['2026-09-01'], 'Tráfico Sept 2026 incluido');
check('caja.cempla.v1' in copia, 'CEMPLA incluido');
check('caja.datafono' in copia, 'Datáfono incluido');
check('caja.irpf.v1' in copia, 'IRPF incluido');
check('caja.saldoInicial.trafic.v1' in copia && JSON.parse(copia['caja.saldoInicial.trafic.v1']).efectivo === 6911.07, 'Saldo Inicial E1 con importe correcto');
check('caja.saldoInicial.cempla.v1' in copia, 'Saldo Inicial E2 incluido');
check('caja.reserva.v1' in copia, 'Reserva E1 incluida');
check('caja.config.v1' in copia, 'Config incluida');
check('caja.calendar.history.v1' in copia, 'Citas historial incluidas');
check('caja.calendar.status.v1' in copia, 'Citas estados incluidos');
check('caja.tarifas.rules.v1' in copia, 'Tarifas incluidas');
check('caja.cambio.history.v1' in copia, 'Historial cambio incluido (NUEVA whitelist)');
check('caja.notif.template.v1' in copia, 'Plantilla SMS incluida (NUEVA whitelist)');
check('caja.notif.settings.v1' in copia, 'Config SMS incluida (NUEVA whitelist)');
check('caja.twilio.mode.v1' in copia, 'Modo Twilio incluido (NUEVA whitelist)');
check('caja.twilio.medicar.sender.v1' in copia, 'Sender medicar incluido (NUEVA whitelist)');
check('caja.mi.futuro.dato.v1' in copia, '🎯 CLAVE DESCONOCIDA auto-descubierta (protege contra futuros bugs)');
check(!('caja.install.id.v1' in copia), 'install.id EXCLUIDO correctamente (específico de PC)');
check(!('caja.license.v1' in copia), 'license EXCLUIDA correctamente (específica de PC)');
check(!('caja.geminiKey' in copia), 'geminiKey EXCLUIDA correctamente (credencial sensible)');
check(!('caja.snapshots' in copia), 'snapshots EXCLUIDOS correctamente (efímeros)');

// ── Ahora RESTAURAR en PC DESTINO ──
const pcDestino = new LS();
// El PC destino tenía algo test previo
pcDestino.setItem('caja.stats.v1', JSON.stringify({autoescoles:['TEST'],data:{'2026-01':{'TEST':1}}}));

function smartMerge(k, existingRaw, incoming, replace){
  if(replace) return incoming;
  if(!existingRaw) return incoming;
  if(incoming === null || incoming === undefined || incoming === '') return null;
  try{
    const cur = typeof existingRaw === 'string' ? JSON.parse(existingRaw) : existingRaw;
    const inc = typeof incoming === 'string' ? JSON.parse(incoming) : incoming;
    if(k === 'caja.stats.v1'){
      const out = {
        autoescoles: Array.from(new Set([...(cur.autoescoles||[]), ...(inc.autoescoles||[])])),
        data: Object.assign({}, cur.data||{}),
      };
      for(const [m, o] of Object.entries(inc.data||{})){ out.data[m] = Object.assign({}, out.data[m]||{}, o); }
      return Object.assign({}, cur, inc, out);
    }
    if(cur && typeof cur === 'object' && !Array.isArray(cur) && inc && typeof inc === 'object' && !Array.isArray(inc)){
      return Object.assign({}, cur, inc);
    }
    return inc;
  }catch(e){ return incoming; }
}

let applied = 0;
const replace = true; // el usuario eligió Reemplazar
for(const k of Object.keys(copia)){
  const excluded = BACKUP_EXCLUDE_KEYS.includes(k);
  const accepted = DATA_LS_KEYS.includes(k) || (k.startsWith('caja.') && !excluded);
  if(!accepted) continue;
  const v = copia[k];
  if(v === null || v === undefined || v === '') continue;
  const existing = pcDestino.getItem(k);
  const merged = smartMerge(k, existing, v, replace);
  if(merged === null || merged === undefined) continue;
  pcDestino.setItem(k, typeof merged === 'string' ? merged : JSON.stringify(merged));
  applied++;
}

console.log(`\n📥 RESTAURACIÓN completada · ${applied} claves aplicadas`);

// Verificar destino
console.log(`\n🎯 VERIFICACIONES POST-RESTAURACIÓN:`);
check(applied === Object.keys(copia).length, `${applied}/${Object.keys(copia).length} claves aplicadas`);
const st = JSON.parse(pcDestino.getItem('caja.stats.v1'));
check(st.autoescoles.length === 6, `autoescolas restauradas (${st.autoescoles.length})`);
check(Object.keys(st.data).length === 4, `meses de datos restaurados (${Object.keys(st.data).length})`);
check(!st.autoescoles.includes('TEST'), 'REEMPLAZAR quitó los datos test');
const v1 = JSON.parse(pcDestino.getItem('caja.v1'));
check(Object.keys(v1.byDate).length === 2, `Tráfico: 2 días restaurados`);
check(pcDestino.getItem('caja.mi.futuro.dato.v1') !== null, 'Clave desconocida auto-restaurada (sin necesidad de whitelist)');
check(pcDestino.getItem('caja.install.id.v1') === null, 'install.id NO se sobrescribió (respeta el nuevo PC)');

console.log(`\n════════════════════════════════════════════════════`);
console.log(`  📊 RESULTADO: ${OK} OK · ${FAIL} FAIL`);
console.log(`════════════════════════════════════════════════════`);
if(FAIL === 0){
  console.log(`  🎉 SISTEMA DE COPIA A PRUEBA DE BALAS`);
  console.log(`  → Todo lo que hay se guarda. Todo lo que se guarda se restaura.`);
  process.exit(0);
} else {
  process.exit(1);
}
