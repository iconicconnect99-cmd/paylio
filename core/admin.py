from django.contrib import admin
from core.models import Transaction, CreditCard, Notification

class TransactionAdmin(admin.ModelAdmin):
    list_editable = ['amount', 'status', 'transaction_type']
    list_display = ['user', 'amount', 'status', 'transaction_type', 'reciever', 'sender', 'date']
    fields = (
        'transaction_id',
        'user', 'amount', 'description',
        'reciever', 'sender',
        'reciever_account', 'sender_account',
        'status', 'transaction_type',
        'date', 'updated'  # ✅ Date can be edited
    )


class CreditCardAdmin(admin.ModelAdmin):
    list_editable = ['amount', 'card_type']
    list_display = ['user', 'amount', 'card_type']
    

class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'amount' ,'date']

admin.site.register(Transaction, TransactionAdmin)
admin.site.register(CreditCard, CreditCardAdmin)
admin.site.register(Notification, NotificationAdmin)