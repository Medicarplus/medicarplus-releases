"""
Iteration 14 backend regression tests.

Verifies the fixes shipped for:
  #1: annual/year-comparison company filter (frontend — not tested here)
  #2: Estadísticas dropdown restructure (frontend — not tested here)
  #3: Tráfico dynamic categories (frontend — not tested here)
  #4: URL rotation resiliency + link-healer + auto-published api-endpoint.json

This module focuses on the BACKEND / INFRASTRUCTURE side of #4:
  - Preview URL is served and reachable
  - Electron download + manifest endpoints healthy
  - Admin / request-license / guides are all served with linkHealer script
  - api-endpoint.json on GitHub is up-to-date and points at the current preview URL
"""
import os
import re
import requests
import pytest

def _load_backend_url() -> str:
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    # Fallback: read from frontend/.env (source of truth in this repo)
    from pathlib import Path
    fenv = Path(__file__).resolve().parents[2] / "frontend" / ".env"
    for line in fenv.read_text(encoding="utf-8").splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'").rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


BASE_URL = _load_backend_url()

# The canonical URL the auto-publisher should now be broadcasting.
EXPECTED_HOST_FRAGMENT = "project-helper-47.preview.emergentagent.com"
GITHUB_ENDPOINT_JSON = (
    "https://raw.githubusercontent.com/Medicarplus/medicarplus-releases/main/api-endpoint.json"
)

GUIDE_PATHS = [
    "/guia-medicar-plus.html",
    "/guia-client-installacio.html",
    "/manual-usuari.html",
]


# ---------------------------------------------------------------------------
# 1. Electron manifest + download endpoints
# ---------------------------------------------------------------------------
class TestElectronManifest:
    def test_manifest_server_ok(self):
        r = requests.get(f"{BASE_URL}/api/electron/manifest", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("server_ok") is True, f"server_ok expected True, got {data.get('errors')}"
        # All 5 tracked files must be hashed
        files = data.get("files", {})
        for fname in ("index.html", "main.js", "preload.js", "sync.js", "package.json"):
            assert fname in files, f"{fname} missing from manifest"
            assert "sha256" in files[fname] and "size" in files[fname]

    def test_download_index_html_200(self):
        """The Electron packaged index.html is served fresh and contains v2.0.65 marker + linkHealer refs."""
        r = requests.get(f"{BASE_URL}/api/electron/download/index.html", timeout=15)
        assert r.status_code == 200
        body = r.text
        assert "MediCar Plus" in body
        # Changelog contains v2.0.65 (whether visible as a version marker or in the "novedades" list)
        assert "v2.0.65" in body, "v2.0.65 changelog marker missing from packaged index.html"
        # The dropdown restructure IDs are present
        for _id in ("btnStatFacMensual", "btnStatAutoescolas", "btnStatTrafico",
                    "btnStatSms", "btnStatCites", "btnStatCompararAnys"):
            assert _id in body, f"dropdown id {_id} missing from packaged index.html"
        # Dynamic Traffic categories helper present
        assert "_trafDetectedCats" in body
        assert "_trafNormalizeCat" in body

    def test_download_rejects_unknown_file(self):
        r = requests.get(f"{BASE_URL}/api/electron/download/evil.exe", timeout=10)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 2. Admin + request-license + guides are all reachable
# ---------------------------------------------------------------------------
class TestPublicPages:
    def test_admin_200(self):
        r = requests.get(f"{BASE_URL}/admin", timeout=15)
        assert r.status_code == 200, f"/admin returned {r.status_code}"

    def test_request_license_200(self):
        r = requests.get(f"{BASE_URL}/request-license", timeout=15)
        assert r.status_code == 200

    def test_v2_html_200_and_has_dropdown_ids(self):
        r = requests.get(f"{BASE_URL}/v2.html", timeout=15)
        assert r.status_code == 200
        body = r.text
        for _id in ("btnStatFacMensual", "btnStatAutoescolas", "btnStatTrafico",
                    "btnStatSms", "btnStatCites", "btnStatCompararAnys"):
            assert _id in body

    @pytest.mark.parametrize("path", GUIDE_PATHS)
    def test_guide_200_with_linkhealer(self, path):
        r = requests.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        body = r.text
        assert "linkHealer" in body, f"linkHealer function missing in {path}"
        assert "link-healer" in body, f"link-healer comment marker missing in {path}"


# ---------------------------------------------------------------------------
# 3. Auto-published api-endpoint.json on GitHub matches current preview URL
# ---------------------------------------------------------------------------
class TestAutoPublishedEndpoint:
    def test_github_endpoint_matches_current_preview(self):
        r = requests.get(GITHUB_ENDPOINT_JSON, timeout=15)
        assert r.status_code == 200, f"api-endpoint.json unreachable: {r.status_code}"
        data = r.json()
        api = (data.get("api") or "").rstrip("/")
        assert EXPECTED_HOST_FRAGMENT in api, (
            f"api-endpoint.json points at wrong host: {api!r} — expected fragment "
            f"{EXPECTED_HOST_FRAGMENT!r}. If this fails the Electron clients on the field "
            f"will still hit an obsolete URL."
        )
        # Must equal REACT_APP_BACKEND_URL exactly (source of truth)
        assert api == BASE_URL, (
            f"api-endpoint.json ({api}) does not match REACT_APP_BACKEND_URL ({BASE_URL})"
        )
        # Sanity: notes + updated fields are present
        assert "updated" in data
        assert "notes" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
