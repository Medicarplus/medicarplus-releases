"""Installations tracking · registra TODA app abierta aunque nunca active.

Objetivo: God-mode para el owner. Trazabilidad total de cada instalación de
MediCar Plus, con o sin licencia activada.

Colección Mongo: `installations`
Doc shape:
{
  _id: "CD-XXXX-XXXX-XXXX-XXXX"        # install_id (único)
  first_seen_at: ISO string             # primer heartbeat
  last_seen_at: ISO string              # último heartbeat
  seen_count: int                       # cuántas veces ha "arrancado"
  user_agent: str                       # último UA
  platform: str                         # "electron-desktop" | "web-browser"
  timezone: str                         # p.ex. "Europe/Madrid"
  screen: str                           # p.ex. "1920x1080"
  ip_country: str                       # opcional (aprox de CF-IPCountry si Cloudflare)
  ip_first: str                         # última IP vista (útil para debug abuso)
  revoked: bool                         # true = bloqueado por el admin (no puede activar)
  revoked_at: ISO string | null
  revoked_reason: str | null
  linked_email: str | null              # email al que el owner vincula esta instalación
  notes: str | null                     # notas libres del owner
}

El backend NO recolecta ni almacena PII adicional. El track es idempotente:
upsert por install_id.
"""
from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/install", tags=["installations"])
admin_router = APIRouter(prefix="/installations", tags=["installations-admin"])


# ---- Rate limit muy sencillo por IP para /track (protege contra spam) --------
_last_track: Dict[str, float] = {}
_TRACK_MIN_INTERVAL = 30.0  # seg entre heartbeats por IP (frontend llama 1×/carga)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _admin_ok(x_admin_token: Optional[str]) -> None:
    expected = os.environ.get("LICENSE_ADMIN_TOKEN", "")
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


class TrackIn(BaseModel):
    install_id: str = Field(..., min_length=8, max_length=64)
    user_agent: Optional[str] = Field(default=None, max_length=512)
    platform: Optional[str] = Field(default=None, max_length=64)
    timezone: Optional[str] = Field(default=None, max_length=64)
    screen: Optional[str] = Field(default=None, max_length=32)
    app_version: Optional[str] = Field(default=None, max_length=32)


class RevokeIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=280)


class UpdateNotesIn(BaseModel):
    linked_email: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=2000)


_INSTALL_RE = re.compile(r"^[A-Z0-9\-]{8,64}$")


def build_router(db):
    """Registers heartbeat endpoint (public)."""

    @router.post("/track")
    async def track_install(body: TrackIn, request: Request):
        install_id = body.install_id.strip().upper()
        if not _INSTALL_RE.match(install_id):
            raise HTTPException(status_code=400, detail="invalid install_id format")

        ip = _client_ip(request)
        now = time.time()
        # Rate-limit débil: si la misma IP hizo track hace <30s, ignoramos con 200.
        last = _last_track.get(ip, 0)
        if now - last < _TRACK_MIN_INTERVAL:
            return {"ok": True, "throttled": True}
        _last_track[ip] = now

        ts = _now_iso()
        existing = await db.installations.find_one({"_id": install_id})
        set_doc = {
            "last_seen_at": ts,
            "user_agent": body.user_agent or "",
            "platform": body.platform or "web-browser",
            "timezone": body.timezone or "",
            "screen": body.screen or "",
            "app_version": body.app_version or "",
            "ip_last": ip,
            "ip_country": request.headers.get("cf-ipcountry", "") or "",
        }
        if existing:
            await db.installations.update_one(
                {"_id": install_id},
                {"$set": set_doc, "$inc": {"seen_count": 1}},
            )
            logger.info(f"[heartbeat] existing install_id={install_id} ip={ip} platform={body.platform or 'web'} seen_count={int(existing.get('seen_count', 0)) + 1}")
            return {"ok": True, "new": False}
        # Inserción nueva
        await db.installations.insert_one({
            "_id": install_id,
            "first_seen_at": ts,
            "ip_first": ip,
            "seen_count": 1,
            "revoked": False,
            "revoked_at": None,
            "revoked_reason": None,
            "linked_email": None,
            "notes": None,
            **set_doc,
        })
        logger.info(f"[heartbeat] 🆕 NEW install_id={install_id} ip={ip} platform={body.platform or 'web'} ua={(body.user_agent or '')[:80]}")
        return {"ok": True, "new": True}

    @router.get("/status/{install_id}")
    async def install_status(install_id: str):
        """Endpoint público (sin auth) para que la app sepa si está revocada.

        Solo devuelve `revoked` boolean, nada más. El frontend puede consultarlo
        al arrancar y mostrar un modal de bloqueo si `revoked=true`.
        """
        install_id = install_id.strip().upper()
        doc = await db.installations.find_one({"_id": install_id}, {"revoked": 1, "revoked_reason": 1})
        if not doc:
            return {"found": False, "revoked": False}
        return {"found": True, "revoked": bool(doc.get("revoked")), "reason": doc.get("revoked_reason")}

    # ---- Admin endpoints ------------------------------------------------------

    @admin_router.get("/debug/summary")
    async def installations_debug_summary(x_admin_token: Optional[str] = Header(None)):
        """Diagnóstico rápido: conteo real por estado + últimos 10 heartbeats.

        Útil para depurar cuando la UI muestra pocos resultados y sospechamos
        filtros o problemas de red en clientes.
        """
        _admin_ok(x_admin_token)
        total = await db.installations.count_documents({})
        active = await db.installations.count_documents({"revoked": {"$ne": True}})
        revoked = await db.installations.count_documents({"revoked": True})
        with_email = await db.installations.count_documents({"linked_email": {"$nin": [None, ""]}})
        electron = await db.installations.count_documents({"platform": "electron-desktop"})
        web = await db.installations.count_documents({"platform": "web-browser"})

        # Últimos 10 arranques (por last_seen_at)
        recent = []
        cursor = db.installations.find({}, {
            "_id": 1, "last_seen_at": 1, "first_seen_at": 1, "ip_last": 1,
            "platform": 1, "seen_count": 1, "app_version": 1, "linked_email": 1,
        }).sort("last_seen_at", -1).limit(10)
        async for d in cursor:
            recent.append({
                "install_id": d.pop("_id"),
                **d,
            })

        # Nuevos en las últimas 24h (por first_seen_at)
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        new_24h = await db.installations.count_documents({"first_seen_at": {"$gte": cutoff}})
        seen_24h = await db.installations.count_documents({"last_seen_at": {"$gte": cutoff}})

        return {
            "total_in_db": total,
            "active": active,
            "revoked": revoked,
            "with_linked_email": with_email,
            "platforms": {"electron_desktop": electron, "web_browser": web},
            "last_24h": {"new_installs": new_24h, "seen_installs": seen_24h},
            "recent_10": recent,
        }

    @admin_router.get("")
    async def list_installations(
        q: str = "",
        status: str = "all",  # all | active | revoked | no_license
        limit: int = 500,
        x_admin_token: Optional[str] = Header(None),
    ):
        _admin_ok(x_admin_token)
        query: dict = {}
        if q:
            q_up = q.strip().upper()
            query["$or"] = [
                {"_id": {"$regex": re.escape(q_up), "$options": "i"}},
                {"linked_email": {"$regex": re.escape(q), "$options": "i"}},
                {"notes": {"$regex": re.escape(q), "$options": "i"}},
                {"user_agent": {"$regex": re.escape(q), "$options": "i"}},
                {"ip_last": {"$regex": re.escape(q), "$options": "i"}},
                {"ip_first": {"$regex": re.escape(q), "$options": "i"}},
            ]
        if status == "active":
            query["revoked"] = {"$ne": True}
        elif status == "revoked":
            query["revoked"] = True

        cursor = db.installations.find(query).sort("last_seen_at", -1).limit(min(limit, 2000))
        items = []
        async for d in cursor:
            iid = d.pop("_id")
            # Enriquecer con datos de licencia si existe (bien como install_id principal, bien como linked_install_ids)
            lic = await db.licenses.find_one({
                "$or": [
                    {"install_id": iid},
                    {"linked_install_ids": iid},
                ]
            }, {
                "plan_family": 1, "status": 1, "client_name": 1, "client_email": 1,
                "expires_at": 1, "license_key": 1, "created_at": 1,
                "install_id": 1, "linked_install_ids": 1, "id": 1,
            })
            link_info = None
            if lic:
                principal = (lic.get("install_id") or "").strip()
                linked = [x for x in (lic.get("linked_install_ids") or []) if x]
                # ¿Este iid es el principal o un secundario?
                if iid == principal:
                    device_no = 1
                elif iid in linked:
                    device_no = 2 + linked.index(iid)  # #2, #3, …
                else:
                    device_no = 0
                total_devices = 1 + len(linked)
                link_info = {
                    "device_no": device_no,
                    "total_devices": total_devices,
                    "plan_family": lic.get("plan_family"),
                    "license_key": lic.get("license_key"),
                    "license_jti": lic.get("id"),
                    "principal_install_id": principal,
                    "linked_install_ids": linked,
                    "client_name": lic.get("client_name"),
                    "client_email": lic.get("client_email"),
                }
            if status == "no_license" and lic:
                continue
            items.append({
                "install_id": iid,
                **d,
                "license": (lic and {**lic, "_id": str(lic.get("_id"))}) or None,
                "link_info": link_info,
            })
        return {"items": items, "total": len(items)}

    @admin_router.get("/{install_id}")
    async def get_installation(install_id: str, x_admin_token: Optional[str] = Header(None)):
        _admin_ok(x_admin_token)
        install_id = install_id.strip().upper()
        doc = await db.installations.find_one({"_id": install_id})
        if not doc:
            raise HTTPException(status_code=404, detail="not found")
        iid = doc.pop("_id")
        lic = await db.licenses.find_one({"install_id": iid})
        if lic:
            lic["_id"] = str(lic.get("_id"))
        return {"install_id": iid, **doc, "license": lic}

    @admin_router.post("/{install_id}/revoke")
    async def revoke_installation(install_id: str, body: RevokeIn, x_admin_token: Optional[str] = Header(None)):
        _admin_ok(x_admin_token)
        install_id = install_id.strip().upper()
        existing = await db.installations.find_one({"_id": install_id})
        if not existing:
            # Crea placeholder revocado (útil para bloquear install_ids que nunca hicieron heartbeat)
            await db.installations.insert_one({
                "_id": install_id,
                "first_seen_at": _now_iso(),
                "last_seen_at": _now_iso(),
                "seen_count": 0,
                "revoked": True,
                "revoked_at": _now_iso(),
                "revoked_reason": body.reason or "",
            })
        else:
            await db.installations.update_one(
                {"_id": install_id},
                {"$set": {"revoked": True, "revoked_at": _now_iso(), "revoked_reason": body.reason or ""}},
            )
        # Marcar también la licencia asociada como revoked (si existe)
        await db.licenses.update_many(
            {"install_id": install_id},
            {"$set": {"status": "revoked", "revoked_at": _now_iso(), "revoked_reason": body.reason or ""}},
        )
        return {"ok": True, "install_id": install_id, "revoked": True}

    @admin_router.post("/{install_id}/unrevoke")
    async def unrevoke_installation(install_id: str, x_admin_token: Optional[str] = Header(None)):
        _admin_ok(x_admin_token)
        install_id = install_id.strip().upper()
        res = await db.installations.update_one(
            {"_id": install_id},
            {"$set": {"revoked": False, "revoked_at": None, "revoked_reason": None}},
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="not found")
        return {"ok": True, "install_id": install_id, "revoked": False}

    @admin_router.patch("/{install_id}")
    async def update_installation(install_id: str, body: UpdateNotesIn, x_admin_token: Optional[str] = Header(None)):
        _admin_ok(x_admin_token)
        install_id = install_id.strip().upper()
        update: dict = {}
        if body.linked_email is not None:
            update["linked_email"] = body.linked_email.strip() or None
        if body.notes is not None:
            update["notes"] = body.notes.strip() or None
        if not update:
            raise HTTPException(status_code=400, detail="no fields to update")
        res = await db.installations.update_one({"_id": install_id}, {"$set": update})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="not found")
        return {"ok": True, **update}

    @admin_router.delete("/{install_id}")
    async def delete_installation(install_id: str, x_admin_token: Optional[str] = Header(None)):
        _admin_ok(x_admin_token)
        install_id = install_id.strip().upper()
        res = await db.installations.delete_one({"_id": install_id})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="not found")
        return {"ok": True, "deleted": install_id}

    return router, admin_router
