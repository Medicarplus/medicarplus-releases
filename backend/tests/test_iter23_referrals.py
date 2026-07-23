"""
Iteration 23 · Referral Program (MediCar Plus).

Coverage:
  TEST 1 — GET /api/referrals/validate (invalid, then valid after seeding STD referrer)
           GET /api/referrals/my-code (active paid license, unknown install_id)
  TEST 2 — /my-code refuses TRIAL license.
  TEST 3 — POST /api/trial/start with referred_by → license doc has referred_by, no reward yet.
  TEST 4 — POST /api/payments/create-subscription with referred_by → HTTP 200, checkout URL,
           source inspection of payments.py verifies discounts_arg logic.
  TEST 7 — Simulate _sync_license_from_subscription with a mock Stripe sub dict; verify
           new STD license is created for referred_install_id, referral_code generated,
           referrer_doc gets a new referral_rewards entry with months_added=2.

Run:
    cd /app/backend && pytest tests/test_iter23_referrals.py -v \
      --tb=short --junitxml=/app/test_reports/pytest/pytest_iter23.xml
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
import requests

BACKEND_DIR = Path("/app/backend")
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# --------------------------------------------------------------------------------------
# Env / constants
# --------------------------------------------------------------------------------------
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from frontend .env
    fe_env = Path("/app/frontend/.env").read_text()
    for line in fe_env.splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

# Shared event loop across ALL tests in this module. Required because
# motor.AsyncIOMotorClient (used inside server.py's `db`) binds to the loop
# it was first used on; closing/creating new loops per test triggers
# "Event loop is closed" when re-touching server.db.
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _await(coro):
    return _LOOP.run_until_complete(coro)

REF_CODE_MAIN = "MC-TEST-2024"
REF_CODE_BAD = "MC-TEST-ZZZZ"
REFERRER_INSTALL_ID = "CD-REF-TEST-1"
REFERRER_EMAIL = "referrer@test.com"
TRIAL_REF_INSTALL_ID = "CD-TRIAL-REF-1"


# --------------------------------------------------------------------------------------
# DB helpers (direct motor client) — used for seeding + assertions
# --------------------------------------------------------------------------------------
def _load_backend_env():
    p = Path("/app/backend/.env")
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)


_load_backend_env()


def _get_db():
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    return client[db_name], client


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module", autouse=True)
def seed_and_cleanup():
    """Seed the referrer STD license + trial license before all tests, cleanup after."""
    db, client = _get_db()

    async def _seed():
        # Cleanup any pre-existing test docs first (idempotent)
        await db.licenses.delete_many({
            "$or": [
                {"install_id": REFERRER_INSTALL_ID},
                {"install_id": TRIAL_REF_INSTALL_ID},
                {"install_id": {"$regex": r"^CD-NEW-PAID-"}},
                {"referral_code": REF_CODE_MAIN},
                {"client_email": {"$regex": r"^(referrer@test\.com|newpaid@test\.com|refe2e-.*@example\.com)$"}},
            ]
        })
        await db.payment_transactions.delete_many({
            "install_id": {"$regex": r"^CD-NEW-PAID-"}
        })

        # Seed referrer STD license (active, paid)
        now = datetime.now(timezone.utc)
        await db.licenses.insert_one({
            "id": str(uuid.uuid4()),
            "install_id": REFERRER_INSTALL_ID,
            "client_name": "Referrer",
            "client_email": REFERRER_EMAIL,
            "plan": "STD",
            "status": "active",
            "duration_days": 365,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=365)).isoformat(),
            "license_key": "SEED-STD-TEST-KEY",
            "referral_code": REF_CODE_MAIN,
            "stripe_subscription_id": None,   # no Stripe sub → reward will use fallback (license extension)
            "notes": "seed for iter23 referral tests",
        })

        # Seed TRIAL license for TEST 2
        await db.licenses.insert_one({
            "id": str(uuid.uuid4()),
            "install_id": TRIAL_REF_INSTALL_ID,
            "client_name": "Trial Tester",
            "client_email": "trialref@test.com",
            "plan": "TRIAL",
            "status": "active",
            "duration_days": 60,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=60)).isoformat(),
            "license_key": "SEED-TRIAL-TEST-KEY",
            "notes": "seed for iter23 trial refers test",
        })

    asyncio.get_event_loop().run_until_complete(_seed()) if False else _await(_seed())

    yield

    async def _cleanup():
        await db.licenses.delete_many({
            "$or": [
                {"install_id": REFERRER_INSTALL_ID},
                {"install_id": TRIAL_REF_INSTALL_ID},
                {"install_id": {"$regex": r"^CD-NEW-PAID-"}},
                {"install_id": {"$regex": r"^CD-TRIAL-PENDING-"}},
                {"referral_code": REF_CODE_MAIN},
                {"client_email": {"$regex": r"^(referrer@test\.com|trialref@test\.com|newpaid.*@test\.com|refe2e-.*@example\.com)$"}},
            ]
        })
        await db.payment_transactions.delete_many({
            "install_id": {"$regex": r"^CD-NEW-PAID-"}
        })
        client.close()

    _await(_cleanup())


# ======================================================================================
# TEST 1 — /validate + /my-code happy paths
# ======================================================================================
class TestValidateAndMyCode:
    def test_validate_invalid_code(self, api):
        r = api.get(f"{BASE_URL}/api/referrals/validate", params={"code": REF_CODE_BAD})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["valid"] is False, data
        assert data.get("referrer_name") in (None, "")

    def test_validate_valid_seeded_code(self, api):
        r = api.get(f"{BASE_URL}/api/referrals/validate", params={"code": REF_CODE_MAIN})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["valid"] is True, data
        # referrer_name derived from client_name / email prefix
        assert data.get("referrer_name"), "referrer_name should be non-empty"
        assert data.get("referrer_plan") == "STD"

    def test_my_code_returns_seeded_code(self, api):
        r = api.get(f"{BASE_URL}/api/referrals/my-code",
                    params={"install_id": REFERRER_INSTALL_ID})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True, data
        assert data.get("referral_code") == REF_CODE_MAIN
        assert "share_url" in data
        assert f"ref={REF_CODE_MAIN}" in data["share_url"]
        assert data.get("total_referrals") == 0
        assert data.get("months_earned") == 0

    def test_my_code_unknown_install(self, api):
        r = api.get(f"{BASE_URL}/api/referrals/my-code",
                    params={"install_id": "CD-UNKNOWN-INSTALL-9999999"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is False, data
        assert data.get("reason") == "no_active_license"


# ======================================================================================
# TEST 2 — /my-code refuses TRIAL license
# ======================================================================================
class TestMyCodeRefusesTrial:
    def test_trial_cannot_refer(self, api):
        r = api.get(f"{BASE_URL}/api/referrals/my-code",
                    params={"install_id": TRIAL_REF_INSTALL_ID})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is False, data
        assert data.get("reason") == "trial_cannot_refer"
        assert "pagado" in (data.get("message") or "").lower()


# ======================================================================================
# TEST 3 — POST /api/trial/start with referred_by MC-TEST-2024
# ======================================================================================
class TestTrialWithReferral:
    def test_trial_start_with_referral(self, api):
        ts = int(time.time())
        email = f"trialref-{ts}@test.com"
        r = api.post(f"{BASE_URL}/api/trial/start", json={
            "email": email,
            "name": "Trial Referred Tester",
            "consent": True,
            "referred_by": REF_CODE_MAIN,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        assert data.get("license_key"), "trial should return a license_key"
        install_id = data.get("install_id")
        assert install_id and install_id.startswith("CD-TRIAL-PENDING-"), install_id

        # Assert DB has referred_by = MC-TEST-2024 on the new trial doc
        db, client = _get_db()

        async def _check():
            doc = await db.licenses.find_one({"install_id": install_id})
            assert doc is not None
            assert doc.get("plan") == "TRIAL"
            assert (doc.get("referred_by") or "").upper() == REF_CODE_MAIN
            # And referrer's rewards array remains empty
            ref = await db.licenses.find_one({"referral_code": REF_CODE_MAIN})
            assert ref is not None
            rewards = ref.get("referral_rewards") or []
            assert rewards == [], f"Trial must NOT trigger reward yet, got: {rewards}"

            # Cleanup this specific trial doc
            await db.licenses.delete_one({"install_id": install_id})
            await db.licenses.delete_many({"client_email": email})
            client.close()

        asyncio.get_event_loop().run_until_complete(_check()) if False else _await(_check())


# ======================================================================================
# TEST 4 — POST /api/payments/create-subscription with referred_by
# ======================================================================================
class TestCreateSubscriptionWithReferral:
    def test_create_subscription_with_referral(self, api):
        install_id = f"CD-NEW-PAID-{int(time.time())}"
        r = api.post(f"{BASE_URL}/api/payments/create-subscription", json={
            "package_id": "STD_MES",
            "customer_email": "newpaid@test.com",
            "install_id": install_id,
            "origin_url": "https://medicarplus.es",
            "referred_by": REF_CODE_MAIN,
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("url", "").startswith("https://checkout.stripe.com/") \
            or data.get("url", "").startswith("https://integrations.emergentagent.com/"), data
        assert data.get("session_id", "").startswith("cs_"), data

        # Source inspection (guarantees the discounts logic path is present)
        src = Path("/app/backend/routes/payments.py").read_text()
        assert "get_or_create_referred_coupon" in src
        assert 'discounts_arg = [{"coupon": coupon.id}]' in src
        assert "Applying referred-1m coupon" in src

    def test_source_inspection_referrals_service(self):
        """Confirms both referrer + referred coupon helpers exist and use idempotent IDs."""
        src = Path("/app/backend/services/referrals.py").read_text()
        assert "MEDICAR_REFERRAL_2M" in src
        assert "MEDICAR_REFERRED_1M" in src
        assert "duration_in_months=2" in src
        assert "duration_in_months=1" in src


# ======================================================================================
# TEST 7 — Simulate _sync_license_from_subscription with mock Stripe sub dict
# ======================================================================================
class TestSyncLicenseFromSubscription:
    def test_full_reward_flow_via_mock_sub(self):
        """Directly invokes _sync_license_from_subscription to prove:
           (a) new STD license is created for CD-NEW-PAID-* with referred_by set,
           (b) referral_code auto-generated for the new license,
           (c) referrer's referral_rewards gets a new entry with months_added=2.
        """
        import importlib
        db, client = _get_db()

        install_id = f"CD-NEW-PAID-SYNC-{int(time.time())}"
        sub_id = f"sub_test_iter23_{int(time.time())}"
        period_end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())

        # Mock Stripe subscription dict (matches what _sync_license_from_subscription expects)
        mock_sub = {
            "id": sub_id,
            "status": "active",
            "current_period_end": period_end,
            "customer": f"cus_test_{sub_id}",
            "cancel_at_period_end": False,
        }

        async def _run():
            # We monkey-patch DB reference in the referrals helper via same client
            import server  # backend/server.py
            # Ensure referrer_doc exists (seeded) and has NO existing rewards
            ref = await server.db.licenses.find_one({"referral_code": REF_CODE_MAIN})
            assert ref is not None, "seed missing"
            # Clear any pre-existing rewards from prior runs
            await server.db.licenses.update_one(
                {"referral_code": REF_CODE_MAIN},
                {"$set": {"referral_rewards": [], "referral_reward_count": 0}},
            )

            # Ensure no license exists yet for install_id
            await server.db.licenses.delete_many({"install_id": install_id})

            # Call the private function directly
            await server._sync_license_from_subscription(
                sub=mock_sub,
                install_id=install_id,
                package_id="STD_MES",
                client_email="newpaid-sync@test.com",
                company_name="NewPaid Sync",
                referred_by=REF_CODE_MAIN,
            )

            # Assert new STD license was created
            new_lic = await server.db.licenses.find_one({"install_id": install_id, "status": "active"})
            assert new_lic is not None, "new license should be created"
            assert new_lic.get("plan") == "STD"
            assert (new_lic.get("referred_by") or "").upper() == REF_CODE_MAIN
            assert new_lic.get("referral_code"), "new license should have its own referral_code"
            assert new_lic.get("referral_code") != REF_CODE_MAIN, "must be unique"

            # Assert referrer got a reward entry
            ref_after = await server.db.licenses.find_one({"referral_code": REF_CODE_MAIN})
            rewards = ref_after.get("referral_rewards") or []
            assert len(rewards) >= 1, f"expected 1 reward, got: {rewards}"
            entry = rewards[-1]
            assert entry.get("months_added") == 2
            assert entry.get("referred_install_id") == install_id
            # info should indicate either stripe_coupon_applied OR license_extended fallback
            info = str(entry.get("reward_info") or "")
            assert info.startswith("stripe_coupon_") or info.startswith("license_extended_"), info

            # Cleanup
            await server.db.licenses.delete_many({"install_id": install_id})
            await server.db.subscriptions.delete_many({"stripe_subscription_id": sub_id})
            # Reset rewards on referrer
            await server.db.licenses.update_one(
                {"referral_code": REF_CODE_MAIN},
                {"$set": {"referral_rewards": [], "referral_reward_count": 0}},
            )

        _await(_run())

    def test_trial_inheritance_to_paid(self):
        """When _sync_license_from_subscription is called WITHOUT referred_by,
        but an active trial exists for the install_id with referred_by set,
        the paid license must inherit referred_by and the referrer must get rewarded."""
        db, client = _get_db()
        install_id = f"CD-NEW-PAID-INHERIT-{int(time.time())}"
        sub_id = f"sub_test_iter23_inherit_{int(time.time())}"
        period_end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())

        mock_sub = {
            "id": sub_id,
            "status": "active",
            "current_period_end": period_end,
            "customer": f"cus_test_{sub_id}",
            "cancel_at_period_end": False,
        }

        async def _run():
            import server
            # Reset any pre-existing rewards
            await server.db.licenses.update_one(
                {"referral_code": REF_CODE_MAIN},
                {"$set": {"referral_rewards": [], "referral_reward_count": 0}},
            )
            # Seed a Trial for install_id with referred_by (as if user came from landing?ref=)
            now = datetime.now(timezone.utc)
            trial_id = str(uuid.uuid4())
            await server.db.licenses.insert_one({
                "id": trial_id,
                "install_id": install_id,
                "client_name": "Inherited",
                "client_email": "inherit@test.com",
                "plan": "TRIAL",
                "status": "active",
                "duration_days": 60,
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(days=60)).isoformat(),
                "license_key": "SEED-TRIAL-INHERIT",
                "referred_by": REF_CODE_MAIN,
            })

            # Sync WITHOUT referred_by → should be inherited from trial
            await server._sync_license_from_subscription(
                sub=mock_sub,
                install_id=install_id,
                package_id="STD_MES",
                client_email="inherit@test.com",
                company_name="Inherit Co",
                referred_by=None,   # ← key part
            )

            new_lic = await server.db.licenses.find_one({
                "install_id": install_id, "status": "active", "plan": "STD"
            })
            assert new_lic is not None, "paid license not created"
            assert (new_lic.get("referred_by") or "").upper() == REF_CODE_MAIN, \
                "referred_by must be inherited from trial"

            ref_after = await server.db.licenses.find_one({"referral_code": REF_CODE_MAIN})
            rewards = ref_after.get("referral_rewards") or []
            assert len(rewards) >= 1, "reward should be recorded after inheritance"

            # Cleanup
            await server.db.licenses.delete_many({"install_id": install_id})
            await server.db.subscriptions.delete_many({"stripe_subscription_id": sub_id})
            await server.db.licenses.update_one(
                {"referral_code": REF_CODE_MAIN},
                {"$set": {"referral_rewards": [], "referral_reward_count": 0}},
            )

        _await(_run())
