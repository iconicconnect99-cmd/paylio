import logging
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core import signing
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from account.models import KYC
from core.crypto_forms import CryptoDepositForm, CryptoPaymentRequestForm
from core.models import CryptoDeposit, CryptoPaymentGateway, CryptoWallet, PaymentLink
from core.resend import send_resend_email

logger = logging.getLogger(__name__)
PAYMENT_REQUEST_SALT = "core.crypto-payment-request"
PAYMENT_REQUEST_MAX_AGE = 30 * 24 * 60 * 60


def _recipient_name(user):
    try:
        return user.kyc.full_name
    except KYC.DoesNotExist:
        return user.username


@login_required
def receive_usdt(request):
    payment_link, _ = PaymentLink.objects.get_or_create(user=request.user)
    form = CryptoPaymentRequestForm(request.POST or None)
    gateways = CryptoPaymentGateway.objects.filter(
        enabled=True,
        gateway__in=("changelly", "moonpay"),
    )
    wallet = CryptoWallet.objects.first()
    if request.method == "POST" and form.is_valid():
        if wallet is None:
            messages.error(
                request,
                "USDT payments are not available until a receiving wallet is configured.",
            )
        elif not settings.RESEND_API_KEY or not settings.RESEND_FROM_EMAIL:
            messages.error(
                request,
                "Resend email delivery is not configured. Please contact Paylio support.",
            )
        else:
            signed_request = signing.dumps(
                {"amount": str(form.cleaned_data["amount"])},
                salt=PAYMENT_REQUEST_SALT,
            )
            payment_url = request.build_absolute_uri(
                reverse("core:crypto-payment", args=[payment_link.token])
            )
            payment_url = f"{payment_url}?{urlencode({'request': signed_request})}"
            email_context = {
                "amount": form.cleaned_data["amount"],
                "payment_url": payment_url,
                "recipient_name": _recipient_name(request.user),
            }
            try:
                email_count = send_resend_email(
                    subject="Your Paylio USDT payment page",
                    text=render_to_string(
                        "crypto/payment-request-email.txt",
                        email_context,
                    ),
                    recipient=form.cleaned_data["sender_email"],
                    html=render_to_string(
                        "crypto/payment-request-email.html",
                        email_context,
                    ),
                )
            except OSError:
                logger.exception("Could not send a USDT payment request through Resend.")
                messages.error(
                    request,
                    "Paylio could not send the payment page email. Please try again later or contact support.",
                )
            else:
                if email_count != 1:
                    messages.error(
                        request,
                        "Paylio could not send the payment page email. Please try again later.",
                    )
                else:
                    messages.success(
                        request,
                        f"Payment page sent to {form.cleaned_data['sender_email']}.",
                    )
                    return redirect("core:crypto-receive")

    return render(
        request,
        "crypto/receive-usdt.html",
        {
            "payment_link": payment_link,
            "form": form,
            "recipient_name": _recipient_name(request.user),
            "gateways": gateways,
            "wallet": wallet,
            "payment_email_from": settings.RESEND_FROM_EMAIL,
            "deposits": payment_link.deposits.select_related("transaction"),
        },
    )


def crypto_payment(request, token):
    payment_link = get_object_or_404(
        PaymentLink.objects.select_related("user"),
        token=token,
    )
    wallet = CryptoWallet.objects.first()
    gateways = CryptoPaymentGateway.objects.filter(
        enabled=True,
        gateway__in=("changelly", "moonpay"),
    )
    recipient_name = _recipient_name(payment_link.user)
    requested_amount = None
    signed_request = request.GET.get("request")
    if signed_request:
        try:
            payload = signing.loads(
                signed_request,
                salt=PAYMENT_REQUEST_SALT,
                max_age=PAYMENT_REQUEST_MAX_AGE,
            )
            requested_amount = Decimal(payload["amount"])
            if requested_amount <= 0:
                raise InvalidOperation
        except (signing.BadSignature, KeyError, TypeError, InvalidOperation):
            raise Http404("This payment request link is invalid or has expired.")

    form = CryptoDepositForm(
        request.POST or None,
        initial={"amount": requested_amount} if requested_amount is not None else None,
    )
    if request.method == "POST" and form.is_valid():
        if wallet is None:
            messages.error(request, "USDT deposits are not available yet.")
        else:
            gateway_unavailable = False
            try:
                with transaction.atomic():
                    deposit = form.save(commit=False)
                    deposit.payment_link = payment_link
                    deposit.user = payment_link.user
                    deposit.network = wallet.network
                    deposit.wallet_address = wallet.address
                    gateway = CryptoPaymentGateway.objects.select_for_update().get(
                        pk=form.cleaned_data["gateway"].pk
                    )
                    if not gateway.enabled or gateway.usd_per_usdt is None:
                        gateway_unavailable = True
                    else:
                        deposit.gateway = gateway
                        deposit.usd_per_usdt_rate = gateway.usd_per_usdt
                        deposit.save()
            except IntegrityError:
                if CryptoDeposit.objects.filter(
                    tx_hash=form.cleaned_data["tx_hash"]
                ).exists():
                    form.add_error(
                        "tx_hash",
                        "This transaction hash has already been submitted.",
                    )
                else:
                    raise
            else:
                if gateway_unavailable:
                    form.add_error(
                        "gateway",
                        "This gateway is no longer available. Select another gateway.",
                    )
                else:
                    messages.success(
                        request,
                        "Payment submitted for verification. Your balance will update after Paylio confirms it.",
                    )
                    return redirect("core:crypto-payment", token=payment_link.token)

    return render(
        request,
        "crypto/payment.html",
        {
            "payment_link": payment_link,
            "recipient_name": recipient_name,
            "requested_amount": requested_amount,
            "wallet": wallet,
            "gateways": gateways,
            "form": form,
        },
    )
