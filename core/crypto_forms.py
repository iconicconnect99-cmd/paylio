import re

from django import forms

from core.models import CryptoDeposit, CryptoPaymentGateway


class CryptoDepositForm(forms.ModelForm):
    gateway = forms.ModelChoiceField(
        queryset=CryptoPaymentGateway.objects.none(),
        empty_label="Select a payment gateway",
    )
    amount = forms.DecimalField(
        max_digits=18,
        decimal_places=6,
        min_value=0.01,
        widget=forms.NumberInput(
            attrs={
                "step": "0.000001",
                "min": "0.01",
                "placeholder": "Amount in USDT",
                "data-usdt-amount": "true",
            }
        ),
    )
    tx_hash = forms.CharField(
        max_length=128,
        widget=forms.TextInput(
            attrs={
                "placeholder": "TRON transaction hash",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = CryptoDeposit
        fields = ("gateway", "amount", "tx_hash")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["gateway"].queryset = CryptoPaymentGateway.objects.filter(
            enabled=True,
            usd_per_usdt__isnull=False,
        )
        self.fields["gateway"].widget.attrs["id"] = "gateway-select"

    def clean_tx_hash(self):
        tx_hash = self.cleaned_data["tx_hash"].strip()
        if not re.fullmatch(r"[0-9a-fA-F]{64}", tx_hash):
            raise forms.ValidationError(
                "Enter the 64-character transaction hash from TRONSCAN."
            )
        return tx_hash.lower()
