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
import uuid
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

# 👑 Offline MASTER key (owner) — bypass DB, always treated as Premium.
# Same key that the client uses in isPremiumLicense() (v2.html).
MASTER_KEY = "MB-MASTER-BRUGULAT-2026-OWNER"


def _synthetic_master_license() -> dict:
    """Doc sintético que representa la MASTER key sin necesitar entrada en DB."""
    return {
        "license_key": MASTER_KEY,
        "plan": "MASTER",
        "plan_family": "MASTER",
        "status": "active",
        "client_email": "owner@medicarplus.es",
        "_synthetic": True,
    }


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


class ModeBody(BaseModel):
    license_key: str = Field(..., min_length=10, max_length=1500)
    install_id: str = Field(..., min_length=4, max_length=200)
    mode: str = Field(..., pattern="^(linked|independent)$")


class BackupSendBody(BaseModel):
    license_key: str = Field(..., min_length=10, max_length=1500)
    install_id: str = Field(..., min_length=4, max_length=200)
    data: dict[str, Any] = Field(default_factory=dict, description="Snapshot completo localStorage")
    label: Optional[str] = Field(default=None, max_length=200)


class BackupConsumeBody(BaseModel):
    license_key: str = Field(..., min_length=10, max_length=1500)
    install_id: str = Field(..., min_length=4, max_length=200)
    backup_id: str


COLL_BACKUPS = "sync_backups"


def build_sync_router(db: AsyncIOMotorDatabase) -> APIRouter:
    router = APIRouter()

    async def _find_license(license_key: str) -> Optional[dict]:
        key = (license_key or "").strip()
        # 👑 Bypass MASTER offline key: no está en DB pero siempre es Premium
        if key == MASTER_KEY:
            return _synthetic_master_license()
        return await db.licenses.find_one({"license_key": key})

    async def _is_device_authorized(license_key_hash: str, install_id: str) -> bool:
        """Un dispositiu es considera autoritzat si ja té una entrada a sync_devices.
        S'insereix a heartbeat quan encara hi ha slots lliures. Push/Pull no obren slots nous."""
        d = await db[COLL_DEVICES].find_one({"license_key_hash": license_key_hash, "install_id": install_id})
        return d is not None

    async def _is_device_linked(license_key_hash: str, install_id: str) -> bool:
        """Un dispositiu participa en sync només si el seu mode = 'linked'.
        Per defecte tots els dispositius nous són 'independent' (el client decideix).
        """
        d = await db[COLL_DEVICES].find_one({"license_key_hash": license_key_hash, "install_id": install_id})
        return bool(d and d.get("sync_mode") == "linked")

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
        if not await _is_device_authorized(lkh, body.install_id):
            raise HTTPException(status_code=403, detail="device_not_authorized")
        # 🔗 Solo dispositivos en modo "linked" participan en sync
        if not await _is_device_linked(lkh, body.install_id):
            raise HTTPException(status_code=409, detail="device_mode_independent")
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
        if not await _is_device_authorized(lkh, install_id):
            raise HTTPException(status_code=403, detail="device_not_authorized")
        # 🔗 Solo dispositivos en modo "linked" participan en sync
        if not await _is_device_linked(lkh, install_id):
            raise HTTPException(status_code=409, detail="device_mode_independent")
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

    @router.post("/sync/mode")
    async def set_mode(body: ModeBody):
        """Cambia el modo del dispositivo entre 'linked' (fusionado) e 'independent'.

        Al cambiar a linked: el próximo push/pull sincronizará con el otro PC.
        Al cambiar a independent: este PC deja de participar en sync (sus datos
        locales siguen intactos y no se ven afectados por el otro PC).
        """
        lic = await _find_license(body.license_key)
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")
        if not _is_premium(lic):
            raise HTTPException(status_code=403, detail="mode_requires_premium")
        lkh = _key_hash(body.license_key)
        if not await _is_device_authorized(lkh, body.install_id):
            raise HTTPException(status_code=403, detail="device_not_authorized")
        now = _now()
        await db[COLL_DEVICES].update_one(
            {"license_key_hash": lkh, "install_id": body.install_id},
            {"$set": {"sync_mode": body.mode, "mode_changed_at": now}},
        )
        # Cuenta cuántos devices en 'linked' hay ahora
        linked_count = await db[COLL_DEVICES].count_documents(
            {"license_key_hash": lkh, "sync_mode": "linked"}
        )
        logger.info("sync/mode install=%s → %s (linked_devices=%d)",
                    body.install_id, body.mode, linked_count)
        return {"ok": True, "mode": body.mode, "linked_devices": linked_count,
                "server_time": _iso(now)}

    @router.get("/sync/status")
    async def status(license_key: str, install_id: str):
        """Devuelve el estado de vinculación del dispositivo y del grupo."""
        lic = await _find_license(license_key)
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")
        lkh = _key_hash(license_key)
        me = await db[COLL_DEVICES].find_one({"license_key_hash": lkh, "install_id": install_id})
        my_mode = (me or {}).get("sync_mode") or "independent"
        all_devices = await db[COLL_DEVICES].find({"license_key_hash": lkh}).to_list(length=10)
        peers = []
        for d in all_devices:
            if d.get("install_id") == install_id:
                continue
            peers.append({
                "install_id": d.get("install_id"),
                "mode": d.get("sync_mode") or "independent",
                "last_seen": _iso(d.get("last_seen")),
            })
        state = await db[COLL_STATE].find_one({"_id": lkh})
        return {
            "linked": my_mode == "linked",
            "my_mode": my_mode,
            "is_premium": _is_premium(lic),
            "peers": peers,
            "cloud_updated_at": _iso((state or {}).get("last_updated_at")),
        }

    # ────────────────────────────────────────────────────────────────────
    # 📨 ENVÍO DE COPIA MANUAL (funciona en modo Independiente)
    # ────────────────────────────────────────────────────────────────────
    # El PC1 envía su snapshot al PC2 pulsando un botón. En el PC2, al
    # arrancar la app, aparece un desplegable "Hay una copia pendiente
    # para restaurar". Solo se guarda la ÚLTIMA copia por remitente
    # (upsert), así que si envías 3 veces solo queda la última.
    # ────────────────────────────────────────────────────────────────────

    @router.post("/sync/backup/send")
    async def backup_send(body: BackupSendBody):
        """PC1 envía una copia completa de sus datos al buzón del grupo.

        Funciona en cualquier modo (linked o independent). No sobrescribe
        automáticamente los datos del receptor; solo se guarda pendiente y
        el receptor decide si aplicar cuando abra la app.
        """
        lic = await _find_license(body.license_key)
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")
        if not _is_premium(lic):
            raise HTTPException(status_code=403, detail="backup_requires_premium")
        lkh = _key_hash(body.license_key)
        if not await _is_device_authorized(lkh, body.install_id):
            raise HTTPException(status_code=403, detail="device_not_authorized")
        now = _now()
        backup_id = str(uuid.uuid4())
        doc = {
            "backup_id": backup_id,
            "license_key_hash": lkh,
            "from_install_id": body.install_id,
            "label": (body.label or "").strip() or None,
            "data": body.data or {},
            "created_at": now,
            "consumed_by": [],  # lista de install_ids que ya lo aplicaron
        }
        # Upsert: solo mantenemos la ÚLTIMA copia por remitente
        await db[COLL_BACKUPS].replace_one(
            {"license_key_hash": lkh, "from_install_id": body.install_id},
            doc,
            upsert=True,
        )
        logger.info("backup/send from=%s size=%d keys", body.install_id, len(body.data or {}))
        return {"ok": True, "backup_id": backup_id, "created_at": _iso(now)}

    @router.get("/sync/backup/pending")
    async def backup_pending(license_key: str, install_id: str):
        """Devuelve las copias pendientes que este install_id AÚN NO ha aplicado.

        Excluye las propias (uno no restaura su propia copia). Ordenadas por
        más reciente primero.
        """
        lic = await _find_license(license_key)
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")
        lkh = _key_hash(license_key)
        cursor = db[COLL_BACKUPS].find({
            "license_key_hash": lkh,
            "from_install_id": {"$ne": install_id},
            "consumed_by": {"$nin": [install_id]},
        }).sort("created_at", -1)
        out = []
        async for d in cursor:
            out.append({
                "backup_id": d["backup_id"],
                "from_install_id": d["from_install_id"],
                "label": d.get("label"),
                "created_at": _iso(d["created_at"]),
                "keys_count": len(d.get("data") or {}),
                "data": d.get("data") or {},
            })
        return {"pending": out, "count": len(out)}

    @router.post("/sync/backup/consume")
    async def backup_consume(body: BackupConsumeBody):
        """Marca una copia como aplicada por este install_id (así ya no vuelve
        a mostrarse en /pending). NO borra la copia (puede haber otro device
        del grupo que aún no la haya aplicado)."""
        lic = await _find_license(body.license_key)
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")
        lkh = _key_hash(body.license_key)
        result = await db[COLL_BACKUPS].update_one(
            {"license_key_hash": lkh, "backup_id": body.backup_id},
            {"$addToSet": {"consumed_by": body.install_id},
             "$set": {"last_consumed_at": _now()}},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="backup_not_found")
        return {"ok": True, "backup_id": body.backup_id}

    return router
