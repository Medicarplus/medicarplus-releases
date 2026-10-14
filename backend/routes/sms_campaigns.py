"""
SMS Campaigns · Mòdul complet d'avisos amb tongades i estadístiques
Marc Brugulat Lopez · 2026
====================================================================
· Import CSV (columnes: Numero, Nombre, Apellido1, Apellido2, Movil, Telefono, FechaRevision)
· Filtra automàticament: només mòbils espanyols (comencen per 6 o 7)
· Guarda campanya amb estats per contacte (sent, error, motiu)
· Cerca per nom/cognom dins una campanya
· Estadístiques agregades
· MODE PROVA activat mentre TWILIO_ACCOUNT_SID no estigui al .env
    → els SMS es marquen com "sent-mock" i NO s'envien de veritat
    → quan l'usuari configuri Twilio → real
"""
import os
import io
import csv
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sms", tags=["sms"])

# --- Regex mòbil espanyol (comença per 6 o 7 + 8 dígits) ---
MOBILE_RE = re.compile(r"^(?:\+?34)?\s*([67]\d{8})$")


def normalize_mobile(raw: str) -> Optional[str]:
    """Retorna el mòbil normalitzat (9 dígits començant per 6/7) o None si invàlid."""
    if not raw:
        return None
    # Neteja espais, guions, punts
    cleaned = re.sub(r"[\s\-.()]", "", str(raw))
    m = MOBILE_RE.match(cleaned)
    if not m:
        return None
    return m.group(1)


def _admin(x_admin_token: Optional[str]) -> None:
    admin_token = os.environ.get("LICENSE_ADMIN_TOKEN", "")
    if not admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=401, detail="unauthorized")


class SmsContactPreview(BaseModel):
    external_id: str = ""
    name: str
    surname1: str = ""
    surname2: str = ""
    mobile: Optional[str] = None       # None → invàlid (fix o buit)
    landline: Optional[str] = None     # informatiu (per fixos)
    revision_date: Optional[str] = None
    valid: bool = False                # true si té mòbil vàlid
    reason: Optional[str] = None       # motiu de invalidez


class SmsCampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    template: str = Field(..., min_length=10, max_length=1600)
    contacts: List[dict]  # llista de contacts que passin
    # ─── Twilio billing mode ────────────────────────────────────────────
    # BYOA: credencials Twilio del client (mode 'byoa')
    twilio_creds: Optional[dict] = None  # {"sid": "...", "token": "...", "from": "+34..."}
    # Mode 'medicar': usa el compte central de MediCar Plus (només Premium).
    # El client no envia creds; només decideix el remitent (Alphanumeric Sender)
    # perquè els pacients rebin els SMS amb el nom del CENTRE, no de MediCar.
    use_medicar: bool = False
    medicar_sender: Optional[str] = None   # Alphanumeric Sender (1-11 chars, sense espais)
    # Identifica al client centre per tracking de consum a MongoDB
    install_id: Optional[str] = None
    client_name: Optional[str] = None


class TwilioTestReq(BaseModel):
    sid: str = Field(..., min_length=10)
    token: str = Field(..., min_length=10)
    from_number: str = Field(..., min_length=6)


class Campaign(BaseModel):
    id: str
    name: str
    template: str
    created_at: str
    status: str
    total: int
    sent_count: int
    error_count: int
    filtered_invalid: int


def render_template(tpl: str, ctx: dict) -> str:
    """Reemplaça {{var}} amb els valors del context."""
    out = tpl
    for k, v in ctx.items():
        out = out.replace("{{" + k + "}}", str(v or ""))
    return out


def _has_twilio() -> bool:
    return bool(
        os.environ.get("TWILIO_ACCOUNT_SID")
        and os.environ.get("TWILIO_AUTH_TOKEN")
        and os.environ.get("TWILIO_FROM_NUMBER")
    )


def _extract_creds(creds: Optional[dict]) -> Optional[tuple]:
    """Retorna (sid, token, from) si les creds són vàlides, None altrament."""
    if not creds or not isinstance(creds, dict):
        return None
    sid = (creds.get("sid") or "").strip()
    token = (creds.get("token") or "").strip()
    from_num = (creds.get("from") or "").strip()
    if sid and token and from_num:
        return sid, token, from_num
    return None


def _creds_incomplete(creds: Optional[dict]) -> Optional[str]:
    """Si el client ha enviat sid/token però falta un camp (típicament 'from'),
    retorna un missatge concret per fer-ho visible al UI. None si tot OK o buit."""
    if not creds or not isinstance(creds, dict):
        return None
    sid = (creds.get("sid") or "").strip()
    token = (creds.get("token") or "").strip()
    from_num = (creds.get("from") or "").strip()
    if (sid or token) and not (sid and token and from_num):
        miss = []
        if not sid: miss.append("Account SID")
        if not token: miss.append("Auth Token")
        if not from_num: miss.append("Remitente (From)")
        return "Credenciales Twilio incompletas · falta: " + ", ".join(miss)
    return None


def _get_sms_price_eur() -> float:
    """Preu per SMS a facturar al client = cost Twilio + marge.
    Vars: MEDICAR_SMS_TWILIO_COST_EUR + MEDICAR_SMS_MARGIN_EUR (fallback: MEDICAR_SMS_PRICE_EUR)"""
    try:
        cost = float(os.environ.get("MEDICAR_SMS_TWILIO_COST_EUR", "").strip() or "0")
        margin = float(os.environ.get("MEDICAR_SMS_MARGIN_EUR", "").strip() or "0")
        if cost > 0 or margin > 0:
            return round(cost + margin, 4)
        return _get_sms_price_eur()
    except Exception:
        return 0.10


def _sanitize_alpha_sender(s: str) -> str:
    """Twilio Alphanumeric Sender ID: màxim 11 caràcters, alfanumèric,
    admet lletres i dígits. Espais/accents fora."""
    import re
    if not s:
        return ""
    # Elimina accents i caràcters no ASCII
    import unicodedata
    normalized = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9]", "", normalized)
    return cleaned[:11]


def _send_sms(
    mobile: str,
    message: str,
    creds: Optional[dict] = None,
    use_medicar: bool = False,
    medicar_sender: Optional[str] = None,
) -> tuple[bool, str, str]:
    """Envia SMS via Twilio. Retorna (ok, detail, source).

    Modes (per prioritat):
    1) use_medicar=True + env creds configurades → compte MediCar Plus + sender custom.
       source='medicar'
    2) creds válides al payload → BYOA (compte del client). source='byoa'
    3) Env creds configurades → fallback per master/admin. source='env'
    4) Res configurat → MOCK. source='mock'
    """
    # Mode MediCar centralitzat
    if use_medicar:
        if not _has_twilio():
            return False, "error:medicar_twilio_not_configured", "medicar_unavailable"
        sid = os.environ["TWILIO_ACCOUNT_SID"]
        token = os.environ["TWILIO_AUTH_TOKEN"]
        # Alphanumeric Sender custom del client (nom del centre)
        sender = _sanitize_alpha_sender(medicar_sender or "")
        from_num = sender if sender else os.environ["TWILIO_FROM_NUMBER"]
        source = "medicar"
    else:
        user_creds = _extract_creds(creds)
        if user_creds:
            sid, token, from_num = user_creds
            source = "byoa"
        else:
            # 🚦 Feb 2026 · Si venen creds però incompletes (típic: falta From),
            #   fallem RÀPID amb el missatge concret en lloc d'anar al fallback env.
            inc = _creds_incomplete(creds)
            if inc:
                return False, f"error:{inc}", "byoa_incomplete"
            if _has_twilio():
                sid = os.environ["TWILIO_ACCOUNT_SID"]
                token = os.environ["TWILIO_AUTH_TOKEN"]
                from_num = os.environ["TWILIO_FROM_NUMBER"]
                source = "env"
            else:
                # MODE PROVA — no envia res, marca com si s'hagués enviat
                return True, "mock:no-twilio", "mock"
    try:
        from twilio.rest import Client  # type: ignore
        client = Client(sid, token)
        # 🔧 Feb 2026 · Sanitización E.164 robusta
        #   El móvil puede venir como "612345678" / "+34612345678" / "34 612 345 678" /
        #   "612-345-678". Normalizamos siempre a "+34XXXXXXXXX" (España) sin que se
        #   duplique el prefijo. Si el número ya trae otro código internacional (+33,
        #   +44, +376, +351…) lo respetamos tal cual.
        raw = (mobile or "").strip()
        # Deja solo dígitos y '+' inicial
        if raw.startswith("+"):
            digits = "+" + "".join(ch for ch in raw[1:] if ch.isdigit())
            to_number = digits
        else:
            digits = "".join(ch for ch in raw if ch.isdigit())
            # Quita 00 inicial (notación internacional alternativa 0034 → 34)
            if digits.startswith("00"): digits = digits[2:]
            # Si ya empieza por 34 y tiene 11 dígitos (ES completo), añade "+"
            if digits.startswith("34") and len(digits) == 11:
                to_number = "+" + digits
            else:
                to_number = "+34" + digits
        msg = client.messages.create(
            to=to_number,
            from_=from_num,
            body=message,
        )
        return True, f"sid:{msg.sid}", source
    except Exception as e:
        return False, f"error:{str(e)[:300]}", source


def build_router(db):
    """
    Endpoints:
        POST   /api/sms/preview            — puja CSV i retorna llista de contactes amb valid=True/False
        POST   /api/sms/campaigns          — crea + envia una campanya
        GET    /api/sms/campaigns          — llista de campanyes (històric)
        GET    /api/sms/campaigns/{id}     — detalls (contactes amb estat)
        GET    /api/sms/stats              — estadístiques agregades
        POST   /api/sms/test-credentials   — valida credencials Twilio BYOA (fa una crida read-only a Twilio)
    Tots requereixen X-Admin-Token (només l'usuari master pot enviar).
    """

    @router.post("/test-credentials")
    async def test_credentials(
        body: TwilioTestReq,
        x_admin_token: Optional[str] = Header(None),
    ):
        _admin(x_admin_token)
        sid = body.sid.strip()
        token = body.token.strip()
        from_num = body.from_number.strip()
        try:
            from twilio.rest import Client  # type: ignore
            client = Client(sid, token)
            # Comprovació 1: fetch account info (valida SID + Token)
            acc = client.api.accounts(sid).fetch()
            acc_name = getattr(acc, "friendly_name", None) or sid
            acc_status = getattr(acc, "status", "unknown")
            # Comprovació 2: verifica que el número from existeix al compte
            numbers = client.incoming_phone_numbers.list(phone_number=from_num, limit=1)
            from_valid = len(numbers) > 0
            # Alternativa: pot ser un Alphanumeric Sender ID → no apareix a incoming_phone_numbers
            if not from_valid and not from_num.startswith("+"):
                # Assumim que és Alphanumeric Sender (Espanya el permet). Twilio l'accepta sense validació prèvia.
                from_valid = True
                from_kind = "alphanumeric"
            else:
                from_kind = "phone_number" if from_valid else "unknown"
            return {
                "ok": True,
                "account_name": acc_name,
                "account_status": acc_status,
                "from_valid": from_valid,
                "from_kind": from_kind,
            }
        except Exception as e:
            emsg = str(e)
            # Detecta errors comuns per donar missatge amigable
            lower = emsg.lower()
            if "authenticate" in lower or "20003" in lower:
                reason = "credentials_invalid"
            elif "not found" in lower or "20404" in lower:
                reason = "account_not_found"
            else:
                reason = "unknown_error"
            return {
                "ok": False,
                "reason": reason,
                "detail": emsg[:250],
            }

    @router.post("/preview")
    async def preview_csv(
        file: UploadFile = File(...),
        x_admin_token: Optional[str] = Header(None),
    ):
        _admin(x_admin_token)
        try:
            raw = (await file.read()).decode("utf-8-sig", errors="replace")
        except Exception:
            raise HTTPException(status_code=400, detail="cannot read file")

        # Sniff delimiter (comma or semicolon)
        try:
            dialect = csv.Sniffer().sniff(raw[:2000], delimiters=";,\t")
        except csv.Error:
            class D:
                delimiter = ";"
            dialect = D()

        reader = csv.DictReader(io.StringIO(raw), dialect=dialect)
        contacts: List[dict] = []
        valid_count = 0
        invalid_count = 0
        duplicate_count = 0
        seen_mobiles: dict = {}  # mobile → index del primer contacte que el té

        # Normalitza noms de capçalera (majúsc + espais)
        def col(row: dict, *aliases: str) -> str:
            for a in aliases:
                for k in row.keys():
                    if k and k.strip().lower() == a.lower():
                        return (row[k] or "").strip()
            return ""

        for row in reader:
            if not row:
                continue
            name = col(row, "Nombre", "NOMBRE", "NOM")
            surname1 = col(row, "Apellido1", "APELLIDO1", "COGNOM1", "APELLIDOS")
            surname2 = col(row, "Apellido2", "APELLIDO2", "COGNOM2")
            movil_raw = col(row, "Movil", "MOVIL", "MÓVIL", "MOBIL", "Mòbil")
            fijo_raw = col(row, "Telefono", "TELEFONO", "TELÉFONO", "TELEFON", "FIJO")
            rev = col(row, "FechaRevision", "FECHAREVISION", "FechaCaducidad", "REVISION")
            ext_id = col(row, "Numero", "NUMERO", "ID")

            if not (name or surname1):
                continue

            mobile = normalize_mobile(movil_raw)
            reason = None
            if not mobile:
                # Prova si el "telèfon" en canvi és mòbil
                mobile = normalize_mobile(fijo_raw)
            is_duplicate = False
            if mobile and mobile in seen_mobiles:
                # Aquest mòbil ja el tenim en un contacte anterior — dupliqué
                is_duplicate = True
                reason = f"duplicat (ja al contacte #{seen_mobiles[mobile]+1})"
                duplicate_count += 1
                mobile_final = None  # No l'incluim al llistat de vàlids
            elif mobile:
                seen_mobiles[mobile] = len(contacts)
                mobile_final = mobile
                valid_count += 1
            else:
                if movil_raw or fijo_raw:
                    reason = "no és mòbil (comença per 9)"
                else:
                    reason = "sense telèfon"
                invalid_count += 1
                mobile_final = None

            contacts.append({
                "external_id": ext_id,
                "name": name,
                "surname1": surname1,
                "surname2": surname2,
                "mobile": mobile_final,
                "landline": fijo_raw if not mobile_final else None,
                "revision_date": rev,
                "valid": mobile_final is not None,
                "reason": reason,
                "duplicate": is_duplicate,
            })

        return {
            "ok": True,
            "total_rows": len(contacts),
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "duplicate_count": duplicate_count,
            "contacts": contacts,
            "twilio_configured": _has_twilio(),
        }

    @router.get("/my-usage")
    async def my_usage(install_id: str):
        """Endpoint PÚBLIC (només requereix install_id) perquè el client vegi
        el seu propi consum SMS mode 'medicar' del mes actual + estimació de cost.
        NO revela dades d'altres clients."""
        if not install_id:
            return {"install_id":"","period":"","sent_count":0,"cost_eur":0.0,"price_per_sms_eur":_get_sms_price_eur()}
        now_dt = datetime.now(timezone.utc)
        period = f"{now_dt.year:04d}-{now_dt.month:02d}"
        doc = await db.sms_usage_medicar.find_one({"install_id": install_id, "period": period})
        sent = int((doc or {}).get("sent_count", 0) or 0)
        price = _get_sms_price_eur()
        return {
            "install_id": install_id,
            "period": period,
            "sent_count": sent,
            "cost_eur": round(sent * price, 2),
            "price_per_sms_eur": price,
            "billed": bool((doc or {}).get("billed", False)),
        }

    @router.get("/medicar-availability")
    async def medicar_availability():
        """Retorna si el compte central MediCar Plus per SMS està operatiu.
        Útil pel frontend per mostrar l'opció 'Usar cuenta MediCar' com a
        disponible/pendent. No requereix admin token (info pública).
        """
        return {
            "available": _has_twilio(),
            "price_per_sms_eur": _get_sms_price_eur(),
        }

    @router.get("/medicar-usage")
    async def medicar_usage(
        install_id: Optional[str] = None,
        period: Optional[str] = None,  # YYYY-MM
        x_admin_token: Optional[str] = Header(None),
    ):
        """Retorna el consum SMS del mode 'medicar' per facturació metered.
        Si install_id → consum del client. Si no → agregat tots els clients.
        """
        _admin(x_admin_token)
        query: dict = {}
        if install_id:
            query["install_id"] = install_id
        if period:
            query["period"] = period
        cursor = db.sms_usage_medicar.find(query).sort("period", -1)
        items = [doc async for doc in cursor]
        price = _get_sms_price_eur()
        for it in items:
            it["_id"] = str(it.get("_id", ""))
            it["cost_estimated_eur"] = round(it.get("sent_count", 0) * price, 2)
        return {"items": items, "count": len(items), "price_per_sms_eur": price}

    @router.post("/campaigns")
    async def create_campaign(
        body: SmsCampaignCreate,
        x_admin_token: Optional[str] = Header(None),
    ):
        _admin(x_admin_token)

        # Si el client vol usar el compte MediCar però no està configurat, error clar
        if body.use_medicar and not _has_twilio():
            raise HTTPException(
                status_code=503,
                detail="La cuenta central MediCar Plus para SMS aún no está disponible. Configura tu cuenta propia de Twilio (BYOA) mientras tanto.",
            )

        campaign_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Filtra només contactes vàlids
        valid_contacts = [c for c in body.contacts if c.get("mobile")]
        invalid_contacts = [c for c in body.contacts if not c.get("mobile")]

        sent_count = 0
        error_count = 0
        processed_contacts = []
        source_final = "mock"

        for c in valid_contacts:
            ctx = {
                "nom": c.get("name", ""),
                "cognom": c.get("surname1", ""),
                "cognom2": c.get("surname2", ""),
                "nom_complet": f'{c.get("name","")} {c.get("surname1","")} {c.get("surname2","")}'.strip(),
                "mobil": c.get("mobile", ""),
                "data_caducitat": c.get("revision_date", ""),
                "data_revisio": c.get("revision_date", ""),
                "id": c.get("external_id", ""),
            }
            msg = render_template(body.template, ctx)
            ok, detail, source = _send_sms(
                c["mobile"], msg,
                creds=body.twilio_creds,
                use_medicar=body.use_medicar,
                medicar_sender=body.medicar_sender,
            )
            source_final = source  # es queda amb l'últim
            if ok:
                sent_count += 1
                # 💰 TRACKING ATÒMIC PER-MISSATGE (mode medicar)
                # Es fa immediatament després de cada SMS enviat amb èxit
                # perquè encara que la campanya crashi més tard, els SMS que ja
                # s'han cobrat a Twilio quedin comptabilitzats a la nostra facturació.
                if source == "medicar" and body.install_id:
                    try:
                        now_dt = datetime.now(timezone.utc)
                        period = f"{now_dt.year:04d}-{now_dt.month:02d}"
                        await db.sms_usage_medicar.update_one(
                            {"install_id": body.install_id, "period": period},
                            {
                                "$inc": {"sent_count": 1},
                                "$setOnInsert": {
                                    "install_id": body.install_id,
                                    "client_name": body.client_name or "",
                                    "period": period,
                                    "first_seen": now,
                                    "billed": False,
                                },
                                "$set": {
                                    "last_seen": datetime.now(timezone.utc).isoformat(),
                                    "medicar_sender": _sanitize_alpha_sender(body.medicar_sender or ""),
                                },
                            },
                            upsert=True,
                        )
                    except Exception as track_err:
                        # Guardem l'error a un log separat perquè no perdem la traça
                        try:
                            await db.sms_usage_errors.insert_one({
                                "install_id": body.install_id,
                                "campaign_id": campaign_id,
                                "mobile": c.get("mobile"),
                                "twilio_sid": detail.replace("sid:", ""),
                                "error": str(track_err)[:500],
                                "ts": datetime.now(timezone.utc).isoformat(),
                            })
                        except Exception:
                            pass
            else:
                error_count += 1
            processed_contacts.append({
                **c,
                "sent": ok,
                "detail": detail,
                "message_final": msg,
                "sent_at": datetime.now(timezone.utc).isoformat() if ok else None,
            })

        # Guarda els contactes invàlids per referència
        for c in invalid_contacts:
            processed_contacts.append({
                **c,
                "sent": False,
                "detail": c.get("reason", "invalid"),
                "message_final": None,
                "sent_at": None,
            })

        # Determinar si es va utilitzar Twilio real
        used_twilio_real = source_final in ("medicar", "byoa", "env")

        status = "sent" if error_count == 0 else ("partial" if sent_count > 0 else "failed")

        doc = {
            "_id": campaign_id,
            "name": body.name,
            "template": body.template,
            "created_at": now,
            "status": status,
            "total": len(body.contacts),
            "sent_count": sent_count,
            "error_count": error_count,
            "filtered_invalid": len(invalid_contacts),
            "contacts": processed_contacts,
            "twilio_used": used_twilio_real,
            "twilio_source": source_final,
            "install_id": body.install_id or None,
            "client_name": body.client_name or None,
            "medicar_sender": _sanitize_alpha_sender(body.medicar_sender) if body.use_medicar else None,
        }
        await db.sms_campaigns.insert_one(doc)

        # NOTA: El tracking del consum SMS pel mode 'medicar' es fa
        # de forma ATÒMICA per cada SMS enviat (dins el bucle anterior)
        # per garantir que ni un sol SMS enviat es perdi de comptabilitzar.
        # Aquí només afegim la campaign_id a la llista per consultes.
        if source_final == "medicar" and sent_count > 0 and body.install_id:
            try:
                now_dt = datetime.now(timezone.utc)
                period = f"{now_dt.year:04d}-{now_dt.month:02d}"
                await db.sms_usage_medicar.update_one(
                    {"install_id": body.install_id, "period": period},
                    {"$push": {"campaign_ids": campaign_id}},
                )
            except Exception:
                pass

        return {
            "ok": True,
            "campaign_id": campaign_id,
            "sent_count": sent_count,
            "error_count": error_count,
            "filtered_invalid": len(invalid_contacts),
            "status": status,
            "twilio_mode": "real" if used_twilio_real else "mock",
            "twilio_source": source_final,
            # 🔧 Feb 2026 · Muestra de errores para que el usuario sepa qué pasó
            #   (antes solo veía "Errores: 1" sin motivo). Enseñamos hasta 5
            #   contactos con el error real devuelto por Twilio.
            "errors_sample": [
                {
                    "name": f'{c.get("name","")} {c.get("surname1","")}'.strip() or c.get("mobile",""),
                    "mobile": c.get("mobile",""),
                    "detail": (c.get("detail") or "").replace("error:", "").strip(),
                }
                for c in processed_contacts
                if c.get("sent") is False and (c.get("detail") or "").startswith("error:")
            ][:5],
        }

    @router.get("/campaigns")
    async def list_campaigns(x_admin_token: Optional[str] = Header(None)):
        _admin(x_admin_token)
        cursor = db.sms_campaigns.find(
            {}, projection={"contacts": 0}
        ).sort("created_at", -1).limit(200)
        items = []
        async for c in cursor:
            c["id"] = c.pop("_id", None)
            items.append(c)
        return {"campaigns": items, "count": len(items)}

    @router.get("/campaigns/{campaign_id}")
    async def get_campaign(
        campaign_id: str,
        q: str = "",
        x_admin_token: Optional[str] = Header(None),
    ):
        _admin(x_admin_token)
        doc = await db.sms_campaigns.find_one({"_id": campaign_id})
        if not doc:
            raise HTTPException(status_code=404, detail="not found")
        doc["id"] = doc.pop("_id", None)
        # Cerca per nom/cognom si q donat
        if q:
            q_lower = q.lower().strip()
            doc["contacts"] = [
                c for c in doc.get("contacts", [])
                if q_lower in (
                    (c.get("name") or "") + " " +
                    (c.get("surname1") or "") + " " +
                    (c.get("surname2") or "")
                ).lower()
            ]
        return doc

    @router.delete("/campaigns/{campaign_id}")
    async def delete_campaign(
        campaign_id: str,
        x_admin_token: Optional[str] = Header(None),
    ):
        _admin(x_admin_token)
        res = await db.sms_campaigns.delete_one({"_id": campaign_id})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="not found")
        return {"ok": True, "deleted_id": campaign_id}

    @router.get("/stats")
    async def stats(x_admin_token: Optional[str] = Header(None)):
        _admin(x_admin_token)
        cursor = db.sms_campaigns.find({}, projection={"contacts": 0}).sort("created_at", -1)
        total_campaigns = 0
        total_sent = 0
        total_errors = 0
        total_invalid = 0
        by_month: dict = {}
        recent = []
        async for c in cursor:
            total_campaigns += 1
            total_sent += c.get("sent_count", 0)
            total_errors += c.get("error_count", 0)
            total_invalid += c.get("filtered_invalid", 0)
            month_key = (c.get("created_at") or "")[:7]  # YYYY-MM
            if month_key:
                by_month[month_key] = by_month.get(month_key, 0) + c.get("sent_count", 0)
            if len(recent) < 5:
                recent.append({
                    "id": c.get("_id"),
                    "name": c.get("name"),
                    "created_at": c.get("created_at"),
                    "sent_count": c.get("sent_count", 0),
                    "error_count": c.get("error_count", 0),
                })
        return {
            "total_campaigns": total_campaigns,
            "total_sent": total_sent,
            "total_errors": total_errors,
            "total_invalid": total_invalid,
            "by_month": [{"month": k, "sent": v} for k, v in sorted(by_month.items(), reverse=True)],
            "recent_campaigns": recent,
            "twilio_mode": "real" if _has_twilio() else "mock",
        }

    @router.get("/search-recipients")
    async def search_recipients(
        q: str = "",
        limit: int = 50,
        x_admin_token: Optional[str] = Header(None),
    ):
        """Búsqueda global: encuentra destinatarios (por nombre/apellidos/móvil) en TODAS las campañas.

        Devuelve hasta `limit` coincidencias, agrupadas por campaña, con el nombre del contacto,
        móvil, estado del envío y campaña de origen. Útil para responder "¿A quién le mandé este SMS?".
        """
        _admin(x_admin_token)
        q_lower = (q or "").strip().lower()
        if len(q_lower) < 2:
            return {"query": q, "results": [], "total": 0, "truncated": False}
        cursor = db.sms_campaigns.find({}).sort("created_at", -1)
        results = []
        truncated = False
        async for c in cursor:
            if len(results) >= limit:
                truncated = True
                break
            camp_id = c.get("_id")
            camp_name = c.get("name") or "—"
            camp_date = c.get("created_at") or ""
            for contact in c.get("contacts", []) or []:
                if len(results) >= limit:
                    truncated = True
                    break
                haystack = " ".join([
                    str(contact.get("name") or ""),
                    str(contact.get("surname1") or ""),
                    str(contact.get("surname2") or ""),
                    str(contact.get("phone") or ""),
                    str(contact.get("original_phone") or ""),
                ]).lower()
                if q_lower in haystack:
                    results.append({
                        "campaign_id": camp_id,
                        "campaign_name": camp_name,
                        "campaign_date": camp_date,
                        "name": contact.get("name"),
                        "surname1": contact.get("surname1"),
                        "surname2": contact.get("surname2"),
                        "phone": contact.get("phone") or contact.get("original_phone"),
                        "status": contact.get("status") or "-",
                        "revision_date": contact.get("revision_date"),
                    })
        return {"query": q, "results": results, "total": len(results), "truncated": truncated}

    # ────────────────────────────────────────────────────────────────
    # 🗂️ BACKUP / RESTORE SMS (Feb 2026)
    # Endpoints PÚBLICS (només install_id) perquè el client pugui
    # incloure les estadístiques SMS del servidor dins la seva
    # còpia de seguretat i restaurar-les si un dia esborra tot i
    # torna a instal·lar (potser amb un nou install_id).
    # ────────────────────────────────────────────────────────────────
    @router.get("/backup-export")
    async def backup_export_sms(install_id: str):
        """Exporta TOTES les campanyes SMS + consum mensual d'un install_id.

        Retorna una estructura serialitzable que el client pot embeure
        dins la seva còpia de seguretat local/núvol. No requereix admin
        token perquè el client és propietari de les seves pròpies dades.
        """
        if not install_id:
            return {"install_id": "", "campaigns": [], "usage": [], "count": 0}
        # Campanyes: filtrar per install_id (les campanyes tenen install_id opcional)
        camp_cursor = db.sms_campaigns.find({"install_id": install_id}).sort("created_at", -1)
        campaigns = []
        async for c in camp_cursor:
            c["id"] = c.pop("_id", None)
            campaigns.append(c)
        # Consum mensual medicar
        usage_cursor = db.sms_usage_medicar.find({"install_id": install_id}).sort("period", -1)
        usage = []
        async for u in usage_cursor:
            u["_id"] = str(u.get("_id", ""))
            usage.append(u)
        return {
            "install_id": install_id,
            "campaigns": campaigns,
            "usage": usage,
            "count": len(campaigns),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

    class SmsBackupImportReq(BaseModel):
        install_id: str
        campaigns: List[dict] = []
        usage: List[dict] = []

    @router.post("/backup-import")
    async def backup_import_sms(body: SmsBackupImportReq):
        """Restaura campanyes + consum SMS d'una còpia dins l'install_id actual.

        - Fa UPSERT per campanya (id → _id). Si ja existeix, s'actualitza.
        - Fa UPSERT per consum mensual (install_id + period).
        - Re-etiqueta TOTES les campanyes amb el nou install_id (per si el PC
          es nou i l'install_id ha canviat) perquè la llista /campaigns torni
          a veure-les tal com estaven.
        """
        if not body.install_id:
            raise HTTPException(status_code=400, detail="install_id_required")
        target_install = body.install_id
        camp_restored = 0
        usage_restored = 0
        for c in (body.campaigns or []):
            if not isinstance(c, dict):
                continue
            cid = c.get("id") or c.get("_id") or str(uuid.uuid4())
            doc = {k: v for k, v in c.items() if k not in ("id", "_id")}
            doc["_id"] = cid
            # Re-atar al install_id actual per si ha canviat de PC
            doc["install_id"] = target_install
            try:
                await db.sms_campaigns.update_one(
                    {"_id": cid},
                    {"$set": doc},
                    upsert=True,
                )
                camp_restored += 1
            except Exception as e:
                logger.warning(f"backup-import campaign {cid} fallada: {e}")
        for u in (body.usage or []):
            if not isinstance(u, dict):
                continue
            period = u.get("period")
            if not period:
                continue
            doc = {k: v for k, v in u.items() if k not in ("_id",)}
            doc["install_id"] = target_install
            doc["period"] = period
            try:
                await db.sms_usage_medicar.update_one(
                    {"install_id": target_install, "period": period},
                    {"$set": doc},
                    upsert=True,
                )
                usage_restored += 1
            except Exception as e:
                logger.warning(f"backup-import usage {period} fallada: {e}")
        return {
            "ok": True,
            "install_id": target_install,
            "campaigns_restored": camp_restored,
            "usage_periods_restored": usage_restored,
        }

    return router
