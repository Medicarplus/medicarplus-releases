// ============================================================================
// Preload script — pont segur entre el main process i el renderer
// Marc Brugulat Lopez · 2026
// ============================================================================
// Exposa nomes info del maquinari necessaria per a HWID lock. El renderer
// no te acces directe a Node.js APIs (contextIsolation + sandbox actius).
// ============================================================================

const { contextBridge, ipcRenderer } = require('electron');
// La versió es passa via additionalArguments des de main.js perquè sandbox=true no permet require('./package.json')
function readAppVersion(){
  try{
    const arg = (process.argv || []).find(a => typeof a==='string' && a.startsWith('--app-version='));
    if(arg) return arg.split('=')[1];
  }catch(e){}
  return '2.0.0';
}
const APP_VERSION = readAppVersion();
const os = require('os');
const crypto = require('crypto');

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
});
