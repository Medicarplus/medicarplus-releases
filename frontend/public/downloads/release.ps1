# ============================================================================
# release.ps1 — Publicar nova versió de MediCar Plus (comanda única)
# Marc Brugulat Lopez · 2026
# ----------------------------------------------------------------------------
# Uso:
#   irm https://project-helper-47.preview.emergentagent.com/downloads/release.ps1 | iex
#
# Aquest script fa TOT automàticament:
#   1. Descarrega l'ultima versio del zip amb tots els fitxers font
#   2. L'extreu a C:\medicarplus\ (sobreescrivint el que hi ha)
#   3. Instal.la dependencies (yarn install) si cal
#   4. Executa `npm run release` -> compila i publica a GitHub
#   5. Mostra el link directe per baixar el .exe recent
# ============================================================================

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Config
$ZIP_URL   = "https://project-helper-47.preview.emergentagent.com/downloads/medicar-plus-electron.zip"
$BASE_DIR  = "C:\medicarplus"
$WORK_DIR  = "$BASE_DIR\electron"
$ZIP_FILE  = "$env:TEMP\medicar-plus-electron.zip"
$GH_TOKEN  = "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"

function Section($msg) {
  Write-Host ""
  Write-Host "============================================================" -ForegroundColor Cyan
  Write-Host " $msg" -ForegroundColor Cyan
  Write-Host "============================================================" -ForegroundColor Cyan
}

function Ok($msg)    { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Info($msg)  { Write-Host "  ...  $msg" -ForegroundColor Gray }
function Warn($msg)  { Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Fail($msg)  { Write-Host "  [X]  $msg" -ForegroundColor Red; exit 1 }

try {
  Section "MediCar Plus - Release Automatic"

  # --- 1. Neteja processos ---
  Section "1/5  Tancant instancies obertes"
  Get-Process | Where-Object { $_.ProcessName -like "*MediCar*" -or $_.ProcessName -like "*electron*" } | Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 1
  Ok "Processos aturats"

  # --- 2. Descarrega zip ---
  Section "2/5  Descarregant fitxers font"
  Info "URL: $ZIP_URL"
  Invoke-WebRequest -Uri $ZIP_URL -OutFile $ZIP_FILE -UseBasicParsing
  $size = (Get-Item $ZIP_FILE).Length
  Ok "Descarregat ($([math]::Round($size/1KB)) KB)"

  # --- 3. Extreu (preservant dist/ i node_modules) ---
  Section "3/5  Actualitzant C:\medicarplus\electron\"
  if (-not (Test-Path $BASE_DIR)) { New-Item -ItemType Directory -Path $BASE_DIR | Out-Null }
  # Netejem dist per evitar cache
  if (Test-Path "$WORK_DIR\dist") {
    Remove-Item -Recurse -Force "$WORK_DIR\dist"
    Info "dist/ netejat"
  }
  Expand-Archive -Force -Path $ZIP_FILE -DestinationPath $BASE_DIR
  Ok "Fitxers extrets a $WORK_DIR"

  # Verifica sync.js
  $syncSize = (Get-Item "$WORK_DIR\sync.js").Length
  Info "sync.js: $syncSize bytes"
  if ($syncSize -lt 4000) {
    Warn "sync.js sembla vell (esperat > 4KB). Servidor pot estar servint versio antiga."
  }

  # --- 4. Instal.la dependencies si cal ---
  Section "4/5  Verificant dependencies"
  Push-Location $WORK_DIR
  try {
    if (-not (Test-Path "node_modules")) {
      Info "node_modules no existeix, executant npm install..."
      npm install --no-audit --no-fund
      if ($LASTEXITCODE -ne 0) { Fail "npm install ha fallat" }
    } else {
      Ok "node_modules ja existeix"
    }

    # --- 5. Release ---
    Section "5/5  Compilant i publicant a GitHub"
    $env:GH_TOKEN = $GH_TOKEN
    npm run release
    if ($LASTEXITCODE -ne 0) { Fail "npm run release ha fallat (codi $LASTEXITCODE)" }

  } finally {
    Pop-Location
  }

  # --- Final ---
  Section "FET!"
  $pkg = Get-Content "$WORK_DIR\package.json" | ConvertFrom-Json
  $ver = $pkg.version
  Write-Host "  Versio publicada: v$ver" -ForegroundColor Green
  Write-Host "  Release GitHub: https://github.com/Medicarplus/medicarplus-releases/releases/tag/v$ver" -ForegroundColor Green
  Write-Host ""
  Write-Host "  Instal.lador (Setup): https://github.com/Medicarplus/medicarplus-releases/releases/download/v$ver/MediCar-Plus-Setup-$ver.exe" -ForegroundColor White
  Write-Host "  Portable:             https://github.com/Medicarplus/medicarplus-releases/releases/download/v$ver/MediCarPlus-Portable-$ver.exe" -ForegroundColor White
  Write-Host ""
  Write-Host "  Els clients rebran l'auto-update proximament (repo public + electron-updater)" -ForegroundColor Cyan
  Write-Host ""

} catch {
  Fail "Error: $_"
}
