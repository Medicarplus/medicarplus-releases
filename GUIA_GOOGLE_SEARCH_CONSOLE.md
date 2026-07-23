# Guia pas a pas · Configurar Google Search Console per medicarplus.es

**Objectiu:** Fer que Google trobi el teu web `medicarplus.es`, l'indexi, i et doni estadístiques (visites, paraules clau, errors detectats).
**Temps estimat:** 15 minuts.
**Cost:** Gratuït.
**Compte a usar:** `brugulatmarc@gmail.com`

---

## 📋 Fitxers que et cal pujar a GitHub abans de començar

Els he generat automàticament. Descarrega'ls del preview:
1. `sitemap.xml` → https://project-helper-47.preview.emergentagent.com/downloads/sitemap.xml
2. `robots.txt` → https://project-helper-47.preview.emergentagent.com/downloads/robots.txt

**Puja aquests 2 fitxers a l'arrel del repo `Medicarplus/medicarplus.es`** (al mateix lloc on hi ha `index.html`).

Encara **NO** vagis a Search Console. Primer puja aquests 2 fitxers. Un cop pujats i visibles a:
- https://medicarplus.es/sitemap.xml
- https://medicarplus.es/robots.txt

passem a l'apartat següent.

---

## 🔍 PAS 1 · Registrar-se a Google Search Console

1. Obre aquesta URL: **https://search.google.com/search-console**
2. Fes login amb `brugulatmarc@gmail.com`.
3. Google et pregunta "Selecciona el tipo de propiedad".
4. **Trieu l'opció de la DRETA "Prefijo de URL"** (NO l'opció de dominio).
5. A la caixa escriu exactament: `https://medicarplus.es/`
6. Clica **"Continuar"**.

---

## ✅ PAS 2 · Verificar que el web és teu (mètode fitxer HTML)

Google necessita comprovar que ets propietari. Et donarà diverses opcions. **Farem la més senzilla per GitHub Pages:**

1. Google et mostrarà un rectangle amb el títol **"Archivo HTML"**.
2. Hi haurà un botó **"Descargar archivo"**. Cliquea'l → et baixarà un fitxer amb nom estrany tipus `google1a2b3c4d5e6f7g8.html` (o similar).
3. **Aquest fitxer NO l'obris**, deixa'l tal qual.
4. Ves al teu repositori GitHub: `Medicarplus/medicarplus.es`
5. Puja aquest fitxer `google...html` a l'arrel del repositori (mateix lloc on hi ha `index.html`).
6. Espera 1 o 2 minuts perquè GitHub Pages el publiqui.
7. Comprova que funciona obrint al navegador: `https://medicarplus.es/google...html` (amb el nom exacte del fitxer).
   - Ha de mostrar-te una línia de text tipus `google-site-verification: google1a2b3c4d5e6f7g8.html`.
8. Torna a Search Console i clica el botó **"Verificar"** de la finestra que tenies oberta.
9. Google respondrà **"¡Propiedad verificada!"** ✅

**Important**: NO esborris aquest fitxer `google...html` del repositori mai més. Si l'esborres, Google et desactivarà el compte.

---

## 🗺️ PAS 3 · Enviar el sitemap

1. Un cop verificat, a Search Console t'apareix el menú de l'esquerra.
2. Clica **"Sitemaps"** (o "Mapas del sitio").
3. A la caixa **"Añadir un nuevo sitemap"** escriu: `sitemap.xml`
4. Clica **"Enviar"**.
5. Google respondrà "Sitemap enviado correctamente" i començarà a llegir les teves URLs.
6. **Estat esperat**: "Correcto" (pot trigar unes hores).

---

## ⏳ PAS 4 · Esperar la indexació

- **Primeres 24 hores**: Google comença a rastrejar la pàgina.
- **Entre 3-7 dies**: Les teves pàgines comencen a aparèixer a resultats de cerca.
- **Fins a 4 setmanes**: Indexació completa i estadístiques significatives.

**Mentre esperes**, pots forçar la indexació d'una URL concreta:
1. A Search Console, dalt de tot hi ha una barra de cerca amb la lupa.
2. Escriu `https://medicarplus.es/` i prem Enter.
3. Google et dirà "URL no está en Google". Clica **"Solicitar indexación"**.
4. Repeteix per cada URL important (terminos-uso, guia-client-installacio).

---

## 📊 PAS 5 · Consultar estadístiques (a partir del 7è dia)

Al menú esquerre tens:
- **"Rendimiento"**: quantes vegades has aparegut, quants clics, paraules clau que t'ha buscat la gent.
- **"Cobertura"**: quantes pàgines tens indexades i si hi ha errors.
- **"Experiencia"**: velocitat i mobile-friendly.

---

## ❓ Preguntes freqüents

**P: I si el web no es carrega en el moment de verificar?**
R: Espera 2-3 minuts després de pujar el fitxer google...html a GitHub. GitHub Pages triga una mica a desplegar.

**P: Cal fer alguna cosa més després?**
R: NO. Un cop configurat, funciona sol per sempre. Només reviseu Search Console 1 cop al mes.

**P: I si canvio el `sitemap.xml` en un futur?**
R: Puges el nou al repositori i Google el rellegeix automàticament (cada 24h).

**P: Google em cobrarà mai res?**
R: **MAI**. Search Console és 100% gratuït i no demana targeta.

---

## 🆘 Si et bloqueges

Digue'm quin pas i què veus a la pantalla, i te'l resolc. Els punts crítics són:

1. **Pujar `sitemap.xml` i `robots.txt` a GitHub** (abans de tot).
2. **Descarregar el fitxer HTML de verificació de Google i pujar-lo a GitHub** (Pas 2).
3. **Enviar el sitemap dins Search Console** (Pas 3).

Bona sort! 🚀
