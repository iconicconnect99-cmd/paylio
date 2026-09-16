from django.shortcuts import get_object_or_404, render, redirect
from account.models import Account
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib import messages
from decimal import Decimal
from core.models import Transaction, Notification


# from django.shortcuts import redirect
# from django.contrib import messages
# from decimal import Decimal
# from django.db.models import Q

# Helper function to check if KYC is completed
def kyc_check(user):
    return user.account.kyc_confirmed  # Assuming `kyc_completed` is a boolean field in the Account model

@login_required
def search_users_account_number(request):
    account = Account.objects.all()
    query = request.POST.get("account_number")  # e.g., 217703423324

    if query:
        account = account.filter(
            Q(account_number=query) |
            Q(account_id=query)
        ).distinct()
    
    context = {
        "account": account,
        "query": query,
    }
    return render(request, "transfer/search-user-by-account-number.html", context)


@login_required
def AmountTransfer(request, account_number):
    if not kyc_check(request.user):
        messages.warning(request, "Please complete your KYC to proceed with transfers.")
        return redirect("account:kyc-reg")  # Replace with your KYC page URL name

    try:
        account = Account.objects.get(account_number=account_number)
    except Account.DoesNotExist:
        messages.warning(request, "Account does not exist.")
        return redirect("core:search-account")
    
    context = {
        "account": account,
    }
    return render(request, "transfer/amount-transfer.html", context)


# @login_required
# def AmountTransferProcess(request, account_number):
#     user_account = get_object_or_404(Account, user=request.user)

#     if not kyc_check(request.user):
#         messages.warning(request, "Please complete your KYC to proceed with transfers.")
#         return redirect("account:kyc-reg")
    
#     # Check if the user's location is enabled
#     if user_account.location:
#         messages.warning(request, "Please enable your location to proceed with transfers.")
#         return redirect("core:location")

#     # Always redirect to the transfer_error page
#     return redirect("core:transfer-error")

@login_required
def AmountTransferProcess(request, account_number):
    user_account = get_object_or_404(Account, user=request.user)

    if not kyc_check(request.user):
        messages.warning(request, "Please complete your KYC to proceed with transfers.")
        return redirect("account:kyc-reg")
    
    # Check if the user's location is enabled
    if user_account.location:
        messages.warning(request, "Please enable your location to proceed with transfers.")
        return redirect("core:location")

    account = Account.objects.get(account_number=account_number)
    sender_account = request.user.account

    if request.method == "POST":
        amount = request.POST.get("amount-send")
        description = request.POST.get("description")

        if sender_account.account_balance >= Decimal(amount):
            new_transaction = Transaction.objects.create(
                user=request.user,
                amount=amount,
                description=description,
                reciever=account.user,
                sender=request.user,
                sender_account=sender_account,
                reciever_account=account,
                status="processing",
                transaction_type="transfer"
            )
            return redirect("core:transfer-confirmation", account.account_number, new_transaction.transaction_id)
        else:
            messages.warning(request, "Insufficient funds.")
            return redirect("core:amount-transfer", account.account_number)
    else:
        messages.warning(request, "An error occurred. Try again later.")
        return redirect("account:account")


@login_required
def TransferConfirmation(request, account_number, transaction_id):
    if not kyc_check(request.user):
        messages.warning(request, "Please complete your KYC to proceed with transfers.")
        return redirect("account:kyc-reg")

    try:
        account = Account.objects.get(account_number=account_number)
        transaction = Transaction.objects.get(transaction_id=transaction_id)
    except (Account.DoesNotExist, Transaction.DoesNotExist):
        messages.warning(request, "Transaction does not exist.")
        return redirect("account:account")

    context = {
        "account": account,
        "transaction": transaction,
    }
    return render(request, "transfer/transfer-confirmation.html", context)


@login_required
def TransferProcess(request, account_number, transaction_id):
    if not kyc_check(request.user):
        messages.warning(request, "Please complete your KYC to proceed with transfers.")
        return redirect("account:kyc-reg")

    account = Account.objects.get(account_number=account_number)
    transaction = Transaction.objects.get(transaction_id=transaction_id)
    sender_account = request.user.account

    if request.method == "POST":
        pin_number = request.POST.get("pin-number")

        if pin_number == sender_account.pin_number:
            transaction.status = "completed"
            transaction.save()

            sender_account.account_balance -= transaction.amount
            sender_account.save()

            account.account_balance += transaction.amount
            account.save()

            Notification.objects.create(
                transaction=transaction,
                amount=transaction.amount,
                user=account.user,
                notification_type="Credit Alert"
            )

            Notification.objects.create(
                transaction=transaction,
                user=request.user,
                notification_type="Debit Alert",
                amount=transaction.amount
            )

            messages.success(request, "Transfer successful.")
            return redirect("core:transfer-completed", account.account_number, transaction.transaction_id)
        else:
            messages.warning(request, "Incorrect PIN.")
            return redirect('core:transfer-confirmation', account.account_number, transaction.transaction_id)
    else:
        messages.warning(request, "An error occurred. Try again later.")
        return redirect('account:account')


@login_required
def TransferCompleted(request, account_number, transaction_id):
    if not kyc_check(request.user):
        messages.warning(request, "Please complete your KYC to proceed with transfers.")
        return redirect("account:kyc-reg")

    try:
        account = Account.objects.get(account_number=account_number)
        transaction = Transaction.objects.get(transaction_id=transaction_id)
    except (Account.DoesNotExist, Transaction.DoesNotExist):
        messages.warning(request, "Transfer does not exist.")
        return redirect("account:account")

    context = {
        "account": account,
        "transaction": transaction,
    }
    return render(request, "transfer/transfer-completed.html", context)


def transfer_error(request):
    return render(request, "transfer/transfer-error.html")

def location(request):
    return render(request, "transfer/location.html")
