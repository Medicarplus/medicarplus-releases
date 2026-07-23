"""
Referral Program per MediCar Plus.

Regles del negoci:
- Cada llicència ACTIVA té un `referral_code` únic (format `MC-XXXX-XXXX`).
- Un client A pot compartir la seva URL de referit: `https://medicarplus.es?ref=<code>`.
- Un client B usa el codi al signup del Trial O al checkout Stripe.
- Quan B **paga la seva primera subscripció** (Trial NO compta), A rep +2 mesos
  gratis del mateix cicle (mensual o anual) que ja té.
- La recompensa s'aplica via Stripe: cupó 100% off amb `duration_in_months=2`.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Optional

import stripe as stripe_sdk

logger = logging.getLogger(__name__)


REF_CODE_PATTERN = re.compile(r"^MC-[A-Z0-9]{4}-[A-Z0-9]{4}$")


def generate_referral_code() -> str:
    """Genera un codi únic de 10 caràcters legibles (sense O, 0, I, 1)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    part1 = "".join(secrets.choice(alphabet) for _ in range(4))
    part2 = "".join(secrets.choice(alphabet) for _ in range(4))
    return f"MC-{part1}-{part2}"


def is_valid_referral_format(code: Optional[str]) -> bool:
    return bool(code) and bool(REF_CODE_PATTERN.match(str(code).upper()))


async def ensure_unique_referral_code(coll) -> str:
    """Genera un referral_code garantit únic dins la col·lecció licenses."""
    for _ in range(10):
        code = generate_referral_code()
        exists = await coll.find_one({"referral_code": code})
        if not exists:
            return code
    # Fallback (extremadament improbable)
    return generate_referral_code() + "-" + secrets.token_hex(2).upper()


async def find_active_referrer(coll, referral_code: str) -> Optional[dict]:
    """Cerca la llicència ACTIVA del referrer per codi. None si no existeix o inactiva."""
    if not is_valid_referral_format(referral_code):
        return None
    code = str(referral_code).upper()
    doc = await coll.find_one({"referral_code": code, "status": "active"})
    return doc


async def apply_stripe_referral_reward(
    *,
    referrer_doc: dict,
    referred_install_id: str,
    referred_email: Optional[str],
    referred_plan: str,
    coll,
) -> tuple[bool, str]:
    """
    Aplica 2 mesos gratis al referrer via cupó Stripe 100% off (duration_in_months=2).

    Returns:
        (success, info_message)
    """
    now = datetime.now(timezone.utc)

    # Evita doble recompensa per mateix referit
    existing_rewards = referrer_doc.get("referral_rewards") or []
    already = any(
        (r.get("referred_install_id") == referred_install_id)
        for r in existing_rewards
    )
    if already:
        return False, "already_rewarded_for_this_referred"

    stripe_sub_id = referrer_doc.get("stripe_subscription_id")
    if not stripe_sub_id:
        # No hi ha subscripció Stripe (potser és llicència generada manualment)
        # → estenem simplement 60 dies l'expires_at de la llicència.
        await _extend_license_expiration(coll, referrer_doc, months=2)
        await _record_reward(
            coll, referrer_doc,
            referred_install_id=referred_install_id,
            referred_email=referred_email,
            referred_plan=referred_plan,
            info="license_extended_60_days_no_stripe",
        )
        return True, "license_extended_no_stripe"

    api_key = os.environ.get("STRIPE_API_KEY") or ""
    if not api_key:
        logger.error("STRIPE_API_KEY missing — cannot apply referral coupon")
        return False, "stripe_key_missing"

    stripe_sdk.api_key = api_key

    try:
        # 1) Assegurar cupó "REFERRAL_2M" existent (100% off, 2 mesos, mensual)
        coupon = await _get_or_create_referral_coupon()
        # 2) Aplicar el cupó a la subscripció existent
        stripe_sdk.Subscription.modify(
            stripe_sub_id,
            coupon=coupon.id,
            metadata={
                "referral_reward": "true",
                "referred_install_id": referred_install_id,
                "referred_email": referred_email or "",
                "rewarded_at": now.isoformat(),
            },
        )
        # 3) Registra a la BD
        await _record_reward(
            coll, referrer_doc,
            referred_install_id=referred_install_id,
            referred_email=referred_email,
            referred_plan=referred_plan,
            info=f"stripe_coupon_{coupon.id}",
        )
        logger.info(
            "Referral coupon applied to %s (sub=%s) for referred %s",
            referrer_doc.get("client_email"), stripe_sub_id, referred_install_id,
        )
        return True, f"stripe_coupon_applied:{coupon.id}"
    except Exception as ex:  # noqa: BLE001
        logger.exception("Stripe coupon application failed: %s", ex)
        return False, f"stripe_error:{ex}"


async def _get_or_create_referral_coupon():
    """Retorna el cupó 'REFERRAL_2M' (100% off, 2 mesos, per REFERRER). El crea si no existeix."""
    coupon_id = "MEDICAR_REFERRAL_2M"
    try:
        return stripe_sdk.Coupon.retrieve(coupon_id)
    except stripe_sdk.error.InvalidRequestError:
        return stripe_sdk.Coupon.create(
            id=coupon_id,
            percent_off=100,
            duration="repeating",
            duration_in_months=2,
            name="Referral 2 months free",
            metadata={"source": "medicarplus_referral_program", "role": "referrer"},
        )


async def get_or_create_referred_coupon():
    """Retorna el cupó 'REFERRED_1M' (100% off, 1 mes, per REFERIT nou). El crea si no existeix.

    Aquest cupó s'aplica al checkout session del nou client quan ve amb un `referred_by`
    vàlid, així veu directament a Stripe "1er mes gratis" abans de pagar.
    """
    coupon_id = "MEDICAR_REFERRED_1M"
    try:
        return stripe_sdk.Coupon.retrieve(coupon_id)
    except stripe_sdk.error.InvalidRequestError:
        return stripe_sdk.Coupon.create(
            id=coupon_id,
            percent_off=100,
            duration="repeating",
            duration_in_months=1,
            name="Referred first month free",
            metadata={"source": "medicarplus_referral_program", "role": "referred"},
        )


async def _extend_license_expiration(coll, doc: dict, *, months: int) -> None:
    """Estén l'expires_at 2 mesos (per llicències sense Stripe)."""
    from dateutil.relativedelta import relativedelta
    current = doc.get("expires_at")
    if isinstance(current, str):
        try:
            current_dt = datetime.fromisoformat(current.replace("Z", "+00:00"))
        except ValueError:
            current_dt = datetime.now(timezone.utc)
    elif isinstance(current, datetime):
        current_dt = current
    else:
        current_dt = datetime.now(timezone.utc)
    new_expiry = current_dt + relativedelta(months=months)
    await coll.update_one(
        {"_id": doc["_id"]},
        {"$set": {"expires_at": new_expiry.isoformat()}},
    )


async def _record_reward(
    coll,
    doc: dict,
    *,
    referred_install_id: str,
    referred_email: Optional[str],
    referred_plan: str,
    info: str,
) -> None:
    reward = {
        "referred_install_id": referred_install_id,
        "referred_email": referred_email,
        "referred_plan": referred_plan,
        "awarded_at": datetime.now(timezone.utc).isoformat(),
        "months_added": 2,
        "reward_info": info,
    }
    await coll.update_one(
        {"_id": doc["_id"]},
        {"$push": {"referral_rewards": reward},
         "$inc": {"referral_reward_count": 1}},
    )
