"""Admin users management (multi-user login).

Owner (`ADMINISTRADOR` / Mbrugulat24) can create/delete additional admin users.
Each user has their own username + password_hash. To revoke access, just delete.

Collection: `admin_users`
  { _id: username (upper), password_hash, is_owner, created_at, created_by, notes }
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Optional

import bcrypt
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def _admin_ok(x_admin_token: Optional[str]) -> None:
    expected = os.environ.get("LICENSE_ADMIN_TOKEN", "")
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=8, max_length=256)
    notes: Optional[str] = Field(default=None, max_length=500)


def build_users_router(db):

    async def _seed_owner():
        """Al iniciar la app, si el usuario ADMINISTRADOR no está en la BD,
        lo creamos usando el hash del .env. Así el owner siempre puede entrar
        con su Mbrugulat24 aunque un día borre la colección por error."""
        owner_username = (os.environ.get("ADMIN_LOGIN_USERNAME") or "ADMINISTRADOR").upper()
        env_hash = (os.environ.get("ADMIN_LOGIN_PASSWORD_HASH") or "").strip()
        if not env_hash:
            return
        exists = await db.admin_users.find_one({"_id": owner_username})
        if not exists:
            await db.admin_users.insert_one({
                "_id": owner_username,
                "password_hash": env_hash,
                "is_owner": True,
                "created_at": _now(),
                "created_by": "system-seed",
                "notes": "Owner · seeded from .env",
            })

    @router.get("")
    async def list_users(x_admin_token: Optional[str] = Header(None)):
        _admin_ok(x_admin_token)
        await _seed_owner()  # idempotent
        items = []
        async for u in db.admin_users.find({}, {"password_hash": 0}).sort("created_at", 1):
            u["username"] = u.pop("_id")
            items.append(u)
        return {"items": items, "total": len(items)}

    @router.post("")
    async def create_user(body: UserCreate, x_admin_token: Optional[str] = Header(None)):
        _admin_ok(x_admin_token)
        uname = body.username.strip().upper()
        if not re.match(r"^[A-Z0-9_-]{2,64}$", uname):
            raise HTTPException(status_code=400, detail="username inválido (solo A-Z, 0-9, - _)")
        existing = await db.admin_users.find_one({"_id": uname})
        if existing:
            raise HTTPException(status_code=409, detail=f"Ya existe usuario '{uname}'")
        hashed = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
        await db.admin_users.insert_one({
            "_id": uname,
            "password_hash": hashed,
            "is_owner": False,
            "created_at": _now(),
            "created_by": "admin-panel",
            "notes": (body.notes or "").strip() or None,
        })
        return {"ok": True, "username": uname}

    @router.delete("/{username}")
    async def delete_user(username: str, x_admin_token: Optional[str] = Header(None)):
        _admin_ok(x_admin_token)
        uname = username.strip().upper()
        doc = await db.admin_users.find_one({"_id": uname})
        if not doc:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if doc.get("is_owner"):
            raise HTTPException(status_code=403, detail="No se puede borrar al owner")
        await db.admin_users.delete_one({"_id": uname})
        return {"ok": True, "deleted": uname}

    return router
