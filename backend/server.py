from fastapi import FastAPI, APIRouter, Request
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone

from routes.licenses import build_router as build_license_router


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')
# C7 fix: fail fast if key missing — no hardcoded fallback in code.
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Rate limiter (C1). Public endpoints are limited by IP.
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])

# App version — clients whose min_client_version is greater than this are rejected.
APP_VERSION = "2.0.0"

# Create the main app without a prefix
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.get("/download-app")
async def download_app():
    """Force-download the standalone caja_del_dia.html file."""
    file_path = Path(__file__).parent.parent / "frontend" / "public" / "caja_del_dia.html"
    return FileResponse(
        path=str(file_path),
        media_type="application/octet-stream",
        filename="caja_del_dia.html",
        headers={"Content-Disposition": 'attachment; filename="caja_del_dia.html"'},
    )


@api_router.get("/download-electron")
async def download_electron():
    """Force-download the Electron packaging bundle (v2 commercial, obfuscated JS).

    Contents: main.js, preload.js, package.json, index.html (obfuscated),
    assets/, BUILD_INSTRUCTIONS.md, LICENSE.txt. Excludes node_modules and
    yarn.lock — `npm install` regenerates them cleanly on the target PC.
    """
    file_path = Path(__file__).parent.parent / "commercial" / "caja_del_dia_electron.zip"
    if not file_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Electron ZIP not generated yet")
    return FileResponse(
        path=str(file_path),
        media_type="application/zip",
        filename="caja_del_dia_electron.zip",
        headers={"Content-Disposition": 'attachment; filename="caja_del_dia_electron.zip"'},
    )


class AiAskBody(BaseModel):
    question: str
    data: dict
    company: str = "cbTrafic"
    diff: float = 0.0
    userGeminiKey: str = ""
    auditSummary: Optional[dict] = None


@api_router.post("/ai-ask")
@limiter.limit("20/minute")
async def ai_ask(request: Request, body: AiAskBody):
    """Ask Gemini Flash to help find discrepancies in the cash log. Prefers user's own Google API key (free tier)."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    company_data = body.data.get(body.company, {}).get("byDate", {})
    sorted_dates = sorted(company_data.keys())[-45:]
    lines = []
    for d in sorted_dates:
        for e in company_data.get(d, []):
            if e.get("retorno"):
                continue
            kind = e.get("kind", "")
            if kind == "DH":
                lines.append(f"{d} [{e.get('tipo')}] {e.get('nombre','')[:35]} {e.get('importe',0)}€ {e.get('fp','')}")
            else:
                lines.append(f"{d} {e.get('tipo','')} {e.get('nombre','')[:30]} imp={e.get('importe',0)} tasa={e.get('tasa',0)} {e.get('fp','')}")
    data_txt = "\n".join(lines[-400:])
    system = (
        "Ets un assessor comptable expert en gestories de trànsit i medicina esportiva a Catalunya. "
        "Analitza el registre de caixa i respon en català o castellà segons l'usuari, breu i pràctic amb vinyetes. "
        "Si hi ha descuadre (diff), busca causes: devolucions de taxa DGT no apuntades, duplicats, imports atípics. "
        "Cita dates concretes dd/mm/yyyy."
    )
    diff_txt = f"DESCUADRE: {body.diff:.2f}€ (positiu=sobra, negatiu=falta)\n" if body.diff else ""
    audit_txt = ""
    if body.auditSummary:
        au = body.auditSummary
        clients = au.get("clients", [])
        if clients:
            rng = f"{au.get('from','')} → {au.get('to','')}" if au.get('from') else au.get('month','')
            lines_au = [f"\n📊 AUDITORIA RANG {rng} · {au.get('totalRepeated',0)} clients repetits ({au.get('suspiciousCount',0)} sospitosos):"]
            for c in clients[:15]:
                flag = "🚨 " if c.get("suspicious") else ""
                span = f" ({c.get('daySpan',0)} dies entre visites)" if c.get('daySpan',0) > 60 else ""
                lines_au.append(f"{flag}{c.get('name','')} — {c.get('fichas',0)} fitxes {c.get('dates',[])}{span} imp={c.get('totalImp',0)}€ tasa={c.get('totalTasa',0)}€ dh={c.get('dhSum',0)}€")
                for en in c.get("entries", [])[:6]:
                    lines_au.append(f"   · {en.get('date')} {en.get('kind')}/{en.get('tipo','')} imp={en.get('importe',0)} tasa={en.get('tasa',0)} {en.get('fp','')}")
            audit_txt = "\n".join(lines_au) + "\n"
    user_msg = f"{diff_txt}Pregunta: {body.question}\n{audit_txt}\nRegistre:\n{data_txt}"
    # Use user's own Google Gemini API key if provided (FREE tier)
    if body.userGeminiKey and len(body.userGeminiKey.strip()) >= 20:
        try:
            import google.generativeai as genai
            genai.configure(api_key=body.userGeminiKey)
            model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system)
            resp = model.generate_content(user_msg)
            return {"answer": resp.text, "source": "user-key"}
        except Exception as ex:
            logging.exception("User Gemini key error")
            return {"answer": f"❌ La teva clau Google Gemini ha donat error: {str(ex)[:200]}\n\nRevisa que la clau sigui vàlida a https://aistudio.google.com/apikey", "error": True}
    # Fallback to Emergent LLM Key
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"caja-{uuid.uuid4().hex[:8]}",
            system_message=system,
        ).with_model("gemini", "gemini-2.5-flash")
        reply = await chat.send_message(UserMessage(text=user_msg))
        return {"answer": reply, "source": "emergent-key"}
    except Exception as ex:
        logging.exception("AI error")
        return {"answer": f"❌ Error del asesor IA: {str(ex)[:250]}\n\n💡 Consell: introdueix la teva pròpia clau gratuïta de Google Gemini a la app (botó ⚙️ del modal) per no dependre de la clau compartida.", "error": True}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    # Exclude MongoDB's _id field from the query results
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    # Convert ISO string timestamps back to datetime objects
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks

# Include the router in the main app
app.include_router(api_router)

# Mount the licenses subrouter under /api/licenses
app.include_router(build_license_router(db, limiter=limiter), prefix="/api")

# Notifications (SMS/WhatsApp via Twilio) — mòdul aïllat
from routes.notifications import router as notifications_router
app.include_router(notifications_router, prefix="/api")

# Payments (Stripe Checkout) — mòdul aïllat
from routes.payments import router as payments_router
app.include_router(payments_router, prefix="/api")

# Support (formulari de contacte dins l'app comercial)
from routes.support import build_router as build_support_router
app.include_router(build_support_router(db), prefix="/api")

# SMS Campaigns (avisos massius amb tongades i estadístiques)
from routes.sms_campaigns import build_router as build_sms_router
app.include_router(build_sms_router(db), prefix="/api")

# Electron manifest — SHA-256 + mida dels fitxers font per sync bulletproof
from routes.electron_manifest import router as electron_manifest_router
app.include_router(electron_manifest_router, prefix="/api")

# Electron update channel — KILL SWITCH remot per bloquejar versions dolentes
from routes.electron_channel import router as electron_channel_router
app.include_router(electron_channel_router, prefix="/api")

# Stripe webhook (obligatori per playbook: /api/webhook/stripe)
# Gestiona tant one-off (via emergentintegrations) com subscriptions (via stripe SDK)
from fastapi import Request as _FastReq
import stripe as _stripe_sdk
from emergentintegrations.payments.stripe.checkout import StripeCheckout as _StripeCK

# Events de subscripció que ens interessen (auto-renewal + cancel·lació)
_SUBSCRIPTION_EVENTS = {
    "checkout.session.completed",
    "invoice.paid",
    "invoice.payment_failed",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}


async def _sync_license_from_subscription(sub: dict, install_id: str | None,
                                          package_id: str | None, client_email: str | None,
                                          company_name: str | None):
    """
    Crea/actualitza una llicència JWT que reflecteix l'estat de la subscripció Stripe.
    - Si status='active' → llicència active amb expires_at = current_period_end
    - Si status='canceled'/'unpaid' → llicència marcada com 'revoked'
    """
    import jwt as _jwt
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz

    if not install_id or install_id == "":
        install_id = f"CD-STRIPE-{sub['id'][:16].upper()}"

    plan_key = package_id or "STD_ANY"
    plan_family = "PREMIUM" if plan_key.startswith("PREMIUM") else "STD"
    sub_status = sub.get("status", "unknown")
    period_end = sub.get("current_period_end")
    expires_at = _dt.fromtimestamp(period_end, tz=_tz.utc) if period_end else None

    # Guarda/actualitza la subscripció al seu registre propi
    await db.subscriptions.update_one(
        {"stripe_subscription_id": sub["id"]},
        {"$set": {
            "stripe_subscription_id": sub["id"],
            "stripe_customer_id": sub.get("customer"),
            "install_id": install_id,
            "customer_email": client_email or "",
            "company_name": company_name or "",
            "package_id": plan_key,
            "plan": plan_family,
            "status": sub_status,
            "current_period_end": period_end,
            "cancel_at_period_end": sub.get("cancel_at_period_end", False),
            "updated_at": _dt.now(_tz.utc).isoformat(),
        },
         "$setOnInsert": {"created_at": _dt.now(_tz.utc).isoformat()}},
        upsert=True,
    )

    # Sync llicència JWT
    if sub_status in ("active", "trialing"):
        # Renova/crea llicència: expires_at = current_period_end
        existing = await db.licenses.find_one({
            "install_id": install_id, "status": "active"
        })
        license_id = existing["id"] if existing else str(_uuid.uuid4())

        secret = os.environ.get("LICENSE_SECRET", "")
        issuer = os.environ.get("LICENSE_ISSUER", "caja-del-dia-license-server")
        payload = {
            "iss": issuer,
            "sub": install_id,
            "jti": license_id,
            "plan": plan_family,
            "iat": int(_dt.now(_tz.utc).timestamp()),
        }
        if expires_at:
            payload["exp"] = int(expires_at.timestamp())
        jwt_key = _jwt.encode(payload, secret, algorithm="HS256")

        doc = {
            "id": license_id,
            "install_id": install_id,
            "client_name": company_name or "",
            "client_email": client_email or None,
            "plan": plan_family,
            "status": "active",
            "duration_days": None,
            "notes": f"Auto-generada per Stripe Subscription {sub['id']}",
            "created_at": _dt.now(_tz.utc).isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "revoked_at": None,
            "revoked_reason": None,
            "last_verified_at": None,
            "verify_count": 0,
            "license_key": jwt_key,
            "stripe_subscription_id": sub["id"],
        }
        if existing:
            await db.licenses.update_one({"id": license_id}, {"$set": doc})
        else:
            # Revoca llicències actives anteriors d'aquest install_id
            await db.licenses.update_many(
                {"install_id": install_id, "status": "active"},
                {"$set": {"status": "revoked",
                          "revoked_at": _dt.now(_tz.utc).isoformat(),
                          "revoked_reason": "replaced_by_subscription"}},
            )
            await db.licenses.insert_one(doc)
        logger.info("License synced from subscription %s → install_id=%s exp=%s",
                    sub["id"], install_id, expires_at)

    elif sub_status in ("canceled", "unpaid", "incomplete_expired"):
        # Revoca la llicència associada
        await db.licenses.update_many(
            {"stripe_subscription_id": sub["id"], "status": "active"},
            {"$set": {"status": "revoked",
                      "revoked_at": _dt.now(_tz.utc).isoformat(),
                      "revoked_reason": f"stripe_subscription_{sub_status}"}},
        )
        logger.info("License revoked for subscription %s (status=%s)", sub["id"], sub_status)


@app.post("/api/webhook/stripe")
async def stripe_webhook(request: _FastReq):
    api_key = os.environ.get("STRIPE_API_KEY", "").strip()
    if not api_key:
        return {"received": False, "error": "not configured"}

    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")

    # 1) Intentem parsejar amb Stripe SDK (necessari per events de Subscription)
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    event = None
    if webhook_secret:
        try:
            _stripe_sdk.api_key = api_key
            event = _stripe_sdk.Webhook.construct_event(body, signature, webhook_secret)
        except Exception as e:
            logger.warning("Stripe webhook signature invalid: %s", e)
            # No retornem 400 encara — provem el path emergent per compatibilitat
            event = None

    # 2) Si és un event de subscripció, gestiona'l aquí
    if event and event["type"] in _SUBSCRIPTION_EVENTS:
        etype = event["type"]
        data = event["data"]["object"]
        try:
            if etype == "checkout.session.completed" and data.get("mode") == "subscription":
                sub_id = data.get("subscription")
                if sub_id:
                    _stripe_sdk.api_key = api_key
                    sub = _stripe_sdk.Subscription.retrieve(sub_id)
                    md = data.get("metadata", {}) or {}
                    await _sync_license_from_subscription(
                        sub,
                        install_id=md.get("install_id"),
                        package_id=md.get("package_id"),
                        client_email=data.get("customer_email") or md.get("customer_email"),
                        company_name=md.get("company_name"),
                    )
                    # Marca la request com paid si té request_id
                    req_id = md.get("request_id")
                    if req_id:
                        await db.license_requests.update_one(
                            {"id": req_id},
                            {"$set": {"payment_status": "paid",
                                      "paid_at": datetime.now(timezone.utc).isoformat(),
                                      "paid_via": "stripe_subscription",
                                      "stripe_subscription_id": sub_id}},
                        )
            elif etype in ("invoice.paid", "invoice.payment_failed"):
                sub_id = data.get("subscription")
                if sub_id:
                    _stripe_sdk.api_key = api_key
                    sub = _stripe_sdk.Subscription.retrieve(sub_id)
                    md = sub.get("metadata", {}) or {}
                    await _sync_license_from_subscription(
                        sub,
                        install_id=md.get("install_id"),
                        package_id=md.get("package_id"),
                        client_email=md.get("customer_email"),
                        company_name=md.get("company_name"),
                    )
            elif etype in ("customer.subscription.updated", "customer.subscription.deleted"):
                sub = data  # aquest event ja porta l'objecte Subscription
                md = sub.get("metadata", {}) or {}
                await _sync_license_from_subscription(
                    sub,
                    install_id=md.get("install_id"),
                    package_id=md.get("package_id"),
                    client_email=md.get("customer_email"),
                    company_name=md.get("company_name"),
                )
        except Exception as e:
            logger.exception("Error handling subscription webhook: %s", e)
        return {"received": True, "event_type": etype, "handled": "subscription"}

    # 3) Fallback: gestiona events one-off amb emergentintegrations (legacy)
    host_url = str(request.base_url).rstrip("/")
    stripe_ck = _StripeCK(api_key=api_key, webhook_url=f"{host_url}/api/webhook/stripe")
    try:
        resp = await stripe_ck.handle_webhook(body, signature)
    except Exception as e:
        return {"received": False, "error": str(e)}

    if resp.session_id and resp.payment_status == "paid":
        tx = await db.payment_transactions.find_one({"session_id": resp.session_id})
        if tx and tx.get("payment_status") != "paid":
            await db.payment_transactions.update_one(
                {"session_id": resp.session_id},
                {"$set": {"payment_status": "paid", "status": "complete",
                          "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
            req_id = (resp.metadata or {}).get("request_id")
            if req_id:
                await db.license_requests.update_one(
                    {"id": req_id},
                    {"$set": {"payment_status": "paid",
                              "paid_at": datetime.now(timezone.utc).isoformat(),
                              "paid_via": "stripe"}},
                )
    return {"received": True, "event_type": resp.event_type, "handled": "one_off"}

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def _startup():
    # C3: create MongoDB indexes so queries stay fast at scale.
    try:
        await db.licenses.create_index("install_id")
        await db.licenses.create_index("id", unique=True)
        await db.licenses.create_index([("status", 1), ("created_at", -1)])
        await db.license_requests.create_index([("install_id", 1), ("status", 1)])
        await db.license_requests.create_index([("status", 1), ("created_at", -1)])
        await db.audit_logs.create_index([("target", 1), ("timestamp", -1)])
        logger.info("MongoDB indexes ensured")
    except Exception:
        logger.exception("Failed to ensure MongoDB indexes")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()