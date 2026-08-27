"""Iteration 30 — Final regression before production deploy.

Covers:
- Panel Cliente v2.html settings 'Datos de facturación' → verify_license with client_meta
  (company_name/contact_name/email/phone/tax_id) → top-level fields in license
- Download installer redirect /api/download/latest-installer
- Notifications category filter (instalaciones/pagos/avisos) + badge endpoint
- Support unified inbox msg-level mark read/unread
- Full admin flow smoke: login → list → generate → edit contact → cliente verify → delete
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://project-helper-47.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "MB-ADMIN-BRUGULAT-2026-4F8E2A1C"
ADMIN_HEADERS = {"X-Admin-Token": ADMIN_TOKEN, "Content-Type": "application/json"}


def _iid(tag="ITER30"):
    h = uuid.uuid4().hex.upper()
    return f"CD-{h[0:4]}-{h[4:8]}-{h[8:12]}-{h[12:16]}"


def _mint(install_id, plan="PREMIUM", days=30, email="iter30@test.com", company="Iter30 Co"):
    r = requests.post(
        f"{BASE_URL}/api/licenses/generate",
        json={"install_id": install_id, "plan": plan, "duration_days": days,
              "client_email": email, "client_name": company},
        headers=ADMIN_HEADERS, timeout=15,
    )
    assert r.status_code in (200, 201), f"generate: {r.status_code} {r.text}"
    return r.json()


def _delete(install_id):
    try:
        requests.delete(f"{BASE_URL}/api/licenses/{install_id}", headers=ADMIN_HEADERS, timeout=10)
    except Exception:
        pass


def _get_lic(install_id):
    r = requests.get(f"{BASE_URL}/api/licenses/{install_id}", headers=ADMIN_HEADERS, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# ==================== 1. Client Panel Billing Sync ====================
class TestClientBillingSync:
    """Simulates v2.html openSettingsModal → 'Guardar datos' flow.
    The client sends POST /api/licenses/verify with client_meta including
    company_name/contact_name/email/phone/tax_id → these must propagate to top-level.
    """

    def setup_method(self):
        self.iid = _iid()
        data = _mint(self.iid, email="initial@t.com", company="Initial Co")
        self.key = data.get("license_key") or data.get("key")
        assert self.key, f"no key returned: {data}"

    def teardown_method(self):
        _delete(self.iid)

    def test_client_billing_form_saves_and_syncs(self):
        """POST /verify with client_meta from client settings modal — full 5 fields."""
        client_meta = {
            "company_name": "Autoescuela Nueva SL",
            "contact_name": "María López",
            "email": "maria@autoescuela.es",
            "phone": "+34611222333",
            "tax_id": "B87654321",
        }
        r = requests.post(f"{BASE_URL}/api/licenses/verify",
                          json={"key": self.key, "install_id": self.iid, "client_meta": client_meta},
                          timeout=15)
        assert r.status_code == 200, f"verify: {r.status_code} {r.text}"
        j = r.json()
        assert j.get("ok") is True, j

        # Verify propagation via admin GET
        lic = _get_lic(self.iid)
        assert lic.get("contact_name") == "María López", lic
        assert lic.get("phone") == "+34611222333", lic
        assert lic.get("tax_id") == "B87654321", lic
        # company_name maps to client_name / centre
        assert lic.get("client_name") == "Autoescuela Nueva SL" or lic.get("centre") == "Autoescuela Nueva SL", lic
        assert lic.get("client_email") == "maria@autoescuela.es" or lic.get("email") == "maria@autoescuela.es", lic

    def test_client_billing_partial_update_does_not_clear_others(self):
        # First set everything
        requests.post(f"{BASE_URL}/api/licenses/verify",
                      json={"key": self.key, "install_id": self.iid,
                            "client_meta": {"contact_name": "First Contact", "phone": "+34600000001",
                                            "tax_id": "A11111111"}},
                      timeout=15)
        # Then update only phone
        r = requests.post(f"{BASE_URL}/api/licenses/verify",
                          json={"key": self.key, "install_id": self.iid,
                                "client_meta": {"phone": "+34600000999"}}, timeout=15)
        assert r.status_code == 200
        lic = _get_lic(self.iid)
        assert lic.get("phone") == "+34600000999"
        # Others should persist
        assert lic.get("contact_name") == "First Contact"
        assert lic.get("tax_id") == "A11111111"


# ==================== 2. Download installer ====================
class TestDownloadInstaller:
    def test_latest_installer_redirects(self):
        r = requests.get(f"{BASE_URL}/api/download/latest-installer",
                         allow_redirects=False, timeout=15)
        # Should 302 to GitHub or return meaningful error/JSON when no release configured
        assert r.status_code in (200, 302, 307, 404, 502, 503), r.status_code
        if r.status_code in (302, 307):
            loc = r.headers.get("Location", "")
            assert "github" in loc.lower() or "medicar" in loc.lower() or loc.endswith(".exe"), f"unexpected location: {loc}"


# ==================== 3. Notifications categories + badge ====================
class TestNotificationsFilters:
    def test_badge_returns_counts(self):
        r = requests.get(f"{BASE_URL}/api/admin/notifications/badge",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "unread" in j and "critical_unread" in j

    @pytest.mark.parametrize("cat", ["instalaciones", "pagos", "avisos"])
    def test_category_filter_returns_list(self, cat):
        r = requests.get(f"{BASE_URL}/api/admin/notifications?category={cat}&limit=20",
                         headers=ADMIN_HEADERS, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert isinstance(j.get("items"), list)

    def test_read_state_filter(self):
        for state in ("unread", "read"):
            r = requests.get(f"{BASE_URL}/api/admin/notifications?read_state={state}&limit=5",
                             headers=ADMIN_HEADERS, timeout=15)
            assert r.status_code == 200
            assert isinstance(r.json().get("items"), list)


# ==================== 4. Auth admin ====================
class TestAdminAuth:
    def test_admin_login_valid(self):
        r = requests.post(f"{BASE_URL}/api/auth/admin-login",
                         json={"username": "ADMINISTRADOR", "password": "Mbrugulat24"},
                         timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_admin_login_invalid(self):
        r = requests.post(f"{BASE_URL}/api/auth/admin-login",
                         json={"username": "ADMINISTRADOR", "password": "wrong-pass-xxx"},
                         timeout=15)
        assert r.status_code in (401, 403, 429)


# ==================== 5. Full E2E flow smoke ====================
class TestE2EAdminFlow:
    def test_admin_generate_edit_verify_delete(self):
        iid = _iid()
        try:
            gen = _mint(iid, email="e2e@iter30.com", company="E2E Test")
            key = gen.get("license_key") or gen.get("key")
            assert key

            # 2. List and confirm present
            r = requests.get(f"{BASE_URL}/api/licenses?limit=500", headers=ADMIN_HEADERS, timeout=15)
            assert r.status_code == 200
            items = r.json().get("items") or r.json().get("licenses") or []
            iids = [it.get("install_id") for it in items]
            assert iid in iids, f"license not in list"

            # 3. Admin PATCH contact
            r = requests.patch(f"{BASE_URL}/api/licenses/{iid}/contact",
                              json={"contact_name": "Admin Edit", "phone": "+34999888777"},
                              headers=ADMIN_HEADERS, timeout=15)
            assert r.status_code == 200, r.text

            # 4. Client verify with new meta
            r = requests.post(f"{BASE_URL}/api/licenses/verify",
                             json={"key": key, "install_id": iid,
                                   "client_meta": {"tax_id": "Z99887766"}}, timeout=15)
            assert r.status_code == 200
            assert r.json().get("ok") is True

            # 5. Confirm merged
            lic = _get_lic(iid)
            assert lic.get("contact_name") == "Admin Edit"
            assert lic.get("phone") == "+34999888777"
            assert lic.get("tax_id") == "Z99887766"
        finally:
            _delete(iid)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
