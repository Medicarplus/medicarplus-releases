"""Iteration 29 tests:
1. PATCH /api/licenses/{install_id}/contact — admin edit of contact fields
2. POST /api/licenses/verify — propagation of client_meta aliases to top-level fields
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://project-helper-47.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "MB-ADMIN-BRUGULAT-2026-4F8E2A1C"
ADMIN_HEADERS = {"X-Admin-Token": ADMIN_TOKEN, "Content-Type": "application/json"}


def _gen_install_id(tag="TEST"):
    """Create install_id matching CD-XXXX-XXXX-XXXX-XXXX (uppercase alphanumeric)."""
    h = uuid.uuid4().hex.upper()
    # 4 groups of 4 alnum
    return f"CD-{h[0:4]}-{h[4:8]}-{h[8:12]}-{h[12:16]}"


def _mint_license(install_id, plan="PREMIUM", days=30, email=None, company=None):
    payload = {
        "install_id": install_id,
        "plan": plan,
        "duration_days": days,
    }
    if email:
        payload["client_email"] = email
    if company:
        payload["client_name"] = company
    r = requests.post(f"{BASE_URL}/api/licenses/generate", json=payload, headers=ADMIN_HEADERS, timeout=15)
    assert r.status_code in (200, 201), f"generate failed: {r.status_code} {r.text}"
    data = r.json()
    return data


def _get_license(install_id):
    r = requests.get(f"{BASE_URL}/api/licenses/{install_id}", headers=ADMIN_HEADERS, timeout=15)
    assert r.status_code == 200, f"get failed: {r.status_code} {r.text}"
    return r.json()


def _delete_license(install_id):
    try:
        requests.delete(f"{BASE_URL}/api/licenses/{install_id}", headers=ADMIN_HEADERS, timeout=10)
    except Exception:
        pass


class TestPatchContact:
    """PATCH /api/licenses/{install_id}/contact"""

    def setup_method(self):
        self.install_id = _gen_install_id()
        _mint_license(self.install_id, email="test29@example.com", company="Empresa Inicial")

    def teardown_method(self):
        _delete_license(self.install_id)

    def test_patch_updates_fields_and_returns_license(self):
        body = {
            "contact_name": "Test User Admin",
            "phone": "+34600123456",
            "tax_id": "12345678A",
            "client_name": "Autoescuela TEST",
            "client_email": "nuevo@test.com",
        }
        r = requests.patch(f"{BASE_URL}/api/licenses/{self.install_id}/contact",
                           json=body, headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert data.get("ok") is True
        assert data.get("modified") == 1
        lic = data.get("license") or {}
        assert lic.get("contact_name") == "Test User Admin"
        assert lic.get("phone") == "+34600123456"
        assert lic.get("tax_id") == "12345678A"
        assert lic.get("client_name") == "Autoescuela TEST"
        assert lic.get("client_email") == "nuevo@test.com"

        # GET verifies persistence
        lic2 = _get_license(self.install_id)
        assert lic2.get("contact_name") == "Test User Admin"
        assert lic2.get("phone") == "+34600123456"
        assert lic2.get("tax_id") == "12345678A"

    def test_patch_partial_update_only_touches_sent_fields(self):
        # First set all fields
        requests.patch(f"{BASE_URL}/api/licenses/{self.install_id}/contact",
                       json={"contact_name": "Original", "phone": "111", "tax_id": "AAA"},
                       headers=ADMIN_HEADERS, timeout=15)
        # Now update ONLY phone
        r = requests.patch(f"{BASE_URL}/api/licenses/{self.install_id}/contact",
                           json={"phone": "222"}, headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        lic = _get_license(self.install_id)
        assert lic.get("phone") == "222"
        assert lic.get("contact_name") == "Original", "contact_name should be untouched when not sent"
        assert lic.get("tax_id") == "AAA", "tax_id should be untouched when not sent"

    def test_patch_empty_string_clears_field(self):
        requests.patch(f"{BASE_URL}/api/licenses/{self.install_id}/contact",
                       json={"contact_name": "ToBeCleared"}, headers=ADMIN_HEADERS, timeout=15)
        r = requests.patch(f"{BASE_URL}/api/licenses/{self.install_id}/contact",
                           json={"contact_name": ""}, headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        lic = _get_license(self.install_id)
        assert lic.get("contact_name") in (None, ""), f"empty string should clear, got: {lic.get('contact_name')!r}"

    def test_patch_404_when_install_id_missing(self):
        r = requests.patch(f"{BASE_URL}/api/licenses/CD-DOES-NOTX-EXST-XXXX-YYYY/contact",
                           json={"contact_name": "X"}, headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 404

    def test_patch_requires_admin_token(self):
        r = requests.patch(f"{BASE_URL}/api/licenses/{self.install_id}/contact",
                           json={"contact_name": "X"},
                           headers={"Content-Type": "application/json"}, timeout=15)
        assert r.status_code in (401, 403), f"expected auth error, got {r.status_code}"


class TestVerifyClientMetaSync:
    """POST /api/licenses/verify propagates client_meta aliases to top-level license fields."""

    def setup_method(self):
        self.install_id = _gen_install_id()
        gen = _mint_license(self.install_id, email="verify29@example.com", company="Empresa Old")
        self.license_key = gen.get("license_key")
        assert self.license_key, f"no license_key in generate response: {gen}"

    def teardown_method(self):
        _delete_license(self.install_id)

    def _verify(self, client_meta):
        r = requests.post(f"{BASE_URL}/api/licenses/verify",
                          json={"install_id": self.install_id,
                                "key": self.license_key,
                                "client_meta": client_meta}, timeout=15)
        assert r.status_code == 200, f"verify failed: {r.status_code} {r.text}"
        return r.json()

    def test_english_aliases_propagate(self):
        self._verify({
            "company_name": "Autoescuela TEST EN",
            "contact_name": "Marc EN",
            "phone": "+34 900 000",
            "tax_id": "X1234567Z",
            "email": "en@test.com",
        })
        time.sleep(0.5)
        lic = _get_license(self.install_id)
        assert lic.get("client_name") == "Autoescuela TEST EN"
        assert lic.get("contact_name") == "Marc EN"
        assert lic.get("phone") == "+34 900 000"
        assert lic.get("tax_id") == "X1234567Z"
        assert lic.get("client_email") == "en@test.com"

    def test_spanish_aliases_propagate(self):
        self._verify({
            "empresa": "Autoescuela ES",
            "persona_contacto": "Marc ES",
            "telefono": "+34 911 111",
            "nif": "Y7654321X",
            "email": "es@test.com",
        })
        time.sleep(0.5)
        lic = _get_license(self.install_id)
        assert lic.get("client_name") == "Autoescuela ES"
        assert lic.get("contact_name") == "Marc ES"
        assert lic.get("phone") == "+34 911 111"
        assert lic.get("tax_id") == "Y7654321X"
        assert lic.get("client_email") == "es@test.com"

    def test_cif_and_accented_telefono_aliases(self):
        self._verify({
            "cif": "B12345678",
            "teléfono": "+34 933 333",
        })
        time.sleep(0.5)
        lic = _get_license(self.install_id)
        assert lic.get("tax_id") == "B12345678", f"cif alias failed: {lic.get('tax_id')}"
        assert lic.get("phone") == "+34 933 333", f"accented telefono alias failed: {lic.get('phone')}"

    def test_meta_appears_in_list_endpoint(self):
        self._verify({"company_name": "ListTestCo", "contact_name": "ListContact"})
        time.sleep(0.5)
        r = requests.get(f"{BASE_URL}/api/licenses", headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200
        items = r.json().get("items") or []
        found = next((x for x in items if x.get("install_id") == self.install_id), None)
        assert found is not None, f"install_id {self.install_id} not in list"
        assert found.get("client_name") == "ListTestCo"
        assert found.get("contact_name") == "ListContact"


class TestNoServerErrors:
    """Full cycle smoke test — no 5xx across admin flows."""

    def test_admin_flow_no_5xx(self):
        # login-equivalent: any authenticated request
        r = requests.get(f"{BASE_URL}/api/licenses?limit=5", headers=ADMIN_HEADERS, timeout=15)
        assert 200 <= r.status_code < 500, f"list 5xx: {r.status_code} {r.text}"

        install_id = _gen_install_id()
        try:
            gen = _mint_license(install_id, email="smoke@t.com", company="Smoke Co")
            key = gen["license_key"]
            # verify with client_meta
            v = requests.post(f"{BASE_URL}/api/licenses/verify",
                              json={"install_id": install_id, "key": key,
                                    "client_meta": {"company_name": "X", "phone": "555"}},
                              timeout=15)
            assert 200 <= v.status_code < 500, f"verify 5xx: {v.status_code}"

            p = requests.patch(f"{BASE_URL}/api/licenses/{install_id}/contact",
                               json={"contact_name": "Smoke"}, headers=ADMIN_HEADERS, timeout=15)
            assert 200 <= p.status_code < 500, f"patch 5xx: {p.status_code}"

            g = requests.get(f"{BASE_URL}/api/licenses/{install_id}", headers=ADMIN_HEADERS, timeout=15)
            assert 200 <= g.status_code < 500

            # notifications endpoint
            n = requests.get(f"{BASE_URL}/api/notifications?limit=5", headers=ADMIN_HEADERS, timeout=15)
            assert n.status_code < 500, f"notifications 5xx: {n.status_code}"
        finally:
            _delete_license(install_id)
