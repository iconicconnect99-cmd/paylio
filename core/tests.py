from decimal import Decimal

from django.contrib.auth import get_user_model
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
        response = self.client.get(
            reverse("core:crypto-payment", args=[self.payment_link.token])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "crypto-recipient")
        self.assertContains(response, self.wallet.address)
        self.assertContains(response, "TRC20")
        self.assertContains(response, "MoonPay")
        self.assertContains(response, "$0.970000 per USDT")
        self.assertContains(response, self.gateway.buy_url)

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
        self.assertContains(response, "Transak")
        self.assertContains(response, "$0.990000 per USDT")

    def test_received_usdt_page_generates_a_shareable_link(self):
        self.client.force_login(self.recipient)

        response = self.client.get(reverse("core:crypto-receive"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your personal payment link")
        self.assertTrue(PaymentLink.objects.filter(user=self.recipient).exists())

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
