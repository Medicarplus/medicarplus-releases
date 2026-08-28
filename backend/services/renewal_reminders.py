"""Recordatoris automàtics de renovació de llicència.

Cada 24h es revisa la col·lecció `licenses`: si una llicència activa caduca
en <= 7 dies, no té subscripció Stripe (que renova sola) i encara no hem
avisat per aquesta caducitat, s'envia un email en castellà al client amb
l'enllaç de renovació. Idempotent via `renewal_reminder_for`.
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
from datetime import datetime, timedelta, timezone

from services.mailer import _send_smtp, _smtp_configured

logger = logging.getLogger(__name__)

REMINDER_WINDOW_DAYS = 7
SWEEP_INTERVAL_SECONDS = 24 * 3600


def _render_reminder_html(*, client_name: str, plan: str, expires_at: datetime, days_left: int) -> str:
    expiry_txt = expires_at.strftime("%d/%m/%Y")
    days_txt = "mañana" if days_left <= 1 else f"en {days_left} días"
    plan_up = (plan or "").upper()
    plan_nice = {"TRIAL": "Prueba gratuita", "STD": "Standard", "STANDARD": "Standard",
                 "PRM": "Premium", "PREMIUM": "Premium"}.get(plan_up, plan_up or "MediCar Plus")
    return f"""
<!doctype html><html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px">
<div style="max-width:560px;margin:auto;background:#1e293b;border-radius:14px;padding:32px;border:2px solid #f5b301">
  <div style="text-align:center;font-size:52px;line-height:1">⏰</div>
  <h1 style="text-align:center;color:#f5b301;font-size:22px;margin:12px 0 8px;font-weight:800">Tu licencia caduca {days_txt}</h1>
  <p style="text-align:center;color:#94a3b8;font-size:12px;margin:0 0 24px;letter-spacing:.5px;text-transform:uppercase">MediCar Plus · Software profesional</p>

  <p style="color:#cbd5e1;font-size:15px;line-height:1.65;margin:0 0 10px">Hola <b>{client_name}</b>,</p>
  <p style="color:#cbd5e1;font-size:14.5px;line-height:1.65;margin:0 0 18px">
    Tu plan <b>{plan_nice}</b> caduca el <b style="color:#f5b301">{expiry_txt}</b>. Para no perder el acceso a MediCar Plus ni a tus copias de seguridad, renueva antes de esa fecha.
  </p>

  <div style="text-align:center;margin:26px 0">
    <a href="https://medicarplus.es/#pricing" style="display:inline-block;padding:16px 32px;background:#22c55e;color:#0f172a;text-decoration:none;font-weight:800;font-size:15px;border-radius:10px;letter-spacing:.3px">💳 Renovar mi licencia</a>
  </div>

  <div style="background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.35);border-radius:10px;padding:14px 16px;margin:20px 0 0;color:#bbf7d0;font-size:13px;line-height:1.6">
    💡 Si eliges la <b>suscripción</b> (mensual o anual), a partir de ahora se renueva sola cada periodo y no volverás a recibir avisos como este.
  </div>

  <p style="color:#64748b;font-size:11px;margin-top:24px;padding-top:16px;border-top:1px solid #334155;line-height:1.6;text-align:center">
    ¿Ya has renovado? Ignora este mensaje.<br>
    ¿Dudas? Escribe a <a href="mailto:suport@medicarplus.es" style="color:#f5b301">suport@medicarplus.es</a><br>
    <span style="color:#475569">MediCar Plus · Marc Brugulat Lopez · <a href="https://medicarplus.es" style="color:#475569">medicarplus.es</a></span>
  </p>
</div>
</body></html>
""".strip()


async def _send_reminder(*, to_email: str, client_name: str, plan: str,
                         expires_at: datetime, days_left: int) -> tuple[bool, str]:
    if not _smtp_configured():
        return False, "smtp_not_configured"
    subject = f"MediCar Plus · Tu licencia caduca el {expires_at.strftime('%d/%m/%Y')} — renueva ahora"
    html = _render_reminder_html(client_name=client_name, plan=plan,
                                 expires_at=expires_at, days_left=days_left)
    return await asyncio.to_thread(_send_smtp, to_email, subject, html)


async def run_renewal_reminder_sweep(db) -> dict:
    """Revisa llicències actives a punt de caducar i envia recordatoris."""
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=REMINDER_WINDOW_DAYS)
    checked = sent = skipped = 0
    errors: list[str] = []

    cursor = db.licenses.find({
        "status": "active",
        "expires_at": {"$ne": None},
        "client_email": {"$nin": [None, ""]},
    })
    async for doc in cursor:
        checked += 1
        try:
            exp = datetime.fromisoformat(doc["expires_at"])
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        if not (now < exp <= horizon):
            continue
        if doc.get("stripe_subscription_id"):
            skipped += 1
            continue
        if doc.get("renewal_reminder_for") == doc["expires_at"]:
            skipped += 1
            continue

        days_left = max(1, math.ceil((exp - now).total_seconds() / 86400))
        ok, info = await _send_reminder(
            to_email=doc["client_email"],
            client_name=doc.get("client_name") or "cliente",
            plan=doc.get("plan") or "STD",
            expires_at=exp,
            days_left=days_left,
        )
        if ok:
            sent += 1
            await db.licenses.update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "renewal_reminder_for": doc["expires_at"],
                    "renewal_reminder_sent_at": now.isoformat(),
                }},
            )
            logger.info("Renewal reminder sent to %s (expires %s)", doc["client_email"], doc["expires_at"])
        else:
            errors.append(f"{doc.get('client_email')}: {info}")
            logger.warning("Renewal reminder failed for %s: %s", doc.get("client_email"), info)

    return {"checked": checked, "sent": sent, "skipped": skipped, "errors": errors}


async def renewal_reminder_loop(db):
    """Bucle en background: sweep a l'arrencada (després d'1 min) i cada 24h."""
    await asyncio.sleep(60)
    while True:
        try:
            result = await run_renewal_reminder_sweep(db)
            logger.info("Renewal reminder sweep: %s", result)
        except Exception:
            logger.exception("Renewal reminder sweep failed")
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
