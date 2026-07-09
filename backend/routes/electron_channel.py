"""
Electron update channel — KILL SWITCH remot.
--------------------------------------------
Cada client Electron consulta aquest endpoint ABANS d'auto-actualitzar-se.
Si una versió està bloquejada aquí, el client NO l'instal·larà encara que
estigui publicada a GitHub Releases. Això et dóna una palanca d'emergència
per rescatar tots els clients si publiques una versió dolenta per error.

Configuració: /app/backend/electron_channel.json (editable en calent).
  {
    "latest_safe_version": "2.0.21",  // versió màxima que els clients poden instal·lar
    "blocked_versions": ["2.0.19"],   // versions específiques bloquejades
    "min_client_version": "2.0.0",    // versions inferiors reben avís urgent
    "message": "..."                  // missatge opcional per als clients
  }

Si el fitxer no existeix, no es bloqueja res (comportament per defecte segur).
"""
from fastapi import APIRouter
from pathlib import Path
import json
from datetime import datetime, timezone

CONFIG_FILE = Path(__file__).resolve().parent.parent / "electron_channel.json"

DEFAULT_CONFIG = {
    "latest_safe_version": None,   # None = permet qualsevol
    "blocked_versions": [],
    "min_client_version": "2.0.0",
    "message": "",
    "rollback_to": None,           # si s'informa, els clients seran empesos a instal·lar aquesta versió
}

router = APIRouter()


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg


@router.get("/electron/update-channel")
async def update_channel(current_version: str | None = None):
    cfg = load_config()
    resp = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "latest_safe_version": cfg["latest_safe_version"],
        "blocked_versions": cfg["blocked_versions"],
        "min_client_version": cfg["min_client_version"],
        "message": cfg["message"],
        "rollback_to": cfg["rollback_to"],
        "action": "ok",  # ok | block-update | force-rollback | urgent-message
    }
    if current_version:
        if current_version in cfg["blocked_versions"]:
            resp["action"] = "force-rollback"
            resp["message"] = resp["message"] or (
                f"La versió {current_version} té un problema conegut. "
                "Es recomana instal·lar l'última versió estable."
            )
        elif cfg["message"]:
            resp["action"] = "urgent-message"
    return resp
