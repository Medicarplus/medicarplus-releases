#!/usr/bin/env node
// ============================================================================
// validate-local.js · Marc Brugulat Lopez · 2026
// ----------------------------------------------------------------------------
// Executat ABANS d'electron-builder. Inspecciona els fitxers locals i verifica
// que continguin TOTES les strings crítiques esperades. Si en falta alguna
// (per exemple, s'ha perdut el modal SMS o el modal de Configuració), ATURA
// el procés de build amb exit code 3.
//
// Aquesta és l'última línia de defensa abans de compilar un .exe corrupte.
// ============================================================================

const fs = require('fs');
const path = require('path');

const dir = __dirname;

// Fitxers requerits amb marcadors crítics. La build ATURA si en falta un.
const REQUIRED = {
  'index.html': [
    { marker: '<!doctype html>', why: 'no és un HTML vàlid', ci: true },
    { marker: 'MediCar Plus',    why: 'no és l\'app MediCar Plus' },
    { marker: 'Entradas del día', why: 'falta la secció principal d\'entrades' },
  ],
  'main.js': [
    { marker: "require('electron')", why: 'no és el main.js d\'Electron' },
    { marker: 'BrowserWindow',       why: 'falta la creació de finestra' },
    { marker: 'autoUpdater',         why: 'falta el sistema d\'auto-update' },
  ],
  'preload.js': [
    { marker: 'contextBridge',       why: 'no és un preload d\'Electron' },
  ],
  'package.json': [
    { marker: '"medicar-plus"',      why: 'package.json no és el correcte' },
    { marker: '"electron-updater"',  why: 'falta electron-updater a dependencies' },
  ],
};

let hasError = false;
console.log('🔎 Validant fitxers locals abans de compilar...');

for (const [file, checks] of Object.entries(REQUIRED)) {
  const p = path.join(dir, file);
  if (!fs.existsSync(p)) {
    console.log(`   ❌ ${file} — NO EXISTEIX`);
    hasError = true;
    continue;
  }
  const content = fs.readFileSync(p, 'utf8');
  if (content.length < 100) {
    console.log(`   ❌ ${file} — fitxer sospitosament curt (${content.length}B)`);
    hasError = true;
    continue;
  }
  const missing = [];
  for (const c of checks) {
    const found = c.ci
      ? new RegExp(c.marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i').test(content)
      : content.includes(c.marker);
    if (!found) missing.push(c);
  }
  if (missing.length > 0) {
    console.log(`   ❌ ${file}`);
    for (const m of missing) console.log(`       · falta "${m.marker}" → ${m.why}`);
    hasError = true;
  } else {
    console.log(`   ✅ ${file} — ${checks.length} marcadors OK (${(content.length/1024).toFixed(1)} KB)`);
  }
}

// Verifica version bump-able
try {
  const pkg = JSON.parse(fs.readFileSync(path.join(dir, 'package.json'), 'utf8'));
  if (!/^\d+\.\d+\.\d+$/.test(pkg.version)) {
    console.log(`   ❌ package.json — versió invàlida: "${pkg.version}"`);
    hasError = true;
  } else {
    console.log(`   ✅ package.json version: ${pkg.version}`);
  }
} catch (e) {
  console.log(`   ❌ package.json — no parsejable: ${e.message}`);
  hasError = true;
}

if (hasError) {
  console.log('\n🚫 VALIDACIÓ FALLIDA — la build s\'ha aturat per NO publicar un .exe corrupte.');
  console.log('👉 Executa `npm run sync` per recuperar els fitxers correctes del servidor.');
  process.exit(3);
}

console.log('\n✅ Tots els fitxers locals són vàlids — safe to build');
process.exit(0);
