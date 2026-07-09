# ============================================================================
# publish-safe.ps1 - MediCar Plus - Marc Brugulat Lopez - 2026
# ----------------------------------------------------------------------------
# US: powershell -File publish-safe.ps1
# Fa TOT el proces amb 7 CAPES i ATURA a la primera cosa rara.
# Impossible que arribi un .exe corrupte als clients.
# ============================================================================

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Section($t) { Write-Host ""; Write-Host "===== $t =====" -ForegroundColor Cyan }
function Ok($t)      { Write-Host "  [OK] $t" -ForegroundColor Green }
function Fail($t)    { Write-Host "  [FAIL] $t" -ForegroundColor Red; exit 1 }
function Info($t)    { Write-Host "  [i] $t" -ForegroundColor Gray }

# ---- 0) Cwd correcte
if (-not (Test-Path "./package.json")) { Fail "No trobo package.json - executa aquest script al directori d Electron" }
if (-not (Test-Path "./sync.js"))      { Fail "No trobo sync.js - executa aquest script al directori d Electron" }

Section "1/7 - SYNC amb manifest + SHA-256"
node sync.js
if ($LASTEXITCODE -ge 3) { Fail "sync.js ha detectat corrupcio local (exit $LASTEXITCODE). ATURAT - no s ha tocat res." }
if ($LASTEXITCODE -eq 2) { Info "sync.js ha fallat pero els locals estan intactes. Continuem." }
Ok "sync completat"

Section "2/7 - VALIDATE fitxers locals"
node validate-local.js
if ($LASTEXITCODE -ne 0) { Fail "validate-local.js ha detectat que els fitxers locals no tenen les strings critiques." }
Ok "fitxers locals verificats"

Section "3/7 - Bump de versio (patch)"
$currentVersion = (Get-Content package.json | ConvertFrom-Json).version
npm version patch --no-git-tag-version | Out-Null
$newVersion = (Get-Content package.json | ConvertFrom-Json).version
Ok "versio: $currentVersion -> $newVersion"

Section "4/7 - Neteja dist/ i build (NSIS + Portable)"
if (Test-Path "./dist") { Remove-Item -Recurse -Force ./dist }
npx electron-builder --win nsis portable --x64
if ($LASTEXITCODE -ne 0) { Fail "electron-builder ha fallat" }
Ok "build compilada"

Section "5/7 - SMOKE TEST sobre el .exe"
node smoke-test.js
if ($LASTEXITCODE -ne 0) { Fail "smoke-test.js ha detectat un .exe corrupte. NO s ha publicat res." }
Ok ".exe verificat"

Section "6/7 - Publish a GitHub Releases"
npx electron-builder --win nsis portable --x64 --publish always
if ($LASTEXITCODE -ne 0) { Fail "publish ha fallat" }
Ok "publicat a GitHub"

Section "7/7 - Verificacio final release remota"
try {
  $rel = Invoke-RestMethod "https://api.github.com/repos/Medicarplus/medicarplus-releases/releases/latest" -Headers @{ "User-Agent" = "medicar-publish" }
  if ($rel.tag_name -match $newVersion) {
    Ok "release v$newVersion visible a GitHub"
    Info "URL: $($rel.html_url)"
  } else {
    Info "release remota vista: $($rel.tag_name) (esperada $newVersion)"
  }
} catch {
  Info ("no s ha pogut verificar remotament (no bloquejant): " + $_.Exception.Message)
}

Write-Host ""
Write-Host "PUBLICAT AMB EXIT - v$newVersion" -ForegroundColor Green
Write-Host "   Els clients rebran l auto-update en els propers minuts." -ForegroundColor Gray
