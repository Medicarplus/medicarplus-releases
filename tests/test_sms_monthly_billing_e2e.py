"""E2E · Ciclo COMPLETO: crear cliente Stripe TEST → suscripción → SMS → cron → cobro → verificar.

Este test es totalmente autocontenido:
  1. Crea un Customer en Stripe TEST con tarjeta test 4242 4242 4242 4242
  2. Crea una suscripción Premium mensual real
  3. Inserta 15 SMS en sms_usage_medicar
  4. Ejecuta bill_all_pending_sms_monthly manualmente
  5. Verifica que Stripe creó y cobró la factura (invoice.amount_paid > 0)
  6. Verifica que los SMS quedan billed=True
  7. Limpieza: cancela sub, elimina customer y test data

⚠️ Usa Stripe TEST mode. No genera cobros reales.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/app/backend")
from dotenv import dotenv_values

env = dotenv_values("/app/backend/.env")
os.environ["MONGO_URL"] = env["MONGO_URL"]
os.environ["DB_NAME"] = env["DB_NAME"]
os.environ["STRIPE_API_KEY"] = env["STRIPE_API_KEY"]
os.environ["MEDICAR_SMS_TWILIO_COST_EUR"] = env.get("MEDICAR_SMS_TWILIO_COST_EUR", "0.07")
os.environ["MEDICAR_SMS_MARGIN_EUR"] = env.get("MEDICAR_SMS_MARGIN_EUR", "0.03")

import stripe  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

stripe.api_key = env["STRIPE_API_KEY"]

TEST_INSTALL_ID = f"CD-E2E-{uuid.uuid4().hex[:8].upper()}"
TEST_SMS_COUNT = 15
TEST_EMAIL = f"e2e-sms-billing-{uuid.uuid4().hex[:6]}@medicarplus-test.example"

# El price_id de PREMIUM mensual (TEST)
PRICE_ID = env["STRIPE_PRICE_PREMIUM_MES"]


async def run():
    from services.sms_monthly_billing import bill_all_pending_sms_monthly

    client_db = AsyncIOMotorClient(env["MONGO_URL"])
    db = client_db[env["DB_NAME"]]

    created_customer_id = None
    created_sub_id = None
    fake_lic_id = str(uuid.uuid4())

    try:
        print("\n=== Paso 1: Crear Customer + Tarjeta test en Stripe ===")
        customer = stripe.Customer.create(
            email=TEST_EMAIL,
            name="Test E2E SMS Billing",
            metadata={"test_e2e": "sms_billing", "install_id": TEST_INSTALL_ID},
        )
        created_customer_id = customer.id
        # Adjunta tarjeta test 4242 (siempre paga OK en TEST mode)
        pm = stripe.PaymentMethod.attach("pm_card_visa", customer=customer.id)
        stripe.Customer.modify(customer.id, invoice_settings={"default_payment_method": pm.id})
        print(f"  ✅ Customer: {customer.id} · payment_method: {pm.id}")

        print(f"\n=== Paso 2: Crear suscripción Premium Mensual ===")
        sub = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price": PRICE_ID}],
            default_payment_method=pm.id,
            metadata={"install_id": TEST_INSTALL_ID, "test_e2e": "sms_billing"},
        )
        created_sub_id = sub.id
        print(f"  ✅ Subscription: {sub.id} · status={sub.status}")

        print(f"\n=== Paso 3: Insertar licencia en Mongo ligada a esta sub ===")
        await db.licenses.insert_one({
            "id": fake_lic_id,
            "install_id": TEST_INSTALL_ID,
            "client_email": TEST_EMAIL,
            "stripe_subscription_id": sub.id,
            "stripe_customer_id": customer.id,
            "status": "active",
            "plan": "PRM",
            "company_name": "Test E2E SMS Billing",
        })
        print(f"  ✅ License row inserted")

        print(f"\n=== Paso 4: Insertar {TEST_SMS_COUNT} SMS pendientes (schema real) ===")
        now = datetime.now(timezone.utc)
        period = now.strftime("%Y-%m")
        # Schema real: 1 doc por (install_id, period) con contador atómico sent_count
        await db.sms_usage_medicar.insert_one({
            "install_id": TEST_INSTALL_ID,
            "period": period,
            "sent_count": TEST_SMS_COUNT,
            "error_count": 0,
            "billed": False,
            "created_at": now.isoformat(),
        })
        print(f"  ✅ 1 doc creado con sent_count={TEST_SMS_COUNT} periodo={period}")

        twilio_cost = float(os.environ["MEDICAR_SMS_TWILIO_COST_EUR"])
        margin = float(os.environ["MEDICAR_SMS_MARGIN_EUR"])
        expected_total_eur = round(TEST_SMS_COUNT * (twilio_cost + margin), 2)
        print(f"  💰 Precio esperado: {TEST_SMS_COUNT} × ({twilio_cost}+{margin}) = {expected_total_eur} €")

        print(f"\n=== Paso 5: Ejecutar cron mensual manualmente ===")
        result = await bill_all_pending_sms_monthly(db, stripe)
        print(f"  Result: clients_billed={result.get('clients_billed')} total_sms={result.get('total_sms')} total_eur={result.get('total_eur')}")
        assert result["clients_billed"] == 1, f"Expected 1 client billed, got {result['clients_billed']}"
        assert result["total_sms"] == TEST_SMS_COUNT
        assert abs(result["total_eur"] - expected_total_eur) < 0.01

        print(f"\n=== Paso 6: Verificar SMS marcados billed=True ===")
        pending_after = await db.sms_usage_medicar.count_documents({"install_id": TEST_INSTALL_ID, "billed": False})
        billed_after = await db.sms_usage_medicar.count_documents({"install_id": TEST_INSTALL_ID, "billed": True})
        print(f"  Pendientes: {pending_after} · Facturados: {billed_after}")
        assert pending_after == 0, "Todavía hay docs pendientes"
        assert billed_after == 1, f"Expected 1 doc facturado, got {billed_after}"

        print(f"\n=== Paso 7: Verificar factura Stripe creada + cobrada ===")
        inv_info = result["invoices"][0]
        stripe_invoice_id = inv_info["stripe_invoice_id"]
        print(f"  Stripe invoice id: {stripe_invoice_id}")
        inv = stripe.Invoice.retrieve(stripe_invoice_id)
        print(f"  Invoice status: {inv.status}")
        print(f"  Amount due: {inv.amount_due/100:.2f} € · Amount paid: {inv.amount_paid/100:.2f} €")
        print(f"  Hosted url: {inv.hosted_invoice_url[:80]}...")
        assert inv.amount_paid == int(expected_total_eur * 100), \
            f"Expected {int(expected_total_eur*100)}, got amount_paid={inv.amount_paid}"
        assert inv.status == "paid", f"Expected paid, got {inv.status}"
        print(f"  ✅ Factura de {expected_total_eur} € COBRADA con éxito por Stripe")

        print(f"\n=== Paso 8: Verificar audit log ===")
        audit = await db.sms_monthly_billing_runs.find_one(sort=[("_id", -1)])
        assert audit["clients_billed"] >= 1
        print(f"  ✅ Latest run audit: clients={audit['clients_billed']} total={audit.get('total_eur')} €")

        print(f"\n=== Paso 9: Verificar que segunda ejecución NO re-cobra ===")
        result2 = await bill_all_pending_sms_monthly(db, stripe)
        assert result2["clients_billed"] == 0, "Idempotency broken: billed again!"
        print(f"  ✅ Idempotencia OK: 2ª ejecución NO cobra ({result2})")

        print("\n🎉 E2E SMS Monthly Billing PASSED · TODO FUNCIONA CORRECTAMENTE")

    finally:
        print("\n=== Limpieza ===")
        try:
            await db.sms_usage_medicar.delete_many({"install_id": TEST_INSTALL_ID})
            await db.licenses.delete_one({"id": fake_lic_id})
            if created_sub_id:
                stripe.Subscription.cancel(created_sub_id)
                print(f"  Cancelled Stripe sub {created_sub_id}")
            if created_customer_id:
                stripe.Customer.delete(created_customer_id)
                print(f"  Deleted Stripe customer {created_customer_id}")
        except Exception as e:
            print(f"  Cleanup warning: {e}")
        client_db.close()


if __name__ == "__main__":
    asyncio.run(run())
