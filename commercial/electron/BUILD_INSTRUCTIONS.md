# 📦 Empaquetar Caja del Día com aplicació Windows (.exe)

**Marc Brugulat Lopez** · Juliol 2026

Aquesta guia t'explica com convertir el projecte HTML en una aplicació nativa de Windows (.exe) que:
- S'obre com una app normal (icona al desktop, menú d'inici, no depèn de Chrome)
- Bloqueja DevTools i tecles d'inspecció
- Mostra el sistema de llicències en obrir
- Guarda dades a `localStorage` d'Electron (persistent, ni s'esborra amb Ctrl+H)

---

## 📥 Requisits previs (fer una sola vegada al teu PC Windows)

1. **Instal·la Node.js LTS**: https://nodejs.org/ (versió 20 o superior)
2. Comprova la instal·lació obrint `cmd`:
   ```bash
   node --version
   npm --version
   ```

---

## 🚀 Passos per generar el .exe

### 1. Descarrega la carpeta `electron/` sencera
Copia tot el contingut de `/app/commercial/electron/` al teu PC Windows. Estructura mínima:

```
electron/
├── package.json          ← config general
├── main.js               ← procés principal Electron
├── preload.js            ← script de seguretat
├── index.html            ← la teva app (còpia del v2.html)
├── LICENSE.txt           ← llicència comercial
└── assets/
    └── icon.ico          ← IMPORTANT: crear-lo, veure sota
```

### 2. Crea la icona `assets/icon.ico`

Windows necessita una icona `.ico` de 256×256 píxels.

**Opcions gratuïtes**:
- Fes-la a mà amb GIMP o Photoshop i exporta a `.ico`
- Genera-la online: https://convertio.co/es/png-ico/ (puja una PNG quadrada de 512×512)
- Usa la icona predeterminada d'Electron (esborra la referència `icon` del `package.json`)

Suggeriment de disseny: fons blau fosc + "€" o "CD" en groc daurat (colors app).

### 3. Obre el terminal a la carpeta `electron/`
```bash
cd C:\ruta\a\electron
```

### 3.5. (opcional però recomanat) ⚡ Regenera l'HTML obfuscat (Fase 7)

Abans del primer build, o cada cop que canviïs la lògica de llicència, torna a **obfuscar el JavaScript**. Això reemplaça `electron/index.html` amb la versió amb:

- `MB-MASTER-BRUGULAT-2026-OWNER` **invisible** amb Ctrl+F
- `VERIFY_URL` amagada al string array (no es pot llegir directament)
- Signatura anti-tampering (`selfDefending: true`): si algú beautifica el codi, entra en bucle infinit
- Noms de variables i paràmetres substituïts per `_0xNNNNNN`

**Com executar-ho (a la teva màquina Linux/dev, NO al Windows del client):**
```bash
cd /app/commercial/build
yarn install        # només el primer cop (~5s)
node obfuscate.js   # llegeix v2.html, escriu commercial/electron/index.html
```

Sortida típica:
```
[obfuscate] Reading   : /app/frontend/public/v2.html
[obfuscate] Block 1: 156021 → 407439 chars (2.01s)
[obfuscate] Wrote     : /app/commercial/electron/index.html
[obfuscate] JS size   : 153.4 KB → 398.2 KB (260%)
```

L'HTML obfuscat continua tenint TOTA la funcionalitat idèntica: MASTER key, JWT, re-check online, etc. Només que ara costa molt més fer reverse-engineering. **Aquest és el fitxer que has de copiar al PC Windows abans de fer `npm run build`.**

> **NOTA**: si estàs iterant a `v2.html` (dev), executa `node obfuscate.js` DESPRÉS de cada canvi per mantenir sincronitzat l'HTML de l'Electron. Si oblides d'obfuscar, la copia a `electron/index.html` quedarà desactualitzada. La font de veritat per dev és sempre `/app/frontend/public/v2.html`.

### 4. Instal·la dependències
```bash
npm install
```
(triga 2-3 minuts, descarrega Electron ~200 MB)

### 5. Prova l'app abans d'empaquetar
```bash
npm start
```
Ha d'obrir-se una finestra amb el modal d'activació de llicència. Introdueix la Master Key i verifica que tot funciona.

### 6. Genera l'instal·lador `.exe`
```bash
npm run build
```
Trigarà 3-5 minuts. Al final trobaràs a la carpeta `dist/`:
- **`Caja del Día Setup 2.0.0.exe`** → instal·lador NSIS (recomanat per clients)
- **`CajaDelDia-Portable-2.0.0.exe`** → versió portable (no cal instal·lar)

### 7. Prova l'instal·lador
Doble-clic al `.exe`, segueix l'assistent, i comprova que:
- Es crea l'accés directe al desktop
- Apareix a "Programes i característiques"
- L'app s'obre correctament
- El modal de llicència no es pot saltar
- **F12 no obre DevTools** (comprovació de seguretat)

---

## 🎯 Alternatives de build

| Comanda | Resultat |
|---|---|
| `npm run build` | Instal·lador NSIS + portable (per defecte) |
| `npm run build:installer` | Només l'instal·lador amb assistent |
| `npm run build:portable` | Només versió portable (single .exe) |
| `npm run build:all` | Tot alhora |

---

## 🔒 Nivell de seguretat actual

### Ja bloquejat ✓
- DevTools (F12, Ctrl+Shift+I, Ctrl+U)
- Menú contextual (botó dret)
- Segona instància simultània
- Navegació externa dins de la finestra
- WebViews no autoritzades

### Pendent (opcional, més endavant)
- **Signatura digital del `.exe`** amb certificat Sectigo/Comodo (~90€/any)  
  Sense això, Windows Defender pot mostrar "SmartScreen" el primer cop
- ~~**Ofuscació JavaScript**~~ ✅ **FET (Fase 7)** — vegeu el pas 3.5 més amunt
- **Xifrat de l'`app.asar`** — cal desxifrat runtime, hi ha llibreries com `asarmor`

---

## 📤 Distribució al client

**Opció A · Auto-update (recomanat, ja configurat)** 🆕

L'app ja té **electron-updater** integrat. Els clients rebran actualitzacions automàtiques via GitHub Releases:

1. **Configuració inicial (una sola vegada):**
   - Crea un repo a GitHub (pot ser privat): p.ex. `caja-del-dia-releases`
   - Edita `package.json` → busca `"TEU_USUARI_GITHUB"` a la secció `build.publish` i posa el teu usuari GitHub real
   - Crea un [Personal Access Token](https://github.com/settings/tokens) amb permís `repo`
   - Al PC on facis els builds, defineix la variable d'entorn:
     ```powershell
     # Windows PowerShell
     $env:GH_TOKEN = "el_teu_token_aqui"
     ```

2. **Publicar una nova versió (cada cop que actualitzis l'app):**
   ```bash
   # 1. Puja el número de versió a package.json (2.0.0 → 2.0.1)
   # 2. Fes el build i publica automàticament al GitHub:
   npm run release
   ```
   Això compila l'instal·lador NSIS i el puja com a Release al teu repo GitHub, incloent el fitxer `latest.yml` que electron-updater necessita.

3. **Què veuen els clients:**
   - Al arrencar l'app, comprova en background si hi ha una versió més nova (5s de retard perquè no bloquegi la UI)
   - Si en troba una: la descarrega **en silenci** en background
   - Un cop descarregada, apareix un diàleg: *"Caja del Día v2.0.1 està llest per instal·lar. Reiniciar ara?"*
   - Clic a **Reiniciar i actualitzar** → l'app es tanca, s'instal·la la nova versió, i es reobre sola
   - Clic a **Més tard** → s'instal·larà automàticament la propera vegada que tanqui l'app

4. **Comprovació manual:** al menú **Ajuda → Comprovar actualitzacions** el client pot forçar-ho quan vulgui.

> **Nota:** si el repo GitHub NO està configurat (queda `TEU_USUARI_GITHUB` al package.json), l'auto-update fallarà silenciosament sense afectar l'app. Perfect per desenvolupament abans de la primera publicació.

**Opció B · Manual (per als primers clients de proves)**

1. Puges el `.exe` a un servidor propi o a WeTransfer/Dropbox
2. Envies el link al client + les seves credencials de llicència
3. El client descarrega, instal·la, i introdueix la clau que li has generat
4. Fet.

---

## 🐛 Problemes freqüents

**"electron-builder no es reconoce como comando interno"**  
Executa `npm install` primer.

**"windows-code-signing" error**  
Ignora'l si no tens certificat. L'app es genera igual, però Windows mostrarà avís SmartScreen a la primera execució. El client ha de clicar "Més informació → Executar de totes maneres".

**Icon.ico invàlid**  
Usa https://convertio.co per convertir PNG a ICO (mides recomanades: 16, 32, 48, 128, 256).

**localStorage no persisteix**  
Electron usa `%APPDATA%\caja-del-dia\Local Storage\` per Windows. Les dades es guarden allà i sobreviuen entre execucions.

---

## 🔄 Actualitzacions futures

Quan generis una nova versió:
1. Puja el número al `package.json` (`"version": "2.0.1"`)
2. `npm run build`
3. Distribueix el nou `.exe`
4. Els clients desinstal·len la vella + instal·len la nova (o al reemplaçar amb NSIS)

**Automatització (Fase 7 del roadmap)**: `electron-updater` + GitHub Releases perquè s'actualitzin sols.

---

## 🎁 Extres opcionals

- **Icona per aplicació Mac** (`.icns`): si vols també fer builds per macOS
- **Snap/Flatpak** per Linux (poc probable amb el teu mercat)
- **Multi-idioma de l'instal·lador NSIS**: catalán, castellà, anglès

Digues-me quan hagis fet el primer build i què tal ha anat. 🚀
