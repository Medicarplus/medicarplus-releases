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
        expires_at.strftime("%d/%m/%Y") if expires_at else "Perpètua (sense caducitat)"
    )
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;padding:32px 0;font-family:Georgia,serif">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="background:#1e293b;border:2px solid #f5b301;border-radius:14px;padding:32px;color:#e2e8f0">
      <tr><td>
        <h1 style="margin:0 0 6px 0;color:#f5b301;font-size:24px;letter-spacing:1px">MediCar Plus · Llicència activada</h1>
        <p style="margin:0 0 20px 0;color:#94a3b8;font-size:13px">Software comercial · Marc Brugulat Lopez</p>

        <p style="color:#e2e8f0;font-size:15px;line-height:1.55">Hola <b>{client_name}</b>,<br>
        La teva llicència ja està activa i vinculada a la teva instal·lació.</p>

        <table width="100%" cellpadding="10" cellspacing="0" style="background:#0f172a;border:1px solid #334155;border-radius:8px;margin:16px 0;font-family:'Courier New',monospace;font-size:13px">
          <tr><td style="color:#f5b301;width:140px">Install ID</td><td>{install_id}</td></tr>
          <tr><td style="color:#f5b301">Plan</td><td>{plan}</td></tr>
          <tr><td style="color:#f5b301">Caducitat</td><td>{expiry_txt}</td></tr>
        </table>

        <p style="margin:20px 0 8px 0;color:#f5b301;font-size:13px;letter-spacing:1.2px"><b>LA TEVA CLAU DE LLICÈNCIA</b></p>
        <div style="background:#0f172a;border:1px dashed #f5b301;border-radius:8px;padding:14px;font-family:'Courier New',monospace;font-size:11px;color:#e2e8f0;word-break:break-all;line-height:1.5">{license_key}</div>

        <p style="color:#cbd5e1;font-size:14px;margin-top:22px;line-height:1.55">
          <b style="color:#f5b301">Com activar-la:</b><br>
          1. Obre l'aplicació <b>MediCar Plus</b>.<br>
          2. Al modal de "Activació de llicència", enganxa la clau completa i prem <b>Activar</b>.<br>
          3. L'app quedarà desbloquejada per aquesta instal·lació.
        </p>

        <p style="color:#64748b;font-size:12px;margin-top:26px;padding-top:18px;border-top:1px solid #334155;line-height:1.5">
          Aquesta clau està vinculada al teu Install ID. Si canvies d'ordinador, contacta amb el proveïdor per traspassar-la.<br>
          Suport: Marc Brugulat Lopez
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
""".strip()


async def send_license_email(
    *,
    to_email: str,
    client_name: str,
    install_id: str,
    license_key: str,
    plan: str,
    expires_at: Optional[datetime],
) -> tuple[bool, str]:
    """Envia l'email de llicència aprovada al client.

    Returns:
        (sent, message). `sent=False` si Resend no està configurat o si falla.
    """
    if not is_configured():
        return False, "resend_not_configured"

    try:
        import resend  # type: ignore

        resend.api_key = _api_key()

        params = {
            "from": _sender(),
            "to": [to_email],
            "subject": f"MediCar Plus · Llicència activada ({plan})",
            "html": _render_html(
                client_name=client_name,
                install_id=install_id,
                license_key=license_key,
                plan=plan,
                expires_at=expires_at,
            ),
        }
        result = await asyncio.to_thread(resend.Emails.send, params)
        email_id = result.get("id") if isinstance(result, dict) else None
        return True, email_id or "sent"
    except Exception as ex:  # noqa: BLE001
        logger.exception("Resend send failed")
        return False, f"resend_error: {ex}"
