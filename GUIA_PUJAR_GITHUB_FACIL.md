# 📤 Guia: Pujar 4 fitxers a GitHub Pages

**Temps:** 5 minuts · **Dificultat:** fàcil · **Requereix:** ordinador amb navegador

---

## 🎯 Què farem

Actualitzarem la web pública `medicarplus.es` amb els 4 fitxers nous perquè els visitants vegin els canvis (Twilio Dual Mode, botons clicables al correu, etc.).

---

## 🔹 PART 1 · Descarregar els 4 fitxers al PC (2 min)

Obre aquestes 4 URLs una per una al navegador. **A cada una: fes `Ctrl+F5` primer** (força recàrrega sense cache), després `Ctrl+S` per guardar-les.

### Fitxer 1 · Landing principal ⭐ (el més important)

**URL:** https://project-helper-47.emergent.host/downloads/landing-medicarplus.html

**Passos:**
1. Obre la URL al navegador.
2. Prem `Ctrl + F5` (força recàrrega).
3. Prem `Ctrl + S` (guardar).
4. Apareix diàleg "Guardar como".
5. **Nom del fitxer**: canvia'l a `index.html` ⚠️ (això és MOLT important!)
6. **Tipus**: "Página web, sólo HTML" (o "Webpage, HTML Only").
7. Guarda a l'Escritori.

### Fitxer 2 · Termes d'ús

**URL:** https://project-helper-47.emergent.host/terminos-uso.html

1. Obre → `Ctrl+F5` → `Ctrl+S`.
2. **Nom**: `terminos-uso.html` (deixa el nom com està).
3. Tipus: "Página web, sólo HTML".
4. Guarda a l'Escritori.

### Fitxer 3 · Pàgina d'èxit després de pagament

**URL:** https://project-helper-47.emergent.host/subscription-success.html

1. Obre → `Ctrl+F5` → `Ctrl+S`.
2. **Nom**: `subscription-success.html`.
3. Tipus: "Página web, sólo HTML".
4. Guarda a l'Escritori.

### Fitxer 4 · Guia d'instal·lació client (amb el nou Twilio Dual Mode)

**URL:** https://project-helper-47.emergent.host/guia-client-installacio.html

1. Obre → `Ctrl+F5` → `Ctrl+S`.
2. **Nom**: `guia-client-installacio.html`.
3. Tipus: "Página web, sólo HTML".
4. Guarda a l'Escritori.

### ✅ Comprovació ràpida

A l'Escritori tens ara **4 fitxers**:
- ✅ `index.html`
- ✅ `terminos-uso.html`
- ✅ `subscription-success.html`
- ✅ `guia-client-installacio.html`

Si algun no hi és o té un nom diferent → repeteix el pas.

---

## 🔹 PART 2 · Pujar-los a GitHub (3 min)

### Pas 2.1 · Obrir el repositori

Vés a: **https://github.com/Medicarplus/medicarplus.es**

Fes login amb el teu compte GitHub si te'l demana. Assegura't que estàs a la branca **`main`** (a dalt a l'esquerra hi ha un botó "main").

### Pas 2.2 · Iniciar la pujada

A la barra de dalt del repo, cliqueu:

**"Add file"** (o "Añadir archivo") ▸ **"Upload files"** (o "Cargar archivos")

### Pas 2.3 · Pujar els 4 fitxers

S'obre una pàgina amb un rectangle gran que diu "Drag files here...".

**Opció A · Arrossegar** (més fàcil): obre l'Escritori i arrossega els 4 fitxers cap al rectangle.

**Opció B · Seleccionar**: cliqueu "choose your files" i selecciona els 4 fitxers (Ctrl+Clic).

Espera 5-10 segons. Comprova que apareixen els 4 noms a la llista:
- ✅ `index.html` (subratllat en vermell si reemplaça l'existent · és NORMAL)
- ✅ `terminos-uso.html`
- ✅ `subscription-success.html`
- ✅ `guia-client-installacio.html`

### Pas 2.4 · Confirmar el canvi (commit)

Baixa scroll a la part inferior. Secció "**Commit changes**":

1. **Títol**: `Update landing + Twilio dual mode guide`
2. **Descripció**: deixa buida.
3. Selecciona "Commit directly to the main branch".
4. Cliqueu el botó verd **"Commit changes"**.

### Pas 2.5 · Esperar (1-2 min)

Torna a la pàgina principal del repo. A dalt:
- 🟡 Rellotgeta → espera.
- ✅ Marca verda → llest!

---

## 🔹 PART 3 · Comprovar que funciona

Obre aquestes URLs amb `Ctrl+F5`:

| URL | Què veure |
|---|---|
| https://medicarplus.es | Landing amb formulari trial |
| https://medicarplus.es/terminos-uso.html | Termes d'ús |
| https://medicarplus.es/subscription-success.html | Pàgina d'èxit |
| https://medicarplus.es/guia-client-installacio.html | Guia + **Secció 7 Twilio Dual Mode** |

Si veus contingut vell: `Ctrl+F5` unes vegades, o finestra d'incògnit (Ctrl+Shift+N), o espera 5 min.

---

## 🚨 Solució de problemes

**"M'apareix `landing-medicarplus.html` al repo, no `index.html`"**  
→ Has oblidat renombrar. Vés al fitxer al GitHub → botó paperera 🗑️ → Delete. Torna a pujar el fitxer 1 amb el nom correcte `index.html`.

**"M'ha creat una branca nova enlloc de main"**  
→ Vés a "Pull Requests" i fes merge de la branca a main.

**"Els canvis no es reflecteixen a medicarplus.es"**  
→ Espera 5-10 min. Si passa >30 min, avisa'm.

---

## 📞 Si et bloqueges

Fes captura de la pantalla on estàs bloquejat i envia-me-la per chat. En 2 minuts et desbloquejo. 🚀
