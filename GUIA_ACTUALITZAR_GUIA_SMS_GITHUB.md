# 📤 Pujar la guia amb selector d'idioma al GitHub Pages · 4 minuts

**Situació actual**: Has actualitzat la guia d'instal·lació del client amb:
- Traducció al **castellà** (idioma per defecte)
- Selector d'idioma amb bandera d'Espanya 🇪🇸 i **senyera catalana**
- Pas 7 SMS amb la plantilla GIC (`.lst`) i botó de descàrrega

Ara cal reflectir això al teu domini `medicarplus.es` (hostat a GitHub Pages).

---

## ❓ Cal esborrar alguna cosa de GitHub?

**NO cal esborrar res**. Al repo `Medicarplus/medicarplus.es` ja hi ha un fitxer `guia-client-installacio.html` de la versió anterior — quan pugis el nou amb el **mateix nom**, GitHub el **sobreescriu automàticament**.

El que sí és nou: `guia-client-installacio-ca.html` (la versió catalana) — aquest fitxer no existeix encara al repo, així que s'afegirà.

**Resum**: només has de **PUJAR 2 fitxers**. Cap acció de esborrat.

---

## 🔹 PAS 1 · Descarregar els 2 fitxers al PC (1 minut)

Obre aquestes 2 URLs al navegador, una per una:

### Fitxer 1 · Guia en castellà (per defecte)

**URL:** https://project-helper-47.emergent.host/guia-client-installacio.html

1. Prem `Ctrl + F5` (força recàrrega sense cache).
2. Prem `Ctrl + S` (guardar).
3. Al diàleg "Guardar como":
   - **Nom del fitxer**: `guia-client-installacio.html` (deixa'l com està).
   - **Tipus**: **"Página web, sólo HTML"** ⚠️ (NO triïs "Página web, completa").
   - **Ubicació**: Escritori.

### Fitxer 2 · Guia en català (nou)

**URL:** https://project-helper-47.emergent.host/guia-client-installacio-ca.html

1. Prem `Ctrl + F5`.
2. Prem `Ctrl + S`.
3. Al diàleg "Guardar como":
   - **Nom del fitxer**: `guia-client-installacio-ca.html` (deixa'l com està).
   - **Tipus**: **"Página web, sólo HTML"**.
   - **Ubicació**: Escritori.

Ara has de tenir a l'Escritori:
- ✅ `guia-client-installacio.html` (~30 KB)
- ✅ `guia-client-installacio-ca.html` (~30 KB)

---

## 🔹 PAS 2 · Pujar-los al GitHub (2 minuts)

1. Vés a: **https://github.com/Medicarplus/medicarplus.es**

2. Clica el botó **"Add file"** (a dalt a la dreta, al costat verd de "Code") → **"Upload files"**.

3. Arrossega els **2 fitxers de l'Escritori** al requadre "Drag files here" (pots pujar-los alhora, GitHub accepta múltiples).

4. Al camp inferior "**Commit changes**":
   - Missatge suggerit: `Actualitzar guia + selector idioma castellà/català`.
   - Deixa marcat "Commit directly to the main branch".

5. Clica el botó verd **"Commit changes"**.

6. Espera 1-2 minuts perquè GitHub Pages processi el desplegament.

> 💡 **Nota**: Com que `guia-client-installacio.html` ja existia al repo, GitHub l'has substituït automàticament amb la versió nova. `guia-client-installacio-ca.html` s'ha afegit com a fitxer nou.

---

## 🔹 PAS 3 · Verificar (30 segons)

Obre en pestanya d'incògnit (`Ctrl+Shift+N` a Chrome) aquestes 2 URLs:

### ✅ Verificació 1 · Castellà per defecte
**URL:** https://medicarplus.es/guia-client-installacio.html

Comprova:
- El títol diu **"Cómo instalar MediCar Plus"** (en castellà).
- A dalt a la dreta apareix el selector: pill daurada 🇪🇸 **Castellano** i botó blanc [senyera] **Català**.
- El Pas 7 té el callout groc "🖨️ Paso previo · Exportar el listado desde el programa GIC" amb el botó 📥 Descargar plantilla GIC.

### ✅ Verificació 2 · Català
**URL:** https://medicarplus.es/guia-client-installacio-ca.html

Comprova:
- El títol diu **"Com instal·lar MediCar Plus"** (en català).
- A dalt a la dreta: botó blanc 🇪🇸 **Castellano** i pill daurada [senyera] **Català**.

### ✅ Verificació 3 · El botó del selector porta a l'altra versió

- A la pàgina castellana, clica **[senyera] Català** → ha de portar a `/guia-client-installacio-ca.html`.
- A la pàgina catalana, clica **🇪🇸 Castellano** → ha de portar a `/guia-client-installacio.html`.

Si tots 3 punts passen: 🎉 **Fet!** Els teus clients ja poden triar l'idioma.

---

## ⚠️ Problemes comuns

**"No apareixen els canvis a medicarplus.es"**  
GitHub Pages triga 1-2 minuts a desplegar. Espera i torna a provar en incògnit (les vegades sortiran del cache).

**"Em surt la versió antiga sense selector"**  
Prem `Ctrl+Shift+R` a la pàgina per forçar recàrrega sense cache. Si continua igual, potser has guardat "Página web, completa" en lloc de "sólo HTML" — repeteix el PAS 1.

**"El botó de descàrrega de la plantilla GIC no funciona"**  
Verifica que la URL apunti a `https://project-helper-47.emergent.host/...` (no relativa). Si no, tornes a descarregar del preview i puja de nou.

**"Quan clico Català em surt 404"**  
No has pujat el fitxer `guia-client-installacio-ca.html` (fitxer 2 del PAS 1). Torna-hi.
