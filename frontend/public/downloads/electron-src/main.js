// ============================================================================
// MediCar Plus · v2 COMERCIAL · Electron Main Process
// Marc Brugulat Lopez · 2026
// ============================================================================
const { app, BrowserWindow, Menu, shell, dialog, ipcMain, net } = require('electron');
const path = require('path');
const fs = require('fs');
const https = require('https');

// Auto-updater (Opció A: GitHub Releases). Fallar silenciosament si el repo
// no està configurat, així el dev local no peta.
let autoUpdater = null;
try {
  ({ autoUpdater } = require('electron-updater'));
} catch (e) {
  console.warn('electron-updater no disponible:', e.message);
}

// Bloqueja segona instància (evita obrir l'app dos cops)
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
  process.exit(0);
}

let mainWindow;
let updateAvailable = false;

// ============================================================================
// RUNTIME DISCOVERY · sempre carrega v2.html del SERVIDOR (mai el local del disc)
// ----------------------------------------------------------------------------
// Fluxe cada cop que s'obre el .exe:
//   1) Descobreix la URL del backend via la mateixa cadena de 4 fonts que sync.js
//      (raw.githubusercontent → jsdelivr → api.github → cache local).
//   2) Carrega `SERVER/v2.html?t=Date.now()` (no-cache) — sempre l'últim UI.
//   3) Si TOTS els discoveries fallen (sense internet, GitHub caigut...) llavors
//      i només llavors → cau al `index.html` local com a xarxa de seguretat.
//
// Conseqüència: qualsevol canvi al v2.html del servidor arriba als clients la
// propera vegada que obren l'app, sense recompilar mai més el .exe.
// ============================================================================
const DISCOVERY_SOURCES = [
  'https://raw.githubusercontent.com/Medicarplus/medicarplus-releases/main/api-endpoint.json',
  'https://cdn.jsdelivr.net/gh/Medicarplus/medicarplus-releases@main/api-endpoint.json',
  'https://api.github.com/repos/Medicarplus/medicarplus-releases/contents/api-endpoint.json',
];
const LAST_KNOWN_FILE = path.join(app.getPath('userData'), 'last-known-server.json');

function _httpGetJson(url, timeoutMs = 8000) {
  return new Promise((resolve, reject) => {
    try {
      const req = https.get(url, {
        timeout: timeoutMs,
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) MediCarPlus-Electron',
          'Accept': 'application/json,*/*',
          'Cache-Control': 'no-cache, no-store, must-revalidate',
        },
      }, (res) => {
        if (res.statusCode !== 200) return reject(new Error('HTTP ' + res.statusCode));
        const chunks = [];
        res.on('data', c => chunks.push(c));
        res.on('end', () => {
          try {
            const txt = Buffer.concat(chunks).toString('utf8');
            resolve(JSON.parse(txt));
          } catch (e) { reject(e); }
        });
        res.on('error', reject);
      });
      req.on('error', reject);
      req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    } catch (e) { reject(e); }
  });
}

function _parseApiField(j) {
  if (j && j.api && /^https?:\/\//.test(j.api)) return j.api.replace(/\/+$/, '');
  if (j && j.content && j.encoding === 'base64') {
    try {
      const decoded = Buffer.from(j.content, 'base64').toString('utf8');
      const inner = JSON.parse(decoded);
      if (inner && inner.api && /^https?:\/\//.test(inner.api)) return inner.api.replace(/\/+$/, '');
    } catch (e) { /* ignore */ }
  }
  return null;
}

async function discoverServerUrl() {
  // 1) Prova cada font online (2 intents amb backoff)
  for (let i = 0; i < DISCOVERY_SOURCES.length; i++) {
    const src = DISCOVERY_SOURCES[i];
    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        const url = src + (src.includes('?') ? '&' : '?') + 't=' + Date.now();
        const j = await _httpGetJson(url, 8000);
        const api = _parseApiField(j);
        if (api) {
          try {
            fs.mkdirSync(path.dirname(LAST_KNOWN_FILE), { recursive: true });
            fs.writeFileSync(LAST_KNOWN_FILE, JSON.stringify({ api, discoveredAt: new Date().toISOString(), source: src }, null, 2));
          } catch (e) { /* ignore */ }
          return api;
        }
      } catch (e) {
        await new Promise(r => setTimeout(r, 400 * attempt));
      }
    }
  }
  // 2) Cache local
  try {
    if (fs.existsSync(LAST_KNOWN_FILE)) {
      const cached = JSON.parse(fs.readFileSync(LAST_KNOWN_FILE, 'utf8'));
      if (cached && cached.api) return cached.api.replace(/\/+$/, '');
    }
  } catch (e) { /* ignore */ }
  return null;
}


function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    icon: path.join(__dirname, 'assets', 'icon.ico'),
    title: 'MediCar Plus',
    backgroundColor: '#0f172a',
    show: false, // no mostrem fins que estigui carregada (evita flash blanc)
    autoHideMenuBar: true, // amaga la barra de menús per defecte
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: true,
      devTools: false, // ⚠️ desactiva DevTools en producció (impedeix inspecció)
      spellcheck: false
    }
  });

  // ── Càrrega WYSIWYG · sempre del servidor (fallback a local si offline) ──
  loadUiFromServerOrLocal();

  // Mostra la finestra quan estigui llesta
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.maximize();
  });

  // Bloqueja shortcuts de DevTools (F12, Ctrl+Shift+I, Ctrl+U)
  mainWindow.webContents.on('before-input-event', (event, input) => {
    const blocked = [
      { key: 'F12' },
      { key: 'I', ctrl: true, shift: true },
      { key: 'J', ctrl: true, shift: true },
      { key: 'C', ctrl: true, shift: true },
      { key: 'U', ctrl: true }
    ];
    for (const b of blocked) {
      if (input.key === b.key &&
          (!b.ctrl || input.control) &&
          (!b.shift || input.shift)) {
        event.preventDefault();
        return;
      }
    }
  });

  // Bloqueja el menú contextual (botó dret)
  mainWindow.webContents.on('context-menu', (e) => {
    e.preventDefault();
  });

  // Obre els enllaços externs al navegador per defecte (no dins l'app)
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) shell.openExternal(url);
    return { action: 'deny' };
  });

  // Evita que l'usuari navegui fora de l'HTML local
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith('file://')) {
      event.preventDefault();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Carrega v2.html: primer intenta baixar l'ÚLTIMA versió del servidor i sobreescriu
// la còpia local. Després carrega el fitxer local (preservant l'origen file:// i,
// per tant, totes les dades de l'usuari a localStorage/indexedDB).
// Si no hi ha connexió, carrega directament el local antic (últim rebut).
async function loadUiFromServerOrLocal() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  const localHtmlPath = path.join(__dirname, 'index.html');
  try {
    const server = await discoverServerUrl();
    if (server) {
      try {
        const remoteHtml = await _httpGetBuffer(server + '/v2.html?t=' + Date.now(), 12000);
        // Validació mínima: ha de ser HTML de MediCar Plus (signatura de contingut)
        const txt = remoteHtml.toString('utf8');
        if (txt.includes('MediCar Plus') && txt.includes('Entradas del día') && txt.length > 50000) {
          // Sobreescriu la còpia local només si ha canviat (evita I/O innecessària)
          let needsWrite = true;
          try {
            const cur = fs.readFileSync(localHtmlPath);
            if (cur.equals(remoteHtml)) needsWrite = false;
          } catch (e) { /* ignore */ }
          if (needsWrite) {
            try {
              fs.writeFileSync(localHtmlPath, remoteHtml);
              console.log('[MediCar] v2.html actualitzat des del servidor (' + (remoteHtml.length / 1024).toFixed(1) + ' KB).');
            } catch (writeErr) {
              console.warn('[MediCar] No s\'ha pogut escriure v2.html local:', writeErr.message);
            }
          } else {
            console.log('[MediCar] v2.html ja al dia amb el servidor.');
          }
        } else {
          console.warn('[MediCar] v2.html descarregat NO passa la validació — es descarta.');
        }
      } catch (fetchErr) {
        console.warn('[MediCar] Fetch v2.html FAIL, es fa servir la còpia local:', fetchErr.message);
      }
    } else {
      console.warn('[MediCar] Cap servidor descobert · fem servir v2.html local existent.');
    }
  } catch (e) {
    console.warn('[MediCar] Discovery error · fallback local:', e.message);
  }
  // Sempre carreguem el fitxer local (que ara pot haver estat actualitzat).
  // Aquest és el pas clau que preserva localStorage/indexedDB del client.
  try { await mainWindow.loadFile('index.html'); } catch (e) { console.error('[MediCar] Local UI FAIL:', e); }
}

function _httpGetBuffer(url, timeoutMs) {
  return new Promise((resolve, reject) => {
    try {
      const req = https.get(url, {
        timeout: timeoutMs || 12000,
        headers: {
          'User-Agent': 'MediCarPlus-Electron/1.0',
          'Accept': 'text/html,*/*',
          'Cache-Control': 'no-cache, no-store, must-revalidate',
        },
      }, (res) => {
        if (res.statusCode !== 200) return reject(new Error('HTTP ' + res.statusCode));
        const chunks = [];
        res.on('data', c => chunks.push(c));
        res.on('end', () => resolve(Buffer.concat(chunks)));
        res.on('error', reject);
      });
      req.on('error', reject);
      req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    } catch (e) { reject(e); }
  });
}

// ============================================================================
// AUTO-UPDATE (electron-updater + GitHub Releases)
// ----------------------------------------------------------------------------
// Requereix haver publicat una Release al repo GitHub configurat a package.json
// (build.publish). Quan detecta versió nova, la descarrega en background i
// pregunta al client si vol reiniciar per instal·lar-la.
//
// Trigger:
//   · Automàtic al arrencar (checkForUpdatesAndNotify)
//   · Manual des del menú Ajuda → Comprovar actualitzacions
// ============================================================================
function setupAutoUpdater() {
  if (!autoUpdater) return;

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.logger = null; // desactivat en producció
  // Desactiva verificació de signatura digital (no signem els .exe amb cert de pagament)
  if (typeof autoUpdater.disableWebInstaller !== 'undefined') autoUpdater.disableWebInstaller = false;
  autoUpdater.forceDevUpdateConfig = false;

  let latestUpdateInfo = null;
  let killSwitch = { blocked: [], latest_safe: null, action: 'ok' };

  // KILL SWITCH · consulta al servidor abans de deixar que autoUpdater instal·li res
  const KILL_URL = 'https://project-helper-47.preview.emergentagent.com/api/electron/update-channel';
  async function fetchKillSwitch() {
    return new Promise((resolve) => {
      try {
        const https = require('https');
        const url = `${KILL_URL}?current_version=${encodeURIComponent(app.getVersion())}&t=${Date.now()}`;
        const req = https.get(url, { timeout: 8000 }, (res) => {
          if (res.statusCode !== 200) return resolve(null);
          const chunks = [];
          res.on('data', c => chunks.push(c));
          res.on('end', () => {
            try {
              const d = JSON.parse(Buffer.concat(chunks).toString('utf8'));
              resolve(d);
            } catch (e) { resolve(null); }
          });
        });
        req.on('error', () => resolve(null));
        req.on('timeout', () => { req.destroy(); resolve(null); });
      } catch (e) { resolve(null); }
    });
  }

  function versionGT(a, b) {
    const pa = String(a).split('.').map(Number);
    const pb = String(b).split('.').map(Number);
    for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
      const x = pa[i] || 0, y = pb[i] || 0;
      if (x > y) return true;
      if (x < y) return false;
    }
    return false;
  }

  autoUpdater.on('update-available', async (info) => {
    updateAvailable = true;
    latestUpdateInfo = info;
    console.log('Nova versió disponible:', info.version);

    // KILL SWITCH CHECK: consulta el servidor si aquesta versió està bloquejada
    const ks = await fetchKillSwitch();
    if (ks) {
      killSwitch = ks;
      if (Array.isArray(ks.blocked_versions) && ks.blocked_versions.includes(info.version)) {
        console.warn(`⛔ Versió ${info.version} BLOQUEJADA pel servidor — cancel·lem l'update.`);
        // Cancel·la la descàrrega — no volem instal·lar una versió dolenta
        try { autoUpdater.autoDownload = false; } catch(e) { /* ignorem */ }
        try { autoUpdater.autoInstallOnAppQuit = false; } catch(e) { /* ignorem */ }
        return;
      }
      if (ks.latest_safe_version && versionGT(info.version, ks.latest_safe_version)) {
        console.warn(`⛔ Versió ${info.version} > latest_safe (${ks.latest_safe_version}) — cancel·lem l'update.`);
        try { autoUpdater.autoDownload = false; } catch(e) { /* ignorem */ }
        try { autoUpdater.autoInstallOnAppQuit = false; } catch(e) { /* ignorem */ }
        return;
      }
    }

    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('update-available', { version: info.version });
    }
  });

  autoUpdater.on('update-not-available', () => {
    updateAvailable = false;
  });

  autoUpdater.on('download-progress', (progress) => {
    // Envia el % al renderer per mostrar-lo a la barra de progres del modal ⚙️
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('update-progress', {
        percent: Math.round(progress.percent),
        transferred: progress.transferred,
        total: progress.total,
        bytesPerSecond: progress.bytesPerSecond
      });
    }
  });

  autoUpdater.on('error', (err) => {
    console.warn('Auto-update error:', err.message);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('update-error', { message: err.message });
    }
  });

  autoUpdater.on('update-downloaded', (info) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('update-downloaded', { version: info.version });
    }
    dialog.showMessageBox(mainWindow, {
      type: 'info',
      buttons: ['🚀 Reiniciar i actualitzar ara', 'Més tard'],
      defaultId: 0,
      cancelId: 1,
      title: '✨ Nova versió llesta',
      message: `MediCar Plus v${info.version} descarregada correctament`,
      detail: 'S\'instal·larà i l\'app es reiniciarà en 2-3 segons. Les teves dades es preserven íntegrament.\n\nVols reiniciar ara?'
    }).then(result => {
      if (result.response === 0) {
        setTimeout(() => autoUpdater.quitAndInstall(), 100);
      }
    }).catch(() => {});
  });

  // Comprovació silenciosa a l'arrencada (espera 5s perquè no bloquegi UI)
  setTimeout(() => {
    try { autoUpdater.checkForUpdates(); }
    catch (e) { console.warn('checkForUpdates failed:', e.message); }
  }, 5000);
}

// Comprovació manual (des del menú)
function checkForUpdatesManual() {
  if (!autoUpdater) {
    dialog.showMessageBox(mainWindow, {
      type: 'warning',
      title: 'Actualitzacions no disponibles',
      message: 'El sistema d\'actualitzacions no està disponible en aquesta versió.',
      buttons: ['D\'acord']
    });
    return;
  }
  autoUpdater.checkForUpdates().then(result => {
    if (!result || !result.updateInfo || result.updateInfo.version === app.getVersion()) {
      dialog.showMessageBox(mainWindow, {
        type: 'info',
        title: 'Ja estàs al dia',
        message: `Tens la última versió instal·lada (v${app.getVersion()}).`,
        buttons: ['D\'acord']
      });
    }
    // Si n'hi ha nova, el listener 'update-downloaded' ja mostrarà el diàleg.
  }).catch(err => {
    dialog.showMessageBox(mainWindow, {
      type: 'error',
      title: 'Error comprovant actualitzacions',
      message: 'No s\'ha pogut connectar amb el servidor.',
      detail: err.message,
      buttons: ['D\'acord']
    });
  });
}

// Menú amb "Sortir" + "Comprovar actualitzacions" + "Sobre"
function setupMenu() {
  const template = [
    {
      label: 'Arxiu',
      submenu: [
        { role: 'quit', label: 'Sortir' }
      ]
    },
    {
      label: 'Ajuda',
      submenu: [
        {
          label: 'Comprovar actualitzacions',
          click: () => checkForUpdatesManual()
        },
        { type: 'separator' },
        {
          label: 'Sobre MediCar Plus',
          click: () => {
            dialog.showMessageBox({
              type: 'info',
              title: 'Sobre MediCar Plus',
              message: `MediCar Plus · v${app.getVersion()}`,
              detail: 'Software comercial per centres mèdics i autoescoles.\n\n' +
                      'Creat per Marc Brugulat Lopez\n' +
                      '© 2026 · Tots els drets reservats\n\n' +
                      'Aquesta còpia està llicenciada. Contacte per suport tècnic.',
              buttons: ['D\'acord']
            });
          }
        }
      ]
    }
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// IPC: Comprovar actualitzacions des del renderer (botó dins l'app)
ipcMain.handle('check-for-updates', async () => {
  if (!autoUpdater) {
    return { ok: false, status: 'unavailable', currentVersion: app.getVersion() };
  }
  try {
    const result = await autoUpdater.checkForUpdates();
    const currentVersion = app.getVersion();
    const latest = result && result.updateInfo ? result.updateInfo.version : currentVersion;
    if (latest && latest !== currentVersion) {
      return { ok: true, status: 'available', currentVersion, latestVersion: latest };
    }
    return { ok: true, status: 'uptodate', currentVersion, latestVersion: latest };
  } catch (err) {
    return { ok: false, status: 'error', message: err.message, currentVersion: app.getVersion() };
  }
});

app.whenReady().then(() => {
  setupMenu();
  createWindow();
  setupAutoUpdater();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Bloqueja creació d'altres finestres no autoritzades
app.on('web-contents-created', (event, contents) => {
  contents.on('will-attach-webview', (e) => e.preventDefault());
});

// Bloqueja segona instància (activa la ja oberta)
app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});
