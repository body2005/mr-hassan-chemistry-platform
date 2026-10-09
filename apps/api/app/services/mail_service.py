from __future__ import annotations

import smtplib
import ssl
import hashlib
import json
from email.message import EmailMessage
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from app.core.config import Settings, get_settings


def password_reset_mail_configured(settings: Settings | None = None) -> bool:
    config = settings or get_settings()
    if not config.email_enabled or not config.cors_origins:
        return False
    if config.email_provider == 'resend':
        return bool(config.resend_api_key and config.resend_api_key.get_secret_value().strip()
                    and config.email_from_email and config.email_from_email.strip())
    return all(bool(value and value.strip()) for value in (
        config.smtp_host, config.smtp_user, config.smtp_password, config.smtp_from_email
    ))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a provider credential to a redirect destination.
        return None


def _send_resend(recipient: str, subject: str, text: str, token: str,
                 config: Settings, message_id: str | None) -> None:
    identity = message_id or hashlib.sha256(token.encode()).hexdigest()
    payload = {'from': config.email_from_email, 'to': [recipient],
               'subject': subject, 'text': text}
    request = Request('https://api.resend.com/emails',
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Authorization': f'Bearer {config.resend_api_key.get_secret_value()}',
                 'Content-Type': 'application/json', 'User-Agent': 'chemistry-platform/1.0',
                 'Idempotency-Key': f'password-reset-{identity}'}, method='POST')
    try:
        opener = build_opener(HTTPSHandler(context=ssl.create_default_context()), _NoRedirect())
        with opener.open(request, timeout=10) as response:
            data = response.read(65537)
            if response.status not in (200, 201) or len(data) > 65536:
                raise ValueError('Invalid email provider response')
            result = json.loads(data)
            if not isinstance(result, dict) or not isinstance(result.get('id'), str) or not result['id']:
                raise ValueError('Missing email provider delivery ID')
    except (OSError, ValueError):
        # No provider response, recipient, key or reset URL in errors/logs.
        raise RuntimeError('Password reset email provider request failed') from None


def send_password_reset_email(recipient: str, token: str, settings: Settings | None = None, *, message_id: str | None = None) -> None:
    config = settings or get_settings()
    if not password_reset_mail_configured(config):
        raise RuntimeError("Password reset email is not configured")

    # Keep the secret in the fragment so it is not included in HTTP requests
    # or Referrer headers.
    origin = config.cors_origins[0].rstrip("/")
    reset_link = f"{origin}/#auth?{urlencode({'reset_token': token})}"
    subject = "إعادة تعيين كلمة المرور — منصة الكيمياء"
    text = (
        "طلبت إعادة تعيين كلمة المرور. افتح الرابط التالي خلال "
        f"{config.password_reset_ttl_minutes} دقيقة:\n\n{reset_link}\n\n"
        "إذا لم تطلب ذلك، تجاهل الرسالة."
    )

    if config.email_provider == 'resend':
        _send_resend(recipient, subject, text, token, config, message_id)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.smtp_from_email
    message["To"] = recipient
    if message_id:
        message["Message-ID"] = f"<reset-{message_id}@chemistry.local>"
    message.set_content(text)

    # smtplib's implicit default context does not verify certificates. Never
    # rely on it when transmitting SMTP credentials and reset links.
    tls_context = ssl.create_default_context() if config.smtp_tls_verify else ssl._create_unverified_context()
    with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=10, context=tls_context) as server:
        server.login(config.smtp_user, config.smtp_password)
        server.send_message(message)
