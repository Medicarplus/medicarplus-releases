"""Stripe payments sync + summary · God-mode owner traceability.

Endpoints (all admin-only, X-Admin-Token):
  POST /api/admin/payments/sync             — sincroniza invoices de Stripe para TODAS las licencias con stripe_subscription_id
  GET  /api/admin/payments/summary          — resumen global (total facturado, nº pagos ok, nº fallidos, MRR aproximado)
  GET  /api/admin/payments/by-license/{jti} — histórico de invoices de una licencia concreta

Estrategia de sync (idempotente):
  Para cada licencia con `stripe_subscription_id`:
    1. Llamamos a stripe.Invoice.list(subscription=..., limit=100)
    2. Para cada invoice:
       - Insertamos/actualizamos en `payments` collection
       - Sumamos al `total_paid_cents` de la licencia si status=paid
       - Guardamos `last_payment_status` + `last_payment_at`
    3. Marcamos la licencia con `payment_health` (green/yellow/red):
       - green  = último pago OK
       - yellow = un pago requiere acción (past_due, etc.)
       - red    = último pago falló definitivamente

Se puede ejecutar bajo demanda desde el panel (botón "↻ Sincronizar Stripe").
Idealmente se automatiza con webhooks en el futuro; de momento este sync manual
resuelve el 100% del caso "ver quién no me ha pagado".
"""
import logging
import os
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Header

logger = logging.getLogger(__name__)


def _admin_ok(x_admin_token: Optional[str]) -> None:
    expected = os.environ.get("LICENSE_ADMIN_TOKEN", "")
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_payments_router(db):
    router = APIRouter(prefix="/admin/payments", tags=["admin-payments"])

    @router.post("/sync")
    async def sync_stripe_payments(x_admin_token: Optional[str] = Header(None)):
        """Sincroniza invoices de Stripe para todas las licencias con subscription activa."""
        _admin_ok(x_admin_token)
        try:
            import stripe as stripe_sdk
        except ImportError:
            raise HTTPException(status_code=503, detail="Stripe SDK no instalado")
        api_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY") or ""
        if not api_key:
            raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY no configurado")
        stripe_sdk.api_key = api_key

        stats = {
            "licenses_processed": 0,
            "invoices_synced": 0,
            "total_paid_eur": 0.0,
            "errors": [],
            "green": 0,
            "yellow": 0,
            "red": 0,
            "no_data": 0,
        }

        cursor = db.licenses.find({
            "stripe_subscription_id": {"$exists": True, "$nin": [None, ""]},
        })
        async for lic in cursor:
            stats["licenses_processed"] += 1
            sub_id = lic.get("stripe_subscription_id")
            jti = lic.get("id")
            try:
                invoices_resp = stripe_sdk.Invoice.list(subscription=sub_id, limit=100)
                lic_total_cents = 0
                paid_count = 0
                failed_count = 0
                last_status = None
                last_paid_at = None
                last_amount = None
                for inv in invoices_resp.data:
                    inv_id = inv.get("id")
                    amount = int(inv.get("amount_paid") or 0)
                    currency = inv.get("currency", "eur")
                    status = inv.get("status")  # paid, open, void, uncollectible
                    created = inv.get("created")
                    paid_at = inv.get("status_transitions", {}).get("paid_at")
                    period_end = inv.get("period_end")
                    hosted_url = inv.get("hosted_invoice_url")
                    pdf_url = inv.get("invoice_pdf")
                    # Upsert en `payments`
                    await db.payments.update_one(
                        {"_id": inv_id},
                        {"$set": {
                            "license_jti": jti,
                            "install_id": lic.get("install_id"),
                            "customer_email": lic.get("client_email"),
                            "stripe_subscription_id": sub_id,
                            "stripe_customer_id": lic.get("stripe_customer_id"),
                            "amount_cents": amount,
                            "currency": currency,
                            "status": status,
                            "created_at": datetime.fromtimestamp(created, tz=timezone.utc).isoformat() if created else None,
                            "paid_at": datetime.fromtimestamp(paid_at, tz=timezone.utc).isoformat() if paid_at else None,
                            "period_end": datetime.fromtimestamp(period_end, tz=timezone.utc).isoformat() if period_end else None,
                            "hosted_url": hosted_url,
                            "pdf_url": pdf_url,
                            "synced_at": _now_iso(),
                        }},
                        upsert=True,
                    )
                    stats["invoices_synced"] += 1
                    if status == "paid":
                        lic_total_cents += amount
                        paid_count += 1
                    elif status in ("open", "uncollectible"):
                        failed_count += 1
                    if last_status is None:
                        last_status = status
                        last_paid_at = paid_at
                        last_amount = amount
                # Salud del pago
                if failed_count > 0 and (last_status != "paid"):
                    health = "red"
                elif last_status == "open":
                    health = "yellow"
                elif last_status == "paid":
                    health = "green"
                else:
                    health = "no_data"
                stats[health] += 1
                stats["total_paid_eur"] += lic_total_cents / 100.0

                await db.licenses.update_one(
                    {"id": jti},
                    {"$set": {
                        "total_paid_cents": lic_total_cents,
                        "paid_invoices_count": paid_count,
                        "failed_invoices_count": failed_count,
                        "last_payment_status": last_status,
                        "last_payment_at": datetime.fromtimestamp(last_paid_at, tz=timezone.utc).isoformat() if last_paid_at else None,
                        "last_payment_amount_cents": last_amount,
                        "payment_health": health,
                        "payments_synced_at": _now_iso(),
                    }},
                )
            except stripe_sdk.error.StripeError as ex:
                stats["errors"].append(f"{sub_id}: {ex.user_message or str(ex)}")
                logger.warning("stripe sync failed for %s: %s", sub_id, ex)
            except Exception as ex:
                stats["errors"].append(f"{sub_id}: {ex}")

        return {"ok": True, **stats}

    @router.get("/summary")
    async def payments_summary(x_admin_token: Optional[str] = Header(None)):
        """Resumen global de pagos (para el panel)."""
        _admin_ok(x_admin_token)
        # Total facturado
        pipeline = [
            {"$match": {"status": "paid"}},
            {"$group": {"_id": None, "total_cents": {"$sum": "$amount_cents"}, "count": {"$sum": 1}}},
        ]
        total = 0
        count_paid = 0
        async for d in db.payments.aggregate(pipeline):
            total = d.get("total_cents", 0)
            count_paid = d.get("count", 0)

        count_failed = await db.payments.count_documents({"status": {"$in": ["open", "uncollectible"]}})

        # Salud por licencia
        health_stats = {}
        for h in ("green", "yellow", "red", "no_data"):
            health_stats[h] = await db.licenses.count_documents({"payment_health": h})

        # Últimos 10 pagos
        latest = []
        async for p in db.payments.find({}, {"_id": 1, "license_jti": 1, "customer_email": 1,
                                              "amount_cents": 1, "currency": 1, "status": 1,
                                              "paid_at": 1, "created_at": 1, "hosted_url": 1}).sort("created_at", -1).limit(20):
            latest.append({
                "invoice_id": p.get("_id"),
                "license_jti": p.get("license_jti"),
                "customer_email": p.get("customer_email"),
                "amount_cents": p.get("amount_cents"),
                "currency": p.get("currency"),
                "status": p.get("status"),
                "paid_at": p.get("paid_at"),
                "created_at": p.get("created_at"),
                "hosted_url": p.get("hosted_url"),
            })

        return {
            "total_paid_cents": total,
            "total_paid_eur": round(total / 100.0, 2),
            "invoices_paid": count_paid,
            "invoices_failed_or_open": count_failed,
            "licenses_by_health": health_stats,
            "latest_invoices": latest,
        }

    @router.get("/by-license/{jti}")
    async def payments_by_license(jti: str, x_admin_token: Optional[str] = Header(None)):
        """Histórico de pagos de una licencia concreta."""
        _admin_ok(x_admin_token)
        rows = []
        async for p in db.payments.find({"license_jti": jti}).sort("created_at", -1):
            rows.append({
                "invoice_id": p.get("_id"),
                "amount_cents": p.get("amount_cents"),
                "currency": p.get("currency"),
                "status": p.get("status"),
                "created_at": p.get("created_at"),
                "paid_at": p.get("paid_at"),
                "period_end": p.get("period_end"),
                "hosted_url": p.get("hosted_url"),
                "pdf_url": p.get("pdf_url"),
            })
        return {"invoices": rows, "total": len(rows)}

    return router
