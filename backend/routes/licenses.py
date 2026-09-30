"""FastAPI router for the Caja del Día license server.

Endpoints (tots prefixats amb /api dins server.py):
    POST   /api/licenses/generate    → admin, crea una llicència nova (JWT)
    POST   /api/licenses/verify      → client, valida una llicència
    POST   /api/licenses/revoke      → admin, revoca una llicència
    GET    /api/licenses             → admin, llista totes les llicències
    GET    /api/licenses/{install_id}→ admin, detall d'una llicència

Autenticació admin: capçalera `X-Admin-Token` que coincideix amb la
variable d'entorn `LICENSE_ADMIN_TOKEN`. Compat total amb el sistema
Master Key offline del `v2.html` (aquest continua funcionant sense
necessitat de contactar amb el servidor).
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel


class UpdateContactBody(BaseModel):
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    tax_id: Optional[str] = None

from models.license import (
    LicenseCreate,
    LicenseListResponse,
    LicenseRecord,
    LicenseRequestApprove,
    LicenseRequestCreate,
    LicenseRequestListResponse,
    LicenseRequestRecord,
    LicenseRequestReject,
    LicenseRevoke,
    LicenseVerify,
    LicenseVerifyResponse,
)
from services import mailer

logger = logging.getLogger(__name__)

JWT_ALG = "HS256"
COLLECTION = "licenses"
REQ_COLLECTION = "license_requests"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _secret() -> str:
    s = os.environ.get("LICENSE_SECRET")
    if not s:
        raise RuntimeError("LICENSE_SECRET no configurat a l'entorn")
    return s


def _issuer() -> str:
    return os.environ.get("LICENSE_ISSUER", "caja-del-dia-license-server")


def _admin_token() -> str:
    t = os.environ.get("LICENSE_ADMIN_TOKEN")
    if not t:
        raise RuntimeError("LICENSE_ADMIN_TOKEN no configurat a l'entorn")
    return t


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _doc_to_record(doc: dict, include_key: bool = False) -> LicenseRecord:
    return LicenseRecord(
        id=doc.get("id") or doc.get("_id", ""),
        install_id=doc["install_id"],
        client_name=doc.get("client_name", ""),
        client_email=doc.get("client_email"),
        contact_name=doc.get("contact_name"),
        phone=doc.get("phone"),
        tax_id=doc.get("tax_id"),
        plan=doc.get("plan", "STD"),
        status=doc.get("status", "active"),
        duration_days=doc.get("duration_days"),
        notes=doc.get("notes"),
        created_at=_to_dt(doc.get("created_at")) or _now(),
        expires_at=_to_dt(doc.get("expires_at")),
        revoked_at=_to_dt(doc.get("revoked_at")),
        revoked_reason=doc.get("revoked_reason"),
        last_verified_at=_to_dt(doc.get("last_verified_at")),
        verify_count=int(doc.get("verify_count", 0) or 0),
        hwid_lock=doc.get("hwid_lock"),
        hwid_locked_at=_to_dt(doc.get("hwid_locked_at")),
        hwid_reset_count=int(doc.get("hwid_reset_count", 0) or 0),
        linked_hwids=doc.get("linked_hwids"),
        linked_install_ids=doc.get("linked_install_ids"),
        referral_code=doc.get("referral_code"),
        referred_by=doc.get("referred_by"),
        referral_reward_count=int(doc.get("referral_reward_count", 0) or 0),
        abuse_flags=doc.get("abuse_flags") if isinstance(doc.get("abuse_flags"), list) else None,
        message_count=int(doc.get("message_count", 0) or 0),
        last_message_at=_to_dt(doc.get("last_message_at")),
        synthetic_master=bool(doc.get("_synthetic_master") or doc.get("synthetic_master")) or None,
        placeholder=bool(doc.get("_placeholder") or doc.get("placeholder")) or None,
        license_key=doc.get("license_key") if include_key else None,
    )


def _mint_jwt(*, install_id: str, license_id: str, plan: str,
              expires_at: Optional[datetime]) -> str:
    """Genera el JWT que serveix com a `license key`.

    Per PREMIUM el `sub` es fa portable (`CD-STRIPE-ADMIN-*`) perquè la mateixa clau
    pugui activar-se al segon dispositiu que permet el pla. Per Standard/Trial el
    `sub` queda lligat a l'install_id inicial (1 sol dispositiu).
    """
    now = _now()
    plan_upper = str(plan or "").upper()
    sub_value = install_id
    if plan_upper in ("PREMIUM", "PRM"):
        # Portable sub → v2.html + verify_license accepten CD-STRIPE-* com a portables
        sub_value = f"CD-STRIPE-ADMIN-{license_id[:12].upper()}"
    payload: dict[str, Any] = {
        "iss": _issuer(),
        "sub": sub_value,
        "jti": license_id,
        "plan": plan,
        "iat": int(now.timestamp()),
    }
    if expires_at is not None:
        payload["exp"] = int(expires_at.timestamp())
    return jwt.encode(payload, _secret(), algorithm=JWT_ALG)


def require_admin(x_admin_token: str = Header(default="", alias="X-Admin-Token")) -> None:
    """Dependency: exigeix la capçalera X-Admin-Token vàlida."""
    if not x_admin_token or x_admin_token != _admin_token():
        raise HTTPException(status_code=401, detail="Admin token invàlid o absent")


# ---------------------------------------------------------------------------
# Factory: cal el `db` viu del server principal per no duplicar clients
# ---------------------------------------------------------------------------
def build_router(db: AsyncIOMotorDatabase, limiter=None) -> APIRouter:
    """Crea el router usant la connexió MongoDB compartida.

    Args:
        db: motor async database
        limiter: optional slowapi Limiter for per-IP rate limiting on public endpoints
    """

    router = APIRouter(prefix="/licenses", tags=["licenses"])
    coll = db[COLLECTION]
    req_coll = db[REQ_COLLECTION]
    audit_coll = db["audit_logs"]

    # -------- Backfill lazy (Feb 2026): rellena contact_name/phone/tax_id en
    # licencias existentes copiando desde la solicitud original. Se ejecuta
    # una sola vez cuando se lista licencias por primera vez tras arrancar.
    _backfill_done = {"v": False}

    async def _backfill_contact_data() -> None:
        if _backfill_done["v"]:
            return
        _backfill_done["v"] = True
        try:
            import re as _re
            missing = coll.find(
                {
                    "$or": [
                        {"contact_name": {"$exists": False}},
                        {"contact_name": None},
                        {"contact_name": ""},
                        {"phone": {"$exists": False}},
                        {"phone": None},
                        {"tax_id": {"$exists": False}},
                        {"tax_id": None},
                    ]
                },
                {"_id": 0, "id": 1, "install_id": 1, "client_email": 1, "client_name": 1, "contact_name": 1, "phone": 1, "tax_id": 1},
            )
            updated = 0
            async for lic in missing:
                iid = lic.get("install_id")
                email = (lic.get("client_email") or "").strip()
                # 1º intento: match exacto por install_id
                req = None
                if iid and iid != "CD-TRIAL-PENDING-0000-0000":
                    req = await req_coll.find_one({"install_id": iid}, sort=[("created_at", -1)])
                # 2º intento: fallback por email (case-insensitive) si el 1º no encontró nada
                if not req and email:
                    req = await req_coll.find_one(
                        {"email": {"$regex": f"^{_re.escape(email)}$", "$options": "i"}},
                        sort=[("created_at", -1)],
                    )
                if not req:
                    continue
                patch: dict = {}
                if not lic.get("contact_name") and req.get("contact_name"):
                    patch["contact_name"] = req["contact_name"]
                if not lic.get("phone") and req.get("phone"):
                    patch["phone"] = req["phone"]
                if not lic.get("tax_id") and req.get("tax_id"):
                    patch["tax_id"] = req["tax_id"]
                # Si la licencia tiene client_name vacío pero la solicitud tiene company_name, usarlo
                if not lic.get("client_name") and req.get("company_name"):
                    patch["client_name"] = req["company_name"]
                if patch:
                    await coll.update_one({"id": lic["id"]}, {"$set": patch})
                    updated += 1
            if updated:
                logger.info("licenses backfill: contactos rellenados en %d licencia(s)", updated)
        except Exception:  # noqa: BLE001
            logger.exception("licenses backfill failed")

    def _rate(spec: str):
        """No-op decorator. Global default limit (300/min) from server.py applies
        to all endpoints automatically. Per-route stricter limits can be added
        later once slowapi + FastAPI signature interop is resolved."""
        return lambda fn: fn

    async def _audit(request: Request, action: str, target: str, actor: str = "admin", extra: Optional[dict] = None) -> None:
        try:
            ip = request.client.host if request and request.client else "-"
            await audit_coll.insert_one({
                "id": str(uuid.uuid4()),
                "action": action,
                "target": target,
                "actor": actor,
                "ip": ip,
                "timestamp": _now().isoformat(),
                "extra": extra or {},
            })
        except Exception:  # noqa: BLE001
            logger.exception("audit log failed")

    async def _create_license(
        *,
        install_id: str,
        client_name: str,
        client_email: Optional[str],
        duration_days: Optional[int],
        plan: str,
        notes: Optional[str],
        contact_name: Optional[str] = None,
        phone: Optional[str] = None,
        tax_id: Optional[str] = None,
    ) -> dict:
        """Reusable helper: revoca l'anterior + insereix una nova llicència."""
        existing = await coll.find_one({"install_id": install_id, "status": "active"})
        if existing:
            await coll.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "status": "revoked",
                    "revoked_at": _now().isoformat(),
                    "revoked_reason": "replaced_by_new_license",
                }},
            )

        license_id = str(uuid.uuid4())
        created_at = _now()
        expires_at: Optional[datetime] = None
        if duration_days:
            expires_at = created_at + timedelta(days=duration_days)

        jwt_key = _mint_jwt(
            install_id=install_id,
            license_id=license_id,
            plan=plan,
            expires_at=expires_at,
        )
        doc = {
            "id": license_id,
            "install_id": install_id,
            "client_name": (client_name or "").strip(),
            "client_email": (client_email or "").strip() or None,
            "contact_name": (contact_name or "").strip() or None,
            "phone": (phone or "").strip() or None,
            "tax_id": (tax_id or "").strip() or None,
            "plan": plan,
            "status": "active",
            "duration_days": duration_days,
            "notes": notes,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "revoked_at": None,
            "revoked_reason": None,
            "last_verified_at": None,
            "verify_count": 0,
            "license_key": jwt_key,
        }
        await coll.insert_one(doc)
        logger.info("license created for %s (id=%s)", install_id, license_id)
        return doc

    # ---------- Generate ----------
    @router.post(
        "/generate",
        response_model=LicenseRecord,
        dependencies=[Depends(require_admin)],
        status_code=status.HTTP_201_CREATED,
    )
    async def generate_license(body: LicenseCreate, request: Request) -> LicenseRecord:
        """Genera una llicència JWT nova per un install_id."""
        doc = await _create_license(
            install_id=body.install_id,
            client_name=body.client_name,
            client_email=body.client_email,
            duration_days=body.duration_days,
            plan=body.plan or "STD",
            notes=body.notes,
        )
        await _audit(request, "license.generate", body.install_id, extra={"plan": doc["plan"]})
        return _doc_to_record(doc, include_key=True)

    # ---------- Transfer to new device (Feb 2026 · God-mode) ----------
    @router.post(
        "/change-email",
        dependencies=[Depends(require_admin)],
    )
    async def change_client_email(body: dict, request: Request):
        """Cambia el email del cliente en TODAS las colecciones + Stripe.

        Propagación automática:
        - `licenses.client_email` (todas las licencias del cliente, incluidas históricas)
        - `subscriptions.customer_email`
        - `installations.linked_email` (por install_ids del cliente)
        - Stripe Customer email (via API, para que las facturas futuras vayan al mail nuevo)

        Body JSON:
        {
          "old_email": "viejo@example.com",   # obligatorio
          "new_email": "nuevo@example.com",   # obligatorio
        }
        """
        old_email = (body.get("old_email") or "").strip().lower()
        new_email = (body.get("new_email") or "").strip().lower()
        if not old_email or not new_email or "@" not in new_email:
            raise HTTPException(status_code=400, detail="old_email y new_email válidos son obligatorios")
        if old_email == new_email:
            raise HTTPException(status_code=400, detail="El email nuevo es igual al viejo")

        results: dict = {}

        # 1) Licencias del cliente (ACTIVAS + históricas) — actualizamos todas.
        r_lic = await coll.update_many(
            {"client_email": old_email},
            {"$set": {"client_email": new_email,
                      "email_changed_from": old_email,
                      "email_changed_at": _now().isoformat()}},
        )
        results["licenses_updated"] = r_lic.modified_count

        # 2) Subscriptions collection
        try:
            r_sub = await db.subscriptions.update_many(
                {"customer_email": old_email},
                {"$set": {"customer_email": new_email,
                          "email_changed_from": old_email,
                          "email_changed_at": _now().isoformat()}},
            )
            results["subscriptions_updated"] = r_sub.modified_count
        except Exception as ex:
            results["subscriptions_error"] = str(ex)

        # 3) Installations: linked_email
        try:
            r_ins = await db.installations.update_many(
                {"linked_email": old_email},
                {"$set": {"linked_email": new_email}},
            )
            results["installations_updated"] = r_ins.modified_count
        except Exception as ex:
            results["installations_error"] = str(ex)

        # 4) Stripe: actualiza el email del Customer para que reciba facturas nuevas
        results["stripe_customers_updated"] = 0
        results["stripe_error"] = None
        try:
            import stripe as _stripe
            _stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
            if _stripe.api_key:
                # Busca subscriptions con este email para localizar el/los customer_id
                async for sub_doc in db.subscriptions.find({"customer_email": new_email}):
                    cust_id = sub_doc.get("stripe_customer_id")
                    if cust_id:
                        try:
                            _stripe.Customer.modify(cust_id, email=new_email)
                            results["stripe_customers_updated"] += 1
                        except Exception as se:
                            results["stripe_error"] = str(se)
        except ImportError:
            results["stripe_error"] = "stripe SDK not installed"
        except Exception as ex:
            results["stripe_error"] = str(ex)

        await _audit(request, "license.change_email", old_email, extra={
            "new_email": new_email, **results,
        })

        return {"ok": True, "old_email": old_email, "new_email": new_email, **results}

    # ---------- Transfer to new device (Feb 2026 · God-mode) ----------
    @router.post(
        "/transfer",
        dependencies=[Depends(require_admin)],
    )
    async def transfer_license(body: dict, request: Request):
        """Transfiere una licencia del install_id viejo al nuevo.

        Casos manejados:
        1) **Licencia mono-dispositivo** (sin `linked_install_ids`):
           - Revoca la licencia vieja + genera CLAVE NUEVA para el nuevo install_id.
           - Copia `stripe_customer_id` + `stripe_subscription_id` (autopagos siguen).
           - Envía email al cliente con la nueva clave.

        2) **Licencia multi-dispositivo Premium** (con `linked_install_ids`):
           2a) Migrar el DISPOSITIVO PRINCIPAL:
               - Actualiza `install_id` a nuevo, mantiene `linked_install_ids` intactos.
               - Regenera JWT con `sub` portable → ambos dispositivos siguen funcionando con nueva clave.
               - El otro dispositivo debe re-copiar la nueva clave desde el email.
           2b) Migrar un DISPOSITIVO SECUNDARIO (linked):
               - Solo swap dentro de `linked_install_ids` (viejo → nuevo).
               - Mantiene la MISMA license_key. El otro dispositivo NO se entera.
               - Email opcional al cliente confirmando swap (sin adjuntar clave nueva).

        En todos los casos: revoca `installations[old_iid]` para bloquear reactivación silenciosa.
        """
        old_iid = (body.get("old_install_id") or "").strip().upper()
        new_iid = (body.get("new_install_id") or "").strip().upper()
        reason = (body.get("reason") or "").strip() or "device_transfer"
        send_email = bool(body.get("send_email", True))

        if not old_iid or not new_iid:
            raise HTTPException(status_code=400, detail="old_install_id y new_install_id son obligatorios")
        if old_iid == new_iid:
            raise HTTPException(status_code=400, detail="old y new install_id son iguales")

        # 1) Localiza la licencia asociada al viejo (como principal o linked)
        lic = await coll.find_one({
            "$or": [{"install_id": old_iid}, {"linked_install_ids": old_iid}],
            "status": "active",
        })
        if not lic:
            raise HTTPException(status_code=404, detail=f"No hay licencia activa vinculada a {old_iid}")

        plan = (lic.get("plan") or "STD").upper()
        client_name = lic.get("client_name") or ""
        client_email = lic.get("client_email") or ""
        linked_installs = [x for x in (lic.get("linked_install_ids") or []) if x]
        total_devices = 1 + len(linked_installs)
        is_principal = (old_iid == lic.get("install_id"))
        is_multi_device = total_devices > 1

        # 2) Marca old_iid en `installations` como revocada (independiente del flow)
        try:
            await db.installations.update_one(
                {"_id": old_iid},
                {"$set": {"revoked": True, "revoked_at": _now().isoformat(),
                          "revoked_reason": f"transferred_to:{new_iid}:{reason}"}},
                upsert=True,
            )
        except Exception as ex:
            logger.warning("installations upsert failed: %s", ex)

        # ---------- CASE B2: Migración de dispositivo SECUNDARIO (linked) ----------
        # No revocamos licencia, no regeneramos clave. Solo swap en linked_install_ids.
        if is_multi_device and not is_principal:
            new_linked = [new_iid if x == old_iid else x for x in linked_installs]
            await coll.update_one(
                {"_id": lic["_id"]},
                {"$set": {
                    "linked_install_ids": new_linked,
                    "linked_install_ids_updated_at": _now().isoformat(),
                }},
            )
            try:
                await db.sync_state.update_many(
                    {"install_id": old_iid},
                    {"$set": {"install_id": new_iid, "migrated_from": old_iid, "migrated_at": _now().isoformat()}},
                )
            except Exception:
                pass
            # También actualizamos subscriptions para consistencia (Premium tiene Stripe activo)
            try:
                await db.subscriptions.update_many(
                    {"install_id": old_iid},
                    {"$set": {"install_id": new_iid, "migrated_from": old_iid, "migrated_at": _now().isoformat()}},
                )
            except Exception:
                pass
            await _audit(request, "license.transfer_linked", old_iid, extra={
                "new_install_id": new_iid, "role": "linked_secondary", "reason": reason,
            })
            return {
                "ok": True,
                "case": "multi_device_secondary_swap",
                "old_install_id": old_iid,
                "new_install_id": new_iid,
                "old_license_revoked": False,
                "same_key_preserved": True,
                "message": "Dispositivo secundario reemplazado. La MISMA clave sigue siendo válida en el nuevo PC. El dispositivo principal no se entera.",
                "email_sent": False,
                "remaining_days": None,
            }

        # ---------- CASE A + B1: Migración de dispositivo PRINCIPAL o mono-dispositivo ----------
        # Calcula días restantes preservando duración
        remaining_days = lic.get("duration_days")
        expires_at_iso = lic.get("expires_at")
        if expires_at_iso:
            try:
                exp_dt = _to_dt(expires_at_iso)
                if exp_dt:
                    delta = (exp_dt - _now()).total_seconds() / 86400.0
                    remaining_days = max(1, int(delta))
            except Exception:
                pass

        # Revoca la licencia vieja
        await coll.update_one(
            {"_id": lic["_id"]},
            {"$set": {
                "status": "revoked",
                "revoked_at": _now().isoformat(),
                "revoked_reason": f"transferred_to:{new_iid}:{reason}",
            }},
        )

        # Genera licencia NUEVA (COPIANDO campos críticos de Stripe y multi-device)
        new_doc = await _create_license(
            install_id=new_iid,
            client_name=client_name,
            client_email=client_email,
            duration_days=remaining_days,
            plan=plan,
            notes=f"Transferida desde {old_iid} · motivo: {reason}",
        )

        # 🔒 CRITICAL FIX #1 · Copia campos de Stripe para que autopagos sigan funcionando
        # Cuando Stripe envía webhook de renewal, busca por stripe_subscription_id.
        # Sin este copy, los pagos futuros no encontrarían la licencia del cliente.
        stripe_fields_to_copy = {}
        for field in ["stripe_subscription_id", "stripe_customer_id",
                      "stripe_price_id", "stripe_product_id",
                      "billing_email", "checkout_session_id"]:
            if lic.get(field):
                stripe_fields_to_copy[field] = lic[field]

        # 🔒 CRITICAL FIX #2 · Si era Premium multi-device y transferimos el PRINCIPAL,
        # copiamos los linked_install_ids intactos para que el 2º device siga funcionando.
        # PERO el JWT nuevo tiene sub=new_iid (no portable), así que el 2º device fallará
        # al verificar con el nuevo key. La solución es que el cliente re-active en el 2º device
        # con la nueva clave. Lo indicamos claramente en la respuesta.
        also_copy_linked = is_multi_device and is_principal
        if also_copy_linked:
            stripe_fields_to_copy["linked_install_ids"] = linked_installs
            stripe_fields_to_copy["linked_install_ids_updated_at"] = _now().isoformat()

        if stripe_fields_to_copy:
            await coll.update_one(
                {"_id": new_doc["_id"] if "_id" in new_doc else new_doc.get("id")},
                {"$set": stripe_fields_to_copy},
            )
            # Actualiza el retorno con los campos copiados para reflejarlos
            new_doc.update(stripe_fields_to_copy)

        # Copia datos de sync (best effort)
        try:
            await db.sync_state.update_many(
                {"install_id": old_iid},
                {"$set": {"install_id": new_iid, "migrated_from": old_iid, "migrated_at": _now().isoformat()}},
            )
        except Exception:
            pass

        # 🔒 CRITICAL FIX #3 · Actualiza la colección `subscriptions` para que el botón
        # "Gestionar Subscripción" del cliente encuentre su suscripción Stripe en el PC nuevo.
        # (subscriptions se busca por install_id o customer_email indistintamente)
        try:
            await db.subscriptions.update_many(
                {"install_id": old_iid},
                {"$set": {"install_id": new_iid, "migrated_from": old_iid,
                          "migrated_at": _now().isoformat()}},
            )
        except Exception as ex:
            logger.warning("subscriptions update failed on transfer: %s", ex)

        # Email al cliente con nueva clave
        email_sent = False
        email_error = None
        if send_email and client_email:
            try:
                exp_dt = _to_dt(new_doc.get("expires_at"))
                ok, info = await mailer.send_license_email(
                    to_email=client_email,
                    client_name=client_name,
                    install_id=new_iid,
                    license_key=new_doc["license_key"],
                    plan=plan,
                    expires_at=exp_dt,
                )
                email_sent = ok
                if not ok:
                    email_error = info
            except Exception as ex:
                email_error = str(ex)

        await _audit(request, "license.transfer", old_iid, extra={
            "new_install_id": new_iid, "new_license_id": new_doc["id"], "reason": reason,
            "email_sent": email_sent, "stripe_fields_copied": list(stripe_fields_to_copy.keys()),
            "also_copy_linked": also_copy_linked,
        })

        return {
            "ok": True,
            "case": "principal_or_single_device_regen",
            "old_install_id": old_iid,
            "new_install_id": new_iid,
            "new_license": _doc_to_record(new_doc, include_key=True).model_dump(mode="json"),
            "old_license_revoked": True,
            "stripe_fields_preserved": list(stripe_fields_to_copy.keys()),
            "linked_devices_also_need_reactivation": also_copy_linked,
            "linked_install_ids_preserved": linked_installs if also_copy_linked else None,
            "email_sent": email_sent,
            "email_error": email_error,
            "remaining_days": remaining_days,
        }

    # ---------- Verify (public, rate-limited) ----------
    @router.post("/verify", response_model=LicenseVerifyResponse)
    @_rate("60/minute")
    async def verify_license(request: Request, body: LicenseVerify) -> LicenseVerifyResponse:
        """Valida una llicència. Pública: la crida el client v2.html."""
        # 1) Decode JWT (sub és opcional per suportar claus portables: trials i Stripe)
        try:
            payload = jwt.decode(
                body.key,
                _secret(),
                algorithms=[JWT_ALG],
                issuer=_issuer(),
                options={"require": ["iss", "jti", "iat"]},
            )
        except jwt.ExpiredSignatureError:
            return LicenseVerifyResponse(
                ok=False, expired=True, reason="Licencia expirada", install_id=body.install_id
            )
        except jwt.InvalidTokenError as ex:
            return LicenseVerifyResponse(ok=False, reason=f"Clave inválida: {ex}",
                                         install_id=body.install_id)

        # 2) Comprovació del subject amb suport per claus portables (bind-on-verify)
        jwt_sub = payload.get("sub")
        portable = (
            not jwt_sub
            or str(jwt_sub).upper().startswith("CD-TRIAL-")
            or str(jwt_sub).upper().startswith("CD-STRIPE-")
        )
        if jwt_sub and not portable and jwt_sub != body.install_id:
            return LicenseVerifyResponse(
                ok=False,
                reason="La clave no corresponde a esta instalación",
                install_id=body.install_id,
            )

        # 3) Busquem la llicència a la DB per l'id (jti)
        doc = await coll.find_one({"id": payload["jti"]})
        if not doc:
            return LicenseVerifyResponse(
                ok=False, reason="Licencia desconocida en el servidor",
                install_id=body.install_id,
            )

        if doc.get("status") == "revoked":
            return LicenseVerifyResponse(
                ok=False,
                revoked=True,
                status="revoked",
                reason=doc.get("revoked_reason") or "Licencia revocada",
                install_id=body.install_id,
                client_name=doc.get("client_name"),
                plan=doc.get("plan"),
                expires_at=_to_dt(doc.get("expires_at")),
            )

        expires_at = _to_dt(doc.get("expires_at"))
        if expires_at and expires_at < _now():
            await coll.update_one({"_id": doc["_id"]}, {"$set": {"status": "expired"}})
            return LicenseVerifyResponse(
                ok=False, expired=True, status="expired",
                reason="Licencia expirada",
                install_id=body.install_id, client_name=doc.get("client_name"),
                plan=doc.get("plan"), expires_at=expires_at,
            )

        # 💡 Retention: registrem l'última vegada que el client va verificar
        # la seva llicència (= última vegada que va obrir l'app). Útil per
        # veure clients inactius i contactar-los proactivament.
        try:
            await coll.update_one(
                {"_id": doc["_id"]},
                {"$set": {"last_verify_at": _now().isoformat()},
                 "$inc": {"verify_count": 1}},
            )
        except Exception:
            pass  # no bloquejar mai el verify per un error de tracking

        # 3.5) HWID lock multi-dispositiu:
        # · Standard/Trial: 1 HWID (hwid_lock)
        # · Premium: fins a 2 HWIDs (hwid_lock + linked_hwids)
        stored_hwid = (doc.get("hwid_lock") or "").strip()
        linked_hwids = [h for h in (doc.get("linked_hwids") or []) if h]
        req_hwid = (body.hwid or "").strip()
        plan_upper = str(doc.get("plan") or "").upper()
        max_devices = 2 if plan_upper == "PREMIUM" else 1
        if req_hwid:
            all_bound = ([stored_hwid] if stored_hwid else []) + linked_hwids
            if req_hwid in all_bound:
                # Ja registrat, seguim endavant
                pass
            elif not stored_hwid:
                # Primera vegada → binding principal
                await coll.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"hwid_lock": req_hwid, "hwid_locked_at": _now().isoformat()}},
                )
                logger.info("HWID binding (primary) for %s → %s", body.install_id, req_hwid)
            elif len(all_bound) < max_devices:
                # Encara hi ha slots → afegim com a HWID vinculat (Premium 2n dispositiu)
                new_linked = linked_hwids + [req_hwid]
                await coll.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"linked_hwids": new_linked,
                              "linked_hwids_updated_at": _now().isoformat()}},
                )
                logger.info("HWID binding (device #%s) for %s → %s (plan=%s max=%s)",
                            len(all_bound)+1, body.install_id, req_hwid, plan_upper, max_devices)
            else:
                # Slots plens → rebutgem
                logger.warning(
                    "HWID limit reached for %s (bound=%s, request=%s, max=%s)",
                    body.install_id, all_bound, req_hwid, max_devices,
                )
                msg_multi = (
                    f"Esta licencia {plan_upper} ya está en uso en {max_devices} ordenador"
                    f"{'es' if max_devices > 1 else ''}. "
                    "Contacta con el proveedor para hacer el cambio."
                )
                return LicenseVerifyResponse(
                    ok=False,
                    hwid_mismatch=True,
                    status="active",
                    reason=msg_multi,
                    install_id=body.install_id,
                    client_name=doc.get("client_name"),
                    plan=doc.get("plan"),
                    expires_at=expires_at,
                )

        # 3.6) Install-ID bind: 1r dispositiu → `install_id` principal.
        # Dispositius addicionals (Premium 2n dispositiu) → array `linked_install_ids`.
        stored_install = (doc.get("install_id") or "").strip()
        linked_installs = [i for i in (doc.get("linked_install_ids") or []) if i]
        if body.install_id:
            is_portable_placeholder = (
                not stored_install
                or stored_install.upper().startswith("CD-TRIAL-PENDING-")
                or stored_install.upper().startswith("CD-STRIPE-PENDING-")
            )
            already_bound = (body.install_id == stored_install) or (body.install_id in linked_installs)
            if is_portable_placeholder:
                await coll.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "install_id": body.install_id,
                        "install_id_bound_at": _now().isoformat(),
                    }},
                )
                logger.info("install_id binding for jti=%s → %s (was %s)",
                            doc.get("id"), body.install_id, stored_install)
            elif not already_bound and plan_upper == "PREMIUM" and len(linked_installs) + 1 < max_devices:
                # Premium admet un install_id addicional (2n dispositiu)
                new_linked = linked_installs + [body.install_id]
                await coll.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "linked_install_ids": new_linked,
                        "linked_install_ids_updated_at": _now().isoformat(),
                    }},
                )
                logger.info("linked install_id added (Premium device #%s) for jti=%s → %s",
                            len(new_linked) + 1, doc.get("id"), body.install_id)

        # 4) Tot OK → actualitzem estadístiques
        _upd_set = {"last_verified_at": _now().isoformat()}
        # 📊 Facturación anual (privada, solo admin): merge sanitizado por año
        # El cliente envía {by_year: {"2024": 152340, "2025": 87220}} en cada verify.
        # Guardamos solo enteros positivos y años razonables (2000-2100).
        try:
            fstats = body.facturacion_stats or {}
            by_year = fstats.get("by_year") if isinstance(fstats, dict) else None
            if isinstance(by_year, dict) and by_year:
                clean_by_year: dict = {}
                for yk, yv in list(by_year.items())[:60]:
                    try:
                        y = int(str(yk).strip())
                        v = int(round(float(yv)))
                        if 2000 <= y <= 2100 and 0 <= v < 10_000_000_000:
                            clean_by_year[str(y)] = v
                    except Exception:
                        continue
                if clean_by_year:
                    # Merge con lo ya guardado para no perder años pasados
                    prev = (doc.get("facturacion_by_year") or {}) if isinstance(doc.get("facturacion_by_year"), dict) else {}
                    merged = {**prev, **clean_by_year}
                    _upd_set["facturacion_by_year"] = merged
                    _upd_set["facturacion_updated_at"] = _now().isoformat()
        except Exception:
            pass
        # Guardar meta info que el cliente sincroniza (empresas configuradas, versión, etc.)
        if body.client_meta and isinstance(body.client_meta, dict):
            # Sanea a strings/números básicos para evitar objetos pesados
            _clean_meta = {}
            for k, v in list(body.client_meta.items())[:20]:  # máximo 20 campos
                if isinstance(v, (str, int, float, bool)) or v is None:
                    _clean_meta[str(k)[:64]] = (v if not isinstance(v, str) else v[:500])
            if _clean_meta:
                _upd_set["client_meta"] = _clean_meta
                _upd_set["client_meta_updated_at"] = _now().isoformat()
                # Propaga datos de contacto que el cliente cambie en su app a los
                # campos top-level de la licencia (aparecerán en el panel admin).
                # Los campos aceptados están mapeados a un alias del cliente.
                _CONTACT_MAP = {
                    "client_name": "client_name",
                    "company_name": "client_name",  # alias
                    "empresa": "client_name",
                    "contact_name": "contact_name",
                    "persona_contacto": "contact_name",
                    "phone": "phone",
                    "telefono": "phone",
                    "teléfono": "phone",
                    "tax_id": "tax_id",
                    "nif": "tax_id",
                    "cif": "tax_id",
                    "client_email": "client_email",
                    "email": "client_email",
                }
                for k, v in list(_clean_meta.items()):
                    lic_field = _CONTACT_MAP.get(str(k).lower().strip())
                    if lic_field and isinstance(v, str) and v.strip():
                        _upd_set[lic_field] = v.strip()
                        _upd_set["contact_updated_at"] = _now().isoformat()
        await coll.update_one(
            {"_id": doc["_id"]},
            {
                "$set": _upd_set,
                "$inc": {"verify_count": 1},
            },
        )

        # 4.5) Si l'admin ha extès la llicència, el JWT del client encara té l'exp antiga.
        # Comparem el `exp` del token amb `expires_at` de la DB i re-emitim si cal.
        new_key_out: Optional[str] = None
        try:
            jwt_exp_ts = int(payload.get("exp") or 0)
            db_exp_ts = int(expires_at.timestamp()) if expires_at else 0
            # Re-emitim si:
            #  · La DB té data d'expiració i el JWT NO en té (permanent → limitat) o
            #  · La DB té data d'expiració més tardana que el JWT (extensió)
            if db_exp_ts and (jwt_exp_ts == 0 or db_exp_ts > jwt_exp_ts + 60):
                new_key_out = _mint_jwt(
                    install_id=payload.get("sub") or body.install_id,
                    license_id=doc.get("id"),
                    plan=doc.get("plan") or "",
                    expires_at=expires_at,
                )
                # També actualitzem el license_key emmagatzemat a la DB perquè coincideixi
                await coll.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"license_key": new_key_out, "license_key_reissued_at": _now().isoformat()}},
                )
                logger.info("Re-issued JWT for %s (extension: exp %s → %s)",
                            body.install_id, jwt_exp_ts, db_exp_ts)
        except Exception as ex:
            logger.warning("Could not re-issue JWT for %s: %s", body.install_id, ex)
        return LicenseVerifyResponse(
            ok=True,
            status="active",
            install_id=body.install_id,
            client_name=doc.get("client_name"),
            plan=doc.get("plan"),
            expires_at=expires_at,
            new_key=new_key_out,
        )

    # ---------- Revoke ----------
    @router.post(
        "/revoke",
        response_model=LicenseRecord,
        dependencies=[Depends(require_admin)],
    )
    async def revoke_license(body: LicenseRevoke, request: Request) -> LicenseRecord:
        doc = await coll.find_one({"install_id": body.install_id, "status": "active"})
        if not doc:
            raise HTTPException(
                status_code=404, detail="No hi ha llicència activa per aquest install_id"
            )
        await coll.update_one(
            {"_id": doc["_id"]},
            {"$set": {
                "status": "revoked",
                "revoked_at": _now().isoformat(),
                "revoked_reason": body.reason or "revoked_by_admin",
            }},
        )
        await _audit(request, "license.revoke", body.install_id, extra={"reason": body.reason})
        updated = await coll.find_one({"_id": doc["_id"]})
        return _doc_to_record(updated)

    # ---------- Unrevoke (reactivar licencia bloqueada) ----------
    @router.post(
        "/unrevoke",
        response_model=LicenseRecord,
        dependencies=[Depends(require_admin)],
    )
    async def unrevoke_license(request: Request) -> LicenseRecord:
        """Reactiva una licencia previamente revocada (bloqueada por admin).

        Solo funciona si `status == "revoked"`. No toca `expires_at`, así que
        si la licencia ya caducó el cliente verá el mismo estado que antes de
        bloquearla (deberá renovar). Idempotente vía audit_logs.
        """
        payload = await request.json()
        install_id = (payload.get("install_id") or "").strip()
        if not install_id:
            raise HTTPException(status_code=400, detail="install_id requerido")
        doc = await coll.find_one({"install_id": install_id, "status": "revoked"},
                                  sort=[("revoked_at", -1)])
        if not doc:
            raise HTTPException(status_code=404, detail="No hay licencia revocada para este install_id")
        await coll.update_one(
            {"_id": doc["_id"]},
            {"$set": {
                "status": "active",
                "revoked_at": None,
                "revoked_reason": None,
                "reactivated_at": _now().isoformat(),
                "reactivated_by": "admin_ui",
            }},
        )
        await _audit(request, "license.unrevoke", install_id,
                     extra={"prev_revoked_reason": doc.get("revoked_reason")})
        updated = await coll.find_one({"_id": doc["_id"]})
        return _doc_to_record(updated)

    # ---------- Hard Delete (borra TODO histórico del cliente) ----------
    @router.post(
        "/hard-delete",
        dependencies=[Depends(require_admin)],
    )
    async def hard_delete_license(request: Request) -> dict:
        """Borra por completo todas las licencias asociadas a un install_id.

        Uso: cuando el admin quiere QUITAR a alguien de la lista definitivamente
        (no solo bloquearle el acceso). Deja el registro en `audit_logs` para
        trazabilidad. También cancela suscripción Stripe si existe.
        """
        payload = await request.json()
        install_id = (payload.get("install_id") or "").strip()
        confirm = payload.get("confirm") == True
        reason = (payload.get("reason") or "hard_deleted_by_admin").strip()
        if not install_id:
            raise HTTPException(status_code=400, detail="install_id requerido")
        if not confirm:
            raise HTTPException(status_code=400, detail="Debe confirmar el borrado (confirm=true)")

        # 1) Cancela suscripciones Stripe activas asociadas
        docs_to_delete = await coll.find({"install_id": install_id}).to_list(length=None)
        cancelled_subs = []
        try:
            import os as _os
            import stripe as _stripe_sdk  # type: ignore
            stripe_key = (_os.environ.get("STRIPE_API_KEY") or "").strip()
            if stripe_key:
                _stripe_sdk.api_key = stripe_key
                for d in docs_to_delete:
                    sub_id = d.get("stripe_subscription_id")
                    if sub_id and sub_id not in cancelled_subs:
                        try:
                            _stripe_sdk.Subscription.delete(sub_id)
                            cancelled_subs.append(sub_id)
                        except Exception as ex:
                            logger.warning("Stripe cancel failed for %s: %s", sub_id, ex)
        except Exception as ex:  # noqa: BLE001
            logger.warning("Stripe SDK unavailable during hard-delete: %s", ex)

        # 2) Borra todas las licencias con ese install_id
        result = await coll.delete_many({"install_id": install_id})
        deleted_count = result.deleted_count

        # 3) Borra también instalaciones tracking
        try:
            db_ref = coll.database
            await db_ref.installations.delete_many({"install_id": install_id})
        except Exception as ex:  # noqa: BLE001
            logger.warning("installations cleanup failed: %s", ex)

        await _audit(request, "license.hard_delete", install_id,
                     extra={"deleted_licenses": deleted_count,
                            "cancelled_stripe_subs": cancelled_subs,
                            "reason": reason})
        return {
            "ok": True,
            "install_id": install_id,
            "deleted_licenses": deleted_count,
            "cancelled_stripe_subs": cancelled_subs,
        }


    # ---------- Current active license (public, per polling d'auto-upgrade) ----------
    @router.get("/current")
    @_rate("60/minute")
    async def current_license(request: Request, install_id: str, email: Optional[str] = None) -> dict:
        """
        Retorna la llicència activa més recent per un install_id o email.
        Usat pel polling del client per detectar auto-upgrades de plan
        (ex: Trial → Standard/Premium després d'una compra Stripe).

        Cerca en aquest ordre:
        1) Llicència ACTIVE amb `install_id` exacte
        2) Llicència ACTIVE portable (CD-TRIAL-PENDING/CD-STRIPE-*) amb `client_email` coincident
        3) Llicència ACTIVE més recent per `client_email` (fallback)
        """
        install_id_norm = (install_id or "").strip()
        email_norm = (email or "").strip().lower() or None
        if not install_id_norm and not email_norm:
            raise HTTPException(status_code=400, detail="install_id o email requerido")

        doc = None
        # 1) Match directe per install_id (principal) O linked_install_ids (Premium 2n dispositiu)
        if install_id_norm:
            doc = await coll.find_one(
                {"status": "active",
                 "$or": [
                     {"install_id": install_id_norm},
                     {"linked_install_ids": install_id_norm},
                 ]},
                sort=[("created_at", -1)],
            )
        # 2) Fallback per email (útil després d'un upgrade abans que la clau nova arribi)
        if not doc and email_norm:
            doc = await coll.find_one(
                {"client_email": email_norm, "status": "active"},
                sort=[("created_at", -1)],
            )
        if not doc:
            return {"ok": False, "found": False}

        return {
            "ok": True,
            "found": True,
            "license_key": doc.get("license_key"),
            "jti": doc.get("id"),
            "install_id": doc.get("install_id"),
            "plan": doc.get("plan"),
            "status": doc.get("status"),
            "expires_at": doc.get("expires_at"),
            "client_name": doc.get("client_name"),
            "client_email": doc.get("client_email"),
            "source": doc.get("source") or doc.get("notes", "").split(" ")[0] if doc.get("notes") else None,
        }

    # ---------- Stats (admin dashboard) ----------
    @router.get(
        "/stats",
        dependencies=[Depends(require_admin)],
    )
    async def get_stats() -> dict:
        """
        Retorna estadístiques agregades per al panel admin:
        - Comptadors llicències per estat i pla
        - Projecció d'ingressos MRR/ARR
        - Estat de sol·licituds + taxa de conversió
        - Activitat (noves llicències 7d/30d, top clients per verify)
        - Estadístiques HWID lock
        """
        from datetime import timedelta as _td
        now = _now()
        cutoff_7d = (now - _td(days=7)).isoformat()
        cutoff_30d = (now - _td(days=30)).isoformat()

        # Preus per plan × duració (han de coincidir amb PACKAGES a payments.py)
        PRICES = {
            ("STD", 30): 29.90, ("STD", 365): 299.90,
            ("PREMIUM", 30): 39.90, ("PREMIUM", 365): 399.90,
        }

        licenses_docs = await coll.find({}, {"_id": 0}).to_list(5000)
        requests_docs = await req_coll.find({}, {"_id": 0}).to_list(5000)

        # Llicències
        by_status = {"active": 0, "revoked": 0, "expired": 0}
        by_plan = {}
        with_hwid_lock = 0
        hwid_resets_total = 0
        new_7d = 0
        new_30d = 0
        verify_total = 0
        top_clients = []

        for lic in licenses_docs:
            st = lic.get("status", "active")
            by_status[st] = by_status.get(st, 0) + 1
            plan = lic.get("plan", "STD")
            by_plan[plan] = by_plan.get(plan, 0) + 1
            if lic.get("hwid_lock"):
                with_hwid_lock += 1
            hwid_resets_total += int(lic.get("hwid_reset_count", 0) or 0)
            created = str(lic.get("created_at") or "")
            if created >= cutoff_7d:
                new_7d += 1
            if created >= cutoff_30d:
                new_30d += 1
            vc = int(lic.get("verify_count", 0) or 0)
            verify_total += vc
            if lic.get("status") == "active":
                top_clients.append({
                    "install_id": lic.get("install_id"),
                    "client_name": lic.get("client_name", ""),
                    "plan": plan,
                    "verify_count": vc,
                    "last_verified_at": lic.get("last_verified_at"),
                })
        top_clients.sort(key=lambda x: x["verify_count"], reverse=True)
        top_clients = top_clients[:5]

        # Ingressos projectats (nomes actives)
        mrr = 0.0
        by_plan_revenue = {}
        for lic in licenses_docs:
            if lic.get("status") != "active":
                continue
            plan = lic.get("plan", "STD")
            if plan not in ("STD", "PREMIUM"):
                continue  # TRIAL / MASTER no compten com a ingressos
            dur = int(lic.get("duration_days") or 0)
            # Determinem si es mensual o anual pels dies
            if dur == 30 or (25 <= dur <= 45):
                period = 30
            elif dur == 365 or (350 <= dur <= 380):
                period = 365
            else:
                continue  # TRIAL / perpetual → sense projecció
            price = PRICES.get((plan, period), 0.0)
            monthly_equiv = price if period == 30 else round(price / 12, 2)
            mrr += monthly_equiv
            key = f"{plan}_{'MES' if period == 30 else 'ANY'}"
            if key not in by_plan_revenue:
                by_plan_revenue[key] = {"count": 0, "monthly_equiv": 0.0, "unit_price": price}
            by_plan_revenue[key]["count"] += 1
            by_plan_revenue[key]["monthly_equiv"] = round(
                by_plan_revenue[key]["monthly_equiv"] + monthly_equiv, 2
            )
        mrr = round(mrr, 2)
        arr = round(mrr * 12, 2)

        # Sol·licituds
        req_by_status = {"pending": 0, "approved": 0, "rejected": 0}
        for r in requests_docs:
            st = r.get("status", "pending")
            req_by_status[st] = req_by_status.get(st, 0) + 1
        total_processed = req_by_status["approved"] + req_by_status["rejected"]
        conversion_rate = (
            round(req_by_status["approved"] / total_processed, 3)
            if total_processed > 0 else None
        )

        return {
            "generated_at": now.isoformat(),
            "licenses": {
                "total": len(licenses_docs),
                "active": by_status.get("active", 0),
                "revoked": by_status.get("revoked", 0),
                "expired": by_status.get("expired", 0),
                "by_plan": by_plan,
                "with_hwid_lock": with_hwid_lock,
                "hwid_resets_total": hwid_resets_total,
                "verify_total": verify_total,
            },
            "revenue": {
                "mrr_eur": mrr,
                "arr_eur": arr,
                "by_plan": by_plan_revenue,
                "currency": "EUR",
            },
            "requests": {
                **req_by_status,
                "total": len(requests_docs),
                "conversion_rate": conversion_rate,
            },
            "activity": {
                "new_last_7d": new_7d,
                "new_last_30d": new_30d,
            },
            "top_clients": top_clients,
        }

    # ---------- Reset HWID lock (admin) ----------
    @router.post(
        "/{install_id}/reset-hwid",
        dependencies=[Depends(require_admin)],
    )
    async def reset_hwid_lock(install_id: str, request: Request) -> dict:
        """
        Desbloqueja el HWID lock d'una llicència activa.
        Cal fer-ho quan un client legítim canvia d'ordinador.
        La propera verificació re-vinculara la llicència al nou HWID.
        """
        install_id = install_id.strip().upper()
        doc = await coll.find_one({"install_id": install_id, "status": "active"})
        if not doc:
            raise HTTPException(status_code=404, detail="No hi ha llicència activa per aquest install_id")
        prev_hwid = doc.get("hwid_lock") or ""
        prev_count = int(doc.get("hwid_reset_count") or 0)
        await coll.update_one(
            {"_id": doc["_id"]},
            {"$set": {
                "hwid_lock": None,
                "hwid_locked_at": None,
                "hwid_reset_count": prev_count + 1,
                "hwid_last_reset_at": _now().isoformat(),
            }},
        )
        await _audit(request, "license.reset_hwid", install_id, extra={"prev_hwid": prev_hwid})
        return {
            "ok": True,
            "install_id": install_id,
            "message": "HWID desbloquejat. La propera activació al nou PC lligarà la llicència automàticament.",
            "reset_count": prev_count + 1,
        }

    # ---------- Delete (RGPD C6) ----------
    @router.delete(
        "/{install_id}",
        dependencies=[Depends(require_admin)],
    )
    async def delete_license(install_id: str, request: Request) -> dict:
        """Hard-delete a license and its requests. RGPD right-to-erasure."""
        install_id = install_id.strip().upper()
        r1 = await coll.delete_many({"install_id": install_id})
        r2 = await req_coll.delete_many({"install_id": install_id})
        await _audit(request, "license.delete", install_id, extra={"licenses_removed": r1.deleted_count, "requests_removed": r2.deleted_count})
        return {"deleted": True, "licenses_removed": r1.deleted_count, "requests_removed": r2.deleted_count}

    # ---------- Editar datos de contacto (admin) ----------
    @router.patch(
        "/{install_id}/contact",
        dependencies=[Depends(require_admin)],
    )
    async def update_license_contact(install_id: str, request: Request, body: UpdateContactBody) -> dict:
        """Actualiza los datos de contacto de una licencia desde el panel admin.
        Solo actualiza los campos enviados; None = no cambiar. Cadena vacía = borrar."""
        install_id = install_id.strip().upper()
        patch: dict = {}
        # Trata cadena vacía como "borrar" (None → no tocar)
        for field, value in body.model_dump(exclude_none=True).items():
            v = str(value).strip() if value is not None else ""
            patch[field] = v or None
        if not patch:
            raise HTTPException(status_code=400, detail="no_fields_to_update")
        patch["contact_updated_at"] = _now().isoformat()
        result = await coll.update_one({"install_id": install_id}, {"$set": patch})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="license_not_found")
        await _audit(request, "license.contact_update", install_id, extra={"fields": list(patch.keys())})
        doc = await coll.find_one({"install_id": install_id}, {"_id": 0})
        return {"ok": True, "modified": result.modified_count, "license": _doc_to_record(doc).model_dump() if doc else None}

    # ---------- Export (RGPD C5) ----------
    @router.get(
        "/{install_id}/export",
        dependencies=[Depends(require_admin)],
    )
    async def export_license(install_id: str, request: Request) -> dict:
        """Return all data associated with an install_id. RGPD right of access."""
        install_id = install_id.strip().upper()
        licenses_docs = await coll.find({"install_id": install_id}, {"_id": 0}).to_list(200)
        requests_docs = await req_coll.find({"install_id": install_id}, {"_id": 0}).to_list(200)
        audit_docs = await audit_coll.find({"target": install_id}, {"_id": 0}).sort("timestamp", -1).to_list(500)
        await _audit(request, "license.export", install_id)
        return {
            "install_id": install_id,
            "exported_at": _now().isoformat(),
            "licenses": licenses_docs,
            "requests": requests_docs,
            "audit_log": audit_docs,
        }

    # ---------- 🧹 PURGE de datos de prueba (Feb 2026) ----------
    #   Elimina TODAS las licencias, suscripciones, pagos y datos ligados
    #   EXCEPTO las que coincidan con `keep_emails` (lista de emails a conservar).
    #   MASTER (owner) siempre se conserva (no está en `licenses`).
    #   Requiere admin token. Devuelve un resumen detallado de qué se ha borrado.
    @router.post(
        "/admin/purge-test-data",
        dependencies=[Depends(require_admin)],
    )
    async def purge_test_data(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        keep_emails = body.get("keep_emails") or []
        if isinstance(keep_emails, str):
            keep_emails = [keep_emails]
        keep_emails_lower = [e.lower().strip() for e in keep_emails if e]
        confirm = body.get("confirm") or ""
        if confirm != "SI-BORRAR-TODO-EXCEPTO-KEEP":
            raise HTTPException(
                status_code=400,
                detail="Requires body {confirm: 'SI-BORRAR-TODO-EXCEPTO-KEEP', keep_emails: [...]}",
            )
        # 1) Identificar licencias a conservar (por email)
        keep_docs = []
        if keep_emails_lower:
            keep_docs = await coll.find(
                {"client_email": {"$in": keep_emails_lower}}, {"install_id": 1, "_id": 0}
            ).to_list(100)
        keep_install_ids = [d["install_id"] for d in keep_docs if d.get("install_id")]

        # 2) Identificar TODAS las licencias a borrar
        all_lics = await coll.find({}, {"install_id": 1, "client_email": 1, "_id": 0}).to_list(2000)
        del_install_ids = [
            l["install_id"] for l in all_lics
            if l.get("install_id") and l.get("install_id") not in keep_install_ids
        ]

        summary = {
            "keep_emails": keep_emails_lower,
            "keep_install_ids": keep_install_ids,
            "deleted": {},
        }

        # 3) Borrar de las colecciones ligadas a install_id (si hay install_ids a borrar)
        collections_with_install_id = [
            "licenses", "installations", "sync_devices", "sync_cloud_backups",
            "sms_campaigns", "sms_usage_medicar", "sms_usage_errors",
            "support_messages", "license_audit", "license_requests",
            "subscriptions", "payments", "referrals",
            "cloudbackup_events", "renewal_reminders_sent",
        ]
        all_colls_available = await db.list_collection_names()
        if del_install_ids:
            for coll_name in collections_with_install_id:
                if coll_name not in all_colls_available:
                    continue
                try:
                    # target=install_id (audit log usa 'target' en algunos casos)
                    q = {"install_id": {"$in": del_install_ids}}
                    res = await db[coll_name].delete_many(q)
                    if res.deleted_count > 0:
                        summary["deleted"][coll_name] = res.deleted_count
                    # Extra: license_audit puede usar `target` en lugar de install_id
                    if coll_name == "license_audit":
                        res2 = await db[coll_name].delete_many({"target": {"$in": del_install_ids}})
                        if res2.deleted_count > 0:
                            summary["deleted"][coll_name] = summary["deleted"].get(coll_name, 0) + res2.deleted_count
                except Exception as e:
                    logger.exception(f"purge · fallo en {coll_name}: {e}")
                    summary["deleted"][coll_name] = f"ERROR: {e}"

        # 4) Borrar suscripciones Stripe huérfanas (por email de test si no llevan install_id)
        try:
            if "subscriptions" in all_colls_available:
                res = await db["subscriptions"].delete_many({
                    "customer_email": {"$nin": keep_emails_lower + [None, ""]}
                })
                if res.deleted_count > 0:
                    summary["deleted"]["subscriptions_by_email"] = res.deleted_count
        except Exception as e:
            logger.warning(f"purge subscriptions by email fallado: {e}")

        # 5) Borrar PAYMENTS (colección Stripe invoices) que NO pertenecen a los emails conservados.
        #   `payments` no tiene install_id; se filtra por `customer_email`.
        #   Esto es lo que hace bajar el "Total facturado" del dashboard a 0€ tras purgar test data.
        try:
            if "payments" in all_colls_available:
                # Borrar todos EXCEPTO los que tengan customer_email dentro de keep_emails
                if keep_emails_lower:
                    res = await db["payments"].delete_many({
                        "customer_email": {"$nin": keep_emails_lower}
                    })
                else:
                    res = await db["payments"].delete_many({})
                if res.deleted_count > 0:
                    summary["deleted"]["payments_all"] = res.deleted_count
        except Exception as e:
            logger.warning(f"purge payments fallado: {e}")

        # 6) Recalcular stats globales (billing counters)
        summary["remaining_licenses"] = await coll.count_documents({})
        if "subscriptions" in all_colls_available:
            summary["remaining_subscriptions"] = await db["subscriptions"].count_documents({})
        if "payments" in all_colls_available:
            summary["remaining_payments"] = await db["payments"].count_documents({})
            pipeline = [{"$match": {"status": "paid"}}, {"$group": {"_id": None, "total_cents": {"$sum": "$amount_cents"}}}]
            total_cents = 0
            async for d in db["payments"].aggregate(pipeline):
                total_cents = d.get("total_cents", 0) or 0
            summary["remaining_total_paid_eur"] = round(total_cents / 100.0, 2)

        # Audit
        try:
            await _audit(request, "licenses.purge_test_data", "*", extra={
                "keep_emails": keep_emails_lower,
                "deleted_install_ids_count": len(del_install_ids),
                "deleted_summary": summary["deleted"],
            })
        except Exception:
            pass

        return summary

    # ---------- List ----------
    @router.get(
        "",
        response_model=LicenseListResponse,
        dependencies=[Depends(require_admin)],
    )
    async def list_licenses(
        status_filter: Optional[str] = Query(None, alias="status"),
        limit: int = Query(200, ge=1, le=1000),
    ) -> LicenseListResponse:
        await _backfill_contact_data()  # one-shot
        query: dict[str, Any] = {}
        if status_filter:
            query["status"] = status_filter
        cursor = coll.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
        docs = await cursor.to_list(limit)
        # 👑 Feb 2026 · Inyectar entradas sintéticas del propio MASTER (owner)
        #   para que aparezcan en el panel admin. El MASTER no está en `db.licenses`
        #   (validación offline con MASTER_KEY hardcodeada), así que se lee de
        #   `sync_devices` cada install_id que haya enviado alguna copia a la nube.
        try:
            import hashlib as _hashlib
            MASTER_KEY_LITERAL = "MB-MASTER-BRUGULAT-2026-OWNER"
            master_lkh = _hashlib.sha256(MASTER_KEY_LITERAL.encode()).hexdigest()
            master_devices = await db["sync_devices"].find(
                {"license_key_hash": master_lkh},
                {"install_id": 1, "created_at": 1, "last_seen": 1, "_id": 0},
            ).sort("last_seen", -1).to_list(length=20)
            if master_devices:
                # Un row por cada instalación real del owner
                for md in master_devices:
                    iid = md.get("install_id")
                    if not iid: continue
                    if any(d.get("install_id") == iid for d in docs): continue
                    synthetic = {
                        "install_id": iid,
                        "client_name": "👑 MediCar Plus (owner)",
                        "client_email": "owner@medicarplus.es",
                        "plan": "MASTER",
                        "status": "active",
                        "created_at": md.get("created_at") or _now(),
                        "expires_at": None,
                        "duration_days": None,
                        "notes": "Cuenta propia del proveedor (MASTER key).",
                        "last_verified_at": md.get("last_seen"),
                        "verify_count": 0,
                        "_synthetic_master": True,
                    }
                    docs.insert(0, synthetic)
            else:
                # Placeholder visible aunque aún no haya instalación registrada.
                # Así el owner SIEMPRE aparece en el panel, incluso justo tras deploy
                # sin que su cliente haya vuelto a abrir la app.
                placeholder = {
                    "install_id": "__owner_pending__",
                    "client_name": "👑 MediCar Plus (owner) · aún no ha enviado copia",
                    "client_email": "owner@medicarplus.es",
                    "plan": "MASTER",
                    "status": "active",
                    "created_at": _now(),
                    "expires_at": None,
                    "duration_days": None,
                    "notes": "Abre la app en tu ordenador y pulsa 'Enviar copia AHORA' para que aparezca aquí con datos reales.",
                    "last_verified_at": None,
                    "verify_count": 0,
                    "_synthetic_master": True,
                    "_placeholder": True,
                }
                docs.insert(0, placeholder)
        except Exception:  # noqa: BLE001
            logger.exception("failed to inject master entries")
        # Enriquece cada licencia con message_count agregado desde support_messages
        try:
            iids = [d.get("install_id") for d in docs if d.get("install_id")]
            if iids:
                pipeline = [
                    {"$match": {"install_id": {"$in": iids}, "direction": "inbound"}},
                    {"$group": {"_id": "$install_id", "count": {"$sum": 1}, "last_at": {"$max": "$sent_at"}}},
                ]
                counts_map: dict = {}
                async for row in db["support_messages"].aggregate(pipeline):
                    counts_map[row["_id"]] = {"count": row.get("count", 0), "last": row.get("last_at")}
                for d in docs:
                    stats = counts_map.get(d.get("install_id"), {})
                    d["message_count"] = stats.get("count", 0)
                    d["last_message_at"] = stats.get("last")
        except Exception:  # noqa: BLE001
            logger.exception("failed to enrich message counts")
        return LicenseListResponse(
            total=len(docs),
            items=[_doc_to_record(d) for d in docs],
        )

    # ---------- Ajustar dies d'una llicència TRIAL (extend/reduce) ----------
    @router.post("/{install_id}/adjust-trial", dependencies=[Depends(require_admin)])
    async def adjust_trial_days(install_id: str, request: Request):
        """Amplia o redueix manualment els dies d'una llicència TRIAL.
        Body JSON: {"days": +N o -N}. Positive extends, negative reduces.
        NO afecta llicències de subscripció Stripe."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        try:
            days = int(body.get("days", 0))
        except Exception:
            days = 0
        if days == 0 or abs(days) > 3650:
            raise HTTPException(status_code=400, detail="days must be a non-zero integer within ±3650")
        lic = await coll.find_one({"install_id": install_id, "status": "active"})
        if not lic:
            raise HTTPException(status_code=404, detail="Active license not found")
        plan_family = (lic.get("plan_family") or lic.get("plan") or "").upper()
        if plan_family != "TRIAL":
            raise HTTPException(status_code=400, detail=f"License is not TRIAL (plan={plan_family})")
        # Nou expires_at
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        cur_exp = lic.get("expires_at")
        if isinstance(cur_exp, str):
            try:
                cur_exp = _dt.fromisoformat(cur_exp.replace("Z","+00:00"))
            except Exception:
                cur_exp = _dt.now(_tz.utc)
        elif not cur_exp:
            cur_exp = _dt.now(_tz.utc)
        new_exp = cur_exp + _td(days=days)
        new_exp_iso = new_exp.isoformat()
        await coll.update_one(
            {"_id": lic["_id"]},
            {"$set": {"expires_at": new_exp_iso, "trial_adjusted_at": _dt.now(_tz.utc).isoformat(), "trial_adjusted_by": days}},
        )
        await _audit(request, "trial_adjust", install_id, extra={"days": days, "new_exp": new_exp_iso})

        # 📧 Enviar email al cliente para que sepa que debe abrir la app y pulsar Verificar
        email_sent = False
        try:
            from services.mailer import _send_smtp, _smtp_configured
            client_email = (lic.get("client_email") or "").strip()
            if client_email and _smtp_configured():
                client_name = (lic.get("client_name") or lic.get("centre") or "").strip()
                # Fecha en formato humano ES
                new_exp_human = new_exp.strftime("%d/%m/%Y")
                action_verb = "ampliada" if days > 0 else "reducida"
                days_abs = abs(days)
                subject = f"MediCar Plus · Tu licencia ha sido {action_verb} · Nueva expiración {new_exp_human}"
                html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;background:#f4f4f7;padding:20px;color:#111">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:10px;padding:30px;box-shadow:0 2px 10px rgba(0,0,0,.05)">
  <div style="text-align:center;margin-bottom:20px">
    <h1 style="color:#f5b301;margin:0;font-size:24px">MediCar Plus</h1>
    <p style="color:#666;margin:4px 0 0 0;font-size:12px">Software profesional de gestión de caja</p>
  </div>
  <h2 style="color:#111;font-size:18px">Hola{(' ' + client_name) if client_name else ''},</h2>
  <p style="line-height:1.6">Hemos <b style="color:#0891b2">{action_verb}</b> tu período de prueba en <b>{days_abs} {'día' if days_abs==1 else 'días'}</b>. Tu nueva fecha de expiración es:</p>
  <div style="background:#fff8e1;border-left:4px solid #f5b301;padding:14px;margin:18px 0;border-radius:4px;text-align:center">
    <p style="margin:0;font-size:13px;color:#666">Nueva expiración</p>
    <p style="margin:6px 0 0 0;font-size:24px;font-weight:700;color:#f5b301">{new_exp_human}</p>
  </div>
  <div style="background:#e0f2fe;border-left:4px solid #0284c7;padding:14px;margin:18px 0;border-radius:6px">
    <p style="margin:0;line-height:1.6"><b>🔄 Cómo aplicar el cambio</b></p>
    <ol style="margin:8px 0 0 20px;line-height:1.8">
      <li>Abre <b>MediCar Plus</b> en tu ordenador</li>
      <li>Pulsa el candado 🔐 en la esquina superior derecha</li>
      <li>Pulsa <b style="color:#0891b2">↻ Verificar ahora</b></li>
      <li>La app se actualizará automáticamente con la nueva fecha</li>
    </ol>
    <p style="margin:8px 0 0 0;font-size:12px;color:#666">💡 O simplemente cierra y abre la app: se sincroniza sola al detectar el cambio.</p>
  </div>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0" />
  <p style="font-size:11px;color:#999;text-align:center">¿Dudas? Escríbenos a <a href="mailto:info@medicarplus.es" style="color:#f5b301">info@medicarplus.es</a><br />MediCar Plus · <a href="https://medicarplus.es" style="color:#666">medicarplus.es</a></p>
</div></body></html>"""
                ok, info = _send_smtp(client_email, subject, html)
                email_sent = bool(ok)
                if not ok:
                    logger.warning("adjust-trial email failed for %s: %s", install_id, info)
        except Exception as ex:
            logger.warning("adjust-trial email exception for %s: %s", install_id, ex)

        return {"ok": True, "install_id": install_id, "days_adjusted": days, "new_expires_at": new_exp_iso, "email_notified": email_sent}

    # ---------- Info enriquida d'una llicència (SMS mode + subscription state) ----------
    @router.get("/{install_id}/enriched", dependencies=[Depends(require_admin)])
    async def enriched_license(install_id: str):
        """Retorna la llicència amb dades addicionals per el panel admin:
        - Info de subscripció Stripe (status, next renewal)
        - SMS del mes actual + total històric
        - Sender del mode MediCar Cloud (si l'usa)
        """
        # 🔧 Fix: prioriza la licencia ACTIVA más reciente para este install_id.
        # Antes usaba find_one sin ordenar → podía devolver una licencia vieja
        # expirada/revocada con last_verify_at obsoleto (bug reportado: cliente
        # se conectó hoy pero panel decía "hace 5d").
        lic = await coll.find_one(
            {"install_id": install_id, "status": "active"},
            {"_id": 0},
            sort=[("created_at", -1)],
        )
        if not lic:
            # Fallback: la más reciente en cualquier estado (expirada/revocada)
            lic = await coll.find_one(
                {"install_id": install_id},
                {"_id": 0},
                sort=[("created_at", -1)],
            )
        if not lic:
            raise HTTPException(status_code=404, detail="License not found")
        from datetime import datetime as _dt, timezone as _tz
        now_dt = _dt.now(_tz.utc)
        cur_period = f"{now_dt.year:04d}-{now_dt.month:02d}"
        # SMS consum actual (mode medicar)
        usage_cur = await db.sms_usage_medicar.find_one({"install_id": install_id, "period": cur_period})
        # SMS històric total
        agg = await db.sms_usage_medicar.aggregate([
            {"$match": {"install_id": install_id}},
            {"$group": {"_id": None, "total_sent": {"$sum": "$sent_count"}, "months": {"$sum": 1}}},
        ]).to_list(1)
        total_hist = agg[0] if agg else {"total_sent": 0, "months": 0}
        # Detecta si té campanyes BYOA (twilio_source='byoa')
        byoa_camps = await db.sms_campaigns.count_documents({"install_id": install_id, "twilio_source": "byoa"})
        medicar_camps = await db.sms_campaigns.count_documents({"install_id": install_id, "twilio_source": "medicar"})
        # Determinar mode preferit del client
        if medicar_camps > 0:
            sms_mode = "medicar"
        elif byoa_camps > 0:
            sms_mode = "byoa"
        else:
            sms_mode = "none"
        price = float(os.environ.get("MEDICAR_SMS_TWILIO_COST_EUR", "0") or 0) + float(os.environ.get("MEDICAR_SMS_MARGIN_EUR", "0") or 0)
        if price <= 0:
            price = float(os.environ.get("MEDICAR_SMS_PRICE_EUR", "0.10"))
        return {
            "license": lic,
            "activity": {
                "last_verify_at": lic.get("last_verify_at"),
                "verify_count": int(lic.get("verify_count", 0) or 0),
                "days_since_last_verify": (
                    (now_dt - _dt.fromisoformat(lic["last_verify_at"].replace("Z","+00:00"))).days
                    if lic.get("last_verify_at") else None
                ),
            },
            "sms": {
                "mode_used": sms_mode,
                "byoa_campaigns": byoa_camps,
                "medicar_campaigns": medicar_camps,
                "current_month": {
                    "period": cur_period,
                    "sent_count": int((usage_cur or {}).get("sent_count", 0)),
                    "cost_eur": round(int((usage_cur or {}).get("sent_count", 0)) * price, 2),
                    "billed": bool((usage_cur or {}).get("billed", False)),
                    "medicar_sender": (usage_cur or {}).get("medicar_sender", ""),
                },
                "total_historic": {
                    "sent_count": int(total_hist.get("total_sent", 0)),
                    "months": int(total_hist.get("months", 0)),
                },
                "price_per_sms_eur": price,
            },
        }

    # =========================================================================
    # LLICÈNCIES · SOL·LICITUDS PÚBLIQUES (portal /request-license + admin)
    # Declarades ABANS de /{install_id} perquè la ruta literal /requests
    # no quedi ombrejada per la paramètrica.
    # =========================================================================
    def _req_to_record(doc: dict) -> LicenseRequestRecord:
        return LicenseRequestRecord(
            id=doc["id"],
            install_id=doc["install_id"],
            company_name=doc.get("company_name", ""),
            contact_name=doc.get("contact_name"),
            email=doc.get("email", ""),
            phone=doc.get("phone"),
            tax_id=doc.get("tax_id"),
            plan_requested=doc.get("plan_requested", "STD"),
            notes=doc.get("notes"),
            status=doc.get("status", "pending"),
            created_at=_to_dt(doc.get("created_at")) or _now(),
            processed_at=_to_dt(doc.get("processed_at")),
            processed_reason=doc.get("processed_reason"),
            license_id=doc.get("license_id"),
            email_sent=bool(doc.get("email_sent", False)),
            email_error=doc.get("email_error"),
        )

    # ---------- Public: lookup Install ID → devuelve datos del cliente para auto-rellenar
    # No es sensible: solo devuelve info que ya está en manos del propietario (empresa, contacto).
    # Si el Install ID no existe, devolvemos found:false (sin exponer si es un guess).
    @router.get("/lookup/{install_id}")
    async def lookup_install_id(install_id: str) -> dict:
        """Devuelve datos del cliente asociados a un install_id para auto-rellenar el
        formulario público de solicitud. Rate-limited a través del limit global del server."""
        install_id = (install_id or "").strip().upper()
        # Validación básica de formato para evitar consultas basura
        import re
        if not re.match(r"^CD-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$", install_id):
            return {"found": False, "reason": "invalid_format"}
        # 1) Primero busca en licencias (fuente autoritativa)
        lic = await coll.find_one(
            {"install_id": install_id},
            sort=[("created_at", -1)],
        )
        if lic:
            return {
                "found": True,
                "source": "license",
                "company_name": lic.get("client_name") or "",
                "contact_name": lic.get("contact_name") or "",
                "email": lic.get("client_email") or "",
                "phone": lic.get("phone") or "",
                "tax_id": lic.get("tax_id") or "",
                "current_plan": lic.get("plan") or "",
                "current_status": lic.get("status") or "",
                "current_expires_at": lic.get("expires_at"),
            }
        # 2) Fallback: solicitud pendiente (aún sin licencia)
        req = await req_coll.find_one(
            {"install_id": install_id},
            sort=[("created_at", -1)],
        )
        if req:
            return {
                "found": True,
                "source": "request",
                "company_name": req.get("company_name") or "",
                "contact_name": req.get("contact_name") or "",
                "email": req.get("email") or "",
                "phone": req.get("phone") or "",
                "tax_id": req.get("tax_id") or "",
                "current_plan": req.get("plan_requested") or "",
                "current_status": req.get("status") or "pending",
                "current_expires_at": None,
            }
        return {"found": False}

    # ---------- Public: create a request (rate-limited + honeypot) ----------
    @router.post(
        "/requests",
        response_model=LicenseRequestRecord,
        status_code=status.HTTP_201_CREATED,
    )
    @_rate("5/minute")
    async def create_license_request(request: Request, body: LicenseRequestCreate) -> LicenseRequestRecord:
        """Endpoint públic: un client demana una llicència omplint el portal."""
        # Anti-spam honeypot
        if body.website and body.website.strip():
            logger.info("honeypot triggered by %s", body.email)
            raise HTTPException(status_code=400, detail="Sol·licitud invàlida")
        if not body.consent:
            raise HTTPException(status_code=400, detail="Has d'acceptar la política de privacitat")
        # Rate limit implícit: una sol·licitud pendent per install_id (només si l'usuari n'ha aportat un).
        # Si no hi ha install_id (client encara no té l'app), fem la comprovació per email.
        if body.install_id:
            existing = await req_coll.find_one(
                {"install_id": body.install_id, "status": "pending"}
            )
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail="Ja hi ha una sol·licitud pendent per aquest Install ID. Espera resposta o contacta amb el proveïdor.",
                )
        else:
            # Sense install_id: comprovem duplicat per email en les últimes 24h
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
            cutoff = (_dt.now(_tz.utc) - _td(hours=24)).isoformat()
            existing = await req_coll.find_one(
                {"email": body.email.strip().lower(), "status": "pending", "created_at": {"$gte": cutoff}}
            )
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail="Ja hi ha una sol·licitud pendent amb aquest email en les últimes 24h. Espera resposta o contacta amb el proveïdor.",
                )
        req_id = str(uuid.uuid4())
        doc = {
            "id": req_id,
            "install_id": body.install_id,
            "company_name": body.company_name.strip(),
            "contact_name": (body.contact_name or "").strip() or None,
            "email": body.email,
            "phone": (body.phone or "").strip() or None,
            "tax_id": (body.tax_id or "").strip() or None,
            "plan_requested": (body.plan_requested or "STD").upper(),
            "notes": body.notes,
            "status": "pending",
            "created_at": _now().isoformat(),
            "processed_at": None,
            "processed_reason": None,
            "license_id": None,
            "email_sent": False,
            "email_error": None,
        }
        await req_coll.insert_one(doc)
        logger.info("license request received for %s", body.install_id)
        return _req_to_record(doc)

    # ---------- Admin: list requests ----------
    @router.get(
        "/requests",
        response_model=LicenseRequestListResponse,
        dependencies=[Depends(require_admin)],
    )
    async def list_license_requests(
        status_filter: Optional[str] = Query(None, alias="status"),
        limit: int = Query(200, ge=1, le=1000),
    ) -> LicenseRequestListResponse:
        query: dict[str, Any] = {}
        if status_filter:
            query["status"] = status_filter
        cursor = req_coll.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
        docs = await cursor.to_list(limit)
        pending = await req_coll.count_documents({"status": "pending"})
        return LicenseRequestListResponse(
            total=len(docs),
            pending=pending,
            items=[_req_to_record(d) for d in docs],
        )

    # ---------- Admin: approve request ----------
    @router.post(
        "/requests/{req_id}/approve",
        dependencies=[Depends(require_admin)],
    )
    async def approve_license_request(
        req_id: str, body: Optional[LicenseRequestApprove] = None
    ) -> dict:
        body = body or LicenseRequestApprove()
        doc = await req_coll.find_one({"id": req_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Sol·licitud no trobada")
        if doc.get("status") != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"La sol·licitud ja està {doc.get('status')}",
            )

        plan = (body.plan or doc.get("plan_requested") or "STD").upper()
        # Si no hi ha install_id (client encara no té l'app · pla TRIAL o similar),
        # usem un placeholder que després el client farà servir per activar TRIAL localment.
        install_id_final = doc.get("install_id") or "CD-TRIAL-PENDING-0000-0000"
        lic_doc = await _create_license(
            install_id=install_id_final,
            client_name=doc.get("company_name", ""),
            client_email=doc.get("email"),
            contact_name=doc.get("contact_name"),
            phone=doc.get("phone"),
            tax_id=doc.get("tax_id"),
            duration_days=body.duration_days,
            plan=plan,
            notes=f"Aprovada des de sol·licitud {req_id}. {doc.get('notes') or ''}".strip(),
        )

        # Intent d'enviar email (opcional)
        email_sent = False
        email_error: Optional[str] = None
        if body.send_email:
            expires_at = _to_dt(lic_doc.get("expires_at"))
            ok, info = await mailer.send_license_email(
                to_email=doc["email"],
                client_name=doc.get("company_name", ""),
                install_id=install_id_final,
                license_key=lic_doc["license_key"],
                plan=plan,
                expires_at=expires_at,
            )
            email_sent = ok
            if not ok:
                email_error = info

        await req_coll.update_one(
            {"id": req_id},
            {"$set": {
                "status": "approved",
                "processed_at": _now().isoformat(),
                "license_id": lic_doc["id"],
                "email_sent": email_sent,
                "email_error": email_error,
            }},
        )
        updated_req = await req_coll.find_one({"id": req_id})
        return {
            "request": _req_to_record(updated_req).model_dump(mode="json"),
            "license": _doc_to_record(lic_doc, include_key=True).model_dump(mode="json"),
            "email_sent": email_sent,
            "email_error": email_error,
            "mailer_configured": mailer.is_configured(),
        }

    # ---------- Admin: reject request ----------
    @router.post(
        "/requests/{req_id}/reject",
        response_model=LicenseRequestRecord,
        dependencies=[Depends(require_admin)],
    )
    async def reject_license_request(
        req_id: str, body: Optional[LicenseRequestReject] = None
    ) -> LicenseRequestRecord:
        body = body or LicenseRequestReject()
        doc = await req_coll.find_one({"id": req_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Sol·licitud no trobada")
        if doc.get("status") != "pending":
            raise HTTPException(status_code=409, detail="Sol·licitud ja processada")
        await req_coll.update_one(
            {"id": req_id},
            {"$set": {
                "status": "rejected",
                "processed_at": _now().isoformat(),
                "processed_reason": body.reason or "rejected_by_admin",
            }},
        )
        updated = await req_coll.find_one({"id": req_id})
        return _req_to_record(updated)

    # ---------- Detail (paramètrica, va al final) ----------
    @router.get(
        "/{install_id}",
        response_model=LicenseRecord,
        dependencies=[Depends(require_admin)],
    )
    async def get_license(install_id: str) -> LicenseRecord:
        install_id = install_id.strip().upper()
        doc = await coll.find_one(
            {"install_id": install_id}, {"_id": 0}, sort=[("created_at", -1)]
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Llicència no trobada")
        return _doc_to_record(doc, include_key=True)

    return router
