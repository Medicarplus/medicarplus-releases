"""
Support router · Formulari de contacte dins l'app comercial
POST /api/support/contact → guarda el ticket a MongoDB + intenta enviar email (si SMTP està configurat)
POST /api/support/remote-assist → registra una sol·licitud d'assistència remota (HopToDesk) + notificació Telegram
GET  /api/support/tickets → llista tickets (protegit per LICENSE_ADMIN_TOKEN)
"""
import os
import uuid
import smtplib
import logging
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Header, Request, BackgroundTasks
from pydantic import BaseModel, Field, EmailStr

from services.discord_notify import (
    send_discord_notification,
    is_configured as discord_ok,
    COLOR_REMOTE_ASSIST, COLOR_BUG, COLOR_QUESTION, COLOR_BILLING, COLOR_GENERAL,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["support"])


class ContactPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    subject: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=4000)
    category: Optional[str] = "general"  # bug | question | billing | general
    app_version: Optional[str] = ""
    hwid: Optional[str] = ""
    license_key: Optional[str] = ""
    client_name: Optional[str] = ""


class ContactResult(BaseModel):
    ok: bool
    ticket_id: str
    email_sent: bool
    detail: Optional[str] = None


class RemoteAssistPayload(BaseModel):
    client_name: str = Field(..., min_length=1, max_length=120)
    contact_name: Optional[str] = ""  # persona que truca
    phone: str = Field(..., min_length=6, max_length=30)  # per si volem trucar-lo nosaltres
    email: Optional[EmailStr] = None
    hoptodesk_id: Optional[str] = ""  # ID de HopToDesk del client
    issue: str = Field(..., min_length=1, max_length=2000)
    app_version: Optional[str] = ""
    license_key: Optional[str] = ""
    install_id: Optional[str] = ""


def _send_email_smtp(payload: ContactPayload, ticket_id: str) -> tuple[bool, Optional[str]]:
    """Intenta enviar l'email via SMTP IONOS. Retorna (ok, error_msg)."""
    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    pwd = os.environ.get("SMTP_PASS", "").strip()
    port = int(os.environ.get("SMTP_PORT", "587") or 587)
    sender = os.environ.get("SMTP_FROM", user).strip() or user
    recipient = os.environ.get("SUPPORT_INBOX", "suport@medicarplus.es").strip()

    if not (host and user and pwd):
        return False, "SMTP no configurat"

    try:
        msg = EmailMessage()
        msg["Subject"] = f"[MediCar Plus · {payload.category.upper()}] {payload.subject}"
        msg["From"] = sender
        msg["To"] = recipient
        msg["Reply-To"] = payload.email
        body = (
            f"Ticket ID: {ticket_id}\n"
            f"Categoria: {payload.category}\n"
            f"---\n"
            f"Nom:     {payload.name}\n"
            f"Email:   {payload.email}\n"
            f"Client:  {payload.client_name or '(no informat)'}\n"
            f"Llicència: {payload.license_key or '(no informat)'}\n"
            f"App ver: {payload.app_version or '(no informat)'}\n"
            f"HWID:    {payload.hwid or '(no informat)'}\n"
            f"---\n\n"
            f"{payload.message}\n"
        )
        msg.set_content(body)

        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(user, pwd)
            smtp.send_message(msg)
        return True, None
    except Exception as e:
        logger.warning(f"SMTP send failed for ticket {ticket_id}: {e}")
        return False, str(e)


def build_router(db):
    @router.post("/contact", response_model=ContactResult)
    async def contact(body: ContactPayload, request: Request, background_tasks: BackgroundTasks):
        ticket_id = str(uuid.uuid4())
        doc = {
            "_id": ticket_id,
            "name": body.name,
            "email": body.email,
            "subject": body.subject,
            "message": body.message,
            "category": body.category or "general",
            "app_version": body.app_version or "",
            "hwid": body.hwid or "",
            "license_key": body.license_key or "",
            "client_name": body.client_name or "",
            "ip": request.client.host if request.client else "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "email_sent": False,
            "email_error": None,
            "status": "open",
        }

        ok, err = _send_email_smtp(body, ticket_id)
        doc["email_sent"] = ok
        doc["email_error"] = err

        await db.support_tickets.insert_one(doc)

        # 📱 Notificació Discord (async, no bloqueja resposta)
        if discord_ok():
            cat = (body.category or "general").upper()
            emoji_map = {"BUG":"🐛","QUESTION":"❓","BILLING":"💳","GENERAL":"💬"}
            color_map = {"BUG":COLOR_BUG,"QUESTION":COLOR_QUESTION,"BILLING":COLOR_BILLING,"GENERAL":COLOR_GENERAL}
            emoji = emoji_map.get(cat, "💬")
            color = color_map.get(cat, COLOR_GENERAL)
            background_tasks.add_task(
                send_discord_notification,
                title=f"{emoji} Nou ticket · {cat}",
                description=f"**{body.subject}**\n\n{body.message[:1500]}",
                color=color,
                fields=[
                    {"name": "De", "value": f"{body.name}\n{body.email}", "inline": True},
                    {"name": "Centre", "value": body.client_name or "—", "inline": True},
                    {"name": "Versió app", "value": body.app_version or "—", "inline": True},
                ],
                footer_text=f"Ticket ID: {ticket_id[:8]}",
            )

        return ContactResult(
            ok=True,
            ticket_id=ticket_id,
            email_sent=ok,
            detail=None if ok else "Ticket guardat. L'enviament d'email pot estar pendent de configuració SMTP.",
        )

    @router.post("/remote-assist")
    async def remote_assist(body: RemoteAssistPayload, request: Request, background_tasks: BackgroundTasks):
        ticket_id = str(uuid.uuid4())
        doc = {
            "_id": ticket_id,
            "kind": "remote_assist",
            "client_name": body.client_name,
            "contact_name": body.contact_name or "",
            "phone": body.phone,
            "email": body.email or "",
            "hoptodesk_id": (body.hoptodesk_id or "").strip(),
            "issue": body.issue,
            "app_version": body.app_version or "",
            "license_key": body.license_key or "",
            "install_id": body.install_id or "",
            "ip": request.client.host if request.client else "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "open",
        }
        await db.support_tickets.insert_one(doc)

        # 📱 Notificació Discord INSTANTÀNIA amb totes les dades
        if discord_ok():
            fields = [
                {"name": "📞 Telèfon", "value": f"**{body.phone}**", "inline": True},
                {"name": "🏥 Centre", "value": body.client_name, "inline": True},
                {"name": "👤 Contacte", "value": body.contact_name or body.client_name, "inline": True},
            ]
            if body.hoptodesk_id:
                fields.append({"name": "🖥️ ID HopToDesk", "value": f"`{body.hoptodesk_id}`", "inline": False})
            if body.email:
                fields.append({"name": "✉️ Email", "value": body.email, "inline": True})
            if body.app_version:
                fields.append({"name": "Versió app", "value": body.app_version, "inline": True})
            background_tasks.add_task(
                send_discord_notification,
                title="🖥️ SOL·LICITUD ASSISTÈNCIA REMOTA",
                description=f"**Problema:**\n{body.issue[:1500]}",
                color=COLOR_REMOTE_ASSIST,
                fields=fields,
                footer_text=f"Ticket: {ticket_id[:8]}",
            )

        # Email fallback per si Telegram no està configurat
        try:
            fake = ContactPayload(
                name=body.contact_name or body.client_name,
                email=body.email or "noemail@medicarplus.local",
                subject=f"[ASSISTÈNCIA REMOTA] {body.client_name}",
                message=(
                    f"Telèfon: {body.phone}\n"
                    f"ID HopToDesk: {body.hoptodesk_id or '(no informat)'}\n"
                    f"Versió: {body.app_version or '—'}\n"
                    f"Install ID: {body.install_id or '—'}\n\n"
                    f"Problema:\n{body.issue}"
                ),
                category="bug",
                app_version=body.app_version,
                license_key=body.license_key,
                client_name=body.client_name,
            )
            _send_email_smtp(fake, ticket_id)
        except Exception as e:
            logger.warning(f"Remote-assist email fallback failed: {e}")

        return {"ok": True, "ticket_id": ticket_id, "discord_sent": discord_ok()}

    @router.get("/tickets")
    async def list_tickets(x_admin_token: Optional[str] = Header(None)):
        admin_token = os.environ.get("LICENSE_ADMIN_TOKEN", "")
        if not admin_token or x_admin_token != admin_token:
            raise HTTPException(status_code=401, detail="unauthorized")
        cursor = db.support_tickets.find({}).sort("created_at", -1).limit(500)
        items: List[dict] = []
        async for t in cursor:
            t["id"] = t.pop("_id", None)
            items.append(t)
        return {"tickets": items, "count": len(items)}

    return router
