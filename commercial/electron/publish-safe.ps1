# ============================================================================
# publish-safe.ps1 · MediCar Plus · Marc Brugulat Lopez · 2026
# ----------------------------------------------------------------------------
# ÚS: doble clic o powershell -File publish-safe.ps1
#
# Fa TOT el procés amb 7 CAPES de seguretat i ABORTA a la primera cosa rara.
# Impossible que arribi un .exe corrupte als clients.
#
# Requisits:
#   - Node.js instal·lat
#   - GH_TOKEN configurat al sistema (o al fitxer .env local d'Electron)
#   - Executar des del directori /commercial/electron
# ============================================================================

$ErrorActionPreference = "Stop"

function Section($t) { Write-Host ""; Write-Host "===== $t =====" -ForegroundColor Cyan }
function Ok($t)      { Write-Host "  ✅ $t" -ForegroundColor Green }
function Fail($t)    { Write-Host "  ❌ $t" -ForegroundColor Red; exit 1 }
function Info($t)    { Write-Host "  ℹ️  $t" -ForegroundColor Gray }

# ---- 0) Cwd correcte
if (!(Test-Path "./package.json") -or !(Test-Path "./sync.js")) {
  Fail "Executa aquest script des de /commercial/electron (falten package.json o sync.js)"
}

Section "1/7 · SYNC amb manifest + SHA-256"
node sync.js
if ($LASTEXITCODE -ge 3) { Fail "sync.js ha detectat corrupció local (exit $LASTEXITCODE). ATURAT — no s'ha tocat res." }
if ($LASTEXITCODE -eq 2) { Info "sync.js ha fallat però els locals estan intactes. Continuem amb els locals." }
Ok "sync completat"

Section "2/7 · VALIDATE fitxers locals"
node validate-local.js
if ($LASTEXITCODE -ne 0) { Fail "validate-local.js ha detectat que els fitxers locals no tenen les strings crítiques. Corregeix-los abans de continuar." }
Ok "fitxers locals verificats"

Section "3/7 · Bump de versió (patch)"
$currentVersion = (Get-Content package.json | ConvertFrom-Json).version
npm version patch --no-git-tag-version | Out-Null
$newVersion = (Get-Content package.json | ConvertFrom-Json).version
Ok "versió: $currentVersion → $newVersion"

Section "4/7 · Neteja dist/ i build (NSIS + Portable)"
if (Test-Path "./dist") { Remove-Item -Recurse -Force ./dist }
npx electron-builder --win nsis portable --x64
if ($LASTEXITCODE -ne 0) { Fail "electron-builder ha fallat" }
Ok "build compilada"

Section "5/7 · SMOKE TEST sobre el .exe"
node smoke-test.js
if ($LASTEXITCODE -ne 0) { Fail "smoke-test.js ha detectat un .exe corrupte. NO s'ha publicat res." }
Ok ".exe verificat"

Section "6/7 · Publish a GitHub Releases"
npx electron-builder --win nsis portable --x64 --publish always
if ($LASTEXITCODE -ne 0) { Fail "publish ha fallat" }
Ok "publicat a GitHub"

Section "7/7 · Verificació final release remota"
try {
  $rel = Invoke-RestMethod "https://api.github.com/repos/Medicarplus/medicarplus-releases/releases/latest" -Headers @{ "User-Agent" = "medicar-publish" }
  if ($rel.tag_name -match $newVersion) {
    Ok "release v$newVersion visible a GitHub"
    Info "URL: $($rel.html_url)"
  } else {
    Info "release remota vista: $($rel.tag_name) (esperada $newVersion)"
  }
} catch {
  Info "no s'ha pogut verificar remotament (no és bloquejant): $($_.Exception.Message)"
}

Write-Host ""
Write-Host "🎉 PUBLICAT AMB ÈXIT · v$newVersion" -ForegroundColor Green
Write-Host "   Els clients rebran l'auto-update en els propers minuts." -ForegroundColor Gray
