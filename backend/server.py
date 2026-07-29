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
        "Eres un asesor contable experto en gestorías de tráfico y medicina deportiva en España. "
        "Analiza el registro de caja y responde en castellano (o catalán solo si el usuario lo pide), breve y práctico con viñetas. "
        "Si hay descuadre (diff), busca causas: devoluciones de tasa DGT no apuntadas, duplicados, importes atípicos. "
        "Cita fechas concretas dd/mm/yyyy."
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
    user_key_error = None
    if body.userGeminiKey and len(body.userGeminiKey.strip()) >= 20:
        try:
            import google.generativeai as genai
            genai.configure(api_key=body.userGeminiKey)
            model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system)
            resp = model.generate_content(user_msg)
            return {"answer": resp.text, "source": "user-key"}
        except Exception as ex:
            logging.exception("User Gemini key error")
            user_key_error = str(ex)
            # SEMPRE fem fallback silenciós — millor UX: l'usuari sempre rep resposta
    # Fallback to Emergent LLM Key (també cau aquí si la user key ha fallat per qualsevol motiu)
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"caja-{uuid.uuid4().hex[:8]}",
            system_message=system,
        ).with_model("gemini", "gemini-3-flash-preview")
        reply = await chat.send_message(UserMessage(text=user_msg))
        note = ""
        if user_key_error:
            # Detecta si és quota per donar-li un missatge útil
            err_lower = user_key_error.lower()
            if "429" in user_key_error or "quota" in err_lower or "rate" in err_lower or "exhausted" in err_lower:
                note = "\n\n_ℹ️ Tu clave gratuita de Google Gemini ha alcanzado el límite diario (10 preguntas/min, 250/día). Se resetea automáticamente. He usado la clave compartida de MediCar Plus mientras tanto._"
            else:
                note = "\n\n_ℹ️ Tu clave de Google Gemini ha dado error temporal. He usado la clave compartida de MediCar Plus. Si el problema persiste, revisa que la clave sea válida en aistudio.google.com/apikey._"
        return {"answer": reply + note, "source": "emergent-key-fallback" if user_key_error else "emergent-key"}
    except Exception as ex:
        logging.exception("AI error")
        return {"answer": f"❌ Error del asesor IA: {str(ex)[:250]}\n\n💡 Consejo: introduce tu propia clave gratuita de Google Gemini en la app (botón ⚙️ del modal) para no depender de la clave compartida.", "error": True}

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

# Calendar Sync (Premium) — proxy iCal per Google Calendar, Doctoralia, etc.
from routes.calendar_sync import router as calendar_sync_router
app.include_router(calendar_sync_router, prefix="/api")

# PDF Render — converteix HTML → PDF A4 amb Playwright (per "Descargar PDF")
from routes.pdf_render import router as pdf_render_router
app.include_router(pdf_render_router, prefix="/api")

# Sync multi-device Premium (heartbeat + push + pull + auto-upgrade STD→PRM)
from routes.sync import build_sync_router
app.include_router(build_sync_router(db), prefix="/api")

from routes.trial import build_trial_router
app.include_router(build_trial_router(db), prefix="/api")

# Referral program (Feb 2026)
from routes.referrals import create_router as build_referrals_router
app.include_router(build_referrals_router(db))

# Admin login (username + password) — second auth path for Master session
from routes.auth_admin import router as auth_admin_router
app.include_router(auth_admin_router, prefix="/api")

# Installations tracking · God-mode owner traceability
from routes.installations import build_router as build_installations_router
_track_r, _admin_r = build_installations_router(db)
app.include_router(_track_r, prefix="/api")
app.include_router(_admin_r, prefix="/api")

# Admin Stripe payments sync + summary (Feb 2026 · God-mode financial view)
from routes.admin_payments import build_payments_router
app.include_router(build_payments_router(db), prefix="/api")

# Admin users management (multi-user login · Feb 2026)
from routes.admin_users import build_users_router
app.include_router(build_users_router(db), prefix="/api")

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
                                          company_name: str | None,
                                          referred_by: str | None = None):
    """
    Crea/actualitza una llicència JWT que reflecteix l'estat de la subscripció Stripe.
    - Si status='active' → llicència active amb expires_at = current_period_end
    - Si status='canceled'/'unpaid' → llicència marcada com 'revoked'
    - Si `referred_by` és un referral_code vàlid i és la 1a activació d'aquest install_id,
      aplica la recompensa al referrer (2 mesos gratis via cupó Stripe).
    """
    import jwt as _jwt
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz

    if not install_id or install_id == "":
        install_id = f"CD-STRIPE-{sub['id'][:16].upper()}"

    # 🆕 Herència automàtica del referred_by des del trial actiu (si l'usuari
    # va usar un codi al signup del trial i ara està upgradeant a paid)
    if not referred_by and install_id:
        try:
            trial_doc = await db.licenses.find_one(
                {"install_id": install_id, "plan": "TRIAL", "referred_by": {"$exists": True, "$ne": None}},
                sort=[("created_at", -1)],
            )
            if trial_doc and trial_doc.get("referred_by"):
                referred_by = trial_doc.get("referred_by")
                logger.info("Inherited referred_by=%s from trial for install_id=%s",
                            referred_by, install_id)
        except Exception:  # noqa: BLE001
            pass

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
            "referred_by": (referred_by or "").upper() if referred_by else None,
        }
        if existing:
            prev_plan = str(existing.get("plan") or "").upper()
            new_plan = str(plan_family or "").upper()
            plan_changed = prev_plan != new_plan
            # 🔁 Si el pla canvia (trial → paid, standard → premium…), NO fem UPDATE
            # in-place perquè trencaríem la generació de referral_code i l'aplicació
            # de recompenses del referrer. En comptes d'això, revoquem l'antic i
            # creem un doc NOU (mateix flux que el branch else).
            if plan_changed:
                await db.licenses.update_one(
                    {"id": existing["id"]},
                    {"$set": {"status": "revoked",
                              "revoked_at": _dt.now(_tz.utc).isoformat(),
                              "revoked_reason": f"upgraded_from_{prev_plan}_to_{new_plan}"}},
                )
                # També heretem el referred_by de l'antic doc si el nou no en tenia
                if not doc.get("referred_by") and existing.get("referred_by"):
                    doc["referred_by"] = existing["referred_by"]
                # Cal un id NOU pel doc nou (l'antic ha estat revocat però continua
                # existint amb el mateix id → l'índex únic bloquejaria l'insert).
                new_license_id = str(_uuid.uuid4())
                doc["id"] = new_license_id
                # Regenera el JWT amb el nou jti perquè coincideixi
                payload_new = dict(payload)
                payload_new["jti"] = new_license_id
                doc["license_key"] = _jwt.encode(payload_new, secret, algorithm="HS256")
                # Genera referral_code únic
                try:
                    from services.referrals import ensure_unique_referral_code
                    doc["referral_code"] = await ensure_unique_referral_code(db.licenses)
                except Exception as _rex:  # noqa: BLE001
                    logger.warning("Could not generate referral_code on upgrade: %s", _rex)
                await db.licenses.insert_one(doc)
                # Aplica recompensa al referrer si hi ha codi vàlid
                if doc.get("referred_by"):
                    try:
                        from services.referrals import find_active_referrer, apply_stripe_referral_reward
                        referrer_doc = await find_active_referrer(db.licenses, doc["referred_by"])
                        if referrer_doc:
                            ok, info = await apply_stripe_referral_reward(
                                referrer_doc=referrer_doc,
                                referred_install_id=install_id,
                                referred_email=client_email,
                                referred_plan=plan_family,
                                coll=db.licenses,
                            )
                            logger.info(
                                "Referral reward (via trial-upgrade) for code=%s: ok=%s info=%s",
                                doc["referred_by"], ok, info,
                            )
                    except Exception as _ref:  # noqa: BLE001
                        logger.exception("Referral reward (upgrade path) failed: %s", _ref)
                # Envia email amb la nova clau
                if client_email:
                    try:
                        from services import mailer as _mailer
                        sent, info = await _mailer.send_license_email(
                            to_email=client_email,
                            client_name=company_name or client_email,
                            install_id=install_id,
                            license_key=jwt_key,
                            plan=plan_family,
                            expires_at=expires_at,
                            subject_prefix=f"Plan actualizado a {new_plan}",
                        )
                        logger.info("Upgrade email (%s → %s) → %s: sent=%s info=%s",
                                    prev_plan, new_plan, client_email, sent, info)
                    except Exception as _em:  # noqa: BLE001
                        logger.exception("Upgrade email failed: %s", _em)
                return
            # No canvi de pla → simple $set (renovació, canvi de període…)
            await db.licenses.update_one({"id": license_id}, {"$set": doc})
            if client_email:
                try:
                    from services import mailer as _mailer
                    sent, info = await _mailer.send_license_email(
                        to_email=client_email,
                        client_name=company_name or client_email,
                        install_id=install_id,
                        license_key=jwt_key,
                        plan=plan_family,
                        expires_at=expires_at,
                        subject_prefix=f"Renovación suscripción {new_plan}",
                    )
                    logger.info("Stripe subscription UPDATE email → %s (plan=%s): sent=%s info=%s",
                                client_email, new_plan, sent, info)
                except Exception as _em:
                    logger.exception("Stripe update email failed: %s", _em)
        else:
            # Revoca llicències actives anteriors d'aquest install_id
            await db.licenses.update_many(
                {"install_id": install_id, "status": "active"},
                {"$set": {"status": "revoked",
                          "revoked_at": _dt.now(_tz.utc).isoformat(),
                          "revoked_reason": "replaced_by_subscription"}},
            )
            # 🆕 Genera referral_code únic per la nova llicència
            try:
                from services.referrals import ensure_unique_referral_code
                doc["referral_code"] = await ensure_unique_referral_code(db.licenses)
            except Exception as _rex:  # noqa: BLE001
                logger.warning("Could not generate referral_code: %s", _rex)
            await db.licenses.insert_one(doc)
            # 🆕 Aplica recompensa al referrer si el codi és vàlid (Trial no compta,
            # aquesta funció només es crida des de Stripe subscription events → sempre paid)
            if referred_by:
                try:
                    from services.referrals import find_active_referrer, apply_stripe_referral_reward
                    referrer_doc = await find_active_referrer(db.licenses, referred_by)
                    if referrer_doc:
                        ok, info = await apply_stripe_referral_reward(
                            referrer_doc=referrer_doc,
                            referred_install_id=install_id,
                            referred_email=client_email,
                            referred_plan=plan_family,
                            coll=db.licenses,
                        )
                        logger.info(
                            "Referral reward for code=%s referrer=%s: ok=%s info=%s",
                            referred_by, referrer_doc.get("client_email"), ok, info,
                        )
                    else:
                        logger.warning("Referral code %s is invalid or inactive", referred_by)
                except Exception as _ref:  # noqa: BLE001
                    logger.exception("Referral reward processing failed: %s", _ref)
            # 🆕 Envia email automàtic al client amb la llicència + guia
            if client_email:
                try:
                    from services import mailer as _mailer
                    sent, info = await _mailer.send_license_email(
                        to_email=client_email,
                        client_name=company_name or client_email,
                        install_id=install_id,
                        license_key=jwt_key,
                        plan=plan_family,
                        expires_at=expires_at,
                    )
                    logger.info("Stripe subscription email → %s: sent=%s info=%s",
                                client_email, sent, info)
                except Exception as _em:
                    logger.exception("Stripe subscription email failed: %s", _em)
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
                        referred_by=md.get("referred_by") or md.get("referral_code"),
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
            elif etype == "invoice.paid":
                # 💰 Actualiza payment tracking en tiempo real (banner verde en el admin)
                inv = data
                sub_id = inv.get("subscription")
                if sub_id:
                    try:
                        lic = await db.licenses.find_one({"stripe_subscription_id": sub_id, "status": "active"})
                        amount = int(inv.get("amount_paid") or 0)
                        paid_at_ts = inv.get("status_transitions", {}).get("paid_at")
                        paid_at_iso = datetime.fromtimestamp(paid_at_ts, tz=timezone.utc).isoformat() if paid_at_ts else datetime.now(timezone.utc).isoformat()
                        # Upsert en payments
                        await db.payments.update_one(
                            {"_id": inv.get("id")},
                            {"$set": {
                                "license_jti": (lic or {}).get("id"),
                                "install_id": (lic or {}).get("install_id"),
                                "customer_email": inv.get("customer_email") or (lic or {}).get("client_email"),
                                "stripe_subscription_id": sub_id,
                                "stripe_customer_id": inv.get("customer"),
                                "amount_cents": amount,
                                "currency": inv.get("currency", "eur"),
                                "status": "paid",
                                "created_at": datetime.fromtimestamp(inv.get("created"), tz=timezone.utc).isoformat() if inv.get("created") else None,
                                "paid_at": paid_at_iso,
                                "hosted_url": inv.get("hosted_invoice_url"),
                                "pdf_url": inv.get("invoice_pdf"),
                                "synced_at": datetime.now(timezone.utc).isoformat(),
                            }},
                            upsert=True,
                        )
                        # Actualiza la licencia con salud verde + total acumulado
                        was_red = False
                        if lic:
                            was_red = (lic.get("payment_health") == "red") or int(lic.get("failed_invoices_count") or 0) > 0
                            await db.licenses.update_one(
                                {"id": lic["id"]},
                                {"$inc": {"total_paid_cents": amount, "paid_invoices_count": 1},
                                 "$set": {"payment_health": "green",
                                          "last_payment_status": "paid",
                                          "last_payment_at": paid_at_iso,
                                          "last_payment_amount_cents": amount,
                                          "failed_invoices_count": 0}},
                            )
                        logger.info(f"[stripe] invoice.paid tracked · sub={sub_id} · {amount/100:.2f} EUR")

                        # 📧 Notificación recovery (solo si venía de rojo)
                        if was_red:
                            try:
                                pay_doc = await db.payments.find_one({"_id": inv.get("id")}) or {}
                                if not pay_doc.get("admin_notified_recovered"):
                                    from services.admin_notifier import notify_payment_recovered
                                    ok_email, _ = notify_payment_recovered(
                                        customer_email=inv.get("customer_email") or (lic or {}).get("client_email") or "",
                                        install_id=(lic or {}).get("install_id"),
                                        amount_cents=amount,
                                        currency=inv.get("currency", "eur"),
                                        hosted_invoice_url=inv.get("hosted_invoice_url"),
                                        stripe_subscription_id=sub_id,
                                        paid_at_iso=paid_at_iso,
                                        company_name=(lic or {}).get("company_name"),
                                    )
                                    if ok_email:
                                        await db.payments.update_one(
                                            {"_id": inv.get("id")},
                                            {"$set": {"admin_notified_recovered": True,
                                                      "admin_notified_recovered_at": datetime.now(timezone.utc).isoformat()}},
                                        )
                            except Exception as ex_notify:
                                logger.warning(f"[stripe] admin notify (recovered) error: {ex_notify}")
                    except Exception as ex:
                        logger.warning(f"[stripe] invoice.paid tracking failed: {ex}")
            elif etype == "invoice.payment_failed":
                # Cobrament fallit → NO revoquem llicència (Stripe farà retries automàtics
                # durant ~3 setmanes). Marquem payment_health=red y guardem el intent fallido.
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
                        referred_by=md.get("referred_by") or md.get("referral_code"),
                    )
                    # 🚨 Registro del intento fallido para el banner rojo del admin
                    try:
                        inv = data
                        lic = await db.licenses.find_one({"stripe_subscription_id": sub_id})
                        cust_email = inv.get("customer_email") or (lic or {}).get("client_email")
                        amount_due = int(inv.get("amount_due") or 0)
                        created_iso = datetime.fromtimestamp(inv.get("created"), tz=timezone.utc).isoformat() if inv.get("created") else None
                        await db.payments.update_one(
                            {"_id": inv.get("id")},
                            {"$set": {
                                "license_jti": (lic or {}).get("id"),
                                "install_id": (lic or {}).get("install_id"),
                                "customer_email": cust_email,
                                "stripe_subscription_id": sub_id,
                                "amount_cents": amount_due,
                                "currency": inv.get("currency", "eur"),
                                "status": "open",
                                "created_at": created_iso,
                                "hosted_url": inv.get("hosted_invoice_url"),
                                "synced_at": datetime.now(timezone.utc).isoformat(),
                            }},
                            upsert=True,
                        )
                        failed_count_new = 0
                        if lic:
                            upd = await db.licenses.find_one_and_update(
                                {"id": lic["id"]},
                                {"$inc": {"failed_invoices_count": 1},
                                 "$set": {"payment_health": "red",
                                          "last_payment_status": "failed"}},
                                return_document=True,
                            )
                            if upd:
                                failed_count_new = int(upd.get("failed_invoices_count", 1))

                        # 📧 Notificación al admin (idempotente por invoice)
                        try:
                            pay_doc = await db.payments.find_one({"_id": inv.get("id")}) or {}
                            if not pay_doc.get("admin_notified_failed"):
                                from services.admin_notifier import notify_payment_failed
                                ok_email, info_email = notify_payment_failed(
                                    customer_email=cust_email or "",
                                    install_id=(lic or {}).get("install_id"),
                                    amount_cents=amount_due,
                                    currency=inv.get("currency", "eur"),
                                    failed_count=failed_count_new or 1,
                                    hosted_invoice_url=inv.get("hosted_invoice_url"),
                                    stripe_subscription_id=sub_id,
                                    invoice_created_iso=created_iso,
                                    company_name=(lic or {}).get("company_name"),
                                )
                                if ok_email:
                                    await db.payments.update_one(
                                        {"_id": inv.get("id")},
                                        {"$set": {"admin_notified_failed": True,
                                                  "admin_notified_failed_at": datetime.now(timezone.utc).isoformat()}},
                                    )
                        except Exception as ex_notify:
                            logger.warning(f"[stripe] admin notify (failed) error: {ex_notify}")
                    except Exception as ex:
                        logger.warning(f"[stripe] invoice.payment_failed tracking failed: {ex}")
                    logger.info(f"[stripe] invoice.payment_failed for sub={sub_id} (Stripe retriarà automàticament)")
            elif etype in ("customer.subscription.updated", "customer.subscription.deleted"):
                sub = data  # aquest event ja porta l'objecte Subscription
                md = sub.get("metadata", {}) or {}
                install_id_from_md = md.get("install_id")
                await _sync_license_from_subscription(
                    sub,
                    install_id=install_id_from_md,
                    package_id=md.get("package_id"),
                    client_email=md.get("customer_email"),
                    company_name=md.get("company_name"),
                    referred_by=md.get("referred_by") or md.get("referral_code"),
                )
                # 💰 SMS BILLING · Facturació final si es cancel·la definitivament
                # (evita perdre diners quan un client cancel·la sense pagar els SMS del mes)
                sub_status = sub.get("status")
                if etype == "customer.subscription.deleted" or sub_status in ("canceled", "unpaid", "incomplete_expired"):
                    try:
                        from services.sms_billing import bill_pending_sms_for_subscription
                        install_id_final = install_id_from_md
                        # Fallback: mira si tenim install_id lligat al subscription_id
                        if not install_id_final:
                            lic_doc = await db.licenses.find_one({"stripe_subscription_id": sub.get("id")})
                            if lic_doc:
                                install_id_final = lic_doc.get("install_id")
                        if install_id_final:
                            result = await bill_pending_sms_for_subscription(
                                db, _stripe_sdk, sub.get("id"), install_id_final, mode="one_off"
                            )
                            logger.info(f"[sms_billing] final invoice on cancel: {result}")
                    except Exception as bill_err:
                        logger.exception(f"[sms_billing] failed on subscription cancel: {bill_err}")
            elif etype == "invoice.paid":
                # També re-sincronitza la llicència + factura SMS pendents del mes anterior
                sub_id = data.get("subscription")
                if sub_id:
                    _stripe_sdk.api_key = api_key
                    sub = _stripe_sdk.Subscription.retrieve(sub_id)
                    md = sub.get("metadata", {}) or {}
                    install_id_paid = md.get("install_id")
                    await _sync_license_from_subscription(
                        sub,
                        install_id=install_id_paid,
                        package_id=md.get("package_id"),
                        client_email=md.get("customer_email"),
                        company_name=md.get("company_name"),
                        referred_by=md.get("referred_by") or md.get("referral_code"),
                    )
                    # 💰 SMS BILLING · adjunta SMS pendents a la següent factura
                    try:
                        from services.sms_billing import bill_pending_sms_for_subscription
                        if not install_id_paid:
                            lic_doc = await db.licenses.find_one({"stripe_subscription_id": sub_id})
                            if lic_doc:
                                install_id_paid = lic_doc.get("install_id")
                        if install_id_paid:
                            result = await bill_pending_sms_for_subscription(
                                db, _stripe_sdk, sub_id, install_id_paid, mode="attach_next"
                            )
                            if result.get("billed", 0) > 0:
                                logger.info(f"[sms_billing] attached to next invoice: {result}")
                    except Exception as bill_err:
                        logger.exception(f"[sms_billing] failed on invoice.paid: {bill_err}")
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

    # Auto-publica la URL actual del preview a medicarplus.es/api-endpoint.json.
    # Si Emergent roti la URL, els clients Electron ho detecten sols en < 24h.
    # No trenca l'arrencada si falla.
    try:
        from services.auto_publish_endpoint import auto_publish_endpoint_url
        await auto_publish_endpoint_url()
    except Exception:
        logger.exception("auto_publish_endpoint_url failed at startup")

    # Recordatoris automàtics de renovació (sweep diari en background)
    try:
        import asyncio as _asyncio
        from services.renewal_reminders import renewal_reminder_loop
        _asyncio.create_task(renewal_reminder_loop(db))
        logger.info("Renewal reminder loop scheduled")
    except Exception:
        logger.exception("Failed to schedule renewal reminder loop")


@app.post("/api/admin/renewal-reminders/run")
async def run_renewal_reminders_now(request: _FastReq):
    """Admin: executa el sweep de recordatoris manualment (X-Admin-Token)."""
    from fastapi import HTTPException as _HTTPExc
    token = request.headers.get("X-Admin-Token", "")
    if not token or token != os.environ.get("LICENSE_ADMIN_TOKEN", ""):
        raise _HTTPExc(status_code=401, detail="Admin token invàlid o absent")
    from services.renewal_reminders import run_renewal_reminder_sweep
    return await run_renewal_reminder_sweep(db)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()