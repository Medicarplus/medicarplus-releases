// ============================================================================
// Caja del Día · v2 COMERCIAL · Electron Main Process
// Marc Brugulat Lopez · 2026
// ============================================================================
const { app, BrowserWindow, Menu, shell, dialog } = require('electron');
const path = require('path');

// Bloqueja segona instància (evita obrir l'app dos cops)
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
  process.exit(0);
}

let mainWindow;

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

// Menú buit (només amb "Sortir" i "Sobre")
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
          label: 'Sobre Caja del Día',
          click: () => {
            dialog.showMessageBox({
              type: 'info',
              title: 'Sobre Caja del Día',
              message: 'Caja del Día · v2.0.0',
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
