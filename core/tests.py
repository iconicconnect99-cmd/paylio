from decimal import Decimal
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from core.crypto_deposits import confirm_crypto_deposit, reject_crypto_deposit
from core.models import (
    CryptoDeposit,
    CryptoPaymentGateway,
    CryptoWallet,
    Notification,
    PaymentLink,
    Transaction,
)


class TransactionHistoryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.sender = User.objects.create_user(
            username="sender",
            email="sender@example.com",
            password="test-password",
        )
        self.receiver = User.objects.create_user(
            username="receiver",
            email="receiver@example.com",
            password="test-password",
        )

    def test_received_transactions_appear_in_recipient_history(self):
        transaction = Transaction.objects.create(
            user=self.sender,
            sender=self.sender,
            reciever=self.receiver,
            amount=Decimal("10000.00"),
            status="processing",
            transaction_type="received",
        )
        self.client.force_login(self.receiver)

        response = self.client.get(reverse("core:transactions"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, transaction.transaction_id)

    def test_completed_received_transaction_creates_credit_alert(self):
        transaction = Transaction.objects.create(
            user=self.sender,
            sender=self.sender,
            reciever=self.receiver,
            amount=Decimal("10000.00"),
            status="completed",
            transaction_type="received",
        )

        notification = Notification.objects.get(
            transaction=transaction,
            user=self.receiver,
            notification_type="Credit Alert",
        )
        self.assertEqual(notification.amount, 10000)


class CryptoDepositTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.recipient = User.objects.create_user(
            username="crypto-recipient",
            email="crypto-recipient@example.com",
            password="test-password",
        )
        self.admin = User.objects.create_user(
            username="crypto-admin",
            email="crypto-admin@example.com",
            password="test-password",
            is_staff=True,
            is_superuser=True,
        )
        self.payment_link = PaymentLink.objects.create(user=self.recipient)
        self.wallet = CryptoWallet.objects.create(
            address="T" + "A" * 33,
        )
        self.gateway = CryptoPaymentGateway.objects.get(gateway="moonpay")
        self.gateway.usd_per_usdt = Decimal("0.970000")
        self.gateway.save(update_fields=["usd_per_usdt"])
        self.tx_hash = "a" * 64

    def test_payment_link_submission_is_pending_and_does_not_credit_balance(self):
        response = self.client.post(
            reverse("core:crypto-payment", args=[self.payment_link.token]),
            {
                "gateway": self.gateway.pk,
                "amount": "25.501234",
                "tx_hash": self.tx_hash,
            },
        )

        self.assertEqual(response.status_code, 302)
        deposit = CryptoDeposit.objects.get(tx_hash=self.tx_hash)
        self.assertEqual(deposit.user, self.recipient)
        self.assertEqual(deposit.status, CryptoDeposit.STATUS_PENDING)
        self.assertEqual(deposit.wallet_address, self.wallet.address)
        self.assertEqual(deposit.network, "TRC20")
        self.assertEqual(deposit.gateway, self.gateway)
        self.assertEqual(deposit.usd_per_usdt_rate, Decimal("0.970000"))
        self.assertEqual(deposit.amount, Decimal("25.501234"))
        self.recipient.account.refresh_from_db()
        self.assertEqual(self.recipient.account.account_balance, Decimal("0.00"))

    def test_payment_page_shows_recipient_wallet_and_changelly_action(self):
        changelly = CryptoPaymentGateway.objects.get(gateway="changelly")
        changelly.usd_per_usdt = Decimal("1.010000")
        changelly.save(update_fields=["usd_per_usdt"])
        response = self.client.get(
            reverse("core:crypto-payment", args=[self.payment_link.token])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "crypto-recipient")
        self.assertContains(response, "Payment for <strong>crypto-recipient</strong>")
        self.assertContains(response, self.wallet.address)
        self.assertContains(response, "TRC20")
        self.assertContains(response, "MoonPay")
        self.assertContains(response, "Changelly")
        self.assertContains(response, "$0.970000 per USDT")
        self.assertContains(response, self.gateway.buy_url)
        self.assertContains(response, changelly.buy_url)
        self.assertContains(response, 'role="dialog" aria-modal="true"')

    def test_each_enabled_configured_gateway_is_shown_with_its_rate(self):
        CryptoPaymentGateway.objects.filter(gateway="changelly").update(
            usd_per_usdt=Decimal("1.010000")
        )
        CryptoPaymentGateway.objects.filter(gateway="transak").update(
            usd_per_usdt=Decimal("0.990000")
        )

        response = self.client.get(
            reverse("core:crypto-payment", args=[self.payment_link.token])
        )

        self.assertContains(response, "Changelly")
        self.assertContains(response, "$1.010000 per USDT")
        self.assertContains(response, "MoonPay")
        self.assertNotContains(response, "Transak")

    def test_receive_usdt_page_asks_for_sender_email_and_amount(self):
        changelly = CryptoPaymentGateway.objects.get(gateway="changelly")
        changelly.usd_per_usdt = Decimal("1.010000")
        changelly.save(update_fields=["usd_per_usdt"])
        self.client.force_login(self.recipient)

        response = self.client.get(
            reverse("core:crypto-receive"),
            HTTP_X_FORWARDED_PROTO="https",
            HTTP_HOST="testserver",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Request USDT from a sender")
        self.assertContains(response, 'role="dialog" aria-modal="true"')
        self.assertContains(response, "Sender email")
        self.assertContains(response, "Amount requested (USDT)")
        self.assertContains(response, "Email payment page to sender")
        self.assertContains(response, "iconicconnect99@gmail.com")
        self.assertTrue(PaymentLink.objects.filter(user=self.recipient).exists())

    def test_receive_usdt_page_explains_missing_wallet_instead_of_hiding_request_form(self):
        self.wallet.delete()
        self.client.force_login(self.recipient)

        response = self.client.get(reverse("core:crypto-receive"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sender email")
        self.assertContains(response, "Amount requested (USDT)")
        self.assertContains(response, "has not configured a receiving wallet yet")
        self.assertRegex(
            response.content.decode(),
            r'<button[^>]*type="submit"[^>]*disabled',
        )

    def test_receive_usdt_emails_signed_page_with_wallet_and_requested_amount(self):
        changelly = CryptoPaymentGateway.objects.get(gateway="changelly")
        changelly.usd_per_usdt = Decimal("1.010000")
        changelly.save(update_fields=["usd_per_usdt"])
        self.client.force_login(self.recipient)

        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            EMAIL_HOST_USER="iconicconnect99@gmail.com",
            EMAIL_HOST_PASSWORD="test-app-password",
            DEFAULT_FROM_EMAIL="iconicconnect99@gmail.com",
        ):
            response = self.client.post(
                reverse("core:crypto-receive"),
                {
                    "sender_email": "sender@example.com",
                    "amount": "25.500000",
                },
                HTTP_X_FORWARDED_PROTO="https",
                HTTP_HOST="testserver",
            )

        self.assertRedirects(response, reverse("core:crypto-receive"))
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.from_email, "iconicconnect99@gmail.com")
        self.assertEqual(sent_email.to, ["sender@example.com"])
        self.assertIn("25.500000 USDT", sent_email.body)
        payment_url = next(
            line for line in sent_email.body.splitlines() if line.startswith("https://")
        )
        parsed_url = urlsplit(payment_url)
        response = self.client.get(f"{parsed_url.path}?{parsed_url.query}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment for <strong>crypto-recipient</strong>")
        self.assertContains(response, self.wallet.address)
        self.assertContains(response, "25.500000 USDT")
        self.assertContains(response, "MoonPay")
        self.assertContains(response, "Changelly")
        self.assertContains(response, "$1.010000/USDT")
        self.assertNotContains(response, "Transak")

    def test_receive_usdt_does_not_claim_to_send_when_email_is_unconfigured(self):
        self.client.force_login(self.recipient)

        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            EMAIL_HOST_USER="",
            EMAIL_HOST_PASSWORD="",
        ):
            response = self.client.post(
                reverse("core:crypto-receive"),
                {
                    "sender_email": "sender@example.com",
                    "amount": "10.00",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment email delivery is not configured")
        self.assertEqual(len(mail.outbox), 0)

    @patch("core.crypto_views.send_mail", side_effect=TimeoutError("SMTP timed out"))
    def test_receive_usdt_shows_error_when_smtp_times_out(self, send_mail_mock):
        self.client.force_login(self.recipient)

        with self.settings(
            EMAIL_HOST_USER="iconicconnect99@gmail.com",
            EMAIL_HOST_PASSWORD="test-app-password",
        ):
            response = self.client.post(
                reverse("core:crypto-receive"),
                {
                    "sender_email": "sender@example.com",
                    "amount": "10.00",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "could not send the payment page email")
        self.assertNotContains(response, "Check the email address")
        send_mail_mock.assert_called_once()

    def test_payment_page_rejects_invalid_signed_request(self):
        response = self.client.get(
            reverse("core:crypto-payment", args=[self.payment_link.token]),
            {"request": "tampered-request"},
        )

        self.assertEqual(response.status_code, 404)

    def test_admin_confirmation_credits_once_and_records_ledger_and_notification(self):
        self.gateway.usd_per_usdt = Decimal("1.250000")
        self.gateway.save(update_fields=["usd_per_usdt"])
        deposit = CryptoDeposit.objects.create(
            payment_link=self.payment_link,
            user=self.recipient,
            amount=Decimal("42.756"),
            wallet_address=self.wallet.address,
            gateway=self.gateway,
            usd_per_usdt_rate=Decimal("1.250000"),
            tx_hash=self.tx_hash,
        )
        self.gateway.usd_per_usdt = Decimal("2.000000")
        self.gateway.save(update_fields=["usd_per_usdt"])

        self.assertTrue(confirm_crypto_deposit(deposit.pk, self.admin))
        self.assertFalse(confirm_crypto_deposit(deposit.pk, self.admin))

        self.recipient.account.refresh_from_db()
        deposit.refresh_from_db()
        self.assertEqual(self.recipient.account.account_balance, Decimal("53.45"))
        self.assertEqual(deposit.transaction.amount, Decimal("53.45"))
        self.assertEqual(deposit.status, CryptoDeposit.STATUS_CONFIRMED)
        self.assertEqual(deposit.transaction.transaction_type, "crypto_deposit")
        self.assertEqual(
            Notification.objects.filter(
                transaction=deposit.transaction,
                user=self.recipient,
                notification_type="Credit Alert",
            ).count(),
            1,
        )

    def test_admin_rejection_does_not_credit_balance(self):
        deposit = CryptoDeposit.objects.create(
            payment_link=self.payment_link,
            user=self.recipient,
            amount=Decimal("42.756"),
            wallet_address=self.wallet.address,
            gateway=self.gateway,
            tx_hash=self.tx_hash,
        )

        self.assertTrue(reject_crypto_deposit(deposit.pk, self.admin))
        self.assertFalse(confirm_crypto_deposit(deposit.pk, self.admin))
        self.recipient.account.refresh_from_db()
        self.assertEqual(self.recipient.account.account_balance, Decimal("0.00"))
# Create your tests here.
