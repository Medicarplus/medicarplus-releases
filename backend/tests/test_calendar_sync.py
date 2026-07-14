"""
Backend tests for MediCar Plus v2.1.0 - Calendar Sync (POST /api/calendar/fetch)
plus regression tests for:
- GET /api/ (health)
- GET /api/electron/download/index.html (must include v2.1.0 changelog + Cites module)
- GET /api/electron/download/package.json (version must be 2.1.0)
- GET /api/sms/campaigns (regression - existing feature)
"""
import os
import re
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://project-helper-47.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

# Spain public holidays iCal from Google Calendar (public URL) — matches task spec
SPAIN_HOLIDAYS_ICAL = (
    "https://calendar.google.com/calendar/ical/"
    "en.spain%23holiday%40group.v.calendar.google.com/public/basic.ics"
)


@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------------------------------------------------------------------------
# Health / regression endpoints (run first — cheap and gates further tests)
# ---------------------------------------------------------------------------
class TestHealthAndRegression:
    def test_api_root_ok(self, http):
        r = http.get(f"{API}/", timeout=10)
        assert r.status_code == 200

    def test_electron_package_json_version(self, http):
        r = http.get(f"{API}/electron/download/package.json", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("version") == "2.1.0", f"expected 2.1.0, got {data.get('version')}"

    def test_electron_index_html_contains_v210_and_cites(self, http):
        r = http.get(f"{API}/electron/download/index.html", timeout=15)
        assert r.status_code == 200
        body = r.text
        # v2.1.0 changelog reference
        assert "2.1.0" in body, "v2.html should reference version 2.1.0"
        # Cites module code should be present
        cites_hits = re.findall(r"[Cc]ites|calendar/fetch|calendarSync|iCal", body)
        assert cites_hits, "Cites/calendar module code should be present in v2.html"

    def test_sms_campaigns_endpoint_reachable(self, http):
        # No regression on SMS campaigns feature. Endpoint requires a license header;
        # we just ensure the endpoint exists (not a 404).
        r = http.get(f"{API}/sms/campaigns", timeout=10)
        assert r.status_code != 404, "SMS campaigns endpoint should still exist"
        # Any of 200 / 401 / 403 / 422 is acceptable — proves route is registered.
        assert r.status_code in (200, 400, 401, 403, 422), f"unexpected status {r.status_code}: {r.text[:200]}"


# ---------------------------------------------------------------------------
# POST /api/calendar/fetch — happy paths
# ---------------------------------------------------------------------------
class TestCalendarFetchHappyPath:
    def test_google_spain_holidays_returns_events(self, http):
        # Use a fixed window that WE KNOW contains Spanish holidays: Aug 2026 (Assumption of Mary on 15-Aug)
        payload = {
            "urls": [SPAIN_HOLIDAYS_ICAL],
            "date_from": "2026-07-20",
            "date_to": "2026-09-15",  # ~57 days, within 60-day cap
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=30)
        assert r.status_code == 200, f"body={r.text[:500]}"
        data = r.json()

        # Structure assertions
        assert set(data.keys()) >= {"ok", "events", "sources_ok", "sources_failed", "fetched_at"}
        assert isinstance(data["events"], list)
        assert isinstance(data["sources_ok"], list)
        assert isinstance(data["sources_failed"], list)

        # If Google Calendar fetch succeeded, ok must be True and label must be present
        if data["ok"]:
            assert "Google Calendar" in data["sources_ok"], data["sources_ok"]
            assert not data["sources_failed"]
            # Expect at least ONE event returned in a ~2 month window of Spain holidays
            assert len(data["events"]) >= 1, "expected at least one Spanish holiday in Jul-Sep 2026"

            # Assumption of Mary (Aug 15) should be there
            aug15 = [e for e in data["events"] if e["date"] == "2026-08-15"]
            assert aug15, f"expected 2026-08-15 event (Assumption of Mary). Got dates: {[e['date'] for e in data['events']]}"
            summaries = " | ".join(e["summary"] for e in aug15).lower()
            assert (
                "assumption" in summaries
                or "asunción" in summaries
                or "asuncion" in summaries
                or "mary" in summaries
                or "virgen" in summaries
            ), f"unexpected summary for 2026-08-15: {summaries}"

            # Each event has the expected schema fields
            ev = data["events"][0]
            for k in ("source", "uid", "date", "time", "end_time", "summary", "description", "location"):
                assert k in ev, f"missing field '{k}' in event: {ev}"
            assert ev["source"] == "Google Calendar"
        else:
            # Network/proxy issue reaching Google — record but don't hard-fail suite
            pytest.skip(f"Could not fetch Google Calendar iCal from server: {data['sources_failed']}")

    def test_events_sorted_by_date_time(self, http):
        payload = {
            "urls": [SPAIN_HOLIDAYS_ICAL],
            "date_from": "2026-01-01",
            "date_to": "2026-02-28",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=30)
        assert r.status_code == 200
        data = r.json()
        if not data["ok"] or len(data["events"]) < 2:
            pytest.skip("Not enough events to verify sort order")
        keys = [(e["date"], e["time"] or "00:00") for e in data["events"]]
        assert keys == sorted(keys), f"events not sorted: {keys}"


# ---------------------------------------------------------------------------
# POST /api/calendar/fetch — validation / error cases
# ---------------------------------------------------------------------------
class TestCalendarFetchValidation:
    def test_range_gt_60_days_returns_400(self, http):
        payload = {
            "urls": [SPAIN_HOLIDAYS_ICAL],
            "date_from": "2026-01-01",
            "date_to": "2026-04-01",  # 90 days
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=15)
        assert r.status_code == 400, r.text
        detail = r.json().get("detail", "")
        assert "60" in detail, f"expected '60 days' error, got: {detail}"

    def test_invalid_url_returns_ok_false_with_sources_failed(self, http):
        payload = {
            "urls": ["https://this-domain-should-not-exist-xyz-medicar.example/foo.ics"],
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is False
        assert isinstance(data["sources_failed"], list) and len(data["sources_failed"]) == 1
        entry = data["sources_failed"][0]
        assert "url" in entry and "error" in entry
        assert data["events"] == []
        assert data["sources_ok"] == []

    def test_empty_urls_array_returns_422(self, http):
        payload = {"urls": [], "date_from": "2026-01-01", "date_to": "2026-01-31"}
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=10)
        # Pydantic v2 rejects min_length violation with 422; acceptable also 400
        assert r.status_code in (400, 422), f"got {r.status_code}: {r.text}"

    def test_more_than_5_urls_rejected(self, http):
        payload = {
            "urls": [SPAIN_HOLIDAYS_ICAL] * 6,
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=10)
        assert r.status_code in (400, 422), r.text

    def test_invalid_date_format_returns_400(self, http):
        payload = {"urls": [SPAIN_HOLIDAYS_ICAL], "date_from": "not-a-date", "date_to": "2026-01-31"}
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=10)
        assert r.status_code == 400, r.text

    def test_date_to_before_date_from(self, http):
        payload = {"urls": [SPAIN_HOLIDAYS_ICAL], "date_from": "2026-02-01", "date_to": "2026-01-01"}
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=10)
        assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# POST /api/calendar/fetch — source labeling logic
# ---------------------------------------------------------------------------
class TestCalendarFetchLabeling:
    """Domain → label detection. Uses invalid hosts on purpose — we just check
    sources_failed contains the correct human label per URL domain."""

    @pytest.mark.parametrize("url,expected_label", [
        ("https://calendar.google.com/xxx.ics", "Google Calendar"),
        ("https://www.doctoralia.es/xxx.ics", "Doctoralia"),
        ("https://calendly.com/xxx.ics", "Calendly"),
        ("https://www.doctolib.fr/xxx.ics", "Doctolib"),
        ("https://p01-caldav.icloud.com/xxx.ics", "iCloud"),
        ("https://outlook.office365.com/xxx.ics", "Outlook"),
        ("https://app.timify.com/xxx.ics", "Timify"),
    ])
    def test_label_from_url(self, http, url, expected_label):
        # These are (mostly) invalid ics paths on real domains → will fail fetch
        # but the label must still be reported in sources_failed.
        payload = {
            "urls": [url],
            "date_from": "2026-01-01",
            "date_to": "2026-01-15",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # Either it succeeded (unlikely for fake URL) or failed with correct label
        labels_seen = set(data["sources_ok"]) | {e["url"] for e in data["sources_failed"]}
        assert expected_label in labels_seen, (
            f"label '{expected_label}' not found for URL {url}. Got: {labels_seen}"
        )


# ---------------------------------------------------------------------------
# POST /api/calendar/fetch — multi-URL merge (up to 5)
# ---------------------------------------------------------------------------
class TestCalendarFetchMulti:
    def test_multiple_urls_merged(self, http):
        # Combine one valid and one invalid — expect partial success
        payload = {
            "urls": [
                SPAIN_HOLIDAYS_ICAL,
                "https://fake-does-not-exist-medicar-xyz.example/cal.ics",
            ],
            "date_from": "2026-07-20",
            "date_to": "2026-09-15",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=45)
        assert r.status_code == 200, r.text
        data = r.json()
        # Overall ok is False because one failed
        assert data["ok"] is False
        # But we should still have both sources categorized
        if "Google Calendar" not in data["sources_ok"]:
            pytest.skip(f"Could not reach Google Calendar: {data['sources_failed']}")
        assert "Google Calendar" in data["sources_ok"]
        assert any(f["url"] in ("Calendari extern", "Google Calendar") or "example" in (f.get("url") or "").lower()
                   for f in data["sources_failed"])
        # Events came from the good source
        assert len(data["events"]) >= 1
