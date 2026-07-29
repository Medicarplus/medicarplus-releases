"""Unit test for admin_notifier email dispatch on Stripe payment events.

Verifies:
- notify_payment_failed() calls _send_smtp with correct subject + recipient
- notify_payment_recovered() calls _send_smtp with the recovery template
- Both return (True, info) when SMTP is configured (mocked)
- Both return (False, "smtp_not_configured") when SMTP env is missing
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, "/app/backend")


def test_notify_payment_failed_sends_email():
    from services import admin_notifier

    with patch("services.admin_notifier._smtp_configured", return_value=True), \
         patch("services.admin_notifier._send_smtp", return_value=(True, "smtp_sent")) as mock_send:
        ok, info = admin_notifier.notify_payment_failed(
            customer_email="cliente@test.com",
            install_id="CD-ABCD-1234",
            amount_cents=2990,
            currency="eur",
            failed_count=2,
            hosted_invoice_url="https://invoice.stripe.com/i/xxx",
            stripe_subscription_id="sub_test_123",
            invoice_created_iso="2026-07-29T10:00:00+00:00",
            company_name="Centro Médico Test",
        )
        assert ok is True, f"expected True, got {ok} / {info}"
        assert mock_send.called, "send_smtp not called"
        args, _ = mock_send.call_args
        to, subject, html = args[:3]
        assert to == "info@medicarplus.es", f"unexpected recipient: {to}"
        assert "Pago fallido" in subject, f"unexpected subject: {subject}"
        assert "cliente@test.com" in subject
        assert "29,90" in html and "€" in html, "amount not rendered"
        assert "CD-ABCD-1234" in html
        assert "sub_test_123" in html
        assert "invoice.stripe.com" in html
        assert "Centro Médico Test" in html
        assert "Intentos fallidos" in html
    print("✅ notify_payment_failed sends email correctly")


def test_notify_payment_recovered_sends_email():
    from services import admin_notifier

    with patch("services.admin_notifier._smtp_configured", return_value=True), \
         patch("services.admin_notifier._send_smtp", return_value=(True, "smtp_sent")) as mock_send:
        ok, info = admin_notifier.notify_payment_recovered(
            customer_email="cliente@test.com",
            install_id="CD-ABCD-1234",
            amount_cents=2990,
            currency="eur",
            hosted_invoice_url="https://invoice.stripe.com/i/yyy",
            stripe_subscription_id="sub_test_123",
            paid_at_iso="2026-07-30T09:00:00+00:00",
            company_name="Centro Médico Test",
        )
        assert ok is True
        assert mock_send.called
        args, _ = mock_send.call_args
        to, subject, html = args[:3]
        assert to == "info@medicarplus.es"
        assert "Pago recuperado" in subject
        assert "cobrar con éxito" in html or "cobrar con" in html
        assert "29,90" in html
    print("✅ notify_payment_recovered sends email correctly")


def test_notify_returns_false_when_smtp_not_configured():
    from services import admin_notifier

    with patch("services.admin_notifier._smtp_configured", return_value=False), \
         patch("services.admin_notifier._send_smtp") as mock_send:
        ok, info = admin_notifier.notify_payment_failed(
            customer_email="x@y.com",
            install_id="X",
            amount_cents=100,
            currency="eur",
            failed_count=1,
            hosted_invoice_url=None,
            stripe_subscription_id=None,
            invoice_created_iso=None,
        )
        assert ok is False
        assert info == "smtp_not_configured"
        assert not mock_send.called
    print("✅ Returns False when SMTP not configured (no accidental sends)")


def test_admin_email_env_override():
    from services import admin_notifier

    with patch.dict(os.environ, {"ADMIN_NOTIFY_EMAIL": "custom@test.com"}), \
         patch("services.admin_notifier._smtp_configured", return_value=True), \
         patch("services.admin_notifier._send_smtp", return_value=(True, "ok")) as mock_send:
        admin_notifier.notify_payment_failed(
            customer_email="c@t.com",
            install_id="i",
            amount_cents=100,
            currency="eur",
            failed_count=1,
            hosted_invoice_url=None,
            stripe_subscription_id="sub_x",
            invoice_created_iso=None,
        )
        to = mock_send.call_args[0][0]
        assert to == "custom@test.com", f"env override failed: {to}"
    print("✅ ADMIN_NOTIFY_EMAIL env var overrides destination")


if __name__ == "__main__":
    test_notify_payment_failed_sends_email()
    test_notify_payment_recovered_sends_email()
    test_notify_returns_false_when_smtp_not_configured()
    test_admin_email_env_override()
    print("\n🎉 All admin_notifier tests passed (4/4)")
