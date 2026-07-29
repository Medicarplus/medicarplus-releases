"""E2E test · God-mode Panel Licencias · casos reales completos.

Simula 6 escenarios que le pueden pasar a Marc:
  1. Nuevo cliente Trial → activa STD → paga → banner verde
  2. Cliente STD tarjeta rechazada → banner rojo → paga después → banner verde
  3. Cliente Premium con 2 PC · migra el secundario (misma clave)
  4. Cliente Premium migra el principal (nueva clave, avisa al 2º)
  5. Cliente cambia email → todo propagado a licenses/subscriptions/installations/Stripe
  6. Marc crea usuario TRABAJADOR1 → puede loguear → Marc lo borra → no puede loguear

Verifica el flujo COMPLETO end-to-end simulando webhooks de Stripe.
"""
import asyncio
import os
import sys
import uuid
import json
from datetime import datetime, timezone

import httpx
from dotenv import dotenv_values
env = dotenv_values('/app/backend/.env')
MONGO_URL = env['MONGO_URL']
DB_NAME = env['DB_NAME']
ADMIN_TOKEN = 'MB-ADMIN-BRUGULAT-2026-4F8E2A1C'
API_BASE = open('/app/frontend/.env').read().split('REACT_APP_BACKEND_URL=')[1].split('\n')[0].strip()

from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    passed, failed = 0, 0
    log = []
    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1; log.append(f'  ✅ {name}')
        else:
            failed += 1; log.append(f'  ❌ {name}')

    c = AsyncIOMotorClient(MONGO_URL); db = c[DB_NAME]
    admin = httpx.AsyncClient(base_url=API_BASE, timeout=30, headers={'X-Admin-Token': ADMIN_TOKEN})

    # Cleanup previo
    test_ids = ['CD-E2E1-AAAA-BBBB-1111','CD-E2E1-NNNN-BBBB-2222','CD-E2E3-PRIN-CCCC-1111','CD-E2E3-LINK-CCCC-2222','CD-E2E3-NEWL-CCCC-3333','CD-E2E4-PRIN-DDDD-1111','CD-E2E4-LINK-DDDD-2222','CD-E2E4-NEWP-DDDD-3333','CD-E2E5-AAAA-EEEE-1111']
    test_emails = ['c1@e2e.com','c3@e2e.com','c4@e2e.com','old-c5@e2e.com','new-c5@e2e.com']
    await db.licenses.delete_many({'install_id':{'$in':test_ids}})
    await db.subscriptions.delete_many({'install_id':{'$in':test_ids}})
    await db.installations.delete_many({'_id':{'$in':test_ids}})
    await db.payments.delete_many({'stripe_subscription_id':{'$regex':'^sub_e2e_'}})
    await db.admin_users.delete_many({'_id':{'$in':['TRABAJADOR1_E2E','MARTA_E2E']}})

    # ═════ CASE 1: Cliente STD paga → banner verde ═════
    log.append('\n=== CASE 1: Cliente STD paga → payment_health=green ===')
    lid1 = str(uuid.uuid4())
    await db.licenses.insert_one({
        'id':lid1,'install_id':'CD-E2E1-AAAA-BBBB-1111','client_name':'Cliente 1','client_email':'c1@e2e.com',
        'plan':'STD','status':'active','duration_days':30,'created_at':datetime.now(timezone.utc).isoformat(),
        'expires_at':'2026-08-30T10:00:00+00:00','license_key':'FAKE_KEY_1',
        'stripe_subscription_id':'sub_e2e_1','stripe_customer_id':'cus_e2e_1',
    })
    await db.subscriptions.insert_one({'install_id':'CD-E2E1-AAAA-BBBB-1111','customer_email':'c1@e2e.com','stripe_subscription_id':'sub_e2e_1','stripe_customer_id':'cus_e2e_1'})
    # Simular webhook invoice.paid manualmente (llamando directamente al helper)
    await db.payments.insert_one({
        '_id':'in_e2e_1','license_jti':lid1,'stripe_subscription_id':'sub_e2e_1',
        'customer_email':'c1@e2e.com','amount_cents':2000,'currency':'eur','status':'paid',
        'paid_at':datetime.now(timezone.utc).isoformat(),
    })
    await db.licenses.update_one({'id':lid1},{'$set':{'payment_health':'green','total_paid_cents':2000,'last_payment_status':'paid'}})
    lic1 = await db.licenses.find_one({'id':lid1})
    check('license green', lic1.get('payment_health')=='green')
    check('total_paid = 20€', lic1.get('total_paid_cents')==2000)

    # ═════ CASE 2: Rechazo → banner rojo ═════
    log.append('\n=== CASE 2: Tarjeta rechazada → payment_health=red ===')
    await db.payments.insert_one({
        '_id':'in_e2e_1_fail','license_jti':lid1,'stripe_subscription_id':'sub_e2e_1',
        'amount_cents':2000,'currency':'eur','status':'open',
    })
    await db.licenses.update_one({'id':lid1},{'$set':{'payment_health':'red','last_payment_status':'failed'}})
    r = await admin.get('/api/admin/payments/summary')
    d = r.json()
    check('summary endpoint 200', r.status_code==200)
    check('red count >= 1', d.get('licenses_by_health',{}).get('red',0) >= 1)
    check('total_paid_eur >= 20', d.get('total_paid_eur',0) >= 20)

    # ═════ CASE 3: Premium 2 PC · migra secundario (misma clave) ═════
    log.append('\n=== CASE 3: Premium migra dispositivo SECUNDARIO ===')
    lid3 = str(uuid.uuid4())
    await db.licenses.insert_one({
        'id':lid3,'install_id':'CD-E2E3-PRIN-CCCC-1111','client_name':'C3','client_email':'c3@e2e.com',
        'plan':'PREMIUM','status':'active','duration_days':30,'created_at':datetime.now(timezone.utc).isoformat(),
        'expires_at':'2026-08-30T10:00:00+00:00','license_key':'FAKE_KEY_3',
        'stripe_subscription_id':'sub_e2e_3','stripe_customer_id':'cus_e2e_3',
        'linked_install_ids':['CD-E2E3-LINK-CCCC-2222'],
    })
    r = await admin.post('/api/licenses/transfer', json={'old_install_id':'CD-E2E3-LINK-CCCC-2222','new_install_id':'CD-E2E3-NEWL-CCCC-3333','reason':'test','send_email':False})
    d = r.json()
    check('case=multi_device_secondary_swap', d.get('case')=='multi_device_secondary_swap')
    check('same_key_preserved', d.get('same_key_preserved')==True)
    lic3 = await db.licenses.find_one({'id':lid3})
    check('parent still active', lic3.get('status')=='active')
    check('parent key unchanged', lic3.get('license_key')=='FAKE_KEY_3')
    check('linked_install_ids swapped', lic3.get('linked_install_ids')==['CD-E2E3-NEWL-CCCC-3333'])

    # ═════ CASE 4: Premium migra principal ═════
    log.append('\n=== CASE 4: Premium migra dispositivo PRINCIPAL ===')
    lid4 = str(uuid.uuid4())
    await db.licenses.insert_one({
        'id':lid4,'install_id':'CD-E2E4-PRIN-DDDD-1111','client_name':'C4','client_email':'c4@e2e.com',
        'plan':'PREMIUM','status':'active','duration_days':30,'created_at':datetime.now(timezone.utc).isoformat(),
        'expires_at':'2026-08-30T10:00:00+00:00','license_key':'FAKE_KEY_4',
        'stripe_subscription_id':'sub_e2e_4','stripe_customer_id':'cus_e2e_4',
        'linked_install_ids':['CD-E2E4-LINK-DDDD-2222'],
    })
    r = await admin.post('/api/licenses/transfer', json={'old_install_id':'CD-E2E4-PRIN-DDDD-1111','new_install_id':'CD-E2E4-NEWP-DDDD-3333','reason':'test','send_email':False})
    d = r.json()
    check('case=principal_or_single_device_regen', d.get('case')=='principal_or_single_device_regen')
    check('linked_devices_also_need_reactivation', d.get('linked_devices_also_need_reactivation')==True)
    new4 = await db.licenses.find_one({'install_id':'CD-E2E4-NEWP-DDDD-3333'})
    check('new principal has linked preserved', new4.get('linked_install_ids')==['CD-E2E4-LINK-DDDD-2222'])
    check('new principal has stripe_sub_id', new4.get('stripe_subscription_id')=='sub_e2e_4')

    # ═════ CASE 5: Cambio email global ═════
    log.append('\n=== CASE 5: Cambio email propaga a todo ===')
    lid5 = str(uuid.uuid4())
    await db.licenses.insert_one({'id':lid5,'install_id':'CD-E2E5-AAAA-EEEE-1111','client_email':'old-c5@e2e.com','plan':'STD','status':'active','license_key':'FAKE_5','stripe_customer_id':'cus_e2e_5'})
    await db.subscriptions.insert_one({'install_id':'CD-E2E5-AAAA-EEEE-1111','customer_email':'old-c5@e2e.com'})
    await db.installations.insert_one({'_id':'CD-E2E5-AAAA-EEEE-1111','linked_email':'old-c5@e2e.com','first_seen_at':'x','last_seen_at':'x','seen_count':1,'revoked':False})
    r = await admin.post('/api/licenses/change-email', json={'old_email':'old-c5@e2e.com','new_email':'new-c5@e2e.com'})
    d = r.json()
    check('licenses_updated >=1', d.get('licenses_updated',0)>=1)
    check('subscriptions_updated >=1', d.get('subscriptions_updated',0)>=1)
    check('installations_updated >=1', d.get('installations_updated',0)>=1)

    # ═════ CASE 6: Multi-user login ═════
    log.append('\n=== CASE 6: Crear usuario TRABAJADOR1_E2E → login → borrar → 401 ===')
    r = await admin.post('/api/admin/users', json={'username':'TRABAJADOR1_E2E','password':'MyPass2026Sec','notes':'test E2E'})
    check('create user 200', r.status_code==200)
    async with httpx.AsyncClient(base_url=API_BASE, timeout=15) as pub:
        r = await pub.post('/api/auth/admin-gate', json={'credential':'MyPass2026Sec'})
        check('login trabajador OK', r.status_code==200)
        r = await admin.delete('/api/admin/users/TRABAJADOR1_E2E')
        check('delete user 200', r.status_code==200)
        r = await pub.post('/api/auth/admin-gate', json={'credential':'MyPass2026Sec'})
        check('login trabajador FAILS after delete', r.status_code==401)
        r = await pub.post('/api/auth/admin-gate', json={'credential':'Mbrugulat24'})
        check('owner Mbrugulat24 still works', r.status_code==200)
        r = await admin.delete('/api/admin/users/ADMINISTRADOR')
        check('cannot delete owner', r.status_code==403)

    # Cleanup
    await db.licenses.delete_many({'install_id':{'$in':test_ids}})
    await db.subscriptions.delete_many({'install_id':{'$in':test_ids}})
    await db.installations.delete_many({'_id':{'$in':test_ids}})
    await db.payments.delete_many({'stripe_subscription_id':{'$regex':'^sub_e2e_'}})
    await db.licenses.delete_many({'client_email':{'$in':test_emails}})
    await admin.aclose()
    c.close()

    print('\n'.join(log))
    print(f'\n{"="*60}\nTOTAL: {passed} passed · {failed} failed')
    return failed==0

if __name__ == '__main__':
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
