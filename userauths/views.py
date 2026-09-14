import hmac
import os

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import Permission
from django.shortcuts import redirect, render
from django.urls import reverse

from account.models import Account
from userauths.forms import ApprovedAdminRegisterForm, UserRegisterForm
from userauths.models import User
from userauths.supabase_auth import SupabaseAuthError, sign_in, sign_out, sign_up


def _account_allows_login(user):
    if user.is_staff and user.is_approved_admin:
        return True
    try:
        return not Account.objects.get(user=user).location
    except Account.DoesNotExist:
        return False


def _login_django_user(request, user, password):
    authenticated_user = authenticate(request, email=user.email, password=password)
    if authenticated_user is None or not _account_allows_login(authenticated_user):
        return False
    login(request, authenticated_user)
    return True


def _sync_supabase_user(supabase_user, email, username):
    user, created = User.objects.get_or_create(
        email=email.lower(),
        defaults={"username": username},
    )
    if created or not user.username:
        user.username = username
    user.supabase_uid = supabase_user.get("id")
    user.set_unusable_password()
    user.save(update_fields=["username", "supabase_uid", "password"])
    return user, created


def _grant_admin_permissions(user):
    user.user_permissions.set(Permission.objects.all())


def RegisterView(request):
    if request.user.is_authenticated:
        messages.warning(request, "You are already logged in.")
        return redirect("account:dashboard")

    form = UserRegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        try:
            supabase_user = sign_up(email, form.cleaned_data["password1"])
            new_user, _ = _sync_supabase_user(
                supabase_user,
                email,
                form.cleaned_data["username"],
            )
            if supabase_user.get("access_token"):
                request.session["supabase_access_token"] = supabase_user["access_token"]
                if _account_allows_login(new_user):
                    login(
                        request,
                        new_user,
                        backend="django.contrib.auth.backends.ModelBackend",
                    )
                    messages.success(
                        request,
                        f"Hey {new_user.username}, your account was created successfully.",
                    )
                    return redirect("account:dashboard")
                messages.warning(request, "Service is not available in your location.")
            else:
                messages.success(
                    request,
                    "Account created. Check your email to confirm it, then log in.",
                )
                return redirect("userauths:sign-in")
        except SupabaseAuthError as exc:
            form.add_error(None, str(exc))

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
            email = form.cleaned_data["email"].strip().lower()
            try:
                supabase_user = sign_up(email, form.cleaned_data["password1"])
                new_user, _ = _sync_supabase_user(
                    supabase_user,
                    email,
                    form.cleaned_data["username"],
                )
                new_user.is_staff = True
                new_user.is_approved_admin = True
                new_user.save(update_fields=["is_staff", "is_approved_admin"])
                _grant_admin_permissions(new_user)
                if supabase_user.get("access_token"):
                    request.session["supabase_access_token"] = supabase_user["access_token"]
                    login(
                        request,
                        new_user,
                        backend="django.contrib.auth.backends.ModelBackend",
                    )
                    messages.success(request, "Your approved admin account was created.")
                    return redirect("admin:index")
                messages.success(
                    request,
                    "Admin account created. Confirm your email, then log in at /admin/.",
                )
                return redirect("admin:login")
            except SupabaseAuthError as exc:
                form.add_error(None, str(exc))

    return render(request, "userauths/admin-sign-up.html", {"form": form})


def LoginView(request):
    if request.user.is_authenticated:
        messages.warning(request, "You are already logged in.")
        return redirect("account:dashboard")

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        try:
            auth_response = sign_in(email, password)
            supabase_user = auth_response.get("user") or {}
            user, _ = _sync_supabase_user(
                supabase_user,
                email,
                supabase_user.get("user_metadata", {}).get("username")
                or email.split("@", 1)[0],
            )
            if _account_allows_login(user):
                request.session["supabase_access_token"] = auth_response.get(
                    "access_token",
                    "",
                )
                login(
                    request,
                    user,
                    backend="django.contrib.auth.backends.ModelBackend",
                )
                messages.success(request, "You are logged in.")
                return redirect("account:dashboard")
            messages.warning(request, "Service is not available in your location.")
        except SupabaseAuthError:
            messages.warning(request, "Email or password is incorrect.")

    return render(request, "userauths/sign-in.html")


def logoutView(request):
    sign_out(request.session.get("supabase_access_token"))
    request.session.pop("supabase_access_token", None)
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("userauths:sign-in")


def AdminLoginView(request):
    if request.user.is_authenticated and request.user.is_staff and request.user.is_approved_admin:
        return redirect(request.GET.get("next") or "admin:index")

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        next_url = request.POST.get("next") or request.GET.get("next") or reverse("admin:index")
        try:
            auth_response = sign_in(email, password)
            supabase_user = auth_response.get("user") or {}
            user, _ = _sync_supabase_user(
                supabase_user,
                email,
                supabase_user.get("user_metadata", {}).get("username")
                or email.split("@", 1)[0],
            )
            if not user.is_staff or not user.is_approved_admin:
                messages.error(request, "This Supabase account is not approved for administration.")
            else:
                request.session["supabase_access_token"] = auth_response.get(
                    "access_token",
                    "",
                )
                login(
                    request,
                    user,
                    backend="django.contrib.auth.backends.ModelBackend",
                )
                return redirect(next_url)
        except SupabaseAuthError:
            messages.error(request, "The admin email or password is incorrect.")

    return render(
        request,
        "userauths/admin-login.html",
        {"next": request.GET.get("next", "")},
    )
