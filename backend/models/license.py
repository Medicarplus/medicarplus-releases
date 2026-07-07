"""Pydantic models for the license server."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

LicenseStatus = Literal["active", "revoked", "expired"]

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
