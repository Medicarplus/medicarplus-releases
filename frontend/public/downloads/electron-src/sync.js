#!/usr/bin/env node
// ============================================================================
// sync.js · Marc Brugulat Lopez · 2026 · SENZILL i ROBUST
// ----------------------------------------------------------------------------
// UNA sola responsabilitat: baixar els fitxers font del servidor i validar
// que tenen contingut real (no HTML 404). Si no pot, ATURA el build.
//
// DISCOVERY (nou · MAI URL VELLA):
//   1) Consulta raw.githubusercontent.com/Medicarplus/medicarplus-releases/main/api-endpoint.json
//      (font canònica auto-publicada pel backend a cada arrencada)
//   2) Si falla → consulta cdn.jsdelivr.net com a mirror del mateix repo
//   3) Si falla → consulta api.github.com/repos/.../contents/api-endpoint.json (té permisos read-only sense token)
//   4) Si TOTS 3 fallen → mira al fitxer local `.last-known-server.json` (última URL descoberta que va funcionar)
//   5) Si tampoc → FAIL i ATURA. NO fem servir mai una URL hardcoded obsoleta.
//
// Reglas:
//   1) Un User-Agent de browser real (Cloudflare no bloqueja)
//   2) 3 reintents per fitxer amb backoff exponencial
//   3) Validació de contingut estricta (signatures)
//   4) Si algun fitxer clau falla → exit code 3 (build ATURAT)
//
// Exit codes:
//   0 = tot OK, safe to build
//   3 = fitxer(s) crític(s) fallits o discovery totalment fallit, NO facis build
// ============================================================================

const https = require('https');
const fs = require('fs');
const path = require('path');

const DISCOVERY_SOURCES = [
  'https://raw.githubusercontent.com/Medicarplus/medicarplus-releases/main/api-endpoint.json',
  'https://cdn.jsdelivr.net/gh/Medicarplus/medicarplus-releases@main/api-endpoint.json',
  'https://api.github.com/repos/Medicarplus/medicarplus-releases/contents/api-endpoint.json',
];
const LAST_KNOWN_FILE = path.join(__dirname, '.last-known-server.json');
let SERVER = null; // s'omple SEMPRE per discovery, mai hardcoded
const FILES = ['index.html', 'main.js', 'preload.js', 'package.json'];

const SIGNATURES = {
  'index.html':   ['<!doctype html>', 'MediCar Plus', 'Entradas del día'],
  'main.js':      ["require('electron')", 'BrowserWindow', 'autoUpdater'],
  'preload.js':   ['contextBridge'],
  'package.json': ['medicar-plus', 'electron-updater'],
};

function fetch(url, extraHeaders) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      timeout: 12000,
      headers: Object.assign({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
      }, extraHeaders || {}),
    }, (res) => {
      if (res.statusCode !== 200) return reject(new Error(`HTTP ${res.statusCode}`));
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => resolve(Buffer.concat(chunks)));
      res.on('error', reject);
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
  });
}

function parseApiEndpointResponse(url, buf) {
  const txt = buf.toString('utf8');
  let j;
  try { j = JSON.parse(txt); } catch (e) { throw new Error('json invalid'); }
  // Format A: {api: "..."} (raw.githubusercontent, jsdelivr)
  if (j && j.api && /^https?:\/\//.test(j.api)) return j.api.replace(/\/+$/, '');
  // Format B: {content: "base64..."} (api.github.com/repos/.../contents/)
  if (j && j.content && j.encoding === 'base64') {
    try {
      const decoded = Buffer.from(j.content, 'base64').toString('utf8');
      const inner = JSON.parse(decoded);
      if (inner && inner.api && /^https?:\/\//.test(inner.api)) return inner.api.replace(/\/+$/, '');
    } catch (e) { throw new Error('base64 decode failed'); }
  }
  throw new Error('no api field');
}

async function discoverServer() {
  // 1) Prova cada font de discovery en ordre (2 intents cada una amb backoff)
  for (let i = 0; i < DISCOVERY_SOURCES.length; i++) {
    const src = DISCOVERY_SOURCES[i];
    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        const url = src + (src.includes('?') ? '&' : '?') + 't=' + Date.now();
        const buf = await fetch(url);
        const api = parseApiEndpointResponse(src, buf);
        // Verifica que la URL descoberta respon (evita URL "publicada" per un backend caigut)
        await fetch(api + '/api/electron/download/package.json?t=' + Date.now());
        console.log(`  Descobert backend via font ${i+1}: ${api}`);
        try { fs.writeFileSync(LAST_KNOWN_FILE, JSON.stringify({api, discoveredAt: new Date().toISOString(), source: src}, null, 2)); } catch (e) {}
        return api;
      } catch (e) {
        if (attempt === 2) console.log(`  Font ${i+1} FAIL (${e.message})`);
        await new Promise(r => setTimeout(r, 500 * attempt));
      }
    }
  }
  // 2) Última opció: URL cachada localment de discovery anterior
  try {
    if (fs.existsSync(LAST_KNOWN_FILE)) {
      const cached = JSON.parse(fs.readFileSync(LAST_KNOWN_FILE, 'utf8'));
      if (cached && cached.api) {
        // Verifica que respon abans de fer-la servir
        await fetch(cached.api + '/api/electron/download/package.json?t=' + Date.now());
        console.log(`  ⚠️  Discovery online FAIL · usant última URL cachada: ${cached.api} (discovered ${cached.discoveredAt})`);
        return cached.api.replace(/\/+$/, '');
      }
    }
  } catch (e) {
    console.log(`  Cache local també FAIL (${e.message})`);
  }
  return null;
}

async function download(fileName) {
  const url = `${SERVER}/api/electron/download/${fileName}?t=${Date.now()}`;
  const MAX = 3;
  let lastErr = null;
  for (let i = 1; i <= MAX; i++) {
    try {
      const buf = await fetch(url);
      // Validació content-based
      const text = buf.toString('utf8');
      const sigs = SIGNATURES[fileName] || [];
      const missing = sigs.filter(s => !text.includes(s));
      if (missing.length > 0) throw new Error(`content check fail: missing "${missing[0]}"`);
      return buf;
    } catch (e) {
      lastErr = e;
      if (i < MAX) await new Promise(r => setTimeout(r, 800 * i));
    }
  }
  throw lastErr;
}

(async () => {
  console.log('Sincronitzant fitxers font...');
  SERVER = await discoverServer();
  if (!SERVER) {
    console.error('\n❌ DISCOVERY TOTALMENT FALLIT.');
    console.error('   No s\'ha pogut obtenir cap URL vàlida ni de GitHub ni de cache local.');
    console.error('   Comprova la connexió a Internet i que Medicarplus/medicarplus-releases està accessible.');
    console.error('   NO fem servir mai una URL vella hardcoded — build ATURAT per seguretat.');
    process.exit(3);
  }
  const localDir = __dirname;
  let updated = 0, failed = [];

  for (const f of FILES) {
    process.stdout.write(`  ${f} ... `);
    try {
      const data = await download(f);
      const localPath = path.join(localDir, f);

      if (f === 'package.json') {
        try {
          const remote = JSON.parse(data.toString('utf8'));
          const local  = fs.existsSync(localPath) ? JSON.parse(fs.readFileSync(localPath, 'utf8')) : {};
          const KEYS = ['scripts', 'build', 'dependencies', 'devDependencies', 'author', 'description', 'main', 'productName'];
          let changed = false;
          for (const k of KEYS) {
            if (JSON.stringify(remote[k]) !== JSON.stringify(local[k])) {
              local[k] = remote[k];
              changed = true;
            }
          }
          if (changed) {
            fs.writeFileSync(localPath, JSON.stringify(local, null, 2) + '\n');
            console.log(`OK (config merge, version preservada)`);
            updated++;
          } else {
            console.log('OK (ja al dia)');
          }
        } catch (e) {
          console.log(`ERROR merge (${e.message})`);
          failed.push(f);
        }
      } else {
        let changed = true;
        if (fs.existsSync(localPath)) {
          const current = fs.readFileSync(localPath);
          if (current.equals(data)) changed = false;
        }
        if (changed) {
          fs.writeFileSync(localPath, data);
          console.log(`OK actualitzat (${(data.length / 1024).toFixed(1)} KB)`);
          updated++;
        } else {
          console.log('OK (ja al dia)');
        }
      }
    } catch (e) {
      console.log(`FAIL (${e.message})`);
      failed.push(f);
    }
  }

  // Neteja dist/ per garantir build fresc
  const distDir = path.join(localDir, 'dist');
  if (fs.existsSync(distDir)) {
    fs.rmSync(distDir, { recursive: true, force: true });
  }

  console.log(`\nResultat: ${updated} actualitzat(s), ${failed.length} error(s)`);

  if (failed.length > 0) {
    console.log(`\nERROR: no s'han pogut baixar aquests fitxers: ${failed.join(', ')}`);
    console.log('NO facis build amb versions barrejades. Espera 30s i torna a intentar.');
    process.exit(3);
  }
  console.log('Safe to build.');
  process.exit(0);
})().catch(err => {
  console.error(`\nError inesperat: ${err.message}`);
  process.exit(3);
});
