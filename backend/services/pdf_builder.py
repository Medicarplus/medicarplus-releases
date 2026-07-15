"""HTML → PDF converter + portada personalitzada per client.

- `html_to_pdf(path)`: converteix un HTML a PDF (amb cache per mtime).
- `render_cover_pdf(...)`: genera una portada A4 amb branding MediCar Plus i dades del client.
- `build_client_pdf(doc_kind, ...)`: retorna els bytes d'un PDF final = portada + cos (cos cacheat).

Usa Playwright Chromium per la conversió i pypdf per l'unió.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)

CACHE_DIR = Path("/tmp/medicar_pdfs")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ── Utilitats bàsiques ──────────────────────────────────────────────────────
async def _print_pdf_from_html_content(html: str) -> bytes:
    """Renderitza un string HTML i retorna els bytes del PDF (A4)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html, wait_until="load")
        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
        )
        await browser.close()
    return pdf_bytes


async def _print_pdf_from_file(html_path: Path) -> bytes:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=15000)
        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "16mm", "right": "12mm", "bottom": "16mm", "left": "12mm"},
        )
        await browser.close()
    return pdf_bytes


async def html_to_pdf(html_path: str) -> Optional[bytes]:
    """Converteix un HTML a PDF amb cache per mtime. Retorna bytes o None si falla."""
    src = Path(html_path)
    if not src.exists():
        logger.warning("html_to_pdf: source not found: %s", html_path)
        return None

    cache_file = CACHE_DIR / (src.stem + ".pdf")
    if cache_file.exists() and cache_file.stat().st_mtime >= src.stat().st_mtime:
        try:
            return cache_file.read_bytes()
        except Exception:  # noqa: BLE001
            pass

    try:
        pdf_bytes = await _print_pdf_from_file(src)
        try:
            cache_file.write_bytes(pdf_bytes)
        except Exception:  # noqa: BLE001
            pass
        return pdf_bytes
    except Exception as ex:  # noqa: BLE001
        logger.exception("html_to_pdf failed for %s: %s", html_path, ex)
        return None


# ── Portada branded ─────────────────────────────────────────────────────────
def _cover_html(
    *,
    doc_title: str,
    doc_subtitle: str,
    client_name: str,
    install_id: str,
    plan: str,
    expires_at: Optional[datetime],
    license_key: str,
) -> str:
    expiry_txt = expires_at.strftime("%d/%m/%Y") if expires_at else "Perpetua (sin caducidad)"
    today = datetime.now().strftime("%d/%m/%Y")
    # Trunquem la clau perquè no ocupi 5 línies
    key_preview = license_key if len(license_key) <= 80 else license_key[:60] + "…" + license_key[-16:]

    return f"""<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>{doc_title}</title>
<style>
  @page {{ size: A4; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0; padding: 0;
    font-family: Georgia, 'Times New Roman', serif;
    color: #e2e8f0;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}
  .page {{
    width: 210mm; height: 297mm;
    background: linear-gradient(160deg, #0b1120 0%, #0f172a 50%, #1e293b 100%);
    position: relative;
    padding: 22mm 20mm;
    display: flex; flex-direction: column;
  }}
  .top-band {{
    position: absolute; top: 0; left: 0; right: 0; height: 8mm;
    background: linear-gradient(90deg, #f5b301 0%, #d97706 100%);
  }}
  .bottom-band {{
    position: absolute; bottom: 0; left: 0; right: 0; height: 8mm;
    background: linear-gradient(90deg, #d97706 0%, #f5b301 100%);
  }}
  .brand {{
    display: flex; align-items: center; gap: 14px;
    margin-top: 4mm;
  }}
  .logo {{
    width: 60px; height: 60px; border-radius: 12px;
    background: linear-gradient(135deg, #f5b301 0%, #d97706 100%);
    display: flex; align-items: center; justify-content: center;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 28px; font-weight: 900; color: #0f172a;
    box-shadow: 0 6px 20px rgba(245,179,1,.35);
    letter-spacing: -1px;
  }}
  .brand-txt {{
    font-family: 'Segoe UI', Arial, sans-serif;
  }}
  .brand-name {{
    font-size: 22px; font-weight: 800; color: #f5b301; letter-spacing: 2px;
    line-height: 1;
  }}
  .brand-tag {{
    font-size: 11px; color: #94a3b8; margin-top: 4px; letter-spacing: 1px;
  }}
  .hero {{
    margin-top: 32mm; padding-bottom: 8mm;
    border-bottom: 1px solid rgba(245,179,1,.25);
  }}
  .doc-label {{
    display: inline-block;
    background: rgba(245,179,1,.12);
    border: 1px solid rgba(245,179,1,.45);
    color: #f5b301;
    padding: 5px 14px; border-radius: 999px;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 11px; font-weight: 700; letter-spacing: 2px;
  }}
  h1 {{
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 42px; font-weight: 800;
    color: #f8fafc;
    margin: 14px 0 8px 0;
    line-height: 1.1;
    letter-spacing: -0.5px;
  }}
  h1 span {{ color: #f5b301; }}
  .subtitle {{
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 14px; color: #94a3b8;
    line-height: 1.5;
    max-width: 140mm;
  }}
  .client-card {{
    margin-top: 14mm;
    background: rgba(15,23,42,.7);
    border: 1px solid rgba(245,179,1,.3);
    border-radius: 14px;
    padding: 8mm 9mm;
    font-family: 'Segoe UI', Arial, sans-serif;
  }}
  .card-title {{
    color: #f5b301;
    font-size: 10px; font-weight: 800; letter-spacing: 2.5px;
    margin: 0 0 6mm 0;
  }}
  .row {{
    display: flex; align-items: baseline;
    padding: 3.5mm 0;
    border-bottom: 1px dashed rgba(148,163,184,.2);
  }}
  .row:last-of-type {{ border-bottom: none; }}
  .label {{
    width: 42mm; color: #64748b;
    font-size: 11px; letter-spacing: 1px;
    text-transform: uppercase; font-weight: 600;
  }}
  .value {{
    flex: 1; color: #f8fafc;
    font-size: 14px; font-weight: 600;
    word-break: break-word;
  }}
  .value.mono {{
    font-family: 'Courier New', monospace;
    font-size: 11px;
    color: #cbd5e1;
    letter-spacing: 0.3px;
  }}
  .footer {{
    margin-top: auto;
    display: flex; justify-content: space-between; align-items: flex-end;
    font-family: 'Segoe UI', Arial, sans-serif;
    color: #64748b; font-size: 10px;
    letter-spacing: 0.5px;
    padding-bottom: 2mm;
  }}
  .footer-left b {{ color: #94a3b8; letter-spacing: 1.5px; }}
  .footer-right {{ text-align: right; }}
  .accent-line {{
    display: block; width: 40mm; height: 3px;
    background: linear-gradient(90deg, #f5b301, transparent);
    margin: 10mm 0 4mm 0;
  }}
</style></head>
<body>
  <div class="page">
    <div class="top-band"></div>
    <div class="bottom-band"></div>

    <div class="brand">
      <div class="logo">M+</div>
      <div class="brand-txt">
        <div class="brand-name">MEDICAR PLUS</div>
        <div class="brand-tag">Software · Marc Brugulat Lopez</div>
      </div>
    </div>

    <div class="hero">
      <span class="doc-label">DOCUMENTACIÓN OFICIAL</span>
      <h1>{doc_title.split(' ')[0]} <span>{' '.join(doc_title.split(' ')[1:]) or ''}</span></h1>
      <div class="subtitle">{doc_subtitle}</div>
      <span class="accent-line"></span>
    </div>

    <div class="client-card">
      <div class="card-title">EMITIDO PARA</div>
      <div class="row"><div class="label">Cliente</div><div class="value">{client_name}</div></div>
      <div class="row"><div class="label">Plan</div><div class="value">{plan}</div></div>
      <div class="row"><div class="label">Caducidad</div><div class="value">{expiry_txt}</div></div>
      <div class="row"><div class="label">Install ID</div><div class="value mono">{install_id}</div></div>
      <div class="row"><div class="label">Clave</div><div class="value mono">{key_preview}</div></div>
    </div>

    <div class="footer">
      <div class="footer-left">
        <b>MEDICARPLUS.ES</b><br>
        info@medicarplus.es
      </div>
      <div class="footer-right">
        Documento emitido el {today}<br>
        © MediCar Plus · Todos los derechos reservados
      </div>
    </div>
  </div>
</body></html>"""


# ── PDF final = portada + cos ───────────────────────────────────────────────
async def build_client_pdf(
    *,
    doc_kind: str,  # "guia" o "manual"
    body_html_path: str,
    doc_title: str,
    doc_subtitle: str,
    client_name: str,
    install_id: str,
    plan: str,
    expires_at: Optional[datetime],
    license_key: str,
) -> Optional[bytes]:
    """Genera un PDF personalitzat = portada (per client) + cos (cacheat).

    Retorna els bytes del PDF combinat o None si falla.
    """
    try:
        body_pdf = await html_to_pdf(body_html_path)
        if not body_pdf:
            return None

        cover_html = _cover_html(
            doc_title=doc_title,
            doc_subtitle=doc_subtitle,
            client_name=client_name,
            install_id=install_id,
            plan=plan,
            expires_at=expires_at,
            license_key=license_key,
        )
        cover_pdf = await _print_pdf_from_html_content(cover_html)

        writer = PdfWriter()
        for src_bytes in (cover_pdf, body_pdf):
            reader = PdfReader(io.BytesIO(src_bytes))
            for page in reader.pages:
                writer.add_page(page)

        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
    except Exception as ex:  # noqa: BLE001
        logger.exception("build_client_pdf failed (%s): %s", doc_kind, ex)
        return None
