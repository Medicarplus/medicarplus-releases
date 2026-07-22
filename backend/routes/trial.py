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
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt as _jwt
from fastapi import APIRouter, HTTPException, Request
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
    async def start_trial(body: TrialStartBody, request: Request):
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

        # 5) Envia email amb clau + PDFs (mateix mailer que Stripe)
        email_sent = False
        email_info = ""
        try:
            from services import mailer as _mailer
            email_sent, email_info = await _mailer.send_license_email(
                to_email=email_norm,
                client_name=body.name.strip() or email_norm,
                install_id=install_id,
                license_key=jwt_key,
                plan=TRIAL_PLAN,
                expires_at=expires_at,
            )
            logger.info("Trial email → %s: sent=%s info=%s", email_norm, email_sent, email_info)
        except Exception as ex:  # noqa: BLE001
            logger.exception("Trial email failed: %s", ex)

        return {
            "ok": True,
            "install_id": install_id,
            "license_key": jwt_key,
            "plan": TRIAL_PLAN,
            "expires_at": expires_at.isoformat(),
            "days": TRIAL_DAYS,
            "email_sent": email_sent,
            "email_info": email_info if not email_sent else None,
            "download_url": "https://github.com/Medicarplus/medicarplus-releases/releases/latest",
        }

    return router
