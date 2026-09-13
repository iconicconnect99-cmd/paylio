from django.contrib import admin
from core.models import Transaction, CreditCard, Notification
from django.http import HttpResponse
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

admin.site.register(Transaction, TransactionAdmin)
admin.site.register(CreditCard, CreditCardAdmin)
admin.site.register(Notification, NotificationAdmin)