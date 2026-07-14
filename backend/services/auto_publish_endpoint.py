"""
auto_publish_endpoint.py
────────────────────────
En arrencar el backend, comprova quina URL de preview està usant Emergent
(env var `preview_endpoint`) i la publica automàticament al fitxer
`api-endpoint.json` del repo GitHub Pages `Medicarplus/medicarplus.es`.

Això fa que si Emergent roti la URL, l'app Electron dels clients es reajusti
sola en < 24h sense cap intervenció manual del propietari.

- Compara la URL actual amb la que ja hi ha al repo
- Si són diferents, commit + push
- Si són iguals, no fa res
- Silenciós als errors (no ha de trencar l'arrencada del backend)
"""
from __future__ import annotations
import os
import json
import base64
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

log = logging.getLogger(__name__)

REPO_OWNER = "Medicarplus"
REPO_NAME = "medicarplus-releases"  # PAT té write access aquí (no a medicarplus.es)
FILE_PATH = "api-endpoint.json"
GITHUB_API = "https://api.github.com"


def _current_preview_url() -> Optional[str]:
    """Retorna la URL actual del backend segons env vars d'Emergent.
    
    Ordre de prioritat:
    1) `preview_endpoint` (nom oficial d'Emergent, minúscules)
    2) `PREVIEW_ENDPOINT` (variant en majúscules)
    3) `APP_URL` (UUID estable per contenidor, disponible al procés)
    """
    for key in ("preview_endpoint", "PREVIEW_ENDPOINT", "APP_URL"):
        url = (os.environ.get(key) or "").strip()
        if url and url.startswith("http"):
            return url.rstrip("/")
    return None


async def _get_current_file(token: str) -> tuple[Optional[dict], Optional[str]]:
    """Retorna (contingut_dict, sha) del fitxer al repo, o (None, None) si no existeix."""
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.get(url, headers=headers)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        data = r.json()
        try:
            content_b64 = (data.get("content") or "").replace("\n", "")
            content = json.loads(base64.b64decode(content_b64).decode("utf-8"))
        except Exception:
            content = None
        return content, data.get("sha")


async def _put_file(token: str, new_content: dict, sha: Optional[str]) -> bool:
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    encoded = base64.b64encode(json.dumps(new_content, indent=2).encode("utf-8")).decode("ascii")
    payload = {
        "message": f"auto: update api-endpoint.json → {new_content.get('api')}",
        "content": encoded,
        "committer": {"name": "MediCar Plus Bot", "email": "bot@medicarplus.es"},
    }
    if sha:
        payload["sha"] = sha
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.put(url, headers=headers, json=payload)
        if r.status_code in (200, 201):
            return True
        log.warning("api-endpoint auto-publish failed: %s %s", r.status_code, r.text[:200])
        return False


async def auto_publish_endpoint_url() -> None:
    """Punt d'entrada · s'invoca al startup del backend."""
    try:
        token = (os.environ.get("GITHUB_TOKEN") or "").strip()
        current_url = _current_preview_url()
        if not token or not current_url:
            log.info("auto-publish skipped (missing GITHUB_TOKEN or preview_endpoint)")
            return

        existing, sha = await _get_current_file(token)
        if existing and existing.get("api", "").rstrip("/") == current_url:
            log.info("api-endpoint.json already up to date (%s)", current_url)
            return

        new_content = {
            "api": current_url,
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
            "notes": "Auto-publicat pel backend al arrencar. NO EDITAR MANUALMENT.",
        }
        ok = await _put_file(token, new_content, sha)
        if ok:
            log.info("api-endpoint.json auto-published → %s", current_url)
        else:
            log.warning("api-endpoint.json auto-publish returned failure")
    except Exception as e:
        # Silent — mai ha de trencar l'arrencada del backend
        log.exception("auto_publish_endpoint_url failed: %s", e)
