from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlencode

from app.core.config import Settings, get_settings


def password_reset_mail_configured(settings: Settings | None = None) -> bool:
    config = settings or get_settings()
    return bool(
        config.smtp_host
        and config.smtp_user
        and config.smtp_password
        and config.smtp_from_email
        and config.cors_origins
    )


def send_password_reset_email(recipient: str, token: str, settings: Settings | None = None, *, message_id: str | None = None) -> None:
    config = settings or get_settings()
    if not password_reset_mail_configured(config):
        raise RuntimeError("Password reset email is not configured")

    # Keep the secret in the fragment so it is not included in HTTP requests
    # or Referrer headers.
    origin = config.cors_origins[0].rstrip("/")
    reset_link = f"{origin}/#auth?{urlencode({'reset_token': token})}"
    message = EmailMessage()
    message["Subject"] = "إعادة تعيين كلمة المرور — منصة الكيمياء"
    message["From"] = config.smtp_from_email
    message["To"] = recipient
    if message_id:
        message["Message-ID"] = f"<reset-{message_id}@chemistry.local>"
    message.set_content(
        "طلبت إعادة تعيين كلمة المرور. افتح الرابط التالي خلال "
        f"{config.password_reset_ttl_minutes} دقيقة:\n\n{reset_link}\n\n"
        "إذا لم تطلب ذلك، تجاهل الرسالة."
    )

    # smtplib's implicit default context does not verify certificates. Never
    # rely on it when transmitting SMTP credentials and reset links.
    tls_context = ssl.create_default_context() if config.smtp_tls_verify else ssl._create_unverified_context()
    with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=10, context=tls_context) as server:
        server.login(config.smtp_user, config.smtp_password)
        server.send_message(message)
