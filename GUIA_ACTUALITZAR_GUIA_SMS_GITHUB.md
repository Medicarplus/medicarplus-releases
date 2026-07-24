# 📤 Actualitzar la Guia SMS a GitHub Pages · 3 minuts

**Situació:** Has actualitzat el Pas 7 SMS amb la nova plantilla GIC (`F_revision_con_telefono_y_movil.lst`) + captura del programa GIC. Ara cal pujar-ho a `medicarplus.es/guia-client-installacio.html`.

**Bona notícia:** només cal pujar **1 sol fitxer HTML**. Els assets (plantilla `.lst` i captura PNG) es serveixen ja des d'Emergent amb URLs absolutes, així que **no** cal pujar cap carpeta `downloads/gic-templates/` al GitHub.

---

## 🔹 PAS 1 · Descarregar la guia actualitzada (30 s)

1. Obre aquesta URL al navegador:  
   **https://project-helper-47.emergent.host/guia-client-installacio.html**

2. Prem `Ctrl + F5` (força recàrrega sense cache — MOLT important).

3. Prem `Ctrl + S` per guardar.

4. Al diàleg "Guardar como":
   - **Nom del fitxer**: `guia-client-installacio.html` (deixa'l com està).
   - **Tipus**: "Página web, sólo HTML" (o "Webpage, HTML Only") — ⚠️ NO triïs "Página web, completa".
   - **Ubicació**: Escritori.

5. Es guardarà 1 sol fitxer `guia-client-installacio.html` (~30 KB).

---

## 🔹 PAS 2 · Pujar-lo al repositori GitHub Pages (2 min)

1. Vés a: **https://github.com/Medicarplus/medicarplus.es**

2. Busca el fitxer `guia-client-installacio.html` al llistat de fitxers del repo.

3. Clica-hi a sobre → et surt la vista prèvia del contingut.

4. Al capdamunt de la vista prèvia, clica la icona **✏️ Edit** (llapis) o **⋯ → Delete this file**.
   
   > **Recomanat:** No et compliquis, esborra i puja de nou.
   > 
   > 4a. Clica **⋯** (tres punts, dalt a la dreta) → **Delete file**.  
   > 4b. Confirma amb "Commit changes" (missatge: `Delete old guide`).
   > 4c. Torna a l'arrel del repositori.
   > 4d. Clica **Add file → Upload files**.  
   > 4e. Arrossega el `guia-client-installacio.html` de l'Escritori.  
   > 4f. Al camp "Commit changes", posa: `Update guia: nou pas 7 SMS amb plantilla GIC`.  
   > 4g. Clica **Commit changes**.

5. Espera 1-2 minuts perquè GitHub Pages processi el desplegament.

---

## 🔹 PAS 3 · Verificar (30 s)

1. Obre en incògnit (`Ctrl+Shift+N` a Chrome): **https://medicarplus.es/guia-client-installacio.html**

2. Cerca el "Pas 7 · Avisos SMS" i comprova que hi apareixi el callout groc:
   
   > 🖨️ **Pas previ · Exportar el llistat des del programa GIC**  
   > [passos numerats + botó groc "📥 Descarregar plantilla GIC"]

3. Clica el botó **📥 Descarregar plantilla GIC** i verifica que descarrega el fitxer `.lst` de ~5 KB.

Si tot va bé: ✅ **Fet!** Els teus clients ja veuran la nova guia amb la plantilla GIC.

---

## ⚠️ Problemes comuns

**"No apareixen els canvis a medicarplus.es"**  
GitHub Pages triga 1-2 min a processar. Espera i torna a provar en incògnit.

**"El botó de descàrrega no funciona"**  
Comprova que la URL del botó apunti a `https://project-helper-47.emergent.host/downloads/gic-templates/F_revision_con_telefono_y_movil.lst`. Si diu `downloads/gic-templates/...` (sense el domini d'Emergent), tornes a descarregar el fitxer del preview i el pugues altra vegada.

**"El fitxer descarregat és molt gran"**  
Vas triar "Página web, completa" en lloc de "sólo HTML". Repeteix el PAS 1 assegurant-te de triar només HTML.
