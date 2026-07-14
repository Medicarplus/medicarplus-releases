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
    # Must NOT still call window.open('','_blank') in code — only in comment
    occurrences = re.findall(r"window\.open", body)
    # We allow at most 1 occurrence which must be in the explanatory comment
    assert len(occurrences) <= 1, f"Too many window.open occurrences: {len(occurrences)}"
    # Find the line and verify it's a comment
    for line in body.splitlines():
        if "window.open" in line:
            assert line.strip().startswith("//"), f"window.open is not in a comment: {line[:100]}"


def test_electron_download_index_html_all_print_handlers_use_printHtml(s):
    r = s.get(f"{BASE_URL}/api/electron/download/index.html", timeout=30)
    body = r.text
    # All 6 print handlers should call printHtml(
    count = body.count("printHtml(")
    # 1 definition + 6 call sites minimum
    assert count >= 7, f"Expected >=7 printHtml occurrences (1 def + 6 handlers), got {count}"
    # Iframe marker used for tests
    assert "data-print-frame" in body
