// -----------------------------------------------------------------------------
// Test · Personalización de chips rápidos (⚙️)
// Oct 2026 · Verifica aplicación idempotente + round-trip + no-borra-sistema
// Simula el bloque `applyChipCustomizations` y `openConfigModal` con JSDOM-like.
// -----------------------------------------------------------------------------
'use strict';

const assert = require('assert');

// Mini-DOM (sin dependencias) suficiente para probar la lógica de inserción.
class El {
  constructor(tag){
    this.tag = tag;
    this.children = [];
    this.parent = null;
    this.classList = { 
      _s: new Set(),
      add: (c) => this.classList._s.add(c),
      remove: (c) => this.classList._s.delete(c),
      contains: (c) => this.classList._s.has(c),
    };
    this.dataset = {};
    this.style = {};
    this._attrs = {};
    this.textContent = '';
    this._cls = '';
    this.onclick = null;
    this.__wired = false;
  }
  set className(v){ this._cls = v; }
  get className(){ return this._cls; }
  setAttribute(k,v){ this._attrs[k] = String(v); }
  getAttribute(k){ return this._attrs[k]; }
  appendChild(c){ c.parent = this; this.children.push(c); return c; }
  insertBefore(c, ref){
    c.parent = this;
    const i = this.children.indexOf(ref);
    if(i<0) this.children.push(c);
    else this.children.splice(i,0,c);
    return c;
  }
  remove(){
    if(!this.parent) return;
    const i = this.parent.children.indexOf(this);
    if(i>=0) this.parent.children.splice(i,1);
    this.parent = null;
  }
  _match(sel){
    // sel: ".chip", ".chip:not([data-custom]):not(.chip-config-btn)", ".chip-config-btn", ".chip[data-custom=\"1\"]"
    if(sel === '.chip-config-btn') return this._cls && this._cls.includes('chip-config-btn');
    if(sel === '.chip'){ return this._cls && /\bchip\b/.test(this._cls); }
    if(sel === '.chip[data-custom="1"]'){
      return (this._cls && /\bchip\b/.test(this._cls)) && this.dataset.custom === '1';
    }
    if(sel.startsWith('.chip:not')){
      // El selector real: .chip:not([data-custom]):not(.chip-config-btn)
      const isChip = this._cls && /\bchip\b/.test(this._cls);
      const notCustom = !('custom' in this.dataset);
      const notGear = !(this._cls && this._cls.includes('chip-config-btn'));
      return isChip && notCustom && notGear;
    }
    return false;
  }
  querySelectorAll(sel){
    const res = [];
    for(const c of this.children){
      if(c._match && c._match(sel)) res.push(c);
      if(c.querySelectorAll){
        for(const d of c.querySelectorAll(sel)) res.push(d);
      }
    }
    return res;
  }
  querySelector(sel){
    const all = this.querySelectorAll(sel);
    return all[0] || null;
  }
}

// Build a fake "container" that mimics #chips-priv
function buildPrivRow(){
  const container = new El('div');
  container.setAttribute('id','chips-priv');
  const chips = [
    { c:'Revisión privada', label:'Revisión privada' },
    { c:'C.Oficial', preu:'20', label:'C.Oficial (20€)' },
    { c:'Fotos', preu:'4', label:'Fotos (4€)' },
    { c:'Certificado', preu:'66.5', label:'Certificado (66,50€)' },
    { c:'Duplicado', preu:'25', label:'Duplicado (25€)' },
    { c:'Informe', label:'Informe' },
  ];
  for(const ch of chips){
    const sp = new El('span');
    sp.className = 'chip';
    sp.dataset.c = ch.c;
    if(ch.preu) sp.dataset.preu = ch.preu;
    sp.textContent = ch.label;
    container.appendChild(sp);
  }
  const gear = new El('button');
  gear.className = 'chip-config-btn';
  gear.dataset.chipsRow = 'priv';
  container.appendChild(gear);
  return container;
}

function applyChipCustomizations(container, cfg){
  const systemChips = container.querySelectorAll('.chip:not([data-custom]):not(.chip-config-btn)');
  systemChips.forEach((c, i) => {
    const ov = cfg.overrides && cfg.overrides[i];
    if(!ov) return;
    if(ov.label!=null && ov.label!=='') c.textContent = ov.label;
    if(ov.preu!=null && ov.preu!=='') c.dataset.preu = String(ov.preu);
  });
  // delete prior custom
  const prevCustom = container.querySelectorAll('.chip[data-custom="1"]');
  prevCustom.forEach(c => c.remove());
  const gearBtn = container.querySelector('.chip-config-btn');
  (cfg.custom||[]).forEach(cc => {
    const sp = new El('span');
    sp.className = 'chip';
    sp.dataset.custom = '1';
    sp.dataset.c = cc.c || cc.label || '';
    if(cc.preu) sp.dataset.preu = String(cc.preu);
    if(cc.tipo) sp.dataset.tipo = cc.tipo;
    sp.textContent = cc.label || cc.c || '(sin etiqueta)';
    if(gearBtn) container.insertBefore(sp, gearBtn);
    else container.appendChild(sp);
  });
}

console.log('\n🧪 TEST 1 · Override de etiqueta y precio en chip de sistema');
console.log('════════════════════════════════════════════════════════════════');
{
  const container = buildPrivRow();
  const cfg = { overrides: { '1': { label: 'C.Oficial MODIF (25€)', preu: '25' } }, custom: [] };
  applyChipCustomizations(container, cfg);
  const chips = container.querySelectorAll('.chip:not([data-custom]):not(.chip-config-btn)');
  assert.strictEqual(chips[1].textContent, 'C.Oficial MODIF (25€)', 'label override no aplicado');
  assert.strictEqual(chips[1].dataset.preu, '25', 'preu override no aplicado');
  // El chip 2 (Fotos) NO debe cambiar
  assert.strictEqual(chips[2].textContent, 'Fotos (4€)', 'otros chips se vieron afectados');
  assert.strictEqual(chips[2].dataset.preu, '4', 'preu de otros chips modificado');
  console.log('  ✅ Override solo afecta al chip indicado');
}

console.log('\n🧪 TEST 2 · Añadir chip custom + idempotencia (3 applies seguidos)');
console.log('════════════════════════════════════════════════════════════════');
{
  const container = buildPrivRow();
  const cfg = { overrides: {}, custom: [
    { label: 'Carnet Náutico', c: 'Nautico', preu: '55', tipo: 'HABER' },
    { label: 'Permiso Grúa', c: 'Grua', preu: '70', tipo: 'HABER' },
  ]};
  applyChipCustomizations(container, cfg);
  applyChipCustomizations(container, cfg);
  applyChipCustomizations(container, cfg);
  const customs = container.querySelectorAll('.chip[data-custom="1"]');
  assert.strictEqual(customs.length, 2, `tras 3 applies, custom chips = ${customs.length}, debería ser 2`);
  assert.strictEqual(customs[0].textContent, 'Carnet Náutico');
  assert.strictEqual(customs[0].dataset.preu, '55');
  assert.strictEqual(customs[1].textContent, 'Permiso Grúa');
  console.log('  ✅ Custom chips idempotentes (no se duplican tras 3 applies)');
}

console.log('\n🧪 TEST 3 · Custom chips se insertan ANTES del botón ⚙️');
console.log('════════════════════════════════════════════════════════════════');
{
  const container = buildPrivRow();
  const cfg = { overrides: {}, custom: [{ label: 'Nuevo', c: 'Nuevo', preu: '10', tipo: 'HABER' }]};
  applyChipCustomizations(container, cfg);
  const last = container.children[container.children.length-1];
  assert.ok(last._cls.includes('chip-config-btn'), 'gear ya no es el último elemento');
  const beforeLast = container.children[container.children.length-2];
  assert.strictEqual(beforeLast.dataset.custom, '1', 'custom chip no está justo antes del gear');
  console.log('  ✅ Orden preservado: [sistema…] [custom…] [⚙️]');
}

console.log('\n🧪 TEST 4 · Eliminar un custom chip (round-trip)');
console.log('════════════════════════════════════════════════════════════════');
{
  const container = buildPrivRow();
  let cfg = { overrides: {}, custom: [
    { label: 'A', c:'A', preu:'10', tipo:'HABER' },
    { label: 'B', c:'B', preu:'20', tipo:'HABER' },
    { label: 'C', c:'C', preu:'30', tipo:'HABER' },
  ]};
  applyChipCustomizations(container, cfg);
  assert.strictEqual(container.querySelectorAll('.chip[data-custom="1"]').length, 3);
  // Eliminamos el chip B
  cfg.custom.splice(1, 1);
  applyChipCustomizations(container, cfg);
  const customs = container.querySelectorAll('.chip[data-custom="1"]');
  assert.strictEqual(customs.length, 2);
  assert.strictEqual(customs[0].textContent, 'A');
  assert.strictEqual(customs[1].textContent, 'C');
  console.log('  ✅ Eliminación limpia + re-render correcto');
}

console.log('\n🧪 TEST 5 · Los chips de SISTEMA nunca se borran');
console.log('════════════════════════════════════════════════════════════════');
{
  const container = buildPrivRow();
  const sysCountBefore = container.querySelectorAll('.chip:not([data-custom]):not(.chip-config-btn)').length;
  const cfg = { overrides: {}, custom: [
    { label: 'X', c:'X', preu:'5', tipo:'HABER' },
  ]};
  // Simular 5 ciclos de apply con añadir/eliminar custom
  for(let i=0;i<5;i++){
    cfg.custom = i%2===0 ? [{label:'X',c:'X',preu:'5',tipo:'HABER'}] : [];
    applyChipCustomizations(container, cfg);
  }
  const sysCountAfter = container.querySelectorAll('.chip:not([data-custom]):not(.chip-config-btn)').length;
  assert.strictEqual(sysCountAfter, sysCountBefore, `sistema cambió: antes=${sysCountBefore} después=${sysCountAfter}`);
  // Y el ⚙️ sigue ahí
  assert.ok(container.querySelector('.chip-config-btn'), 'botón ⚙️ desapareció');
  console.log('  ✅ Chips de sistema intactos tras N ciclos · gear persiste');
}

console.log('\n🧪 TEST 6 · Serialización/deserialización LocalStorage (round-trip)');
console.log('════════════════════════════════════════════════════════════════');
{
  const STORAGE_KEY = (row) => `caja.chips.${row}.v1`;
  const fakeLS = {};
  const saveCfg = (row,cfg) => fakeLS[STORAGE_KEY(row)] = JSON.stringify(cfg);
  const loadCfg = (row) => { try{ return JSON.parse(fakeLS[STORAGE_KEY(row)]||'{"overrides":{},"custom":[]}'); }catch(_){ return {overrides:{},custom:[]}; } };
  const cfgIn = {
    overrides: { '1': { label: 'C.Oficial MODIF', preu: '22.50' } },
    custom: [
      { label: 'Náutico', c: 'Nautico', preu: '55', tipo: 'HABER', color: '#f59e0b' },
      { label: 'Gasto Papel', c: 'Papel', preu: '12', tipo: 'DEBE' },
    ],
  };
  saveCfg('priv', cfgIn);
  const cfgOut = loadCfg('priv');
  assert.deepStrictEqual(cfgOut, cfgIn, 'round-trip rompe la estructura');
  // Y claves independientes por fila
  saveCfg('priv-cempla', { overrides:{}, custom:[{label:'Z',c:'Z',preu:'0',tipo:'HABER'}]});
  const dhDefault = loadCfg('dh');
  assert.deepStrictEqual(dhDefault, { overrides:{}, custom:[] }, 'default LS para dh roto');
  console.log('  ✅ Round-trip exacto · claves independientes por fila');
}

console.log('\n🧪 TEST 7 · tipo HABER/DEBE para chips-dh');
console.log('════════════════════════════════════════════════════════════════');
{
  const container = new El('div');
  container.setAttribute('id','chips-dh');
  const gear = new El('button');
  gear.className = 'chip-config-btn';
  gear.dataset.chipsRow = 'dh';
  container.appendChild(gear);
  const cfg = { overrides: {}, custom: [
    { label: 'Factura luz', c: 'Luz', preu: '55', tipo: 'DEBE' },
    { label: 'Donativo', c: 'Donativo', preu: '20', tipo: 'HABER' },
  ]};
  // Simulamos el bloque real `if(row === 'dh') sp.dataset.t = cc.tipo` para que
  // el handler global de la línea 4648 pueda leer data-t sin pisar nuestro valor.
  function applyChipCustomizationsDh(container, cfg){
    const prevCustom = container.querySelectorAll('.chip[data-custom="1"]');
    prevCustom.forEach(c => c.remove());
    const gearBtn = container.querySelector('.chip-config-btn');
    (cfg.custom||[]).forEach(cc => {
      const sp = new El('span');
      sp.className = 'chip';
      sp.dataset.custom = '1';
      sp.dataset.c = cc.c || cc.label || '';
      if(cc.preu) sp.dataset.preu = String(cc.preu);
      if(cc.tipo){
        sp.dataset.tipo = cc.tipo;
        sp.dataset.t = cc.tipo; // compat handler global #chips-dh
      }
      sp.textContent = cc.label || cc.c || '(sin etiqueta)';
      if(gearBtn) container.insertBefore(sp, gearBtn);
      else container.appendChild(sp);
    });
  }
  applyChipCustomizationsDh(container, cfg);
  const customs = container.querySelectorAll('.chip[data-custom="1"]');
  assert.strictEqual(customs.length, 2);
  assert.strictEqual(customs[0].dataset.tipo, 'DEBE');
  assert.strictEqual(customs[0].dataset.t, 'DEBE', 'data-t debe estar en custom chips de DH');
  assert.strictEqual(customs[1].dataset.tipo, 'HABER');
  assert.strictEqual(customs[1].dataset.t, 'HABER', 'data-t debe estar en custom chips de DH');
  console.log('  ✅ Chip-row dh · data-tipo + data-t (compat handler global) OK');
}

console.log('\n═══════════════════════════════════════════════════════════════════');
console.log('  📊 RESULTADO · 7 TESTS · 0 FAIL');
console.log('═══════════════════════════════════════════════════════════════════');
console.log('  🎉 Configuración de chips rápidos verificada:');
console.log('     · Idempotencia · Round-trip LS · No borra sistema · tipo DH ok');
