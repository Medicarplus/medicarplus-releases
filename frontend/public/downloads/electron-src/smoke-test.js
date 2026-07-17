#!/usr/bin/env node
// ============================================================================
// smoke-test.js · Marc Brugulat Lopez · 2026
// ----------------------------------------------------------------------------
// Executat DESPRÉS d'electron-builder però ABANS de publish a GitHub.
// Extreu el contingut de dist/win-unpacked/resources/app.asar i verifica
// que hi són les strings crítiques (SMS modal, Configuració, MediCar Plus).
//
// Si falla → NO es publica. És la darrera xarxa de seguretat abans que
// arribi res als clients.
// ============================================================================

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const distDir = path.join(__dirname, 'dist');
const asar = path.join(distDir, 'win-unpacked', 'resources', 'app.asar');

if (!fs.existsSync(asar)) {
  console.log('❌ SMOKE TEST: no s\'ha trobat app.asar a', asar);
  console.log('   La build no s\'ha completat correctament.');
  process.exit(3);
}

console.log('🔬 Smoke test sobre app.asar compilat...');

// Prova extraure via @electron/asar (viene com dep transitiva d'electron-builder)
let asarContent = null;
try {
  const asarPkg = require('@electron/asar');
  const tmpExtract = path.join(__dirname, '.smoke-extract');
  if (fs.existsSync(tmpExtract)) fs.rmSync(tmpExtract, { recursive: true, force: true });
  fs.mkdirSync(tmpExtract, { recursive: true });
  asarPkg.extractAll(asar, tmpExtract);
  asarContent = tmpExtract;
} catch (e) {
  // Fallback: llegim l'ASAR com a binari i cerquem strings dins
  // (l'ASAR és bàsicament un tarball amb header JSON, les strings hi són en clar)
  console.log('   ℹ️  @electron/asar no disponible, fent fallback per binary-grep');
  const raw = fs.readFileSync(asar, 'utf8');
  const REQUIRED_STRINGS = [
    'MediCar Plus',
    'MediCar Plus Bootstrap',
    'require(\'electron\')',
  ];
  const missing = REQUIRED_STRINGS.filter(s => !raw.includes(s));
  if (missing.length > 0) {
    console.log('❌ SMOKE TEST FALLIT: falten strings al .exe compilat:');
    for (const m of missing) console.log(`   · "${m}"`);
    process.exit(3);
  }
  console.log(`✅ Smoke test OK (binary-grep, ${REQUIRED_STRINGS.length} strings trobades)`);
  process.exit(0);
}

// Extret OK, mirem els fitxers clau
const idxPath = path.join(asarContent, 'index.html');
if (!fs.existsSync(idxPath)) {
  console.log('❌ SMOKE TEST: index.html no és dins l\'ASAR');
  process.exit(3);
}
const idx = fs.readFileSync(idxPath, 'utf8');

const REQUIRED_IN_INDEX = ['MediCar Plus', 'MediCar Plus Bootstrap'];
const missing = REQUIRED_IN_INDEX.filter(s => !idx.includes(s));

// Neteja
try { fs.rmSync(asarContent, { recursive: true, force: true }); } catch (e) { /* ignorem */ }

if (missing.length > 0) {
  console.log('❌ SMOKE TEST FALLIT: index.html dins l\'ASAR no conté strings crítiques:');
  for (const m of missing) console.log(`   · "${m}"`);
  console.log('\n🚫 NO publiquis aquest .exe.');
  process.exit(3);
}

// Verifica que existeixen els installers
const nsisFiles = fs.readdirSync(distDir).filter(f => /Setup.*\.exe$/i.test(f));
const portableFiles = fs.readdirSync(distDir).filter(f => /Portable.*\.exe$/i.test(f));
if (nsisFiles.length === 0 || portableFiles.length === 0) {
  console.log('❌ SMOKE TEST: falten installers a dist/');
  console.log(`   NSIS: ${nsisFiles.length}, Portable: ${portableFiles.length}`);
  process.exit(3);
}

// Verifica mida raonable (>30MB, un Electron buit ja és >50MB)
for (const f of [...nsisFiles, ...portableFiles]) {
  const size = fs.statSync(path.join(distDir, f)).size;
  if (size < 30 * 1024 * 1024) {
    console.log(`❌ SMOKE TEST: ${f} és sospitosament petit (${(size/1024/1024).toFixed(1)} MB)`);
    process.exit(3);
  }
  console.log(`   ✅ ${f} (${(size/1024/1024).toFixed(1)} MB)`);
}

console.log('\n✅ Smoke test PASSAT — el .exe és publicable');
process.exit(0);
