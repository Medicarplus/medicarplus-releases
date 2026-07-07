"""Integration tests for the license server.

Run:  cd /app/backend && pytest tests/test_licenses.py -q
Requires the backend already running on port 8001.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Utilitzem la URL interna del container per no dependre d'ingress.
BASE = "http://localhost:8001/api"
ADMIN_HEADERS = {"X-Admin-Token": os.environ["LICENSE_ADMIN_TOKEN"]}


def _rand_install_id() -> str:
    """Genera un install_id vàlid amb el format CD-XXXX-XXXX-XXXX-XXXX."""
    raw = uuid.uuid4().hex.upper()[:16]
    return "CD-" + "-".join(raw[i : i + 4] for i in range(0, 16, 4))


@pytest.fixture()
def install_id() -> str:
    return _rand_install_id()


@pytest.fixture(autouse=True)
def _cleanup(install_id: str):
    yield
    # Fem cleanup via mongo directament perquè no exposem un delete a l'API
    from pymongo import MongoClient

    client = MongoClient(os.environ["MONGO_URL"])
    client[os.environ["DB_NAME"]].licenses.delete_many({"install_id": install_id})
    client.close()


def test_generate_requires_admin(install_id):
    r = requests.post(
        f"{BASE}/licenses/generate",
        json={"install_id": install_id, "client_name": "X"},
        timeout=5,
    )
    assert r.status_code == 401


def test_generate_and_verify_ok(install_id):
    r = requests.post(
        f"{BASE}/licenses/generate",
        headers=ADMIN_HEADERS,
        json={
            "install_id": install_id,
            "client_name": "ACME SL",
            "client_email": "acme@example.com",
            "duration_days": 30,
            "plan": "STD",
        },
        timeout=5,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["install_id"] == install_id
    assert body["status"] == "active"
    assert body["expires_at"] is not None
    key = body["license_key"]
    assert key and key.count(".") == 2  # JWT

    v = requests.post(
        f"{BASE}/licenses/verify",
        json={"install_id": install_id, "key": key},
        timeout=5,
    ).json()
    assert v["ok"] is True
    assert v["status"] == "active"
    assert v["client_name"] == "ACME SL"


def test_verify_wrong_install_rejected(install_id):
    gen = requests.post(
        f"{BASE}/licenses/generate",
        headers=ADMIN_HEADERS,
        json={"install_id": install_id, "client_name": "A"},
        timeout=5,
    ).json()
    other = _rand_install_id()
    v = requests.post(
        f"{BASE}/licenses/verify",
        json={"install_id": other, "key": gen["license_key"]},
        timeout=5,
    ).json()
    assert v["ok"] is False
    assert "no correspon" in v["reason"].lower() or "instal" in v["reason"].lower()


def test_verify_bogus_key_rejected(install_id):
    v = requests.post(
        f"{BASE}/licenses/verify",
        json={"install_id": install_id, "key": "abc.def.ghi"},
        timeout=5,
    ).json()
    assert v["ok"] is False


def test_revoke_and_verify_blocked(install_id):
    gen = requests.post(
        f"{BASE}/licenses/generate",
        headers=ADMIN_HEADERS,
        json={"install_id": install_id, "client_name": "R", "duration_days": 10},
        timeout=5,
    ).json()
    key = gen["license_key"]

    rev = requests.post(
        f"{BASE}/licenses/revoke",
        headers=ADMIN_HEADERS,
        json={"install_id": install_id, "reason": "test"},
        timeout=5,
    )
    assert rev.status_code == 200, rev.text
    assert rev.json()["status"] == "revoked"

    v = requests.post(
        f"{BASE}/licenses/verify",
        json={"install_id": install_id, "key": key},
        timeout=5,
    ).json()
    assert v["ok"] is False
    assert v["revoked"] is True


def test_perpetual_license_has_no_expiry(install_id):
    r = requests.post(
        f"{BASE}/licenses/generate",
        headers=ADMIN_HEADERS,
        json={"install_id": install_id, "client_name": "Perpetual"},
        timeout=5,
    ).json()
    assert r["expires_at"] is None
    assert r["duration_days"] is None


def test_regenerate_replaces_previous_active(install_id):
    first = requests.post(
        f"{BASE}/licenses/generate",
        headers=ADMIN_HEADERS,
        json={"install_id": install_id, "client_name": "V1", "duration_days": 10},
        timeout=5,
    ).json()
    second = requests.post(
        f"{BASE}/licenses/generate",
        headers=ADMIN_HEADERS,
        json={"install_id": install_id, "client_name": "V2", "duration_days": 20},
        timeout=5,
    ).json()

    # La primera clau ja no ha de verificar
    v_old = requests.post(
        f"{BASE}/licenses/verify",
        json={"install_id": install_id, "key": first["license_key"]},
        timeout=5,
    ).json()
    assert v_old["ok"] is False

    # La segona clau ha de verificar OK
    v_new = requests.post(
        f"{BASE}/licenses/verify",
        json={"install_id": install_id, "key": second["license_key"]},
        timeout=5,
    ).json()
    assert v_new["ok"] is True
    assert v_new["client_name"] == "V2"


def test_list_and_detail(install_id):
    requests.post(
        f"{BASE}/licenses/generate",
        headers=ADMIN_HEADERS,
        json={"install_id": install_id, "client_name": "L"},
        timeout=5,
    )
    lst = requests.get(f"{BASE}/licenses?limit=5", headers=ADMIN_HEADERS, timeout=5).json()
    assert lst["total"] >= 1

    det = requests.get(
        f"{BASE}/licenses/{install_id}", headers=ADMIN_HEADERS, timeout=5
    ).json()
    assert det["install_id"] == install_id
    assert det["license_key"]  # el detall inclou la clau


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
