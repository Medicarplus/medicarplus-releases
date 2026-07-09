#!/usr/bin/env node
// ============================================================================
// sync.js — Auto-sincronitza els fitxers font des del servidor
// Marc Brugulat Lopez · 2026
// ----------------------------------------------------------------------------
// S'executa automàticament abans de `npm run release`.
//  · Descarrega les últimes versions de index.html, main.js, preload.js
//  · Sincronitza el `build` config de package.json (però preserva la versió local)
//  · S'auto-actualitza (sync.js baixa la seva pròpia última versió)
//  · Neteja el cache de dist/ per evitar builds amb fitxers cachejats
// Si no hi ha internet, usa els fitxers locals sense fallar.
// ============================================================================

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

const SOURCES = [
  'https://medicarplus.es/downloads/electron-src',
  'https://project-helper-47.preview.emergentagent.com/downloads/electron-src'
];

// Fitxers que se sincronitzen 1:1 des del servidor
const FILES_1TO1 = ['index.html', 'main.js', 'preload.js', 'sync.js'];

// package.json se sincronitza intel·ligentment (preserva version, sync build config)
const PKG_MERGE_KEYS = ['scripts', 'build', 'author', 'description', 'main', 'productName'];

function download(url, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    const req = client.get(url, { timeout: timeoutMs }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return resolve(download(res.headers.location, timeoutMs));
      }
      if (res.statusCode !== 200) return reject(new Error(`HTTP ${res.statusCode}`));
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
      if (data.length < 50) throw new Error(`resposta massa curta (${data.length}B)`);
      return { data, url };
    } catch (e) { lastErr = e; }
  }
  throw lastErr || new Error('cap font disponible');
}

function rimraf(dir) {
  try {
    if (fs.existsSync(dir)) {
      fs.rmSync(dir, { recursive: true, force: true });
      return true;
    }
  } catch (e) {}
  return false;
}

(async () => {
  console.log('🔄 Sincronitzant fitxers font des del servidor...');
  const localDir = __dirname;
  let updated = 0, failed = 0;

  // 1) Sync de fitxers 1:1
  for (const f of FILES_1TO1) {
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
      console.log(`⚠️  no disponible (${e.message})`);
      failed++;
    }
  }

  // 2) Sync intel·ligent de package.json (preserva version)
  process.stdout.write(`   · package.json (build config) ... `);
  try {
    const { data } = await tryDownloadFile('package.json');
    const remotePkg = JSON.parse(data.toString('utf8'));
    const localPath = path.join(localDir, 'package.json');
    const localPkg = JSON.parse(fs.readFileSync(localPath, 'utf8'));
    let changed = false;
    for (const k of PKG_MERGE_KEYS) {
      if (JSON.stringify(remotePkg[k]) !== JSON.stringify(localPkg[k])) {
        localPkg[k] = remotePkg[k];
        changed = true;
      }
    }
    // Preservem: version, dependencies (perquè node_modules no es trenqui)
    if (changed) {
      fs.writeFileSync(localPath, JSON.stringify(localPkg, null, 2) + '\n');
      console.log('✅ build config actualitzada (version preservada)');
      updated++;
    } else {
      console.log('✔️  ja al dia');
    }
  } catch (e) {
    console.log(`⚠️  no disponible (${e.message})`);
    failed++;
  }

  // 3) Neteja cache de builds anteriors per garantir build net
  const distDir = path.join(localDir, 'dist');
  if (rimraf(distDir)) {
    console.log('🧹 dist/ netejat (build fresc garantit)');
  }

  console.log(`\n📦 Resultat: ${updated} actualitzat(s), ${failed} error(s)`);
  process.exit(0);
})();
