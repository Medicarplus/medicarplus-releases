# Guia · Notificacions Discord per rebre alertes de suport al mòbil

**Objectiu:** Rebre notificacions push instantànies al teu mòbil (i al PC) cada vegada que un client:
- 🖥️ Demani assistència remota (mostrarà telèfon, nom, ID HopToDesk).
- 🐛 Reporti un bug.
- 💬 Envii una consulta.

**Temps:** 5 minuts.
**Cost:** 100% gratuït.
**Compte a usar:** el teu Discord personal.

---

## 📱 Pas 1 · Instal·la Discord al mòbil

1. App Store (iPhone) o Play Store (Android) → cerca **"Discord"** → instal·la.
2. Registra't (o inicia sessió amb el teu compte).
3. Assegura't que les **notificacions push** de l'app estan activades a la configuració del mòbil.

**Opcional però recomanat:** instal·la també Discord al teu ordinador des de https://discord.com/download

---

## 🏗️ Pas 2 · Crea el teu servidor Discord privat

1. Obre Discord (mòbil o PC).
2. A la barra lateral esquerra, cliqueu el botó **"+"** (Afegir servidor).
3. Selecciona **"Crear el meu propi"** ▸ **"Solo per mi i els meus amics"**.
4. Nom del servidor: `MediCar Plus · Alertes` (o el que vulguis).
5. Icona: opcional (pots posar el logo de MediCar).
6. Cliqueu **Crear**.

Ara tens un servidor privat només per tu. Ningú més hi pot entrar.

---

## ⚙️ Pas 3 · Configura el webhook

1. Al teu servidor nou, apareixerà un canal per defecte anomenat `#general`.
2. **PC**: Passa el ratolí per sobre de `#general` → apareix una **rodeta** ⚙️ a la dreta → clic-la.
   **Mòbil**: Deixa el dit apretat sobre `#general` → apareix menú → tria "Editar canal".
3. Al menú lateral esquerre, tria **"Integracions"**.
4. Cliqueu **"Webhooks"** ▸ **"Nou Webhook"**.
5. Discord crearà automàticament un webhook amb un nom (ex: "Captain Hook").
6. Personalitza (opcional):
   - Nom: `MediCar Plus Bot`
   - Avatar: pots pujar un logo si vols.
7. Cliqueu **"Copiar URL del webhook"**.

**⚠️ IMPORTANT:** Aquesta URL és secreta. **NO la comparteixis amb ningú**. Qualsevol que la tingui pot enviar missatges al teu Discord.

---

## 🔧 Pas 4 · Enganxa la URL al backend

**Opció A · Des d'Emergent (recomanat)**
1. Al chat d'Emergent, escriu: `Configura DISCORD_WEBHOOK_URL amb aquesta URL: https://discord.com/api/webhooks/XXXXXX/YYYY`
2. Jo (agent) actualitzaré el `.env` automàticament i faré restart del backend.

**Opció B · Directe al `.env`** (si tens accés directe)
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/XXXXXX/YYYY
```

Un cop desat, cal fer **Deploy** perquè els canvis arribin a producció.

---

## 🧪 Pas 5 · Prova que funciona

1. Obre l'app MediCar Plus (mode Master o Client).
2. Ves a **⚙️ Configuración ▸ 🖥️ Solicitar asistencia remota**.
3. Omple els camps (nom, telèfon, ID HopToDesk, problema).
4. Cliqueu **"🖥️ Solicitar asistencia ahora"**.
5. En 1-2 segons, hauries de rebre una notificació **push al mòbil** i veure-la al canal `#general` del teu Discord.

Si no rebus res:
- Comprova que la URL del webhook s'ha copiat correctament (sense espais al principi/final).
- Comprova que les notificacions push del mòbil estan activades.
- Cerca el missatge al canal `#general` (potser només arriba a Discord PC si el mòbil està silenciat).

---

## 📊 Què veuràs a la notificació

Quan un client demana assistència remota, rebràs un missatge com aquest:

```
🖥️ SOL·LICITUD ASSISTÈNCIA REMOTA

Problema:
Quan faig una revisió i vull marcar-la com apte, em surt error…

📞 Telèfon: +34 972 34 56 78     🏥 Centre: Autoescola Costa Brava
👤 Contacte: Maria Puig           ✉️ Email: maria@autoescolacb.com

🖥️ ID HopToDesk: 123-456-789
Versió app: 2.4.3

Ticket: 7240686a
```

- El **telèfon** s'auto-detecta com a clicable al Discord mòbil (un toc i truca).
- L'**ID HopToDesk** és copiable amb un tap llarg.
- Al PC, tot es mostra amb format ric (colors, camps).

---

## 🛠️ Configuracions extra (opcional)

**Silenciar durant la nit:**
- Al servidor Discord → clic dret al servidor → **"Silenciar servidor"** → tria 8 hores, 24h, o personalitzat.

**Filtrar per tipus (avançat):**
- Pots crear diferents canals (`#bugs`, `#trucades`, `#consultes`) amb webhooks diferents i afegir-los al codi. Actualment tot va al mateix canal.

**Alertes al PC:**
- Instal·la Discord Desktop i activa les notificacions natives Windows → rebràs pop-ups mentre treballes.

---

## 🆘 Si et bloqueges

Digue'm quin pas i què veus a la pantalla, i te l'explico. Els punts crítics són:

1. **Crear el servidor Discord** (Pas 2).
2. **Obtenir la URL del webhook** (Pas 3).
3. **Enganxar-la al `.env`** i redesplegar (Pas 4).

Bona sort! 🚀
