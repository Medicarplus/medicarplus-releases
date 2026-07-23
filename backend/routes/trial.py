"""
Automatic Trial · /api/trial/start
==================================
Endpoint públic per generar una llicència TRIAL de 60 dies al moment,
sense intervenció manual. Envia email amb la clau + PDFs (mateix flux que Stripe).

Regles anti-abús:
- 1 sol trial per email (històric permanent).
- Honeypot antispam (camp `website` invisible al form).
- Rate limit global heretat del limiter de server.py.
- Consent obligatori (checkbox privacitat).
"""
from __future__ import annotations

import logging
import os
import re
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt as _jwt
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)

TRIAL_DAYS = 60
TRIAL_PLAN = "TRIAL"


class TrialStartBody(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=120)
    company: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=40)
    consent: bool = Field(default=False)
    website: Optional[str] = Field(default=None, max_length=200)  # honeypot


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _short_uuid() -> str:
    return uuid.uuid4().hex[:8].upper()


def _mint_trial_jwt(*, install_id: str, license_id: str, expires_at: datetime) -> str:
    payload = {
        "iss": os.environ.get("LICENSE_ISSUER", "caja-del-dia-license-server"),
        "sub": install_id,
        "jti": license_id,
        "plan": TRIAL_PLAN,
        "iat": int(_now().timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return _jwt.encode(payload, os.environ.get("LICENSE_SECRET", ""), algorithm="HS256")


def build_trial_router(db: AsyncIOMotorDatabase) -> APIRouter:
    router = APIRouter(prefix="/trial", tags=["trial"])

    @router.post("/start")
    async def start_trial(body: TrialStartBody, request: Request, background_tasks: BackgroundTasks):
        # 1) Honeypot antispam
        if body.website and body.website.strip():
            logger.info("trial honeypot triggered by %s", body.email)
            raise HTTPException(status_code=400, detail="invalid_request")

        # 2) Consent obligatori
        if not body.consent:
            raise HTTPException(status_code=400, detail="consent_required")

        email_norm = str(body.email).strip().lower()

        # 3) Anti-abús: 1 trial per email (històric complet)
        existing = await db.licenses.find_one({
            "client_email": email_norm,
            "plan": TRIAL_PLAN,
        })
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Ya has solicitado una prueba gratuita con este email. "
                       "Revisa tu bandeja de entrada (incluye spam) o contacta con info@medicarplus.es.",
            )

        # 4) Genera llicència TRIAL
        install_id = f"CD-TRIAL-{_short_uuid()}-{_short_uuid()}"
        license_id = str(uuid.uuid4())
        created_at = _now()
        expires_at = created_at + timedelta(days=TRIAL_DAYS)

        jwt_key = _mint_trial_jwt(
            install_id=install_id,
            license_id=license_id,
            expires_at=expires_at,
        )

        doc = {
            "id": license_id,
            "install_id": install_id,
            "client_name": body.name.strip(),
            "client_email": email_norm,
            "company_name": (body.company or "").strip() or None,
            "phone": (body.phone or "").strip() or None,
            "plan": TRIAL_PLAN,
            "status": "active",
            "duration_days": TRIAL_DAYS,
            "notes": "Auto-generated · Public trial endpoint",
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "revoked_at": None,
            "revoked_reason": None,
            "last_verified_at": None,
            "verify_count": 0,
            "license_key": jwt_key,
            "source": "trial_auto",
            "ip": request.client.host if request and request.client else "-",
        }
        await db.licenses.insert_one(doc)
        logger.info("Auto-trial created for %s (install_id=%s)", email_norm, install_id)

        # 5) Envia email en BACKGROUND (no bloqueja la resposta HTTP).
        # L'usuari rep la clau al moment i l'email arriba als 5-15s per correu.
        async def _send_email_bg():
            try:
                from services import mailer as _mailer
                sent, info = await _mailer.send_license_email(
                    to_email=email_norm,
                    client_name=body.name.strip() or email_norm,
                    install_id=install_id,
                    license_key=jwt_key,
                    plan=TRIAL_PLAN,
                    expires_at=expires_at,
                )
                logger.info("Trial email (bg) → %s: sent=%s info=%s", email_norm, sent, info)
                # Marca el resultat al doc perquè el user pugui saber si va fallar
                try:
                    await db.licenses.update_one(
                        {"id": license_id},
                        {"$set": {"email_sent": sent, "email_info": info, "email_sent_at": _now().isoformat()}},
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("failed to persist email status")
            except Exception as ex:  # noqa: BLE001
                logger.exception("Trial email failed in background: %s", ex)

        background_tasks.add_task(_send_email_bg)

        return {
            "ok": True,
            "install_id": install_id,
            "license_key": jwt_key,
            "plan": TRIAL_PLAN,
            "expires_at": expires_at.isoformat(),
            "days": TRIAL_DAYS,
            "email_sent": True,  # optimista · s'envia en background
            "email_pending": True,
            "email_info": None,
            "download_url": "https://github.com/Medicarplus/medicarplus-releases/releases/latest",
        }

    return router
