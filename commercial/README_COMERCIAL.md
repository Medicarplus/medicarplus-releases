# 🔐 Caja del Día · v2 COMERCIAL

**Autor**: Marc Brugulat Lopez
**Versió**: 2.0.0-alpha
**Data**: Juliol 2026

---

## 📁 Estructura d'aquesta carpeta

```
/app/commercial/
├── ORIGINAL_v1_ESTABLE_NO_TOCAR.html   ← Còpia congelada de la v1 (mai s'edita)
├── caja_del_dia_v2.html                ← Còpia interna de treball
└── README_COMERCIAL.md                 ← Aquest fitxer
```

També publicat a:
- **v1 (producció)**: `https://project-helper-47.preview.emergentagent.com/caja_del_dia.html`
- **v2 (comercial)**: `https://project-helper-47.preview.emergentagent.com/v2.html`

---

## 🔑 Sistema de llicències actual

### Master Key (tu, Marc, com a creador)
```
MB-MASTER-BRUGULAT-2026-OWNER
```
Aquesta clau activa l'app en qualsevol instal·lació. NO la comparteixis.

### Format de claus per clients
```
MB-XXXX-XXXX-XXXX-XXXX
```
Cada clau conté un checksum matemàtic vinculat a l'Install ID del client.

### Estructura al localStorage
```json
{
  "caja.install.id.v1": "CD-B247-002D-F6B5-4483",
  "caja.install.date.v1": "2026-07-07T10:06:23.293Z",
  "caja.license.v1": {
    "key": "MB-XXXX-XXXX-XXXX-XXXX",
    "type": "STD",
    "centre": "Centre Mèdic Exemple",
    "expires": "2027-07-07",
    "activated": "2026-07-07T10:06:23.293Z",
    "installId": "CD-B247-002D-F6B5-4483"
  },
  "caja.license.lastcheck.v1": "1720347983293"
}
```

### Com generar una clau vàlida per un client (versió demo, sense servidor)

L'algoritme demo és un checksum XOR de l'Install ID. Per generar una clau vàlida:

```javascript
// Node.js script - guarda com generate-license.js
function generateKey(installId) {
  const digits = installId.replace(/[^A-Z0-9]/g, '');
  let installSum = 0;
  for (let i = 0; i < digits.length; i++) installSum = (installSum * 17 + digits.charCodeAt(i)) % 100000;
  // Genera una clau amb el mateix checksum
  const alpha = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  for (let attempt = 0; attempt < 100000; attempt++) {
    let candidate = '';
    for (let i = 0; i < 16; i++) candidate += alpha[Math.floor(Math.random()*36)];
    let sum = 0;
    for (let i = 0; i < 16; i++) sum = (sum * 31 + candidate.charCodeAt(i)) % 100000;
    if ((sum % 1000) === (installSum % 1000)) {
      return 'MB-' + candidate.match(/.{4}/g).join('-');
    }
  }
  throw new Error('No trobada');
}
console.log(generateKey('CD-B247-002D-F6B5-4483'));
```

**IMPORTANT**: Aquesta versió demo NO és segura per producció. En producció usaràs signatura RSA-PSS amb clau privada al teu servidor. El codi actual ja té l'estructura preparada.

---

## 🚀 Roadmap comercial (segons el pla acordat)

### Fase 1 · Còpia protegida ✓ FET
- `ORIGINAL_v1_ESTABLE_NO_TOCAR.html` congelat
- `v2.html` servit independent de l'original

### Fase 2 · Sistema de llicències ✓ FET
- Install ID únic per instal·lació
- Modal d'activació que bloqueja l'app
- Master Key per al creador
- Verificació periòdica (esperant servidor)
- Info-panel clicable a la signatura "Created by"

### Fase 3 · Electron (empaquetar com .exe) ⏳ PENDENT
Cal executar al teu PC Windows:
```bash
# 1. Instal·la Node.js LTS des de nodejs.org
# 2. Crea una carpeta buida i posa dins v2.html
# 3. Executa:
npm init -y
npm install --save-dev electron electron-builder

# 4. Crea main.js (proporcionat més avall)
# 5. Crea el package.json (proporcionat més avall)
# 6. Build:
npx electron-builder --win --x64
```

Fitxers necessaris (t'ho puc generar quan diguis "vés"):
- `package.json` amb config electron-builder
- `main.js` (finestra Electron amb menús desactivats i DevTools bloquejats)
- `preload.js` (seguretat entre main i renderer)
- `assets/icon.ico` (icona de l'app)

### Fase 4 · Servidor de llicències (Python FastAPI) ⏳ PENDENT
- Endpoint `POST /api/generate-license` (només tu amb password)
- Endpoint `POST /api/verify-license` (l'app truca cada 15 dies)
- Endpoint `POST /api/revoke-license` (per bloquejar clients morosos)
- MongoDB per emmagatzemar llicències + logs de verificació
- Signatura RSA-PSS (Ed25519 opcional)

### Fase 5 · Panel admin web ⏳ PENDENT
- React + Emergent Auth (Google OAuth)
- Llista de tots els clients
- Botons: activar / desactivar / renovar / veure última connexió
- Estadístiques: MRR, actius, expirats

### Fase 6 · Ofuscació ⏳ PENDENT
Amb `javascript-obfuscator`:
```bash
npx javascript-obfuscator v2.html --output v2-obfuscated.html \
  --control-flow-flattening true \
  --dead-code-injection true \
  --string-array true \
  --string-array-encoding base64
```

### Fase 7 · Instal·lador Windows amb electron-builder ⏳ PENDENT
- Config NSIS al `package.json`
- Creació d'accessos directes automàtics
- Registre a "Programes i característiques"
- Signatura del `.exe` (recomanat: certificat Sectigo, ~90€/any)

### Fase 8 · Auto-actualitzacions ⏳ PENDENT
- `electron-updater` + GitHub Releases (gratis)
- L'app comprova versió al iniciar, descarrega i instal·la automàticament

### Fase 9 · Auditoria de seguretat ⏳ PENDENT
- Test manual de bypass de llicència
- Test d'inspecció amb DevTools
- Test d'extracció de codi (`.exe` → `app.asar`)
- (Opcional) Contractar pentester extern

---

## 📞 Contacte

Per activació de llicència, dubtes o suport:
**Marc Brugulat Lopez** · Creator & owner

---

## ⚠️ IMPORTANT

- La **v1** (`/caja_del_dia.html`) NO té llicència i és la que uses tu dia a dia
- La **v2** (`/v2.html`) és la que envies a clients comercials
- Mai barregis les dades: cada versió té el seu `localStorage` independent (mateix domini però pots afegir un prefix diferent si cal)
- La còpia `ORIGINAL_v1_ESTABLE_NO_TOCAR.html` és intocable per si has de tornar enrere
