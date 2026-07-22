"""
Iteration 15 backend tests
==========================
Covers:
- POST /api/sync/heartbeat (license_not_found, valid Premium, device limit)
- POST /api/sync/push (requires premium, writes entries)
- GET  /api/sync/pull  (returns pushed entries)
- POST /api/pdf/render (returns a valid PDF - magic bytes %PDF)

The tests use the admin endpoint /api/licenses/generate to mint a real DB-backed
PRM license (per the review request instruction). MASTER offline key is NOT a
DB license so it cannot be used against /sync/*.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

ADMIN_TOKEN = "MB-ADMIN-BRUGULAT-2026-4F8E2A1C"
API = f"{BASE_URL}/api"


def _make_install_id(prefix: str = "AA") -> str:
    """install_id must match CD-XXXX-XXXX-XXXX-XXXX with uppercase hex."""
    h = uuid.uuid4().hex.upper()
    return f"CD-{prefix[:2].upper()}{h[0:2]}-{h[2:6]}-{h[6:10]}-{h[10:14]}"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def premium_license(session):
    """Create a PRM license via admin endpoint. Returns dict with license_key + install_id."""
    install_id = _make_install_id("PR")
    r = session.post(
        f"{API}/licenses/generate",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={
            "install_id": install_id,
            "client_name": "TEST_iter15_prm",
            "client_email": "test_iter15@example.com",
            "plan": "PRM",
            "duration_days": 30,
            "notes": "iter15 sync backend test",
        },
    )
    assert r.status_code == 201, f"admin generate failed: {r.status_code} {r.text}"
    data = r.json()
    assert "license_key" in data and data["license_key"].startswith("ey"), "expected JWT"
    return {"license_key": data["license_key"], "install_id": install_id, "id": data["id"]}


@pytest.fixture(scope="module")
def std_license(session):
    """Create a STD license (non premium) to test 403 on /sync/push."""
    install_id = _make_install_id("SD")
    r = session.post(
        f"{API}/licenses/generate",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={
            "install_id": install_id,
            "client_name": "TEST_iter15_std",
            "plan": "STD",
            "duration_days": 30,
        },
    )
    assert r.status_code == 201, f"admin generate std failed: {r.text}"
    return {"license_key": r.json()["license_key"], "install_id": install_id, "id": r.json()["id"]}


# ---------- heartbeat ----------
class TestHeartbeat:
    def test_heartbeat_not_found(self, session):
        r = session.post(
            f"{API}/sync/heartbeat",
            json={"license_key": "not-a-real-jwt-key-1234567890", "install_id": "TEST_x"},
        )
        assert r.status_code == 404
        assert r.json().get("detail") == "license_not_found"

    def test_heartbeat_premium_authorized(self, session, premium_license):
        r = session.post(
            f"{API}/sync/heartbeat",
            json={
                "license_key": premium_license["license_key"],
                "install_id": premium_license["install_id"],
            },
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["authorized"] is True
        assert d["is_premium"] is True
        assert d["plan"] == "PRM"
        assert d["max_devices"] == 2
        assert d["device_limit_reached"] is False

    def test_heartbeat_device_limit(self, session, premium_license):
        """Send heartbeats from install_id_2 (accepted), then install_id_3 (rejected)."""
        # install_id 2 → accepted
        r2 = session.post(
            f"{API}/sync/heartbeat",
            json={
                "license_key": premium_license["license_key"],
                "install_id": _make_install_id("D2"),
            },
        )
        assert r2.status_code == 200
        assert r2.json()["authorized"] is True

        # install_id 3 → should be device_limit_reached
        r3 = session.post(
            f"{API}/sync/heartbeat",
            json={
                "license_key": premium_license["license_key"],
                "install_id": _make_install_id("D3"),
            },
        )
        assert r3.status_code == 200
        d = r3.json()
        assert d["device_limit_reached"] is True
        assert d["authorized"] is False
        assert d["current_devices"] == 2  # only first two accepted


# ---------- push / pull ----------
class TestPushPull:
    def test_push_std_forbidden(self, session, std_license):
        r = session.post(
            f"{API}/sync/push",
            json={
                "license_key": std_license["license_key"],
                "install_id": std_license["install_id"],
                "entries": {"foo": {"value": 1, "updated_at": "2026-01-01T10:00:00+00:00"}},
            },
        )
        assert r.status_code == 403
        assert r.json().get("detail") == "sync_requires_premium"

    def test_push_premium_ok(self, session, premium_license):
        entries = {
            "cfg.company_name": {"value": "TEST_Auto_Iter15", "updated_at": "2026-01-15T09:00:00+00:00"},
            "cfg.color": {"value": "#ff0055", "updated_at": "2026-01-15T09:00:01+00:00"},
        }
        r = session.post(
            f"{API}/sync/push",
            json={
                "license_key": premium_license["license_key"],
                "install_id": premium_license["install_id"],
                "entries": entries,
            },
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["written"] == 2
        assert d["cloud_updated_at"] is not None

    def test_pull_returns_pushed(self, session, premium_license):
        r = session.get(
            f"{API}/sync/pull",
            params={
                "license_key": premium_license["license_key"],
                "install_id": premium_license["install_id"],
            },
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert "entries" in d
        e = d["entries"]
        assert "cfg.company_name" in e
        assert e["cfg.company_name"]["value"] == "TEST_Auto_Iter15"
        assert e["cfg.color"]["value"] == "#ff0055"
        assert d["cloud_updated_at"] is not None


# ---------- pdf render ----------
class TestPdfRender:
    def test_pdf_render_returns_pdf(self, session):
        html = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>t</title></head><body style='font:14px sans-serif'>"
            "<h1>Test iter15 PDF</h1><p>Hello from pytest</p>"
            "<table border=1><tr><td>A</td><td>B</td></tr></table></body></html>"
        )
        r = session.post(
            f"{API}/pdf/render",
            json={"html": html, "filename": "iter15_test.pdf"},
            timeout=90,
        )
        assert r.status_code == 200, f"pdf render http {r.status_code}: {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        content = r.content
        assert content[:4] == b"%PDF", f"invalid PDF magic bytes: {content[:8]!r}"
        assert len(content) > 1000, f"PDF suspiciously small: {len(content)}B"
