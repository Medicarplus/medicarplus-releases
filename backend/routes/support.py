"""
Support router · Formulari de contacte dins l'app comercial
POST /api/support/contact → guarda el ticket a MongoDB + intenta enviar email (si SMTP està configurat)
GET  /api/support/tickets → llista tickets (protegit per LICENSE_ADMIN_TOKEN)
"""
import os
import uuid
import smtplib
import logging
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, Field, EmailStr

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
    async def contact(body: ContactPayload, request: Request):
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

        return ContactResult(
            ok=True,
            ticket_id=ticket_id,
            email_sent=ok,
            detail=None if ok else "Ticket guardat. L'enviament d'email pot estar pendent de configuració SMTP.",
        )

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
