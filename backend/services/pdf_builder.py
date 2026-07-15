"""HTML → PDF converter usant Playwright Chromium.

Genera PDFs a partir dels arxius HTML de guia/manual per adjuntar-los al correu
de llicència. Cache basat en mtime: si l'HTML no ha canviat, reutilitza el PDF
generat prèviament (evita cost d'obrir Chromium a cada correu).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

CACHE_DIR = Path("/tmp/medicar_pdfs")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


async def html_to_pdf(html_path: str) -> bytes | None:
    """Converteix un HTML a PDF. Retorna els bytes o None si falla.

    Usa cache: si el PDF ja existeix i és més recent que l'HTML, el reutilitza.
    """
    src = Path(html_path)
    if not src.exists():
        logger.warning("html_to_pdf: source not found: %s", html_path)
        return None

    cache_file = CACHE_DIR / (src.stem + ".pdf")
    if cache_file.exists() and cache_file.stat().st_mtime >= src.stat().st_mtime:
        try:
            return cache_file.read_bytes()
        except Exception:  # noqa: BLE001
            pass  # regenerem

    try:
        file_url = src.resolve().as_uri()
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(file_url, wait_until="load", timeout=15000)
            pdf_bytes = await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "16mm", "right": "12mm", "bottom": "16mm", "left": "12mm"},
            )
            await browser.close()
        try:
            cache_file.write_bytes(pdf_bytes)
        except Exception:  # noqa: BLE001
            pass
        return pdf_bytes
    except Exception as ex:  # noqa: BLE001
        logger.exception("html_to_pdf failed for %s: %s", html_path, ex)
        return None
