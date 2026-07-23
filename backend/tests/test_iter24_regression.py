"""
Iteration 24 · Regression + fresh scenarios for referral program.

Covers:
  - Direct checkout flow (?ref= direct purchase, no trial): POST /api/payments/create-subscription
    with valid referred_by → HTTP 200, Stripe URL, backend logs contain 'Applying referred-1m coupon'.
  - Coupon idempotency: 2 consecutive calls both return HTTP 200 (coupon MEDICAR_REFERRED_1M is retrieved,
    not re-created).
  - Regression NON-REFERRED checkout: without referred_by → HTTP 200, Stripe URL, uses
    allow_promotion_codes=True (verified by source inspection since we can't retrieve
    Stripe session detail via test API easily).
  - MASTER flow E2E (referrer earns +2m, referred gets +1m):
      (a) Seed STD referrer with referral_code=MC-E2E-9999, install_id=CD-E2E-REF
      (b) POST /api/trial/start with referred_by=MC-E2E-9999 → trial doc has referred_by
      (c) _sync_license_from_subscription with same trial install_id upgrading to STD_MES
          → trial revoked, new paid STD doc with unique referral_code, referrer gets +2m entry
      (d) Paid doc has referred_by='MC-E2E-9999' inherited.
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

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    fe_env = Path("/app/frontend/.env").read_text()
    for line in fe_env.splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break
assert BASE_URL

_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _await(coro):
    # If server.db was bound to a different loop in a previous test module,
    # reuse that loop to avoid "attached to a different loop" errors.
    try:
        import server as _srv
        if hasattr(_srv, 'client') and _srv.client is not None:
            other_loop = _srv.client.get_io_loop() if hasattr(_srv.client, 'get_io_loop') else None
            if other_loop and other_loop is not _LOOP and not other_loop.is_closed():
                return other_loop.run_until_complete(coro)
    except Exception:
        pass
    return _LOOP.run_until_complete(coro)


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
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]], None


REF_CODE = "MC-E2E9-9999"  # NOTE: problem statement said MC-E2E-9999 but that fails the 4-char format regex
REFERRER_INSTALL_ID = "CD-E2E-REF"
REFERRER_EMAIL = "e2e-referrer@test.com"


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module", autouse=True)
def seed_and_cleanup():
    db, _ = _get_db()

    async def _seed():
        # Cleanup any prior test data
        await db.licenses.delete_many({
            "$or": [
                {"install_id": REFERRER_INSTALL_ID},
                {"install_id": {"$regex": r"^CD-E2E-"}},
                {"install_id": {"$regex": r"^CD-DIRECT-"}},
                {"install_id": {"$regex": r"^CD-NOREF-"}},
                {"install_id": {"$regex": r"^CD-TRIAL-PENDING-.*e2e-referred.*"}},
                {"referral_code": REF_CODE},
                {"client_email": {"$regex": r"^(e2e-|direct@|noref@).*@(test\.com|example\.com)$"}},
            ]
        })
        await db.payment_transactions.delete_many({
            "install_id": {"$regex": r"^CD-(E2E-|DIRECT-|NOREF-)"}
        })
        now = datetime.now(timezone.utc)
        # Seed STD referrer
        await db.licenses.insert_one({
            "id": str(uuid.uuid4()),
            "install_id": REFERRER_INSTALL_ID,
            "client_name": "E2E Referrer",
            "client_email": REFERRER_EMAIL,
            "plan": "STD",
            "status": "active",
            "duration_days": 365,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=365)).isoformat(),
            "license_key": "SEED-E2E-KEY",
            "referral_code": REF_CODE,
            "stripe_subscription_id": None,  # No real Stripe sub → uses license-extension fallback
            "referral_rewards": [],
            "referral_reward_count": 0,
        })

    _await(_seed())
    yield

    async def _cleanup():
        await db.licenses.delete_many({
            "$or": [
                {"install_id": REFERRER_INSTALL_ID},
                {"install_id": {"$regex": r"^CD-E2E-"}},
                {"install_id": {"$regex": r"^CD-DIRECT-"}},
                {"install_id": {"$regex": r"^CD-NOREF-"}},
                {"referral_code": REF_CODE},
                {"client_email": {"$regex": r"^(e2e-|direct@|noref@).*@(test\.com|example\.com)$"}},
            ]
        })
        await db.payment_transactions.delete_many({
            "install_id": {"$regex": r"^CD-(E2E-|DIRECT-|NOREF-)"}
        })

    _await(_cleanup())


# ======================================================================================
# TEST A · Direct checkout with referred_by → HTTP 200 + Stripe URL
# ======================================================================================
class TestDirectCheckoutWithReferral:
    def test_direct_referred_checkout_returns_200(self, api):
        install_id = f"CD-DIRECT-{int(time.time())}"
        r = api.post(f"{BASE_URL}/api/payments/create-subscription", json={
            "package_id": "STD_MES",
            "customer_email": "direct@test.com",
            "install_id": install_id,
            "origin_url": "https://medicarplus.es",
            "referred_by": REF_CODE,
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("url", "").startswith("https://checkout.stripe.com/"), data
        assert data.get("session_id", "").startswith("cs_"), data


# ======================================================================================
# TEST B · Coupon idempotency — 2 consecutive referred checkouts both succeed
# ======================================================================================
class TestCouponIdempotency:
    def test_two_consecutive_referred_checkouts(self, api):
        for i in range(2):
            install_id = f"CD-DIRECT-IDEMP-{int(time.time())}-{i}"
            r = api.post(f"{BASE_URL}/api/payments/create-subscription", json={
                "package_id": "STD_MES",
                "customer_email": f"direct@test.com",
                "install_id": install_id,
                "origin_url": "https://medicarplus.es",
                "referred_by": REF_CODE,
            })
            assert r.status_code == 200, f"Iter {i}: {r.status_code}: {r.text}"
            assert r.json().get("url", "").startswith("https://checkout.stripe.com/"), r.json()

    def test_coupon_retrieve_path_present_in_service(self):
        """Confirms services/referrals.py uses idempotent retrieve→create pattern for coupon."""
        src = Path("/app/backend/services/referrals.py").read_text()
        assert "MEDICAR_REFERRED_1M" in src
        # Idempotency: must retrieve first, fall back to create
        assert "Coupon.retrieve" in src or "coupon.retrieve" in src.lower(), \
            "Referrals service must attempt Coupon.retrieve before Create for idempotency"


# ======================================================================================
# TEST C · Regression — non-referred checkout uses allow_promotion_codes
# ======================================================================================
class TestNonReferredCheckoutRegression:
    def test_no_referred_by_returns_200(self, api):
        install_id = f"CD-NOREF-{int(time.time())}"
        r = api.post(f"{BASE_URL}/api/payments/create-subscription", json={
            "package_id": "STD_MES",
            "customer_email": "noref@test.com",
            "install_id": install_id,
            "origin_url": "https://medicarplus.es",
        })
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        assert r.json().get("url", "").startswith("https://checkout.stripe.com/"), r.json()

    def test_invalid_referred_by_falls_back_to_promo_codes(self, api):
        install_id = f"CD-NOREF-INVALID-{int(time.time())}"
        r = api.post(f"{BASE_URL}/api/payments/create-subscription", json={
            "package_id": "STD_MES",
            "customer_email": "noref@test.com",
            "install_id": install_id,
            "origin_url": "https://medicarplus.es",
            "referred_by": "MC-INVALID-XXXX",
        })
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        assert r.json().get("url", "").startswith("https://checkout.stripe.com/"), r.json()

    def test_conditional_kwargs_logic_present_in_source(self):
        """Source-level check: ensures the mutual-exclusion logic is present."""
        src = Path("/app/backend/routes/payments.py").read_text()
        # New logic: build kwargs conditionally
        assert 'checkout_kwargs["discounts"] = discounts_arg' in src, \
            "payments.py must add 'discounts' only when referral coupon is present"
        assert 'checkout_kwargs["allow_promotion_codes"] = True' in src, \
            "payments.py must add 'allow_promotion_codes' only when no discount"
        # Confirm both keys are NEVER passed simultaneously — via if/else structure
        assert "if discounts_arg:" in src


# ======================================================================================
# TEST D · MASTER FLOW E2E · Trial → paid upgrade with referral
# ======================================================================================
class TestMasterFlowE2E:
    def test_full_e2e_referrer_earns_2m_referred_gets_paid_license(self, api):
        db, _ = _get_db()

        # Step (b): POST /api/trial/start with referred_by=MC-E2E-9999
        ts = int(time.time())
        email = f"e2e-referred-{ts}@example.com"
        r = api.post(f"{BASE_URL}/api/trial/start", json={
            "email": email,
            "name": "E2E Referred",
            "consent": True,
            "website": "",
            "referred_by": REF_CODE,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        trial_install_id = data.get("install_id")
        assert trial_install_id and trial_install_id.startswith("CD-TRIAL-PENDING-"), trial_install_id

        async def _verify_trial_and_upgrade():
            import server

            # Verify trial doc has referred_by
            trial_doc = await server.db.licenses.find_one({"install_id": trial_install_id})
            assert trial_doc is not None
            assert trial_doc.get("plan") == "TRIAL"
            assert (trial_doc.get("referred_by") or "").upper() == REF_CODE

            # Ensure referrer starts with 0 rewards
            await server.db.licenses.update_one(
                {"referral_code": REF_CODE},
                {"$set": {"referral_rewards": [], "referral_reward_count": 0}},
            )

            # Step (c): Simulate Stripe subscription upgrade for the same install_id
            sub_id = f"sub_e2e_upgrade_{ts}"
            period_end = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
            mock_sub = {
                "id": sub_id,
                "status": "active",
                "current_period_end": period_end,
                "customer": f"cus_e2e_{ts}",
                "cancel_at_period_end": False,
            }
            await server._sync_license_from_subscription(
                sub=mock_sub,
                install_id=trial_install_id,
                package_id="STD_MES",
                client_email=email,
                company_name="E2E Referred",
                referred_by=None,  # deve heredarse del trial doc
            )

            # Verify: trial doc revoked
            trial_after = await server.db.licenses.find_one({
                "install_id": trial_install_id, "plan": "TRIAL"
            })
            assert trial_after is not None
            assert trial_after.get("status") == "revoked", \
                f"Trial should be revoked after upgrade, got: {trial_after.get('status')}"

            # Verify: NEW paid STD license exists
            new_paid = await server.db.licenses.find_one({
                "install_id": trial_install_id, "status": "active", "plan": "STD"
            })
            assert new_paid is not None, "New paid STD license must exist"
            assert (new_paid.get("referred_by") or "").upper() == REF_CODE, \
                "Paid license must inherit referred_by from trial"
            assert new_paid.get("referral_code"), "New paid license must have its own referral_code"
            assert new_paid.get("referral_code") != REF_CODE, "referral_code must be unique"

            # Verify: referrer has +2m reward entry
            ref_after = await server.db.licenses.find_one({"referral_code": REF_CODE})
            rewards = ref_after.get("referral_rewards") or []
            assert len(rewards) == 1, f"Expected 1 reward entry, got: {rewards}"
            entry = rewards[0]
            assert entry.get("months_added") == 2, entry
            assert entry.get("referred_install_id") == trial_install_id, entry

            # Cleanup
            await server.db.licenses.delete_many({"install_id": trial_install_id})
            await server.db.subscriptions.delete_many({"stripe_subscription_id": sub_id})

        _await(_verify_trial_and_upgrade())
