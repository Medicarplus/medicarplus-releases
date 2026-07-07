// ============================================================================
// Caja del Día · v2 COMERCIAL · Electron Main Process
// Marc Brugulat Lopez · 2026
// ============================================================================
const { app, BrowserWindow, Menu, shell, dialog } = require('electron');
const path = require('path');

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

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    icon: path.join(__dirname, 'assets', 'icon.ico'),
    title: 'Caja del Día',
    backgroundColor: '#0f172a',
    show: false, // no mostrem fins que estigui carregada (evita flash blanc)
    autoHideMenuBar: true, // amaga la barra de menús per defecte
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      devTools: false, // ⚠️ desactiva DevTools en producció (impedeix inspecció)
      spellcheck: false
    }
  });

  // Carrega el fitxer HTML local
  mainWindow.loadFile('index.html');

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

  autoUpdater.on('update-available', (info) => {
    updateAvailable = true;
    console.log('Nova versió disponible:', info.version);
  });

  autoUpdater.on('update-not-available', () => {
    updateAvailable = false;
  });

  autoUpdater.on('error', (err) => {
    console.warn('Auto-update error:', err.message);
    // Silenciós — el client no ha de veure errors de update si el repo encara
    // no està configurat o si no hi ha internet.
  });

  autoUpdater.on('update-downloaded', (info) => {
    dialog.showMessageBox(mainWindow, {
      type: 'info',
      buttons: ['Reiniciar i actualitzar ara', 'Més tard'],
      defaultId: 0,
      cancelId: 1,
      title: 'Actualització disponible',
      message: `Caja del Día v${info.version} està llest per instal·lar`,
      detail: 'La nova versió s\'ha descarregat i s\'instal·larà al reiniciar. Vols reiniciar ara?'
    }).then(result => {
      if (result.response === 0) {
        autoUpdater.quitAndInstall();
      }
    }).catch(() => {});
  });

  // Comprovació silenciosa a l'arrencada (espera 5s perquè no bloquegi UI)
  setTimeout(() => {
    try { autoUpdater.checkForUpdatesAndNotify(); }
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
          label: 'Sobre Caja del Día',
          click: () => {
            dialog.showMessageBox({
              type: 'info',
              title: 'Sobre Caja del Día',
              message: `Caja del Día · v${app.getVersion()}`,
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
