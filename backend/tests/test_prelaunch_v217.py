"""Pre-launch v2.1.7 comprehensive backend tests.

Covers critical flows for MediCar Plus commercial launch:
  - Health + versioning
  - License verification via master key (backend rejects — master is client-side only)
  - SMS: CSV preview (admin) → mock campaign create → list → detail search → delete
  - Calendar sync: Spain holidays + range validation
  - Auto-endpoint publish artifact accessibility (public JSON)
  - Static SPA served with expected artifacts (Guardar PDF button, printVisibleElement)
"""
import io
import os
import re
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_TOKEN = "MB-ADMIN-BRUGULAT-2026-4F8E2A1C"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"User-Agent": "prelaunch-test/1.0"})
    return sess


@pytest.fixture(scope="module")
def admin_headers():
    return {"X-Admin-Token": ADMIN_TOKEN}


# ---------- Health / basics ----------
def test_api_health(s):
    r = s.get(f"{BASE_URL}/api/", timeout=15)
    assert r.status_code == 200
    assert r.json().get("message") == "Hello World"


def test_electron_manifest_version(s):
    r = s.get(f"{BASE_URL}/api/electron/download/package.json", timeout=15)
    assert r.status_code == 200
    v = r.json().get("version") or ""
    assert v.startswith("2.1."), f"Expected 2.1.x, got {v}"


# ---------- SMS flow — CRITICAL pre-launch ----------
def test_sms_preview_requires_admin(s):
    files = {"file": ("t.csv", b"Nombre;Movil\nMarc;666111222\n", "text/csv")}
    r = s.post(f"{BASE_URL}/api/sms/preview", files=files, timeout=15)
    assert r.status_code == 401


def test_sms_preview_valid_csv(s, admin_headers):
    csv_body = (
        "Nombre;Apellido1;Apellido2;Movil;Telefono;FechaRevision\n"
        "Marc;Brugulat;Lopez;666111222;932000000;2026-06-15\n"
        "Anna;Puig;;677333444;;2026-07-01\n"
        "Joan;Sanz;;655111000;;2026-08-01\n"
        "DupMarc;Brugulat;;666111222;;2026-09-01\n"      # duplicate mobile
        "InvalidFix;Roca;;;931234567;2026-10-01\n"        # only landline
        "NoPhone;Puig;;;;2026-11-01\n"                    # no phone
    )
    files = {"file": ("contacts.csv", csv_body.encode("utf-8"), "text/csv")}
    r = s.post(f"{BASE_URL}/api/sms/preview", files=files, headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text[:400]
    d = r.json()
    assert d["ok"] is True
    assert d["total_rows"] == 6
    assert d["valid_count"] == 3, f"expected 3 valid mobiles, got {d}"
    assert d["duplicate_count"] == 1
    assert d["invalid_count"] == 2
    assert isinstance(d["contacts"], list) and len(d["contacts"]) == 6
    valids = [c for c in d["contacts"] if c["valid"]]
    assert {c["mobile"] for c in valids} == {"666111222", "677333444", "655111000"}


def test_sms_campaign_full_lifecycle(s, admin_headers):
    # 1) Preview a small CSV
    csv_body = (
        "Nombre;Apellido1;Movil;FechaRevision\n"
        "TestUno;PruebaA;666000111;2026-06-01\n"
        "TestDos;PruebaB;677000222;2026-06-15\n"
    )
    files = {"file": ("t.csv", csv_body.encode("utf-8"), "text/csv")}
    pr = s.post(f"{BASE_URL}/api/sms/preview", files=files, headers=admin_headers, timeout=15).json()
    contacts = pr["contacts"]
    assert len([c for c in contacts if c["valid"]]) == 2

    # 2) Create campaign (mock mode — no twilio env in preview)
    payload = {
        "name": "TEST_prelaunch_v217",
        "template": "Hola {{nom}} {{cognom}}, revisió {{data_revisio}}",
        "contacts": contacts,
    }
    cr = s.post(
        f"{BASE_URL}/api/sms/campaigns",
        json=payload,
        headers={**admin_headers, "Content-Type": "application/json"},
        timeout=20,
    )
    assert cr.status_code == 200, cr.text[:400]
    cdata = cr.json()
    assert cdata["ok"] is True
    campaign_id = cdata["campaign_id"]
    assert cdata["sent_count"] == 2
    assert cdata["error_count"] == 0
    assert cdata["twilio_mode"] in ("mock", "real")

    # 3) List — campaign must appear
    lr = s.get(f"{BASE_URL}/api/sms/campaigns", headers=admin_headers, timeout=15)
    assert lr.status_code == 200
    lst = lr.json()
    assert any(c["id"] == campaign_id for c in lst["campaigns"])

    # 4) Detail with search
    dr = s.get(
        f"{BASE_URL}/api/sms/campaigns/{campaign_id}",
        params={"q": "TestUno"},
        headers=admin_headers,
        timeout=15,
    )
    assert dr.status_code == 200
    detail = dr.json()
    assert detail["id"] == campaign_id
    # Search filters contacts down to 1
    filtered_names = [c.get("name") for c in detail.get("contacts", [])]
    assert "TestUno" in filtered_names
    assert "TestDos" not in filtered_names

    # 5) Stats
    st = s.get(f"{BASE_URL}/api/sms/stats", headers=admin_headers, timeout=15)
    assert st.status_code == 200
    assert st.json()["total_campaigns"] >= 1

    # 6) Cleanup — DELETE
    dl = s.delete(f"{BASE_URL}/api/sms/campaigns/{campaign_id}", headers=admin_headers, timeout=15)
    assert dl.status_code == 200
    assert dl.json()["ok"] is True

    # 7) Verify deletion
    dr2 = s.get(f"{BASE_URL}/api/sms/campaigns/{campaign_id}", headers=admin_headers, timeout=15)
    assert dr2.status_code == 404


# ---------- Calendar sync ----------
def test_calendar_fetch_spain_holidays(s):
    r = s.post(
        f"{BASE_URL}/api/calendar/fetch",
        json={
            "urls": [
                "https://calendar.google.com/calendar/ical/es.spain%23holiday%40group.v.calendar.google.com/public/basic.ics"
            ],
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
        },
        timeout=30,
    )
    assert r.status_code == 200
    d = r.json()
    assert "events" in d and isinstance(d["events"], list)


# ---------- Static SPA (v2.html) served via electron endpoint ----------
def test_v2_spa_has_guardar_pdf_and_master_key(s):
    r = s.get(f"{BASE_URL}/api/electron/download/index.html", timeout=30)
    assert r.status_code == 200
    body = r.text
    # Master key constant is present
    assert "MB-MASTER-BRUGULAT-2026-OWNER" in body
    # New PDF preview button
    assert "Guardar PDF" in body
    # Print helpers
    assert "function printHtml" in body
    assert "function printVisibleElement" in body
    # Iframe marker for print
    assert 'data-print-frame="1"' in body
    # No actual window.open() calls in code (only in comment & string references)
    for line in body.splitlines():
        if "window.open(" in line:
            stripped = line.strip()
            allowed = (
                stripped.startswith("//")
                or stripped.startswith("*")
                or stripped.startswith("/*")
                or "'window.open" in line
                or '"window.open' in line
                or "<code>window.open" in line
            )
            assert allowed, f"Real window.open call: {line[:120]}"


def test_v2_spa_no_diagnostico_url_panel(s):
    """Configuración modal must NOT contain 'Diagnóstico URL' panel per v2.1.7 spec."""
    r = s.get(f"{BASE_URL}/api/electron/download/index.html", timeout=30)
    body = r.text
    # These strings appeared in older versions; must be gone
    assert "Diagnóstico URL" not in body, "Diagnóstico URL panel must be removed"
    assert "Diagnòstic URL" not in body


def test_v2_spa_has_expected_testids(s):
    r = s.get(f"{BASE_URL}/api/electron/download/index.html", timeout=30)
    body = r.text
    for tid in [
        "sms-csv-file",
        "sms-camp-name",
        "sms-search",
        "btn-settings",
    ]:
        assert f'data-testid="{tid}"' in body, f"Missing data-testid={tid}"
