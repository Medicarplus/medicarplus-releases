"""Redirect endpoint · Descarga directa del último instalador MediCar Plus.

El cliente NO ve la página de GitHub Releases (que muestra 3 assets confusos).
Recibe una descarga directa del `.exe` correcto.

GET /api/download/latest-installer → HTTP 302 al último `MediCar-Plus-Setup-*.exe`
GET /api/download/latest-portable  → HTTP 302 al último `MediCarPlus-Portable-*.exe` (opcional)

Si falla (GitHub down, no releases todavía, red rara) → fallback al link tradicional
`https://github.com/Medicarplus/medicarplus-releases/releases/latest` como safety net.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

GITHUB_API_LATEST = "https://api.github.com/repos/Medicarplus/medicarplus-releases/releases/latest"
GITHUB_RELEASES_FALLBACK = "https://github.com/Medicarplus/medicarplus-releases/releases/latest"

# Cache in-process: evita golpear la API de GitHub en cada descarga
# (rate limit anónimo: 60 req/h por IP). TTL 15 min.
_cache: dict = {"expires_at": 0.0, "installer_url": None, "portable_url": None}
_CACHE_TTL = 15 * 60  # 15 min


async def _resolve_asset_urls() -> tuple[Optional[str], Optional[str]]:
    """Consulta GitHub y devuelve (installer_url, portable_url) del último release."""
    now = time.time()
    if _cache["expires_at"] > now and _cache["installer_url"]:
        return _cache["installer_url"], _cache["portable_url"]

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(GITHUB_API_LATEST, headers={"Accept": "application/vnd.github+json"})
            if r.status_code != 200:
                logger.warning("GitHub API returned %s", r.status_code)
                return None, None
            data = r.json()
    except Exception as ex:
        logger.warning("Could not fetch GitHub latest release: %s", ex)
        return None, None

    installer = None
    portable = None
    for asset in data.get("assets", []):
        name = str(asset.get("name") or "")
        url = asset.get("browser_download_url")
        if not url:
            continue
        if name.startswith("MediCar-Plus-Setup-") and name.endswith(".exe"):
            installer = url
        elif name.startswith("MediCarPlus-Portable-") and name.endswith(".exe"):
            portable = url

    _cache["expires_at"] = now + _CACHE_TTL
    _cache["installer_url"] = installer
    _cache["portable_url"] = portable
    return installer, portable


router = APIRouter(prefix="/download", tags=["download"])


@router.get("/latest-installer")
async def latest_installer():
    """HTTP 302 al último instalador (Setup) de Windows.

    Si la API de GitHub falla, redirige a la página de Releases para no romper el flujo.
    """
    installer, _ = await _resolve_asset_urls()
    if installer:
        return RedirectResponse(url=installer, status_code=302)
    # Fallback: página de Releases (mismo comportamiento anterior)
    return RedirectResponse(url=GITHUB_RELEASES_FALLBACK, status_code=302)


@router.get("/latest-portable")
async def latest_portable():
    """HTTP 302 al último ejecutable portable (sin instalador)."""
    _, portable = await _resolve_asset_urls()
    if portable:
        return RedirectResponse(url=portable, status_code=302)
    return RedirectResponse(url=GITHUB_RELEASES_FALLBACK, status_code=302)


@router.get("/latest-info")
async def latest_info():
    """JSON con los URLs resueltos (útil para debug y para que el frontend
    pueda mostrar el nombre real del archivo si algún día lo quiere)."""
    installer, portable = await _resolve_asset_urls()
    return {
        "installer_url": installer,
        "portable_url": portable,
        "fallback_url": GITHUB_RELEASES_FALLBACK,
        "cache_expires_in_sec": max(0, int(_cache["expires_at"] - time.time())),
    }
