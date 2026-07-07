// ============================================================================
// Preload script — pont segur entre el main process i el renderer
// Marc Brugulat Lopez · 2026
// ============================================================================
// En aquesta versió no exposem cap API Node al renderer (màxima seguretat).
// Si en el futur cal accedir a fitxers locals per backups o similar,
// afegir aquí els mètodes exposats mitjançant contextBridge.exposeInMainWorld.

const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('appInfo', {
  version: '2.0.0',
  platform: 'electron',
  isDesktop: true
});
