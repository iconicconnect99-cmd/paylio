from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from account.models import Account
from core.models import CryptoDeposit, Notification, Transaction


@transaction.atomic
def confirm_crypto_deposit(deposit_id, admin_user):
    deposit = CryptoDeposit.objects.select_for_update().get(pk=deposit_id)
    if deposit.status != CryptoDeposit.STATUS_PENDING:
        return False

    account = Account.objects.select_for_update().get(user=deposit.user)
    usd_amount = (deposit.amount * deposit.usd_per_usdt_rate).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    ledger_transaction = Transaction.objects.create(
        user=deposit.user,
        reciever=deposit.user,
        reciever_account=account,
        amount=usd_amount,
        description=(
            f"Verified {deposit.gateway.get_gateway_display() if deposit.gateway else 'crypto'} "
            f"USDT {deposit.network} deposit at "
            f"${deposit.usd_per_usdt_rate} per USDT"
        ),
        status="completed",
        transaction_type="crypto_deposit",
    )
    account.account_balance += usd_amount
    account.save(update_fields=["account_balance"])

    deposit.status = CryptoDeposit.STATUS_CONFIRMED
    deposit.transaction = ledger_transaction
    deposit.verified_at = timezone.now()
    deposit.verified_by = admin_user
    deposit.save(
        update_fields=[
            "status",
            "transaction",
            "verified_at",
            "verified_by",
        ]
    )
    Notification.objects.create(
        transaction=ledger_transaction,
        user=deposit.user,
        notification_type="Credit Alert",
        amount=usd_amount,
    )
    return True


@transaction.atomic
def reject_crypto_deposit(deposit_id, admin_user):
    deposit = CryptoDeposit.objects.select_for_update().get(pk=deposit_id)
    if deposit.status != CryptoDeposit.STATUS_PENDING:
        return False

    deposit.status = CryptoDeposit.STATUS_REJECTED
    deposit.verified_at = timezone.now()
    deposit.verified_by = admin_user
    deposit.save(update_fields=["status", "verified_at", "verified_by"])
    return True
