from django.contrib import admin
from core.crypto_deposits import confirm_crypto_deposit, reject_crypto_deposit
from core.models import (
    CryptoDeposit,
    CryptoPaymentGateway,
    CryptoWallet,
    CreditCard,
    Notification,
    Transaction,
)
from django.http import HttpResponse
from django.utils.html import format_html
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class TransactionAdmin(admin.ModelAdmin):
    list_editable = ['amount', 'status', 'transaction_type']
    list_display = ['user', 'amount', 'status', 'transaction_type', 'reciever', 'sender', 'date']
    list_filter = ['status', 'transaction_type', 'user']
    search_fields = ['transaction_id', 'user__email', 'user__username', 'description']
    date_hierarchy = 'date'
    actions = ['download_transaction_history_pdf']
    fields = (
        'transaction_id',
        'user', 'amount', 'description',
        'reciever', 'sender',
        'reciever_account', 'sender_account',
        'status', 'transaction_type',
        'date', 'updated'  # ✅ Date can be edited
    )

    @admin.action(description='Download transaction history PDF')
    def download_transaction_history_pdf(self, request, queryset):
        if not queryset.exists():
            self.message_user(request, 'Select at least one transaction.', level='error')
            return None

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="transaction-history.pdf"'
        document = SimpleDocTemplate(
            response,
            pagesize=landscape(A4),
            rightMargin=10 * mm,
            leftMargin=10 * mm,
            topMargin=10 * mm,
            bottomMargin=10 * mm,
        )
        styles = getSampleStyleSheet()
        story = [
            Paragraph('Paylio Transaction History', styles['Title']),
            Spacer(1, 5 * mm),
        ]
        headers = [
            'Transaction', 'User', 'Amount', 'Status', 'Type',
            'Sender', 'Receiver', 'Description', 'Date',
        ]
        rows = [headers]
        for transaction in queryset.select_related('user', 'sender', 'reciever').order_by('date'):
            rows.append([
                transaction.transaction_id,
                transaction.user.email if transaction.user else '-',
                str(transaction.amount),
                transaction.get_status_display(),
                transaction.get_transaction_type_display(),
                transaction.sender.email if transaction.sender else '-',
                transaction.reciever.email if transaction.reciever else '-',
                transaction.description or '-',
                transaction.date.strftime('%Y-%m-%d %H:%M'),
            ])

        table = Table(rows, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4338ca')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
        ]))
        story.append(table)
        document.build(story)
        return response


class CreditCardAdmin(admin.ModelAdmin):
    list_editable = ['amount', 'card_type']
    list_display = ['user', 'amount', 'card_type']
    

class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'amount' ,'date']


@admin.register(CryptoWallet)
class CryptoWalletAdmin(admin.ModelAdmin):
    list_display = ("network", "address", "updated")
    fields = ("network", "address", "updated")
    readonly_fields = ("network", "updated")

    def has_add_permission(self, request):
        return not CryptoWallet.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CryptoPaymentGateway)
class CryptoPaymentGatewayAdmin(admin.ModelAdmin):
    list_display = ("gateway", "usd_per_usdt", "enabled", "buy_url")
    list_editable = ("usd_per_usdt", "enabled", "buy_url")
    list_display_links = ("gateway",)
    fields = ("gateway", "buy_url", "usd_per_usdt", "enabled")
    readonly_fields = ("gateway",)
    help_texts = {
        "usd_per_usdt": "USD added to the recipient balance per 1 USDT verified on TRON.",
        "buy_url": "The provider page that opens when the sender chooses this gateway.",
    }


@admin.register(CryptoDeposit)
class CryptoDepositAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "amount",
        "gateway",
        "usd_per_usdt_rate",
        "network",
        "status",
        "explorer_link",
        "submitted_at",
    )
    list_filter = ("status", "network", "submitted_at")
    search_fields = ("user__email", "user__username", "tx_hash")
    readonly_fields = (
        "payment_link",
        "user",
        "amount",
        "gateway",
        "usd_per_usdt_rate",
        "network",
        "wallet_address",
        "tx_hash",
        "status",
        "transaction",
        "submitted_at",
        "verified_at",
        "verified_by",
        "explorer_link",
    )
    fields = readonly_fields
    actions = ("confirm_and_credit", "reject_deposits")

    @admin.display(description="TRONSCAN")
    def explorer_link(self, deposit):
        return format_html(
            '<a href="https://tronscan.org/#/transaction/{}" target="_blank" rel="noopener">Verify on TRONSCAN</a>',
            deposit.tx_hash,
        )

    @admin.action(description="Confirm verified deposits and credit balances")
    def confirm_and_credit(self, request, queryset):
        credited = 0
        for deposit_id in queryset.values_list("pk", flat=True):
            credited += confirm_crypto_deposit(deposit_id, request.user)
        self.message_user(request, f"{credited} deposit(s) credited.")

    @admin.action(description="Reject selected pending deposits")
    def reject_deposits(self, request, queryset):
        rejected = 0
        for deposit_id in queryset.values_list("pk", flat=True):
            rejected += reject_crypto_deposit(deposit_id, request.user)
        self.message_user(request, f"{rejected} deposit(s) rejected.")


admin.site.register(Transaction, TransactionAdmin)
admin.site.register(CreditCard, CreditCardAdmin)
admin.site.register(Notification, NotificationAdmin)