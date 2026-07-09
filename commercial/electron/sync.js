#!/usr/bin/env node
// ============================================================================
// sync.js — Auto-sincronitza els fitxers font des del servidor
// Marc Brugulat Lopez · 2026
// ----------------------------------------------------------------------------
// Baixa les últimes versions dels fitxers font, VALIDA que el contingut sigui
// realment el fitxer esperat (evita rebre HTML 404 en lloc de codi JS), i
// només l'escriu al disc si la validació passa. Si tots els fitxers fallen,
// deixa els locals intactes.
// ============================================================================

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

// Ordre de prioritat: preview Emergent PRIMER perquè és el que serveix els fitxers font.
// medicarplus.es és GitHub Pages estàtic (no té /downloads/electron-src/).
const SOURCES = [
  'https://project-helper-47.preview.emergentagent.com/downloads/electron-src',
  'https://medicarplus.es/downloads/electron-src'
];

const FILES_1TO1 = ['index.html', 'main.js', 'preload.js', 'sync.js'];
const PKG_MERGE_KEYS = ['scripts', 'build', 'author', 'description', 'main', 'productName'];

// Validacions per assegurar que el contingut és el fitxer real i no una pàgina HTML de 404.
const FILE_SIGNATURES = {
  'index.html': (s) => s.includes('<!DOCTYPE html>') && s.includes('MediCar Plus'),
  'main.js': (s) => !s.startsWith('<!DOCTYPE') && s.includes("require('electron')"),
  'preload.js': (s) => !s.startsWith('<!DOCTYPE') && s.includes('contextBridge'),
  'sync.js': (s) => !s.startsWith('<!DOCTYPE') && s.includes('SOURCES') && s.includes('FILES_1TO1'),
  'package.json': (s) => { try { const j = JSON.parse(s); return !!(j.name && j.version); } catch(e){ return false; } },
};

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
      const validator = FILE_SIGNATURES[fileName];
      if (validator) {
        const text = data.toString('utf8');
        if (!validator(text)) {
          throw new Error('contingut invàlid (probablement HTML 404 en lloc del fitxer real)');
        }
      }
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
      console.log(`⚠️  no disponible (${e.message}) — mantenim la còpia local`);
      failed++;
    }
  }

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

  const distDir = path.join(localDir, 'dist');
  if (rimraf(distDir)) {
    console.log('🧹 dist/ netejat (build fresc garantit)');
  }

  console.log(`\n📦 Resultat: ${updated} actualitzat(s), ${failed} error(s)`);
  process.exit(0);
})();
