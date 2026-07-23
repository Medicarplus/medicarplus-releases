# 📤 Guia · Pujar la web nova a GitHub Pages

**Objectiu:** actualitzar `medicarplus.es` amb els últims canvis (colors, consentiment legal, programa de referits).
**Temps:** ~10 minuts.
**Requisits:** ordinador amb navegador + credencials GitHub.

---

## Pas 1 · Obre l'ordinador i entra a GitHub

1. Ves a **https://github.com**
2. Clica **"Sign in"** (a dalt a la dreta)
3. Introdueix el teu usuari + contrasenya
   - Si no els recordes: https://github.com/password_reset

---

## Pas 2 · Localitza el repositori de la teva web

Al teu perfil hauries de veure els teus repositoris. Busca'n un que sigui:
- `Medicarplus/Medicarplus.github.io` (nom estàndard de Pages)
- O `Medicarplus/medicarplus-releases` (si serveix Pages també)
- O qualsevol amb "web" o "landing" al nom

**Per confirmar quin serveix `medicarplus.es`:**
1. Obre el repositori sospitós
2. Vés a **Settings** (icona d'engranatge a dalt)
3. Menú lateral esquerre → **Pages**
4. Aquí veuràs: *"Your site is published at https://medicarplus.es"*
5. Anota **quin branch** i **quina carpeta** està servint (típic: branch `main`, folder `/` o `/docs`)

---

## Pas 3 · Descarrega els 4 fitxers nous des d'Emergent

Al mateix navegador de l'ordinador, obre aquests 4 links **fent-hi clic dret → "Guardar como" (Ctrl+S)**:

| Fitxer a descarregar | URL |
|---|---|
| 1. Landing principal | https://project-helper-47.emergent.host/downloads/landing-medicarplus.html |
| 2. Termes legals | https://project-helper-47.emergent.host/terminos-uso.html |
| 3. Pàgina post-pagament | https://project-helper-47.emergent.host/subscription-success.html |
| 4. Guia d'instal·lació | https://project-helper-47.emergent.host/guia-client-installacio.html |

**Guarda'ls tots 4 a la mateixa carpeta al teu escriptori** (ex: crea una carpeta `medicarplus-nou/`).

Comprova que els noms són exactament aquests (sense sufixos com "(1)"):
- `landing-medicarplus.html`
- `terminos-uso.html`
- `subscription-success.html`
- `guia-client-installacio.html`

---

## Pas 4 · Puja'ls al repositori GitHub

Torna al repositori que serveix Pages (Pas 2):

### 4.1 · Puja `landing-medicarplus.html`
1. Navega a la carpeta on està l'antic: **`downloads/`** (o on estigui actualment)
2. Clica el botó **"Add file"** → **"Upload files"** (a dalt a la dreta de la llista de fitxers)
3. Arrossega el nou `landing-medicarplus.html` de la teva carpeta local a la finestra del navegador
4. Al camp **"Commit changes"** (a baix), escriu: `Update landing (referral + consent + colors)`
5. Clica **"Commit changes"** (botó verd)

### 4.2 · Puja `terminos-uso.html`
- Aquesta és una PÀGINA NOVA, no existeix encara. Ves a l'**arrel del repositori** (no dins `downloads/`)
- Clica **"Add file"** → **"Upload files"**
- Arrossega `terminos-uso.html`
- Commit message: `Add terminos-uso.html (legal compliance)`
- **"Commit changes"**

### 4.3 · Puja `subscription-success.html`
- També a l'**arrel** (no dins downloads)
- Mateix procés: Upload → Commit

### 4.4 · Puja `guia-client-installacio.html`
- També a l'**arrel** (per si volem enllaçar-hi des de la landing)
- Mateix procés: Upload → Commit

---

## Pas 5 · Espera 1-2 minuts i verifica

1. Al repositori, ves a la pestanya **"Actions"** (a dalt) — hi veuràs si el desplegament de Pages està en curs (icona groga girant → verda quan acabi)
2. Un cop es posi verd (2-3 min màxim), obre `https://medicarplus.es` **en INCÒGNIT** (per bypassar caché)
3. Verifica que veus:
   - ✅ Botó verd pulsant "🎁 Empezar prueba gratuita" a la card Trial
   - ✅ Botons blaus "Suscribirse (mensual)" al Standard
   - ✅ Botons daurats brillants al Premium
   - ✅ Card Trial sencera clicable (no només el botó)
   - ✅ Al modal Trial: 2 checkboxes obligatoris + camp opcional "🎁 Código de referido"

---

## 🆘 Si alguna cosa no funciona

**Els canvis no apareixen després de 5 minuts:**
- Espera 10 min més (GitHub Pages pot ser lent)
- Fes **Ctrl+Shift+R** al navegador (força refrescar sense caché)
- Prova en mode incògnit
- Comprova a **Actions** del repo si el build està verd o vermell (si vermell, envia'm captura)

**Error "Failed to upload":**
- Puja d'un en un enlloc de tots junts
- Comprova que la mida no és massa gran (>25MB no es pot pujar via web)

**Vull revertir un canvi:**
- Ves a l'històric de commits del fitxer
- Clica el commit anterior → botó **"Revert"**

---

## 📅 Per a la propera vegada

Cada cop que et digui *"cal actualitzar la landing"* tornaràs a fer aquests passos. Per estalviar-te feina, podries considerar (quan tinguis temps) **migrar el domini a Emergent** (gratis, 10 min una sola vegada) — així cada Deploy s'aplicaria automàticament a `medicarplus.es` sense haver de pujar res a GitHub.

Però mentre no ho facis, aquesta guia és el teu camí.

---

**Última revisió:** Feb 2026
