from django.contrib import admin
from account.models import Account, KYC
from userauths.models import User

class AccountAdminModel(admin.ModelAdmin):
    list_editable = ['account_status', 'account_balance', 'kyc_submitted', 'kyc_confirmed', 'location']
    list_display = ['user', 'account_number', 'account_status', 'account_balance', 'kyc_submitted', 'kyc_confirmed', 'location']
    list_filter = ['account_status', 'kyc_submitted', 'kyc_confirmed']
    search_fields = ['user__username', 'user__email', 'account_number']
    readonly_fields = ['id', 'account_number', 'account_id', 'pin_number', 'red_code', 'date']

class KYCAdmin(admin.ModelAdmin):
    search_fields = ["full_name", "user__username", "user__email"]
    list_display = ['user', 'full_name', 'gender', 'identity_type', 'date_of_birth']
    readonly_fields = ['id', 'date']
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'account', 'id', 'date')
        }),
        ('Personal Information', {
            'fields': ('full_name', 'gender', 'marrital_status', 'date_of_birth')
        }),
        ('Contact Information', {
            'fields': ('mobile', 'fax', 'country', 'state', 'city')
        }),
        ('Documents', {
            'fields': ('image', 'identity_type', 'identity_image', 'signature')
        }),
    )


admin.site.register(Account, AccountAdminModel)
admin.site.register(KYC, KYCAdmin)