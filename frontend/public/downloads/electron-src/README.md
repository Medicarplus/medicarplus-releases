# Electron Bootstrap · MediCar Plus

Aquesta carpeta conté els fitxers font per compilar el `.exe` d'escriptori.

## Estructura

- `index.html` — bootstrap loader que carrega dinàmicament `v2.html` del servidor
- `main.js` — procés principal d'Electron
- `preload.js` — bridge segur renderer↔main
- `sync.js` — sincronització dades entre dispositius
- `smoke-test.js`, `validate-local.js` — tests locals de compilació
- `publish-safe.ps1` — script PowerShell per publicar release a GitHub
- `package.json` + `yarn.lock` — dependències (Electron 30.x + electron-builder)
- `assets/icon.ico` — icona de l'app (M+ dourat rounded)
- `assets/icon.png` — versió PNG 256x256

## Compilar el `.exe`

Al Windows / Mac amb Node.js 18+ i yarn instal·lats:

```powershell
cd frontend/public/downloads/electron-src
yarn install       # 5 min · descarrega dependencies (~574 MB)
yarn dist          # 10 min · compila .exe a dist/
```

El fitxer final serà `dist/MediCar Plus Setup 2.0.0.exe` (~120 MB).

## Publicar release a GitHub

Un cop compilat, executa:

```powershell
.\publish-safe.ps1 -Version 2.0.0
```

Això puja el `.exe` al repo `Medicarplus/medicarplus-releases` com a Release nova.
Els clients existents reben la notificació d'actualització automàticament pel bootstrap loader.

## Notes importants

- **NO commitis mai `node_modules/`** — està al `.gitignore`. Ocupa 574 MB i alenteix deploys.
- El `assets/icon.ico` inclou totes les mides (16/24/32/48/64/128/256) generat automàticament amb el nou logo M+ Option 2.
- El bootstrap `index.html` NO cal recompilar-lo per canvis a `v2.html` — l'app agafa la darrera versió del servidor Emergent automàticament cada cop que s'obre.
