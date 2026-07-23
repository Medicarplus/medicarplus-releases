"""
Discord push notifications · Notificacions instantànies al mòbil del propietari.
Usa Discord Webhooks (sense bot, sense OAuth · només una URL).

Configuració (backend/.env):
    DISCORD_WEBHOOK_URL  →  URL del webhook de Discord

Com obtenir-la (5 minuts):
    1. Obre Discord (mòbil o desktop).
    2. Crea (o entra a) un servidor personal (no cal que sigui públic; pot ser només teu).
    3. Fes clic dret sobre un canal (ex: #general) → Editar canal → Integracions → Webhooks.
    4. Nou webhook → tria nom (ex: "MediCar Plus") + icona opcional → Copia URL del webhook.
    5. Enganxa la URL a DISCORD_WEBHOOK_URL al backend/.env.
    6. Instal·la l'app Discord al teu mòbil i activa les notificacions push del servidor.

Format d'un missatge (Discord Embed):
    {
        "title": "🖥️ Assistència remota",
        "description": "Text principal amb **negreta** i *cursiva*",
        "color": 0xf5b301,  # daurat (RGB hex sense #)
        "fields": [{"name":"Camp","value":"Valor","inline":True}, ...],
        "timestamp": "ISO 8601 datetime",
    }
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import httpx

logger = logging.getLogger(__name__)


def _webhook_url() -> Optional[str]:
    url = (os.environ.get("DISCORD_WEBHOOK_URL") or "").strip()
    if not url or not url.startswith("https://"):
        return None
    return url


def is_configured() -> bool:
    return _webhook_url() is not None


# Colors útils (RGB decimals) — Discord no admet HTML color codes, cal enter
COLOR_REMOTE_ASSIST = 0xf5b301   # daurat (urgent)
COLOR_BUG = 0xef4444             # vermell
COLOR_QUESTION = 0x3b82f6        # blau
COLOR_BILLING = 0x22c55e         # verd
COLOR_GENERAL = 0x94a3b8         # gris


async def send_discord_notification(
    *,
    title: str,
    description: str = "",
    color: int = 0xf5b301,
    fields: Optional[List[Dict[str, Any]]] = None,
    footer_text: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """Envia una notificació estructurada (embed) al Discord configurat.
    Retorna (ok, error_msg).
    Camps Discord suporta markdown: **bold**, *italic*, `code`, ```block```, > quote.
    """
    url = _webhook_url()
    if not url:
        return False, "DISCORD_WEBHOOK_URL no configurat"

    embed: Dict[str, Any] = {
        "title": title[:256],
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if description:
        embed["description"] = description[:4000]
    if fields:
        embed["fields"] = [
            {"name": str(f.get("name", ""))[:256],
             "value": str(f.get("value", ""))[:1024],
             "inline": bool(f.get("inline", False))}
            for f in fields[:25]
        ]
    if footer_text:
        embed["footer"] = {"text": footer_text[:2048]}

    payload = {"embeds": [embed]}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json=payload)
            if 200 <= r.status_code < 300:
                return True, None
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        logger.warning(f"Discord send failed: {e}")
        return False, str(e)
