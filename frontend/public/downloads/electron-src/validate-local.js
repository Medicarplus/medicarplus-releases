#!/usr/bin/env node
// ============================================================================
// validate-local.js · Marc Brugulat Lopez · 2026
// ----------------------------------------------------------------------------
// Verifica que els fitxers locals continguin les strings i IDs crítics ABANS
// de compilar el .exe. Si en falta un → ATURA amb exit 3.
//
// Aquesta és la darrera línia de defensa entre "sync ha acabat" i "compila".
// ============================================================================

const fs = require('fs');
const path = require('path');

const dir = __dirname;

// Fitxers requerits i les strings/IDs que HAN de contenir.
// Si en falta cap, la build s'atura per NO publicar una app trencada.
const REQUIRED = {
  'index.html': [
    '<!doctype html>',        // HTML vàlid
    'MediCar Plus',           // Marca correcta
    'Entradas del día',       // Secció principal
    'id="appTitle"',          // Header renderitzat
    'id="mainTabs"',          // Sistema de pestanyes
    'id="btn-settings"',      // Botó Configuració
    'id="btn-import-csv"',    // Botó Importar CSV
    'id="btn-sms-new"',       // Botó SMS
  ],
  'main.js': [
    "require('electron')",
    'BrowserWindow',
    'autoUpdater',
    'checkForUpdates',
  ],
  'preload.js': [
    'contextBridge',
  ],
  'package.json': [
    '"medicar-plus"',
    '"electron-updater"',
    '"electron-builder"',
  ],
};

let hasError = false;
console.log('Validant fitxers locals abans de compilar...');

for (const [file, markers] of Object.entries(REQUIRED)) {
  const p = path.join(dir, file);
  if (!fs.existsSync(p)) {
    console.log(`  ${file}: NO EXISTEIX`);
    hasError = true;
    continue;
  }
  const content = fs.readFileSync(p, 'utf8');
  if (content.length < 100) {
    console.log(`  ${file}: fitxer sospitosament curt (${content.length}B)`);
    hasError = true;
    continue;
  }
  const missing = markers.filter(m => !content.includes(m));
  if (missing.length > 0) {
    console.log(`  ${file}: FALTEN ${missing.length} marcador(s)`);
    for (const m of missing) console.log(`    - "${m}"`);
    hasError = true;
  } else {
    console.log(`  ${file}: OK (${markers.length} marcadors, ${(content.length / 1024).toFixed(1)} KB)`);
  }
}

// Validació addicional: la versió del package.json ha de ser semver
try {
  const pkg = JSON.parse(fs.readFileSync(path.join(dir, 'package.json'), 'utf8'));
  if (!/^\d+\.\d+\.\d+$/.test(pkg.version)) {
    console.log(`  package.json: versió no vàlida "${pkg.version}"`);
    hasError = true;
  } else {
    console.log(`  package.json: version ${pkg.version} OK`);
  }
} catch (e) {
  console.log(`  package.json: no parsejable (${e.message})`);
  hasError = true;
}

if (hasError) {
  console.log('\nVALIDACIO FALLIDA — no compilem per no publicar una versio trencada.');
  console.log('Executa "npm run sync" per baixar les versions correctes.');
  process.exit(3);
}

console.log('\nTots els fitxers son valids — safe to build.');
process.exit(0);
