"""
Iteration 22 — Stripe Checkout locale='es' fix.

Bug: users with browser locale ca-ES saw mixed Spanish/Catalan on Stripe Checkout
     (e.g. 'COMENZAR PROVA GRATIS' — 'COMENZAR' es + 'PROVA' ca).

Fix: /app/backend/routes/payments.py:238 passes `locale='es'` to
     stripe_sdk.checkout.Session.create() so all UI is rendered in Spanish
     regardless of browser locale.

Verification strategy for THIS TEST FILE (backend-only asserts):
  1. Static code inspection: ensure `locale="es"` is present in the actual
     `stripe_sdk.checkout.Session.create(...)` call of create_subscription.
  2. Regression: POST /api/payments/create-subscription for each of the 4
     packages, assert HTTP 200 and `url` starts with `https://checkout.stripe.com/`.

The additional dynamic verification (loading the checkout page with ca-ES
browser locale and checking for Spanish tokens) is done separately in the
Playwright script, because Stripe's session retrieve via the Emergent
proxy does not support cross-process reads.
"""
import os
import re
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)

PACKAGES = ["STD_MES", "STD_ANY", "PREMIUM_MES", "PREMIUM_ANY"]


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _payload(package_id: str) -> dict:
    return {
        "package_id": package_id,
        "customer_email": f"TEST_locale_{package_id.lower()}@example.com",
        "install_id": f"CD-LOCALE-CHECK-{package_id}",
        "company_name": "Locale Test",
        "origin_url": "https://medicarplus.es",
    }


# ---------------------------------------------------------------------------
# 1) Static code inspection: `locale="es"` must be inside the Session.create call
# ---------------------------------------------------------------------------
def test_payments_source_declares_locale_es():
    """The backend must pass locale='es' explicitly to Stripe Checkout.

    If this is missing, Stripe defaults to auto-detecting the browser locale
    and users with ca-ES locale see mixed Catalan/Spanish text like
    'COMENZAR PROVA GRATIS'.
    """
    path = "/app/backend/routes/payments.py"
    src = open(path, encoding="utf-8").read()

    # Locate the create-subscription handler
    m = re.search(
        r"async def create_subscription\(.*?\)\s*:\s*(.+?)(?=\nasync def |\ndef |\Z)",
        src, re.DOTALL,
    )
    assert m, "create_subscription handler not found in payments.py"
    body = m.group(1)

    # Session.create block
    sess_m = re.search(
        r"stripe_sdk\.checkout\.Session\.create\((.+?)\n\s*\)",
        body, re.DOTALL,
    )
    assert sess_m, "stripe_sdk.checkout.Session.create(...) block not found"
    call = sess_m.group(1)

    assert re.search(r'locale\s*=\s*["\']es["\']', call), (
        "locale='es' NOT passed to stripe_sdk.checkout.Session.create(). "
        "Stripe Checkout will auto-detect browser locale (ca-ES users will "
        "see mixed Catalan/Spanish text)."
    )
    # Sanity: not accidentally set to 'auto' or 'ca'
    assert not re.search(r'locale\s*=\s*["\']auto["\']', call), "locale must not be 'auto'"
    assert not re.search(r'locale\s*=\s*["\']ca["\']', call), "locale must not be 'ca'"


# ---------------------------------------------------------------------------
# 2) Regression: 4 packages create valid Stripe checkout sessions
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("package_id", PACKAGES)
def test_create_subscription_returns_valid_checkout_url(api_client, package_id):
    r = api_client.post(
        f"{BASE_URL}/api/payments/create-subscription", json=_payload(package_id)
    )
    assert r.status_code == 200, f"[{package_id}] HTTP {r.status_code}: {r.text}"

    data = r.json()
    assert "url" in data and "session_id" in data, (
        f"[{package_id}] response missing keys: {data}"
    )

    url = data["url"]
    assert url.startswith("https://checkout.stripe.com/"), (
        f"[{package_id}] URL does not point to Stripe Checkout: {url}"
    )
    assert data["session_id"].startswith("cs_"), (
        f"[{package_id}] unexpected session id: {data['session_id']}"
    )


# ---------------------------------------------------------------------------
# 3) The generated URL must NOT contain a Catalan locale hint in query params.
#     Stripe sometimes reflects the locale into the URL fragment; this is a
#     cheap belt-and-braces check without hitting the checkout page.
# ---------------------------------------------------------------------------
def test_checkout_url_has_no_catalan_locale_hint(api_client):
    r = api_client.post(
        f"{BASE_URL}/api/payments/create-subscription", json=_payload("STD_MES")
    )
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    # These are the tokens Stripe emits when locale is 'ca' — they must not appear.
    lowered = url.lower()
    for bad in ("locale=ca", "lang=ca", "hl=ca"):
        assert bad not in lowered, (
            f"Checkout URL leaks Catalan locale hint '{bad}': {url}"
        )
