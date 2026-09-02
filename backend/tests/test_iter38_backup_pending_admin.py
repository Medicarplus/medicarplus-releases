"""Iteration 38 · Regresión Sync Multi-PC — backup entre PCs + admin push + admin reset.

Foco: (1) upsert de copias por remitente + created_at con tz + consume;
      (2) admin push-to-license (MASTER→MASTER y MASTER→cliente) + upsert admin + 403 clave falsa;
      (3) admin reset-devices 200/403/404.
"""
import os
import sys
import uuid
import hashlib
import asyncio
import re
from datetime import datetime, timezone, timedelta

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://project-helper-47.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"
MASTER = "MB-MASTER-BRUGULAT-2026-OWNER"
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']


def _hash(k):
    return hashlib.sha256(k.strip().encode()).hexdigest()


@pytest.fixture(scope="module")
def premium_key():
    """Crea licencia Premium fresca para el módulo."""
    key = f"TEST-ITER38-PRM-{uuid.uuid4().hex[:10]}"
    async def _setup():
        c = AsyncIOMotorClient(MONGO_URL)
        db = c[DB_NAME]
        await db.licenses.insert_one({
            "id": str(uuid.uuid4()),
            "install_id": "TEST-ITER38-BASE",
            "license_key": key,
            "plan": "PRM",
            "plan_family": "PRM",
            "status": "active",
            "client_email": "iter38@medicarplus.es",
            "client_name": "Iter38 Test",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
        })
        c.close()
    asyncio.get_event_loop().run_until_complete(_setup())
    yield key
    async def _cleanup():
        c = AsyncIOMotorClient(MONGO_URL)
        db = c[DB_NAME]
        h = _hash(key)
        await db.licenses.delete_many({"license_key": key})
        await db.sync_devices.delete_many({"license_key_hash": h})
        await db.sync_backups.delete_many({"license_key_hash": h})
        await db.sync_states.delete_many({"_id": h})
        c.close()
    asyncio.get_event_loop().run_until_complete(_cleanup())


@pytest.fixture(scope="module")
def install_ids(premium_key):
    """Reset devices for the license, then returns (PC_A, PC_B) authorised."""
    pc_a = f"iter38-PC-A-{uuid.uuid4().hex[:6]}"
    pc_b = f"iter38-PC-B-{uuid.uuid4().hex[:6]}"
    # Reset via admin
    requests.post(f"{API}/sync/admin/reset-devices", json={
        "admin_license_key": MASTER, "target_license_key": premium_key
    }, timeout=15)
    # Heartbeat each
    for iid in (pc_a, pc_b):
        r = requests.post(f"{API}/sync/heartbeat",
                          json={"license_key": premium_key, "install_id": iid}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("authorized") is True
    yield pc_a, pc_b
    # cleanup
    requests.post(f"{API}/sync/admin/reset-devices", json={
        "admin_license_key": MASTER, "target_license_key": premium_key
    }, timeout=15)


# ─────────────────── BACKUP FLOW (PC-A → PC-B) ───────────────────

def test_backup_send_two_consecutive_only_latest_pending(premium_key, install_ids):
    pc_a, pc_b = install_ids
    r1 = requests.post(f"{API}/sync/backup/send", json={
        "license_key": premium_key, "install_id": pc_a,
        "data": {"caja.v1": {"2026-01-01": [{"id": "x1"}]}},
        "label": "Copia 1"
    }, timeout=15)
    assert r1.status_code == 200, r1.text
    bid1 = r1.json()["backup_id"]

    r2 = requests.post(f"{API}/sync/backup/send", json={
        "license_key": premium_key, "install_id": pc_a,
        "data": {"caja.v1": {"2026-01-02": [{"id": "x2"}]}},
        "label": "Copia 2 (más nueva)"
    }, timeout=15)
    assert r2.status_code == 200, r2.text
    bid2 = r2.json()["backup_id"]
    assert bid2 != bid1

    # PC-B pending debe ser 1 y con label "Copia 2"
    r = requests.get(f"{API}/sync/backup/pending",
                     params={"license_key": premium_key, "install_id": pc_b},
                     timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1, data
    p = data["pending"][0]
    assert p["label"] == "Copia 2 (más nueva)"
    assert p["from_install_id"] == pc_a
    # created_at ha de contenir zona horaria (+00:00 o Z)
    created_at = p["created_at"]
    assert re.search(r"(\+00:00|Z)$", created_at), f"missing tz: {created_at}"
    # data llegó correctamente
    assert "caja.v1" in p["data"]
    assert p["data"]["caja.v1"].get("2026-01-02")


def test_backup_consume_pc_b(premium_key, install_ids):
    pc_a, pc_b = install_ids
    # Get current pending backup_id
    r = requests.get(f"{API}/sync/backup/pending",
                     params={"license_key": premium_key, "install_id": pc_b}, timeout=15)
    assert r.status_code == 200
    pending = r.json()["pending"]
    assert len(pending) == 1
    bid = pending[0]["backup_id"]

    rc = requests.post(f"{API}/sync/backup/consume", json={
        "license_key": premium_key, "install_id": pc_b, "backup_id": bid
    }, timeout=15)
    assert rc.status_code == 200

    # Ahora PC-B ya no ve pendientes
    r2 = requests.get(f"{API}/sync/backup/pending",
                      params={"license_key": premium_key, "install_id": pc_b}, timeout=15)
    assert r2.json()["count"] == 0


# ─────────────────── ADMIN PUSH-TO-LICENSE ───────────────────

def test_admin_push_wrong_key_403(premium_key):
    r = requests.post(f"{API}/sync/admin/push-to-license", json={
        "admin_license_key": "FAKEFAKEFAKEFAKE",
        "admin_install_id": "admin-fake-1",
        "target_license_key": premium_key,
        "data": {"x": 1}, "label": "hack"
    }, timeout=15)
    assert r.status_code == 403, r.text


def test_admin_push_to_master_own_license():
    admin_iid = f"adminPC-{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/sync/admin/push-to-license", json={
        "admin_license_key": MASTER,
        "admin_install_id": admin_iid,
        "target_license_key": MASTER,
        "data": {"caja.v1": {"2026-01-05": [{"id": "master-self"}]}},
        "label": "Copia self-master"
    }, timeout=15)
    assert r.status_code == 200, r.text
    # Verificar pending desde un install_id distinto de "admin:<...>"
    r2 = requests.get(f"{API}/sync/backup/pending",
                      params={"license_key": MASTER, "install_id": "some-other-master-pc"},
                      timeout=15)
    assert r2.status_code == 200
    # Puede haber otras, pero al menos 1 con label "Copia self-master"
    labels = [p.get("label") for p in r2.json()["pending"]]
    assert "Copia self-master" in labels
    # Cleanup: consume desde ese install_id para no dejar basura
    for p in r2.json()["pending"]:
        if p.get("label") == "Copia self-master":
            requests.post(f"{API}/sync/backup/consume", json={
                "license_key": MASTER, "install_id": "some-other-master-pc",
                "backup_id": p["backup_id"]
            }, timeout=15)


def test_admin_push_to_client_upsert_only_latest(premium_key, install_ids):
    pc_a, pc_b = install_ids
    admin_iid = "adminPC-iter38"

    # 1st push (default label)
    r1 = requests.post(f"{API}/sync/admin/push-to-license", json={
        "admin_license_key": MASTER, "admin_install_id": admin_iid,
        "target_license_key": premium_key,
        "data": {"caja.v1": {"2026-02-01": [{"id": "admin-1"}]}}
    }, timeout=15)
    assert r1.status_code == 200, r1.text

    # 2nd push (custom label) → upsert reemplaza
    r2 = requests.post(f"{API}/sync/admin/push-to-license", json={
        "admin_license_key": MASTER, "admin_install_id": admin_iid,
        "target_license_key": premium_key,
        "data": {"caja.v1": {"2026-02-02": [{"id": "admin-2"}]}},
        "label": "Mi label custom"
    }, timeout=15)
    assert r2.status_code == 200

    # Cliente (PC-B) ve solo 1 pendiente del admin
    r = requests.get(f"{API}/sync/backup/pending",
                     params={"license_key": premium_key, "install_id": pc_b}, timeout=15)
    admin_pending = [p for p in r.json()["pending"]
                     if str(p.get("from_install_id", "")).startswith("admin:")]
    assert len(admin_pending) == 1, admin_pending
    assert admin_pending[0]["label"] == "Mi label custom"
    assert "caja.v1" in admin_pending[0]["data"]
    assert "2026-02-02" in admin_pending[0]["data"]["caja.v1"]

    # Sin label → default label
    r3 = requests.post(f"{API}/sync/admin/push-to-license", json={
        "admin_license_key": MASTER, "admin_install_id": admin_iid,
        "target_license_key": premium_key,
        "data": {"caja.v1": {"2026-02-03": [{"id": "admin-3"}]}}
    }, timeout=15)
    assert r3.status_code == 200
    r = requests.get(f"{API}/sync/backup/pending",
                     params={"license_key": premium_key, "install_id": pc_b}, timeout=15)
    admin_pending = [p for p in r.json()["pending"]
                     if str(p.get("from_install_id", "")).startswith("admin:")]
    assert len(admin_pending) == 1
    assert admin_pending[0]["label"] == "Copia enviada por MediCar Plus (admin)"


# ─────────────────── ADMIN RESET-DEVICES ───────────────────

def test_admin_reset_wrong_key_403(premium_key):
    r = requests.post(f"{API}/sync/admin/reset-devices", json={
        "admin_license_key": "FAKEFAKEFAKEFAKE",
        "target_license_key": premium_key
    }, timeout=15)
    assert r.status_code == 403, r.text


def test_admin_reset_target_not_found():
    r = requests.post(f"{API}/sync/admin/reset-devices", json={
        "admin_license_key": MASTER,
        "target_license_key": "NONEXISTENT-LICENSE-XYZ-DOESNOTEXIST"
    }, timeout=15)
    assert r.status_code == 404, r.text


def test_admin_reset_frees_slots(premium_key):
    # Reset first
    r = requests.post(f"{API}/sync/admin/reset-devices", json={
        "admin_license_key": MASTER, "target_license_key": premium_key
    }, timeout=15)
    assert r.status_code == 200

    # Fill 2 slots
    id1 = f"reset-A-{uuid.uuid4().hex[:6]}"
    id2 = f"reset-B-{uuid.uuid4().hex[:6]}"
    id3 = f"reset-C-{uuid.uuid4().hex[:6]}"
    assert requests.post(f"{API}/sync/heartbeat", json={"license_key": premium_key, "install_id": id1}).json()["authorized"]
    assert requests.post(f"{API}/sync/heartbeat", json={"license_key": premium_key, "install_id": id2}).json()["authorized"]
    # 3rd rejected
    r3 = requests.post(f"{API}/sync/heartbeat", json={"license_key": premium_key, "install_id": id3})
    assert r3.json()["authorized"] is False

    # Reset
    r_reset = requests.post(f"{API}/sync/admin/reset-devices", json={
        "admin_license_key": MASTER, "target_license_key": premium_key
    }, timeout=15)
    assert r_reset.status_code == 200
    assert r_reset.json()["removed"] >= 2

    # Ahora id3 debería entrar
    r4 = requests.post(f"{API}/sync/heartbeat", json={"license_key": premium_key, "install_id": id3})
    assert r4.json()["authorized"] is True
