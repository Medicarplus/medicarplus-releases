// 🧪 TEST v2: Reserva de cambio día-a-día tras sync PC↔PC CON SALDO INICIAL
// Reproduce EXACTAMENTE el caso reportado por el usuario:
//   - El 31/08/2026 configura el Saldo Inicial con cambio=344,74 € (arranque del programa).
//   - A lo largo de Sept/Oct, el usuario modifica DENOMINACIONES físicas con +/−
//     en el modal (SIN crear asientos dated). La reserva actual acaba en 436,74 €.
//   - Hoy (15/10/2026) envía la copia diaria al PC gerente.
//   - En el PC gerente: al visitar 31/08 debe seguir mostrando 344,74 € (saldo inicial).
//   - La fórmula FORWARD (siCambio + Σ traspasos dated hasta la fecha) hace que
//     los días pasados NO se vean afectados por la reserva actual del otro PC.

'use strict';

function assertEqual(actual, expected, label){
  const ok = Math.abs(actual - expected) < 0.005;
  const sign = ok ? '✅' : '❌';
  console.log(`${sign} ${label} · esperado=${expected.toFixed(2)}  real=${actual.toFixed(2)}`);
  if(!ok) process.exitCode = 1;
  return ok;
}

// Reproducimos la fórmula FORWARD (idéntica a v2.html)
function makeResCambio(si, reservaActual, byDate){
  function atEndOfDate(date){
    if(!date) return reservaActual;
    if(!si || !si.fecha){
      let laterNet = 0;
      for(const d in byDate){
        if(d <= date) continue;
        for(const e of (byDate[d]||[])){
          if(e.kind !== 'DH' || !e._internal) continue;
          const amt = +e.importe || 0;
          if(e._transferDir === 'caja_to_reserva') laterNet += amt;
          else if(e._transferDir === 'banco_to_reserva') laterNet += amt;
          else if(e._transferDir === 'reserva_to_caja') laterNet -= amt;
        }
      }
      return reservaActual - laterNet;
    }
    if(date < si.fecha) return 0;
    let net = 0;
    for(const d in byDate){
      if(d < si.fecha) continue;
      if(d > date) continue;
      for(const e of (byDate[d]||[])){
        if(e.kind !== 'DH' || !e._internal) continue;
        const amt = +e.importe || 0;
        if(e._transferDir === 'caja_to_reserva') net += amt;
        else if(e._transferDir === 'banco_to_reserva') net += amt;
        else if(e._transferDir === 'reserva_to_caja') net -= amt;
      }
    }
    return (+si.cambio||0) + net;
  }
  function atStartOfDate(date){
    if(!date) return reservaActual;
    if(!si || !si.fecha){
      let laterNet = 0;
      for(const d in byDate){
        if(d < date) continue;
        for(const e of (byDate[d]||[])){
          if(e.kind !== 'DH' || !e._internal) continue;
          const amt = +e.importe || 0;
          if(e._transferDir === 'caja_to_reserva') laterNet += amt;
          else if(e._transferDir === 'banco_to_reserva') laterNet += amt;
          else if(e._transferDir === 'reserva_to_caja') laterNet -= amt;
        }
      }
      return reservaActual - laterNet;
    }
    if(date <= si.fecha) return (date < si.fecha) ? 0 : (+si.cambio||0);
    let net = 0;
    for(const d in byDate){
      if(d < si.fecha) continue;
      if(d >= date) continue;
      for(const e of (byDate[d]||[])){
        if(e.kind !== 'DH' || !e._internal) continue;
        const amt = +e.importe || 0;
        if(e._transferDir === 'caja_to_reserva') net += amt;
        else if(e._transferDir === 'banco_to_reserva') net += amt;
        else if(e._transferDir === 'reserva_to_caja') net -= amt;
      }
    }
    return (+si.cambio||0) + net;
  }
  return { atEndOfDate, atStartOfDate };
}

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('🧪 TEST: Reserva histórica día-a-día tras sync PC↔PC');
console.log('     con Saldo Inicial configurado el 31/08/2026');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

// ────────────────────────────────────────────────────────────────
// CASO 1: El caso REAL del usuario (bug reportado)
// Saldo Inicial 31/08 = 344,74 €. Reserva física actual (por recuento
// manual con +/-) = 436,74 €. NO hay asientos dated entre 31/08 y hoy.
// ────────────────────────────────────────────────────────────────
console.log('\n📍 CASO REAL REPORTADO:');
console.log('   Saldo Inicial 31/08: 344,74 €');
console.log('   Reserva actual física (modal): 436,74 €');
console.log('   Traspasos dated entre 31/08 y hoy: NINGUNO');

const PC_gerente = {
  si: { fecha: '2026-08-31', cambio: 344.74 },
  reservaActual: 436.74,  // modificado manualmente con +/- en modal (sin dated)
  byDate: {
    // Sin asientos _internal en ningún día
    '2026-09-15': [{ kind:'HABER', importe:50, fp:'E' }],
    '2026-10-15': [{ kind:'HABER', importe:30, fp:'E' }]
  }
};
const r1 = makeResCambio(PC_gerente.si, PC_gerente.reservaActual, PC_gerente.byDate);

assertEqual(r1.atEndOfDate('2026-08-30'), 0,       '  30/08 (antes arranque) → 0 €');
assertEqual(r1.atEndOfDate('2026-08-31'), 344.74,  '  31/08 (fecha arranque) → 344,74 €  ⬅ EL BUG DEL USUARIO SOLUCIONADO');
assertEqual(r1.atEndOfDate('2026-09-15'), 344.74,  '  15/09 (sin traspasos) → 344,74 €');
assertEqual(r1.atEndOfDate('2026-10-15'), 344.74,  '  15/10 (sin traspasos) → 344,74 €');

// ────────────────────────────────────────────────────────────────
// CASO 2: Usuario hace flujos correctos CON asientos dated.
//   01/09: +50 € de banco → reserva (344,74 → 394,74)
//   10/09: +40 € de caja  → reserva (394,74 → 434,74)
//   20/09: -36,5 € reserva → caja  (434,74 → 398,24)
// ────────────────────────────────────────────────────────────────
console.log('\n📍 CASO FLUJO CORRECTO (traspasos dated):');
const PC_correcto = {
  si: { fecha: '2026-08-31', cambio: 344.74 },
  reservaActual: 398.24,
  byDate: {
    '2026-09-01': [
      { kind:'DH', tipo:'DEBE', _internal:true, _transferDir:'banco_to_reserva', importe:50 }
    ],
    '2026-09-10': [
      { kind:'DH', tipo:'DEBE', _internal:true, _transferDir:'caja_to_reserva',  importe:40 }
    ],
    '2026-09-20': [
      { kind:'DH', tipo:'HABER', _internal:true, _transferDir:'reserva_to_caja', importe:36.5 }
    ]
  }
};
const r2 = makeResCambio(PC_correcto.si, PC_correcto.reservaActual, PC_correcto.byDate);
assertEqual(r2.atEndOfDate('2026-08-31'), 344.74,  '  31/08 → 344,74 €');
assertEqual(r2.atEndOfDate('2026-09-01'), 394.74,  '  01/09 (+50) → 394,74 €');
assertEqual(r2.atEndOfDate('2026-09-05'), 394.74,  '  05/09 (intermedio) → 394,74 €');
assertEqual(r2.atEndOfDate('2026-09-10'), 434.74,  '  10/09 (+40) → 434,74 €');
assertEqual(r2.atEndOfDate('2026-09-19'), 434.74,  '  19/09 (intermedio) → 434,74 €');
assertEqual(r2.atEndOfDate('2026-09-20'), 398.24,  '  20/09 (-36,5) → 398,24 €');
assertEqual(r2.atEndOfDate('2026-10-15'), 398.24,  '  15/10 (hoy) → 398,24 €');

// Saldo anterior (atStartOfDate) excluye el propio día:
assertEqual(r2.atStartOfDate('2026-09-01'), 344.74, '  Inicio día 01/09 (saldo ant.) → 344,74 €');
assertEqual(r2.atStartOfDate('2026-09-10'), 394.74, '  Inicio día 10/09 (saldo ant.) → 394,74 €');
assertEqual(r2.atStartOfDate('2026-09-20'), 434.74, '  Inicio día 20/09 (saldo ant.) → 434,74 €');

// ────────────────────────────────────────────────────────────────
// CASO 3: Sync entre dos PCs con la nueva fórmula.
//   Ambos PCs tienen el mismo Saldo Inicial local (344,74 el 31/08).
//   PC_user añade +340 € el 15/10 (asiento dated banco_to_reserva).
//   Envía copia a PC_gerente. PC_gerente ya tenía los días previos.
// ────────────────────────────────────────────────────────────────
console.log('\n📍 CASO SYNC (ambos con mismo Saldo Inicial local):');

const siLocal = { fecha: '2026-08-31', cambio: 344.74 };
const PC_user = {
  si: siLocal,
  reservaActual: 684.74,  // 344,74 + 340
  byDate: {
    '2026-09-01': [{ kind:'DH', tipo:'DEBE', _internal:true, _transferDir:'banco_to_reserva', importe:50 }],
    '2026-10-15': [{ kind:'DH', tipo:'DEBE', _internal:true, _transferDir:'banco_to_reserva', importe:340 }]
  }
};
const rU = makeResCambio(PC_user.si, PC_user.reservaActual, PC_user.byDate);
assertEqual(rU.atEndOfDate('2026-08-31'), 344.74,  '  PC_user 31/08 → 344,74 €');
assertEqual(rU.atEndOfDate('2026-09-01'), 394.74,  '  PC_user 01/09 (+50) → 394,74 €');
assertEqual(rU.atEndOfDate('2026-10-14'), 394.74,  '  PC_user 14/10 → 394,74 €');
assertEqual(rU.atEndOfDate('2026-10-15'), 734.74,  '  PC_user 15/10 (+340) → 734,74 €');

// Tras aplicar la copia diaria, PC_gerente recibe el día 15/10 y la reserva global
const PC_gerente_tras_sync = {
  si: siLocal,
  reservaActual: 684.74, // sobreescrita por _mtime (LWW) con el valor del user
  byDate: {
    '2026-09-01': [{ kind:'DH', tipo:'DEBE', _internal:true, _transferDir:'banco_to_reserva', importe:50 }],
    '2026-10-15': [{ kind:'DH', tipo:'DEBE', _internal:true, _transferDir:'banco_to_reserva', importe:340 }]
  }
};
const rG = makeResCambio(PC_gerente_tras_sync.si, PC_gerente_tras_sync.reservaActual, PC_gerente_tras_sync.byDate);
assertEqual(rG.atEndOfDate('2026-08-31'), 344.74,  '  PC_gerente 31/08 → 344,74 €  ✅ YA NO PASA EL BUG');
assertEqual(rG.atEndOfDate('2026-09-01'), 394.74,  '  PC_gerente 01/09 → 394,74 €');
assertEqual(rG.atEndOfDate('2026-10-14'), 394.74,  '  PC_gerente 14/10 → 394,74 €');
assertEqual(rG.atEndOfDate('2026-10-15'), 734.74,  '  PC_gerente 15/10 → 734,74 €');

// ────────────────────────────────────────────────────────────────
// CASO 4: Legacy (sin Saldo Inicial configurado) → fallback a lógica antigua
// ────────────────────────────────────────────────────────────────
console.log('\n📍 CASO LEGACY (sin Saldo Inicial · fallback):');
const PC_legacy = {
  si: null,
  reservaActual: 436.74,
  byDate: {
    '2026-10-15': [{ kind:'DH', tipo:'DEBE', _internal:true, _transferDir:'banco_to_reserva', importe:340 }]
  }
};
const rL = makeResCambio(PC_legacy.si, PC_legacy.reservaActual, PC_legacy.byDate);
assertEqual(rL.atEndOfDate('2026-10-14'), 96.74,  '  Legacy 14/10 → 96,74 € (fallback hacia atrás)');
assertEqual(rL.atEndOfDate('2026-10-15'), 436.74, '  Legacy 15/10 → 436,74 €');

console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
if(process.exitCode){
  console.log('❌ ALGUNOS TESTS HAN FALLADO');
} else {
  console.log('✅ TODOS LOS TESTS PASAN · fórmula FORWARD robusta');
  console.log('   · 31/08/2026 muestra 344,74 € (NO 436,74 € como en el bug reportado)');
  console.log('   · Sync PC↔PC ya NO contamina días pasados');
}
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
