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
    referred_by: Optional[str] = None   # Codi de referit (MC-XXXX-XXXX) — opcional


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
    # Redirigim SEMPRE al servidor d'Emergent (no a GitHub Pages) perquè la
    # pàgina de gràcies estigui hostejada i pugui llegir el session_id.
    PROD_HOST = os.environ.get("APP_PROD_URL", "https://project-helper-47.emergent.host").rstrip("/")
    success_url = f"{PROD_HOST}/subscription-success.html?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{PROD_HOST}/subscription-success.html?cancelled=1"

    # 🎁 Programa de referits · Si el nou client ve d'un codi vàlid,
    # apliquem el cupó REFERRED_1M (100% off del 1r mes) al Checkout.
    discounts_arg = None
    referred_by_valid = None
    if body.referred_by:
        try:
            from services.referrals import (
                is_valid_referral_format,
                find_active_referrer,
                get_or_create_referred_coupon,
            )
            code_upper = str(body.referred_by).upper().strip()
            if is_valid_referral_format(code_upper):
                # Import lazy per no crear dependència circular
                from server import db as _db  # type: ignore
                ref_doc = await find_active_referrer(_db.licenses, code_upper)
                if ref_doc:
                    referred_by_valid = code_upper
                    try:
                        coupon = await get_or_create_referred_coupon()
                        discounts_arg = [{"coupon": coupon.id}]
                        logger.info(
                            "Applying referred-1m coupon %s for referred_by=%s",
                            coupon.id, code_upper,
                        )
                    except Exception as ex:  # noqa: BLE001
                        logger.warning("Could not apply referred coupon: %s", ex)
        except Exception as ex:  # noqa: BLE001
            logger.warning("Referral pre-flight check failed: %s", ex)

    try:
        checkout_kwargs = dict(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=body.customer_email,
            success_url=success_url,
            cancel_url=cancel_url,
            billing_address_collection="required",
            # 🏢 Habilita recol·lecció de NIF/CIF per facturació B2B
            # Els clients poden introduir el NIF/CIF de la seva empresa durant
            # el checkout. Stripe l'inclou automàticament a les factures generades
            # (subscripció + one-off SMS pendents en cancel·lació). Compatible amb
            # Verifactu (registre fiscal ES 2026).
            tax_id_collection={"enabled": True},
            # Força castellà a tota la UI de Stripe Checkout (evita mescla es/ca)
            locale="es",
            metadata={
                "mode": "subscription",
                "package_id": body.package_id,
                "request_id": body.request_id or "",
                "install_id": body.install_id or "",
                "company_name": body.company_name or "",
                "customer_email": body.customer_email,
                "referred_by": referred_by_valid or "",
            },
            subscription_data={
                "metadata": {
                    "package_id": body.package_id,
                    "request_id": body.request_id or "",
                    "install_id": body.install_id or "",
                    "company_name": body.company_name or "",
                    "customer_email": body.customer_email,
                    "referred_by": referred_by_valid or "",
                },
            },
        )
        # Stripe força exclusió mútua entre `discounts` i `allow_promotion_codes`.
        # Si tenim descompte de referit, l'apliquem directament (sense promo codes).
        # Si no, permetem que l'usuari introdueixi un codi promocional manualment.
        if discounts_arg:
            checkout_kwargs["discounts"] = discounts_arg
        else:
            checkout_kwargs["allow_promotion_codes"] = True
        # Nota: consent_collection.terms_of_service afegeix un checkbox obligatori
        # dins el propi Checkout Stripe amb l'enllaç als T&C. Requereix tenir
        # Terms of Service URL configurat al Stripe Dashboard (Settings → Public details → Legal).
        # L'afegim si l'usuari té configurada la URL; si no, Stripe rebutja i tornem a
        # crear la sessió sense aquesta opció.
        try:
            checkout_kwargs["consent_collection"] = {"terms_of_service": "required"}
            session = stripe_sdk.checkout.Session.create(**checkout_kwargs)
        except stripe_sdk.error.InvalidRequestError as _err:
            err_msg = str(_err).lower()
            # Stripe retorna missatges variats: "terms of service", "terms_of_service",
            # "consent_collection"... capturem qualsevol combinació.
            if "terms of service" in err_msg or "terms_of_service" in err_msg or "consent" in err_msg:
                logger.warning(
                    "Stripe consent_collection ToS URL no configurada al Dashboard "
                    "(Settings → Public details → Terms of service). Fallback sense consent."
                )
                checkout_kwargs.pop("consent_collection", None)
                session = stripe_sdk.checkout.Session.create(**checkout_kwargs)
            else:
                raise
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
    Retorna també la llicència generada pel webhook (si ja hi és).
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

    customer_email = sess.get("customer_email") or sess.get("customer_details", {}).get("email")

    # Cerca la llicència generada pel webhook (pot trigar uns segons)
    from server import db
    license_key = None
    install_id = None
    plan = None
    expires_at = None
    if sub_id:
        lic = await db.licenses.find_one(
            {"stripe_subscription_id": sub_id, "status": "active"},
            sort=[("created_at", -1)],
        )
        if lic:
            license_key = lic.get("license_key")
            install_id = lic.get("install_id")
            plan = lic.get("plan")
            expires_at = lic.get("expires_at")

    return {
        "status": sess.get("status"),
        "payment_status": sess.get("payment_status"),
        "subscription_id": sub_id,
        "customer_id": cust_id,
        "customer_email": customer_email,
        "metadata": sess.get("metadata", {}),
        # Camps de llicència (poden ser null si el webhook encara no ha corregut)
        "license_key": license_key,
        "install_id": install_id,
        "plan": plan,
        "expires_at": expires_at,
        "license_ready": bool(license_key),
        "download_url": "https://github.com/Medicarplus/medicarplus-releases/releases/latest",
    }


@router.get("/subscription/list")
async def list_subscriptions():
    """Admin: llista totes les subscripcions actives guardades a la DB."""
    from server import db
    docs = await db.subscriptions.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"total": len(docs), "items": docs}


# ===========================================================================
# BILLING PORTAL · self-service (cancel, update card, view invoices)
# ===========================================================================
class BillingPortalBody(BaseModel):
    install_id: Optional[str] = None
    customer_email: Optional[str] = None
    return_url: str


@router.post("/billing-portal")
async def billing_portal(body: BillingPortalBody):
    """
    Genera una URL del Stripe Customer Portal per què el client
    pugui gestionar la seva subscripció (cancel·lar, canviar targeta,
    veure factures) sense passar per suport.

    Cerca el `stripe_customer_id` a la col·lecció `subscriptions` per:
    1. install_id (preferit — l'usa l'app Electron)
    2. customer_email (fallback — l'usa la web pública)
    """
    if not body.install_id and not body.customer_email:
        raise HTTPException(status_code=400, detail="Cal install_id o customer_email")

    from server import db
    query = {}
    if body.install_id:
        query["install_id"] = body.install_id
    elif body.customer_email:
        query["customer_email"] = body.customer_email.lower().strip()

    sub_doc = await db.subscriptions.find_one(query, sort=[("updated_at", -1)])
    if not sub_doc or not sub_doc.get("stripe_customer_id"):
        raise HTTPException(
            status_code=404,
            detail=(
                "No hem trobat cap subscripció activa. "
                "Si acabes de pagar, espera 1 minut i torna-ho a provar. "
                "Si el problema persisteix, escriu a info@medicarplus.es."
            ),
        )

    stripe_sdk.api_key = _stripe_api_key()
    try:
        portal = stripe_sdk.billing_portal.Session.create(
            customer=sub_doc["stripe_customer_id"],
            return_url=body.return_url,
        )
    except stripe_sdk.error.StripeError as e:
        logger.error("Billing portal creation failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(e)}")

    return {"url": portal.url}


@router.get("/subscription/by-install/{install_id}")
async def subscription_by_install(install_id: str):
    """Retorna la subscripció d'un install_id (o null). Usat pel botó
    'Gestionar subscripció' del client per saber si l'ha de mostrar."""
    from server import db
    sub = await db.subscriptions.find_one({"install_id": install_id}, {"_id": 0})
    return {"subscription": sub}
