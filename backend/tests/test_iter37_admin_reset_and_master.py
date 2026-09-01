"""Iteration 37 · Verificación completa de:
  1. Nuevo endpoint POST /api/sync/admin/reset-devices
  2. Ciclo real MASTER: 2 PCs autorizados + PC3 rechazado + reset libera slots
  3. Escenario PREMIUM E2E completo (2 PCs push/pull + backup manual)
  4. Endpoint admin/list-licenses (30+ clientes reales)

Ejecutable con pytest o directo. Backend URL: REACT_APP_BACKEND_URL del frontend/.env.
"""
import os
import sys
import uuid
import hashlib
import asyncio
import pytest
import httpx
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# Use the public preview URL (what user sees)
FRONTEND_ENV = "/app/frontend/.env"
BASE_URL = None
with open(FRONTEND_ENV) as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL"):
            BASE_URL = line.split("=", 1)[1].strip()

assert BASE_URL, "REACT_APP_BACKEND_URL missing"
API = BASE_URL.rstrip("/")
MASTER_KEY = "MB-MASTER-BRUGULAT-2026-OWNER"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def _hash(k: str) -> str:
    return hashlib.sha256(k.strip().encode()).hexdigest()


@pytest.fixture
def db():
    client = AsyncIOMotorClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture
async def premium_license(db):
    """Create a TEST_ prefixed Premium license, yield the key, cleanup after."""
    key = f"TEST_PRM_ITER37_{uuid.uuid4().hex[:10]}"
    doc = {
        "id": str(uuid.uuid4()),
        "install_id": "TEST_BASE",
        "license_key": key,
        "plan": "PRM",
        "plan_family": "PRM",
        "status": "active",
        "client_email": "TEST_iter37@medicarplus.es",
        "client_name": "Iter37 Premium Test",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
    }
    await db.licenses.insert_one(doc)
    yield key
    h = _hash(key)
    await db.licenses.delete_many({"license_key": key})
    await db.sync_devices.delete_many({"license_key_hash": h})
    await db.sync_states.delete_many({"_id": h})
    await db.sync_backups.delete_many({"license_key_hash": h})


# ────────────────────────── MASTER: reset devices ──────────────────────────

@pytest.mark.asyncio
async def test_master_reset_before_and_authorize_two(db):
    """MASTER: reset → PC1 auth → PC2 auth → PC3 rechazado."""
    master_h = _hash(MASTER_KEY)
    PC1, PC2, PC3 = f"TEST_M1_{uuid.uuid4().hex[:6]}", f"TEST_M2_{uuid.uuid4().hex[:6]}", f"TEST_M3_{uuid.uuid4().hex[:6]}"
    async with httpx.AsyncClient(base_url=API, timeout=15.0) as ac:
        # Pre-clean via reset
        r = await ac.post("/api/sync/admin/reset-devices",
                          json={"admin_license_key": MASTER_KEY, "target_license_key": MASTER_KEY})
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        # PC1
        r = await ac.post("/api/sync/heartbeat", json={"license_key": MASTER_KEY, "install_id": PC1})
        assert r.status_code == 200
        j = r.json()
        assert j["authorized"] is True
        assert j["is_premium"] is True
        assert j["max_devices"] == 2
        # PC2
        r = await ac.post("/api/sync/heartbeat", json={"license_key": MASTER_KEY, "install_id": PC2})
        j = r.json()
        assert j["authorized"] is True
        assert j["current_devices"] == 2
        # PC3 rejected
        r = await ac.post("/api/sync/heartbeat", json={"license_key": MASTER_KEY, "install_id": PC3})
        j = r.json()
        assert j["authorized"] is False
        assert j["device_limit_reached"] is True
        # Now RESET again → slots freed → PC3 accepted
        r = await ac.post("/api/sync/admin/reset-devices",
                          json={"admin_license_key": MASTER_KEY, "target_license_key": MASTER_KEY})
        assert r.json()["removed"] >= 2
        r = await ac.post("/api/sync/heartbeat", json={"license_key": MASTER_KEY, "install_id": PC3})
        assert r.json()["authorized"] is True
    # cleanup MASTER sync_devices to leave clean state
    await db.sync_devices.delete_many({"license_key_hash": master_h})


@pytest.mark.asyncio
async def test_admin_reset_devices_403_wrong_key():
    async with httpx.AsyncClient(base_url=API, timeout=15.0) as ac:
        r = await ac.post("/api/sync/admin/reset-devices",
                          json={"admin_license_key": "FAKE-KEY-WRONG-12345",
                                "target_license_key": MASTER_KEY})
        assert r.status_code == 403, r.text
        assert r.json()["detail"] == "admin_only"


@pytest.mark.asyncio
async def test_admin_reset_devices_404_target_not_found():
    async with httpx.AsyncClient(base_url=API, timeout=15.0) as ac:
        r = await ac.post("/api/sync/admin/reset-devices",
                          json={"admin_license_key": MASTER_KEY,
                                "target_license_key": "NONEXISTENT-LICENSE-XYZ-999"})
        assert r.status_code == 404, r.text
        assert r.json()["detail"] == "target_license_not_found"


# ────────────────────────── admin list-licenses ──────────────────────────

@pytest.mark.asyncio
async def test_admin_list_licenses_master():
    async with httpx.AsyncClient(base_url=API, timeout=15.0) as ac:
        r = await ac.get(f"/api/sync/admin/list-licenses?admin_license_key={MASTER_KEY}")
        assert r.status_code == 200
        j = r.json()
        assert "licenses" in j and isinstance(j["licenses"], list)
        # Expect at least a handful of real licenses (per request ~30)
        assert j["count"] >= 1
        # Shape check
        if j["licenses"]:
            sample = j["licenses"][0]
            for f in ("license_key", "plan"):
                assert f in sample


@pytest.mark.asyncio
async def test_admin_list_licenses_403_fake():
    async with httpx.AsyncClient(base_url=API, timeout=15.0) as ac:
        r = await ac.get("/api/sync/admin/list-licenses?admin_license_key=FAKE-KEY-XXX-9999")
        assert r.status_code == 403


# ─────────────────────── PREMIUM 2-PC full flow ───────────────────────

@pytest.mark.asyncio
async def test_premium_2pc_full_flow(db, premium_license):
    key = premium_license
    PC1 = f"TEST_CLI1_{uuid.uuid4().hex[:6]}"
    PC2 = f"TEST_CLI2_{uuid.uuid4().hex[:6]}"
    PC3 = f"TEST_CLI3_{uuid.uuid4().hex[:6]}"
    async with httpx.AsyncClient(base_url=API, timeout=15.0) as ac:
        # 1) heartbeats
        r1 = (await ac.post("/api/sync/heartbeat", json={"license_key": key, "install_id": PC1})).json()
        assert r1["authorized"] is True and r1["current_devices"] == 1
        r2 = (await ac.post("/api/sync/heartbeat", json={"license_key": key, "install_id": PC2})).json()
        assert r2["authorized"] is True and r2["current_devices"] == 2
        r3 = (await ac.post("/api/sync/heartbeat", json={"license_key": key, "install_id": PC3})).json()
        assert r3["authorized"] is False and r3["device_limit_reached"] is True
        # 2) both to linked
        for pc in (PC1, PC2):
            r = await ac.post("/api/sync/mode", json={"license_key": key, "install_id": pc, "mode": "linked"})
            assert r.status_code == 200
        # 3) PC1 push
        ts = datetime.now(timezone.utc).isoformat()
        r = await ac.post("/api/sync/push", json={
            "license_key": key, "install_id": PC1,
            "entries": {"caja.demo.iter37": {"value": {"amount": 100, "from": "PC1"}, "updated_at": ts}}
        })
        assert r.status_code == 200 and r.json()["written"] == 1
        # 4) PC2 pull → recibe
        r = await ac.get(f"/api/sync/pull?license_key={key}&install_id={PC2}")
        entries = r.json()["entries"]
        assert "caja.demo.iter37" in entries
        assert entries["caja.demo.iter37"]["value"]["from"] == "PC1"
        # 5) independent mode + backup manual
        for pc in (PC1, PC2):
            await ac.post("/api/sync/mode", json={"license_key": key, "install_id": pc, "mode": "independent"})
        r = await ac.post("/api/sync/backup/send", json={
            "license_key": key, "install_id": PC1,
            "data": {"caja.byDate.v1": {"2026-01-10": [{"id": "b1", "amount": 55}]}},
            "label": "TEST_iter37 manual"
        })
        assert r.status_code == 200
        backup_id = r.json()["backup_id"]
        # PC2 pending
        r = await ac.get(f"/api/sync/backup/pending?license_key={key}&install_id={PC2}")
        j = r.json()
        assert j["count"] == 1
        assert j["pending"][0]["backup_id"] == backup_id
        # consume
        r = await ac.post("/api/sync/backup/consume", json={
            "license_key": key, "install_id": PC2, "backup_id": backup_id
        })
        assert r.status_code == 200
        r = await ac.get(f"/api/sync/backup/pending?license_key={key}&install_id={PC2}")
        assert r.json()["count"] == 0


# ─────────────────── Admin reset-devices frees client slots ───────────────────

@pytest.mark.asyncio
async def test_admin_reset_frees_client_slots(db, premium_license):
    """Full cycle: 2 devices → limit reached → reset → new device accepted."""
    key = premium_license
    PC_A = f"TEST_A_{uuid.uuid4().hex[:6]}"
    PC_B = f"TEST_B_{uuid.uuid4().hex[:6]}"
    PC_C = f"TEST_C_{uuid.uuid4().hex[:6]}"
    async with httpx.AsyncClient(base_url=API, timeout=15.0) as ac:
        # Pre-reset to ensure clean slots
        await ac.post("/api/sync/admin/reset-devices",
                      json={"admin_license_key": MASTER_KEY, "target_license_key": key})
        await ac.post("/api/sync/heartbeat", json={"license_key": key, "install_id": PC_A})
        await ac.post("/api/sync/heartbeat", json={"license_key": key, "install_id": PC_B})
        r = await ac.post("/api/sync/heartbeat", json={"license_key": key, "install_id": PC_C})
        assert r.json()["authorized"] is False, "should hit device limit"
        r = await ac.post("/api/sync/admin/reset-devices",
                          json={"admin_license_key": MASTER_KEY, "target_license_key": key})
        assert r.status_code == 200
        assert r.json()["removed"] >= 2
        r = await ac.post("/api/sync/heartbeat", json={"license_key": key, "install_id": PC_C})
        assert r.json()["authorized"] is True
