"""Inject a STANDARD license into MongoDB for a specific install_id, revoking previous active ones.

Usage: python /app/tests/inject_standard.py <install_id>
"""
import asyncio, os, sys, uuid, jwt
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')

INSTALL_ID = sys.argv[1] if len(sys.argv) > 1 else 'CD-STDT-TEST-BUG1-0001'

async def main():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=365)
    lic_id = str(uuid.uuid4())
    jwt_key = jwt.encode({
        'iss': os.environ.get('LICENSE_ISSUER', 'caja-del-dia-license-server'),
        'sub': INSTALL_ID,
        'jti': lic_id,
        'plan': 'STD',
        'iat': int(now.timestamp()),
        'exp': int(exp.timestamp())
    }, os.environ['LICENSE_SECRET'], algorithm='HS256')
    revoke_res = await db.licenses.update_many(
        {'install_id': INSTALL_ID, 'status': 'active'},
        {'$set': {'status': 'revoked', 'revoked_at': now.isoformat(), 'revoked_reason': 'upgrade_test'}}
    )
    print(f"Revoked {revoke_res.modified_count} previous active license(s) for {INSTALL_ID}")
    await db.licenses.insert_one({
        'id': lic_id,
        'install_id': INSTALL_ID,
        'client_name': 'Bug Test STD',
        'client_email': None,
        'plan': 'STD',
        'status': 'active',
        'duration_days': 365,
        'notes': 'sim_std_multi_device_test',
        'created_at': now.isoformat(),
        'expires_at': exp.isoformat(),
        'license_key': jwt_key,
        'verify_count': 0
    })
    print(f"Inserted STANDARD license id={lic_id} for install_id={INSTALL_ID}")
    print(f"license_key(first 40)={jwt_key[:40]}...")

asyncio.run(main())
