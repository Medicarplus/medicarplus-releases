# PRD — MediCar Plus (Estat 15/07/2026 — v2.1.11)

## 🆕 CANVIS 15/07/2026 · Sessió acumulada

### v2.1.11 · Estat més recent
- **🛡️ Nou dropdown "Copias de seguridad"** al header (verd fosc), agrupa: Guardar copia · Restaurar copia · Historial de copias. Testids: `btn-backup`, `btn-save-backup`, `btn-restore-backup`, `btn-history`.
- **🤖 Fix crític AI Gemini**: model actualitzat a `gemini-3-flash-preview` (Emergent LLM Key) i `gemini-2.0-flash` (Google API key usuari). Prompt del sistema traduït al castellà (resposta per defecte en castellà, català només si l'usuari ho demana explícitament).
- **🌍 Missatges d'error AI traduïts al castellà**: "Tu clave de Google Gemini ha dado error", "💡 Consejo: introduce tu propia clave..." (abans en català).
- **💳 Fix pagament UX**:
  - `openExternalUrl()` universal: Electron → `window.open` intercepted per `setWindowOpenHandler` → `shell.openExternal`. Navegador → `window.location.href` (evita bloqueig popups).
  - "Ver planes y pagar" ara TANCA el modal Config abans d'obrir el modal Upgrade (arregla z-index bug on Config 10000 > Upgrade 9999).
- **🧾 Portal Client Stripe**:
  - Backend: `POST /api/payments/billing-portal` (params: install_id o customer_email) + `GET /api/payments/subscription/by-install/{id}`
  - Frontend: botó **"🧾 Gestionar subscripció / Cancel·lar"** dins ⚙️ Configuración, només visible si té subscripció activa. Mostra estat (activa/cancelada/past_due) i si es cancel·larà al final del període.
  - Landing: link "Gestionar mi suscripción" al peu de pàgina → prompt d'email → obre portal.
- **📊 Dropdown Estadísticas** (Facturación mensual · Estadísticas autoescuelas · **Comparativa años** [NOU])
  - `openYearComparison()` amb KPIs, taula comparativa % variació, taula mensual 12×N anys, selector 2-6 anys, impressió.

### Documentació actualitzada
- `guia-client-installacio.html`: nou dropdown, comparativa anys, subscripció auto-renovable, cancel·lació pas a pas
- `guia-medicar-plus.html`: novetats v2.1.10-11 al top, portal Stripe tècnic, webhook flow
- `guia-stripe-setup.html`: pas obligatori d'activar Billing Portal a Stripe Dashboard, flux complet de cancel·lació 10 passos

### Cal fer després per anar LIVE
- Activar Customer Portal a Stripe Dashboard (Settings → Billing → Customer Portal): Cancel subscriptions "at end of billing period", Invoice history, Payment methods, Business info amb Privacy/Terms URLs
- Substituir Stripe TEST keys per LIVE keys al backend `.env` quan tinguis IBAN

---

# PRD — MediCar Plus (Estat 14/07/2026)

## 🚨 REGLA D'OR · PRIORITAT MÀXIMA · LLEGIR ABANS DE QUALSEVOL CANVI

**MediCar Plus és programari de FACTURACIÓ i CAIXA per a negocis en funcionament.**

**Zero tolerància a bugs.** No poden fallar:
- Cap botó
- Cap càlcul (IRPF, totals, sumes, IVA)
- Cap enviament de SMS
- L'agenda de visites (Cites)
- La sincronització de dades
- Els descuadres de caixa
- La generació d'impressions/rebuts
- L'auto-updater ni les llicències

**Els bugs recurrents són símptomes d'una decisió arquitectural equivocada**, no bugs individuals. Cal atacar l'ARREL, no la fulla. Cada cop que un problema tornia a aparèixer, cal preguntar-se: "com fem que aquest problema no pugui existir mai més?"

**Abans de finalitzar qualsevol tasca:**
- Testing exhaustiu (Playwright + curl + regression)
- Verificar que els fluxos crítics (cierre diario, IRPF, SMS, Cites, licencia) segueixen funcionant
- Si detectes un possible edge case, NO deixar-lo per després

**Marc no és informàtic.** Tot ha d'auto-repararse o ser trivial d'usar. Cap panell exposat al client final que pugui rompre res.

---

## ✅ ESTAT PRE-LLANÇAMENT (14/07/2026)

**Testing exhaustiu completat**: 81/81 pytest backend + tots els fluxos frontend crítics verificats.

Cap bug crític. Cap regressió. LLEST PER LLANÇAR AL MERCAT.

### Verificat funcionant:
- Activació llicència amb Master Key
- Setup 2 empreses (Tráfico + Revisiones) amb dades aïllades
- Cierre diario · ingressos/despeses · totals
- Impressió WYSIWYG UNIVERSAL (Cierre + IRPF + Estadístiques + Libro Registro + Llibreta) — mateixa UI, botó 'Guardar PDF' morat + 'Imprimir ara' verd
- IRPF: auto-BRUT, càlculs S.S./TOTAL/IRPF/NET/NET S.S./TOTAL FINAL en viu sense pèrdua de focus
- SMS import CSV (backend `/api/sms/preview`): 3 vàlids + 1 duplicat detectat correctament
- SMS campanya en mode mock (funciona · Twilio real pendent env vars)
- Cites del dia (modal amb 3 tabs)
- Auto-descoberta URL: recupera de URL morta en 4-5s via GitHub raw
- Configuración modal net (sense panells d'URL exposats)
- Idioma switcher CA/ES
- Widget IA (Google Gemini) present a guies

---

## 🛡️ SISTEMA DE PUBLICACIÓ DEFINITIU

**UNA sola comanda per publicar:**
```powershell
cd C:\medicarplus\electron
powershell -ExecutionPolicy Bypass -File .\publish-safe.ps1
```

**Última versió publicada**: v2.0.36 (13/07/2026)
**Pròxima versió (pendent de publicar per Marc)**: v2.1.7 amb:

## 🖨️ IMPRESSIÓ · SOLUCIÓ DEFINITIVA (v2.1.9 · 14/07/2026)

**Bug reportat**: "Esta aplicación no admite la vista previa de impresión" al diàleg de Windows.

**Root cause**: intent d'imprimir un iframe (off-screen o inline). Windows/Electron mostren aquest error perquè no poden generar preview d'un iframe extern.

**Solució definitiva**:
- Injectem el HTML del print com un `<div id="_print_root">` dins el DOM principal
- Afegim CSS `@media print` que amaga tot el document EXCEPTE aquest div durant la impressió
- Cridem `window.print()` del document principal
- Al finalitzar (afterprint), netegem el div i l'estil

**Beneficis**:
- ✅ Windows fa preview correcta (imprimeix el document actual, no un iframe)
- ✅ Consistent amb comportament de qualsevol app web professional
- ✅ Zero clics intermedis: 1 clic → diàleg amb preview → Imprimir/PDF/Cancel·lar
- ✅ Compatible amb Electron + navegadors + macOS

**Aplicat automàticament a**: Cierre diari, IRPF, Estadístiques, Libro Registro, Llibreta, SMS report.

## 🤖 SISTEMA AUTO-REPARACIÓ D'URL (v2.1.6 · manteniu)

**Problema resolt**: Emergent rota les URLs de preview periòdicament, deixant les apps instal·lades amb 404.

**Solució 100% automàtica (sense intervenció humana)**:
1. Backend a l'arrencar detecta la seva pròpia URL via env var `APP_URL`/`preview_endpoint`
2. Auto-commit del fitxer `api-endpoint.json` al repo GitHub `Medicarplus/medicarplus-releases` (PAT ja té write access)
3. Fitxer accessible via `raw.githubusercontent.com/Medicarplus/medicarplus-releases/main/api-endpoint.json` (CDN estable, mai canvia)
4. App Electron consulta aquest URL a l'iniciar-se, cachea 24h a localStorage
5. Si rep 404, invalida caché i re-consulta el JSON automàticament
6. Auto-invalidació de caché al canvi de versió de l'app

**Verificació**: 8/8 tests Playwright OK · Auto-publish funcionant a Github

## Altres fixes v2.1.6
- 🐛 Fix crític S.S. IRPF: cel·les es sobrescrivien perquè índexs `cells[]` eren obsolets després d'afegir columna €/CERT
- ⚡ Auto-BRUT visual immediat (CERT × €/CERT)
- 🔧 Fix alineació taula TOTALS MES (colspan=3)
- 🎨 Configuración neta: sense panells de URL avançada exposats al client
- 📚 Guia admin: nova pestanya "🆘 Errors 404" amb explicació del sistema auto-heal
- 🤖 Widget IA gratuïta a totes les guies (Google Gemini · 1.500 consultes/dia amb clau pròpia)
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

## 📝 Sessió 15/07/2026 · Gemini onboarding + email prova + decisió Verifactu

### 🎁 Popup onboarding clau Gemini gratuïta (FET + testejat)
- `showGeminiOnboarding()` a v2.html (~línia 3390): modal en castellà que apareix el 1r cop que l'usuari obre l'Asesor IA sense clau guardada
- Passos guiats + botó "Abrir Google AI Studio" (window.open → interceptat per Electron a shell.openExternal)
- Guardar clau → valida ≥20 car., desa a `caja.geminiKey`, obre modal IA
- "Ahora no" → desa `caja.aiOnboardSeen=1`, no torna a molestar
- Traduïts tots els textos catalans restants del modal IA a castellà
- Test IDs: `gemini-onboarding-modal`, `gemini-onboarding-open-link`, `gemini-onboarding-key-input`, `gemini-onboarding-save-btn`, `gemini-onboarding-skip-btn`
- Testejat amb Playwright local (4 fluxos: guardar, saltar, no-reaparició, clau curta rebutjada) ✅

### 📧 Email de llicència de prova (FET)
- Enviat a marcbrugulat@hotmail.com via SMTP IONOS (`smtp_sent` OK) amb dades demo

### 🧾 Verifactu · Decisió (RECERCA FETA — pendent que Marc creï el compte)
- Guanyador: **Verifacti** app per Stripe (~2,90€/NIF/mes, prova gratuïta) — verifacti.com/plugins/stripe
- S'instal·la dins Stripe, genera factures PDF amb QR Verifactu, numeració correlativa, rectificatives, i envia registres a l'AEAT amb el seu propi certificat. ZERO codi nostre.
- Alternatives descartades per preu: EasyVerifactu (14,95€/mes), BeeL (15,90€/mes), Billin (12,50€/mes), Holded (15€/mes), Quaderno (49€/mes)
- ACCIÓ MARC: registrar-se a verifacti.com i instal·lar l'app al seu compte Stripe (quan passi a live mode)

## 📝 Sessió 15/07/2026 (2a part) · Recordatoris renovació + checklist sortida

### 📧 Recordatoris de renovació automàtics (FET + testejat)
- `/app/backend/services/renewal_reminders.py`: sweep diari (background loop a startup) que envia email castellà als clients amb llicència que caduca en ≤7 dies, sense subscripció Stripe activa. Idempotent (`renewal_reminder_for`).
- Endpoint manual admin: `POST /api/admin/renewal-reminders/run` (X-Admin-Token). Testejat: sent=1, 2a passada skipped=1, sense token 401. Email real enviat a marcbrugulat@hotmail.com.

### 🎯 Trial badge millorat
- Botó "Comprar" del badge de prova ara obre `openUpgradeModal()` (checkout in-app) en lloc d'enllaç extern. "PROVA EXPIRADA" → "PRUEBA EXPIRADA" (castellà).

### 📚 Guia personal actualitzada (guia-medicar-plus.html)
- Nou "🚀 CHECKLIST DE SORTIDA AL MERCAT" (#checklist-sortida) amb 5 passos ordenats: 1) Claus Stripe LIVE, 2) Verifacti (~2,90€/mes, instal·lar quan Stripe sigui live), 3) Twilio real, 4) Google Search Console, 5) Deploy backend producció. Costos actualitzats (~21€/mes).
- Taula d'estat actualitzada (Stripe test 100% testejat, Verifacti decidit, recordatoris actius, Search Console pendent).

### ✅ Testing agent iteration_13: 100% backend (10/10) + 100% frontend (5/5), zero errors consola. Llest per llançament.

## 📝 Sessió 15/07/2026 (3a part) · Guia + Manual com a adjunts

### 📎 Correu de llicència ara inclou guia i manual com a ADJUNTS
- **Problema detectat**: els enllaços `medicarplus.es/guia-client-installacio.html` i `/manual-usuari.html` retornaven 404 perquè aquests arxius mai s'havien pujat al repo GitHub Pages `Medicarplus/medicarplus.es` (i el PAT no té permís d'escriptura en aquest repo).
- **Solució escollida (opció A)**: adjuntar els dos arxius HTML directament al correu de llicència. Independent de GitHub Pages, funciona sempre.
- **Canvis a `/app/backend/services/mailer.py`**:
  - Nova funció `_load_attachments()` que llegeix els 2 HTML de `/app/frontend/public/`.
  - `_send_smtp()` accepta `attachments` opcionals (multipart/mixed amb `MIMEApplication`).
  - Resend inclou `attachments` amb el contingut en base64.
  - Cos del correu actualitzat: enllaços trencats reemplaçats per referències als adjunts (`guia-client-installacio.html`, `manual-usuari.html`).
- **Testejat**: correu real enviat a marcbrugulat@hotmail.com amb els 2 adjunts (14 KB + 28 KB). Result: `smtp_sent`.

## 📝 Sessió 15/07/2026 (4a part) · Adjunts en PDF

### 📄 Guia i manual ara s'adjunten com a PDF (no HTML)
- Nou mòdul `/app/backend/services/pdf_builder.py`: `html_to_pdf(path)` amb Playwright Chromium (A4, marges 16/12mm, fons imprès). Cache a `/tmp/medicar_pdfs/` per mtime.
- `mailer.py` → `_load_attachments()` és async i genera PDFs a partir dels HTML. Fallback a HTML si Playwright falla.
- Cos del correu i botons actualitzats amb noms nous: `guia-instalacion-medicar-plus.pdf` i `manual-usuario-medicar-plus.pdf`.
- SMTP diferencia `application/pdf` vs `octet-stream` segons extensió.
- **Testejat**: correu real a marcbrugulat@hotmail.com amb 2 PDF adjunts (667 KB guia + 313 KB manual). Magic `%PDF-` verificat. `smtp_sent` OK.

## 📝 Sessió 15/07/2026 (5a part) · Portada branded per PDF

### 🎨 Portada personalitzada per client
- `pdf_builder.py` refactoritzat:
  - `_cover_html(...)` genera una portada A4 amb branding MediCar Plus (logo M+ daurat, bandes superior/inferior en gradient, targeta "EMITIDO PARA" amb Cliente/Plan/Caducidad/Install ID/Clave).
  - `build_client_pdf(doc_kind, ...)` renderitza portada + cos i els uneix amb `pypdf`. El cos es cacheja per mtime (guia/manual només es regeneren si canvien els HTML). Només la portada es genera per client (~1s).
- `mailer.py` → `_load_attachments()` ara accepta les dades del client i genera dos PDFs personalitzats (guia + manual) amb la portada corresponent (títol i subtítol diferents).
- Nova dependència: `pypdf==6.14.2` afegida a `requirements.txt`.
- **Testejat**: correu real a marcbrugulat@hotmail.com. PDFs: guia 746 KB (2 pàgines: portada + cos), manual 391 KB. Portada verificada amb screenshot: logo, bandes daurades, targeta client i footer amb dades. `smtp_sent` OK.

## 📝 Sessió 15/07/2026 (6a part) · Nº Documento correlatiu

### 📇 Referència d'emissió atòmica per PDF
- Nou `/app/backend/services/doc_counter.py`:
  - `next_doc_number()` → `MCP-{year}-{seq:06d}`. Ex: `MCP-2026-000042`.
  - Backend: `db.emission_counters` amb `find_one_and_update({_id:license_docs_2026},{$inc:{seq:1}},upsert=True)`. Atòmic, thread-safe. Reset anual automàtic.
  - ⚠️ NO és factura fiscal (la real l'emet Stripe/Verifacti). Només ref. interna.
- Portada actualitzada: cantonada superior dreta amb "Nº DOCUMENTO · MCP-YYYY-NNNNNN" en Courier daurat.
- `mailer.py` genera el número una vegada per emissió i el comparteix entre guia i manual (mateixa ref. per a ambdós PDFs).
- **Testejat**: counter incrementa correctament (000001 → 000002 → 000003). Screenshot portada verificat. Correu enviat OK a marcbrugulat@hotmail.com.
