"""
POST /api/pdf/render
--------------------
Rep un HTML sencer (amb els seus estils inline / @page) i el retorna com a PDF A4
generat amb Playwright. Manté fidelitat WYSIWYG: el que envies és el que descarregues.

Body JSON:
    {
      "html": "<!doctype html>...",   // OBLIGATORI
      "filename": "informe.pdf",       // opcional
      "landscape": false               // opcional (només s'usa si el HTML no defineix @page)
    }
"""
from __future__ import annotations

import logging
import re
import urllib.parse

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from services.pdf_builder import render_html_to_pdf_bytes

logger = logging.getLogger(__name__)
router = APIRouter()


class RenderRequest(BaseModel):
    html: str = Field(..., min_length=20, max_length=10_000_000)
    filename: str | None = None
    landscape: bool = False


def _safe_filename(name: str) -> str:
    name = (name or "").strip() or "documento.pdf"
    # Elimina caràcters de path i control
    name = re.sub(r"[\\/\r\n\t]+", " ", name).strip()
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return name[:180]


@router.post("/pdf/render")
async def render_pdf(payload: RenderRequest):
    try:
        pdf_bytes = await render_html_to_pdf_bytes(
            payload.html,
            landscape=payload.landscape,
        )
    except Exception as ex:  # noqa: BLE001
        logger.exception("PDF render failed: %s", ex)
        raise HTTPException(status_code=500, detail="pdf_render_failed")

    filename = _safe_filename(payload.filename or "documento.pdf")
    # RFC 5987 per suportar accents/espais
    quoted = urllib.parse.quote(filename, safe="")
    disposition = f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quoted}"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": disposition,
            "Cache-Control": "no-store",
        },
    )
