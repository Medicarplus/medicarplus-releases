"""Admin endpoint para reenviar el instalador de MediCar Plus a un cliente.

Casos de uso:
- El cliente ha reformateado / cambiado de disco y ha perdido el .exe pero mantiene su clave
- El cliente pide el enlace de descarga porque no encuentra el email original

El endpoint envía un email desde `info@medicarplus.es` (IONOS SMTP ya configurado)
con el enlace de descarga del instalador y las instrucciones de reactivación.
"""

from __future__ import annotations

import os
import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, EmailStr

from services.mailer import _send_smtp, _smtp_configured

logger = logging.getLogger(__name__)


def _admin_ok(x_admin_token: Optional[str]) -> None:
    expected = os.environ.get("LICENSE_ADMIN_TOKEN", "")
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


class ResendDownloadBody(BaseModel):
    override_email: Optional[EmailStr] = None  # opcional: envío a otra dirección distinta al cliente_email guardado


def _download_url() -> str:
    """URL pública del instalador. Configurable via env var."""
    return (os.environ.get("INSTALLER_DOWNLOAD_URL") or "https://medicarplus.es/downloads/MediCarPlus-Setup.exe").strip()


def _build_email_html(client_name: str, license_key: str, install_id: str, download_url: str) -> str:
    return f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;background:#f4f4f7;padding:20px;color:#111">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:10px;padding:30px;box-shadow:0 2px 10px rgba(0,0,0,.05)">
  <div style="text-align:center;margin-bottom:20px">
    <h1 style="color:#f5b301;margin:0;font-size:24px">MediCar Plus</h1>
    <p style="color:#666;margin:4px 0 0 0;font-size:12px">Software profesional de gestión de caja</p>
  </div>
  <h2 style="color:#111;font-size:18px">Hola{(' ' + client_name) if client_name else ''},</h2>
  <p style="line-height:1.6">Aquí tienes de nuevo el instalador de <b>MediCar Plus</b> para reinstalar el programa en tu ordenador.</p>
  <div style="background:#fff8e1;border-left:4px solid #f5b301;padding:14px;margin:18px 0;border-radius:4px">
    <p style="margin:0;font-size:14px"><b>📥 Descargar instalador:</b></p>
    <p style="margin:8px 0 0 0"><a href="{download_url}" style="display:inline-block;background:#f5b301;color:#0b1121;padding:10px 22px;border-radius:6px;text-decoration:none;font-weight:700">Descargar MediCar Plus</a></p>
    <p style="margin:10px 0 0 0;font-size:11px;color:#666">Enlace directo: <a href="{download_url}" style="color:#666">{download_url}</a></p>
  </div>
  <h3 style="color:#111;font-size:15px;margin-top:24px">🔑 Tus datos de activación</h3>
  <table style="width:100%;border-collapse:collapse;background:#f8f9fa;border-radius:6px;overflow:hidden">
    <tr><td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-weight:700;font-size:13px;color:#666">Install ID</td><td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-family:monospace;font-size:13px">{install_id or '(vinculado a tu ordenador anterior)'}</td></tr>
    <tr><td style="padding:10px 14px;font-weight:700;font-size:13px;color:#666">Clave de licencia</td><td style="padding:10px 14px;font-family:monospace;font-size:13px;color:#f5b301;font-weight:700">{license_key}</td></tr>
  </table>
  <h3 style="color:#111;font-size:15px;margin-top:24px">📋 Cómo reinstalar</h3>
  <ol style="line-height:1.8;color:#333">
    <li>Descarga el instalador desde el botón de arriba</li>
    <li>Ejecuta el archivo <b>MediCarPlus-Setup.exe</b> (Windows) y sigue las instrucciones</li>
    <li>Abre el programa e introduce tu <b>Install ID</b> y <b>Clave de licencia</b></li>
    <li>Si es el mismo ordenador donde ya tenías el programa, se reactivará automáticamente sin gastar activaciones</li>
  </ol>
  <div style="background:#e0f2fe;border-left:4px solid #0284c7;padding:12px;margin:18px 0;border-radius:4px;font-size:13px">
    <b>⚠️ Importante:</b> La licencia está vinculada a tu ordenador (HWID). Si intentas activarla en otro equipo distinto, contacta con nosotros antes en <a href="mailto:info@medicarplus.es">info@medicarplus.es</a> para transferirla.
  </div>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0" />
  <p style="font-size:11px;color:#999;text-align:center">¿Dudas? Escríbenos a <a href="mailto:info@medicarplus.es" style="color:#f5b301">info@medicarplus.es</a><br />MediCar Plus · <a href="https://medicarplus.es" style="color:#666">medicarplus.es</a></p>
</div></body></html>"""


def build_downloads_router(db):
    router = APIRouter(prefix="/admin/licenses", tags=["admin-downloads"])

    @router.post("/{license_key}/resend-download")
    async def resend_download(
        license_key: str,
        body: ResendDownloadBody,
        x_admin_token: Optional[str] = Header(None),
    ):
        """Reenvía el instalador de MediCar Plus al email del cliente (o al override)."""
        _admin_ok(x_admin_token)
        if not _smtp_configured():
            raise HTTPException(status_code=503, detail="smtp_not_configured")

        # Buscar la licencia por license_key o jti
        lic = await db.licenses.find_one({"$or": [{"license_key": license_key}, {"jti": license_key}]})
        if not lic:
            raise HTTPException(status_code=404, detail="license_not_found")

        client_email = (body.override_email or lic.get("client_email") or "").strip()
        if not client_email:
            raise HTTPException(status_code=400, detail="client_email_missing")

        client_name = (lic.get("client_name") or lic.get("centre") or "").strip()
        install_id = (lic.get("install_id") or "").strip()
        real_license_key = (lic.get("license_key") or license_key).strip()

        subject = "MediCar Plus · Aquí tienes tu instalador"
        html = _build_email_html(client_name, real_license_key, install_id, _download_url())

        ok, info = _send_smtp(client_email, subject, html)
        if not ok:
            logger.error("Failed to resend download for %s: %s", license_key, info)
            raise HTTPException(status_code=500, detail=f"send_failed:{info}")

        return {"ok": True, "sent_to": client_email, "license_key": real_license_key, "download_url": _download_url()}

    return router
