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


def _reply_to() -> str:
    """Adreça on van les respostes dels mails automàtics (suport)."""
    return (os.environ.get("REPLY_TO_EMAIL") or "suport@medicarplus.es").strip()


def is_configured() -> bool:
    return bool(_api_key())


GUIDE_ATTACHMENTS = [
    {
        "pdf_name": "guia-instalacion-medicar-plus.pdf",
        "html_path": "/app/frontend/public/guia-client-installacio.html",
        "doc_kind": "guia",
        "doc_title": "Guía de Instalación",
        "doc_subtitle": "Cómo activar tu licencia MediCar Plus en 5 minutos · Windows",
    },
    # NOTA: El Manual de Usuario ja NO s'adjunta com a PDF perquè conté
    # pestanyes interactives (Empezar / Tráfico / Revisiones / Contabilidad …)
    # que no funcionen en format PDF. En lloc d'això, el correu enllaça a la
    # versió web online (https://…/manual-usuari.html) on tot funciona.
]


async def _load_attachments(
    *,
    client_name: str,
    install_id: str,
    license_key: str,
    plan: str,
    expires_at: Optional[datetime],
) -> list[tuple[str, bytes]]:
    """Genera PDFs personalitzats (portada + cos) per client i els retorna com a adjunts.

    Si la conversió falla, fa fallback al HTML original perquè el correu
    encara arribi amb documentació.
    """
    from services.pdf_builder import build_client_pdf
    from services.doc_counter import next_doc_number

    # Un únic Nº Documento per aquesta emissió (compartit entre guia i manual)
    try:
        doc_number = await next_doc_number()
    except Exception:  # noqa: BLE001
        doc_number = ""

    out: list[tuple[str, bytes]] = []
    for spec in GUIDE_ATTACHMENTS:
        pdf_bytes = await build_client_pdf(
            doc_kind=spec["doc_kind"],
            body_html_path=spec["html_path"],
            doc_title=spec["doc_title"],
            doc_subtitle=spec["doc_subtitle"],
            client_name=client_name,
            install_id=install_id,
            plan=plan,
            expires_at=expires_at,
            license_key=license_key,
            doc_number=doc_number,
        )
        if pdf_bytes:
            out.append((spec["pdf_name"], pdf_bytes))
            continue
        # Fallback: adjunta l'HTML si el PDF no es pot generar
        try:
            with open(spec["html_path"], "rb") as fh:
                fallback_name = os.path.basename(spec["html_path"])
                out.append((fallback_name, fh.read()))
        except Exception as ex:  # noqa: BLE001
            logger.warning("attachment missing: %s (%s)", spec["html_path"], ex)
    return out


def _reason_header(reason: str, plan: str) -> tuple[str, str, str, str]:
    """Devuelve (emoji, título grande, subtítulo explicativo, color hex) según motivo del email.

    Objetivo: que el cliente entienda AL INSTANTE por qué recibe este email,
    sin tener que leer tecnicismos ni interpretar la clave.
    """
    plan_up = (plan or "").upper()
    plan_nice = {"TRIAL": "Prueba gratuita", "STD": "Standard", "STANDARD": "Standard",
                 "PRM": "Premium", "PREMIUM": "Premium"}.get(plan_up, plan_up or "MediCar Plus")
    r = (reason or "activated").lower()
    if r == "renewed":
        return (
            "🔄",
            "Tu suscripción se ha renovado",
            f"Todo en orden. Hemos cobrado automáticamente la cuota de tu plan <b>{plan_nice}</b> y hemos extendido tu licencia por otro periodo. No necesitas hacer nada.",
            "#22c55e",
        )
    if r == "upgraded":
        return (
            "⬆️",
            "¡Plan actualizado con éxito!",
            f"Has cambiado a <b>{plan_nice}</b>. Ya tienes disponibles todas las funciones del nuevo plan. Al abrir MediCar Plus lo detectará automáticamente.",
            "#a855f7",
        )
    if r == "downgraded":
        return (
            "⬇️",
            "Has cambiado a un plan más básico",
            f"Tu suscripción ahora es <b>{plan_nice}</b>. La aplicación seguirá funcionando con las funciones incluidas en tu nuevo plan.",
            "#0ea5e9",
        )
    if r == "reactivated":
        return (
            "✅",
            "Bienvenido de vuelta a MediCar Plus",
            f"Tu suscripción <b>{plan_nice}</b> vuelve a estar activa. Puedes seguir usando la aplicación con normalidad.",
            "#22c55e",
        )
    # Por defecto: activación inicial (primer email)
    return (
        "🎉",
        "¡Tu licencia MediCar Plus ya está lista!",
        f"Gracias por confiar en nosotros. Has activado el plan <b>{plan_nice}</b>. En 5 minutos tendrás la aplicación instalada y funcionando.",
        "#f5b301",
    )


def _render_html(
    *,
    client_name: str,
    install_id: str,
    license_key: str,
    plan: str,
    expires_at: Optional[datetime],
    referral_code: Optional[str] = None,
    reason: str = "activated",
) -> str:
    expiry_txt = (
        expires_at.strftime("%d/%m/%Y") if expires_at else "Perpetua (sin caducidad)"
    )
    public_base = (os.environ.get("PUBLIC_APP_URL") or "https://medicarplus.es").rstrip("/")
    manual_url = f"{public_base}/manual-usuari.html"
    guia_url = f"{public_base}/guia-client-installacio.html"
    download_url = "https://medicarplus.es/api/download/latest-installer"
    emoji, big_title, subtitle, color = _reason_header(reason, plan)
    plan_up = (plan or "").upper()
    plan_nice = {"TRIAL": "Prueba gratuita", "STD": "Standard", "STANDARD": "Standard",
                 "PRM": "Premium", "PREMIUM": "Premium"}.get(plan_up, plan_up or "—")

    # Bloque referrals solo en el email de ACTIVACIÓN de un plan pagado (no en renovaciones)
    is_paid = plan_up in ("STD", "STANDARD", "PRM", "PREMIUM") and referral_code
    show_referral = is_paid and reason.lower() == "activated"
    referral_block = ""
    if show_referral:
        share_url = f"https://medicarplus.es/?ref={referral_code}"
        referral_block = f"""
        <table width="100%" cellpadding="16" cellspacing="0" style="background:linear-gradient(135deg,rgba(168,85,247,.14),rgba(34,197,94,.06));border:2px dashed #a855f7;border-radius:10px;margin:22px 0">
          <tr><td>
            <div style="color:#e9d5ff;font-weight:800;font-size:14px;letter-spacing:.5px;margin-bottom:6px">🎁 Recomienda MediCar Plus y gana meses gratis</div>
            <div style="color:#c4b5fd;font-size:12.5px;line-height:1.6;margin-bottom:12px">
              Comparte tu código y <b>ganas 2 meses gratis</b> por cada amigo que se suscriba. Ellos ganan 1 mes gratis también.
            </div>
            <div style="background:#0b1121;border:1px dashed #a855f7;border-radius:8px;padding:12px;text-align:center;font-family:'Courier New',monospace;font-size:18px;font-weight:800;color:#f5b301;letter-spacing:2px;user-select:all;margin-bottom:8px">{referral_code}</div>
            <div style="text-align:center">
              <a href="{share_url}" style="color:#a855f7;font-size:12px;text-decoration:underline;word-break:break-all">{share_url}</a>
            </div>
          </td></tr>
        </table>"""

    # Solo mostramos "Cómo activarla" en el email de ACTIVACIÓN inicial
    show_activation_steps = reason.lower() == "activated"
    activation_steps = ""
    if show_activation_steps:
        activation_steps = f"""
        <div style="background:#0f172a;border:1px solid #334155;border-radius:10px;padding:18px 20px;margin:22px 0">
          <div style="color:#f5b301;font-size:14px;font-weight:800;margin-bottom:12px;letter-spacing:.3px">📋 Solo 3 pasos para empezar</div>
          <div style="color:#e2e8f0;font-size:14px;line-height:1.9">
            <div><b style="color:{color}">1.</b> Pulsa el botón <b>Descargar la app</b> de abajo.</div>
            <div><b style="color:{color}">2.</b> Instala el fichero <code style="background:#1e293b;padding:2px 6px;border-radius:4px;font-size:12px">.exe</code> (doble clic).</div>
            <div><b style="color:{color}">3.</b> Cuando la aplicación te pida la clave, <b>copia</b> la que encontrarás más abajo y <b>pégala</b>. Se activará sola.</div>
          </div>
          <div style="margin-top:12px;padding-top:12px;border-top:1px dashed #334155;color:#94a3b8;font-size:12px">
            💡 Adjunto encontrarás la guía completa en PDF por si prefieres seguirla paso a paso.
          </div>
        </div>"""

    # Botones de acción (CTA) — el principal cambia según motivo
    if reason.lower() == "activated":
        primary_cta = f'<a href="{download_url}" style="display:inline-block;padding:16px 32px;background:{color};color:#0f172a;text-decoration:none;font-weight:800;font-size:15px;border-radius:10px;letter-spacing:.3px">📥 Descargar la aplicación</a>'
    elif reason.lower() in ("renewed", "reactivated"):
        primary_cta = f'<a href="{download_url}" style="display:inline-block;padding:14px 28px;background:{color};color:#0f172a;text-decoration:none;font-weight:800;font-size:14px;border-radius:10px">↻ Actualizar la app (opcional)</a>'
    else:  # upgraded/downgraded
        primary_cta = f'<a href="{download_url}" style="display:inline-block;padding:14px 28px;background:{color};color:#0f172a;text-decoration:none;font-weight:800;font-size:14px;border-radius:10px">💻 Abrir MediCar Plus</a>'

    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;padding:32px 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="background:#1e293b;border:2px solid {color};border-radius:14px;padding:32px;color:#e2e8f0">
      <tr><td>
        <!-- CABECERA CON MOTIVO CLARO -->
        <div style="text-align:center;margin-bottom:8px">
          <div style="font-size:52px;line-height:1">{emoji}</div>
        </div>
        <h1 style="margin:8px 0 6px 0;color:{color};font-size:24px;text-align:center;font-weight:800">{big_title}</h1>
        <p style="margin:0 0 4px 0;color:#94a3b8;font-size:12px;text-align:center;letter-spacing:.5px;text-transform:uppercase">MediCar Plus · Software profesional</p>

        <p style="color:#cbd5e1;font-size:15px;line-height:1.6;margin:22px 0 0">
          Hola <b>{client_name}</b>,
        </p>
        <p style="color:#cbd5e1;font-size:14.5px;line-height:1.65;margin:8px 0 20px">
          {subtitle}
        </p>

        <!-- Datos clave en lenguaje humano -->
        <table width="100%" cellpadding="12" cellspacing="0" style="background:#0f172a;border:1px solid #334155;border-radius:10px;margin:14px 0;font-size:14px">
          <tr>
            <td style="color:#94a3b8;width:40%">Plan contratado</td>
            <td style="color:{color};font-weight:700">{plan_nice}</td>
          </tr>
          <tr>
            <td style="color:#94a3b8">Válida hasta</td>
            <td style="color:#e2e8f0;font-weight:700">{expiry_txt}</td>
          </tr>
        </table>

        {activation_steps}

        <!-- CTA principal grande y claro -->
        <div style="text-align:center;margin:26px 0 22px">
          {primary_cta}
        </div>

        {referral_block}

        <!-- DATOS TÉCNICOS colapsables al final -->
        <div style="margin-top:24px;padding-top:20px;border-top:1px solid #334155">
          <div style="color:#94a3b8;font-size:11px;letter-spacing:1px;text-transform:uppercase;font-weight:700;margin-bottom:10px">🔐 Datos técnicos de tu licencia</div>
          <div style="color:#64748b;font-size:12px;line-height:1.5;margin-bottom:10px">
            Solo necesitas esto si la aplicación te lo pide manualmente. Normalmente se activa sola.
          </div>
          <table width="100%" cellpadding="6" cellspacing="0" style="background:#0b1121;border:1px solid #334155;border-radius:6px;font-family:'Courier New',monospace;font-size:11px">
            <tr><td style="color:#64748b;width:28%">ID instalación</td><td style="color:#94a3b8;word-break:break-all">{install_id}</td></tr>
            <tr><td style="color:#64748b" colspan="2">
              <div style="color:#64748b;margin:8px 0 4px">Clave de licencia (para copiar y pegar):</div>
              <div style="background:#0f172a;border:1px dashed #334155;border-radius:6px;padding:10px;color:#cbd5e1;word-break:break-all;line-height:1.4;user-select:all;-webkit-user-select:all;cursor:text;font-size:10.5px">{license_key}</div>
              <div style="color:#22c55e;font-size:11px;margin-top:6px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif">👆 Haz doble clic para seleccionarla entera, después <b>Ctrl+C</b> para copiar.</div>
            </td></tr>
          </table>
        </div>

        <p style="color:#64748b;font-size:12px;margin-top:24px;padding-top:16px;border-top:1px solid #334155;line-height:1.6;text-align:center">
          ¿Alguna duda? Responde a este email o escríbenos a <a href="mailto:suport@medicarplus.es" style="color:{color};text-decoration:none">suport@medicarplus.es</a><br>
          <span style="color:#475569;font-size:11px">MediCar Plus · Marc Brugulat Lopez · <a href="https://medicarplus.es" style="color:#475569;text-decoration:none">medicarplus.es</a></span>
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
    subject_prefix: Optional[str] = None,
    referral_code: Optional[str] = None,
    reason: str = "activated",
) -> tuple[bool, str]:
    """Envia l'email de llicència aprovada. Intenta Resend, fallback a SMTP.

    `reason` controla la CABECERA del email para que el cliente entienda al
    instante por qué lo recibe. Valores válidos:
      - "activated"    → 🎉 activación inicial
      - "renewed"      → 🔄 renovación automática mensual/anual
      - "upgraded"     → ⬆️ cambio a plan superior
      - "downgraded"   → ⬇️ cambio a plan inferior
      - "reactivated"  → ✅ reactivación tras cancelación/pago fallido

    Returns:
        (sent, info). sent=True si algun mètode ha reeixit.
    """
    # Asunto según motivo (evita duplicar el plan en el subject como "PREMIUM (PREMIUM)")
    plan_up = (plan or "").upper()
    plan_nice = {"TRIAL": "Prueba", "STD": "Standard", "STANDARD": "Standard",
                 "PRM": "Premium", "PREMIUM": "Premium"}.get(plan_up, plan_up or "")
    r = (reason or "activated").lower()
    if r == "renewed":
        subject = f"MediCar Plus · Suscripción {plan_nice} renovada"
    elif r == "upgraded":
        subject = f"MediCar Plus · Bienvenido al plan {plan_nice} ✨"
    elif r == "downgraded":
        subject = f"MediCar Plus · Cambio de plan confirmado ({plan_nice})"
    elif r == "reactivated":
        subject = f"MediCar Plus · Suscripción {plan_nice} reactivada"
    else:  # activated (default)
        subject = f"MediCar Plus · Tu licencia {plan_nice} está lista 🎉"
    # Si el llamador fuerza un subject_prefix legacy, lo respetamos (compat)
    if subject_prefix:
        # Solo añadimos plan si no está ya presente en el prefix (evita "PREMIUM (PREMIUM)")
        if plan_up and plan_up in subject_prefix.upper():
            subject = f"MediCar Plus · {subject_prefix}"
        else:
            subject = f"MediCar Plus · {subject_prefix}"
    html = _render_html(
        client_name=client_name,
        install_id=install_id,
        license_key=license_key,
        plan=plan,
        expires_at=expires_at,
        referral_code=referral_code,
        reason=reason,
    )
    attachments = await _load_attachments(
        client_name=client_name,
        install_id=install_id,
        license_key=license_key,
        plan=plan,
        expires_at=expires_at,
    )

    # 1) Prova Resend
    if is_configured():
        try:
            import base64 as _b64
            import resend  # type: ignore

            resend.api_key = _api_key()
            params: dict = {
                "from": _sender(),
                "reply_to": [_reply_to()],
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


async def send_payment_failed_email(
    *,
    to_email: str,
    client_name: str,
    plan: str,
    hosted_invoice_url: Optional[str] = None,
    amount_eur: Optional[float] = None,
) -> tuple[bool, str]:
    """Envía email al cliente cuando Stripe no ha podido cobrar la renovación.

    El único CTA es 'Actualizar método de pago' apuntando al invoice hosted URL
    de Stripe (que incluye el botón para cambiar tarjeta). Cero tecnicismos.
    """
    if not to_email or "@" not in to_email:
        return False, "invalid_email"

    plan_up = (plan or "").upper()
    plan_nice = {"TRIAL": "Prueba", "STD": "Standard", "STANDARD": "Standard",
                 "PRM": "Premium", "PREMIUM": "Premium"}.get(plan_up, plan_up or "MediCar Plus")
    amount_txt = f"{amount_eur:.2f} €".replace(".", ",") if amount_eur else "la cuota de tu plan"
    cta_url = hosted_invoice_url or "https://medicarplus.es/#pricing"

    subject = f"⚠️ MediCar Plus · No hemos podido cobrar tu suscripción"
    html = f"""<!doctype html><html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px">
<div style="max-width:560px;margin:auto;background:#1e293b;border-radius:14px;padding:32px;border:2px solid #f97316">
  <div style="text-align:center;font-size:52px;line-height:1">⚠️</div>
  <h1 style="text-align:center;color:#f97316;font-size:24px;margin:12px 0 8px;font-weight:800">No hemos podido cobrar tu suscripción</h1>
  <p style="text-align:center;color:#94a3b8;font-size:12px;margin:0 0 26px;letter-spacing:.5px;text-transform:uppercase">MediCar Plus · Software profesional</p>

  <p style="color:#cbd5e1;font-size:15px;line-height:1.65;margin:0 0 12px">Hola <b>{client_name}</b>,</p>
  <p style="color:#cbd5e1;font-size:14.5px;line-height:1.65;margin:0 0 20px">
    Hemos intentado cobrar <b>{amount_txt}</b> de tu plan <b>{plan_nice}</b> pero <b>tu tarjeta ha sido rechazada</b>.
    Puede ser porque ha caducado, no tiene saldo, o tu banco la ha bloqueado por seguridad.
  </p>

  <div style="background:rgba(249,115,22,.08);border:1px solid rgba(249,115,22,.35);border-radius:10px;padding:16px 18px;margin:18px 0;color:#fed7aa;font-size:13.5px;line-height:1.6">
    <b>¿Qué pasa ahora?</b><br>
    Stripe volverá a intentar el cobro automáticamente durante las próximas 3 semanas. Para evitar que tu licencia se cancele, actualiza tu método de pago cuanto antes.
  </div>

  <div style="text-align:center;margin:26px 0">
    <a href="{cta_url}" style="display:inline-block;padding:16px 32px;background:#f97316;color:#0f172a;text-decoration:none;font-weight:800;font-size:15px;border-radius:10px;letter-spacing:.3px">💳 Actualizar mi tarjeta</a>
  </div>

  <p style="color:#94a3b8;font-size:13px;line-height:1.6;margin:20px 0 0">
    Si tienes cualquier duda, escríbenos a <a href="mailto:suport@medicarplus.es" style="color:#f97316">suport@medicarplus.es</a> o responde a este email.
    Estamos aquí para ayudarte.
  </p>

  <p style="color:#64748b;font-size:11px;margin-top:24px;padding-top:16px;border-top:1px solid #334155;line-height:1.6;text-align:center">
    Este email es una notificación transaccional relacionada con tu suscripción activa.<br>
    MediCar Plus · Marc Brugulat Lopez · <a href="https://medicarplus.es" style="color:#64748b">medicarplus.es</a>
  </p>
</div>
</body></html>"""

    if is_configured():
        try:
            import resend  # type: ignore
            resend.api_key = _api_key()
            params: dict = {
                "from": _sender(),
                "reply_to": [_reply_to()],
                "to": [to_email],
                "subject": subject,
                "html": html,
            }
            result = await asyncio.to_thread(resend.Emails.send, params)
            email_id = result.get("id") if isinstance(result, dict) else None
            return True, email_id or "resend_sent"
        except Exception:
            logger.exception("Resend send (payment_failed) failed, falling back to SMTP")

    if _smtp_configured():
        ok, info = await asyncio.to_thread(_send_smtp, to_email, subject, html, None)
        return ok, info

    return False, "no_mail_provider_configured"


async def send_subscription_canceled_email(
    *,
    to_email: str,
    client_name: str,
    plan: str,
    access_until: Optional[datetime] = None,
) -> tuple[bool, str]:
    """Email de despedida cuando la suscripción termina definitivamente.

    Tono amable, sin culpar. Le decimos hasta cuándo tiene acceso y le damos
    un link para volver cuando quiera. Sin tecnicismos, sin clave.
    """
    if not to_email or "@" not in to_email:
        return False, "invalid_email"

    plan_up = (plan or "").upper()
    plan_nice = {"TRIAL": "Prueba", "STD": "Standard", "STANDARD": "Standard",
                 "PRM": "Premium", "PREMIUM": "Premium"}.get(plan_up, plan_up or "MediCar Plus")
    if access_until:
        until_txt = access_until.strftime("%d/%m/%Y")
        access_line = f"Podrás seguir usando MediCar Plus hasta el <b>{until_txt}</b> con normalidad."
    else:
        access_line = "El acceso a MediCar Plus ha terminado. Tus datos locales siguen en tu ordenador."

    subject = "MediCar Plus · Suscripción cancelada"
    html = f"""<!doctype html><html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px">
<div style="max-width:560px;margin:auto;background:#1e293b;border-radius:14px;padding:32px;border:2px solid #64748b">
  <div style="text-align:center;font-size:52px;line-height:1">👋</div>
  <h1 style="text-align:center;color:#e2e8f0;font-size:22px;margin:12px 0 8px;font-weight:800">Suscripción cancelada</h1>
  <p style="text-align:center;color:#94a3b8;font-size:12px;margin:0 0 24px;letter-spacing:.5px;text-transform:uppercase">MediCar Plus · Software profesional</p>

  <p style="color:#cbd5e1;font-size:15px;line-height:1.65;margin:0 0 12px">Hola <b>{client_name}</b>,</p>
  <p style="color:#cbd5e1;font-size:14.5px;line-height:1.65;margin:0 0 18px">
    Confirmamos que tu suscripción <b>{plan_nice}</b> se ha cancelado. Gracias por haber confiado en nosotros durante este tiempo.<br><br>
    {access_line}
  </p>

  <div style="background:rgba(148,163,184,.08);border:1px solid rgba(148,163,184,.25);border-radius:10px;padding:14px 16px;margin:18px 0;color:#cbd5e1;font-size:13px;line-height:1.6">
    <b>Cuando quieras volver</b>, solo tienes que activar una nueva suscripción desde <a href="https://medicarplus.es/#pricing" style="color:#f5b301">medicarplus.es</a>. Recuperarás el acceso al instante y con los mismos datos que tenías.
  </div>

  <div style="text-align:center;margin:24px 0">
    <a href="https://medicarplus.es/#pricing" style="display:inline-block;padding:14px 28px;background:#f5b301;color:#0f172a;text-decoration:none;font-weight:800;font-size:14px;border-radius:10px">Ver planes</a>
  </div>

  <p style="color:#64748b;font-size:11px;margin-top:24px;padding-top:16px;border-top:1px solid #334155;line-height:1.6;text-align:center">
    ¿Nos cuentas por qué te vas? Nos ayuda a mejorar: <a href="mailto:suport@medicarplus.es" style="color:#64748b">suport@medicarplus.es</a><br>
    <span style="color:#475569">MediCar Plus · Marc Brugulat Lopez · <a href="https://medicarplus.es" style="color:#475569">medicarplus.es</a></span>
  </p>
</div>
</body></html>"""

    if is_configured():
        try:
            import resend  # type: ignore
            resend.api_key = _api_key()
            params: dict = {
                "from": _sender(),
                "reply_to": [_reply_to()],
                "to": [to_email],
                "subject": subject,
                "html": html,
            }
            result = await asyncio.to_thread(resend.Emails.send, params)
            email_id = result.get("id") if isinstance(result, dict) else None
            return True, email_id or "resend_sent"
        except Exception:
            logger.exception("Resend send (subscription_canceled) failed, falling back to SMTP")

    if _smtp_configured():
        ok, info = await asyncio.to_thread(_send_smtp, to_email, subject, html, None)
        return ok, info

    return False, "no_mail_provider_configured"


async def send_referral_notification_email(
    *,
    referrer_email: str,
    referrer_name: str,
    referred_display_name: str,
    referred_plan: str,
    total_referrals: int,
    months_earned_total: int,
) -> tuple[bool, str]:
    """
    Envia un email al REFERRER quan un dels seus referits paga la 1a subscripció.

    L'email confirma la recompensa (+2 mesos gratis) i mostra estadístiques del programa.
    Funciona amb Resend + SMTP fallback (idèntic a send_license_email).
    """
    if not referrer_email or "@" not in referrer_email:
        return False, "invalid_referrer_email"

    subject = f"🎉 MediCar Plus · ¡Has ganado 2 meses gratis! · Ref: {referred_display_name}"
    # Bloc HTML simple i clar
    html = f"""<!doctype html><html><body style="font-family:Segoe UI,Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px">
<div style="max-width:560px;margin:auto;background:#1e293b;border-radius:14px;padding:32px;border:1px solid #334155">
  <div style="text-align:center;font-size:52px;line-height:1">🎁</div>
  <h1 style="text-align:center;color:#fbbf24;font-size:24px;margin:12px 0 8px">¡Enhorabuena, {referrer_name or 'cliente'}!</h1>
  <p style="text-align:center;color:#94a3b8;font-size:14px;margin:0 0 26px">Tu programa de referidos MediCar Plus da sus frutos.</p>

  <div style="background:linear-gradient(135deg,rgba(34,197,94,.15),rgba(34,197,94,.05));border:2px solid #22c55e;border-radius:12px;padding:20px;margin:22px 0;text-align:center">
    <div style="font-size:13px;color:#a7f3d0;font-weight:700;letter-spacing:.5px;text-transform:uppercase">Recompensa aplicada</div>
    <div style="font-size:28px;color:#4ade80;font-weight:900;margin:8px 0">+2 meses gratis</div>
    <div style="font-size:13px;color:#bbf7d0">Aplicados automáticamente a tu suscripción MediCar Plus. Tu próximo cobro se retrasa 2 meses.</div>
  </div>

  <div style="background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.25);border-radius:10px;padding:16px;margin:18px 0">
    <div style="font-size:13px;color:#bfdbfe;font-weight:700;margin-bottom:6px">👥 Cliente referido</div>
    <div style="color:#e2e8f0;font-size:14px;line-height:1.6">
      <b>{referred_display_name}</b> ha activado su suscripción <b style="color:#f5b301">{referred_plan}</b>.<br>
      <span style="color:#94a3b8;font-size:12px">Le hemos aplicado también <b>1 mes gratis</b> (nuestro incentivo por venir de tu recomendación).</span>
    </div>
  </div>

  <div style="display:flex;gap:12px;margin:22px 0">
    <div style="flex:1;background:#0b1121;border-radius:10px;padding:14px;text-align:center;border:1px solid #334155">
      <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px">Total referidos</div>
      <div style="font-size:26px;color:#f5b301;font-weight:900;margin-top:4px">{total_referrals}</div>
    </div>
    <div style="flex:1;background:#0b1121;border-radius:10px;padding:14px;text-align:center;border:1px solid #334155">
      <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px">Meses ganados</div>
      <div style="font-size:26px;color:#4ade80;font-weight:900;margin-top:4px">+{months_earned_total}</div>
    </div>
  </div>

  <p style="color:#cbd5e1;font-size:13px;line-height:1.6;margin:20px 0 4px">
    Sigue compartiendo tu enlace para acumular más meses gratis. Cada nuevo cliente que pague te suma <b>2 meses adicionales</b>.
  </p>
  <p style="color:#94a3b8;font-size:12px;line-height:1.5;margin:8px 0 0">
    Puedes ver tu código y estadísticas en cualquier momento desde la propia aplicación MediCar Plus, en el modal <b>Información de licencia</b> (esquina superior derecha).
  </p>

  <hr style="border:0;border-top:1px solid #334155;margin:26px 0 16px">
  <div style="text-align:center;color:#64748b;font-size:11px;line-height:1.5">
    ¿Preguntas? <a href="mailto:suport@medicarplus.es" style="color:#f5b301">suport@medicarplus.es</a><br>
    Este email es una notificación transaccional relacionada con tu suscripción activa.
  </div>
</div>
</body></html>"""

    # Envia via el mateix pipeline (Resend + fallback SMTP), sense adjunts.
    if is_configured():
        try:
            import base64 as _b64  # noqa: F401
            import resend  # type: ignore
            resend.api_key = _api_key()
            params: dict = {
                "from": _sender(),
                "reply_to": [_reply_to()],
                "to": [referrer_email],
                "subject": subject,
                "html": html,
            }
            result = await asyncio.to_thread(resend.Emails.send, params)
            email_id = result.get("id") if isinstance(result, dict) else None
            return True, email_id or "resend_sent"
        except Exception as ex:  # noqa: BLE001
            logger.exception("Resend send (referral notif) failed, falling back to SMTP")

    if _smtp_configured():
        ok, info = await asyncio.to_thread(_send_smtp, referrer_email, subject, html, None)
        return ok, info

    return False, "no_mail_provider_configured"
