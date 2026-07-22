"""
Iteration 17 — Stripe subscriptions + sync security (device_not_authorized) + landing badges

Backend tests:
  - GET  /api/payments/subscription/enabled → 4 packages configured
  - POST /api/payments/create-subscription  → Stripe checkout.stripe.com URL for all 4 packages
  - POST /api/payments/create-subscription  → 422 when customer_email missing
  - POST /api/sync/heartbeat                → authorized=true for already-registered install
  - POST /api/sync/heartbeat                → device_limit_reached=true for 3rd new install
  - POST /api/sync/push                     → 403 device_not_authorized for unknown install
  - GET  /api/sync/pull                     → 403 device_not_authorized for unknown install
  - POST /api/sync/push                     → ok=true, written=1 for authorized install
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

# PRM license already in DB with 2 authorized devices (CD-PR8E... and CD-D299...)
PRM_LICENSE = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJjYWphLWRlbC1kaWEtbGljZW5zZS1zZXJ2ZXIiLCJzdWIiOiJDRC1QUjhFLUQ0RDgtQTcxQS0yODQyIiwianRpIjoiOGI4ZGI4NWEtMjM3NS00ZGQzLTg5ODgtN2VmMmQxNjE2NGJjIiwicGxhbiI6IlBSTSIsImlhdCI6MTc4NDcxNDk5OCwiZXhwIjoxNzg3MzA2OTk4fQ."
    "4YX9sbXouZeaWsk33x7S-r3zYFONLS0bFXQ4WNbWc88"
)
AUTHORIZED_INSTALL = "CD-PR8E-D4D8-A71A-2842"
UNKNOWN_INSTALL = "UNAUTHORIZED-TEST-XYZ"
THIRD_INSTALL = "CD-TEST-EXTRA-DEV3-9999"

PACKAGES = ["STD_MES", "STD_ANY", "PREMIUM_MES", "PREMIUM_ANY"]


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ============================================================
# STRIPE — subscription/enabled
# ============================================================
class TestStripeEnabled:
    def test_enabled_returns_true_and_4_packages(self, api):
        r = api.get(f"{BASE_URL}/api/payments/subscription/enabled", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("enabled") is True, f"enabled must be True, got {data}"
        assert data.get("stripe_api_key_present") is True
        pkgs = data.get("packages") or {}
        for pkg in PACKAGES:
            assert pkg in pkgs, f"{pkg} missing from response"
            assert pkgs[pkg] is True, f"{pkg} not configured on server"


# ============================================================
# STRIPE — create-subscription for all 4 packages
# ============================================================
class TestStripeCreateSubscription:
    @pytest.mark.parametrize("pkg", PACKAGES)
    def test_create_subscription_returns_stripe_url(self, api, pkg):
        body = {
            "package_id": pkg,
            "install_id": AUTHORIZED_INSTALL,
            "customer_email": f"TEST_{pkg.lower()}@medicarplus.es",
            "origin_url": BASE_URL,
        }
        r = api.post(
            f"{BASE_URL}/api/payments/create-subscription",
            json=body,
            timeout=30,
        )
        assert r.status_code == 200, f"[{pkg}] {r.status_code} {r.text[:400]}"
        data = r.json()
        url = data.get("url", "")
        session_id = data.get("session_id", "")
        assert "checkout.stripe.com" in url, f"[{pkg}] url={url}"
        assert session_id.startswith("cs_"), f"[{pkg}] session_id={session_id}"

    def test_create_subscription_missing_email_returns_422(self, api):
        body = {
            "package_id": "STD_MES",
            "install_id": AUTHORIZED_INSTALL,
            "origin_url": BASE_URL,
        }
        r = api.post(
            f"{BASE_URL}/api/payments/create-subscription",
            json=body,
            timeout=30,
        )
        assert r.status_code == 422, f"expected 422, got {r.status_code} {r.text[:200]}"

    def test_create_subscription_unknown_package_returns_400(self, api):
        body = {
            "package_id": "NOT_A_PACKAGE",
            "install_id": AUTHORIZED_INSTALL,
            "customer_email": "TEST_bad@medicarplus.es",
            "origin_url": BASE_URL,
        }
        r = api.post(
            f"{BASE_URL}/api/payments/create-subscription",
            json=body,
            timeout=30,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text[:200]}"


# ============================================================
# SYNC — heartbeat / push / pull with device_not_authorized check
# ============================================================
class TestSyncSecurity:
    def test_heartbeat_authorized_device(self, api):
        r = api.post(
            f"{BASE_URL}/api/sync/heartbeat",
            json={"license_key": PRM_LICENSE, "install_id": AUTHORIZED_INSTALL},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("authorized") is True
        assert data.get("is_premium") is True
        assert data.get("plan_family") == "PRM"
        assert data.get("max_devices") == 2

    def test_heartbeat_third_install_hits_device_limit(self, api):
        # This install is NEW — since PRM has 2 slots and both are already used
        # (CD-PR8E... and CD-D299...), the 3rd install must be rejected.
        r = api.post(
            f"{BASE_URL}/api/sync/heartbeat",
            json={"license_key": PRM_LICENSE, "install_id": THIRD_INSTALL},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("authorized") is False, f"3rd device must be denied: {data}"
        assert data.get("device_limit_reached") is True
        assert data.get("is_premium") is True

    def test_push_unauthorized_install_returns_403(self, api):
        r = api.post(
            f"{BASE_URL}/api/sync/push",
            json={
                "license_key": PRM_LICENSE,
                "install_id": UNKNOWN_INSTALL,
                "entries": {"foo": {"value": "bar", "updated_at": "2026-02-22T12:00:00Z"}},
            },
            timeout=20,
        )
        assert r.status_code == 403, r.text
        detail = r.json().get("detail")
        assert detail == "device_not_authorized", f"detail={detail}"

    def test_pull_unauthorized_install_returns_403(self, api):
        r = api.get(
            f"{BASE_URL}/api/sync/pull",
            params={"license_key": PRM_LICENSE, "install_id": UNKNOWN_INSTALL},
            timeout=20,
        )
        assert r.status_code == 403, r.text
        detail = r.json().get("detail")
        assert detail == "device_not_authorized", f"detail={detail}"

    def test_push_authorized_install_writes_entry(self, api):
        r = api.post(
            f"{BASE_URL}/api/sync/push",
            json={
                "license_key": PRM_LICENSE,
                "install_id": AUTHORIZED_INSTALL,
                "entries": {"caja.testkey": {"value": "X", "updated_at": "2026-02-22T12:00:00Z"}},
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        assert data.get("written") == 1
        assert data.get("cloud_updated_at")

    def test_pull_authorized_install_returns_entry(self, api):
        r = api.get(
            f"{BASE_URL}/api/sync/pull",
            params={"license_key": PRM_LICENSE, "install_id": AUTHORIZED_INSTALL},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        entries = data.get("entries") or {}
        assert "caja.testkey" in entries, f"entry not persisted: {list(entries.keys())}"
        assert entries["caja.testkey"]["value"] == "X"


# ============================================================
# Teardown — remove the 3rd install we may have accidentally registered
# ============================================================
@pytest.fixture(scope="module", autouse=True)
def cleanup_third_install():
    yield
    try:
        import asyncio, hashlib
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        lkh = hashlib.sha256(PRM_LICENSE.strip().encode()).hexdigest()

        async def _cleanup():
            await db.sync_devices.delete_many({
                "license_key_hash": lkh,
                "install_id": {"$in": [THIRD_INSTALL, UNKNOWN_INSTALL]},
            })
            # remove test key from sync_states.data
            state = await db.sync_states.find_one({"_id": lkh})
            if state:
                data = state.get("data", {}) or {}
                if "caja.testkey" in data:
                    data.pop("caja.testkey", None)
                    await db.sync_states.update_one({"_id": lkh}, {"$set": {"data": data}})

        asyncio.get_event_loop().run_until_complete(_cleanup())
    except Exception as e:  # noqa: BLE001
        print(f"cleanup warning: {e}")
