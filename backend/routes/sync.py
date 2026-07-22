"""
Sync multi-device Premium
==========================
Endpoints per sincronitzar l'estat entre 2 ordinadors amb la mateixa llicència PREMIUM.

- POST /api/sync/heartbeat    → 1 cop cada 60s. Retorna pla actual + timestamp cloud.
                                Serveix TAMBÉ per detectar upgrades STD→PRM en calent.
- POST /api/sync/push         → puja canvis locals (last-write-wins per clau).
- GET  /api/sync/pull         → baixa estat del núvol (només claus modificades després de `since`).

Regles:
  · Standard/Free: 1 sol install_id per llicència.
  · Premium/Trial/Master: fins a 2 install_ids per llicència.
  · Estat com a blob JSON per llicència amb `updated_at` per clau.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

COLL_STATE = "sync_states"
COLL_DEVICES = "sync_devices"
MAX_DEVICES_PREMIUM = 2
MAX_DEVICES_OTHER = 1
PREMIUM_PLANS = {"PRM", "PREMIUM", "TRIAL", "MASTER"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.replace(microsecond=0).isoformat()
    return str(dt)


def _key_hash(key: str) -> str:
    return hashlib.sha256(key.strip().encode()).hexdigest()


def _parse_iso(s) -> Optional[datetime]:
    if s is None:
        return None
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def _is_premium(doc: dict) -> bool:
    plan = str(doc.get("plan", "")).upper()
    plan_family = str(doc.get("plan_family", plan)).upper()
    return plan in PREMIUM_PLANS or plan_family in PREMIUM_PLANS


class HeartbeatBody(BaseModel):
    license_key: str = Field(..., min_length=10, max_length=1500)
    install_id: str = Field(..., min_length=4, max_length=200)


class PushBody(BaseModel):
    license_key: str = Field(..., min_length=10, max_length=1500)
    install_id: str = Field(..., min_length=4, max_length=200)
    entries: dict[str, Any] = Field(default_factory=dict)


def build_sync_router(db: AsyncIOMotorDatabase) -> APIRouter:
    router = APIRouter()

    async def _find_license(license_key: str) -> Optional[dict]:
        return await db.licenses.find_one({"license_key": license_key.strip()})

    @router.post("/sync/heartbeat")
    async def heartbeat(body: HeartbeatBody):
        lic = await _find_license(body.license_key)
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")
        if lic.get("status") == "revoked":
            raise HTTPException(status_code=403, detail="license_revoked")

        lkh = _key_hash(body.license_key)
        now = _now()
        is_premium = _is_premium(lic)
        max_dev = MAX_DEVICES_PREMIUM if is_premium else MAX_DEVICES_OTHER

        devices_coll = db[COLL_DEVICES]
        existing = await devices_coll.find({"license_key_hash": lkh}).to_list(length=10)
        existing_ids = {d["install_id"] for d in existing}
        authorized = True
        if body.install_id not in existing_ids:
            if len(existing_ids) >= max_dev:
                authorized = False
            else:
                await devices_coll.insert_one({
                    "license_key_hash": lkh,
                    "install_id": body.install_id,
                    "created_at": now,
                    "last_seen": now,
                })
                existing_ids.add(body.install_id)
        else:
            await devices_coll.update_one(
                {"license_key_hash": lkh, "install_id": body.install_id},
                {"$set": {"last_seen": now}},
            )

        state = await db[COLL_STATE].find_one({"_id": lkh})
        cloud_updated_at = state.get("last_updated_at") if state else None

        return {
            "authorized": authorized,
            "plan": str(lic.get("plan", "STD")).upper(),
            "plan_family": str(lic.get("plan_family", lic.get("plan", "STD"))).upper(),
            "is_premium": is_premium,
            "cloud_updated_at": _iso(cloud_updated_at),
            "server_time": _iso(now),
            "max_devices": max_dev,
            "current_devices": len(existing_ids),
            "device_limit_reached": not authorized,
        }

    @router.post("/sync/push")
    async def push(body: PushBody):
        if not body.entries:
            return {"ok": True, "written": 0, "cloud_updated_at": None}
        lic = await _find_license(body.license_key)
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")
        if not _is_premium(lic):
            raise HTTPException(status_code=403, detail="sync_requires_premium")

        lkh = _key_hash(body.license_key)
        now = _now()
        state = await db[COLL_STATE].find_one({"_id": lkh}) or {
            "_id": lkh,
            "data": {},
            "created_at": now,
        }
        data = state.get("data", {})
        written = 0
        for key, incoming in body.entries.items():
            if not isinstance(incoming, dict) or "value" not in incoming:
                continue
            cur = data.get(key)
            cur_ts = _parse_iso(cur.get("updated_at")) if cur else None
            inc_ts = _parse_iso(incoming.get("updated_at")) or now
            if cur_ts is None or inc_ts > cur_ts:
                data[key] = {
                    "value": incoming.get("value"),
                    "updated_at": _iso(inc_ts),
                    "author": body.install_id,
                }
                written += 1

        await db[COLL_STATE].replace_one(
            {"_id": lkh},
            {
                "_id": lkh,
                "data": data,
                "last_updated_at": now,
                "created_at": state.get("created_at", now),
            },
            upsert=True,
        )
        return {"ok": True, "written": written, "cloud_updated_at": _iso(now)}

    @router.get("/sync/pull")
    async def pull(license_key: str, install_id: str, since: str = ""):
        lic = await _find_license(license_key)
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")
        if not _is_premium(lic):
            raise HTTPException(status_code=403, detail="sync_requires_premium")

        lkh = _key_hash(license_key)
        state = await db[COLL_STATE].find_one({"_id": lkh})
        if not state:
            return {"entries": {}, "cloud_updated_at": None}

        since_dt = _parse_iso(since) if since else None
        entries: dict[str, Any] = {}
        for key, item in (state.get("data") or {}).items():
            ts = _parse_iso(item.get("updated_at"))
            if since_dt is None or (ts and ts > since_dt):
                entries[key] = {
                    "value": item.get("value"),
                    "updated_at": item.get("updated_at"),
                    "author": item.get("author"),
                }
        last_updated = state.get("last_updated_at")
        return {"entries": entries, "cloud_updated_at": _iso(last_updated)}

    return router
