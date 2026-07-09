#!/usr/bin/env node
// ============================================================================
// sync.js — Auto-sincronitza els fitxers font des del servidor abans de build
// Marc Brugulat Lopez · 2026
// ----------------------------------------------------------------------------
// Es crida automàticament abans de `npm run release`. Descarrega les últimes
// versions de index.html, main.js i preload.js del servidor de MediCar Plus
// perquè el .exe generat sempre inclogui els canvis més recents.
//
// NO sobreescriu package.json (per no trencar la versió local).
// ============================================================================

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

// URL base del servidor on hi ha els fitxers font actualitzats.
// Ordre de prioritat: producció primer, preview com a fallback.
const SOURCES = [
  'https://medicarplus.es/downloads/electron-src',
  'https://project-helper-47.preview.emergentagent.com/downloads/electron-src'
];

const FILES = ['index.html', 'main.js', 'preload.js'];

function download(url, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    const req = client.get(url, { timeout: timeoutMs }, (res) => {
      // Segueix redireccions
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return resolve(download(res.headers.location, timeoutMs));
      }
      if (res.statusCode !== 200) {
        return reject(new Error(`HTTP ${res.statusCode}`));
      }
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve(Buffer.concat(chunks)));
      res.on('error', reject);
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
  });
}

async function tryDownloadFile(fileName) {
  let lastErr = null;
  for (const base of SOURCES) {
    const url = `${base}/${fileName}?t=${Date.now()}`;
    try {
      const data = await download(url);
      if (data.length < 100) {
        throw new Error(`Fitxer massa petit (${data.length} bytes)`);
      }
      return { data, url };
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr || new Error('cap font disponible');
}

(async () => {
  console.log('🔄 Sincronitzant fitxers font des del servidor...');
  const localDir = __dirname;
  let updated = 0;
  let failed = 0;

  for (const f of FILES) {
    process.stdout.write(`   · ${f} ... `);
    try {
      const { data, url } = await tryDownloadFile(f);
      const localPath = path.join(localDir, f);
      let changed = true;
      if (fs.existsSync(localPath)) {
        const current = fs.readFileSync(localPath);
        if (current.equals(data)) changed = false;
      }
      if (changed) {
        fs.writeFileSync(localPath, data);
        console.log(`✅ actualitzat (${(data.length/1024).toFixed(1)} KB) [${new URL(url).hostname}]`);
        updated++;
      } else {
        console.log('✔️  ja al dia');
      }
    } catch (e) {
      console.log(`⚠️  no disponible (${e.message}) — mantenim la còpia local`);
      failed++;
    }
  }

  console.log(`\n📦 Resultat: ${updated} fitxer(s) actualitzat(s), ${failed} error(s)`);
  if (failed === FILES.length) {
    console.log('⚠️  No s\'ha pogut sincronitzar cap fitxer. El build usarà els fitxers locals actuals.');
  }
  // No fallar mai el build per un error de xarxa — permetem builds offline.
  process.exit(0);
})();
