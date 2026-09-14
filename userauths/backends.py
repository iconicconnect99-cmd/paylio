from django.contrib.auth import get_user_model

from userauths.supabase_auth import SupabaseAuthError, sign_in


class SupabaseBackend:
    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        identifier = (email or username or "").strip().lower()
        if not identifier or not password:
            return None

        try:
            response = sign_in(identifier, password)
        except SupabaseAuthError:
            return None

        supabase_user = response.get("user") or {}
        if (supabase_user.get("email") or identifier).lower() != identifier:
            return None

        User = get_user_model()
        user = User.objects.filter(email=identifier).first()
        if user is None:
            return None

        user.supabase_uid = supabase_user.get("id")
        user.set_unusable_password()
        user.save(update_fields=["supabase_uid", "password"])
        if request is not None:
            request.session["supabase_access_token"] = response.get("access_token", "")
        return user

    def get_user(self, user_id):
        User = get_user_model()
        return User.objects.filter(pk=user_id, is_active=True).first()
