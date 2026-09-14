import requests
from django.conf import settings


class SupabaseAuthError(Exception):
    pass


def _request(path, payload):
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        raise SupabaseAuthError(
            "Supabase Auth is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY."
        )

    try:
        response = requests.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/{path}",
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
    except requests.RequestException as exc:
        raise SupabaseAuthError("Supabase Auth is temporarily unavailable.") from exc

    if not response.ok:
        try:
            body = response.json()
            detail = (
                body.get("msg")
                or body.get("error_description")
                or body.get("message")
                or body.get("error")
            )
        except ValueError:
            detail = None
        raise SupabaseAuthError(detail or "Supabase Auth rejected the request.")

    return response.json()


def sign_up(email, password):
    return _request("signup", {"email": email, "password": password})


def sign_in(email, password):
    return _request("token?grant_type=password", {"email": email, "password": password})


def sign_out(access_token):
    if not access_token or not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        return
    try:
        requests.post(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/logout",
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {access_token}",
            },
            timeout=15,
        )
    except requests.RequestException:
        pass
