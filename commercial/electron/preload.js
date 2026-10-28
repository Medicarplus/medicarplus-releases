// ============================================================================
// Preload script — pont segur entre el main process i el renderer
// Marc Brugulat Lopez · 2026
// ============================================================================
// Exposa nomes info del maquinari necessaria per a HWID lock. El renderer
// no te acces directe a Node.js APIs (contextIsolation actiu, sandbox false
// perque necessitem os/crypto/require al preload).
// ============================================================================

const { contextBridge, ipcRenderer, webUtils } = require('electron');
const os = require('os');
const path = require('path');
const crypto = require('crypto');

// Llegim la versió del package.json en runtime (sandbox=false permet require)
function readAppVersion(){
  try{
    const pkg = require('./package.json');
    if(pkg && pkg.version) return pkg.version;
  }catch(e){
    console.warn('preload: no s\'ha pogut llegir package.json:', e.message);
  }
  return '0.0.0';
}
const APP_VERSION = readAppVersion();

/**
 * Genera un HWID estable a partir de trets del maquinari.
 * Combina: hostname + platform + arquitectura + primera MAC no-virtual.
 * Sortida: SHA-256 hex tallat a 24 chars → estable entre reinicis del PC,
 * canvia si l'usuari canvia d'ordinador.
 */
function computeHwid() {
  try {
    const parts = [
      os.hostname() || '',
      os.platform() || '',
      os.arch() || '',
      String(os.totalmem() || 0),
    ];
    // Afegim la primera MAC address no interna (les internes són 00:00:00:...)
    const nets = os.networkInterfaces();
    for (const name of Object.keys(nets)) {
      for (const iface of nets[name] || []) {
        if (!iface.internal && iface.mac && iface.mac !== '00:00:00:00:00:00') {
          parts.push(iface.mac);
          break;
        }
      }
      if (parts.length >= 5) break;
    }
    const hash = crypto.createHash('sha256').update(parts.join('|')).digest('hex');
    return 'HW-' + hash.slice(0, 24).toUpperCase();
  } catch (e) {
    return null;
  }
}

contextBridge.exposeInMainWorld('appInfo', {
  version: APP_VERSION,
  platform: 'electron',
  isDesktop: true,
  hwid: computeHwid(),
  checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),
  onUpdateEvent: (callback) => {
    const handler = (_ev, payload) => callback(payload);
    ipcRenderer.on('update-available', (_ev, p) => callback({ event: 'available', ...p }));
    ipcRenderer.on('update-progress', (_ev, p) => callback({ event: 'progress', ...p }));
    ipcRenderer.on('update-downloaded', (_ev, p) => callback({ event: 'downloaded', ...p }));
    ipcRenderer.on('update-error', (_ev, p) => callback({ event: 'error', ...p }));
  },
  // feb 2026 · Devuelve la ruta OS real del File object (Electron 32+).
  //   El renderer la usa para mostrar la carpeta real donde se ha guardado
  //   la copia de seguridad después de showSaveFilePicker().
  getPathForFile: (f) => {
    try{
      if(!f || !webUtils || typeof webUtils.getPathForFile !== 'function') return null;
      const full = webUtils.getPathForFile(f);
      if(!full) return null;
      return { full, dir: path.dirname(full), base: path.basename(full) };
    }catch(_){ return null; }
  },
  // oct 2026 · Guarda la copia vía diálogo nativo del main process.
  //   Devuelve { ok, path, dir, filename } con la ruta OS real.
  //   Preferido sobre showSaveFilePicker porque webUtils.getPathForFile
  //   NO retorna la ruta en archivos de FileSystemFileHandle.
  saveBackupViaDialog: (contents, suggestedName, lastDir) =>
    ipcRenderer.invoke('backup-save-dialog', { contents, suggestedName, lastDir }),
  // oct 2026 · Escritura silenciosa de la auto-copia dentro de `dir/filename`.
  //   Devuelve { ok, path, dir, filename } con la ruta OS real para el panel.
  autoWriteBackup: (contents, dir, filename) =>
    ipcRenderer.invoke('backup-auto-write', { contents, dir, filename }),
});
