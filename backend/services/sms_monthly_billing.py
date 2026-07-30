"""Monthly SMS billing loop · MediCar Plus.

Al día 1 de cada mes a las 03:00 UTC, factura a TODOS los clientes con SMS
pendientes (independientemente de si su plan es mensual o anual). Esto evita
que los clientes anuales acumulen 12 meses de SMS antes de recibir factura.

Filosofía:
  - Los SMS SIEMPRE se facturan mensualmente, como servicio pay-per-use.
  - La suscripción (STD/PRM) sigue su ciclo (mensual o anual).
  - Cada factura SMS es one-off, cobrada inmediatamente con la tarjeta guardada.

Precio: `MEDICAR_SMS_TWILIO_COST_EUR + MEDICAR_SMS_MARGIN_EUR` (por defecto 0.10 €).
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def _seconds_until_next_run() -> float:
    """Calcula segundos hasta el día 1 del mes siguiente a las 03:00 UTC."""
    now = datetime.now(timezone.utc)
    # Primer día del mes siguiente
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1, 3, 0, 0, tzinfo=timezone.utc)
    else:
        next_month = datetime(now.year, now.month + 1, 1, 3, 0, 0, tzinfo=timezone.utc)
    return max((next_month - now).total_seconds(), 60)


async def bill_all_pending_sms_monthly(db, stripe_sdk) -> dict:
    """Recorre todos los install_ids con SMS pendientes y crea una factura Stripe
    one-off por cada uno con lo consumido en el mes anterior.

    Idempotente: marca `billed=True` inmediatamente después de crear el InvoiceItem.
    """
    from services.sms_billing import bill_pending_sms_for_subscription, get_pending_usage  # noqa: F401

    # 1) Encontrar install_ids únicos con SMS pendientes (campo real del schema: sent_count)
    pipeline = [
        {"$match": {"$or": [{"billed": False}, {"billed": {"$exists": False}}]}},
        {"$group": {"_id": "$install_id", "count": {"$sum": "$sent_count"}}},
        {"$match": {"count": {"$gt": 0}}},
    ]
    install_ids_with_pending: list[str] = []
    async for grp in db.sms_usage_medicar.aggregate(pipeline):
        iid = grp.get("_id")
        if iid:
            install_ids_with_pending.append(iid)

    if not install_ids_with_pending:
        logger.info("[sms_monthly] No pending SMS to bill this month")
        return {"ok": True, "clients_billed": 0, "total_invoices": 0}

    stats = {"clients_billed": 0, "total_sms": 0, "total_eur": 0.0, "errors": [], "invoices": []}

    for install_id in install_ids_with_pending:
        try:
            # Encuentra la suscripción activa Stripe para este install_id
            lic = await db.licenses.find_one({
                "install_id": install_id,
                "status": "active",
                "stripe_subscription_id": {"$exists": True, "$ne": None},
            })
            if not lic:
                logger.warning(f"[sms_monthly] no active subscription found for install_id={install_id}, skipping")
                stats["errors"].append({"install_id": install_id, "error": "no_active_subscription"})
                continue

            sub_id = lic.get("stripe_subscription_id")
            # Factura one-off (cobra inmediatamente)
            result = await bill_pending_sms_for_subscription(
                db, stripe_sdk, sub_id, install_id, mode="one_off"
            )
            if result.get("ok") and result.get("billed", 0) > 0:
                stats["clients_billed"] += 1
                stats["total_sms"] += result.get("billed", 0)
                stats["total_eur"] += result.get("amount_cents", 0) / 100.0
                stats["invoices"].append({
                    "install_id": install_id,
                    "sms": result.get("billed"),
                    "amount_eur": round(result.get("amount_cents", 0) / 100.0, 2),
                    "stripe_invoice_id": result.get("stripe_invoice_id"),
                })
                logger.info(f"[sms_monthly] billed install_id={install_id} sms={result.get('billed')} amount=€{result.get('amount_cents',0)/100:.2f}")
            else:
                logger.info(f"[sms_monthly] skip install_id={install_id}: {result}")
        except Exception as e:
            logger.exception(f"[sms_monthly] failed to bill install_id={install_id}: {e}")
            stats["errors"].append({"install_id": install_id, "error": str(e)[:200]})

    stats["ok"] = True
    stats["run_at"] = datetime.now(timezone.utc).isoformat()
    stats["total_eur"] = round(stats["total_eur"], 2)

    # Guarda un log en DB para auditoría
    try:
        await db.sms_monthly_billing_runs.insert_one({**stats, "_id": f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"})
    except Exception as ex:
        logger.warning(f"[sms_monthly] audit log write failed: {ex}")

    logger.info(f"[sms_monthly] SUMMARY · clients_billed={stats['clients_billed']} total_sms={stats['total_sms']} total_eur={stats['total_eur']}")
    return stats


async def sms_monthly_billing_loop(db, stripe_sdk) -> None:
    """Loop asyncio que espera hasta el día 1 del mes a las 03:00 UTC y ejecuta la facturación."""
    while True:
        try:
            wait_seconds = _seconds_until_next_run()
            logger.info(f"[sms_monthly] next run in {wait_seconds/3600:.1f} hours ({wait_seconds/86400:.1f} days)")
            await asyncio.sleep(wait_seconds)
            logger.info("[sms_monthly] 🔔 Running monthly SMS billing…")
            await bill_all_pending_sms_monthly(db, stripe_sdk)
        except asyncio.CancelledError:
            logger.info("[sms_monthly] loop cancelled")
            raise
        except Exception as ex:
            logger.exception(f"[sms_monthly] loop error, retrying in 1h: {ex}")
            await asyncio.sleep(3600)
