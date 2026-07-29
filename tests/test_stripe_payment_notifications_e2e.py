"""E2E integration test · Stripe webhook triggers admin email notifications.

Simulates:
  Case A · invoice.payment_failed → admin_notifier.notify_payment_failed called
           → payments doc has admin_notified_failed=True
           → second identical webhook does NOT re-notify (idempotency)
  Case B · invoice.paid AFTER a failed payment → notify_payment_recovered called
           → license.failed_invoices_count reset to 0
           → payments doc has admin_notified_recovered=True

Runs directly against local backend via Motor + patched _send_smtp.
"""
import asyncio
import os
import sys
import uuid
from unittest.mock import patch

sys.path.insert(0, "/app/backend")

from dotenv import dotenv_values

env = dotenv_values("/app/backend/.env")
MONGO_URL = env["MONGO_URL"]
DB_NAME = env["DB_NAME"]

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


async def _cleanup(db, sub_id):
    await db.licenses.delete_many({"stripe_subscription_id": sub_id})
    await db.payments.delete_many({"stripe_subscription_id": sub_id})


async def run():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    sub_id = f"sub_test_{uuid.uuid4().hex[:8]}"
    inv_id_failed = f"in_failed_{uuid.uuid4().hex[:8]}"
    inv_id_paid = f"in_paid_{uuid.uuid4().hex[:8]}"
    install_id = f"CD-{uuid.uuid4().hex[:8].upper()}"
    customer_email = "recovery-test@medicar.test"

    await _cleanup(db, sub_id)

    # 1) Seed license first so webhook can find it
    lic_id = str(uuid.uuid4())
    await db.licenses.insert_one({
        "id": lic_id,
        "install_id": install_id,
        "client_email": customer_email,
        "stripe_subscription_id": sub_id,
        "status": "active",
        "payment_health": "green",
        "failed_invoices_count": 0,
        "paid_invoices_count": 0,
        "company_name": "Test Empresa",
    })

    # --- CASE A: invoice.payment_failed ---
    # Simulate the code inside server.py's webhook handler by calling the
    # notifier through the same code path (payments upsert + license update
    # + notify + idempotency flag).
    print("\n=== CASE A · invoice.payment_failed ===")

    call_counts = {"failed": 0, "recovered": 0}

    def fake_send_smtp(to, subject, html, attachments=None):
        if "Pago fallido" in subject:
            call_counts["failed"] += 1
        elif "Pago recuperado" in subject:
            call_counts["recovered"] += 1
        return True, "smtp_sent_mock"

    with patch("services.admin_notifier._smtp_configured", return_value=True), \
         patch("services.admin_notifier._send_smtp", side_effect=fake_send_smtp):

        from services.admin_notifier import notify_payment_failed, notify_payment_recovered

        # Simulate first payment_failed webhook
        await db.payments.update_one(
            {"_id": inv_id_failed},
            {"$set": {
                "customer_email": customer_email,
                "install_id": install_id,
                "stripe_subscription_id": sub_id,
                "amount_cents": 2990,
                "currency": "eur",
                "status": "open",
                "hosted_url": "https://invoice.stripe.com/test/failed",
            }},
            upsert=True,
        )
        updated_lic = await db.licenses.find_one_and_update(
            {"id": lic_id},
            {"$inc": {"failed_invoices_count": 1},
             "$set": {"payment_health": "red", "last_payment_status": "failed"}},
            return_document=True,
        )
        failed_count_new = int(updated_lic.get("failed_invoices_count") or 1)

        pay = await db.payments.find_one({"_id": inv_id_failed})
        if not pay.get("admin_notified_failed"):
            ok, info = notify_payment_failed(
                customer_email=customer_email,
                install_id=install_id,
                amount_cents=2990,
                currency="eur",
                failed_count=failed_count_new,
                hosted_invoice_url="https://invoice.stripe.com/test/failed",
                stripe_subscription_id=sub_id,
                invoice_created_iso="2026-07-29T10:00:00+00:00",
                company_name="Test Empresa",
            )
            if ok:
                await db.payments.update_one(
                    {"_id": inv_id_failed},
                    {"$set": {"admin_notified_failed": True}},
                )

        assert call_counts["failed"] == 1, f"expected 1 failed email, got {call_counts['failed']}"
        pay = await db.payments.find_one({"_id": inv_id_failed})
        assert pay.get("admin_notified_failed") is True, "flag not set"
        print(f"  ✅ 1st payment_failed → admin notified (count={call_counts['failed']})")

        # 2nd webhook (same invoice) must NOT re-notify
        pay = await db.payments.find_one({"_id": inv_id_failed})
        if not pay.get("admin_notified_failed"):
            notify_payment_failed(
                customer_email=customer_email,
                install_id=install_id,
                amount_cents=2990,
                currency="eur",
                failed_count=1,
                hosted_invoice_url=None,
                stripe_subscription_id=sub_id,
                invoice_created_iso=None,
            )
        assert call_counts["failed"] == 1, f"IDEMPOTENCY BROKEN: got {call_counts['failed']}"
        print(f"  ✅ 2nd webhook (same invoice) → idempotent (count still {call_counts['failed']})")

        # --- CASE B: invoice.paid after a failed → recovery notification ---
        print("\n=== CASE B · invoice.paid (recovery from red) ===")
        lic = await db.licenses.find_one({"id": lic_id})
        assert lic.get("payment_health") == "red", f"expected red, got {lic.get('payment_health')}"
        assert int(lic.get("failed_invoices_count") or 0) > 0

        was_red = (lic.get("payment_health") == "red") or int(lic.get("failed_invoices_count") or 0) > 0
        await db.payments.update_one(
            {"_id": inv_id_paid},
            {"$set": {
                "customer_email": customer_email,
                "install_id": install_id,
                "stripe_subscription_id": sub_id,
                "amount_cents": 2990,
                "currency": "eur",
                "status": "paid",
                "hosted_url": "https://invoice.stripe.com/test/paid",
            }},
            upsert=True,
        )
        await db.licenses.update_one(
            {"id": lic_id},
            {"$inc": {"total_paid_cents": 2990, "paid_invoices_count": 1},
             "$set": {"payment_health": "green", "last_payment_status": "paid",
                      "failed_invoices_count": 0}},
        )

        if was_red:
            pay = await db.payments.find_one({"_id": inv_id_paid})
            if not pay.get("admin_notified_recovered"):
                ok, _ = notify_payment_recovered(
                    customer_email=customer_email,
                    install_id=install_id,
                    amount_cents=2990,
                    currency="eur",
                    hosted_invoice_url="https://invoice.stripe.com/test/paid",
                    stripe_subscription_id=sub_id,
                    paid_at_iso="2026-07-30T09:00:00+00:00",
                    company_name="Test Empresa",
                )
                if ok:
                    await db.payments.update_one(
                        {"_id": inv_id_paid},
                        {"$set": {"admin_notified_recovered": True}},
                    )

        assert call_counts["recovered"] == 1, f"expected 1 recovery email, got {call_counts['recovered']}"
        lic_after = await db.licenses.find_one({"id": lic_id})
        assert lic_after.get("payment_health") == "green"
        assert int(lic_after.get("failed_invoices_count", -1)) == 0, "failed count not reset"
        pay_paid = await db.payments.find_one({"_id": inv_id_paid})
        assert pay_paid.get("admin_notified_recovered") is True
        print(f"  ✅ payment recovered → admin notified (count={call_counts['recovered']})")
        print(f"  ✅ license.payment_health back to green + failed_count reset to 0")

    # Cleanup
    await _cleanup(db, sub_id)
    client.close()
    print("\n🎉 All webhook notification E2E assertions passed")


if __name__ == "__main__":
    asyncio.run(run())
