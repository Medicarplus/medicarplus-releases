"""
SMS Billing · Metered billing dels SMS enviats en mode 'MediCar Cloud'
─────────────────────────────────────────────────────────────────────
Estratègia:
1. Quan un client (Premium) envia SMS via mode 'medicar', es registra a
   la col·lecció `sms_usage_medicar` (increment atòmic per SMS).
2. Al webhook Stripe:
   - Event `invoice.paid` d'una subscripció → afegim els SMS del period
     anterior com a InvoiceItem a la subscripció (s'inclouran a la
     PRÒXIMA factura mensual).
   - Event `customer.subscription.deleted` → si el client cancel·la, els
     SMS pendents s'inclouen a una FACTURA ONE-OFF final que es cobra
     immediatament amb la seva targeta guardada.

Camps del document `sms_usage_medicar`:
    install_id, period (YYYY-MM), sent_count, error_count,
    client_name, medicar_sender, first_seen, last_seen, billed,
    billed_at, stripe_invoice_item_id, stripe_invoice_id

Preu per SMS: variable env `MEDICAR_SMS_PRICE_EUR` (per defecte 0.10 €).
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def _price_cents() -> int:
    """Preu per SMS en cèntims d'euro.
    Preu = cost Twilio + marge fix.
    Fórmula: MEDICAR_SMS_TWILIO_COST_EUR + MEDICAR_SMS_MARGIN_EUR
    Si canvia el preu de Twilio, actualitza MEDICAR_SMS_TWILIO_COST_EUR i el
    marge (0,03€ per defecte) s'aplica automàticament.
    Fallback a MEDICAR_SMS_PRICE_EUR (legacy) si les 2 noves no existeixen."""
    try:
        cost_eur = float(os.environ.get("MEDICAR_SMS_TWILIO_COST_EUR", "").strip() or "0")
        margin_eur = float(os.environ.get("MEDICAR_SMS_MARGIN_EUR", "").strip() or "0")
        if cost_eur > 0 or margin_eur > 0:
            return int(round((cost_eur + margin_eur) * 100))
        # Fallback legacy
        return int(round(float(os.environ.get("MEDICAR_SMS_PRICE_EUR", "0.10")) * 100))
    except Exception:
        return 10


async def get_pending_usage(db, install_id: str) -> dict:
    """Retorna la suma d'SMS enviats i encara no facturats per aquest install_id."""
    query = {"install_id": install_id, "$or": [{"billed": False}, {"billed": {"$exists": False}}]}
    cursor = db.sms_usage_medicar.find(query)
    total_sent = 0
    docs = []
    async for d in cursor:
        docs.append(d)
        total_sent += int(d.get("sent_count", 0) or 0)
    return {"total_sms": total_sent, "docs": docs}


async def bill_pending_sms_for_subscription(
    db,
    stripe_sdk,
    subscription_id: str,
    install_id: str,
    mode: str = "attach_next",  # 'attach_next' (metered) o 'one_off' (cancel·lació)
) -> dict:
    """Crea a Stripe una càrrega pels SMS pendents del client.

    - mode='attach_next': crea un InvoiceItem lligat a la subscripció; Stripe
      l'inclourà automàticament a la PRÒXIMA factura mensual.
    - mode='one_off': crea InvoiceItem + Invoice + finalitza + paga immediatament
      (per cancel·lacions on ja no hi haurà més factures automàtiques).

    Retorna dict amb resultat i marca la usage com billed=True.
    """
    pending = await get_pending_usage(db, install_id)
    total_sms = pending["total_sms"]
    if total_sms <= 0:
        return {"ok": True, "billed": 0, "reason": "no_pending_sms"}

    price_cents = _price_cents()
    amount_cents = total_sms * price_cents
    if amount_cents <= 0:
        return {"ok": True, "billed": 0, "reason": "zero_amount"}

    # Cal recuperar customer_id per crear InvoiceItem
    try:
        sub = stripe_sdk.Subscription.retrieve(subscription_id)
        customer_id = sub.get("customer") if isinstance(sub, dict) else sub.customer
    except Exception as e:
        logger.warning(f"[sms_billing] cannot retrieve subscription {subscription_id}: {e}")
        return {"ok": False, "error": f"stripe_retrieve_failed: {str(e)[:200]}"}

    if not customer_id:
        return {"ok": False, "error": "no_customer_id"}

    try:
        # 1) Crear InvoiceItem
        item_kwargs = dict(
            customer=customer_id,
            amount=amount_cents,
            currency="eur",
            description=f"SMS Premium · {total_sms} enviados × {price_cents/100:.2f} €",
            metadata={
                "install_id": install_id,
                "sms_count": str(total_sms),
                "price_per_sms_eur": f"{price_cents/100:.2f}",
                "kind": "sms_metered",
            },
        )
        if mode == "attach_next":
            # Adjunta a la subscripció → la propera factura la inclourà
            item_kwargs["subscription"] = subscription_id

        item = stripe_sdk.InvoiceItem.create(**item_kwargs)
        item_id = item.get("id") if isinstance(item, dict) else item.id

        stripe_invoice_id = None
        if mode == "one_off":
            # Crear factura + finalitzar + intent de cobrament immediat.
            # `pending_invoice_items_behavior=include` fuerza a Stripe a incluir el
            # InvoiceItem que acabamos de crear (si no, Stripe podría dejarlo para la
            # próxima factura de suscripción, resultando en amount_due=0).
            inv = stripe_sdk.Invoice.create(
                customer=customer_id,
                auto_advance=True,
                collection_method="charge_automatically",
                pending_invoice_items_behavior="include",
                description=f"Facturación · Consumo SMS ({total_sms} SMS)",
                metadata={"install_id": install_id, "kind": "sms_metered"},
            )
            inv_id = inv.get("id") if isinstance(inv, dict) else inv.id
            # Finalitzar (això la fa cobrable)
            stripe_sdk.Invoice.finalize_invoice(inv_id)
            # Al finalizar con collection_method=charge_automatically, Stripe intenta cobrar.
            # Si ya se ha cobrado en el finalize, el pay() posterior lanza "Invoice is already paid" (esperado).
            try:
                stripe_sdk.Invoice.pay(inv_id)
            except Exception as pay_err:
                if "already paid" in str(pay_err).lower():
                    logger.info(f"[sms_billing] one_off invoice {inv_id} already paid on finalize (OK)")
                else:
                    logger.warning(f"[sms_billing] one_off invoice pay failed: {pay_err}")
            stripe_invoice_id = inv_id

        # 2) Marca totes les usage docs com billed
        now_iso = datetime.now(timezone.utc).isoformat()
        for d in pending["docs"]:
            await db.sms_usage_medicar.update_one(
                {"_id": d["_id"]},
                {"$set": {
                    "billed": True,
                    "billed_at": now_iso,
                    "stripe_invoice_item_id": item_id,
                    "stripe_invoice_id": stripe_invoice_id,
                    "billing_mode": mode,
                }},
            )

        return {
            "ok": True,
            "billed": total_sms,
            "amount_cents": amount_cents,
            "amount_eur": amount_cents / 100,
            "stripe_invoice_item_id": item_id,
            "stripe_invoice_id": stripe_invoice_id,
            "mode": mode,
        }
    except Exception as e:
        logger.exception(f"[sms_billing] failed to bill install_id={install_id}: {e}")
        return {"ok": False, "error": str(e)[:300]}
