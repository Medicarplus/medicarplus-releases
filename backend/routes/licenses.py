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
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

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
        license_key=doc.get("license_key") if include_key else None,
    )


def _mint_jwt(*, install_id: str, license_id: str, plan: str,
              expires_at: Optional[datetime]) -> str:
    """Genera el JWT que serveix com a `license key`."""
    now = _now()
    payload: dict[str, Any] = {
        "iss": _issuer(),
        "sub": install_id,
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
def build_router(db: AsyncIOMotorDatabase) -> APIRouter:
    """Crea el router usant la connexió MongoDB compartida."""

    router = APIRouter(prefix="/licenses", tags=["licenses"])
    coll = db[COLLECTION]
    req_coll = db[REQ_COLLECTION]

    async def _create_license(
        *,
        install_id: str,
        client_name: str,
        client_email: Optional[str],
        duration_days: Optional[int],
        plan: str,
        notes: Optional[str],
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
    async def generate_license(body: LicenseCreate) -> LicenseRecord:
        """Genera una llicència JWT nova per un install_id."""
        doc = await _create_license(
            install_id=body.install_id,
            client_name=body.client_name,
            client_email=body.client_email,
            duration_days=body.duration_days,
            plan=body.plan or "STD",
            notes=body.notes,
        )
        return _doc_to_record(doc, include_key=True)

    # ---------- Verify ----------
    @router.post("/verify", response_model=LicenseVerifyResponse)
    async def verify_license(body: LicenseVerify) -> LicenseVerifyResponse:
        """Valida una llicència. Pública: la crida el client v2.html."""
        # 1) Decode JWT
        try:
            payload = jwt.decode(
                body.key,
                _secret(),
                algorithms=[JWT_ALG],
                issuer=_issuer(),
                options={"require": ["iss", "sub", "jti", "iat"]},
            )
        except jwt.ExpiredSignatureError:
            return LicenseVerifyResponse(
                ok=False, expired=True, reason="Llicència expirada", install_id=body.install_id
            )
        except jwt.InvalidTokenError as ex:
            return LicenseVerifyResponse(ok=False, reason=f"Clau invàlida: {ex}",
                                         install_id=body.install_id)

        # 2) Comprovem que el subject del JWT coincideix amb l'install_id enviat
        if payload.get("sub") != body.install_id:
            return LicenseVerifyResponse(
                ok=False,
                reason="La clau no correspon a aquesta instal·lació",
                install_id=body.install_id,
            )

        # 3) Busquem la llicència a la DB per l'id (jti)
        doc = await coll.find_one({"id": payload["jti"]})
        if not doc:
            return LicenseVerifyResponse(
                ok=False, reason="Llicència desconeguda al servidor",
                install_id=body.install_id,
            )

        if doc.get("status") == "revoked":
            return LicenseVerifyResponse(
                ok=False,
                revoked=True,
                status="revoked",
                reason=doc.get("revoked_reason") or "Llicència revocada",
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
                reason="Llicència expirada",
                install_id=body.install_id, client_name=doc.get("client_name"),
                plan=doc.get("plan"), expires_at=expires_at,
            )

        # 4) Tot OK → actualitzem estadístiques
        await coll.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {"last_verified_at": _now().isoformat()},
                "$inc": {"verify_count": 1},
            },
        )
        return LicenseVerifyResponse(
            ok=True,
            status="active",
            install_id=body.install_id,
            client_name=doc.get("client_name"),
            plan=doc.get("plan"),
            expires_at=expires_at,
        )

    # ---------- Revoke ----------
    @router.post(
        "/revoke",
        response_model=LicenseRecord,
        dependencies=[Depends(require_admin)],
    )
    async def revoke_license(body: LicenseRevoke) -> LicenseRecord:
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
        updated = await coll.find_one({"_id": doc["_id"]})
        return _doc_to_record(updated)

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
        query: dict[str, Any] = {}
        if status_filter:
            query["status"] = status_filter
        cursor = coll.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
        docs = await cursor.to_list(limit)
        return LicenseListResponse(
            total=len(docs),
            items=[_doc_to_record(d) for d in docs],
        )

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

    # ---------- Public: create a request ----------
    @router.post(
        "/requests",
        response_model=LicenseRequestRecord,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_license_request(body: LicenseRequestCreate) -> LicenseRequestRecord:
        """Endpoint públic: un client demana una llicència omplint el portal."""
        # Rate limit implícit: una sol·licitud pendent per install_id.
        existing = await req_coll.find_one(
            {"install_id": body.install_id, "status": "pending"}
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Ja hi ha una sol·licitud pendent per aquest Install ID. Espera resposta o contacta amb el proveïdor.",
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
        lic_doc = await _create_license(
            install_id=doc["install_id"],
            client_name=doc.get("company_name", ""),
            client_email=doc.get("email"),
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
                install_id=doc["install_id"],
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
