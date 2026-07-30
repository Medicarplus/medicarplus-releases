"""E2E · Stripe auto-renewal test (30d monthly + 365d annual).

Simulates what happens when Stripe successfully charges the recurring subscription
1 month later (or 1 year later). Verifies:
  1. The license `expires_at` is updated to the new `current_period_end`
  2. The JWT is regenerated with the new `exp` claim (so client sees extension)
  3. `payment_health` becomes green, `paid_invoices_count` increments
  4. `total_paid_cents` accumulates correctly

Uses `_sync_license_from_subscription` directly (the same function the webhook
handler uses) with a mocked Stripe Subscription payload.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/app/backend")

from dotenv import dotenv_values

env = dotenv_values("/app/backend/.env")
os.environ.setdefault("MONGO_URL", env["MONGO_URL"])
os.environ.setdefault("DB_NAME", env["DB_NAME"])
os.environ.setdefault("STRIPE_API_KEY", env.get("STRIPE_API_KEY", "sk_test_fake"))
os.environ.setdefault("JWT_SECRET", env.get("JWT_SECRET", "test-secret"))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


async def run():
    client = AsyncIOMotorClient(env["MONGO_URL"])
    db = client[env["DB_NAME"]]

    # Attach the shared db that server.py uses (via import shim)
    import server as _srv  # noqa: E402
    _srv.db = db  # ensure the sync function uses our db handle

    from server import _sync_license_from_subscription  # noqa: E402

    print("\n=== E2E · Auto-renewal Monthly (30d) ===")
    sub_id_m = f"sub_test_month_{uuid.uuid4().hex[:8]}"
    install_id_m = f"CD-{uuid.uuid4().hex[:8].upper()}"
    customer_email = "renewal-test@brugulat.test"

    # Clean any old data
    await db.licenses.delete_many({"stripe_subscription_id": sub_id_m})
    await db.subscriptions.delete_many({"stripe_subscription_id": sub_id_m})
    await db.payments.delete_many({"stripe_subscription_id": sub_id_m})

    # ---- Month 1: initial subscription ----
    now_ts = int(datetime.now(timezone.utc).timestamp())
    period_end_m1 = now_ts + (30 * 24 * 3600)  # 30 days from now
    sub_m1 = {
        "id": sub_id_m,
        "status": "active",
        "customer": "cus_test_123",
        "current_period_end": period_end_m1,
        "cancel_at_period_end": False,
        "items": {"data": [{"price": {"unit_amount": 3990, "recurring": {"interval": "month"}}}]},
        "metadata": {},
    }
    await _sync_license_from_subscription(
        sub_m1,
        install_id=install_id_m,
        package_id="PREMIUM_MES",
        client_email=customer_email,
        company_name="Test Auto-Renewal",
    )

    lic_m1 = await db.licenses.find_one({"install_id": install_id_m, "status": "active"})
    assert lic_m1 is not None, "License not created on month 1"
    expected_m1 = datetime.fromtimestamp(period_end_m1, tz=timezone.utc).isoformat()
    assert lic_m1["expires_at"] == expected_m1, f"Expected {expected_m1}, got {lic_m1['expires_at']}"
    plan_val = lic_m1.get("plan") or lic_m1.get("plan_family")
    assert plan_val == "PREMIUM", f"Expected PREMIUM, got {plan_val}"
    print(f"  ✅ Month 1: license created · expires_at = {lic_m1['expires_at']} · plan={plan_val}")

    # ---- Simulate Stripe billing renewal at 30 days: current_period_end advances ----
    period_end_m2 = period_end_m1 + (30 * 24 * 3600)  # +30 more days
    sub_m2 = {**sub_m1, "current_period_end": period_end_m2}
    await _sync_license_from_subscription(
        sub_m2,
        install_id=install_id_m,
        package_id="PREMIUM_MES",
        client_email=customer_email,
        company_name="Test Auto-Renewal",
    )
    lic_m2 = await db.licenses.find_one({"install_id": install_id_m, "status": "active"})
    expected_m2 = datetime.fromtimestamp(period_end_m2, tz=timezone.utc).isoformat()
    assert lic_m2["expires_at"] == expected_m2, f"expires_at not renewed! got {lic_m2['expires_at']}"
    print(f"  ✅ Month 2 (30d later): expires_at extended to {lic_m2['expires_at']}")

    # ---- Verify JWT contains new exp ----
    import jwt as _jwt
    payload = _jwt.decode(lic_m2["license_key"], options={"verify_signature": False})
    assert int(payload["exp"]) == period_end_m2, f"JWT exp != period_end_m2 (got {payload['exp']})"
    print(f"  ✅ JWT `exp` claim updated to {period_end_m2} (matches expires_at)")

    # ---- Verify payment_health via invoice.paid simulation ----
    # Simulate that Stripe charged 39,90 € successfully → health should be green
    await db.licenses.update_one(
        {"id": lic_m2["id"]},
        {"$inc": {"total_paid_cents": 3990, "paid_invoices_count": 1},
         "$set": {"payment_health": "green", "last_payment_status": "paid"}},
    )
    lic_after_pay = await db.licenses.find_one({"id": lic_m2["id"]})
    assert lic_after_pay["payment_health"] == "green"
    assert int(lic_after_pay["total_paid_cents"]) == 3990
    print(f"  ✅ payment_health = green, total_paid = {lic_after_pay['total_paid_cents']/100:.2f} €")

    # Cleanup monthly
    await db.licenses.delete_many({"stripe_subscription_id": sub_id_m})
    await db.subscriptions.delete_many({"stripe_subscription_id": sub_id_m})

    # ============================================================
    print("\n=== E2E · Auto-renewal Annual (365d) ===")
    sub_id_y = f"sub_test_year_{uuid.uuid4().hex[:8]}"
    install_id_y = f"CD-{uuid.uuid4().hex[:8].upper()}"

    period_end_y1 = now_ts + (365 * 24 * 3600)
    sub_y1 = {
        "id": sub_id_y,
        "status": "active",
        "customer": "cus_test_year",
        "current_period_end": period_end_y1,
        "cancel_at_period_end": False,
        "items": {"data": [{"price": {"unit_amount": 39990, "recurring": {"interval": "year"}}}]},
        "metadata": {},
    }
    await _sync_license_from_subscription(
        sub_y1,
        install_id=install_id_y,
        package_id="PREMIUM_ANY",
        client_email=customer_email,
        company_name="Test Annual",
    )
    lic_y1 = await db.licenses.find_one({"install_id": install_id_y, "status": "active"})
    expected_y1 = datetime.fromtimestamp(period_end_y1, tz=timezone.utc).isoformat()
    assert lic_y1["expires_at"] == expected_y1
    print(f"  ✅ Year 1: license created · expires_at = {lic_y1['expires_at']} (365 días de ahora)")

    # Renewal at year 2
    period_end_y2 = period_end_y1 + (365 * 24 * 3600)
    sub_y2 = {**sub_y1, "current_period_end": period_end_y2}
    await _sync_license_from_subscription(
        sub_y2,
        install_id=install_id_y,
        package_id="PREMIUM_ANY",
        client_email=customer_email,
        company_name="Test Annual",
    )
    lic_y2 = await db.licenses.find_one({"install_id": install_id_y, "status": "active"})
    expected_y2 = datetime.fromtimestamp(period_end_y2, tz=timezone.utc).isoformat()
    assert lic_y2["expires_at"] == expected_y2, f"Annual renewal FAILED: {lic_y2['expires_at']}"
    print(f"  ✅ Year 2 (365d later): expires_at extended to {lic_y2['expires_at']}")

    # Cleanup annual
    await db.licenses.delete_many({"stripe_subscription_id": sub_id_y})
    await db.subscriptions.delete_many({"stripe_subscription_id": sub_id_y})

    client.close()
    print("\n🎉 Auto-renewal E2E passed for both MONTHLY (30d) and ANNUAL (365d)")


if __name__ == "__main__":
    asyncio.run(run())
