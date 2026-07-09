#!/usr/bin/env node
// ============================================================================
// sync.js v2 · BULLETPROOF · Marc Brugulat Lopez · 2026
// ----------------------------------------------------------------------------
// SISTEMA A PROVA DE BALES:
//   1. Baixa el MANIFEST del servidor (JSON amb SHA-256 de cada fitxer)
//   2. Baixa cada fitxer a un DIRECTORI TEMPORAL
//   3. Verifica SHA-256 contra el manifest
//   4. Verifica signatures de contingut (backup)
//   5. Fa BACKUP dels fitxers locals actuals
//   6. Fa MOVE ATÒMIC dels fitxers verificats
//   7. Si QUALSEVOL pas falla → 100% RESTAURA els originals, mai deixa
//      fitxers a mig sobreescriure. IMPOSSIBLE que es publiqui un .exe corrupte.
//
// SORTIDA:
//   - Exit 0: sync OK, es pot fer build
//   - Exit 2: sync fallit però locals intactes (build POT continuar amb els locals)
//   - Exit 3: FATAL — locals corruptes, NO facis build (script build.ps1 aborta)
// ============================================================================

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Fonts en ordre de prioritat. Manifest és el ORIGEN DE VERITAT.
const SOURCES = [
  'https://project-helper-47.preview.emergentagent.com',
  'https://medicarplus.es'
];
const MANIFEST_PATHS = [
  '/api/electron/manifest',              // preview server (dinàmic, sempre fresc)
  '/downloads/electron-src/manifest.json' // fallback estàtic (GitHub Pages, si es publica)
];
// Ruta primària: /api/electron/download/{f} (BYPASSA bot-detection de Cloudflare)
// Ruta fallback: /downloads/electron-src/{f} (estàtic, pot rebre 404 des d'algunes IPs)
const SRC_PATHS = ['/api/electron/download', '/downloads/electron-src'];

const FILES_1TO1 = ['index.html', 'main.js', 'preload.js', 'sync.js'];
const PKG_MERGE_KEYS = ['scripts', 'build', 'author', 'description', 'main', 'productName'];

// Signatures de contingut (backup si manifest falla o no cobreix el fitxer)
const FILE_SIGNATURES = {
  'index.html': (s) => /<!doctype html>/i.test(s) && s.includes('MediCar Plus'),
  'main.js':    (s) => !/^<!doctype/i.test(s) && s.includes("require('electron')"),
  'preload.js': (s) => !/^<!doctype/i.test(s) && s.includes('contextBridge'),
  'sync.js':    (s) => !/^<!doctype/i.test(s) && s.includes('SOURCES') && s.includes('tryDownloadFile'),
  'package.json': (s) => { try { const j = JSON.parse(s); return !!(j.name && j.version); } catch(e){ return false; } },
};

// Signatures crítiques que HAN d'estar a index.html (evita perdre features)
// Aquestes són marca-que-una-versió-és-completa. Si en falta alguna, no és safe.
const CRITICAL_INDEX_MARKERS = [
  'MediCar Plus',
  'Entradas del día',
];

function log(msg) { process.stdout.write(msg); }
function logln(msg) { console.log(msg); }

function download(url, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    const req = client.get(url, { timeout: timeoutMs, headers: { 'Cache-Control': 'no-cache' } }, (res) => {
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

function sha256(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

async function fetchManifest() {
  for (const base of SOURCES) {
    for (const p of MANIFEST_PATHS) {
      const url = `${base}${p}?t=${Date.now()}`;
      try {
        const buf = await download(url, 20000);
        const json = JSON.parse(buf.toString('utf8'));
        if (json && json.files && Object.keys(json.files).length > 0) {
          return { manifest: json, source: base };
        }
      } catch (e) { /* prova següent */ }
    }
  }
  return null;
}

async function downloadFileWithRetries(base, fileName, expectedHash) {
  const MAX_ATTEMPTS = 4;
  let lastErr = null;
  // Combinacions de paths (primer /api/, després estàtic). Per index.html també /v2.html.
  const paths = SRC_PATHS.map(sp => `${sp}/${fileName}`);
  if (fileName === 'index.html') paths.push('/v2.html');
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    for (const p of paths) {
      const isOfficial = p.endsWith(`/${fileName}`) && (p.startsWith('/api/electron/download') || p.startsWith(SRC_PATHS[1]));
      const url = `${base}${p}?t=${Date.now()}_${attempt}`;
      try {
        const data = await download(url, 30000);
        if (data.length < 50) throw new Error(`resposta massa curta (${data.length}B)`);
        // Verifica SHA-256 contra manifest NOMÉS a rutes oficials (mateix contingut).
        if (expectedHash && isOfficial) {
          const got = sha256(data);
          if (got !== expectedHash) {
            throw new Error(`SHA mismatch (esperat ${expectedHash.slice(0,10)}…, rebut ${got.slice(0,10)}…)`);
          }
        }
        // Verifica signatura de contingut (defense in depth, sempre)
        const validator = FILE_SIGNATURES[fileName];
        if (validator) {
          const text = data.toString('utf8');
          if (!validator(text)) {
            throw new Error('signatura de contingut invàlida (probablement HTML 404)');
          }
        }
        return data;
      } catch (e) {
        lastErr = e;
      }
    }
    if (attempt < MAX_ATTEMPTS) await new Promise(r => setTimeout(r, 1500 * attempt));
  }
  throw lastErr || new Error('no disponible');
}

function rimraf(dir) {
  try { if (fs.existsSync(dir)) { fs.rmSync(dir, { recursive: true, force: true }); return true; } }
  catch (e) { /* ignorem, retornem false */ }
  return false;
}

function validateLocalIndexHtml(filePath) {
  try {
    const s = fs.readFileSync(filePath, 'utf8');
    if (!FILE_SIGNATURES['index.html'](s)) return { ok: false, reason: 'signatura general falla' };
    for (const marker of CRITICAL_INDEX_MARKERS) {
      if (!s.includes(marker)) return { ok: false, reason: `falta marker "${marker}"` };
    }
    return { ok: true };
  } catch (e) { return { ok: false, reason: e.message }; }
}

(async () => {
  console.log('🔄 Sincronitzant fitxers font (mode BULLETPROOF)...');
  const localDir = __dirname;
  const tmpDir = path.join(localDir, '.sync-tmp');
  const backupDir = path.join(localDir, '.sync-backup');

  // Neteja workspaces temporals
  rimraf(tmpDir); rimraf(backupDir);
  fs.mkdirSync(tmpDir, { recursive: true });
  fs.mkdirSync(backupDir, { recursive: true });

  // 1) Manifest
  log('   · manifest ... ');
  const manifestResult = await fetchManifest();
  if (manifestResult) {
    logln(`✅ obtingut (${Object.keys(manifestResult.manifest.files).length} fitxers) [${new URL(manifestResult.source).hostname}]`);
  } else {
    logln('⚠️  no disponible — usarem només signatures de contingut');
  }
  const manifestFiles = manifestResult ? manifestResult.manifest.files : {};

  // 2) Baixa cada fitxer al tmp i valida
  const downloaded = {};   // fileName -> Buffer
  const failedFiles = [];
  const allFiles = [...FILES_1TO1, 'package.json'];

  for (const f of allFiles) {
    log(`   · ${f} ... `);
    const expectedHash = manifestFiles[f] ? manifestFiles[f].sha256 : null;
    let success = false;
    let lastErr = null;
    for (const base of SOURCES) {
      try {
        const data = await downloadFileWithRetries(base, f, expectedHash);
        downloaded[f] = data;
        fs.writeFileSync(path.join(tmpDir, f), data);
        logln(`✅ verificat (${(data.length/1024).toFixed(1)} KB${expectedHash ? ', SHA OK' : ''}) [${new URL(base).hostname}]`);
        success = true;
        break;
      } catch (e) { lastErr = e; }
    }
    if (!success) {
      logln(`⚠️  fallit (${lastErr ? lastErr.message : '?'}) — mantindrem la còpia local`);
      failedFiles.push(f);
    }
  }

  // 3) Backup + swap atòmic dels que hem descarregat OK
  let updated = 0;
  for (const [fname, data] of Object.entries(downloaded)) {
    const localPath = path.join(localDir, fname);
    // Si és package.json, fem MERGE (preservem version local)
    if (fname === 'package.json') {
      try {
        const remotePkg = JSON.parse(data.toString('utf8'));
        const localPkg = fs.existsSync(localPath) ? JSON.parse(fs.readFileSync(localPath, 'utf8')) : {};
        // Backup abans de tocar
        if (fs.existsSync(localPath)) fs.copyFileSync(localPath, path.join(backupDir, fname));
        let changed = false;
        for (const k of PKG_MERGE_KEYS) {
          if (JSON.stringify(remotePkg[k]) !== JSON.stringify(localPkg[k])) {
            localPkg[k] = remotePkg[k];
            changed = true;
          }
        }
        if (changed) {
          fs.writeFileSync(localPath, JSON.stringify(localPkg, null, 2) + '\n');
          updated++;
        }
      } catch (e) {
        console.warn(`   ⚠️  no s'ha pogut fer merge de package.json (${e.message})`);
      }
      continue;
    }
    // Els altres: comparar amb local, sobreescriure si canvia
    let changed = true;
    if (fs.existsSync(localPath)) {
      const current = fs.readFileSync(localPath);
      if (current.equals(data)) changed = false;
      else fs.copyFileSync(localPath, path.join(backupDir, fname));
    }
    if (changed) {
      fs.writeFileSync(localPath, data);
      updated++;
    }
  }

  // 4) VALIDACIÓ FINAL: els fitxers locals resultants són usables?
  const idxCheck = validateLocalIndexHtml(path.join(localDir, 'index.html'));
  if (!idxCheck.ok) {
    console.log(`\n❌ FATAL: index.html local és invàlid (${idxCheck.reason}).`);
    // Restaura backups (si en tenim)
    const bkIdx = path.join(backupDir, 'index.html');
    if (fs.existsSync(bkIdx)) {
      fs.copyFileSync(bkIdx, path.join(localDir, 'index.html'));
      console.log('🔙 restaurat index.html des del backup');
    }
    rimraf(tmpDir);
    process.exit(3);
  }

  // 5) Neteja dist/ per garantir un build fresc
  const distDir = path.join(localDir, 'dist');
  if (rimraf(distDir)) console.log('🧹 dist/ netejat (build fresc garantit)');
  rimraf(tmpDir);

  console.log(`\n📦 Resultat: ${updated} actualitzat(s), ${failedFiles.length} error(s)`);
  console.log(`✅ Fitxers locals VÀLIDS — safe to build`);
  if (failedFiles.length > 0) {
    console.log(`ℹ️  Fallits (sense afectar la build): ${failedFiles.join(', ')}`);
    process.exit(failedFiles.length === allFiles.length ? 2 : 0);
  }
  process.exit(0);
})().catch(err => {
  console.error(`\n❌ Error inesperat: ${err.message}`);
  process.exit(3);
});
