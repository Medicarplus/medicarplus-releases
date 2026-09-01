"""End-to-end test del sistema Sync Multi-PC.

Simula 2 ordenadores (PC1 y PC2) usando la misma licencia Premium con todos
los escenarios críticos que debe soportar:
  1. PC1 arranca solo (independent)
  2. PC2 arranca (autorizado, se aceptan hasta 2 devices Premium)
  3. PC3 rechazado (max 2)
  4. Ambos en modo Independent → NO se sincronizan
  5. Cambian a Linked → SÍ se sincronizan
  6. Push desde PC1 → PC2 recibe con pull
  7. Push simultáneo (last-write-wins por timestamp)
  8. Merge sin duplicados
  9. Un PC vuelve a Independent → deja de recibir sync
 10. Standard NO permite sync
"""
import os
import sys
import asyncio
import json
import time
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

API_URL = os.environ.get('BACKEND_URL', 'http://localhost:8001')
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']


class Colors:
    G = '\033[92m'
    R = '\033[91m'
    Y = '\033[93m'
    B = '\033[94m'
    E = '\033[0m'


PASS = f"{Colors.G}✓{Colors.E}"
FAIL = f"{Colors.R}✗{Colors.E}"

results = {"pass": 0, "fail": 0, "errors": []}


def check(cond, msg):
    if cond:
        print(f"  {PASS} {msg}")
        results["pass"] += 1
    else:
        print(f"  {FAIL} {msg}")
        results["fail"] += 1
        results["errors"].append(msg)


async def setup_premium_license(db):
    """Crea (o reutiliza) una licencia Premium de test."""
    test_key = f"TEST-PREMIUM-SYNC-{uuid.uuid4().hex[:12]}"
    doc = {
        "id": str(uuid.uuid4()),
        "install_id": "TEST-BASE",
        "license_key": test_key,
        "plan": "PRM",
        "plan_family": "PRM",
        "status": "active",
        "client_email": "sync-test@medicarplus.es",
        "client_name": "Test Sync",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
    }
    await db.licenses.insert_one(doc)
    return test_key


async def setup_standard_license(db):
    test_key = f"TEST-STANDARD-SYNC-{uuid.uuid4().hex[:12]}"
    doc = {
        "id": str(uuid.uuid4()),
        "install_id": "TEST-STD-BASE",
        "license_key": test_key,
        "plan": "STD",
        "plan_family": "STD",
        "status": "active",
        "client_email": "sync-std-test@medicarplus.es",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
    }
    await db.licenses.insert_one(doc)
    return test_key


async def setup_trial_license(db):
    test_key = f"TEST-TRIAL-SYNC-{uuid.uuid4().hex[:12]}"
    doc = {
        "id": str(uuid.uuid4()),
        "install_id": "TEST-TRIAL-BASE",
        "license_key": test_key,
        "plan": "TRIAL",
        "plan_family": "TRIAL",
        "status": "active",
        "client_email": "sync-trial-test@medicarplus.es",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),
    }
    await db.licenses.insert_one(doc)
    return test_key


async def cleanup(db, license_keys, install_ids):
    """Limpieza: borra licencias de test + sync_states + sync_devices."""
    import hashlib
    for k in license_keys:
        await db.licenses.delete_many({"license_key": k})
        h = hashlib.sha256(k.strip().encode()).hexdigest()
        await db.sync_states.delete_many({"_id": h})
        await db.sync_devices.delete_many({"license_key_hash": h})
        await db.sync_backups.delete_many({"license_key_hash": h})
    for iid in install_ids:
        await db.sync_devices.delete_many({"install_id": iid})


async def main():
    print(f"\n{Colors.B}════════════════════════════════════════════════════════════════════{Colors.E}")
    print(f"{Colors.B}   TEST END-TO-END · Sync Multi-PC (Premium){Colors.E}")
    print(f"{Colors.B}════════════════════════════════════════════════════════════════════{Colors.E}\n")
    print(f"API: {API_URL}")

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Genera IDs únicos para no chocar con otras runs
    PC1 = f"PC1-{uuid.uuid4().hex[:8]}"
    PC2 = f"PC2-{uuid.uuid4().hex[:8]}"
    PC3 = f"PC3-{uuid.uuid4().hex[:8]}"
    PC_STD = f"PCSTD-{uuid.uuid4().hex[:8]}"

    KEY_PRM = await setup_premium_license(db)
    KEY_STD = await setup_standard_license(db)
    KEY_TRIAL = await setup_trial_license(db)
    print(f"License Premium test: {KEY_PRM}")
    print(f"License Standard test: {KEY_STD}")
    print(f"License Trial test:    {KEY_TRIAL}")
    PC_TR1 = f"PCTR1-{uuid.uuid4().hex[:8]}"
    PC_TR2 = f"PCTR2-{uuid.uuid4().hex[:8]}"
    print(f"PCs: {PC1}, {PC2}, {PC3}, {PC_STD}\n")

    async with httpx.AsyncClient(base_url=API_URL, timeout=10.0) as ac:

        # ──────────────────────────────────────────────────────────────────
        print(f"{Colors.Y}▸ Escenario 1: PC1 arranca (heartbeat){Colors.E}")
        r = await ac.post("/api/sync/heartbeat", json={"license_key": KEY_PRM, "install_id": PC1})
        d = r.json()
        check(r.status_code == 200, f"HTTP 200 (got {r.status_code})")
        check(d.get("authorized") is True, "authorized=True")
        check(d.get("is_premium") is True, "is_premium=True")
        check(d.get("max_devices") == 2, "max_devices=2")
        check(d.get("current_devices") == 1, f"current_devices=1 (got {d.get('current_devices')})")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 2: PC2 arranca (heartbeat){Colors.E}")
        r = await ac.post("/api/sync/heartbeat", json={"license_key": KEY_PRM, "install_id": PC2})
        d = r.json()
        check(d.get("authorized") is True, "PC2 authorized=True")
        check(d.get("current_devices") == 2, f"current_devices=2 (got {d.get('current_devices')})")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 3: PC3 intenta arrancar → RECHAZADO{Colors.E}")
        r = await ac.post("/api/sync/heartbeat", json={"license_key": KEY_PRM, "install_id": PC3})
        d = r.json()
        check(d.get("authorized") is False, "PC3 authorized=False (max 2)")
        check(d.get("device_limit_reached") is True, "device_limit_reached=True")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 4: Ambos independent → push RECHAZADO{Colors.E}")
        r = await ac.post("/api/sync/push", json={
            "license_key": KEY_PRM, "install_id": PC1,
            "entries": {"foo": {"value": {"x": 1}, "updated_at": datetime.now(timezone.utc).isoformat()}}
        })
        check(r.status_code == 409, f"PC1 push rechazado con 409 (got {r.status_code}: {r.text[:80]})")

        # Status para PC1
        r = await ac.get(f"/api/sync/status?license_key={KEY_PRM}&install_id={PC1}")
        d = r.json()
        check(d.get("my_mode") == "independent", f"PC1 mode=independent (got {d.get('my_mode')})")
        check(d.get("linked") is False, "PC1 linked=False")
        check(len(d.get("peers", [])) == 1, f"PC1 ve 1 peer (PC2 · PC3 fue rechazado) (got {len(d.get('peers', []))})")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 5: PC1 y PC2 pasan a Linked{Colors.E}")
        r = await ac.post("/api/sync/mode", json={"license_key": KEY_PRM, "install_id": PC1, "mode": "linked"})
        check(r.status_code == 200, f"PC1 → linked (got {r.status_code})")
        r = await ac.post("/api/sync/mode", json={"license_key": KEY_PRM, "install_id": PC2, "mode": "linked"})
        d = r.json()
        check(r.status_code == 200, f"PC2 → linked (got {r.status_code})")
        check(d.get("linked_devices") == 2, f"linked_devices=2 (got {d.get('linked_devices')})")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 6: PC1 hace push → PC2 hace pull → recibe datos{Colors.E}")
        t1 = datetime.now(timezone.utc).isoformat()
        r = await ac.post("/api/sync/push", json={
            "license_key": KEY_PRM, "install_id": PC1,
            "entries": {
                "caja.byDate.2026-03-05": {"value": [{"id": "entry-A", "amount": 100}], "updated_at": t1},
                "caja.config.v1": {"value": {"company1": "AutoTest"}, "updated_at": t1}
            }
        })
        d = r.json()
        check(r.status_code == 200, f"PC1 push OK (got {r.status_code})")
        check(d.get("written") == 2, f"written=2 (got {d.get('written')})")

        r = await ac.get(f"/api/sync/pull?license_key={KEY_PRM}&install_id={PC2}")
        d = r.json()
        entries = d.get("entries", {})
        check(r.status_code == 200, f"PC2 pull OK (got {r.status_code})")
        check("caja.byDate.2026-03-05" in entries, "PC2 recibe byDate del PC1")
        check("caja.config.v1" in entries, "PC2 recibe config del PC1")
        # Datos exactos:
        e = entries.get("caja.byDate.2026-03-05", {}).get("value", [])
        check(len(e) == 1 and e[0].get("id") == "entry-A", "byDate value coincide")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 7: PC2 añade DISTINTA entrada mismo día → NO duplica{Colors.E}")
        # NOTA: el frontend hará el merge de arrays (union por id). El backend
        # es last-write-wins por KEY, así que la lógica de fusion vive en el
        # cliente. Aquí testeamos que el backend acepta y devuelve.
        t2 = datetime.now(timezone.utc).isoformat()
        # Simula el merge que hace el cliente: local [entry-A, entry-B]
        merged_frontend = [
            {"id": "entry-A", "amount": 100},   # ya existente
            {"id": "entry-B", "amount": 200}    # nueva de PC2
        ]
        r = await ac.post("/api/sync/push", json={
            "license_key": KEY_PRM, "install_id": PC2,
            "entries": {"caja.byDate.2026-03-05": {"value": merged_frontend, "updated_at": t2}}
        })
        check(r.status_code == 200, "PC2 push del merge OK")

        r = await ac.get(f"/api/sync/pull?license_key={KEY_PRM}&install_id={PC1}")
        d = r.json()
        merged_back = d.get("entries", {}).get("caja.byDate.2026-03-05", {}).get("value", [])
        ids = [e.get("id") for e in merged_back]
        check(len(merged_back) == 2, f"cloud tiene 2 entradas (got {len(merged_back)})")
        check("entry-A" in ids and "entry-B" in ids, "sin duplicados: A y B presentes")
        check(len(set(ids)) == len(ids), "IDs únicos (sin duplicados)")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 8: Last-Write-Wins por timestamp{Colors.E}")
        # PC1 push con timestamp OLD, PC2 después con timestamp NEW
        t_old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        t_new = datetime.now(timezone.utc).isoformat()
        await ac.post("/api/sync/push", json={
            "license_key": KEY_PRM, "install_id": PC1,
            "entries": {"caja.saldo.v1": {"value": 5000, "updated_at": t_old}}
        })
        await ac.post("/api/sync/push", json={
            "license_key": KEY_PRM, "install_id": PC2,
            "entries": {"caja.saldo.v1": {"value": 7500, "updated_at": t_new}}
        })
        r = await ac.get(f"/api/sync/pull?license_key={KEY_PRM}&install_id={PC1}")
        val = r.json().get("entries", {}).get("caja.saldo.v1", {}).get("value")
        check(val == 7500, f"último timestamp gana (got {val}, esperado 7500)")

        # PC1 push con timestamp aún más OLD → no debe pisar el NEW
        await ac.post("/api/sync/push", json={
            "license_key": KEY_PRM, "install_id": PC1,
            "entries": {"caja.saldo.v1": {"value": 1234, "updated_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()}}
        })
        r = await ac.get(f"/api/sync/pull?license_key={KEY_PRM}&install_id={PC1}")
        val = r.json().get("entries", {}).get("caja.saldo.v1", {}).get("value")
        check(val == 7500, f"timestamp OLD no pisa NEW (got {val}, esperado 7500)")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 9: PC2 vuelve a Independent → deja de participar{Colors.E}")
        r = await ac.post("/api/sync/mode", json={"license_key": KEY_PRM, "install_id": PC2, "mode": "independent"})
        d = r.json()
        check(r.status_code == 200, "PC2 → independent OK")
        check(d.get("linked_devices") == 1, f"linked_devices=1 (got {d.get('linked_devices')})")

        # PC2 push → RECHAZADO
        r = await ac.post("/api/sync/push", json={
            "license_key": KEY_PRM, "install_id": PC2,
            "entries": {"caja.saldo.v1": {"value": 999, "updated_at": datetime.now(timezone.utc).isoformat()}}
        })
        check(r.status_code == 409, f"PC2 push rechazado (independent) (got {r.status_code})")

        # PC1 sigue pudiendo (está linked)
        r = await ac.post("/api/sync/push", json={
            "license_key": KEY_PRM, "install_id": PC1,
            "entries": {"caja.saldo.v1": {"value": 8000, "updated_at": datetime.now(timezone.utc).isoformat()}}
        })
        check(r.status_code == 200, "PC1 (linked) sigue pudiendo push")

        r = await ac.get(f"/api/sync/pull?license_key={KEY_PRM}&install_id={PC1}")
        val = r.json().get("entries", {}).get("caja.saldo.v1", {}).get("value")
        check(val == 8000, f"PC1 ve su último push (got {val})")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 10: Standard NO permite sync ni mode{Colors.E}")
        r = await ac.post("/api/sync/heartbeat", json={"license_key": KEY_STD, "install_id": PC_STD})
        d = r.json()
        check(d.get("is_premium") is False, "Standard is_premium=False")
        check(d.get("max_devices") == 1, "Standard max_devices=1")

        r = await ac.post("/api/sync/mode", json={"license_key": KEY_STD, "install_id": PC_STD, "mode": "linked"})
        check(r.status_code == 403, f"Standard mode/linked rechazado (got {r.status_code})")

        r = await ac.post("/api/sync/push", json={
            "license_key": KEY_STD, "install_id": PC_STD,
            "entries": {"foo": {"value": 1, "updated_at": datetime.now(timezone.utc).isoformat()}}
        })
        check(r.status_code == 403, f"Standard push rechazado (got {r.status_code})")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 11: PC2 vuelve a linked → recibe los datos actualizados{Colors.E}")
        r = await ac.post("/api/sync/mode", json={"license_key": KEY_PRM, "install_id": PC2, "mode": "linked"})
        check(r.status_code == 200, "PC2 → linked otra vez")
        r = await ac.get(f"/api/sync/pull?license_key={KEY_PRM}&install_id={PC2}")
        val = r.json().get("entries", {}).get("caja.saldo.v1", {}).get("value")
        check(val == 8000, f"PC2 recibe el estado actualizado (got {val})")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 12: Backup manual · PC1 envía copia a PC2 (independent){Colors.E}")
        # Ambos vuelven a independent
        await ac.post("/api/sync/mode", json={"license_key": KEY_PRM, "install_id": PC1, "mode": "independent"})
        await ac.post("/api/sync/mode", json={"license_key": KEY_PRM, "install_id": PC2, "mode": "independent"})

        # PC1 envía copia
        snapshot_pc1 = {
            "caja.byDate.v1": {"2026-04-01": [{"id": "backup-1", "amount": 500}]},
            "caja.saldoInicial.v1": {"fecha": "2026-04-01", "efectivo": 3500},
        }
        r = await ac.post("/api/sync/backup/send", json={
            "license_key": KEY_PRM, "install_id": PC1,
            "data": snapshot_pc1, "label": "Copia final de marzo"
        })
        d = r.json()
        check(r.status_code == 200, f"backup/send OK (got {r.status_code})")
        check("backup_id" in d, "backup_id devuelto")
        backup_id_pc1 = d.get("backup_id")

        # PC2 comprueba pending
        r = await ac.get(f"/api/sync/backup/pending?license_key={KEY_PRM}&install_id={PC2}")
        d = r.json()
        check(d.get("count") == 1, f"PC2 ve 1 copia pendiente (got {d.get('count')})")
        pending = d.get("pending", [])
        if pending:
            check(pending[0]["from_install_id"] == PC1, "copia viene de PC1")
            check(pending[0]["label"] == "Copia final de marzo", "label correcto")
            check("backup-1" in json.dumps(pending[0]["data"]), "data incluida en el payload")

        # PC1 NO ve su propia copia (uno no restaura la suya)
        r = await ac.get(f"/api/sync/backup/pending?license_key={KEY_PRM}&install_id={PC1}")
        d = r.json()
        check(d.get("count") == 0, f"PC1 no ve su propia copia (got {d.get('count')})")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 13: Backup upsert · reenviar sobrescribe la anterior{Colors.E}")
        r = await ac.post("/api/sync/backup/send", json={
            "license_key": KEY_PRM, "install_id": PC1,
            "data": {"caja.new.v1": {"foo": "bar"}}, "label": "Copia más reciente"
        })
        check(r.status_code == 200, "segundo backup/send OK")
        r = await ac.get(f"/api/sync/backup/pending?license_key={KEY_PRM}&install_id={PC2}")
        d = r.json()
        check(d.get("count") == 1, f"sigue habiendo solo 1 pendiente (got {d.get('count')})")
        if d.get("pending"):
            check(d["pending"][0]["label"] == "Copia más reciente", "es la copia MÁS reciente")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 14: PC2 consume la copia → deja de aparecer{Colors.E}")
        r = await ac.get(f"/api/sync/backup/pending?license_key={KEY_PRM}&install_id={PC2}")
        pending = r.json().get("pending", [])
        if pending:
            backup_id = pending[0]["backup_id"]
            r = await ac.post("/api/sync/backup/consume", json={
                "license_key": KEY_PRM, "install_id": PC2, "backup_id": backup_id
            })
            check(r.status_code == 200, "backup/consume OK")

            # Ya no aparece para PC2
            r = await ac.get(f"/api/sync/backup/pending?license_key={KEY_PRM}&install_id={PC2}")
            d = r.json()
            check(d.get("count") == 0, f"PC2 ya no ve la copia consumida (got {d.get('count')})")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 15: Standard NO puede usar backup{Colors.E}")
        r = await ac.post("/api/sync/backup/send", json={
            "license_key": KEY_STD, "install_id": PC_STD, "data": {"x": 1}
        })
        check(r.status_code == 403, f"Standard backup/send rechazado (got {r.status_code})")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 16: TRIAL SÍ permite sync (mismo comportamiento que Premium){Colors.E}")
        r = await ac.post("/api/sync/heartbeat", json={"license_key": KEY_TRIAL, "install_id": PC_TR1})
        d = r.json()
        check(d.get("is_premium") is True, "TRIAL is_premium=True (permite sync)")
        check(d.get("max_devices") == 2, f"TRIAL max_devices=2 (got {d.get('max_devices')})")
        r = await ac.post("/api/sync/heartbeat", json={"license_key": KEY_TRIAL, "install_id": PC_TR2})
        check(r.json().get("authorized") is True, "TRIAL PC2 autorizado")

        # Modo linked funciona
        r = await ac.post("/api/sync/mode", json={"license_key": KEY_TRIAL, "install_id": PC_TR1, "mode": "linked"})
        check(r.status_code == 200, "TRIAL mode/linked OK (no 403)")
        r = await ac.post("/api/sync/mode", json={"license_key": KEY_TRIAL, "install_id": PC_TR2, "mode": "linked"})
        check(r.status_code == 200, "TRIAL PC2 mode/linked OK")

        # Push funciona
        now = datetime.now(timezone.utc).isoformat()
        r = await ac.post("/api/sync/push", json={
            "license_key": KEY_TRIAL, "install_id": PC_TR1,
            "entries": {"trial.test": {"value": {"a": 1}, "updated_at": now}}
        })
        check(r.status_code == 200, f"TRIAL push OK (got {r.status_code})")

        # Pull funciona
        r = await ac.get(f"/api/sync/pull?license_key={KEY_TRIAL}&install_id={PC_TR2}")
        val = r.json().get("entries", {}).get("trial.test", {}).get("value")
        check(val == {"a": 1}, f"TRIAL PC2 recibe datos de PC1 (got {val})")

        # Backup manual funciona
        r = await ac.post("/api/sync/backup/send", json={
            "license_key": KEY_TRIAL, "install_id": PC_TR1,
            "data": {"trial.snap": [{"id": "T1"}]}, "label": "TRIAL backup"
        })
        check(r.status_code == 200, "TRIAL backup/send OK")
        r = await ac.get(f"/api/sync/backup/pending?license_key={KEY_TRIAL}&install_id={PC_TR2}")
        check(r.json().get("count") == 1, "TRIAL PC2 ve la copia pendiente")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 17: Flujo completo end-to-end simulando 2 secretarias{Colors.E}")
        # Reset a modo independent, empezamos de cero
        await ac.post("/api/sync/mode", json={"license_key": KEY_PRM, "install_id": PC1, "mode": "linked"})
        await ac.post("/api/sync/mode", json={"license_key": KEY_PRM, "install_id": PC2, "mode": "linked"})

        # Secretaria (PC1) mete revisiones día 6
        rev_pc1 = {"caja.byDate.v1": {"value": {"2026-04-06": [
            {"id": "rev-001", "kind": "REV", "amount": 50, "updated_at": now},
            {"id": "rev-002", "kind": "REV", "amount": 75, "updated_at": now}
        ]}, "updated_at": now}}
        r = await ac.post("/api/sync/push", json={"license_key": KEY_PRM, "install_id": PC1, "entries": rev_pc1})
        check(r.status_code == 200, "Secretaria PC1 sube 2 revisiones")

        # Gerente (PC2) hace pull y añade gastos día 6 (mismo día!) SIN sobrescribir revisiones
        r = await ac.get(f"/api/sync/pull?license_key={KEY_PRM}&install_id={PC2}")
        cloud = r.json().get("entries", {}).get("caja.byDate.v1", {}).get("value", {})
        cloud_day6 = cloud.get("2026-04-06", [])
        check(len(cloud_day6) == 2, f"Gerente PC2 pull → ve 2 revisiones (got {len(cloud_day6)})")

        # Gerente añade 2 gastos al mismo día
        gerente_day6 = cloud_day6 + [
            {"id": "gasto-001", "kind": "GAS", "amount": -20, "updated_at": now},
            {"id": "gasto-002", "kind": "GAS", "amount": -35, "updated_at": now}
        ]
        r = await ac.post("/api/sync/push", json={
            "license_key": KEY_PRM, "install_id": PC2,
            "entries": {"caja.byDate.v1": {"value": {"2026-04-06": gerente_day6}, "updated_at": now}}
        })
        check(r.status_code == 200, "Gerente PC2 sube 2 gastos en el mismo día")

        # Secretaria hace pull y ve TODO (revisiones + gastos, sin duplicados)
        r = await ac.get(f"/api/sync/pull?license_key={KEY_PRM}&install_id={PC1}")
        final_day6 = r.json().get("entries", {}).get("caja.byDate.v1", {}).get("value", {}).get("2026-04-06", [])
        ids = [e.get("id") for e in final_day6]
        check(len(final_day6) == 4, f"PC1 final ve 4 entradas del mismo día (got {len(final_day6)})")
        check("rev-001" in ids and "rev-002" in ids, "revisiones preservadas")
        check("gasto-001" in ids and "gasto-002" in ids, "gastos añadidos")
        check(len(set(ids)) == 4, "IDs únicos (sin duplicados)")

        # ──────────────────────────────────────────────────────────────────
        print(f"\n{Colors.Y}▸ Escenario 18: Backup manual → aplicar → sin duplicados{Colors.E}")
        # PC1 cambia a independiente y envía backup con datos nuevos + repetidos
        await ac.post("/api/sync/mode", json={"license_key": KEY_PRM, "install_id": PC1, "mode": "independent"})
        await ac.post("/api/sync/mode", json={"license_key": KEY_PRM, "install_id": PC2, "mode": "independent"})
        backup_data = {
            "caja.byDate.v1": {"2026-04-06": [
                {"id": "rev-001", "kind": "REV", "amount": 50},  # REPETIDO
                {"id": "rev-003", "kind": "REV", "amount": 88},  # NUEVO
            ]}
        }
        r = await ac.post("/api/sync/backup/send", json={
            "license_key": KEY_PRM, "install_id": PC1, "data": backup_data, "label": "Backup con repetidos"
        })
        check(r.status_code == 200, "backup con repetidos enviado")
        r = await ac.get(f"/api/sync/backup/pending?license_key={KEY_PRM}&install_id={PC2}")
        pending = r.json().get("pending", [])
        check(len(pending) == 1, "PC2 ve 1 copia pendiente con contenido")
        # Comprobamos que los datos llegan tal cual (el merge cliente-side ocurre en frontend)
        if pending:
            got_ids = [e.get("id") for e in pending[0]["data"].get("caja.byDate.v1", {}).get("2026-04-06", [])]
            check("rev-001" in got_ids and "rev-003" in got_ids, "backup transporta rev-001 (repetido) + rev-003 (nuevo)")

    # Cleanup
    print(f"\n{Colors.B}▸ Cleanup{Colors.E}")
    await cleanup(db, [KEY_PRM, KEY_STD, KEY_TRIAL], [PC1, PC2, PC3, PC_STD, PC_TR1, PC_TR2])
    client.close()

    # Summary
    print(f"\n{Colors.B}════════════════════════════════════════════════════════════════════{Colors.E}")
    total = results["pass"] + results["fail"]
    if results["fail"] == 0:
        print(f"{Colors.G}✅ TODOS LOS TESTS PASAN · {results['pass']}/{total}{Colors.E}")
    else:
        print(f"{Colors.R}❌ FALLAN {results['fail']}/{total} tests{Colors.E}")
        for err in results["errors"]:
            print(f"   {FAIL} {err}")
    print(f"{Colors.B}════════════════════════════════════════════════════════════════════{Colors.E}\n")
    return 0 if results["fail"] == 0 else 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
