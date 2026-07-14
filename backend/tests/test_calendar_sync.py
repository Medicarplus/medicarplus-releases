"""
Backend tests for MediCar Plus v2.1.0 - Calendar Sync (POST /api/calendar/fetch)
================================================================================
Covers the v2.1.0 regression + security additions:
- SSRF protection via _is_url_safe (localhost, private IPs, file://, non-http schemes)
- webcal:// → https:// normalisation
- RRULE recurring events expansion via recurring-ical-events lib
- date_to INCLUSIVE fix (previous bug had .between stop param exclusive)
- sources_failed now carries BOTH 'url' (truncated original) AND 'label'
- Max 5 URLs enforced; range ≤ 60 days enforced
Regression:
- /api/ health
- /api/electron/download/package.json (v2.1.0)
- /api/electron/download/index.html (Cites + v2.1.0)
- /api/sms/campaigns, /api/sms/stats reachable
"""
import os
import re

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://project-helper-47.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

# Spain public holidays iCal from Google Calendar
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
# Health / regression endpoints
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
        assert "2.1.0" in body, "v2.html should reference version 2.1.0"
        cites_hits = re.findall(r"[Cc]ites|calendar/fetch|calendarSync|iCal", body)
        assert cites_hits, "Cites/calendar module code should be present in v2.html"

    def test_sms_campaigns_endpoint_reachable(self, http):
        r = http.get(f"{API}/sms/campaigns", timeout=10)
        assert r.status_code != 404, "SMS campaigns endpoint should still exist"
        assert r.status_code in (200, 400, 401, 403, 422), f"unexpected status {r.status_code}: {r.text[:200]}"

    def test_sms_stats_endpoint_reachable(self, http):
        r = http.get(f"{API}/sms/stats", timeout=10)
        assert r.status_code != 404, "SMS stats endpoint should still exist"
        assert r.status_code in (200, 400, 401, 403, 422), f"unexpected status {r.status_code}: {r.text[:200]}"


# ---------------------------------------------------------------------------
# POST /api/calendar/fetch — happy paths (Spain holidays)
# ---------------------------------------------------------------------------
class TestCalendarFetchHappyPath:
    def test_spain_holidays_jul_aug_2026_returns_expected_events(self, http):
        """Per task spec: range 2026-07-01 to 2026-08-15 must include
        Feast of Saint James on 2026-07-25 and Assumption of Mary on 2026-08-15.
        Also proves date_to is INCLUSIVE (2026-08-15 must be present)."""
        payload = {
            "urls": [SPAIN_HOLIDAYS_ICAL],
            "date_from": "2026-07-01",
            "date_to": "2026-08-15",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=45)
        assert r.status_code == 200, f"body={r.text[:500]}"
        data = r.json()

        # Envelope
        assert set(data.keys()) >= {"ok", "events", "sources_ok", "sources_failed", "fetched_at"}
        if not data["ok"]:
            pytest.skip(f"Could not reach Google Calendar: {data['sources_failed']}")

        assert "Google Calendar" in data["sources_ok"]
        assert data["sources_failed"] == []

        dates = {e["date"] for e in data["events"]}
        # date_to INCLUSIVE — 2026-08-15 (Assumption) must be present
        assert "2026-08-15" in dates, (
            f"expected 2026-08-15 (Assumption of Mary) — date_to must be INCLUSIVE. Got: {sorted(dates)}"
        )
        # Feast of Saint James, 2026-07-25 must be present
        assert "2026-07-25" in dates, (
            f"expected 2026-07-25 (Feast of Saint James). Got: {sorted(dates)}"
        )

        # Verify event summaries make sense
        aug15 = [e for e in data["events"] if e["date"] == "2026-08-15"]
        jul25 = [e for e in data["events"] if e["date"] == "2026-07-25"]
        aug15_txt = " | ".join(e["summary"].lower() for e in aug15)
        jul25_txt = " | ".join(e["summary"].lower() for e in jul25)
        assert any(k in aug15_txt for k in ("assumption", "asunción", "asuncion", "mary", "virgen")), \
            f"unexpected summary for 2026-08-15: {aug15_txt}"
        assert any(k in jul25_txt for k in ("saint james", "santiago", "james", "sant jaume")), \
            f"unexpected summary for 2026-07-25: {jul25_txt}"

        # Schema check
        ev = data["events"][0]
        for k in ("source", "uid", "date", "time", "end_time", "summary", "description", "location"):
            assert k in ev, f"missing field '{k}' in event: {ev}"
        assert ev["source"] == "Google Calendar"

    def test_events_sorted_by_date_time(self, http):
        payload = {
            "urls": [SPAIN_HOLIDAYS_ICAL],
            "date_from": "2026-01-01",
            "date_to": "2026-02-28",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=45)
        assert r.status_code == 200
        data = r.json()
        if not data["ok"] or len(data["events"]) < 2:
            pytest.skip("Not enough events to verify sort order")
        keys = [(e["date"], e["time"] or "00:00") for e in data["events"]]
        assert keys == sorted(keys), f"events not sorted: {keys}"

    def test_date_to_boundary_inclusive_single_day_range(self, http):
        """Explicit inclusive-boundary test: from == to == 2026-08-15 must return Aug 15."""
        payload = {
            "urls": [SPAIN_HOLIDAYS_ICAL],
            "date_from": "2026-08-15",
            "date_to": "2026-08-15",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=45)
        assert r.status_code == 200, r.text
        data = r.json()
        if not data["ok"]:
            pytest.skip(f"Could not reach Google Calendar: {data['sources_failed']}")
        dates = [e["date"] for e in data["events"]]
        assert "2026-08-15" in dates, (
            f"Single-day inclusive range failed. date_to must include the day itself. Got dates: {dates}"
        )


# ---------------------------------------------------------------------------
# POST /api/calendar/fetch — SSRF protection (NEW in v2.1.0)
# ---------------------------------------------------------------------------
class TestCalendarFetchSSRF:
    """All SSRF attack URLs should be rejected in sources_failed with a
    descriptive error, and the endpoint must still return HTTP 200 with ok=false."""

    def _assert_rejected(self, data, url_hint, error_substrings):
        """Helper: assert exactly one failure with URL & label & error matching."""
        assert data["ok"] is False, data
        assert data["events"] == []
        assert data["sources_ok"] == []
        assert len(data["sources_failed"]) == 1, data["sources_failed"]
        entry = data["sources_failed"][0]
        # NEW in v2.1.0: sources_failed carries BOTH url + label
        assert "url" in entry, f"'url' missing in sources_failed entry: {entry}"
        assert "label" in entry, f"'label' missing in sources_failed entry: {entry}"
        assert "error" in entry, f"'error' missing in sources_failed entry: {entry}"
        # Truncated original URL should include our hint
        assert url_hint in entry["url"], f"expected url hint '{url_hint}' in {entry['url']!r}"
        err = entry["error"]
        assert any(s in err for s in error_substrings), (
            f"expected error to contain one of {error_substrings!r}, got: {err!r}"
        )

    def test_ssrf_localhost_backend_rejected(self, http):
        payload = {
            "urls": ["http://localhost:8001/api/calendar/fetch"],
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        self._assert_rejected(
            r.json(),
            url_hint="localhost",
            error_substrings=["URL rebutjada", "Internal hostname not allowed"],
        )

    def test_ssrf_private_ip_192_rejected(self, http):
        payload = {
            "urls": ["http://192.168.1.1/cal.ics"],
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        self._assert_rejected(
            r.json(),
            url_hint="192.168.1.1",
            error_substrings=["Private/reserved IP not allowed", "192.168.1.1"],
        )

    def test_ssrf_private_ip_10_rejected(self, http):
        payload = {
            "urls": ["http://10.0.0.1/cal.ics"],
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        self._assert_rejected(
            r.json(),
            url_hint="10.0.0.1",
            error_substrings=["Private/reserved IP not allowed", "10.0.0.1"],
        )

    def test_ssrf_loopback_127_rejected(self, http):
        payload = {
            "urls": ["http://127.0.0.1/cal.ics"],
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        self._assert_rejected(
            r.json(),
            url_hint="127.0.0.1",
            error_substrings=["Private/reserved IP not allowed", "127.0.0.1"],
        )

    def test_ssrf_link_local_metadata_ip_rejected(self, http):
        """AWS/GCP metadata endpoint 169.254.169.254 must be blocked."""
        payload = {
            "urls": ["http://169.254.169.254/latest/meta-data/"],
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        self._assert_rejected(
            r.json(),
            url_hint="169.254.169.254",
            error_substrings=["Private/reserved IP not allowed", "169.254"],
        )

    def test_ssrf_file_scheme_rejected(self, http):
        payload = {
            "urls": ["file:///etc/passwd"],
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        self._assert_rejected(
            r.json(),
            url_hint="file:///etc/passwd",
            error_substrings=["Only http(s) URLs allowed", "URL rebutjada"],
        )

    def test_ssrf_dot_local_hostname_rejected(self, http):
        payload = {
            "urls": ["http://myserver.local/cal.ics"],
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        self._assert_rejected(
            r.json(),
            url_hint="myserver.local",
            error_substrings=["Internal hostname not allowed"],
        )

    def test_webcal_scheme_normalised_to_https(self, http):
        """webcal://calendar.google.com/... should be converted to https:// internally
        and then fetched. We use the public Spain holidays calendar with webcal://."""
        webcal_url = (
            "webcal://calendar.google.com/calendar/ical/"
            "en.spain%23holiday%40group.v.calendar.google.com/public/basic.ics"
        )
        payload = {
            "urls": [webcal_url],
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=45)
        assert r.status_code == 200, r.text
        data = r.json()
        # If Google is reachable, webcal:// must have been converted successfully.
        if data["ok"]:
            assert "Google Calendar" in data["sources_ok"], data
            assert data["sources_failed"] == []
            # Should still return Assumption of Mary on Aug 15
            dates = {e["date"] for e in data["events"]}
            assert "2026-08-15" in dates, f"Assumption of Mary missing. Got: {sorted(dates)}"
        else:
            # If fetch failed, error must NOT be an SSRF/scheme rejection —
            # webcal:// must NOT be rejected as "Only http(s) URLs allowed".
            errors = " ".join(e.get("error", "") for e in data["sources_failed"])
            assert "Only http(s)" not in errors, f"webcal:// wrongly rejected: {errors}"
            assert "Internal hostname" not in errors, f"webcal:// wrongly rejected: {errors}"
            pytest.skip(f"Could not reach Google via webcal→https: {data['sources_failed']}")


# ---------------------------------------------------------------------------
# POST /api/calendar/fetch — validation
# ---------------------------------------------------------------------------
class TestCalendarFetchValidation:
    def test_range_gt_60_days_returns_400(self, http):
        payload = {
            "urls": [SPAIN_HOLIDAYS_ICAL],
            "date_from": "2026-01-01",
            "date_to": "2026-04-01",
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
        # NEW in v2.1.0: url + label both present
        assert "url" in entry and "label" in entry and "error" in entry
        # url should carry the actual URL (or its truncation), not just the label
        assert "example" in entry["url"] or entry["url"].startswith("http"), (
            f"expected original URL in 'url' field, got: {entry['url']!r}"
        )
        assert data["events"] == []
        assert data["sources_ok"] == []

    def test_empty_urls_array_returns_422(self, http):
        payload = {"urls": [], "date_from": "2026-01-01", "date_to": "2026-01-31"}
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=10)
        assert r.status_code in (400, 422), f"got {r.status_code}: {r.text}"

    def test_exactly_5_urls_accepted(self, http):
        """5 URLs is the max — must NOT be a validation error."""
        payload = {
            "urls": [
                "https://calendar.google.com/x1.ics",
                "https://calendar.google.com/x2.ics",
                "https://calendar.google.com/x3.ics",
                "https://calendar.google.com/x4.ics",
                "https://calendar.google.com/x5.ics",
            ],
            "date_from": "2026-01-01",
            "date_to": "2026-01-15",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=60)
        # 5 URLs must be accepted (endpoint returns 200, even if all fetches fail individually)
        assert r.status_code == 200, f"5 URLs rejected unexpectedly: {r.status_code} {r.text[:300]}"

    def test_more_than_5_urls_rejected_422(self, http):
        payload = {
            "urls": [SPAIN_HOLIDAYS_ICAL] * 6,
            "date_from": "2026-01-01",
            "date_to": "2026-01-31",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=10)
        assert r.status_code == 422, r.text

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
        payload = {"urls": [url], "date_from": "2026-01-01", "date_to": "2026-01-15"}
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # Now that sources_failed has explicit 'label' field, check it directly.
        seen_labels = set(data["sources_ok"]) | {e.get("label") for e in data["sources_failed"]}
        assert expected_label in seen_labels, (
            f"label '{expected_label}' not found for URL {url}. Got: {seen_labels}. "
            f"sources_failed={data['sources_failed']}"
        )


# ---------------------------------------------------------------------------
# POST /api/calendar/fetch — multi-URL merge (partial success)
# ---------------------------------------------------------------------------
class TestCalendarFetchMulti:
    def test_multiple_urls_partial_success(self, http):
        payload = {
            "urls": [
                SPAIN_HOLIDAYS_ICAL,
                "https://fake-does-not-exist-medicar-xyz.example/cal.ics",
            ],
            "date_from": "2026-07-20",
            "date_to": "2026-09-15",
        }
        r = http.post(f"{API}/calendar/fetch", json=payload, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is False  # one failed
        if "Google Calendar" not in data["sources_ok"]:
            pytest.skip(f"Could not reach Google Calendar: {data['sources_failed']}")
        assert "Google Calendar" in data["sources_ok"]
        # sources_failed must contain the invalid one with url + label
        fail_urls = [e.get("url", "") for e in data["sources_failed"]]
        assert any("example" in u for u in fail_urls), (
            f"expected the .example URL in sources_failed, got: {data['sources_failed']}"
        )
        assert len(data["events"]) >= 1
