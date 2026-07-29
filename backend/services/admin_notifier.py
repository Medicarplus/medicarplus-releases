"""Admin email notifications for Stripe payment events.

Sends transactional alerts to `ADMIN_NOTIFY_EMAIL` when a customer's payment
turns red (`invoice.payment_failed`) or recovers back to green (`invoice.paid`
after a previous failure). Uses the existing SMTP configuration (IONOS) via
`services.mailer._send_smtp`, so no new provider is required.

Idempotency is enforced at the caller by checking/setting a `notification_sent`
flag on the `payments` document before invoking these helpers.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from services.mailer import _send_smtp, _smtp_configured

logger = logging.getLogger(__name__)


def _admin_email() -> str:
    return (os.environ.get("ADMIN_NOTIFY_EMAIL") or "info@medicarplus.es").strip()


def _admin_panel_url() -> str:
    return (os.environ.get("ADMIN_PANEL_URL") or "https://medicarplus.es/admin.html").strip()


def _fmt_eur(cents: int) -> str:
    try:
        return f"{(int(cents) / 100):.2f}".replace(".", ",") + " €"
    except Exception:
        return f"{cents} cents"


def _fmt_dt(iso: Optional[str]) -> str:
    if not iso:
        return "—"
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return d.strftime("%d/%m/%Y %H:%M UTC")
    except Exception:
        return iso


def _base_wrapper(title: str, color: str, body_html: str) -> str:
    """Wraps a section into the standard MediCar Plus admin email template."""
    year = datetime.now(timezone.utc).year
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:#0b0e14;padding:24px;font-family:Arial,Helvetica,sans-serif">
  <tr><td align="center">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0"
           style="background:#111827;border-radius:12px;overflow:hidden">
      <tr><td style="background:{color};padding:20px 24px;color:#fff">
        <h2 style="margin:0;font-size:20px">{title}</h2>
      </td></tr>
      <tr><td style="padding:24px;color:#e5e7eb;font-size:14px;line-height:1.6">
        {body_html}
        <p style="margin:24px 0 0;font-size:12px;color:#94a3b8">
          MediCar Plus · Notificación automática · {year}<br>
          No respondas a este email. Accede al panel para gestionar.
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
""".strip()


def _kv_row(label: str, value: str, mono: bool = False) -> str:
    val_style = "font-family:ui-monospace,Menlo,monospace;color:#fbbf24" if mono else "color:#f5f5f5"
    return (
        f'<tr><td style="padding:6px 0;color:#94a3b8;width:180px">{label}</td>'
        f'<td style="padding:6px 0;{val_style}"><b>{value}</b></td></tr>'
    )


def notify_payment_failed(
    *,
    customer_email: str,
    install_id: Optional[str],
    amount_cents: int,
    currency: str,
    failed_count: int,
    hosted_invoice_url: Optional[str],
    stripe_subscription_id: Optional[str],
    invoice_created_iso: Optional[str],
    company_name: Optional[str] = None,
) -> tuple[bool, str]:
    """Sends the 🚨 red alert to the admin. Returns (sent, info)."""
    if not _smtp_configured():
        return False, "smtp_not_configured"

    to = _admin_email()
    subject = f"⚠️ Pago fallido — MediCar Plus — {customer_email or 'cliente desconocido'}"

    rows = [
        _kv_row("Cliente (email)", customer_email or "—", mono=True),
        _kv_row("Empresa", company_name or "—"),
        _kv_row("Install ID", install_id or "—", mono=True),
        _kv_row("Importe intentado", _fmt_eur(amount_cents)),
        _kv_row("Divisa", (currency or "eur").upper()),
        _kv_row("Intentos fallidos", str(failed_count)),
        _kv_row("Fecha intento", _fmt_dt(invoice_created_iso)),
        _kv_row("Suscripción Stripe", stripe_subscription_id or "—", mono=True),
    ]

    hosted_link = (
        f'<p style="margin:16px 0"><a href="{hosted_invoice_url}" '
        f'style="background:#dc2626;color:#fff;padding:10px 18px;border-radius:8px;'
        f'text-decoration:none;display:inline-block">Ver factura en Stripe</a></p>'
        if hosted_invoice_url else ""
    )
    panel_url = _admin_panel_url()

    body = f"""
<p style="margin:0 0 12px;font-size:15px">
  Se ha registrado un <b style="color:#f87171">pago fallido</b> en la suscripción de un cliente.
  Stripe reintentará el cobro automáticamente durante ~3 semanas antes de cancelar.
</p>
<table role="presentation" cellpadding="0" cellspacing="0" width="100%"
       style="border-top:1px solid #374151;border-bottom:1px solid #374151;
       margin:12px 0;padding:12px 0">
  {''.join(rows)}
</table>
{hosted_link}
<p style="margin:16px 0 0">
  <a href="{panel_url}" style="color:#60a5fa">→ Abrir Panel Licencias</a>
</p>
<p style="margin:16px 0 0;font-size:12px;color:#94a3b8;font-style:italic">
  Recomendación: contacta al cliente si es un cliente clave. Si prefieres esperar,
  Stripe volverá a intentarlo automáticamente.
</p>
"""
    html = _base_wrapper("🚨 Pago fallido detectado", "#dc2626", body)

    ok, info = _send_smtp(to, subject, html)
    if ok:
        logger.info(f"[admin_notifier] payment_failed email sent to {to} for {customer_email}")
    else:
        logger.warning(f"[admin_notifier] payment_failed email failed: {info}")
    return ok, info


def notify_payment_recovered(
    *,
    customer_email: str,
    install_id: Optional[str],
    amount_cents: int,
    currency: str,
    hosted_invoice_url: Optional[str],
    stripe_subscription_id: Optional[str],
    paid_at_iso: Optional[str],
    company_name: Optional[str] = None,
) -> tuple[bool, str]:
    """Sends the ✅ green recovery alert to the admin. Returns (sent, info)."""
    if not _smtp_configured():
        return False, "smtp_not_configured"

    to = _admin_email()
    subject = f"✅ Pago recuperado — MediCar Plus — {customer_email or 'cliente'}"

    rows = [
        _kv_row("Cliente (email)", customer_email or "—", mono=True),
        _kv_row("Empresa", company_name or "—"),
        _kv_row("Install ID", install_id or "—", mono=True),
        _kv_row("Importe cobrado", _fmt_eur(amount_cents)),
        _kv_row("Divisa", (currency or "eur").upper()),
        _kv_row("Fecha cobro", _fmt_dt(paid_at_iso)),
        _kv_row("Suscripción Stripe", stripe_subscription_id or "—", mono=True),
    ]

    hosted_link = (
        f'<p style="margin:16px 0"><a href="{hosted_invoice_url}" '
        f'style="background:#16a34a;color:#fff;padding:10px 18px;border-radius:8px;'
        f'text-decoration:none;display:inline-block">Ver factura en Stripe</a></p>'
        if hosted_invoice_url else ""
    )
    panel_url = _admin_panel_url()

    body = f"""
<p style="margin:0 0 12px;font-size:15px">
  El cliente había tenido <b style="color:#f87171">pagos fallidos previos</b> y
  Stripe acaba de <b style="color:#4ade80">cobrar con éxito</b>. Su estado vuelve a verde.
</p>
<table role="presentation" cellpadding="0" cellspacing="0" width="100%"
       style="border-top:1px solid #374151;border-bottom:1px solid #374151;
       margin:12px 0;padding:12px 0">
  {''.join(rows)}
</table>
{hosted_link}
<p style="margin:16px 0 0">
  <a href="{panel_url}" style="color:#60a5fa">→ Abrir Panel Licencias</a>
</p>
<p style="margin:16px 0 0;font-size:12px;color:#94a3b8;font-style:italic">
  No hace falta que contactes al cliente: el cobro ya está confirmado.
</p>
"""
    html = _base_wrapper("✅ Pago recuperado", "#16a34a", body)

    ok, info = _send_smtp(to, subject, html)
    if ok:
        logger.info(f"[admin_notifier] payment_recovered email sent to {to} for {customer_email}")
    else:
        logger.warning(f"[admin_notifier] payment_recovered email failed: {info}")
    return ok, info
