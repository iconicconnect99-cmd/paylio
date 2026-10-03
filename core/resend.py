import json
import urllib.error
import urllib.request

from django.conf import settings


RESEND_EMAILS_URL = "https://api.resend.com/emails"


class ResendEmailError(OSError):
    pass


def send_resend_email(subject, recipient, text, html):
    api_key = settings.RESEND_API_KEY
    from_email = settings.RESEND_FROM_EMAIL
    if not api_key or not from_email:
        raise ResendEmailError("Resend email delivery is not configured.")

    payload = json.dumps(
        {
            "from": from_email,
            "to": [recipient],
            "subject": subject,
            "text": text,
            "html": html,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        RESEND_EMAILS_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.RESEND_TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ResendEmailError(
            f"Resend rejected the email request (HTTP {exc.code})."
        ) from exc
    except urllib.error.URLError as exc:
        raise ResendEmailError("Could not connect to the Resend email service.") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResendEmailError("Resend returned an invalid response.") from exc

    if not isinstance(result, dict) or not result.get("id"):
        raise ResendEmailError("Resend did not confirm the email request.")

    return 1
