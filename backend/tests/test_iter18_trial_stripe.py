"""
Iteration 18 · Backend tests
============================
- /api/trial/start  (happy path, duplicate 409, honeypot 400, consent 400)
- /api/payments/create-subscription (all 4 packages return checkout.stripe.com)
- /api/payments/subscription/status/{session_id}  (returns license_key/plan/expires_at/license_ready)
"""
from __future__ import annotations

import os
import re
import time
import requests
import pytest


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from frontend/.env
    try:
        with open("/app/frontend/.env") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
    except Exception:
        pass


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _uniq_email(prefix: str = "e2e") -> str:
    return f"TEST_{prefix}_{int(time.time() * 1000)}@medicarplus-test.example"


# --- TRIAL ------------------------------------------------------------------

class TestTrialFlow:
    def test_trial_start_success(self, api):
        email = _uniq_email("trial")
        r = api.post(f"{BASE_URL}/api/trial/start", json={
            "name": "Iter18 Tester",
            "email": email,
            "company": "Test Clinic",
            "consent": True,
        })
        assert r.status_code == 200, f"Body: {r.text}"
        d = r.json()
        # Structure
        assert d["ok"] is True
        assert d["plan"] == "TRIAL"
        assert d["days"] == 60
        assert d["install_id"].startswith("CD-TRIAL-")
        assert isinstance(d["license_key"], str)
        assert d["license_key"].startswith("eyJ"), f"license_key should be JWT (starts with eyJ), got: {d['license_key'][:20]}"
        assert d["expires_at"], "expires_at must be present"
        assert "download_url" in d and "github.com/Medicarplus" in d["download_url"]
        # Email flag present (True in prod, may be False in preview if SMTP blocked)
        assert "email_sent" in d
        # Save for duplicate test
        TestTrialFlow._existing_email = email

    def test_trial_duplicate_returns_409(self, api):
        email = getattr(TestTrialFlow, "_existing_email", None)
        assert email, "prev test must have run first"
        r = api.post(f"{BASE_URL}/api/trial/start", json={
            "name": "Dup Tester",
            "email": email,
            "consent": True,
        })
        assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"
        assert "prueba" in r.json().get("detail", "").lower()

    def test_trial_honeypot_returns_400(self, api):
        r = api.post(f"{BASE_URL}/api/trial/start", json={
            "name": "Bot",
            "email": _uniq_email("bot"),
            "consent": True,
            "website": "https://iamabot.com",
        })
        assert r.status_code == 400
        assert r.json().get("detail") == "invalid_request"

    def test_trial_consent_false_returns_400(self, api):
        r = api.post(f"{BASE_URL}/api/trial/start", json={
            "name": "Nocons",
            "email": _uniq_email("noc"),
            "consent": False,
        })
        assert r.status_code == 400
        assert r.json().get("detail") == "consent_required"

    def test_trial_invalid_email_422(self, api):
        r = api.post(f"{BASE_URL}/api/trial/start", json={
            "name": "Bad",
            "email": "not-an-email",
            "consent": True,
        })
        assert r.status_code in (400, 422)


# --- STRIPE SUBSCRIBE -------------------------------------------------------

class TestStripeSubscription:
    @pytest.mark.parametrize("pkg", ["STD_MES", "STD_ANY", "PREMIUM_MES", "PREMIUM_ANY"])
    def test_create_subscription_returns_checkout_url(self, api, pkg):
        r = api.post(f"{BASE_URL}/api/payments/create-subscription", json={
            "package_id": pkg,
            "customer_email": _uniq_email(pkg.lower()),
            "origin_url": BASE_URL,
        })
        assert r.status_code == 200, f"Body: {r.text}"
        d = r.json()
        assert "checkout.stripe.com" in d["url"], f"URL should be Stripe checkout, got {d['url']}"
        assert d["session_id"].startswith("cs_")
        # Save for status test
        TestStripeSubscription._last_session_id = d["session_id"]

    def test_subscription_status_returns_license_fields(self, api):
        session_id = getattr(TestStripeSubscription, "_last_session_id", None)
        assert session_id, "prev test must have created a session"
        r = api.get(f"{BASE_URL}/api/payments/subscription/status/{session_id}")
        assert r.status_code == 200, f"Body: {r.text}"
        d = r.json()
        # Ha de retornar els nous camps (poden ser None abans del webhook)
        for k in ("license_key", "install_id", "plan", "expires_at", "license_ready"):
            assert k in d, f"Missing field {k} in {list(d.keys())}"
        # Just after creation, no webhook has fired → license_ready must be false
        assert d["license_ready"] is False
        assert d["license_key"] is None
        # But payment_status is 'unpaid' since no card was entered yet
        assert d.get("payment_status") in ("unpaid", "no_payment_required", None, "open")

    def test_unknown_package_returns_400(self, api):
        r = api.post(f"{BASE_URL}/api/payments/create-subscription", json={
            "package_id": "FAKE_PKG",
            "customer_email": _uniq_email("bad"),
            "origin_url": BASE_URL,
        })
        assert r.status_code == 400
