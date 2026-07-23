"""Iteration 21 · Backend tests for multi-device Premium licensing, install_id
linking, and Stripe subscription update email.

Covers:
- TEST 1: Premium multi-device HWID lock (2 devices allowed, 3rd rejected)
- TEST 2: Standard single-device HWID lock (1 device, 2nd rejected + grammar)
- TEST 3: /api/licenses/current returns license via linked_install_ids
- TEST 4: _sync_license_from_subscription sends email on UPDATE with subject_prefix
"""
import os
import sys
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

import jwt
import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

load_dotenv('/app/backend/.env')

# Ensure backend module importable for direct fn tests
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ['REACT_APP_BACKEND_URL_PUBLIC'] if os.environ.get('REACT_APP_BACKEND_URL_PUBLIC') else 'https://project-helper-47.preview.emergentagent.com'
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
LICENSE_SECRET = os.environ['LICENSE_SECRET']
LICENSE_ISSUER = os.environ.get('LICENSE_ISSUER', 'caja-del-dia-license-server')


def _now():
    return datetime.now(timezone.utc)


def _mint_jwt(install_id: str, jti: str, plan: str, ttl_days: int = 365,
              portable_sub: str | None = None) -> str:
    """Mint JWT. Use portable_sub='CD-STRIPE-XXX' for multi-device Premium keys."""
    now = _now()
    exp = now + timedelta(days=ttl_days)
    return jwt.encode({
        'iss': LICENSE_ISSUER,
        'sub': portable_sub or install_id,
        'jti': jti,
        'plan': plan,
        'iat': int(now.timestamp()),
        'exp': int(exp.timestamp()),
    }, LICENSE_SECRET, algorithm='HS256')


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope='module')
def mongo_db():
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture(scope='module')
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def api():
    s = requests.Session()
    s.headers.update({'Content-Type': 'application/json'})
    return s


async def _seed_license(install_id: str, plan: str, jti: str | None = None,
                        portable: bool = True) -> dict:
    """Insert a license doc using a fresh async client bound to the current loop."""
    jti = jti or str(uuid.uuid4())
    now = _now()
    exp = now + timedelta(days=365)
    portable_sub = f'CD-STRIPE-TEST-{jti[:8].upper()}' if portable else None
    jwt_key = _mint_jwt(install_id, jti, plan, portable_sub=portable_sub)
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    await db.licenses.update_many(
        {'install_id': install_id, 'status': 'active'},
        {'$set': {'status': 'revoked', 'revoked_at': now.isoformat(),
                  'revoked_reason': 'test_reset'}}
    )
    doc = {
        'id': jti,
        'install_id': install_id,
        'client_name': f'TEST_{plan}_multi',
        'client_email': f'test_{plan.lower()}_multi@example.com',
        'plan': plan,
        'status': 'active',
        'duration_days': 365,
        'notes': 'iter21_test',
        'created_at': now.isoformat(),
        'expires_at': exp.isoformat(),
        'license_key': jwt_key,
        'verify_count': 0,
    }
    await db.licenses.insert_one(doc)
    client.close()
    return doc


def _sync_db():
    """Return a synchronous pymongo db handle (avoids motor event loop headaches)."""
    return MongoClient(MONGO_URL)[DB_NAME]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if asyncio.get_event_loop().is_running() is False else asyncio.new_event_loop().run_until_complete(coro)


def _sync(coro):
    """Run a coroutine in a fresh event loop (avoids 'Event loop is closed').

    Motor clients are bound to the loop they're first used on. To avoid
    cross-loop errors we accept a factory: pass a callable returning a coroutine
    when the coroutine needs to create its own motor client.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mongo():
    """Fresh motor client bound to current running loop."""
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


# ===========================================================================
# TEST 1 · Premium multi-device HWID lock
# ===========================================================================
class TestPremiumMultiDevice:
    """Premium license admits up to 2 HWIDs + 2 install_ids."""

    def test_premium_two_devices_allowed_third_rejected(self, api):
        install_id_1 = 'CD-PREM-DEV1-BUG1-1001'
        install_id_2 = 'CD-PREM-DEV2-BUG1-1002'
        install_id_3 = 'CD-PREM-DEV3-BUG1-1003'
        hwid_a = 'HW-PREM-A-001'
        hwid_b = 'HW-PREM-B-002'
        hwid_c = 'HW-PREM-C-003'
        # Seed premium license (portable JWT so it works on multiple devices)
        doc = _sync(_seed_license(install_id_1, 'PREMIUM'))
        key = doc['license_key']
        jti = doc['id']

        # Device 1 verify
        r1 = api.post(f"{BASE_URL}/api/licenses/verify", json={
            'key': key, 'install_id': install_id_1, 'hwid': hwid_a,
        })
        assert r1.status_code == 200, r1.text
        j1 = r1.json()
        assert j1['ok'] is True, f"Device 1 should be OK: {j1}"
        assert (j1.get('plan') or '').upper() == 'PREMIUM'

        # Device 2 verify (should be accepted as 2nd Premium device)
        r2 = api.post(f"{BASE_URL}/api/licenses/verify", json={
            'key': key, 'install_id': install_id_2, 'hwid': hwid_b,
        })
        assert r2.status_code == 200, r2.text
        j2 = r2.json()
        assert j2['ok'] is True, f"Device 2 SHOULD be allowed for Premium: {j2}"

        # Device 3 verify → must be rejected
        r3 = api.post(f"{BASE_URL}/api/licenses/verify", json={
            'key': key, 'install_id': install_id_3, 'hwid': hwid_c,
        })
        assert r3.status_code == 200, r3.text
        j3 = r3.json()
        assert j3['ok'] is False, f"Device 3 must be rejected: {j3}"
        assert j3.get('hwid_mismatch') is True, f"expected hwid_mismatch=true: {j3}"
        assert 'ya está en uso en 2 ordenadores' in (j3.get('reason') or ''), j3

        # Verify DB has linked_hwids=[hwid_b] and linked_install_ids=[install_id_2]
        stored = _sync_db().licenses.find_one({'id': jti})
        assert stored is not None
        assert stored.get('hwid_lock') == hwid_a
        assert stored.get('linked_hwids') == [hwid_b], f"linked_hwids: {stored.get('linked_hwids')}"
        assert stored.get('linked_install_ids') == [install_id_2], (
            f"linked_install_ids: {stored.get('linked_install_ids')}"
        )


# ===========================================================================
# TEST 2 · Standard single-device HWID lock
# ===========================================================================
class TestStandardSingleDevice:
    """Standard license only 1 HWID → 2nd is rejected with singular 'ordenador'."""

    def test_standard_second_device_rejected_singular_grammar(self, api):
        install_id_1 = 'CD-STDT-DEV1-BUG1-2001'
        install_id_2 = 'CD-STDT-DEV2-BUG1-2002'
        hwid_a = 'HW-STD-A-001'
        hwid_b = 'HW-STD-B-002'
        doc = _sync(_seed_license(install_id_1, 'STD'))
        key = doc['license_key']

        r1 = api.post(f"{BASE_URL}/api/licenses/verify", json={
            'key': key, 'install_id': install_id_1, 'hwid': hwid_a,
        })
        assert r1.status_code == 200, r1.text
        assert r1.json().get('ok') is True

        r2 = api.post(f"{BASE_URL}/api/licenses/verify", json={
            'key': key, 'install_id': install_id_2, 'hwid': hwid_b,
        })
        assert r2.status_code == 200, r2.text
        j2 = r2.json()
        assert j2['ok'] is False
        assert j2.get('hwid_mismatch') is True
        reason = j2.get('reason') or ''
        assert 'ya está en uso en 1 ordenador' in reason, f"Grammar/reason wrong: {reason}"
        assert 'ordenadores' not in reason, f"Should be singular, got: {reason}"


# ===========================================================================
# TEST 3 · /api/licenses/current with linked_install_ids
# ===========================================================================
class TestCurrentEndpointLinkedInstallIds:
    """/current endpoint must return license when queried by 2nd Premium install_id."""

    def test_current_returns_license_via_linked_install_id(self, api):
        install_id_1 = 'CD-PREM-DEV1-BUG1-3001'
        install_id_2 = 'CD-PREM-DEV2-BUG1-3002'
        hwid_a = 'HW-PREM-A-003'
        hwid_b = 'HW-PREM-B-003'

        doc = _sync(_seed_license(install_id_1, 'PREMIUM'))
        key = doc['license_key']
        jti = doc['id']

        # Verify device 1 and device 2 to populate linked_install_ids
        api.post(f"{BASE_URL}/api/licenses/verify", json={
            'key': key, 'install_id': install_id_1, 'hwid': hwid_a,
        })
        api.post(f"{BASE_URL}/api/licenses/verify", json={
            'key': key, 'install_id': install_id_2, 'hwid': hwid_b,
        })

        # Query /current by 2nd install_id
        r = api.get(f"{BASE_URL}/api/licenses/current",
                    params={'install_id': install_id_2})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get('found') is True, f"Should find via linked_install_ids: {j}"
        assert (j.get('plan') or '').upper() == 'PREMIUM'
        assert j.get('license_key') == key, "Same JWT for both devices"
        assert j.get('jti') == jti


# ===========================================================================
# TEST 4 · _sync_license_from_subscription sends email on UPDATE
# ===========================================================================
class TestStripeSubscriptionUpdateEmail:
    """
    Directly call server._sync_license_from_subscription with an existing license
    and verify the email path fires with subject_prefix 'Pla actualitzat a PREMIUM'.
    """

    def test_update_flow_calls_mailer_with_subject_prefix(self, monkeypatch):
        # Import the function under test after env is loaded
        import importlib
        server_mod = importlib.import_module('server')

        # Track calls to send_license_email
        captured = {}

        async def _fake_send(**kwargs):
            captured.update(kwargs)
            return True, 'test_ok'

        # Patch the mailer.send_license_email used inside _sync_license_from_subscription
        from services import mailer as _mailer
        monkeypatch.setattr(_mailer, 'send_license_email', _fake_send)

        db_client = AsyncIOMotorClient(MONGO_URL)
        db = db_client[DB_NAME]
        install_id = 'CD-STRP-UPGR-BUG1-4001'
        # Seed existing STD license so it goes through the UPDATE branch
        _sync(_seed_license(install_id, 'STD'))

        # Build fake Stripe subscription dict with status=active
        fake_sub = {
            'id': f'sub_test_iter21_{uuid.uuid4().hex[:8]}',
            'customer': 'cus_test_iter21',
            'status': 'active',
            'current_period_end': int((_now() + timedelta(days=30)).timestamp()),
            'cancel_at_period_end': False,
        }

        # Call the async function
        _sync(server_mod._sync_license_from_subscription(
            sub=fake_sub,
            install_id=install_id,
            package_id='PREMIUM_ANY',
            client_email='test_upgrade@example.com',
            company_name='Test Iter21',
        ))

        # Assertions: fake_send must have been called with subject_prefix
        assert 'subject_prefix' in captured, f"Mailer not called with subject_prefix. captured={captured}"
        sp = captured.get('subject_prefix') or ''
        assert 'Pla actualitzat a PREMIUM' in sp or 'PREMIUM' in sp, (
            f"subject_prefix should mention plan upgrade, got: {sp!r}"
        )
        assert captured.get('to_email') == 'test_upgrade@example.com'
        assert (captured.get('plan') or '').upper() == 'PREMIUM'
        assert captured.get('install_id') == install_id

        # Verify DB now has plan=PREMIUM
        updated = _sync_db().licenses.find_one({'install_id': install_id, 'status': 'active'})
        assert updated is not None
        assert (updated.get('plan') or '').upper() == 'PREMIUM'


# ---------------------------------------------------------------------------
# Teardown module-level: clean TEST_ data
# ---------------------------------------------------------------------------
def teardown_module(module):
    """Cleanup TEST_ data (sync)."""
    db = _sync_db()
    prefixes = ['CD-PREM-DEV', 'CD-STDT-DEV', 'CD-STRP-UPGR']
    for pref in prefixes:
        db.licenses.delete_many({'install_id': {'$regex': f'^{pref}'}})
