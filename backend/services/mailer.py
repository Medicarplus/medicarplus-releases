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


GUIDE_ATTACHMENTS = [
    ("guia-instalacion-medicar-plus.pdf", "/app/frontend/public/guia-client-installacio.html"),
    ("manual-usuario-medicar-plus.pdf", "/app/frontend/public/manual-usuari.html"),
]


async def _load_attachments() -> list[tuple[str, bytes]]:
    """Genera PDFs a partir dels HTML de guia/manual i els retorna com a adjunts.

    Si la conversió a PDF falla, fa fallback al HTML original perquè el correu
    encara arribi amb documentació.
    """
    from services.pdf_builder import html_to_pdf

    out: list[tuple[str, bytes]] = []
    for pdf_name, html_path in GUIDE_ATTACHMENTS:
        pdf_bytes = await html_to_pdf(html_path)
        if pdf_bytes:
            out.append((pdf_name, pdf_bytes))
            continue
        # Fallback: adjunta l'HTML si el PDF no es pot generar
        try:
            with open(html_path, "rb") as fh:
                fallback_name = os.path.basename(html_path)
                out.append((fallback_name, fh.read()))
        except Exception as ex:  # noqa: BLE001
            logger.warning("attachment missing: %s (%s)", html_path, ex)
    return out


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
          2. Instala el ejecutable (sigue la <b style="color:#22c55e">guía de instalación</b> adjunta en PDF — <code style="color:#22c55e">guia-instalacion-medicar-plus.pdf</code>).<br>
          3. En la pantalla "Activación de licencia", pega la clave completa y pulsa <b>Activar</b>.<br>
          4. Consulta el <b style="color:#7ec8ff">manual de usuario completo</b> adjunto en PDF (<code style="color:#7ec8ff">manual-usuario-medicar-plus.pdf</code>) cuando tengas cualquier duda.
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
              <span style="color:#22c55e;font-size:13px;font-weight:700">
                📄 Guía<br>de instalación<br><span style="font-size:10px;color:#94a3b8;font-weight:400">(PDF adjunto)</span>
              </span>
            </td>
            <td style="width:2%"></td>
            <td style="background:#0f172a;border:1px solid #7ec8ff;border-radius:8px;padding:14px;text-align:center;width:33%">
              <span style="color:#7ec8ff;font-size:13px;font-weight:700">
                📄 Manual<br>de usuario<br><span style="font-size:10px;color:#94a3b8;font-weight:400">(PDF adjunto)</span>
              </span>
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


def _send_smtp(to_email: str, subject: str, html: str, attachments: list[tuple[str, bytes]] | None = None) -> tuple[bool, str]:
    """Envia email via SMTP (IONOS o qualsevol proveïdor SMTP) amb adjunts opcionals."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.application import MIMEApplication

    host = os.environ.get("SMTP_HOST", "").strip()
    port = int(os.environ.get("SMTP_PORT", "587").strip() or "587")
    user = os.environ.get("SMTP_USER", "").strip()
    pw = os.environ.get("SMTP_PASS", "").strip()
    sender = os.environ.get("SMTP_FROM", user).strip()

    try:
        # Si hi ha adjunts, usem "mixed" com a wrapper i "alternative" a dins
        if attachments:
            msg = MIMEMultipart("mixed")
            body = MIMEMultipart("alternative")
            body.attach(MIMEText(html, "html", "utf-8"))
            msg.attach(body)
            for fname, data in attachments:
                subtype = "pdf" if fname.lower().endswith(".pdf") else "octet-stream"
                part = MIMEApplication(data, _subtype=subtype)
                part.add_header("Content-Disposition", "attachment", filename=fname)
                msg.attach(part)
        else:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(html, "html", "utf-8"))

        msg["From"] = f"MediCar Plus <{sender}>"
        msg["To"] = to_email
        msg["Subject"] = subject

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
    attachments = await _load_attachments()

    # 1) Prova Resend
    if is_configured():
        try:
            import base64 as _b64
            import resend  # type: ignore

            resend.api_key = _api_key()
            params: dict = {
                "from": _sender(),
                "to": [to_email],
                "subject": subject,
                "html": html,
            }
            if attachments:
                params["attachments"] = [
                    {"filename": fname, "content": _b64.b64encode(data).decode("ascii")}
                    for fname, data in attachments
                ]
            result = await asyncio.to_thread(resend.Emails.send, params)
            email_id = result.get("id") if isinstance(result, dict) else None
            return True, email_id or "resend_sent"
        except Exception as ex:  # noqa: BLE001
            logger.exception("Resend send failed, falling back to SMTP")

    # 2) Fallback SMTP
    if _smtp_configured():
        ok, info = await asyncio.to_thread(_send_smtp, to_email, subject, html, attachments)
        return ok, info

    return False, "no_mail_provider_configured"
