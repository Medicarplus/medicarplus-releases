"""Admin notifications feed · God-mode traceability of key events.

Provides a lightweight `notifications` collection + API endpoints so the owner
can see at a glance:
  🔴 Payment failures (CRITICAL — never miss one)
  🟡 Subscription cancellations / downgrades
  🟢 Plan upgrades, new installations, payment recoveries

Events are created by hooks in `server.py` (webhooks) and `routes/installations.py`
(heartbeat). This module only defines the CRUD + list endpoints.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Severity levels
SEV_INFO = "info"
SEV_WARNING = "warning"
SEV_CRITICAL = "critical"

# Event types
TYPE_INSTALL_NEW = "install_new"
TYPE_PAYMENT_FAILED = "payment_failed"
TYPE_PAYMENT_RECOVERED = "payment_recovered"
TYPE_SUBSCRIPTION_CANCELED = "subscription_canceled"
TYPE_PLAN_UPGRADE = "plan_upgrade"
TYPE_PLAN_DOWNGRADE = "plan_downgrade"

_TYPE_META = {
    TYPE_INSTALL_NEW: {"icon": "🆕", "sev": SEV_INFO, "label": "Nueva instalación"},
    TYPE_PAYMENT_FAILED: {"icon": "🚨", "sev": SEV_CRITICAL, "label": "Pago fallido"},
    TYPE_PAYMENT_RECOVERED: {"icon": "✅", "sev": SEV_INFO, "label": "Pago recuperado"},
    TYPE_SUBSCRIPTION_CANCELED: {"icon": "🛑", "sev": SEV_WARNING, "label": "Suscripción cancelada"},
    TYPE_PLAN_UPGRADE: {"icon": "⬆️", "sev": SEV_INFO, "label": "Ampliación de plan"},
    TYPE_PLAN_DOWNGRADE: {"icon": "⬇️", "sev": SEV_WARNING, "label": "Bajada de plan"},
}


# Category groupings for UI filter (Feb 2026)
_CATEGORY_TYPES = {
    "instalaciones": [TYPE_INSTALL_NEW],
    "pagos": [TYPE_PAYMENT_FAILED, TYPE_PAYMENT_RECOVERED],
    "avisos": [TYPE_SUBSCRIPTION_CANCELED, TYPE_PLAN_UPGRADE, TYPE_PLAN_DOWNGRADE],
}


def _admin_ok(x_admin_token: Optional[str]) -> None:
    expected = os.environ.get("LICENSE_ADMIN_TOKEN", "")
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


async def create_notification(
    db,
    *,
    ntype: str,
    title: str,
    message: str,
    email: Optional[str] = None,
    install_id: Optional[str] = None,
    amount_cents: Optional[int] = None,
    invoice_url: Optional[str] = None,
    extra: Optional[dict] = None,
    dedupe_key: Optional[str] = None,
) -> Optional[str]:
    """Insert a notification. If dedupe_key is given, upserts (no duplicates).

    Returns the notification id (or None if type unknown).
    """
    meta = _TYPE_META.get(ntype)
    if not meta:
        logger.warning(f"[notifications] unknown type {ntype}")
        return None
    doc: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "type": ntype,
        "severity": meta["sev"],
        "icon": meta["icon"],
        "title": title,
        "message": message,
        "email": email,
        "install_id": install_id,
        "amount_cents": amount_cents,
        "invoice_url": invoice_url,
        "extra": extra or {},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if dedupe_key:
        doc["dedupe_key"] = dedupe_key
        existing = await db.notifications.find_one({"dedupe_key": dedupe_key})
        if existing:
            return existing.get("id")
    await db.notifications.insert_one(doc)
    logger.info(f"[notifications] {meta['icon']} {meta['label']} · email={email} install_id={install_id}")
    return doc["id"]


def build_notifications_router(db):
    router = APIRouter(prefix="/admin/notifications", tags=["admin-notifications"])

    # Auto-cleanup: en cada request al panel, si han pasado >24h desde la última limpieza,
    # borra silenciosamente notificaciones leídas de más de 30 días.
    # Estado guardado en la propia colección (doc especial _id=_meta) para persistir tras reinicios.
    AUTO_CLEANUP_DAYS = 30
    AUTO_CLEANUP_EVERY_HOURS = 24

    async def _maybe_auto_cleanup():
        try:
            now = datetime.now(timezone.utc)
            meta = await db.notifications.find_one({"_id": "_meta"})
            last_iso = (meta or {}).get("last_cleanup_at")
            if last_iso:
                try:
                    last = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
                    if (now - last).total_seconds() < AUTO_CLEANUP_EVERY_HOURS * 3600:
                        return
                except Exception:
                    pass
            cutoff = (now - timedelta(days=AUTO_CLEANUP_DAYS)).isoformat()
            r = await db.notifications.delete_many({"read": True, "created_at": {"$lt": cutoff}})
            await db.notifications.update_one(
                {"_id": "_meta"},
                {"$set": {"last_cleanup_at": now.isoformat(), "last_cleanup_deleted": r.deleted_count}},
                upsert=True,
            )
            if r.deleted_count:
                logger.info(f"[notifications] auto-cleanup: eliminadas {r.deleted_count} leídas de >{AUTO_CLEANUP_DAYS} días")
        except Exception as e:
            logger.warning(f"[notifications] auto-cleanup falló: {e}")

    @router.get("")
    async def list_notifications(
        unread_only: bool = False,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        read_state: Optional[str] = None,
        limit: int = 100,
        x_admin_token: Optional[str] = Header(None),
    ):
        _admin_ok(x_admin_token)
        query: dict = {"type": {"$exists": True}}  # excluye docs internos (ej: _meta)
        # read_state has priority over legacy unread_only
        if read_state == "unread":
            query["read"] = False
        elif read_state == "read":
            query["read"] = True
        elif unread_only:
            query["read"] = False
        if severity in (SEV_INFO, SEV_WARNING, SEV_CRITICAL):
            query["severity"] = severity
        # Category filter groups multiple types together
        if category and category in _CATEGORY_TYPES:
            query["type"] = {"$in": _CATEGORY_TYPES[category]}

        # Critical items always sorted at top, then by date desc
        items: list[dict] = []
        cursor = db.notifications.find(query).sort("created_at", -1).limit(min(limit, 500))
        async for n in cursor:
            n.pop("_id", None)
            items.append(n)

        # Sort: unread critical first, then unread others (by date desc), then read (by date desc)
        def _sort_key(n: dict) -> tuple:
            unread_score = 0 if not n.get("read") else 1
            sev_score = 0 if n.get("severity") == SEV_CRITICAL else 1
            return (unread_score, sev_score, -_ts(n.get("created_at")))

        items.sort(key=_sort_key)
        return {"items": items, "total": len(items)}

    @router.get("/badge")
    async def badge_counts(x_admin_token: Optional[str] = Header(None)):
        _admin_ok(x_admin_token)
        # Dispara auto-cleanup silencioso (throttle 24h, borra leídas > 30 días)
        await _maybe_auto_cleanup()
        unread = await db.notifications.count_documents({"read": False, "type": {"$exists": True}})
        critical = await db.notifications.count_documents({"read": False, "severity": SEV_CRITICAL, "type": {"$exists": True}})
        # Last critical (for tooltip)
        last = await db.notifications.find_one(
            {"read": False, "severity": SEV_CRITICAL, "type": {"$exists": True}},
            sort=[("created_at", -1)],
        )
        return {
            "unread": unread,
            "critical_unread": critical,
            "last_critical_title": (last or {}).get("title"),
            "last_critical_at": (last or {}).get("created_at"),
        }

    @router.post("/{nid}/read")
    async def mark_read(nid: str, x_admin_token: Optional[str] = Header(None)):
        _admin_ok(x_admin_token)
        r = await db.notifications.update_one({"id": nid}, {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}})
        return {"ok": r.matched_count > 0, "modified": r.modified_count}

    @router.post("/mark-all-read")
    async def mark_all_read(x_admin_token: Optional[str] = Header(None)):
        _admin_ok(x_admin_token)
        r = await db.notifications.update_many({"read": False}, {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}})
        return {"ok": True, "modified": r.modified_count}

    @router.delete("/{nid}")
    async def delete_notification(nid: str, x_admin_token: Optional[str] = Header(None)):
        _admin_ok(x_admin_token)
        r = await db.notifications.delete_one({"id": nid})
        return {"ok": r.deleted_count > 0}

    @router.post("/delete-all-read")
    async def delete_all_read(x_admin_token: Optional[str] = Header(None)):
        """Elimina TODAS las notificaciones marcadas como leídas."""
        _admin_ok(x_admin_token)
        r = await db.notifications.delete_many({"read": True, "type": {"$exists": True}})
        return {"deleted": r.deleted_count}

    @router.post("/delete-all")
    async def delete_all(x_admin_token: Optional[str] = Header(None)):
        """Elimina TODAS las notificaciones (leídas y no leídas). Irreversible."""
        _admin_ok(x_admin_token)
        r = await db.notifications.delete_many({"type": {"$exists": True}})
        return {"deleted": r.deleted_count}

    @router.post("/cleanup")
    async def cleanup_old(days: int = 90, x_admin_token: Optional[str] = Header(None)):
        """Elimina notificaciones LEÍDAS de hace más de `days` días."""
        _admin_ok(x_admin_token)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        r = await db.notifications.delete_many({"read": True, "created_at": {"$lt": cutoff}})
        return {"deleted": r.deleted_count, "cutoff": cutoff}

    return router


def _ts(iso: Optional[str]) -> float:
    if not iso:
        return 0.0
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0
