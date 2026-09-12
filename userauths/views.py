import hmac
import os

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render

from account.models import Account
from userauths.forms import ApprovedAdminRegisterForm, UserRegisterForm
from userauths.models import User


def _account_allows_login(user):
    if user.is_superuser:
        return True
    try:
        return Account.objects.get(user=user).location
    except Account.DoesNotExist:
        return False


def _login_user(request, user, password):
    authenticated_user = authenticate(request, email=user.email, password=password)
    if authenticated_user is None:
        return False
    if not _account_allows_login(authenticated_user):
        return False
    login(request, authenticated_user)
    return True


def RegisterView(request):
    if request.user.is_authenticated:
        messages.warning(request, "You are already logged in.")
        return redirect("account:dashboard")

    form = UserRegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        new_user = form.save()
        if _login_user(request, new_user, form.cleaned_data["password1"]):
            messages.success(request, f"Hey {new_user.username}, your account was created successfully.")
            return redirect("account:dashboard")
        messages.warning(request, "Service is not available in your location.")

    return render(request, "userauths/sign-up.html", {"form": form})


def AdminRegisterView(request):
    if request.user.is_authenticated:
        messages.warning(request, "You are already logged in.")
        return redirect("account:dashboard")

    form = ApprovedAdminRegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        configured_code = os.environ.get("PAYLIO_ADMIN_INVITE_CODE", "")
        supplied_code = form.cleaned_data["invite_code"]
        if not configured_code or not hmac.compare_digest(supplied_code, configured_code):
            form.add_error("invite_code", "The admin invite code is invalid.")
        else:
            new_user = form.save(commit=False)
            new_user.is_approved_admin = True
            new_user.save()
            if _login_user(request, new_user, form.cleaned_data["password1"]):
                messages.success(request, "Your approved admin account was created.")
                return redirect("account:dashboard")

    return render(request, "userauths/admin-sign-up.html", {"form": form})


def LoginView(request):
    if request.user.is_authenticated:
        messages.warning(request, "You are already logged in.")
        return redirect("account:dashboard")

    if request.method == "POST":
        email = request.POST.get("email", "")
        password = request.POST.get("password", "")
        user = authenticate(request, email=email, password=password)
        if user is not None:
            if _account_allows_login(user):
                login(request, user)
                messages.success(request, "You are logged in.")
                return redirect("account:dashboard")
            messages.warning(request, "Service is not available in your location.")
        else:
            messages.warning(request, "Email or password is incorrect.")

    return render(request, "userauths/sign-in.html")


def logoutView(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("userauths:sign-in")
