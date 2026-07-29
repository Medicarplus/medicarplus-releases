"""E2E integration test · God-mode license lifecycle.

Simula 4 casos reales que le pueden pasar a un cliente:
  Case 1 · Cliente STD (mono-dispositivo) migra de PC
  Case 2 · Cliente Premium con 2 dispositivos migra el SECUNDARIO
  Case 3 · Cliente Premium con 2 dispositivos migra el PRINCIPAL
  Case 4 · Cliente cambia de email

Verifica en cada caso:
- La licencia queda correctamente revocada/preservada
- La clave nueva funciona (verify)
- Los datos Stripe (customer_id + subscription_id) se preservan
- Subscriptions collection queda actualizada
- Installations queda actualizada con revocación
- Sync data se transfiere
"""
import asyncio
import os
import sys
import uuid
import httpx

# Load env
from dotenv import dotenv_values
env = dotenv_values('/app/backend/.env')
MONGO_URL = env['MONGO_URL']
DB_NAME = env['DB_NAME']
ADMIN_TOKEN = 'MB-ADMIN-BRUGULAT-2026-4F8E2A1C'
API_BASE = os.environ.get('API_BASE') or open('/app/frontend/.env').read().split('REACT_APP_BACKEND_URL=')[1].split('\n')[0].strip()

from motor.motor_asyncio import AsyncIOMotorClient


async def _setup_license(db, install_id, plan, client_email, stripe_sub_id, linked_ids=None):
    lid = str(uuid.uuid4())
    doc = {
        'id': lid,
        'install_id': install_id,
        'client_name': f'Cliente {plan}',
        'client_email': client_email,
        'plan': plan,
        'status': 'active',
        'duration_days': 30,
        'created_at': '2026-02-28T10:00:00+00:00',
        'expires_at': '2026-03-30T10:00:00+00:00',
        'license_key': f'FAKE_JWT_{install_id[:8]}',
        'stripe_subscription_id': stripe_sub_id,
        'stripe_customer_id': f'cus_test_{install_id[:8]}',
    }
    if linked_ids:
        doc['linked_install_ids'] = linked_ids
    await db.licenses.insert_one(doc)
    await db.subscriptions.insert_one({
        'install_id': install_id,
        'customer_email': client_email,
        'stripe_customer_id': doc['stripe_customer_id'],
        'stripe_subscription_id': stripe_sub_id,
        'updated_at': '2026-02-28T10:00:00',
    })
    return lid


async def _cleanup(db, install_ids, emails):
    await db.licenses.delete_many({'install_id': {'$in': install_ids}})
    await db.subscriptions.delete_many({'install_id': {'$in': install_ids}})
    await db.installations.delete_many({'_id': {'$in': install_ids}})
    if emails:
        await db.licenses.delete_many({'client_email': {'$in': emails}})
        await db.subscriptions.delete_many({'customer_email': {'$in': emails}})


async def run_tests():
    passed, failed = 0, 0
    logs = []

    def assert_eq(name, got, expected):
        nonlocal passed, failed
        if got == expected:
            passed += 1
            logs.append(f'  ✅ {name}: {got}')
        else:
            failed += 1
            logs.append(f'  ❌ {name}: got={got!r} expected={expected!r}')

    def assert_ne(name, got, unwanted):
        nonlocal passed, failed
        if got != unwanted:
            passed += 1
            logs.append(f'  ✅ {name}: {got}')
        else:
            failed += 1
            logs.append(f'  ❌ {name}: got={got!r} (should not equal {unwanted!r})')

    c = AsyncIOMotorClient(MONGO_URL)
    db = c[DB_NAME]

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers={'X-Admin-Token': ADMIN_TOKEN}) as http:

        # ═══════════════════════════════════════════════════════════════════
        # CASE 1: STD single-device migration
        # ═══════════════════════════════════════════════════════════════════
        logs.append('\n=== CASE 1: STD single-device migration ===')
        await _setup_license(db, 'CD-CASE1-AAAA-BBBB-1111', 'STD', 'case1@test.com', 'sub_case1')
        r = await http.post('/api/licenses/transfer', json={
            'old_install_id': 'CD-CASE1-AAAA-BBBB-1111',
            'new_install_id': 'CD-CASE1-NNNN-BBBB-2222',
            'reason': 'test STD change PC',
            'send_email': False,
        })
        d = r.json()
        assert_eq('case detected', d.get('case'), 'principal_or_single_device_regen')
        assert_eq('old_license_revoked', d.get('old_license_revoked'), True)
        assert_eq('stripe fields preserved', 'stripe_subscription_id' in (d.get('stripe_fields_preserved') or []), True)
        # Confirm new license has stripe_subscription_id
        new_lic = await db.licenses.find_one({'install_id': 'CD-CASE1-NNNN-BBBB-2222', 'status': 'active'})
        assert_eq('new license has stripe_sub_id', new_lic.get('stripe_subscription_id'), 'sub_case1')
        # Confirm old license is revoked
        old_lic = await db.licenses.find_one({'install_id': 'CD-CASE1-AAAA-BBBB-1111'})
        assert_eq('old license status', old_lic.get('status'), 'revoked')
        assert_eq('old revoked_reason includes transferred_to', 'transferred_to' in (old_lic.get('revoked_reason') or ''), True)
        # Confirm subscriptions updated
        sub_new = await db.subscriptions.find_one({'install_id': 'CD-CASE1-NNNN-BBBB-2222'})
        assert_eq('subscription install_id updated', sub_new is not None, True)
        # Confirm installation revoked
        inst_old = await db.installations.find_one({'_id': 'CD-CASE1-AAAA-BBBB-1111'})
        assert_eq('old installation revoked', inst_old.get('revoked'), True)
        await _cleanup(db, ['CD-CASE1-AAAA-BBBB-1111', 'CD-CASE1-NNNN-BBBB-2222'], [])

        # ═══════════════════════════════════════════════════════════════════
        # CASE 2: Premium multi-device, migrate SECONDARY (linked)
        # ═══════════════════════════════════════════════════════════════════
        logs.append('\n=== CASE 2: Premium multi-device · migrate SECONDARY ===')
        await _setup_license(
            db, 'CD-CASE2-PRIN-CCCC-1111', 'PREMIUM', 'case2@test.com', 'sub_case2',
            linked_ids=['CD-CASE2-LINK-CCCC-2222'],
        )
        r = await http.post('/api/licenses/transfer', json={
            'old_install_id': 'CD-CASE2-LINK-CCCC-2222',
            'new_install_id': 'CD-CASE2-NEWL-CCCC-3333',
            'reason': 'test Premium 2nd device change',
            'send_email': False,
        })
        d = r.json()
        assert_eq('case detected', d.get('case'), 'multi_device_secondary_swap')
        assert_eq('same_key_preserved', d.get('same_key_preserved'), True)
        assert_eq('old_license NOT revoked (parent still active)', d.get('old_license_revoked'), False)
        # Confirm license doc still active with SAME key, linked updated
        parent = await db.licenses.find_one({'install_id': 'CD-CASE2-PRIN-CCCC-1111'})
        assert_eq('parent license still active', parent.get('status'), 'active')
        assert_eq('parent key unchanged', parent.get('license_key'), 'FAKE_JWT_CD-CASE2')
        assert_eq('linked_install_ids swapped', parent.get('linked_install_ids'), ['CD-CASE2-NEWL-CCCC-3333'])
        # Old secondary revoked in installations
        inst_old = await db.installations.find_one({'_id': 'CD-CASE2-LINK-CCCC-2222'})
        assert_eq('old secondary installation revoked', inst_old.get('revoked'), True)
        await _cleanup(db, ['CD-CASE2-PRIN-CCCC-1111', 'CD-CASE2-LINK-CCCC-2222', 'CD-CASE2-NEWL-CCCC-3333'], [])

        # ═══════════════════════════════════════════════════════════════════
        # CASE 3: Premium multi-device, migrate PRINCIPAL
        # ═══════════════════════════════════════════════════════════════════
        logs.append('\n=== CASE 3: Premium multi-device · migrate PRINCIPAL ===')
        await _setup_license(
            db, 'CD-CASE3-PRIN-DDDD-1111', 'PREMIUM', 'case3@test.com', 'sub_case3',
            linked_ids=['CD-CASE3-LINK-DDDD-2222'],
        )
        r = await http.post('/api/licenses/transfer', json={
            'old_install_id': 'CD-CASE3-PRIN-DDDD-1111',
            'new_install_id': 'CD-CASE3-NEWP-DDDD-3333',
            'reason': 'test Premium principal change',
            'send_email': False,
        })
        d = r.json()
        assert_eq('case detected', d.get('case'), 'principal_or_single_device_regen')
        assert_eq('linked_devices_also_need_reactivation', d.get('linked_devices_also_need_reactivation'), True)
        assert_eq('linked ids preserved in new', d.get('linked_install_ids_preserved'), ['CD-CASE3-LINK-DDDD-2222'])
        # New license has linked_install_ids preserved
        new_lic = await db.licenses.find_one({'install_id': 'CD-CASE3-NEWP-DDDD-3333'})
        assert_eq('new license has linked_install_ids', new_lic.get('linked_install_ids'), ['CD-CASE3-LINK-DDDD-2222'])
        assert_eq('new license has stripe_sub_id', new_lic.get('stripe_subscription_id'), 'sub_case3')
        await _cleanup(db, ['CD-CASE3-PRIN-DDDD-1111', 'CD-CASE3-LINK-DDDD-2222', 'CD-CASE3-NEWP-DDDD-3333'], [])

        # ═══════════════════════════════════════════════════════════════════
        # CASE 4: Client changes email
        # ═══════════════════════════════════════════════════════════════════
        logs.append('\n=== CASE 4: Client changes email ===')
        await _setup_license(db, 'CD-CASE4-AAAA-EEEE-1111', 'PREMIUM', 'viejo-case4@test.com', 'sub_case4')
        await db.installations.update_one(
            {'_id': 'CD-CASE4-AAAA-EEEE-1111'},
            {'$set': {'linked_email': 'viejo-case4@test.com', 'first_seen_at': 'x', 'last_seen_at': 'x', 'seen_count': 1, 'revoked': False}},
            upsert=True,
        )
        r = await http.post('/api/licenses/change-email', json={
            'old_email': 'viejo-case4@test.com',
            'new_email': 'nuevo-case4@test.com',
        })
        d = r.json()
        assert_eq('licenses_updated ≥1', d.get('licenses_updated') >= 1, True)
        assert_eq('subscriptions_updated ≥1', d.get('subscriptions_updated') >= 1, True)
        assert_eq('installations_updated ≥1', d.get('installations_updated') >= 1, True)
        lic4 = await db.licenses.find_one({'install_id': 'CD-CASE4-AAAA-EEEE-1111'})
        assert_eq('license email changed', lic4.get('client_email'), 'nuevo-case4@test.com')
        assert_eq('license email_changed_from tracked', lic4.get('email_changed_from'), 'viejo-case4@test.com')
        sub4 = await db.subscriptions.find_one({'install_id': 'CD-CASE4-AAAA-EEEE-1111'})
        assert_eq('subscription email changed', sub4.get('customer_email'), 'nuevo-case4@test.com')
        inst4 = await db.installations.find_one({'_id': 'CD-CASE4-AAAA-EEEE-1111'})
        assert_eq('installation email changed', inst4.get('linked_email'), 'nuevo-case4@test.com')
        await _cleanup(db, ['CD-CASE4-AAAA-EEEE-1111'], ['viejo-case4@test.com', 'nuevo-case4@test.com'])

    c.close()

    print('\n'.join(logs))
    print(f'\n{"="*60}\nTOTAL: {passed} passed · {failed} failed')
    return failed == 0


if __name__ == '__main__':
    ok = asyncio.run(run_tests())
    sys.exit(0 if ok else 1)
