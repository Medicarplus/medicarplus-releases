"""API pública per Referral Program."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from services.referrals import (
    find_active_referrer,
    is_valid_referral_format,
    ensure_unique_referral_code,
)

logger = logging.getLogger(__name__)


class ReferralValidateResponse(BaseModel):
    valid: bool
    referrer_name: Optional[str] = None
    referrer_plan: Optional[str] = None


def create_router(db: AsyncIOMotorDatabase) -> APIRouter:
    router = APIRouter(prefix="/api/referrals", tags=["referrals"])
    coll = db.licenses

    @router.get("/validate")
    async def validate_code(code: str = Query(..., min_length=8, max_length=20)) -> ReferralValidateResponse:
        """Valida un codi de referit abans que l'usuari el faci servir."""
        if not is_valid_referral_format(code):
            return ReferralValidateResponse(valid=False)
        ref = await find_active_referrer(coll, code)
        if not ref:
            return ReferralValidateResponse(valid=False)
        return ReferralValidateResponse(
            valid=True,
            referrer_name=(ref.get("client_name") or "").split("@")[0][:30] or "Cliente",
            referrer_plan=str(ref.get("plan") or "").upper(),
        )

    @router.get("/my-code")
    async def my_referral_code(
        install_id: str = Query(..., min_length=6),
    ) -> dict:
        """Retorna el referral_code de la llicència activa de l'install_id + estadístiques.

        Requereix llicència ACTIVA i PAGADA (Trial NO té codi propi — el pot fer servir però
        no pot referir fins que passi a plan pagat).
        """
        install_id_norm = install_id.strip()
        doc = await coll.find_one(
            {"status": "active",
             "$or": [
                 {"install_id": install_id_norm},
                 {"linked_install_ids": install_id_norm},
             ]},
            sort=[("created_at", -1)],
        )
        if not doc:
            return {"ok": False, "reason": "no_active_license"}

        plan_upper = str(doc.get("plan") or "").upper()
        # Trial no pot referir
        if plan_upper == "TRIAL":
            return {
                "ok": False,
                "reason": "trial_cannot_refer",
                "message": "Solo los clientes con plan pagado (Standard o Premium) pueden participar en el programa de referidos.",
            }

        # Assigna referral_code si encara no en té
        code = doc.get("referral_code")
        if not code:
            code = await ensure_unique_referral_code(coll)
            await coll.update_one({"_id": doc["_id"]}, {"$set": {"referral_code": code}})

        rewards = doc.get("referral_rewards") or []
        return {
            "ok": True,
            "referral_code": code,
            "plan": plan_upper,
            "share_url": f"https://medicarplus.es/?ref={code}",
            "total_referrals": len(rewards),
            "months_earned": sum(int(r.get("months_added") or 0) for r in rewards),
            "recent_rewards": [
                {
                    "referred_email_masked": _mask_email(r.get("referred_email") or ""),
                    "awarded_at": r.get("awarded_at"),
                    "months_added": r.get("months_added"),
                }
                for r in rewards[-10:]
            ],
        }

    return router


def _mask_email(email: str) -> str:
    """m***@example.com per protegir privacitat dels referits."""
    if not email or "@" not in email:
        return ""
    user, dom = email.split("@", 1)
    if len(user) <= 1:
        return f"*@{dom}"
    return f"{user[0]}***@{dom}"
