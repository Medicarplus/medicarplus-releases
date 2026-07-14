# PRD — MediCar Plus (Estat 14/07/2026)

## 🛡️ SISTEMA DE PUBLICACIÓ DEFINITIU

**UNA sola comanda per publicar:**
```powershell
cd C:\medicarplus\electron
powershell -ExecutionPolicy Bypass -File .\publish-safe.ps1
```

**Última versió publicada**: v2.0.36 (13/07/2026)
**Pròxima versió (pendent de publicar per Marc)**: v2.1.5 amb:
- 🐛 **FIX CRÍTIC (14/07/2026)**: quan s'escrivia al camp S.S. (o NET S.S.) el DOM es corrompia perquè els índexs `cells[]` del handler d'actualització en viu eren obsolets (van quedar desalineats després d'afegir la columna €/CERT). Ara els índexs són correctes: `cells[5]=TOTAL, cells[6]=IRPF, cells[7]=NET, cells[9]=TOTAL FINAL`.
- ⚡ **Auto-BRUT visual immediat**: quan escrius CERT + €/CERT, el camp BRUT s'actualitza visualment a l'instant (abans requeria fer Tab per veure el resultat).
- ⏱️ **Debounce optimitzat**: full re-render passa de 600ms → 800ms + skip si l'usuari està escrivint. Refresc immediat del resum trimestral en fer blur.
- 🔧 Fix alineació taula TOTALS MES (colspan=3 cobreix NOM+CERT+€/CERT)
- 💶 **IRPF · Columna €/CERT** (v2.1.3): càlcul automàtic BRUT = CERT × €/CERT quan es completa la columna
- 🖨️ **Fix crític impressió Electron**: `window.open` no funcionava a l'app compilada → substituït per `printHtml()` amb iframe ocult. IRPF/Estadísticas/Llibreta imprimeixen amb `@page{size:A4 landscape}` i colors de fons.
- 👁️ Modal de Print Preview abans del diàleg d'impressió
- 📅 **MÒDUL "CITES DEL DIA"** (Premium): sincronització amb Google Calendar, Doctoralia, Calendly, Doctolib, Timify, iCloud i qualsevol calendari amb URL iCal
  - Backend endpoint: `POST /api/calendar/sync` (parseja iCal amb `icalendar` + `recurring-ical-events`)
  - Badge notificacions no llegides + polling 5 min
  - Estadístiques històriques de cites al modal principal
- 📋 IRPF · fix hardcoded català → respecta preferència idioma (Spanish)
- 🐛 IRPF · Fix regressió: entrades "BRUGULAT" ja no s'eliminen per seed-clearing
- 🌐 Landing `medicarplus.es`: 8 captures reals amb lightbox

### Pipeline 5-passos (tot dins publish-safe.ps1):
1. `sync.js` — Baixa fitxers font del servidor via `/api/electron/download/*` amb User-Agent Mozilla. Aborta si algun fitxer no passa signatures. **MAI barreja versions.**
2. `validate-local.js` — Verifica 8+ marcadors reals a index.html (IDs de botons, seccions, títol), signatures a main.js/preload.js/package.json.
3. `npm version patch` + `electron-builder --win nsis portable --x64`
4. `smoke-test.js` — Extreu app.asar del .exe compilat i verifica strings crítiques + mida ≥30MB.
5. `electron-builder --publish always` → GitHub Releases

### Fitxers clau
- `/app/commercial/electron/sync.js` — Sync bulletproof (User-Agent Mozilla, exit 3 si falla)
- `/app/commercial/electron/validate-local.js` — Pre-build validation
- `/app/commercial/electron/smoke-test.js` — Post-build validation
- `/app/commercial/electron/publish-safe.ps1` — Orquestrador (ASCII pur, comprova GH_TOKEN)
- `/app/backend/routes/electron_manifest.py` — Endpoint `/api/electron/download/{file}` + `/api/electron/manifest`
- `/app/backend/routes/electron_channel.py` — Endpoint `/api/electron/update-channel` (kill switch)
- `/app/frontend/public/downloads/electron-src/*` — Fitxers font servits al Marc
- `/app/frontend/public/guia-publicar-versions.html` — Guia actualitzada

### Requisits Marc PC (Windows)
- Directori: `C:\medicarplus\electron`
- `GH_TOKEN` a env vars permanent (via `setx`), permisos `repo` + `workflow`
- Node.js ≥18

### Kill Switch d'emergència
Editar `/app/backend/electron_channel.json`:
```json
{"blocked_versions":["2.0.X"], "latest_safe_version":"2.0.Y"}
```
Efecte immediat en tots els clients (main.js consulta abans d'auto-actualitzar).

---

## Estat del sistema (heretat)

### ✅ COMPLETAT

**Domini + Email**
- `medicarplus.es` (IONOS) — 1€/any
- 5 correus: `info@` + 4 àlies
- SMTP `smtp.ionos.es:587` (TLS) · IMAP `imap.ionos.es:993`

**Stripe (Test mode)**
- 4 preus: STD_MES · STD_ANY · PREMIUM_MES · PREMIUM_ANY
- Webhook actiu · Auto-renovació provat

**GitHub Releases (Auto-updater)**
- Repo públic `Medicarplus/medicarplus-releases`
- `electron-updater` a main.js amb kill switch integrat
- Auto-download + auto-install oneClick

**App v2 (Electron)**
- Modal Configuració ⚙️
- Modal SMS Campaigns (mode MOCK)
- Importar CSV al costat d'Entradas del día
- Botó Suport / Contacte (SMTP IONOS)
- Auto-updater silenciós

**Landing Page**
- `medicarplus.es` a GitHub Pages amb HTTPS
- Cloudflare CDN

---

## Pendents / Backlog

### P1 (properes tasques)
- Publicar v2.0.27 (Marc): `powershell -ExecutionPolicy Bypass -File .\publish-safe.ps1`
- Screenshots reals de l'app a `medicarplus.es`
- Google Search Console per SEO
- Verificar propagació DNS (ja hauria d'estar propagat)

### P2 (quan hi hagi)
- Stripe Live Mode (quan Marc tingui IBAN d'empresa)
- Twilio real (quan compri crèdit, ara MOCKED)
- Deploy backend a producció Emergent (per stripe live)

### Backlog (idees futures)
- Panell admin visual per gestionar kill switch sense editar JSON
- Heartbeat `/api/electron/heartbeat` amb versió del client → dashboard de versions instal·lades
- Signatura digital de codi (evitar SmartScreen warning)

---

## Credencials i URLs

- Admin Panel Token: `MB-ADMIN-BRUGULAT-2026-4F8E2A1C`
- Master License: `MB-MASTER-BRUGULAT-2026-OWNER`
- Backend URL preview: `https://project-helper-47.preview.emergentagent.com`
- Landing: `https://medicarplus.es`
- Releases: `https://github.com/Medicarplus/medicarplus-releases/releases`
- Guia: `/guia-publicar-versions.html`

## 🚨 Historial d'incidents resolts

- **09/07**: `sync.js` corromplent builds → resolt amb signatures + exit 3 + endpoint /api/electron/download bypassant Cloudflare
- **09/07**: Boot-guard mostrant "app aturada" en pantalla completa → ELIMINAT (selectors buggy)
- **10/07**: GH_TOKEN perdut a nova sessió → documentat `setx` permanent

## 📝 Nous features (11/07/2026)

### 📊 Estadísticas · Sección Tráfico
- Nou toggle dins del modal d'Estadísticas: **🚗 Autoescolas** (existing) / **🚦 Tráfico** (nou)
- Agrega automàticament totes les entrades importades del CSV DGT (`kind:'TRAF' && _csv:true`) de `caja.v1`
- **Vista anual**: gràfic de barres per mesos + gràfic per tipus + 4 KPIs (entrades, importes, tasas, total) + taula 12 mesos × [total, renov, exped, dupli, canje, otro, importe, tasas]
- **Vista mensual**: gràfic diari + tipus + KPIs + taula per dia
- Impressió separada per la secció Tráfico
- Funció de test: `renderTrafficTable()` a v2.html línies ~800–990

### 🎁 Modal ¿Novedades?
- CHANGELOG in-app amb entrades semver (versió + data + highlights)
- Auto-show quan `caja.last_seen_version` < versió actual (i no és primera instal·lació)
- Accés manual: menú *Contabilidad ▸ 🎁 Novedades* (mostra les 3 més recents)
- Botó "Entendido" tanca i actualitza `caja.last_seen_version`
- Test IDs: `whats-new-modal`, `whats-new-ok`, `btn-whats-new`, `st-section-switch`, `traffic-stats-year`, `traffic-stats-month`
