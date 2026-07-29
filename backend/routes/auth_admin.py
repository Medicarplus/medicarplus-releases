"""Admin login endpoint (username + password) for MediCar Plus.

The MASTER key remains functional as before via the activation modal. This
endpoint is a *second* authentication path so the owner (or a delegated
employee in the future) can log in with:

    Username: ADMINISTRADOR  (case-insensitive)
    Password: <value hashed with bcrypt and stored in ADMIN_LOGIN_PASSWORD_HASH>

On success the frontend will locally set the MASTER license and reload. The
backend does not return the master key — the frontend already knows it. We
just answer `{"ok": true}` so the client can proceed.

Brute force protection: 5 failed attempts / 15 min per source IP, tracked in an
in-memory dict (single-worker uvicorn). Restart clears the counter.
"""

from __future__ import annotations

import os
import time
from typing import Dict, Tuple

import bcrypt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field


router = APIRouter(prefix="/auth", tags=["auth-admin"])


# --- Brute-force lockout (per IP) --------------------------------------------
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 15 * 60  # 15 min

# ip -> (failed_count, first_failure_epoch)
_attempts: Dict[str, Tuple[int, float]] = {}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_lockout(ip: str) -> None:
    """Raise 429 if this IP has exceeded the failed-attempt budget."""
    now = time.time()
    entry = _attempts.get(ip)
    if not entry:
        return
    count, first_ts = entry
    if now - first_ts > _WINDOW_SECONDS:
        # Window elapsed — reset silently.
        _attempts.pop(ip, None)
        return
    if count >= _MAX_ATTEMPTS:
        remaining = int(_WINDOW_SECONDS - (now - first_ts))
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos fallidos. Inténtalo de nuevo en {remaining // 60} min {remaining % 60} s.",
        )


def _register_failure(ip: str) -> None:
    now = time.time()
    entry = _attempts.get(ip)
    if not entry or (now - entry[1]) > _WINDOW_SECONDS:
        _attempts[ip] = (1, now)
    else:
        _attempts[ip] = (entry[0] + 1, entry[1])


def _reset_failures(ip: str) -> None:
    _attempts.pop(ip, None)


# --- Request schema ----------------------------------------------------------
class AdminLoginIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


# --- Endpoint ----------------------------------------------------------------
@router.post("/admin-login")
async def admin_login(body: AdminLoginIn, request: Request):
    ip = _client_ip(request)
    _check_lockout(ip)

    expected_user = (os.environ.get("ADMIN_LOGIN_USERNAME") or "").strip()
    stored_hash = (os.environ.get("ADMIN_LOGIN_PASSWORD_HASH") or "").strip()
    if not expected_user or not stored_hash:
        # Misconfigured server — fail closed but don't leak internals.
        raise HTTPException(status_code=503, detail="Login de administrador no configurado.")

    # Username is case-insensitive per user's requirement.
    username_ok = body.username.strip().upper() == expected_user.upper()

    # Always run bcrypt.checkpw even if username is wrong to reduce timing side-channel.
    try:
        password_ok = bcrypt.checkpw(body.password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception:
        password_ok = False

    if not (username_ok and password_ok):
        _register_failure(ip)
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")

    _reset_failures(ip)
    # Devolvemos también el admin token del backend para que admin.html pueda usarlo
    # sin exponerlo en el frontend hardcodeado.
    admin_token = os.environ.get("LICENSE_ADMIN_TOKEN", "")
    return {"ok": True, "admin_token": admin_token or None}


class UnifiedGateIn(BaseModel):
    """Cualquiera de los dos vale: password (Mbrugulat24) O admin token literal."""
    credential: str = Field(..., min_length=1, max_length=512)


@router.post("/admin-gate")
async def admin_unified_gate(body: UnifiedGateIn, request: Request):
    """Puerta unificada para el panel admin.

    Acepta cualquiera de estos:
    - Password del owner `Mbrugulat24` (bcrypt via .env)
    - Password de cualquier usuario adicional creado en `admin_users` collection
    - Token literal `LICENSE_ADMIN_TOKEN` (por si el owner pierde su password)

    Devuelve el admin token en todos los casos → el frontend lo usa para las
    llamadas API subsiguientes con header `X-Admin-Token`.
    """
    ip = _client_ip(request)
    _check_lockout(ip)
    admin_token_env = os.environ.get("LICENSE_ADMIN_TOKEN", "")
    cred = body.credential.strip()

    # Case 1: match directo con el token literal
    token_ok = bool(admin_token_env) and cred == admin_token_env
    matched_user = None

    if not token_ok:
        # Case 2: match como password contra la colección admin_users
        try:
            from server import db as _srv_db
            async for u in _srv_db.admin_users.find({}, {"password_hash": 1}):
                stored = (u.get("password_hash") or "").strip()
                if not stored:
                    continue
                try:
                    if bcrypt.checkpw(cred.encode("utf-8"), stored.encode("utf-8")):
                        matched_user = u.get("_id")
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Case 3: fallback contra el hash del .env directamente (backwards compat)
        if not matched_user:
            stored_hash = (os.environ.get("ADMIN_LOGIN_PASSWORD_HASH") or "").strip()
            if stored_hash:
                try:
                    if bcrypt.checkpw(cred.encode("utf-8"), stored_hash.encode("utf-8")):
                        matched_user = (os.environ.get("ADMIN_LOGIN_USERNAME") or "ADMINISTRADOR").upper()
                except Exception:
                    pass

    if not (token_ok or matched_user):
        _register_failure(ip)
        raise HTTPException(status_code=401, detail="Credencial incorrecta")

    _reset_failures(ip)
    used = "token" if token_ok else ("password:" + (matched_user or "?"))
    return {"ok": True, "admin_token": admin_token_env or None, "used": used}
