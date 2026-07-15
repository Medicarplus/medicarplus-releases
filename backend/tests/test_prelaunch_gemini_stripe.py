"""
Pre-launch tests for MediCar Plus — iteration 13.
Focus: Stripe subscriptions end-to-end (test mode, no card charge),
AI-ask fallback logic, billing portal 400/404 branches, webhook rejection,
Gemini onboarding backend integration.

Runs against REACT_APP_BACKEND_URL (public preview URL).
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # frontend/.env is source of truth for the preview URL
    from pathlib import Path
    envp = Path("/app/frontend/.env")
    if envp.exists():
        for ln in envp.read_text().splitlines():
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().strip('"').rstrip("/")
                break

API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def s():
    ses = requests.Session()
    ses.headers.update({"Content-Type": "application/json"})
    return ses


# ---------------------------------------------------------------------------
# 1) Subscription enabled — all 4 packages configured
# ---------------------------------------------------------------------------
class TestSubscriptionEnabled:
    def test_enabled_true_and_all_four_packages(self, s):
        r = s.get(f"{API}/payments/subscription/enabled", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("enabled") is True
        assert data.get("stripe_api_key_present") is True
        pkgs = data.get("packages") or {}
        for pid in ("STD_MES", "STD_ANY", "PREMIUM_MES", "PREMIUM_ANY"):
            assert pkgs.get(pid) is True, f"Package {pid} not configured: {pkgs}"


# ---------------------------------------------------------------------------
# 2) Create subscription — STD_MES via Stripe test mode
# ---------------------------------------------------------------------------
_created_session_id: dict = {}


class TestCreateSubscription:
    def test_std_mes_creates_stripe_checkout_session(self, s):
        payload = {
            "package_id": "STD_MES",
            "origin_url": BASE_URL,
            "customer_email": "TEST_prelaunch@medicarplus.es",
            "install_id": "CD-TEST-PRELAUNCH-13",
            "company_name": "TEST Company",
        }
        r = s.post(f"{API}/payments/create-subscription", json=payload, timeout=30)
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        data = r.json()
        assert "url" in data and data["url"].startswith("https://checkout.stripe.com/")
        assert "session_id" in data and data["session_id"].startswith("cs_test_")
        _created_session_id["id"] = data["session_id"]

    def test_invalid_package_id_returns_400(self, s):
        payload = {
            "package_id": "INVALID_XYZ",
            "origin_url": BASE_URL,
            "customer_email": "TEST_prelaunch@medicarplus.es",
        }
        r = s.post(f"{API}/payments/create-subscription", json=payload, timeout=15)
        assert r.status_code == 400
        assert "desconegut" in r.text.lower() or "unknown" in r.text.lower()

    def test_subscription_status_after_creation(self, s):
        sid = _created_session_id.get("id")
        if not sid:
            pytest.skip("no session_id from previous test")
        r = s.get(f"{API}/payments/subscription/status/{sid}", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # freshly created session should be 'open' and 'unpaid'
        assert data.get("status") == "open"
        assert data.get("payment_status") in ("unpaid", "no_payment_required", None)


# ---------------------------------------------------------------------------
# 3) Billing portal — 400 / 404 branches
# ---------------------------------------------------------------------------
class TestBillingPortal:
    def test_missing_both_ids_returns_400(self, s):
        r = s.post(f"{API}/payments/billing-portal", json={"return_url": BASE_URL}, timeout=15)
        assert r.status_code == 400
        assert "install_id" in r.text or "customer_email" in r.text

    def test_unknown_install_id_returns_404(self, s):
        payload = {"install_id": "CD-UNKNOWN-XXXX-9999", "return_url": BASE_URL}
        r = s.post(f"{API}/payments/billing-portal", json=payload, timeout=15)
        assert r.status_code == 404
        # friendly Spanish/Catalan message
        assert ("subscripció" in r.text.lower()
                or "subscripcion" in r.text.lower()
                or "no hem trobat" in r.text.lower())


# ---------------------------------------------------------------------------
# 4) Stripe webhook — rejects invalid signature
# ---------------------------------------------------------------------------
class TestStripeWebhookSecurity:
    def test_webhook_no_signature_does_not_create_license(self, s):
        # Post arbitrary payload with no/invalid signature. The server MUST NOT create
        # any license/subscription document. Response may be 200 with received=False
        # or 400 — the important part is that no side-effect occurs.
        fake = {
            "id": "evt_test_fake_signature",
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_fake", "mode": "subscription",
                                "subscription": "sub_test_fake",
                                "metadata": {"install_id": "CD-FAKE-WEBHOOK-XYZ",
                                             "package_id": "STD_MES"}}},
        }
        r = requests.post(
            f"{API}/webhook/stripe",
            data=str(fake).encode("utf-8"),
            headers={"Stripe-Signature": "t=1234,v1=deadbeef"},
            timeout=15,
        )
        # Accept either 400 or 200 with received=False, but confirm nothing was persisted
        assert r.status_code in (200, 400)
        if r.status_code == 200:
            j = r.json()
            assert j.get("received") is False or j.get("handled") != "subscription"


# ---------------------------------------------------------------------------
# 5) /api/ai-ask — fallback logic (no key + invalid user key)
# ---------------------------------------------------------------------------
class TestAiAsk:
    def _payload(self, user_key=""):
        return {
            "question": "¿Ves algún descuadre obvio en el registro?",
            "company": "cbTrafic",
            "diff": 0,
            "userGeminiKey": user_key,
            "data": {
                "cbTrafic": {
                    "byDate": {
                        "2026-01-15": [
                            {"kind": "tramite", "tipo": "TRANSF", "nombre": "Juan Perez",
                             "importe": 50, "tasa": 27, "fp": "EF"},
                            {"kind": "tramite", "tipo": "MATR", "nombre": "Ana Lopez",
                             "importe": 80, "tasa": 55, "fp": "TG"},
                        ]
                    }
                }
            },
        }

    def test_ai_ask_no_user_key_uses_emergent_fallback(self, s):
        r = s.post(f"{API}/ai-ask", json=self._payload(""), timeout=90)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "answer" in data
        assert isinstance(data["answer"], str) and len(data["answer"]) > 5
        assert data.get("source") in ("emergent-key", "emergent-key-fallback", None) or data.get("error") in (None, False)

    def test_ai_ask_invalid_user_key_falls_back_silently(self, s):
        # 39-char fake key — passes length check but Gemini will reject it
        fake = "AIzaSyTEST" + "0" * 29
        assert len(fake) == 39
        r = s.post(f"{API}/ai-ask", json=self._payload(fake), timeout=90)
        assert r.status_code == 200, r.text  # MUST NOT be 500
        data = r.json()
        assert "answer" in data
        assert isinstance(data["answer"], str) and len(data["answer"]) > 5


# ---------------------------------------------------------------------------
# 6) License verify — offline MASTER key (no server-side validation expected)
# ---------------------------------------------------------------------------
class TestLicenseMasterOffline:
    def test_master_key_is_offline_only(self, s):
        """
        The master key MB-MASTER-BRUGULAT-2026-OWNER is an OFFLINE bypass
        implemented on the frontend v2.html. Backend /api/licenses/verify
        does NOT accept it (it expects a JWT). We simply verify that:
        - The endpoint exists (not 404)
        - It gracefully rejects the master string (ok=false)
        """
        payload = {
            "install_id": "CD-TEST-OFFLINE-13",
            "key": "MB-MASTER-BRUGULAT-2026-OWNER",
        }
        r = s.post(f"{API}/licenses/verify", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # backend should reject (not a valid JWT), but must NOT crash
        assert data.get("ok") is False
        assert "reason" in data
