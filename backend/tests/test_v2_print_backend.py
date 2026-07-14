"""Backend regression tests for MediCar Plus v2.1.0 print-flow fix.

Covers:
  - /api/           health
  - /api/calendar/fetch  Spain holidays (POST)
  - /api/sms/campaigns   401 without admin token (public shape check)
  - /api/electron/download/index.html   serves v2.html WITH printHtml
"""
import os
import re
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


@pytest.fixture(scope="module")
def s():
    return requests.Session()


# ---------- Health ----------
def test_health_root_returns_200(s):
    r = s.get(f"{BASE_URL}/api/", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    # Server returns a minimal {"message": "Hello World"} — MediCar Plus branding
    # lives in the SPA (v2.html), so just verify the health endpoint is up.
    assert "message" in body


# ---------- Calendar sync (Spain holidays via Google) ----------
def test_calendar_fetch_spain_holidays(s):
    payload = {
        "urls": [
            "https://calendar.google.com/calendar/ical/es.spain%23holiday%40group.v.calendar.google.com/public/basic.ics"
        ],
        "date_from": "2026-01-01",
        "date_to": "2026-01-31",
    }
    r = s.post(f"{BASE_URL}/api/calendar/fetch", json=payload, timeout=30)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert "events" in data
    assert isinstance(data["events"], list)
    # January 2026 has at least Jan 1 (New Year) — Spain holiday feed should include it
    dates = [e.get("date") for e in data["events"]]
    assert any(d and d.startswith("2026-01") for d in dates), f"No Jan-2026 events: {dates[:5]}"


def test_calendar_fetch_invalid_range_rejected(s):
    r = s.post(
        f"{BASE_URL}/api/calendar/fetch",
        json={"urls": ["https://example.com/a.ics"], "date_from": "2026-05-01", "date_to": "2026-01-01"},
        timeout=15,
    )
    assert r.status_code == 400


# ---------- SMS campaigns list requires admin token ----------
def test_sms_campaigns_list_requires_admin(s):
    r = s.get(f"{BASE_URL}/api/sms/campaigns", timeout=15)
    # Public: 401 unauthorized (expected — endpoint exists and is guarded)
    assert r.status_code == 401
    body = r.json()
    assert body.get("detail") == "unauthorized"


def test_sms_campaigns_list_with_admin_if_available(s):
    """If LICENSE_ADMIN_TOKEN is set locally, verify authenticated list works."""
    token = os.environ.get("LICENSE_ADMIN_TOKEN", "")
    if not token:
        pytest.skip("LICENSE_ADMIN_TOKEN not set in env")
    r = s.get(f"{BASE_URL}/api/sms/campaigns", headers={"X-Admin-Token": token}, timeout=15)
    assert r.status_code == 200
    body = r.json()
    # Endpoint returns either a bare list or {campaigns:[...], count:N} envelope
    if isinstance(body, dict):
        assert "campaigns" in body and isinstance(body["campaigns"], list)
    else:
        assert isinstance(body, list)


# ---------- Electron download serves v2.html with printHtml() ----------
def test_electron_download_index_html_contains_printHtml(s):
    r = s.get(f"{BASE_URL}/api/electron/download/index.html", timeout=30)
    assert r.status_code == 200
    body = r.text
    # Must contain the new helper function
    assert "function printHtml" in body, "printHtml() function missing from served v2.html"
    # Must NOT still CALL window.open('','_blank') in code — only in comments/strings
    # v2.1.7: the code no longer invokes window.open; there may be 2 references
    # (one in a JS comment at ~line 604, one inside a what's-new string ~line 4895).
    # Neither is an actual call.
    for line in body.splitlines():
        if "window.open(" in line:
            stripped = line.strip()
            # Allow comment lines and string literals in what's-new content
            is_comment = stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*")
            is_string = ("'window.open" in line) or ('"window.open' in line) or ("<code>window.open" in line)
            assert is_comment or is_string, f"Actual window.open call found: {line[:120]}"


def test_electron_download_index_html_all_print_handlers_use_printVisibleElement(s):
    r = s.get(f"{BASE_URL}/api/electron/download/index.html", timeout=30)
    body = r.text
    # v2.1.7: handlers now use printVisibleElement(el, opts) which internally
    # calls printHtml(). We expect at least 4 printVisibleElement call sites
    # (IRPF, Libro Registro, Estadísticas, Llibreta) plus its definition.
    pve = body.count("printVisibleElement(")
    assert pve >= 5, f"Expected >=5 printVisibleElement occurrences, got {pve}"
    # printHtml is still the internal helper — >=2 (def + at least 1 caller)
    ph = body.count("printHtml(")
    assert ph >= 2, f"Expected >=2 printHtml occurrences, got {ph}"
    # Iframe marker used for tests
    assert "data-print-frame" in body
    # New PDF button
    assert "Guardar PDF" in body, "'Guardar PDF' button missing from print preview modal"
