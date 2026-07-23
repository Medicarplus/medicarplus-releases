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
    # BYOA: credencials Twilio del client (opcionals). Si es passen, s'usen només
    # per aquesta petició. NO es persisteixen al backend.
    twilio_creds: Optional[dict] = None  # {"sid": "...", "token": "...", "from": "+34..."}


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


def _send_sms(mobile: str, message: str, creds: Optional[dict] = None) -> tuple[bool, str]:
    """Envia SMS via Twilio. Prioritat:
    1) Credencials passades per la request (BYOA · Bring Your Own Account).
    2) Credencials globals del .env (fallback per master/admin).
    3) MODE MOCK si res configurat.
    Retorna (ok, detail).
    """
    user_creds = _extract_creds(creds)
    if user_creds:
        sid, token, from_num = user_creds
    elif _has_twilio():
        sid = os.environ["TWILIO_ACCOUNT_SID"]
        token = os.environ["TWILIO_AUTH_TOKEN"]
        from_num = os.environ["TWILIO_FROM_NUMBER"]
    else:
        # MODE PROVA — no envia res, marca com si s'hagués enviat
        return True, "mock:no-twilio"
    try:
        from twilio.rest import Client  # type: ignore
        client = Client(sid, token)
        msg = client.messages.create(
            to=f"+34{mobile}",
            from_=from_num,
            body=message,
        )
        return True, f"sid:{msg.sid}"
    except Exception as e:
        return False, f"error:{str(e)[:200]}"


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

    @router.post("/campaigns")
    async def create_campaign(
        body: SmsCampaignCreate,
        x_admin_token: Optional[str] = Header(None),
    ):
        _admin(x_admin_token)

        campaign_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Filtra només contactes vàlids
        valid_contacts = [c for c in body.contacts if c.get("mobile")]
        invalid_contacts = [c for c in body.contacts if not c.get("mobile")]

        sent_count = 0
        error_count = 0
        processed_contacts = []

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
            ok, detail = _send_sms(c["mobile"], msg, creds=body.twilio_creds)
            if ok:
                sent_count += 1
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

        # Determinar si es va utilitzar Twilio real (BYOA o global) o mock
        used_twilio_real = bool(_extract_creds(body.twilio_creds)) or _has_twilio()

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
            "twilio_source": "byoa" if _extract_creds(body.twilio_creds) else ("global" if _has_twilio() else "mock"),
        }
        await db.sms_campaigns.insert_one(doc)

        return {
            "ok": True,
            "campaign_id": campaign_id,
            "sent_count": sent_count,
            "error_count": error_count,
            "filtered_invalid": len(invalid_contacts),
            "status": status,
            "twilio_mode": "real" if used_twilio_real else "mock",
            "twilio_source": doc["twilio_source"],
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

    return router
