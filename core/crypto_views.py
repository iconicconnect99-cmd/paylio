from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from account.models import KYC
from core.crypto_forms import CryptoDepositForm
from core.models import CryptoDeposit, CryptoPaymentGateway, CryptoWallet, PaymentLink


def _recipient_name(user):
    try:
        return user.kyc.full_name
    except KYC.DoesNotExist:
        return user.username


@login_required
def receive_usdt(request):
    payment_link, _ = PaymentLink.objects.get_or_create(user=request.user)
    share_url = request.build_absolute_uri(
        reverse("core:crypto-payment", args=[payment_link.token])
    )
    gateways = CryptoPaymentGateway.objects.filter(
        enabled=True,
        usd_per_usdt__isnull=False,
    )
    return render(
        request,
        "crypto/receive-usdt.html",
        {
            "payment_link": payment_link,
            "share_url": share_url,
            "recipient_name": _recipient_name(request.user),
            "gateways": gateways,
            "deposits": payment_link.deposits.select_related("transaction"),
        },
    )


def crypto_payment(request, token):
    payment_link = get_object_or_404(
        PaymentLink.objects.select_related("user"),
        token=token,
    )
    wallet = CryptoWallet.objects.first()
    gateways = CryptoPaymentGateway.objects.filter(enabled=True)
    recipient_name = _recipient_name(payment_link.user)

    form = CryptoDepositForm(request.POST or None)
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
            "wallet": wallet,
            "gateways": gateways,
            "form": form,
        },
    )
