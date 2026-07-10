# ============================================================================
# publish-safe.ps1 - MediCar Plus - Marc Brugulat Lopez - 2026
# ----------------------------------------------------------------------------
# US: powershell -File publish-safe.ps1
# Fa TOT el proces en 5 passos. Si qualsevol pas falla, ATURA immediatament.
# Impossible publicar una versio antiga o corrupta.
# ============================================================================

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Step($n, $t) { Write-Host ""; Write-Host "===== $n · $t =====" -ForegroundColor Cyan }
function Ok($t)       { Write-Host "  [OK] $t" -ForegroundColor Green }
function Fail($t)     { Write-Host ""; Write-Host "  [FAIL] $t" -ForegroundColor Red; Write-Host "  Res s ha publicat." -ForegroundColor Red; exit 1 }
function Info($t)     { Write-Host "  [i] $t" -ForegroundColor Gray }

# Directori correcte
if (-not (Test-Path "./package.json") -or -not (Test-Path "./sync.js")) {
  Fail "No trobo package.json o sync.js. Executa aquest script al directori d Electron."
}

# --- 1/5 SYNC ---
# Baixa els fitxers font del servidor. Si ALGUN falla, aturem sense compilar.
# Aixi mai publicarem una versio amb codi antic barrejat.
Step "1/5" "Sync fitxers font (obligatori tot OK)"
node sync.js
if ($LASTEXITCODE -ne 0) { Fail "sync.js no ha pogut baixar tots els fitxers del servidor. NO compilem amb versions barrejades." }
Ok "sync completat"

# --- 2/5 VALIDATE ---
# Comprova que els fitxers locals contenen les strings i IDs critics.
Step "2/5" "Validate fitxers locals"
node validate-local.js
if ($LASTEXITCODE -ne 0) { Fail "Els fitxers locals no tenen les marques esperades." }
Ok "fitxers verificats"

# --- 3/5 BUMP + BUILD ---
Step "3/5" "Bump versio i build"
$currentVersion = (Get-Content package.json | ConvertFrom-Json).version
npm version patch --no-git-tag-version | Out-Null
$newVersion = (Get-Content package.json | ConvertFrom-Json).version
Info "versio: $currentVersion -> $newVersion"

if (Test-Path "./dist") { Remove-Item -Recurse -Force ./dist }
npx electron-builder --win nsis portable --x64
if ($LASTEXITCODE -ne 0) { Fail "electron-builder ha fallat" }
Ok "build compilada"

# --- 4/5 SMOKE TEST ---
# Verifica que el .exe compilat conte les strings critiques.
Step "4/5" "Smoke test sobre el .exe"
node smoke-test.js
if ($LASTEXITCODE -ne 0) { Fail "smoke-test.js ha detectat un .exe incomplet o corrupte." }
Ok ".exe verificat"

# --- 5/5 PUBLISH ---
Step "5/5" "Publish a GitHub Releases"
npx electron-builder --win nsis portable --x64 --publish always
if ($LASTEXITCODE -ne 0) { Fail "publish a GitHub ha fallat" }
Ok "publicat a GitHub"

# Verificacio remota (no bloquejant)
try {
  $rel = Invoke-RestMethod "https://api.github.com/repos/Medicarplus/medicarplus-releases/releases/latest" -Headers @{ "User-Agent" = "medicar-publish" }
  if ($rel.tag_name -match $newVersion) {
    Ok "release v$newVersion visible a GitHub"
    Info ("URL: " + $rel.html_url)
  }
} catch { Info ("no s ha pogut verificar remotament: " + $_.Exception.Message) }

Write-Host ""
Write-Host "PUBLICAT AMB EXIT - v$newVersion" -ForegroundColor Green
Write-Host "Els clients rebran l auto-update en els propers minuts." -ForegroundColor Gray
