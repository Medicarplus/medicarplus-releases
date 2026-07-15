"""Contador atómico de números de documento.

Genera referencias correlativas para los PDFs de licencia (portada).
Format: `MCP-{year}-{seq:06d}` → `MCP-2026-000042`.

⚠️ IMPORTANT: NO és una factura fiscal. La factura legal l'emet Stripe/Verifacti.
Aquest número és només una referència interna d'emissió del document.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

_client: Optional[AsyncIOMotorClient] = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        _db = _client[os.environ["DB_NAME"]]
    return _db


async def next_doc_number() -> str:
    """Retorna el següent número correlatiu (thread-safe via `$inc` atòmic).

    Reset per any: cada 1 de gener comença per 000001.
    """
    year = datetime.now(timezone.utc).year
    counter_id = f"license_docs_{year}"
    try:
        db = _get_db()
        doc = await db.emission_counters.find_one_and_update(
            {"_id": counter_id},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=True,  # after update
        )
        # find_one_and_update in motor returns the doc after upsert insert with seq=1
        seq = int(doc.get("seq", 1)) if doc else 1
    except Exception as ex:  # noqa: BLE001
        logger.exception("next_doc_number failed, using timestamp fallback: %s", ex)
        seq = int(datetime.now(timezone.utc).timestamp()) % 1000000
    return f"MCP-{year}-{seq:06d}"
