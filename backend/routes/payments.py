"""
Payments router · Stripe Checkout via emergentintegrations
Fixed packages defined on backend only. Frontend passes origin URL and package ID.
"""
import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout,
    CheckoutSessionRequest,
)

router = APIRouter(prefix="/payments", tags=["payments"])

# ---------------------------------------------------------------------------
# FIXED PACKAGES · defined on backend only (security: never trust frontend prices)
# ---------------------------------------------------------------------------
PACKAGES = {
    "STD_MES":     {"amount": 29.90,  "currency": "eur", "label": "STD Mensual",     "period": "month"},
    "STD_ANY":     {"amount": 299.90, "currency": "eur", "label": "STD Anual",       "period": "year"},
    "PREMIUM_MES": {"amount": 39.90,  "currency": "eur", "label": "PREMIUM Mensual", "period": "month"},
    "PREMIUM_ANY": {"amount": 399.90, "currency": "eur", "label": "PREMIUM Anual",   "period": "year"},
}


class CreateCheckoutBody(BaseModel):
    package_id: str
    origin_url: str
    request_id: Optional[str] = None
    customer_email: Optional[str] = None


def _get_client(request: Request) -> StripeCheckout:
    api_key = os.environ.get("STRIPE_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Stripe no està configurat al servidor.")
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    return StripeCheckout(api_key=api_key, webhook_url=webhook_url)


@router.post("/create-checkout")
async def create_checkout(body: CreateCheckoutBody, request: Request):
    if body.package_id not in PACKAGES:
        raise HTTPException(status_code=400, detail=f"Paquet desconegut: {body.package_id}")
    pkg = PACKAGES[body.package_id]

    origin = body.origin_url.rstrip("/")
    success_url = f"{origin}/request-license?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/request-license?cancelled=1"

    stripe_checkout = _get_client(request)
    checkout_req = CheckoutSessionRequest(
        amount=pkg["amount"],
        currency=pkg["currency"],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "package_id": body.package_id,
            "request_id": body.request_id or "",
            "customer_email": body.customer_email or "",
        },
    )
    session = await stripe_checkout.create_checkout_session(checkout_req)

    # Registre a payment_transactions (obligatori segons playbook)
    from server import db
    await db.payment_transactions.insert_one({
        "session_id": session.session_id,
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
    stripe_checkout = _get_client(request)
    result = await stripe_checkout.get_checkout_status(session_id)

    from server import db
    tx = await db.payment_transactions.find_one({"session_id": session_id})
    already_processed = tx and tx.get("payment_status") == "paid"

    # Actualitza el registre (idempotent)
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
        # Si acaba de pagar, marca la sol·licitud com "paid" (només primera vegada)
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
