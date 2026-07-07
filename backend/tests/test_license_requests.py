"""Integration tests for the Fase 5 license request endpoints.

Covers:
- POST /api/licenses/requests (public creation + validation + 409 duplicate)
- GET  /api/licenses/requests (admin list w/ pending count + 401 without auth)
- POST /api/licenses/requests/{id}/approve (creates license + graceful email fallback)
- POST /api/licenses/requests/{id}/reject (marks rejected)
- Re-approve returns 409
- Admin-only routes reject requests without token
- GET  /api/licenses/{install_id} returns license_key
- POST /api/licenses/verify malformed key + wrong install_id branches
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BASE = "http://localhost:8001/api"
ADMIN_HEADERS = {"X-Admin-Token": os.environ["LICENSE_ADMIN_TOKEN"]}


def _rand_install_id() -> str:
    raw = uuid.uuid4().hex.upper()[:16]
    return "CD-" + "-".join(raw[i : i + 4] for i in range(0, 16, 4))


# --------- Cleanup helper ---------
def _mongo_cleanup(install_ids: list[str]) -> None:
    from pymongo import MongoClient

    client = MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    if install_ids:
        db.licenses.delete_many({"install_id": {"$in": install_ids}})
        db.license_requests.delete_many({"install_id": {"$in": install_ids}})
    client.close()


@pytest.fixture()
def install_id() -> str:
    return _rand_install_id()


@pytest.fixture(autouse=True)
def _cleanup(install_id: str):
    yield
    _mongo_cleanup([install_id])


# ============================================================================
# Public: POST /api/licenses/requests
# ============================================================================
class TestPublicRequestCreate:
    def test_create_pending_request_ok(self, install_id):
        payload = {
            "install_id": install_id,
            "company_name": "ACME SL",
            "contact_name": "Joan Roig",
            "email": "acme@example.com",
            "phone": "600123123",
            "tax_id": "B12345678",
            "plan_requested": "STD",
            "notes": "Volem provar",
        }
        r = requests.post(f"{BASE}/licenses/requests", json=payload, timeout=5)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["install_id"] == install_id
        assert data["status"] == "pending"
        assert data["company_name"] == "ACME SL"
        assert data["email"] == "acme@example.com"
        assert isinstance(data["id"], str) and len(data["id"]) > 0
        assert data["license_id"] is None
        assert data["email_sent"] is False

    def test_invalid_install_id_format_422(self):
        r = requests.post(
            f"{BASE}/licenses/requests",
            json={
                "install_id": "NOT-A-VALID-ID",
                "company_name": "X",
                "email": "x@example.com",
            },
            timeout=5,
        )
        assert r.status_code == 422

    def test_invalid_email_422(self, install_id):
        r = requests.post(
            f"{BASE}/licenses/requests",
            json={
                "install_id": install_id,
                "company_name": "X",
                "email": "not-an-email",
            },
            timeout=5,
        )
        assert r.status_code == 422

    def test_duplicate_pending_returns_409(self, install_id):
        body = {
            "install_id": install_id,
            "company_name": "Dup Co",
            "email": "dup@example.com",
        }
        first = requests.post(f"{BASE}/licenses/requests", json=body, timeout=5)
        assert first.status_code == 201, first.text
        second = requests.post(f"{BASE}/licenses/requests", json=body, timeout=5)
        assert second.status_code == 409
        assert "pendent" in second.json()["detail"].lower()


# ============================================================================
# Admin: GET /api/licenses/requests
# ============================================================================
class TestListRequests:
    def test_list_requires_admin(self):
        r = requests.get(f"{BASE}/licenses/requests", timeout=5)
        assert r.status_code == 401

    def test_list_returns_pending_count(self, install_id):
        requests.post(
            f"{BASE}/licenses/requests",
            json={
                "install_id": install_id,
                "company_name": "ListCo",
                "email": "list@example.com",
            },
            timeout=5,
        )
        r = requests.get(
            f"{BASE}/licenses/requests", headers=ADMIN_HEADERS, timeout=5
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and isinstance(data["items"], list)
        assert data["pending"] >= 1
        assert any(x["install_id"] == install_id for x in data["items"])


# ============================================================================
# Admin: approve / reject
# ============================================================================
class TestApproveReject:
    def _create_pending(self, install_id: str) -> str:
        r = requests.post(
            f"{BASE}/licenses/requests",
            json={
                "install_id": install_id,
                "company_name": "ApproveCo",
                "email": "approve@example.com",
                "plan_requested": "STD",
            },
            timeout=5,
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def test_approve_creates_license_and_graceful_email_fallback(self, install_id):
        req_id = self._create_pending(install_id)
        # RESEND_API_KEY is empty in .env → mailer must degrade gracefully
        r = requests.post(
            f"{BASE}/licenses/requests/{req_id}/approve",
            headers=ADMIN_HEADERS,
            json={"duration_days": 90, "plan": "STD", "send_email": True},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # Shape
        assert "request" in data and "license" in data
        # Email must degrade gracefully
        assert data["mailer_configured"] is False
        assert data["email_sent"] is False
        assert data["email_error"] == "resend_not_configured"
        # License must still be created + JWT present
        lic = data["license"]
        assert lic["install_id"] == install_id
        assert lic["status"] == "active"
        assert lic["license_key"] and lic["license_key"].count(".") == 2
        assert lic["plan"] == "STD"
        assert lic["expires_at"] is not None
        # Request marked approved with link to license
        req_obj = data["request"]
        assert req_obj["status"] == "approved"
        assert req_obj["license_id"] == lic["id"]
        assert req_obj["email_sent"] is False
        assert req_obj["email_error"] == "resend_not_configured"

    def test_reapprove_returns_409(self, install_id):
        req_id = self._create_pending(install_id)
        r1 = requests.post(
            f"{BASE}/licenses/requests/{req_id}/approve",
            headers=ADMIN_HEADERS,
            json={"duration_days": 30},
            timeout=10,
        )
        assert r1.status_code == 200
        r2 = requests.post(
            f"{BASE}/licenses/requests/{req_id}/approve",
            headers=ADMIN_HEADERS,
            json={"duration_days": 30},
            timeout=10,
        )
        assert r2.status_code == 409

    def test_approve_requires_admin(self, install_id):
        req_id = self._create_pending(install_id)
        r = requests.post(
            f"{BASE}/licenses/requests/{req_id}/approve",
            json={"duration_days": 30},
            timeout=5,
        )
        assert r.status_code == 401

    def test_reject_marks_rejected(self, install_id):
        req_id = self._create_pending(install_id)
        r = requests.post(
            f"{BASE}/licenses/requests/{req_id}/reject",
            headers=ADMIN_HEADERS,
            json={"reason": "prova cancel·lada"},
            timeout=5,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "rejected"
        assert data["processed_reason"] == "prova cancel·lada"

    def test_reject_requires_admin(self, install_id):
        req_id = self._create_pending(install_id)
        r = requests.post(
            f"{BASE}/licenses/requests/{req_id}/reject",
            json={"reason": "x"},
            timeout=5,
        )
        assert r.status_code == 401

    def test_approve_not_found_404(self):
        r = requests.post(
            f"{BASE}/licenses/requests/does-not-exist/approve",
            headers=ADMIN_HEADERS,
            json={},
            timeout=5,
        )
        assert r.status_code == 404


# ============================================================================
# Detail endpoint returns license_key (admin only)
# ============================================================================
class TestDetailIncludesKey:
    def test_detail_includes_license_key(self, install_id):
        r = requests.post(
            f"{BASE}/licenses/generate",
            headers=ADMIN_HEADERS,
            json={"install_id": install_id, "client_name": "KeyCo"},
            timeout=5,
        )
        assert r.status_code == 201
        det = requests.get(
            f"{BASE}/licenses/{install_id}", headers=ADMIN_HEADERS, timeout=5
        )
        assert det.status_code == 200
        data = det.json()
        assert data["install_id"] == install_id
        assert data["license_key"] and data["license_key"].count(".") == 2

    def test_detail_requires_admin(self, install_id):
        r = requests.get(f"{BASE}/licenses/{install_id}", timeout=5)
        assert r.status_code == 401


# ============================================================================
# Verify additional branches (malformed / wrong install)
# ============================================================================
class TestVerifyBranches:
    def test_verify_malformed_jwt_ok_false(self, install_id):
        r = requests.post(
            f"{BASE}/licenses/verify",
            json={"install_id": install_id, "key": "abc.def.ghi"},
            timeout=5,
        ).json()
        assert r["ok"] is False

    def test_verify_wrong_install_id_message_mentions_install(self, install_id):
        gen = requests.post(
            f"{BASE}/licenses/generate",
            headers=ADMIN_HEADERS,
            json={"install_id": install_id, "client_name": "W"},
            timeout=5,
        ).json()
        other = _rand_install_id()
        v = requests.post(
            f"{BASE}/licenses/verify",
            json={"install_id": other, "key": gen["license_key"]},
            timeout=5,
        ).json()
        assert v["ok"] is False
        # cleanup extra install id
        _mongo_cleanup([other])
        assert "instal" in v["reason"].lower()
