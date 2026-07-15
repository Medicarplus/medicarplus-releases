"""Resend transactional email helper with graceful fallback.

If `RESEND_API_KEY` is missing/empty, `send_license_email` becomes a no-op that
returns `(False, "resend_not_configured")`. This lets us ship the approval flow
before the user finishes setting up their Resend account.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def _api_key() -> str:
    return (os.environ.get("RESEND_API_KEY") or "").strip()


def _sender() -> str:
    return (os.environ.get("SENDER_EMAIL") or "onboarding@resend.dev").strip()


def is_configured() -> bool:
    return bool(_api_key())


def _render_html(
    *,
    client_name: str,
    install_id: str,
    license_key: str,
    plan: str,
    expires_at: Optional[datetime],
) -> str:
    expiry_txt = (
        expires_at.strftime("%d/%m/%Y") if expires_at else "Perpetua (sin caducidad)"
    )
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;padding:32px 0;font-family:Georgia,serif">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="background:#1e293b;border:2px solid #f5b301;border-radius:14px;padding:32px;color:#e2e8f0">
      <tr><td>
        <h1 style="margin:0 0 6px 0;color:#f5b301;font-size:24px;letter-spacing:1px">MediCar Plus · Licencia activada</h1>
        <p style="margin:0 0 20px 0;color:#94a3b8;font-size:13px">Software comercial · Marc Brugulat Lopez</p>

        <p style="color:#e2e8f0;font-size:15px;line-height:1.55">Hola <b>{client_name}</b>,<br>
        Tu licencia ya está activa y vinculada a tu instalación.</p>

        <table width="100%" cellpadding="10" cellspacing="0" style="background:#0f172a;border:1px solid #334155;border-radius:8px;margin:16px 0;font-family:'Courier New',monospace;font-size:13px">
          <tr><td style="color:#f5b301;width:140px">Install ID</td><td>{install_id}</td></tr>
          <tr><td style="color:#f5b301">Plan</td><td>{plan}</td></tr>
          <tr><td style="color:#f5b301">Caducidad</td><td>{expiry_txt}</td></tr>
        </table>

        <p style="margin:20px 0 8px 0;color:#f5b301;font-size:13px;letter-spacing:1.2px"><b>TU CLAVE DE LICENCIA</b></p>
        <div style="background:#0f172a;border:1px dashed #f5b301;border-radius:8px;padding:14px;font-family:'Courier New',monospace;font-size:11px;color:#e2e8f0;word-break:break-all;line-height:1.5">{license_key}</div>

        <p style="color:#cbd5e1;font-size:14px;margin-top:22px;line-height:1.55">
          <b style="color:#f5b301">Cómo activarla:</b><br>
          1. Descarga la aplicación MediCar Plus desde <a href="https://github.com/Medicarplus/medicarplus-releases/releases/latest" style="color:#f5b301;text-decoration:underline">este enlace</a>.<br>
          2. Instala el ejecutable (sigue la <a href="https://medicarplus.es/guia-client-installacio.html" style="color:#f5b301;text-decoration:underline">guía de instalación de 5 minutos</a>).<br>
          3. En la pantalla "Activación de licencia", pega la clave completa y pulsa <b>Activar</b>.<br>
          4. Consulta el <a href="https://medicarplus.es/manual-usuari.html" style="color:#f5b301;text-decoration:underline">manual de usuario completo</a> cuando tengas cualquier duda.
        </p>

        <table width="100%" cellpadding="12" cellspacing="0" style="margin-top:20px">
          <tr>
            <td style="background:#0f172a;border:1px solid #f5b301;border-radius:8px;padding:14px;text-align:center;width:33%">
              <a href="https://github.com/Medicarplus/medicarplus-releases/releases/latest" style="color:#f5b301;text-decoration:none;font-size:13px;font-weight:700">
                📥 Descargar<br>la aplicación
              </a>
            </td>
            <td style="width:2%"></td>
            <td style="background:#0f172a;border:1px solid #22c55e;border-radius:8px;padding:14px;text-align:center;width:33%">
              <a href="https://medicarplus.es/guia-client-installacio.html" style="color:#22c55e;text-decoration:none;font-size:13px;font-weight:700">
                📥 Guía<br>de instalación
              </a>
            </td>
            <td style="width:2%"></td>
            <td style="background:#0f172a;border:1px solid #7ec8ff;border-radius:8px;padding:14px;text-align:center;width:33%">
              <a href="https://medicarplus.es/manual-usuari.html" style="color:#7ec8ff;text-decoration:none;font-size:13px;font-weight:700">
                📘 Manual<br>de usuario
              </a>
            </td>
          </tr>
        </table>

        <p style="color:#64748b;font-size:12px;margin-top:26px;padding-top:18px;border-top:1px solid #334155;line-height:1.5">
          Esta clave está vinculada a tu Install ID. Si cambias de ordenador, contacta con el proveedor para trasladarla.<br>
          Soporte: info@medicarplus.es · Marc Brugulat Lopez
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
""".strip()


def _smtp_configured() -> bool:
    return bool(
        (os.environ.get("SMTP_HOST") or "").strip()
        and (os.environ.get("SMTP_USER") or "").strip()
        and (os.environ.get("SMTP_PASS") or "").strip()
    )


def _send_smtp(to_email: str, subject: str, html: str) -> tuple[bool, str]:
    """Envia email via SMTP (IONOS o qualsevol proveïdor SMTP)."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    host = os.environ.get("SMTP_HOST", "").strip()
    port = int(os.environ.get("SMTP_PORT", "587").strip() or "587")
    user = os.environ.get("SMTP_USER", "").strip()
    pw = os.environ.get("SMTP_PASS", "").strip()
    sender = os.environ.get("SMTP_FROM", user).strip()

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"MediCar Plus <{sender}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(user, pw)
            smtp.sendmail(sender, [to_email], msg.as_string())
        return True, "smtp_sent"
    except Exception as ex:  # noqa: BLE001
        logger.exception("SMTP send failed")
        return False, f"smtp_error: {ex}"


async def send_license_email(
    *,
    to_email: str,
    client_name: str,
    install_id: str,
    license_key: str,
    plan: str,
    expires_at: Optional[datetime],
) -> tuple[bool, str]:
    """Envia l'email de llicència aprovada. Intenta Resend, fallback a SMTP.

    Returns:
        (sent, info). sent=True si algun mètode ha reeixit.
    """
    subject = f"MediCar Plus · Licencia activada ({plan})"
    html = _render_html(
        client_name=client_name,
        install_id=install_id,
        license_key=license_key,
        plan=plan,
        expires_at=expires_at,
    )

    # 1) Prova Resend
    if is_configured():
        try:
            import resend  # type: ignore

            resend.api_key = _api_key()
            params = {
                "from": _sender(),
                "to": [to_email],
                "subject": subject,
                "html": html,
            }
            result = await asyncio.to_thread(resend.Emails.send, params)
            email_id = result.get("id") if isinstance(result, dict) else None
            return True, email_id or "resend_sent"
        except Exception as ex:  # noqa: BLE001
            logger.exception("Resend send failed, falling back to SMTP")

    # 2) Fallback SMTP
    if _smtp_configured():
        ok, info = await asyncio.to_thread(_send_smtp, to_email, subject, html)
        return ok, info

    return False, "no_mail_provider_configured"
