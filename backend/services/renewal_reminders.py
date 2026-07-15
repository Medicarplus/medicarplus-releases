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
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;padding:32px 0;font-family:Georgia,serif">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="background:#1e293b;border:2px solid #f5b301;border-radius:14px;padding:32px;color:#e2e8f0">
      <tr><td>
        <h1 style="margin:0 0 6px 0;color:#f5b301;font-size:24px;letter-spacing:1px">MediCar Plus · Tu licencia caduca {days_txt}</h1>
        <p style="margin:0 0 20px 0;color:#94a3b8;font-size:13px">Software comercial · Marc Brugulat Lopez</p>

        <p style="color:#e2e8f0;font-size:15px;line-height:1.55">Hola <b>{client_name}</b>,<br>
        Tu licencia de MediCar Plus (plan <b>{plan}</b>) caduca el <b style="color:#f5b301">{expiry_txt}</b>.<br>
        Para no perder el acceso a la aplicación ni a tus copias de seguridad, renueva antes de esa fecha.</p>

        <table width="100%" cellpadding="12" cellspacing="0" style="margin-top:20px">
          <tr>
            <td style="background:#0f172a;border:1px solid #22c55e;border-radius:8px;padding:16px;text-align:center">
              <a href="https://medicarplus.es/#pricing" style="color:#22c55e;text-decoration:none;font-size:15px;font-weight:700">
                💳 Renovar ahora — pago seguro con tarjeta
              </a>
            </td>
          </tr>
        </table>

        <p style="color:#cbd5e1;font-size:13px;margin-top:18px;line-height:1.6">
          💡 <b style="color:#f5b301">Consejo:</b> si eliges la <b>suscripción</b> (mensual o anual), la renovación
          será automática y no volverás a recibir este aviso: tu licencia se renueva sola cada periodo.
        </p>

        <p style="color:#64748b;font-size:12px;margin-top:26px;padding-top:18px;border-top:1px solid #334155;line-height:1.5">
          ¿Dudas? Escríbenos a info@medicarplus.es · Marc Brugulat Lopez<br>
          Si ya has renovado, ignora este mensaje.
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
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
