"""Pydantic models for the license server."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

LicenseStatus = Literal["active", "revoked", "expired"]
RequestStatus = Literal["pending", "approved", "rejected"]

# Format d'Install ID generat pel frontend v2.html: CD-XXXX-XXXX-XXXX-XXXX
INSTALL_ID_RE = re.compile(r"^CD-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")


def _validate_install_id(value: str) -> str:
    value = (value or "").strip().upper()
    if not INSTALL_ID_RE.match(value):
        raise ValueError(
            "install_id ha de tenir el format CD-XXXX-XXXX-XXXX-XXXX (majúscules i dígits)."
        )
    return value


class LicenseCreate(BaseModel):
    """Payload per generar una llicència nova (endpoint admin)."""

    install_id: str = Field(..., description="ID d'instal·lació generat pel frontend")
    client_name: str = Field(..., min_length=1, max_length=200)
    client_email: Optional[str] = Field(None, max_length=200)
    duration_days: Optional[int] = Field(
        None,
        ge=1,
        le=365 * 20,
        description="Dies de validesa. None = perpètua.",
    )
    notes: Optional[str] = Field(None, max_length=500)
    plan: Optional[str] = Field("STD", max_length=40, description="STD, PREMIUM, TRIAL, MASTER...")

    @field_validator("install_id")
    @classmethod
    def _norm_install_id(cls, v: str) -> str:
        return _validate_install_id(v)


class LicenseVerify(BaseModel):
    """Payload per verificar una llicència des del client."""

    install_id: str
    key: str = Field(..., min_length=10)

    @field_validator("install_id")
    @classmethod
    def _norm_install_id(cls, v: str) -> str:
        return _validate_install_id(v)


class LicenseRevoke(BaseModel):
    """Payload per revocar una llicència."""

    install_id: str
    reason: Optional[str] = Field(None, max_length=300)

    @field_validator("install_id")
    @classmethod
    def _norm_install_id(cls, v: str) -> str:
        return _validate_install_id(v)


class LicenseRecord(BaseModel):
    """Representació persistida a MongoDB / retornada per l'API."""

    model_config = ConfigDict(extra="ignore")

    id: str
    install_id: str
    client_name: str
    client_email: Optional[str] = None
    plan: str = "STD"
    status: LicenseStatus = "active"
    duration_days: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None
    last_verified_at: Optional[datetime] = None
    verify_count: int = 0
    # La clau JWT — es retorna només al moment de generar-la. En verificar
    # només retornem metadades.
    license_key: Optional[str] = None


class LicenseVerifyResponse(BaseModel):
    ok: bool
    status: Optional[LicenseStatus] = None
    revoked: bool = False
    expired: bool = False
    reason: Optional[str] = None
    install_id: Optional[str] = None
    client_name: Optional[str] = None
    plan: Optional[str] = None
    expires_at: Optional[datetime] = None
    server_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LicenseListResponse(BaseModel):
    total: int
    items: list[LicenseRecord]


# ---------------------------------------------------------------------------
# Sol·licituds públiques de llicència (public request → admin approval)
# ---------------------------------------------------------------------------
class LicenseRequestCreate(BaseModel):
    """Payload públic que envia un client des del portal /request-license."""

    install_id: str
    company_name: str = Field(..., min_length=1, max_length=200)
    contact_name: Optional[str] = Field(None, max_length=200)
    email: str = Field(..., max_length=200)
    phone: Optional[str] = Field(None, max_length=40)
    tax_id: Optional[str] = Field(None, max_length=40, description="NIF/CIF")
    plan_requested: Optional[str] = Field("STD", max_length=40)
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("install_id")
    @classmethod
    def _norm_install_id(cls, v: str) -> str:
        return _validate_install_id(v)

    @field_validator("email")
    @classmethod
    def _basic_email(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if "@" not in v or "." not in v.split("@", 1)[1]:
            raise ValueError("Adreça de correu invàlida")
        return v


class LicenseRequestApprove(BaseModel):
    """Payload d'aprovació (admin). Permet sobreescriure plan / duració."""

    duration_days: Optional[int] = Field(None, ge=1, le=365 * 20)
    plan: Optional[str] = Field(None, max_length=40)
    send_email: bool = Field(True, description="Intentar enviar email al client")


class LicenseRequestReject(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


class LicenseRequestRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    install_id: str
    company_name: str
    contact_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    tax_id: Optional[str] = None
    plan_requested: Optional[str] = "STD"
    notes: Optional[str] = None
    status: RequestStatus = "pending"
    created_at: datetime
    processed_at: Optional[datetime] = None
    processed_reason: Optional[str] = None
    license_id: Optional[str] = None  # llicència creada quan s'aprova
    email_sent: bool = False
    email_error: Optional[str] = None


class LicenseRequestListResponse(BaseModel):
    total: int
    pending: int
    items: list[LicenseRequestRecord]
