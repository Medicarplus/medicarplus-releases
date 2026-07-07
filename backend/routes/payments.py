"""
Payments router · Stripe Checkout via emergentintegrations (one-off)
                + Stripe Subscriptions via raw `stripe` SDK (recurring).

⚠️ Subscriptions mode is READY but INACTIVE fins que l'usuari configuri
les variables d'entorn amb els Price IDs de Stripe (veure guia-stripe-setup.html):

  STRIPE_API_KEY               = sk_test_xxx  (o sk_live_xxx a producció)
  STRIPE_WEBHOOK_SECRET        = whsec_xxx    (webhook signing secret)
  STRIPE_PRICE_STD_MES         = price_xxx    (29.90€/mes)
  STRIPE_PRICE_STD_ANY         = price_xxx    (299.90€/any)
  STRIPE_PRICE_PREMIUM_MES     = price_xxx    (39.90€/mes)
  STRIPE_PRICE_PREMIUM_ANY     = price_xxx    (399.90€/any)

Si les variables STRIPE_PRICE_* no hi són, /subscription/enabled retorna
false i el frontend amaga el botó de pagament amb targeta.
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import stripe as stripe_sdk

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout,
    CheckoutSessionRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])

# ---------------------------------------------------------------------------
# FIXED PACKAGES · defined on backend only (security: never trust frontend prices)
# ---------------------------------------------------------------------------
PACKAGES = {
    "STD_MES":     {"amount": 29.90,  "currency": "eur", "label": "STD Mensual",     "period": "month", "days": 30,  "env_price": "STRIPE_PRICE_STD_MES"},
    "STD_ANY":     {"amount": 299.90, "currency": "eur", "label": "STD Anual",       "period": "year",  "days": 365, "env_price": "STRIPE_PRICE_STD_ANY"},
    "PREMIUM_MES": {"amount": 39.90,  "currency": "eur", "label": "PREMIUM Mensual", "period": "month", "days": 30,  "env_price": "STRIPE_PRICE_PREMIUM_MES"},
    "PREMIUM_ANY": {"amount": 399.90, "currency": "eur", "label": "PREMIUM Anual",   "period": "year",  "days": 365, "env_price": "STRIPE_PRICE_PREMIUM_ANY"},
}


def _stripe_api_key() -> str:
    k = os.environ.get("STRIPE_API_KEY", "").strip()
    if not k:
        raise HTTPException(status_code=503, detail="Stripe no està configurat al servidor.")
    return k


def _subscriptions_configured() -> dict:
    """Return which packages have a Stripe Price ID configured."""
    result = {}
    for pkg_id, cfg in PACKAGES.items():
        env_name = cfg["env_price"]
        price_id = os.environ.get(env_name, "").strip()
        result[pkg_id] = bool(price_id)
    return result


# ===========================================================================
# ONE-OFF CHECKOUT (llegat — via emergentintegrations)
# ===========================================================================
class CreateCheckoutBody(BaseModel):
    package_id: str
    origin_url: str
    request_id: Optional[str] = None
    customer_email: Optional[str] = None


def _get_emergent_client(request: Request) -> StripeCheckout:
    api_key = _stripe_api_key()
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    return StripeCheckout(api_key=api_key, webhook_url=webhook_url)


@router.post("/create-checkout")
async def create_checkout(body: CreateCheckoutBody, request: Request):
    """One-off payment (targeta única). Legacy — no auto-renewal."""
    if body.package_id not in PACKAGES:
        raise HTTPException(status_code=400, detail=f"Paquet desconegut: {body.package_id}")
    pkg = PACKAGES[body.package_id]

    origin = body.origin_url.rstrip("/")
    success_url = f"{origin}/request-license?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/request-license?cancelled=1"

    stripe_checkout = _get_emergent_client(request)
    checkout_req = CheckoutSessionRequest(
        amount=pkg["amount"],
        currency=pkg["currency"],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "mode": "one_off",
            "package_id": body.package_id,
            "request_id": body.request_id or "",
            "customer_email": body.customer_email or "",
        },
    )
    session = await stripe_checkout.create_checkout_session(checkout_req)

    from server import db
    await db.payment_transactions.insert_one({
        "session_id": session.session_id,
        "mode": "one_off",
        "package_id": body.package_id,
        "amount": pkg["amount"],
        "currency": pkg["currency"],
        "customer_email": body.customer_email or "",
        "request_id": body.request_id or "",
        "status": "initiated",
        "payment_status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"url": session.url, "session_id": session.session_id}


@router.get("/status/{session_id}")
async def get_status(session_id: str, request: Request):
    stripe_checkout = _get_emergent_client(request)
    result = await stripe_checkout.get_checkout_status(session_id)

    from server import db
    tx = await db.payment_transactions.find_one({"session_id": session_id})
    already_processed = tx and tx.get("payment_status") == "paid"

    if not already_processed:
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "status": result.status,
                "payment_status": result.payment_status,
                "amount_total": result.amount_total,
                "currency": result.currency,
                "metadata": result.metadata,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        if result.payment_status == "paid":
            req_id = (result.metadata or {}).get("request_id")
            if req_id:
                await db.license_requests.update_one(
                    {"id": req_id},
                    {"$set": {
                        "payment_status": "paid",
                        "paid_at": datetime.now(timezone.utc).isoformat(),
                        "paid_amount": result.amount_total / 100,
                        "paid_via": "stripe",
                    }},
                )

    return {
        "status": result.status,
        "payment_status": result.payment_status,
        "amount_total": result.amount_total,
        "currency": result.currency,
    }


@router.get("/packages")
async def get_packages():
    return {"packages": PACKAGES}


# ===========================================================================
# STRIPE SUBSCRIPTIONS (recurrent — auto-renewal)
# ===========================================================================
class CreateSubscriptionBody(BaseModel):
    package_id: str            # STD_MES / STD_ANY / PREMIUM_MES / PREMIUM_ANY
    origin_url: str
    request_id: Optional[str] = None
    customer_email: str        # obligatori per crear el Stripe Customer
    install_id: Optional[str] = None
    company_name: Optional[str] = None


@router.get("/subscription/enabled")
async def subscription_enabled():
    """
    Retorna quins paquets tenen Price ID configurat.
    El frontend usa això per decidir si mostra el botó "Pagar amb targeta".
    """
    api_key = os.environ.get("STRIPE_API_KEY", "").strip()
    configured = _subscriptions_configured()
    any_configured = any(configured.values())
    return {
        "enabled": bool(api_key) and any_configured,
        "stripe_api_key_present": bool(api_key),
        "packages": configured,
    }


@router.post("/create-subscription")
async def create_subscription(body: CreateSubscriptionBody, request: Request):
    """
    Crea una Stripe Checkout Session en mode=subscription.
    Requereix STRIPE_PRICE_* configurat a .env.
    """
    if body.package_id not in PACKAGES:
        raise HTTPException(status_code=400, detail=f"Paquet desconegut: {body.package_id}")
    pkg = PACKAGES[body.package_id]

    price_id = os.environ.get(pkg["env_price"], "").strip()
    if not price_id:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Subscripcions per '{body.package_id}' encara no configurades. "
                f"Cal definir {pkg['env_price']} al servidor. "
                "Veure /guia-stripe-setup.html per la configuració completa."
            ),
        )

    stripe_sdk.api_key = _stripe_api_key()
    origin = body.origin_url.rstrip("/")
    success_url = f"{origin}/request-license?subscription_session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/request-license?cancelled=1"

    try:
        session = stripe_sdk.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=body.customer_email,
            success_url=success_url,
            cancel_url=cancel_url,
            allow_promotion_codes=True,
            billing_address_collection="required",
            metadata={
                "mode": "subscription",
                "package_id": body.package_id,
                "request_id": body.request_id or "",
                "install_id": body.install_id or "",
                "company_name": body.company_name or "",
                "customer_email": body.customer_email,
            },
            subscription_data={
                "metadata": {
                    "package_id": body.package_id,
                    "request_id": body.request_id or "",
                    "install_id": body.install_id or "",
                    "company_name": body.company_name or "",
                    "customer_email": body.customer_email,
                },
            },
        )
    except stripe_sdk.error.StripeError as e:
        logger.error("Stripe subscription creation failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(e)}")

    from server import db
    await db.payment_transactions.insert_one({
        "session_id": session.id,
        "mode": "subscription",
        "package_id": body.package_id,
        "amount": pkg["amount"],
        "currency": pkg["currency"],
        "customer_email": body.customer_email,
        "request_id": body.request_id or "",
        "install_id": body.install_id or "",
        "company_name": body.company_name or "",
        "status": "initiated",
        "payment_status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"url": session.url, "session_id": session.id}


@router.get("/subscription/status/{session_id}")
async def subscription_status(session_id: str):
    """
    Polling: consulta l'estat d'una checkout session de subscripció.
    """
    stripe_sdk.api_key = _stripe_api_key()
    try:
        sess = stripe_sdk.checkout.Session.retrieve(
            session_id,
            expand=["subscription", "customer"],
        )
    except stripe_sdk.error.StripeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    sub_id = sess.get("subscription")
    if isinstance(sub_id, dict):
        sub_id = sub_id.get("id")
    cust_id = sess.get("customer")
    if isinstance(cust_id, dict):
        cust_id = cust_id.get("id")

    return {
        "status": sess.get("status"),
        "payment_status": sess.get("payment_status"),
        "subscription_id": sub_id,
        "customer_id": cust_id,
        "customer_email": sess.get("customer_email") or sess.get("customer_details", {}).get("email"),
        "metadata": sess.get("metadata", {}),
    }


@router.get("/subscription/list")
async def list_subscriptions():
    """Admin: llista totes les subscripcions actives guardades a la DB."""
    from server import db
    docs = await db.subscriptions.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"total": len(docs), "items": docs}
