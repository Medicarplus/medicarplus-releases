"""
Notifications router · SMS/WhatsApp bulk sending via Twilio
POST /api/notifications/send
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/notifications", tags=["notifications"])


class MessageEntry(BaseModel):
    nom: str
    telefon: str
    dni: Optional[str] = ""
    body: str


class ChannelsPayload(BaseModel):
    sms: bool = True
    whatsapp: bool = False


class SendPayload(BaseModel):
    channels: ChannelsPayload
    messages: List[MessageEntry]


class SendResult(BaseModel):
    telefon: str
    nom: str
    ok: bool
    sms_sid: Optional[str] = None
    wa_sid: Optional[str] = None
    error: Optional[str] = None


def _twilio_client():
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    if not sid or not token:
        raise HTTPException(
            status_code=503,
            detail="Twilio no està configurat. Falten TWILIO_ACCOUNT_SID i TWILIO_AUTH_TOKEN al servidor.",
        )
    try:
        from twilio.rest import Client
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Twilio SDK no instal·lat al servidor (pip install twilio).",
        )
    return Client(sid, token)


@router.post("/send")
async def send_bulk(payload: SendPayload):
    if not payload.messages:
        raise HTTPException(status_code=400, detail="No hi ha missatges a enviar.")
    if not payload.channels.sms and not payload.channels.whatsapp:
        raise HTTPException(status_code=400, detail="Selecciona almenys un canal (SMS o WhatsApp).")

    client = _twilio_client()
    from_sms = os.environ.get("TWILIO_SMS_FROM", "").strip()
    from_wa = os.environ.get("TWILIO_WHATSAPP_FROM", "").strip()  # ex: "whatsapp:+14155238886"

    if payload.channels.sms and not from_sms:
        raise HTTPException(status_code=503, detail="Falta TWILIO_SMS_FROM (número emissor SMS) al servidor.")
    if payload.channels.whatsapp and not from_wa:
        raise HTTPException(status_code=503, detail="Falta TWILIO_WHATSAPP_FROM (ex: whatsapp:+14155238886) al servidor.")

    results = []
    for m in payload.messages:
        r = {"telefon": m.telefon, "nom": m.nom, "ok": False, "sms_sid": None, "wa_sid": None, "error": None}
        errs = []
        if payload.channels.sms:
            try:
                msg = client.messages.create(from_=from_sms, to=m.telefon, body=m.body)
                r["sms_sid"] = msg.sid
            except Exception as e:
                errs.append(f"SMS: {e}")
        if payload.channels.whatsapp:
            try:
                to_wa = m.telefon if m.telefon.startswith("whatsapp:") else f"whatsapp:{m.telefon}"
                msg = client.messages.create(from_=from_wa, to=to_wa, body=m.body)
                r["wa_sid"] = msg.sid
            except Exception as e:
                errs.append(f"WhatsApp: {e}")
        if errs:
            r["error"] = " · ".join(errs)
        r["ok"] = r["sms_sid"] is not None or r["wa_sid"] is not None
        results.append(r)

    ok_count = sum(1 for r in results if r["ok"])
    return {"total": len(results), "ok": ok_count, "failed": len(results) - ok_count, "results": results}


@router.get("/status")
async def twilio_status():
    """Comprova si Twilio està configurat (sense fer cap trucada externa)."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    from_sms = os.environ.get("TWILIO_SMS_FROM", "").strip()
    from_wa = os.environ.get("TWILIO_WHATSAPP_FROM", "").strip()
    return {
        "configured": bool(sid and token),
        "sms_ready": bool(sid and token and from_sms),
        "whatsapp_ready": bool(sid and token and from_wa),
    }
