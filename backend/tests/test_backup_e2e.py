"""
🧪 TEST E2E · Sistema de copias en la nube · Feb 2026

Verifica end-to-end contra el backend REAL:
  1. Envío sin comprimir (legacy)
  2. Envío comprimido con gzip base64
  3. Recuperación descomprimida transparente
  4. Auto-registro de dispositivo en primer envío (MASTER + STD)
  5. Rotación de copias (últimas 30)
  6. Integridad SHA-256
  7. MASTER aparece en admin/list-licenses
  8. Stress con 3 años de datos (compresión >30x)
"""
import base64
import gzip
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime

import requests

API_URL = os.environ.get('BACKEND_URL', 'http://localhost:8001')
MASTER_KEY = "MB-MASTER-BRUGULAT-2026-OWNER"

# ─────────────────────────────────────────────────────────────────────
# Fixtures de datos
# ─────────────────────────────────────────────────────────────────────
def fixture_realistic():
    return {
        'caja.v1': json.dumps({'byDate': {'2026-02-28': {'rows': [
            {'id': 'e1', 'kind': 'TRAF', 'nombre': 'María López', 'importe': 145.55, 'tasa': 91.60, 'fp': 'E'},
            {'id': 'e2', 'kind': 'TRAF', 'nombre': 'Pedro Sanz',  'importe': 220.00, 'tasa': 91.60, 'fp': 'T'},
        ]}}}),
        'caja.saldoInicial.trafic.v1': json.dumps({'fecha': '2024-01-01', 'efectivo': 1250.75, 'banco': 8890.20, 'cambio': 200.00, 'nota': 'E1 apertura'}),
        'caja.saldoInicial.cempla.v1': json.dumps({'fecha': '2024-03-01', 'efectivo': 340.50, 'banco': 2100.00, 'cambio': 50.00, 'nota': 'E2 apertura'}),
        'caja.stats.v1': json.dumps({'data': {'2025-08': {'AUTOESCOLA MARTINEZ': 65}}}),
        'caja.config.v1': json.dumps({'company1': {'name': 'CENTRO EL PRAT'}, 'company2': {'name': 'CEMPLA'}, 'socios': [{'nombre': 'Juan', 'pct': 50}, {'nombre': 'María', 'pct': 50}]}),
        'caja.irpf.v1': json.dumps({'months': {'2024-Q1': 155.55}, 'quarters': {'2024-Q1': {'pagado': True}}}),
        'caja.reserva.v1': json.dumps({'billete_50': 4, 'moneda_2': 10}),
        'caja.cuadre.overrides.v1': json.dumps({'2025-12': {'caja_manual': 3250.15}}),
        'caja.calendar.urls.v1': json.dumps([{'name': 'Google', 'url': 'https://calendar.google.com/x.ics'}]),
        'caja.count_zero': '1',
    }


def fixture_stress_3years():
    """Simula 3 años de caja con ~30 entradas/día = ~30.000 filas"""
    days = {}
    for y in [2024, 2025, 2026]:
        for m in range(1, 13):
            for d in range(1, 29):
                key = f'{y}-{m:02d}-{d:02d}'
                days[key] = {'rows': [
                    {'id': f'{y}{m}{d}-{i}', 'kind': 'TRAF', 'nombre': f'Cliente {i}',
                     'importe': 145.55 + i, 'tasa': 91.60, 'fp': 'E', 'cat': 'inicial'}
                    for i in range(30)
                ]}
    return {'caja.v1': json.dumps({'byDate': days})}


def compress_gz_b64(data_dict):
    raw = json.dumps(data_dict)
    gz = gzip.compress(raw.encode('utf-8'), compresslevel=6)
    return base64.b64encode(gz).decode('ascii'), len(raw), len(gz)


def _post(path, body):
    r = requests.post(f'{API_URL}{path}', json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def _get(path):
    r = requests.get(f'{API_URL}{path}', timeout=30)
    r.raise_for_status()
    return r.json()


# ─────────────────────────────────────────────────────────────────────
# Cleanup helper
# ─────────────────────────────────────────────────────────────────────
def cleanup_install(install_id):
    """Elimina copias y devices de test para no ensuciar la BD."""
    try:
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        async def _clean():
            c = AsyncIOMotorClient(os.environ['MONGO_URL'])
            db = c[os.environ['DB_NAME']]
            await db['sync_devices'].delete_many({'install_id': install_id})
            await db['sync_cloud_backups'].delete_many({'install_id': install_id})
        asyncio.run(_clean())
    except Exception as e:
        print(f'  ⚠️ Cleanup failed: {e}')


# ─────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────
class Result:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.details = []

    def check(self, cond, label, extra=''):
        if cond:
            self.passed += 1
            self.details.append(f'  ✅ {label}' + (f'  {extra}' if extra else ''))
        else:
            self.failed += 1
            self.details.append(f'  ❌ {label}' + (f'  {extra}' if extra else ''))
        return cond


def test_uncompressed_legacy(res):
    """1. Envío SIN comprimir (cliente muy antiguo)"""
    print('\n📤 Test 1: Envío legacy sin comprimir')
    install_id = f'TEST-LEGACY-{uuid.uuid4().hex[:8]}'
    data = fixture_realistic()
    try:
        r = _post('/api/sync/cloudbackup/send', {
            'license_key': MASTER_KEY,
            'install_id': install_id,
            'data': data,
            'label': 'test-legacy',
        })
        res.check(r.get('ok'), 'endpoint responde ok:true')
        res.check(r.get('backup_id'), 'devuelve backup_id')
        res.check(r.get('payload_sha256'), 'devuelve payload_sha256')
        res.check(r.get('size_bytes') > 0, f"size_bytes={r.get('size_bytes')}")
        res.check(r.get('size_bytes_stored'), f"size_bytes_stored={r.get('size_bytes_stored')} (comprimido en servidor)")
        # Recuperar y verificar contenido
        got = _get(f'/api/sync/cloudbackup/get?license_key={MASTER_KEY}&install_id={install_id}&backup_id={r["backup_id"]}')
        res.check(got['data'] == data, 'GET devuelve exactamente los mismos datos')
    finally:
        cleanup_install(install_id)


def test_compressed_gzip(res):
    """2. Envío comprimido gzip+base64 (cliente moderno)"""
    print('\n🗜️ Test 2: Envío comprimido gzip+base64')
    install_id = f'TEST-GZIP-{uuid.uuid4().hex[:8]}'
    data = fixture_realistic()
    b64, raw_size, gz_size = compress_gz_b64(data)
    try:
        r = _post('/api/sync/cloudbackup/send', {
            'license_key': MASTER_KEY,
            'install_id': install_id,
            'data_gz_b64': b64,
            'label': 'test-gzip',
        })
        res.check(r.get('ok'), 'endpoint acepta payload comprimido')
        res.check(r.get('size_bytes') == raw_size, f'size_bytes matches raw ({raw_size})')
        res.check(r.get('size_bytes_stored') < raw_size, f'size stored < raw (compresión efectiva)')
        # Recuperar y verificar descompresión transparente
        got = _get(f'/api/sync/cloudbackup/get?license_key={MASTER_KEY}&install_id={install_id}&backup_id={r["backup_id"]}')
        res.check(got['data'] == data, 'GET devuelve datos descomprimidos idénticos')
    finally:
        cleanup_install(install_id)


def test_stress_3years(res):
    """3. Stress test con 3 años de datos (~30.000 filas)"""
    print('\n💪 Test 3: Stress · 3 años de datos')
    install_id = f'TEST-STRESS-{uuid.uuid4().hex[:8]}'
    data = fixture_stress_3years()
    b64, raw_size, gz_size = compress_gz_b64(data)
    print(f'  Raw JSON: {raw_size/1024/1024:.2f} MB · Comprimido: {gz_size/1024:.1f} KB · Ratio: {raw_size/gz_size:.1f}x')
    try:
        r = _post('/api/sync/cloudbackup/send', {
            'license_key': MASTER_KEY,
            'install_id': install_id,
            'data_gz_b64': b64,
            'label': 'test-stress',
        })
        res.check(r.get('ok'), 'acepta payload de 3 años')
        res.check(r.get('compression_ratio', 0) > 20, f"compression_ratio={r.get('compression_ratio')} > 20x")
        # Verifica que devuelve TODOS los días
        got = _get(f'/api/sync/cloudbackup/get?license_key={MASTER_KEY}&install_id={install_id}&backup_id={r["backup_id"]}')
        got_caja = json.loads(got['data']['caja.v1'])
        original_caja = json.loads(data['caja.v1'])
        res.check(len(got_caja['byDate']) == len(original_caja['byDate']),
                  f"{len(got_caja['byDate'])} días recuperados == {len(original_caja['byDate'])} originales")
        # Verifica un día al azar
        sample_day = '2025-06-15'
        res.check(got_caja['byDate'][sample_day] == original_caja['byDate'][sample_day],
                  f'día {sample_day} idéntico byte a byte')
    finally:
        cleanup_install(install_id)


def test_auto_register_device(res):
    """4. Auto-registro de dispositivo en primer envío"""
    print('\n🆔 Test 4: Auto-registro de dispositivo')
    install_id = f'TEST-AUTOREG-{uuid.uuid4().hex[:8]}'
    try:
        # Primer envío sin heartbeat previo
        r = _post('/api/sync/cloudbackup/send', {
            'license_key': MASTER_KEY,
            'install_id': install_id,
            'data': {'caja.v1': '{"byDate":{}}'},
            'label': 'test-autoreg',
        })
        res.check(r.get('ok'), 'primer envío OK aunque no hubo heartbeat')
        # Verifica que se creó entry en sync_devices
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        async def _check():
            c = AsyncIOMotorClient(os.environ['MONGO_URL'])
            db = c[os.environ['DB_NAME']]
            d = await db['sync_devices'].find_one({'install_id': install_id})
            return d
        dev = asyncio.run(_check())
        res.check(dev is not None, f'device creado en sync_devices')
        res.check(dev and dev.get('auto_registered_via') == 'cloudbackup', 'flag auto_registered_via=cloudbackup')
    finally:
        cleanup_install(install_id)


def test_master_in_admin_list(res):
    """5. MASTER aparece en admin/list-licenses"""
    print('\n👑 Test 5: MASTER visible en admin/list-licenses')
    install_id = f'TEST-MASTER-VISIBLE-{uuid.uuid4().hex[:8]}'
    try:
        # Primero envía copia para registrar el device
        _post('/api/sync/cloudbackup/send', {
            'license_key': MASTER_KEY,
            'install_id': install_id,
            'data': {'caja.v1': '{"byDate":{}}'},
        })
        # Listado desde /api/sync/admin/list-licenses
        lst = _get(f'/api/sync/admin/list-licenses?admin_license_key={MASTER_KEY}')
        master_entries = [l for l in lst.get('licenses', []) if l.get('plan') == 'MASTER' and l.get('install_id') == install_id]
        res.check(len(master_entries) >= 1, f'MASTER {install_id} aparece en /sync/admin/list-licenses')
        # También en /api/licenses (panel admin principal)
        headers = {'X-Admin-Token': 'MB-ADMIN-BRUGULAT-2026-4F8E2A1C'}
        r = requests.get(f'{API_URL}/api/licenses', headers=headers, timeout=30)
        r.raise_for_status()
        licenses = r.json()
        master_in_main = [l for l in licenses.get('items', []) if l.get('plan') == 'MASTER' and l.get('install_id') == install_id]
        res.check(len(master_in_main) >= 1, f'MASTER {install_id} aparece en /api/licenses (panel admin)')
    finally:
        cleanup_install(install_id)


def test_integrity_sha256(res):
    """6. Integridad SHA-256"""
    print('\n🔒 Test 6: Integridad SHA-256')
    install_id = f'TEST-SHA-{uuid.uuid4().hex[:8]}'
    data = fixture_realistic()
    try:
        r = _post('/api/sync/cloudbackup/send', {
            'license_key': MASTER_KEY,
            'install_id': install_id,
            'data': data,
        })
        sha = r.get('payload_sha256', '')
        expected = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        res.check(sha == expected, f'SHA-256 servidor coincide con cálculo local ({sha[:16]}...)')
    finally:
        cleanup_install(install_id)


def test_rotation(res):
    """7. Rotación (mantiene últimas 30 por install_id)"""
    print('\n🔄 Test 7: Rotación · 32 envíos, esperar 30 conservadas')
    install_id = f'TEST-ROT-{uuid.uuid4().hex[:8]}'
    try:
        # Envía 32 copias rápidas
        for i in range(32):
            _post('/api/sync/cloudbackup/send', {
                'license_key': MASTER_KEY,
                'install_id': install_id,
                'data': {'caja.v1': f'{{"n":{i}}}'},
                'label': f'rot-{i}',
            })
        lst = _get(f'/api/sync/cloudbackup/list?license_key={MASTER_KEY}&install_id={install_id}')
        res.check(lst['count'] <= 30, f"solo {lst['count']} copias conservadas (rotación funcional)")
        res.check(lst['count'] == 30, f"exactamente 30 copias mantenidas")
    finally:
        cleanup_install(install_id)


def test_size_limits(res):
    """8. Límites de tamaño (raw 50 MB / stored 15 MB)"""
    print('\n📏 Test 8: Límites de tamaño')
    install_id = f'TEST-LIMITS-{uuid.uuid4().hex[:8]}'
    # Payload que excede 50 MB raw (huge repeated string)
    huge = 'X' * (51 * 1024 * 1024)  # 51 MB
    data = {'caja.v1': huge}
    try:
        try:
            r = _post('/api/sync/cloudbackup/send', {
                'license_key': MASTER_KEY,
                'install_id': install_id,
                'data': data,
            })
            res.check(False, 'payload de 51 MB fue rechazado (413)')
        except requests.HTTPError as e:
            res.check(e.response.status_code == 413, f'HTTP 413 payload_too_large_raw devuelto correctamente')
    finally:
        cleanup_install(install_id)


# ─────────────────────────────────────────────────────────────────────
def main():
    print('════════════════════════════════════════════════════════════════')
    print(f'   🧪 TEST E2E BACKEND · Cloud Backup · MediCar Plus')
    print(f'   Backend: {API_URL}')
    print('════════════════════════════════════════════════════════════════')

    res = Result()

    tests = [
        test_uncompressed_legacy,
        test_compressed_gzip,
        test_stress_3years,
        test_auto_register_device,
        test_master_in_admin_list,
        test_integrity_sha256,
        test_rotation,
        test_size_limits,
    ]
    for t in tests:
        try:
            t(res)
        except Exception as e:
            res.check(False, f'{t.__name__} lanzó excepción: {e}')

    print('\n════════════════════════════════════════════════════════════════')
    print('   📊 RESUMEN')
    print('════════════════════════════════════════════════════════════════')
    for d in res.details:
        print(d)
    print(f'\n   Total: {res.passed} OK · {res.failed} FAIL')
    if res.failed == 0:
        print('\n   🎉 TODAS LAS VALIDACIONES PASARON — Sistema de copias 100% funcional')
        sys.exit(0)
    else:
        print(f'\n   ⚠️  {res.failed} test(s) fallaron — revisar arriba')
        sys.exit(1)


if __name__ == '__main__':
    main()
