/**
 * 🔗 MediCar Plus · Sync Multi-PC Client (Fase 2)
 *
 * Uso desde v2.html:
 *   window.mcSync.init({
 *     apiBase: '<REACT_APP_BACKEND_URL>',
 *     licenseKey: '<JWT>',
 *     installId: '<install_id>',
 *     onIncoming: (mergedData) => { ...apply to localStorage... },
 *     onModeChange: (mode) => { ...update UI... }
 *   });
 *   window.mcSync.startAutosync();
 *   window.mcSync.setMode('linked'|'independent');
 *   window.mcSync.sendBackup(label);
 *   window.mcSync.getPendingBackup();
 *   window.mcSync.applyBackup(backupId, mergedLocal);
 */
(function(global){
  const cfg = { apiBase:null, licenseKey:null, installId:null,
                onIncoming:null, onModeChange:null };
  let autosyncTimer = null;
  let currentMode = 'independent';
  let currentPeers = [];

  const _url = (p) => `${cfg.apiBase.replace(/\/$/,'')}${p}`;
  const _headers = { 'Content-Type': 'application/json' };

  async function _post(path, body){
    const r = await fetch(_url(path), { method:'POST', headers:_headers, body: JSON.stringify(body) });
    if(!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
    return r.json();
  }
  async function _get(path){
    const r = await fetch(_url(path));
    if(!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
    return r.json();
  }

  // ─── Snapshot completo del localStorage relevante (todas las keys 'caja.*') ─────
  function _snapshotLocalStorage(){
    const out = {};
    for(let i=0; i<localStorage.length; i++){
      const k = localStorage.key(i);
      if(!k || !k.startsWith('caja.')) continue;
      try { out[k] = JSON.parse(localStorage.getItem(k)); }
      catch(e){ out[k] = localStorage.getItem(k); }
    }
    return out;
  }

  // ─── Merge sin duplicados en cliente ───────────────────────────────────────
  // Para arrays con id: unión por id (más reciente gana si mismo id + updated_at)
  // Para objetos byDate (dict de arrays): merge por iso → merge de arrays
  // Para escalares/configs: si remote tiene updated_at más nuevo, remote gana
  function _mergeArrays(local, remote){
    const map = new Map();
    (local||[]).forEach(e => { if(e && e.id) map.set(e.id, e); else map.set(Symbol(), e); });
    (remote||[]).forEach(e => {
      if(!e || !e.id) return map.set(Symbol(), e);
      const cur = map.get(e.id);
      // Si el remoto es más reciente (updated_at) o el local no existe → remote gana
      const cur_ts = cur && cur.updated_at ? new Date(cur.updated_at).getTime() : 0;
      const rem_ts = e.updated_at ? new Date(e.updated_at).getTime() : 0;
      if(!cur || rem_ts >= cur_ts) map.set(e.id, e);
    });
    return Array.from(map.values());
  }
  function _mergeByDate(local, remote){
    const out = {};
    const dates = new Set([...Object.keys(local||{}), ...Object.keys(remote||{})]);
    dates.forEach(iso => {
      out[iso] = _mergeArrays((local||{})[iso], (remote||{})[iso]);
    });
    return out;
  }
  function _isByDateShape(v){
    if(!v || typeof v !== 'object' || Array.isArray(v)) return false;
    const k = Object.keys(v)[0];
    return typeof k === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(k);
  }
  // Merge de 2 snapshots completos de localStorage
  function _mergeSnapshots(localSnap, remoteSnap){
    const out = {};
    const keys = new Set([...Object.keys(localSnap||{}), ...Object.keys(remoteSnap||{})]);
    keys.forEach(k => {
      const lv = (localSnap||{})[k];
      const rv = (remoteSnap||{})[k];
      if(rv === undefined){ out[k] = lv; return; }
      if(lv === undefined){ out[k] = rv; return; }
      // Detectar shape byDate
      if(_isByDateShape(lv) && _isByDateShape(rv)){ out[k] = _mergeByDate(lv, rv); return; }
      // Detectar objetos con {byDate: {...}}
      if(lv && rv && lv.byDate && rv.byDate){
        out[k] = { ...lv, ...rv, byDate: _mergeByDate(lv.byDate, rv.byDate) }; return;
      }
      // Arrays con id → merge por id
      if(Array.isArray(lv) && Array.isArray(rv)){ out[k] = _mergeArrays(lv, rv); return; }
      // Configs: si remote tiene _mtime más nuevo → gana remote, si no → local
      const lts = (lv && lv._mtime) || 0;
      const rts = (rv && rv._mtime) || 0;
      out[k] = rts > lts ? rv : lv;
    });
    return out;
  }

  // ─── API public ────────────────────────────────────────────────────────────
  async function init(opts){
    Object.assign(cfg, opts);
    if(!cfg.apiBase || !cfg.licenseKey || !cfg.installId){
      console.warn('[mcSync] Falta apiBase / licenseKey / installId');
      return { ok:false };
    }
    try {
      const hb = await _post('/api/sync/heartbeat', {
        license_key: cfg.licenseKey, install_id: cfg.installId
      });
      const st = await _get(`/api/sync/status?license_key=${encodeURIComponent(cfg.licenseKey)}&install_id=${encodeURIComponent(cfg.installId)}`);
      currentMode = st.my_mode || 'independent';
      currentPeers = st.peers || [];
      if(cfg.onModeChange) cfg.onModeChange(currentMode, st);
      return { ok:true, heartbeat: hb, status: st };
    } catch(e){
      console.warn('[mcSync] init error', e);
      return { ok:false, error: e.message };
    }
  }
  async function setMode(mode){
    if(mode !== 'linked' && mode !== 'independent') throw new Error('mode inválido');
    const r = await _post('/api/sync/mode', {
      license_key: cfg.licenseKey, install_id: cfg.installId, mode
    });
    currentMode = mode;
    if(cfg.onModeChange) cfg.onModeChange(mode, r);
    return r;
  }
  async function getStatus(){
    return await _get(`/api/sync/status?license_key=${encodeURIComponent(cfg.licenseKey)}&install_id=${encodeURIComponent(cfg.installId)}`);
  }
  async function pushNow(){
    if(currentMode !== 'linked') return { skipped: true, reason: 'independent' };
    const snap = _snapshotLocalStorage();
    // Adaptar formato al esperado por backend (entries: { key: { value, updated_at }})
    const now = new Date().toISOString();
    const entries = {};
    Object.keys(snap).forEach(k => { entries[k] = { value: snap[k], updated_at: now }; });
    try {
      const r = await _post('/api/sync/push', {
        license_key: cfg.licenseKey, install_id: cfg.installId, entries
      });
      return r;
    } catch(e){ return { error: e.message }; }
  }
  async function pullNow(){
    if(currentMode !== 'linked') return { skipped: true, reason: 'independent' };
    try {
      const r = await _get(`/api/sync/pull?license_key=${encodeURIComponent(cfg.licenseKey)}&install_id=${encodeURIComponent(cfg.installId)}`);
      const cloudSnap = {};
      Object.entries(r.entries || {}).forEach(([k, v]) => { cloudSnap[k] = v && v.value; });
      // Merge con localStorage local (sin duplicados)
      const localSnap = _snapshotLocalStorage();
      const merged = _mergeSnapshots(localSnap, cloudSnap);
      if(cfg.onIncoming) cfg.onIncoming(merged, cloudSnap);
      return r;
    } catch(e){ return { error: e.message }; }
  }
  function startAutosync(intervalMs = 30000){
    if(autosyncTimer) clearInterval(autosyncTimer);
    autosyncTimer = setInterval(async () => {
      if(currentMode !== 'linked') return;
      await pushNow();
      await pullNow();
    }, intervalMs);
  }
  function stopAutosync(){
    if(autosyncTimer){ clearInterval(autosyncTimer); autosyncTimer = null; }
  }
  async function sendBackup(label){
    const data = _snapshotLocalStorage();
    return await _post('/api/sync/backup/send', {
      license_key: cfg.licenseKey, install_id: cfg.installId,
      data, label: label || null
    });
  }
  async function getPendingBackup(){
    return await _get(`/api/sync/backup/pending?license_key=${encodeURIComponent(cfg.licenseKey)}&install_id=${encodeURIComponent(cfg.installId)}`);
  }
  async function applyBackup(backupData){
    // Merge en cliente y devuelve el snapshot resultante (sin escribir aún — el caller decide)
    const localSnap = _snapshotLocalStorage();
    return _mergeSnapshots(localSnap, backupData || {});
  }
  async function consumeBackup(backupId){
    return await _post('/api/sync/backup/consume', {
      license_key: cfg.licenseKey, install_id: cfg.installId, backup_id: backupId
    });
  }
  function getMode(){ return currentMode; }
  function getPeers(){ return currentPeers; }

  global.mcSync = { init, setMode, getMode, getStatus, getPeers,
                    pushNow, pullNow, startAutosync, stopAutosync,
                    sendBackup, getPendingBackup, applyBackup, consumeBackup,
                    _mergeSnapshots  // exportado para testear en consola
                  };
})(window);
