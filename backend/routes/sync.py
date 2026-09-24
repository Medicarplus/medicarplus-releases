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

from fastapi import APIRouter, HTTPException, Request
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
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.replace(microsecond=0).isoformat()
    return str(dt)


def _key_hash(key: str) -> str:
    return hashlib.sha256(key.strip().encode()).hexdigest()


def _check_admin_auth(request):
    """Auth para endpoints admin: exige X-Admin-Token header o admin_license_key=MASTER en query.
    Lanza HTTPException 403 si no autorizado.
    """
    import os as _os
    admin_token_env = (_os.environ.get("LICENSE_ADMIN_TOKEN") or "").strip()
    hdr = (request.headers.get("X-Admin-Token") or "").strip()
    q_key = (request.query_params.get("admin_license_key") or "").strip()
    if admin_token_env and hdr == admin_token_env:
        return True
    if q_key == MASTER_KEY:
        return True
    raise HTTPException(status_code=403, detail="admin_only")


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


class AdminPushToLicenseBody(BaseModel):
    """👑 Admin-only: enviar copia a la licencia de otro cliente sin estar vinculados.
    Requiere autenticación como MASTER (license_key=MASTER_KEY) o X-Admin-Token.
    """
    admin_license_key: str = Field(..., min_length=10, max_length=1500,
                                   description="Licencia MASTER del admin que envía")
    admin_install_id: str = Field(..., min_length=4, max_length=200)
    target_license_key: str = Field(..., min_length=10, max_length=1500,
                                    description="Licencia del cliente que recibirá la copia")
    data: dict[str, Any] = Field(default_factory=dict, description="Snapshot completo localStorage")
    label: Optional[str] = Field(default=None, max_length=200)


class AdminResetDevicesBody(BaseModel):
    admin_license_key: str = Field(..., min_length=10, max_length=1500)
    target_license_key: str = Field(..., min_length=10, max_length=1500)
    install_id: Optional[str] = Field(default=None, max_length=200)


COLL_BACKUPS = "sync_backups"
COLL_CLOUD_BACKUPS = "sync_cloud_backups"  # 🌤️ Feb 2026: archivo rotativo diario (últimas 30 copias por install_id)
CLOUD_BACKUP_KEEP = 30  # cuántas copias mantener por install_id


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

    # ────────────────────────────────────────────────────────────────────
    # 🌤️ CLOUD BACKUP AUTOMÁTICO DIARIO (feb 2026)
    # Archivo rotativo de las últimas 30 copias por install_id.
    # A prueba de pérdida catastrófica: SSD estropeado, formateo Windows,
    # ransomware, borrado accidental → cliente recupera desde el servidor.
    # ────────────────────────────────────────────────────────────────────
    @router.post("/sync/cloudbackup/send")
    async def cloud_backup_send(body: BackupSendBody):
        """Guarda una NUEVA copia (no upsert). Mantiene rotativo las últimas 30
        por install_id. Se llama silenciosamente 1 vez cada 24h desde la app.
        """
        lic = await _find_license(body.license_key)
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")
        if not _is_premium(lic):
            raise HTTPException(status_code=403, detail="cloudbackup_requires_premium")
        lkh = _key_hash(body.license_key)
        if not await _is_device_authorized(lkh, body.install_id):
            raise HTTPException(status_code=403, detail="device_not_authorized")
        # Sanity: limitar tamaño (2 MB max por copia — más que suficiente)
        try:
            import json as _json
            _size = len(_json.dumps(body.data or {}))
        except Exception:
            _size = 0
        MAX_BYTES = 2 * 1024 * 1024
        if _size > MAX_BYTES:
            raise HTTPException(status_code=413, detail=f"payload_too_large ({_size} > {MAX_BYTES})")
        now = _now()
        backup_id = str(uuid.uuid4())
        doc = {
            "backup_id": backup_id,
            "license_key_hash": lkh,
            "install_id": body.install_id,
            "label": (body.label or "").strip() or "auto-daily",
            "data": body.data or {},
            "size_bytes": _size,
            "keys_count": len(body.data or {}),
            "created_at": now,
        }
        await db[COLL_CLOUD_BACKUPS].insert_one(doc)
        # Rotación: elimina las que sobran (mantén solo las últimas CLOUD_BACKUP_KEEP)
        cursor = db[COLL_CLOUD_BACKUPS].find({
            "license_key_hash": lkh,
            "install_id": body.install_id,
        }).sort("created_at", -1).skip(CLOUD_BACKUP_KEEP)
        old_ids = [d["_id"] async for d in cursor]
        if old_ids:
            await db[COLL_CLOUD_BACKUPS].delete_many({"_id": {"$in": old_ids}})
        logger.info("cloudbackup/send install=%s size=%d keys=%d rotated=%d",
                    body.install_id, _size, len(body.data or {}), len(old_ids))
        return {"ok": True, "backup_id": backup_id, "created_at": _iso(now),
                "size_bytes": _size, "rotated": len(old_ids)}

    @router.get("/sync/cloudbackup/list")
    async def cloud_backup_list(license_key: str, install_id: str):
        """Lista metadata de las últimas N copias en la nube (sin data).
        Útil para el panel "Estado de tus copias" y para el flujo de restauración.
        """
        lic = await _find_license(license_key)
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")
        lkh = _key_hash(license_key)
        cursor = db[COLL_CLOUD_BACKUPS].find({
            "license_key_hash": lkh,
            "install_id": install_id,
        }, {"data": 0}).sort("created_at", -1)
        out = []
        async for d in cursor:
            out.append({
                "backup_id": d["backup_id"],
                "label": d.get("label"),
                "size_bytes": d.get("size_bytes", 0),
                "keys_count": d.get("keys_count", 0),
                "created_at": _iso(d["created_at"]),
            })
        return {"backups": out, "count": len(out), "keep": CLOUD_BACKUP_KEEP}

    @router.get("/sync/cloudbackup/get")
    async def cloud_backup_get(license_key: str, install_id: str, backup_id: str):
        """Devuelve el snapshot completo de una copia concreta (para restaurar)."""
        lic = await _find_license(license_key)
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")
        lkh = _key_hash(license_key)
        d = await db[COLL_CLOUD_BACKUPS].find_one({
            "license_key_hash": lkh,
            "install_id": install_id,
            "backup_id": backup_id,
        })
        if not d:
            raise HTTPException(status_code=404, detail="backup_not_found")
        return {
            "backup_id": d["backup_id"],
            "label": d.get("label"),
            "size_bytes": d.get("size_bytes", 0),
            "keys_count": d.get("keys_count", 0),
            "created_at": _iso(d["created_at"]),
            "data": d.get("data") or {},
        }

    # ────────────────────────────────────────────────────────────────────
    # 🔍 Snapshot del "otro PC" para el Asesor IA · Buscar descuadre
    # ────────────────────────────────────────────────────────────────────
    # Devuelve los datos que el otro ordenador de la MISMA licencia tiene:
    #   · En modo Fusionado → snapshot vivo desde sync_groups (COLL_STATE)
    #   · En modo Independiente → última copia recibida en el buzón (mailbox)
    # El frontend usa este snapshot para pedir a la IA una comparación día a
    # día y detectar entradas que falten o discrepen entre los dos PCs.
    @router.get("/sync/other-snapshot")
    async def other_snapshot(license_key: str, install_id: str):
        lic = await _find_license(license_key)
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")
        lkh = _key_hash(license_key)
        data_out: dict[str, Any] = {}
        source = None
        other_install_id = None
        cloud_ts = None

        # 🔒 Sólo consideramos "otro PC" a los devices ACTIVOS de esta licencia
        # distintos del que llama. Si no hay ninguno, no devolvemos data (aunque
        # queden restos huérfanos en sync_groups de instalaciones eliminadas).
        active_devices = await db[COLL_DEVICES].find({"license_key_hash": lkh}).to_list(length=10)
        active_ids = {d.get("install_id") for d in active_devices if d.get("install_id") and d.get("install_id") != install_id}

        state = await db[COLL_STATE].find_one({"_id": lkh})
        if active_ids and state and isinstance(state.get("data"), dict):
            latest_ts = None
            for key, item in state["data"].items():
                if not isinstance(item, dict):
                    continue
                author = item.get("author")
                # Sólo aceptamos data de un device ACTUALMENTE activo (no huérfanos)
                if not author or author == install_id or author not in active_ids:
                    continue
                data_out[key] = item.get("value")
                ts = _parse_iso(item.get("updated_at"))
                if ts and (latest_ts is None or ts > latest_ts):
                    latest_ts = ts
                    other_install_id = author
            cloud_ts = _iso(state.get("last_updated_at")) if state.get("last_updated_at") else None
            if data_out:
                source = "linked"

        # Fallback: última copia manual/admin recibida (aunque el emisor ya no
        # esté activo, la copia es real y sirve para comparar).
        if not data_out:
            cursor = db[COLL_BACKUPS].find({
                "license_key_hash": lkh,
                "from_install_id": {"$ne": install_id},
            }).sort("created_at", -1).limit(1)
            async for d in cursor:
                data_out = d.get("data") or {}
                other_install_id = d.get("from_install_id")
                cloud_ts = _iso(d.get("created_at")) if d.get("created_at") else None
                source = "backup_mailbox"
                break
        return {
            "ok": True,
            "has_data": bool(data_out),
            "source": source,
            "other_install_id": other_install_id,
            "cloud_updated_at": cloud_ts,
            "data": data_out,
        }

    # ────────────────────────────────────────────────────────────────────
    # 👑 ADMIN-ONLY · Enviar copia a CUALQUIER cliente sin vincular licencias
    # ────────────────────────────────────────────────────────────────────
    # Uso: yo (admin MASTER) tengo datos en mi PC. Quiero enviarle una copia
    # al PC de Victoria López Navas (otro cliente con licencia distinta).
    # Este endpoint deposita la copia en el buzón de SU licencia. Cuando
    # Victoria abra su app, verá el aviso "Copia pendiente de restaurar"
    # como si le llegara de un compañero suyo.
    # SEGURIDAD: solo la MASTER key puede llamar este endpoint.
    # ────────────────────────────────────────────────────────────────────

    @router.post("/sync/admin/push-to-license")
    async def admin_push_to_license(body: AdminPushToLicenseBody):
        # 1) Verificar que el que llama es el MASTER (única vía autorizada)
        if body.admin_license_key.strip() != MASTER_KEY:
            raise HTTPException(status_code=403, detail="admin_only")

        # 2) Verificar que la licencia destino existe (permite MASTER→MASTER también)
        target = await _find_license(body.target_license_key)
        if not target:
            raise HTTPException(status_code=404, detail="target_license_not_found")
        if target.get("status") == "revoked":
            raise HTTPException(status_code=403, detail="target_license_revoked")

        # 3) Depositar en el buzón de la LICENCIA DESTINO (upsert por remitente)
        target_lkh = _key_hash(body.target_license_key)
        now = _now()
        backup_id = str(uuid.uuid4())
        # Etiqueta clara para el receptor: "Copia enviada por el administrador"
        label = (body.label or "").strip() or "Copia enviada por MediCar Plus (admin)"
        # Remitente sintético: identificable como admin en el buzón
        admin_sender_id = f"admin:{body.admin_install_id}"
        doc = {
            "backup_id": backup_id,
            "license_key_hash": target_lkh,
            "from_install_id": admin_sender_id,
            "from_admin": True,
            "admin_license_key": body.admin_license_key.strip(),
            "target_license_key": body.target_license_key.strip(),
            "target_client_email": target.get("client_email"),
            "target_client_name": target.get("client_name"),
            "label": label,
            "data": body.data or {},
            "created_at": now,
            "consumed_by": [],
        }
        # Reemplaza cualquier copia anterior del ADMIN al mismo cliente
        await db[COLL_BACKUPS].replace_one(
            {"license_key_hash": target_lkh, "from_install_id": admin_sender_id},
            doc,
            upsert=True,
        )
        logger.info("admin/push-to-license admin=%s → target=%s (%s) size=%d keys",
                    body.admin_install_id, body.target_license_key[:20],
                    target.get("client_email"), len(body.data or {}))
        return {
            "ok": True,
            "backup_id": backup_id,
            "target_client_email": target.get("client_email"),
            "target_client_name": target.get("client_name"),
            "created_at": _iso(now),
        }

    # ────────────────────────────────────────────────────────────────────
    # 🛠️ ADMIN CLOUD BACKUP · listar las 30 copias del cliente + push individual
    # (Feb 2026 · para que soporte pueda enviar CUALQUIER copia histórica al cliente)
    # ────────────────────────────────────────────────────────────────────
    @router.get("/sync/admin/cloudbackup/list")
    async def admin_cloudbackup_list(target_install_id: str, request: Request):
        """Lista las últimas 30 cloud backups de CUALQUIER cliente (metadata, sin data).
        Auth: X-Admin-Token header (opcional, si está configurado) O MASTER key.
        """
        _check_admin_auth(request)
        cursor = db[COLL_CLOUD_BACKUPS].find({
            "install_id": target_install_id,
        }, {"data": 0}).sort("created_at", -1)
        out = []
        async for d in cursor:
            out.append({
                "backup_id": d["backup_id"],
                "label": d.get("label"),
                "size_bytes": d.get("size_bytes", 0),
                "keys_count": d.get("keys_count", 0),
                "created_at": _iso(d["created_at"]),
            })
        return {"backups": out, "count": len(out), "target_install_id": target_install_id}

    @router.post("/sync/admin/cloudbackup/push")
    async def admin_cloudbackup_push(body: dict, request: Request):
        """Envía una copia HISTÓRICA concreta (backup_id de sync_cloud_backups) al buzón
        del cliente destino. El cliente la verá como "Copia enviada por soporte" al abrir la app.

        Body: { target_license_key, target_install_id, backup_id, label? }
        """
        _check_admin_auth(request)
        target_lk = (body.get("target_license_key") or "").strip()
        target_iid = (body.get("target_install_id") or "").strip()
        backup_id = (body.get("backup_id") or "").strip()
        if not target_lk or not target_iid or not backup_id:
            raise HTTPException(status_code=400, detail="missing_required_fields")
        target = await _find_license(target_lk)
        if not target:
            raise HTTPException(status_code=404, detail="target_license_not_found")
        # Cargar la copia histórica solicitada
        cb = await db[COLL_CLOUD_BACKUPS].find_one({
            "install_id": target_iid,
            "backup_id": backup_id,
        })
        if not cb:
            raise HTTPException(status_code=404, detail="cloudbackup_not_found")
        # Depositarla en el buzón pending del cliente (upsert admin sender)
        target_lkh = _key_hash(target_lk)
        now = _now()
        new_backup_id = str(uuid.uuid4())
        created_human = cb["created_at"].strftime("%d/%m/%Y %H:%M") if isinstance(cb.get("created_at"), datetime) else str(cb.get("created_at",""))
        label = (body.get("label") or "").strip() or f"📩 Copia enviada por soporte (del {created_human})"
        admin_sender_id = "admin:support-cloud"
        doc = {
            "backup_id": new_backup_id,
            "license_key_hash": target_lkh,
            "from_install_id": admin_sender_id,
            "from_admin": True,
            "admin_source_backup_id": backup_id,  # trazabilidad
            "admin_source_date": cb["created_at"].isoformat() if isinstance(cb.get("created_at"), datetime) else None,
            "target_license_key": target_lk,
            "target_install_id": target_iid,
            "target_client_email": target.get("client_email"),
            "target_client_name": target.get("client_name"),
            "label": label,
            "data": cb.get("data") or {},
            "created_at": now,
            "consumed_by": [],
        }
        await db[COLL_BACKUPS].replace_one(
            {"license_key_hash": target_lkh, "from_install_id": admin_sender_id},
            doc,
            upsert=True,
        )
        logger.info("admin/cloudbackup/push target=%s source_bid=%s new_bid=%s",
                    target_iid, backup_id[:8], new_backup_id[:8])
        return {
            "ok": True,
            "backup_id": new_backup_id,
            "source_backup_id": backup_id,
            "source_date": doc["admin_source_date"],
            "target_client_email": target.get("client_email"),
            "target_client_name": target.get("client_name"),
            "created_at": _iso(now),
        }

    @router.post("/sync/admin/reset-devices")
    async def admin_reset_devices(body: AdminResetDevicesBody):
        """👑 Libera los slots de dispositivos de una licencia (borra sync_devices)."""
        if body.admin_license_key.strip() != MASTER_KEY:
            raise HTTPException(status_code=403, detail="admin_only")
        target = await _find_license(body.target_license_key)
        if not target:
            raise HTTPException(status_code=404, detail="target_license_not_found")
        lkh = _key_hash(body.target_license_key)
        if body.install_id:
            res = await db[COLL_DEVICES].delete_many({"license_key_hash": lkh, "install_id": body.install_id})
        else:
            res = await db[COLL_DEVICES].delete_many({"license_key_hash": lkh})
        logger.info("admin/reset-devices target=%s removed=%d", body.target_license_key[:20], res.deleted_count)
        return {"ok": True, "removed": res.deleted_count}

    @router.get("/sync/admin/list-licenses")
    async def admin_list_licenses(admin_license_key: str):
        """👑 Lista licencias activas para el selector de destino en la UI admin."""
        if (admin_license_key or "").strip() != MASTER_KEY:
            raise HTTPException(status_code=403, detail="admin_only")
        cursor = db.licenses.find(
            {"status": {"$ne": "revoked"}},
            {"license_key": 1, "client_email": 1, "client_name": 1,
             "plan": 1, "install_id": 1, "created_at": 1, "_id": 0},
        ).sort("created_at", -1).limit(500)
        out = []
        async for d in cursor:
            out.append({
                "license_key": d.get("license_key"),
                "client_email": d.get("client_email"),
                "client_name": d.get("client_name"),
                "plan": d.get("plan"),
                "install_id": d.get("install_id"),
            })
        return {"licenses": out, "count": len(out)}

    @router.get("/sync/admin/other-license-snapshot")
    async def admin_other_license_snapshot(admin_license_key: str, target_license_key: str):
        """👑 ADMIN-ONLY · Devuelve el snapshot de datos de una licencia objetivo.

        Se combinan dos fuentes:
          · sync_groups (COLL_STATE) → últimos datos push del cliente en la nube.
          · última copia del buzón de la licencia (si no hay estado vivo).

        Uso: comparar los datos del admin contra los de cualquier cliente para
        auditar o ayudar a detectar descuadres/entradas faltantes en su caja.
        """
        if (admin_license_key or "").strip() != MASTER_KEY:
            raise HTTPException(status_code=403, detail="admin_only")
        target_lic = await _find_license(target_license_key)
        if not target_lic:
            raise HTTPException(status_code=404, detail="target_license_not_found")
        lkh = _key_hash(target_license_key)
        data_out: dict[str, Any] = {}
        source = None
        author = None
        cloud_ts = None
        state = await db[COLL_STATE].find_one({"_id": lkh})
        if state and isinstance(state.get("data"), dict):
            latest_ts = None
            for key, item in state["data"].items():
                if not isinstance(item, dict):
                    continue
                data_out[key] = item.get("value")
                ts = _parse_iso(item.get("updated_at"))
                if ts and (latest_ts is None or ts > latest_ts):
                    latest_ts = ts
                    author = item.get("author") or author
            cloud_ts = _iso(state.get("last_updated_at")) if state.get("last_updated_at") else None
            if data_out:
                source = "linked"
        if not data_out:
            # Fallback: última copia recibida (mailbox), independientemente del emisor
            cursor = db[COLL_BACKUPS].find({"license_key_hash": lkh}).sort("created_at", -1).limit(1)
            async for d in cursor:
                data_out = d.get("data") or {}
                author = d.get("from_install_id")
                cloud_ts = _iso(d.get("created_at")) if d.get("created_at") else None
                source = "backup_mailbox"
                break
        return {
            "ok": True,
            "has_data": bool(data_out),
            "source": source,
            "target_client_name": target_lic.get("client_name"),
            "target_client_email": target_lic.get("client_email"),
            "target_plan": target_lic.get("plan"),
            "author_install_id": author,
            "cloud_updated_at": cloud_ts,
            "data": data_out,
        }

    return router
