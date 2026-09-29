# from datetime import timezone
from django.db import models
from userauths.models import User 
from account.models import Account
from shortuuid.django_fields import ShortUUIDField
# from django.utils.timezone import now
from django.utils import timezone
from django.db.models.signals import post_save
import uuid
from django.core.validators import MinValueValidator, RegexValidator



TRANSFER_TRANSACTION_TYPES = ("transfer", "received", "recieved")
RECEIVED_TRANSACTION_TYPES = TRANSFER_TRANSACTION_TYPES + ("crypto_deposit",)

TRANSACTION_TYPE = (
    ("transfer", "Transfer"),
    ("received", "Received"),
    ("recieved", "Recieved"),
    ("crypto_deposit", "Crypto Deposit"),
    ("withdraw", "withdraw"),
    ("refund", "Refund"),
    ("request", "Payment Request"),
    ("none", "None")
)

TRANSACTION_STATUS = (
    ("failed", "failed"),
    ("completed", "completed"),
    ("pending", "pending"),
    ("processing", "processing"),
    ("request_sent", "request_sent"),
    ("request_settled", "request settled"),
    ("request_processing", "request processing"),

)


CARD_TYPE = (
    ("master", "master"),
    ("visa", "visa"),
    ("verve", "verve"),

)


NOTIFICATION_TYPE = (
    ("None", "None"),
    ("Transfer", "Transfer"),
    ("Credit Alert", "Credit Alert"),
    ("Debit Alert", "Debit Alert"),
    ("Sent Payment Request", "Sent Payment Request"),
    ("Recieved Payment Request", "Recieved Payment Request"),
    ("Funded Credit Card", "Funded Credit Card"),
    ("Withdrew Credit Card Funds", "Withdrew Credit Card Funds"),
    ("Deleted Credit Card", "Deleted Credit Card"),
    ("Added Credit Card", "Added Credit Card"),

)

class Transaction(models.Model):
    transaction_id = ShortUUIDField(unique=True, length=15, max_length=20, prefix="TRN")

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="user")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    description = models.CharField(max_length=1000, null=True, blank=True)

    reciever = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="reciever")
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="sender")

    reciever_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, related_name="reciever_account")
    sender_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, related_name="sender_account")

    status = models.CharField(choices=TRANSACTION_STATUS, max_length=100, default="pending")
    transaction_type = models.CharField(choices=TRANSACTION_TYPE, max_length=100, default="none")

    date = models.DateTimeField(auto_now_add=False, default=timezone.now, editable=True)  # ✅ Editable
    updated = models.DateTimeField(default=timezone.now)  # editable by default

    def __str__(self):
        return str(self.user) if self.user else "Transaction"



class CreditCard(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    card_id = ShortUUIDField(unique=True, length=5, max_length=20, prefix="CARD", alphabet="1234567890")

    name = models.CharField(max_length=100)
    number = models.IntegerField()
    month = models.IntegerField()
    year = models.IntegerField()
    cvv = models.IntegerField()

    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    card_type = models.CharField(choices=CARD_TYPE, max_length=20, default="master")
    card_status = models.BooleanField(default=True)

    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user}"


class Notification(models.Model):
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notification_type = models.CharField(max_length=100, choices=NOTIFICATION_TYPE, default="none")
    amount = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    is_read = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    nid = ShortUUIDField(length=10, max_length=25, alphabet="abcdefghijklmnopqrstuvxyz")
    
    class Meta:
        ordering = ["-date"]
        verbose_name_plural = "Notification"

    def __str__(self):
        return f"{self.user} - {self.notification_type}"


class CryptoWallet(models.Model):
    network = models.CharField(max_length=20, default="TRC20", editable=False)
    address = models.CharField(
        max_length=128,
        validators=[
            RegexValidator(
                regex=r"^T[1-9A-HJ-NP-Za-km-z]{33}$",
                message="Enter a valid-looking TRON wallet address.",
            )
        ],
    )
    changelly_url = models.URLField(default="https://changelly.com/buy")
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paylio USDT receiving wallet"
        verbose_name_plural = "Paylio USDT receiving wallet"

    def __str__(self):
        return f"USDT {self.network} wallet"


class CryptoPaymentGateway(models.Model):
    GATEWAY_CHOICES = (
        ("changelly", "Changelly"),
        ("moonpay", "MoonPay"),
        ("transak", "Transak"),
    )

    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES, unique=True)
    buy_url = models.URLField()
    usd_per_usdt = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.000001)],
        help_text="USD credited for each 1 USDT received.",
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ("gateway",)
        verbose_name = "crypto payment gateway"
        verbose_name_plural = "crypto payment gateways"

    def __str__(self):
        return self.get_gateway_display()


class PaymentLink(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="crypto_payment_link",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"USDT payment link for {self.user}"


class CryptoDeposit(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending verification"),
        (STATUS_CONFIRMED, "Confirmed and credited"),
        (STATUS_REJECTED, "Rejected"),
    )

    payment_link = models.ForeignKey(
        PaymentLink,
        on_delete=models.PROTECT,
        related_name="deposits",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="crypto_deposits",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=6)
    network = models.CharField(max_length=20, default="TRC20", editable=False)
    wallet_address = models.CharField(max_length=128)
    gateway = models.ForeignKey(
        CryptoPaymentGateway,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="deposits",
    )
    usd_per_usdt_rate = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=1,
    )
    tx_hash = models.CharField(max_length=128, unique=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    transaction = models.OneToOneField(
        Transaction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="crypto_deposit",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_crypto_deposits",
    )

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.amount} USDT deposit for {self.user}"


def create_transfer_notification(sender, instance, **kwargs):
    if (
        instance.transaction_type in {"transfer", "received", "recieved"}
        and instance.status == "completed"
        and instance.reciever_id
    ):
        Notification.objects.get_or_create(
            transaction=instance,
            user_id=instance.reciever_id,
            notification_type="Credit Alert",
            defaults={"amount": instance.amount},
        )


post_save.connect(create_transfer_notification, sender=Transaction)