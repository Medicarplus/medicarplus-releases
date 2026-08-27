"""Admin endpoint para enviar mensajes de soporte al cliente.

El admin escribe un mensaje desde el panel y llega al cliente por email desde
info@medicarplus.es. La respuesta del cliente llega a la bandeja de info@medicarplus.es
de forma natural (Reply-To). Se guarda una copia del hilo en `support_messages`.

También expone un endpoint público autenticado por license_key para que el cliente
envíe mensajes desde la app (v2.html · botón "Contactar soporte").
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field

from services.mailer import _send_smtp, _smtp_configured

logger = logging.getLogger(__name__)


def _admin_ok(x_admin_token: Optional[str]) -> None:
    expected = os.environ.get("LICENSE_ADMIN_TOKEN", "")
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


class SupportMessageBody(BaseModel):
    subject: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=5, max_length=5000)
    override_email: Optional[EmailStr] = None


class ClientSupportMessageBody(BaseModel):
    """Payload del cliente (v2.html) para enviar un mensaje al admin."""
    install_id: str = Field(..., min_length=6, max_length=64)
    license_key: str = Field(..., min_length=10, max_length=2000)
    subject: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=5, max_length=5000)
    # Adjuntos: lista de imágenes en base64 (data:image/…;base64,…) máx 3 imágenes, ~2MB cada una
    attachments: Optional[List[str]] = None


def _build_support_email(client_name: str, admin_message: str) -> str:
    from html import escape
    safe_msg = escape(admin_message).replace("\n", "<br>")
    return f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;background:#f4f4f7;padding:20px;color:#111">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:10px;padding:30px;box-shadow:0 2px 10px rgba(0,0,0,.05)">
  <div style="text-align:center;margin-bottom:20px">
    <h1 style="color:#f5b301;margin:0;font-size:24px">MediCar Plus · Soporte</h1>
    <p style="color:#666;margin:4px 0 0 0;font-size:12px">Mensaje del equipo de MediCar Plus</p>
  </div>
  <h2 style="color:#111;font-size:16px">Hola{(' ' + client_name) if client_name else ''},</h2>
  <div style="background:#fff8e1;border-left:4px solid #f5b301;padding:18px;margin:18px 0;border-radius:4px;line-height:1.7;font-size:14px;color:#222">
    {safe_msg}
  </div>
  <div style="background:#e0f2fe;border-left:4px solid #0284c7;padding:12px;margin:18px 0;border-radius:6px;font-size:13px">
    💬 <b>Responde directamente a este email</b> — tu respuesta llegará al equipo de soporte en <a href="mailto:info@medicarplus.es" style="color:#0284c7">info@medicarplus.es</a> y te contestaremos en breve.
  </div>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0" />
  <p style="font-size:11px;color:#999;text-align:center">MediCar Plus · <a href="https://medicarplus.es" style="color:#666">medicarplus.es</a><br />¿Necesitas descargar el programa? <a href="https://medicarplus.es/downloads/" style="color:#f5b301">medicarplus.es/downloads</a></p>
</div></body></html>"""


def build_support_router(db):
    router = APIRouter(prefix="/admin/licenses", tags=["admin-support"])
    coll = db.support_messages

    @router.post("/{license_key}/send-support")
    async def send_support_message(
        license_key: str,
        body: SupportMessageBody,
        x_admin_token: Optional[str] = Header(None),
    ):
        """Envía un mensaje al cliente por email y lo guarda en el historial."""
        _admin_ok(x_admin_token)
        if not _smtp_configured():
            raise HTTPException(status_code=503, detail="smtp_not_configured")

        # Buscar licencia
        lic = await db.licenses.find_one({"$or": [{"license_key": license_key}, {"jti": license_key}, {"id": license_key}]})
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")

        to_email = (body.override_email or lic.get("client_email") or "").strip()
        if not to_email:
            raise HTTPException(status_code=400, detail="client_email_missing")

        client_name = (lic.get("client_name") or lic.get("centre") or "").strip()
        install_id = (lic.get("install_id") or "").strip()

        subject = f"MediCar Plus · {body.subject}"
        html = _build_support_email(client_name, body.body)

        ok, info = _send_smtp(to_email, subject, html)
        if not ok:
            logger.warning("Support message failed for %s: %s", install_id, info)
            raise HTTPException(status_code=500, detail=f"send_failed:{info}")

        # Guardar en historial
        now = datetime.now(timezone.utc)
        await coll.insert_one({
            "install_id": install_id,
            "license_key": license_key,
            "to_email": to_email,
            "client_name": client_name,
            "direction": "outbound",  # admin → cliente
            "subject": body.subject,
            "body": body.body,
            "sent_at": now.isoformat(),
        })
        return {"ok": True, "sent_to": to_email, "sent_at": now.isoformat()}

    @router.get("/{license_key}/support-history")
    async def get_support_history(
        license_key: str,
        x_admin_token: Optional[str] = Header(None),
    ):
        """Devuelve el historial de mensajes enviados a este cliente."""
        _admin_ok(x_admin_token)
        lic = await db.licenses.find_one({"$or": [{"license_key": license_key}, {"jti": license_key}, {"id": license_key}]})
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")
        install_id = lic.get("install_id") or ""
        cur = coll.find({"install_id": install_id}).sort("sent_at", -1).limit(50)
        messages = []
        unread_count = 0
        async for m in cur:
            is_inbound = m.get("direction") == "inbound"
            is_unread = is_inbound and not m.get("read_by_admin_at")
            if is_unread:
                unread_count += 1
            messages.append({
                "direction": m.get("direction"),
                "subject": m.get("subject"),
                "body": m.get("body"),
                "attachments": m.get("attachments") or [],
                "sent_at": m.get("sent_at"),
                "to_email": m.get("to_email"),
                "unread": is_unread,
            })
        return {"install_id": install_id, "messages": messages, "count": len(messages), "unread_count": unread_count}

    @router.get("/inbox-unified")
    async def get_unified_inbox(
        unread_only: bool = True,
        limit: int = 100,
        x_admin_token: Optional[str] = Header(None),
    ):
        """Bandeja unificada · todos los mensajes de todos los clientes en un solo listado."""
        _admin_ok(x_admin_token)
        query = {"direction": "inbound"}
        if unread_only:
            query["read_by_admin_at"] = None
        cur = coll.find(query).sort("sent_at", -1).limit(min(limit, 500))
        # Cargar info de licencias en batch
        install_ids = []
        msgs_raw = []
        async for m in cur:
            msgs_raw.append(m)
            iid = m.get("install_id")
            if iid and iid not in install_ids: install_ids.append(iid)
        lic_map = {}
        if install_ids:
            async for lic in db.licenses.find({"install_id": {"$in": install_ids}}, {"install_id": 1, "client_name": 1, "client_email": 1, "license_key": 1, "plan": 1, "status": 1}):
                lic_map[lic.get("install_id")] = lic
        messages = []
        for m in msgs_raw:
            iid = m.get("install_id") or ""
            lic = lic_map.get(iid) or {}
            messages.append({
                "msg_id": str(m.get("_id")),
                "install_id": iid,
                "license_key": lic.get("license_key"),
                "client_name": lic.get("client_name") or m.get("client_name") or "",
                "client_email": lic.get("client_email") or m.get("from_email") or "",
                "plan": lic.get("plan") or "",
                "subject": m.get("subject"),
                "body": (m.get("body") or "")[:400],  # preview
                "has_attachments": bool(m.get("attachments")),
                "attachments_count": len(m.get("attachments") or []),
                "sent_at": m.get("sent_at"),
                "unread": not m.get("read_by_admin_at"),
            })
        # Cuenta total no leídos (independiente del filtro)
        total_unread = await coll.count_documents({"direction": "inbound", "read_by_admin_at": None})
        return {"messages": messages, "count": len(messages), "total_unread": total_unread}

    @router.post("/{license_key}/mark-read")
    async def mark_messages_read(
        license_key: str,
        x_admin_token: Optional[str] = Header(None),
    ):
        """Marca todos los mensajes inbound (del cliente) como leídos por el admin."""
        _admin_ok(x_admin_token)
        lic = await db.licenses.find_one({"$or": [{"license_key": license_key}, {"jti": license_key}, {"id": license_key}]})
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")
        install_id = lic.get("install_id") or ""
        res = await coll.update_many(
            {"install_id": install_id, "direction": "inbound", "read_by_admin_at": None},
            {"$set": {"read_by_admin_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {"ok": True, "marked_read": res.modified_count}

    # ---------- Bandeja unificada: acciones por mensaje individual ----------
    msg_router = APIRouter(prefix="/admin/support/messages", tags=["admin-support"])

    @msg_router.post("/{msg_id}/mark-unread")
    async def mark_single_unread(
        msg_id: str,
        x_admin_token: Optional[str] = Header(None),
    ):
        """Devuelve un mensaje inbound al estado NO leído (limpia read_by_admin_at)."""
        _admin_ok(x_admin_token)
        try:
            from bson import ObjectId
            oid = ObjectId(msg_id)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_msg_id")
        r = await coll.update_one(
            {"_id": oid, "direction": "inbound"},
            {"$unset": {"read_by_admin_at": ""}},
        )
        if r.matched_count == 0:
            raise HTTPException(status_code=404, detail="message_not_found")
        return {"ok": True, "modified": r.modified_count}

    @msg_router.post("/{msg_id}/mark-read")
    async def mark_single_read(
        msg_id: str,
        x_admin_token: Optional[str] = Header(None),
    ):
        """Marca un mensaje individual como leído."""
        _admin_ok(x_admin_token)
        try:
            from bson import ObjectId
            oid = ObjectId(msg_id)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_msg_id")
        r = await coll.update_one(
            {"_id": oid, "direction": "inbound"},
            {"$set": {"read_by_admin_at": datetime.now(timezone.utc).isoformat()}},
        )
        if r.matched_count == 0:
            raise HTTPException(status_code=404, detail="message_not_found")
        return {"ok": True, "modified": r.modified_count}

    # ---------- Endpoint público (autenticado por license_key) ----------
    # El cliente escribe desde la app y el mensaje entra en el historial como "inbound"
    public_router = APIRouter(prefix="/support", tags=["client-support"])

    @public_router.post("/client-message")
    async def client_message(body: ClientSupportMessageBody):
        """El cliente envía un mensaje al admin desde la app.

        Autenticación: la license_key debe corresponder al install_id y estar activa.
        """
        lic = await db.licenses.find_one({"install_id": body.install_id})
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")
        if lic.get("status") != "active":
            raise HTTPException(status_code=403, detail="license_not_active")
        stored_key = (lic.get("license_key") or "").strip()
        if stored_key and stored_key != body.license_key.strip():
            raise HTTPException(status_code=401, detail="invalid_license_key")

        client_name = (lic.get("client_name") or lic.get("centre") or "").strip()
        client_email = (lic.get("client_email") or "").strip()
        # Saneamos adjuntos: máximo 3 imágenes, cada una <2.5MB base64, formato data:image/*;base64,
        clean_attachments = []
        if body.attachments and isinstance(body.attachments, list):
            for att in body.attachments[:3]:  # máx 3
                if not isinstance(att, str): continue
                if not att.startswith("data:image/"): continue
                if len(att) > 2_800_000: continue  # ~2MB útiles
                clean_attachments.append(att)
        now = datetime.now(timezone.utc)
        await coll.insert_one({
            "install_id": body.install_id,
            "license_key": stored_key,
            "from_email": client_email,
            "client_name": client_name,
            "direction": "inbound",  # cliente → admin
            "subject": body.subject,
            "body": body.body,
            "attachments": clean_attachments,
            "sent_at": now.isoformat(),
            "read_by_admin_at": None,
        })

        # Notifica al admin por email para que se entere al momento
        try:
            admin_notify = os.environ.get("ADMIN_NOTIFY_EMAIL", "").strip()
            if admin_notify and _smtp_configured():
                from html import escape
                safe_msg = escape(body.body).replace("\n", "<br>")
                html = f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;padding:20px;color:#111">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:10px;padding:24px;border:1px solid #ddd">
<h2 style="color:#a855f7;margin:0 0 12px 0">💬 Nuevo mensaje de cliente</h2>
<p style="margin:0 0 8px 0"><b>Cliente:</b> {escape(client_name or 'Sin nombre')} · <a href="mailto:{escape(client_email)}">{escape(client_email)}</a></p>
<p style="margin:0 0 12px 0"><b>Install ID:</b> <code>{escape(body.install_id)}</code></p>
<hr style="border:none;border-top:1px solid #eee">
<p style="margin:12px 0 4px 0;font-weight:700">{escape(body.subject)}</p>
<div style="background:#f9fafb;border-left:3px solid #a855f7;padding:12px;font-size:14px;line-height:1.6">{safe_msg}</div>
<p style="margin-top:20px;font-size:11px;color:#666">Responde desde el panel admin → ficha del cliente → 💬 Enviar mensaje</p>
</div></body></html>"""
                _send_smtp(admin_notify, f"[MediCar Plus · Cliente] {body.subject}", html)
        except Exception as ex:
            logger.warning("Could not notify admin about client message: %s", ex)

        return {"ok": True, "received_at": now.isoformat()}

    return router, public_router, msg_router
