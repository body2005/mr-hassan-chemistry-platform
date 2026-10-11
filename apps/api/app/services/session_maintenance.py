"""Bounded, multi-worker safe maintenance. No token or recipient logs."""
import asyncio
import base64
import hashlib
import logging
import json
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.mail_outbox import ResetMailOutbox, ResetRequestOutbox
from app.models.platform import RefreshSession, RevokedSession
from app.models.user import PasswordResetToken, User
from app.services.mail_service import send_password_reset_email

logger = logging.getLogger(__name__)


def token_cipher():
    # Domain-separated application key; rotating SECRET_KEY requires draining
    # the outbox first. Unreadable ciphertext is never logged or mailed.
    key = hashlib.sha256(("reset-mail-outbox-v1:" + get_settings().secret_key).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def enqueue_reset_mail(db, token, raw_token):
    db.flush()
    db.add(ResetMailOutbox(token_id=token.id, encrypted_token=token_cipher().encrypt(raw_token.encode()).decode()))


def request_cipher():
    key = hashlib.sha256(("reset-request-outbox-v1:" + get_settings().secret_key).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def enqueue_reset_request(db, email, institution_slug):
    # Uniform work for every validated identity, including unknown tenants.
    # Pad the encrypted envelope so its length depends on neither lookup nor
    # input length. Never look up a user, publish a broker task, or send mail.
    payload = json.dumps([email.strip().lower(), institution_slug.strip().lower()],
                         ensure_ascii=True, separators=(",", ":")).encode()
    if len(payload) > 4096:
        raise ValueError("Reset identity exceeds the envelope limit")
    now = datetime.now(timezone.utc)
    db.add(ResetRequestOutbox(encrypted_identity=request_cipher().encrypt(payload.ljust(4096, b" ")).decode(),
                             requested_at=now, expires_at=now + timedelta(minutes=5)))
    db.commit()


def process_reset_requests(batch_size=25):
    if not get_settings().email_enabled:
        return 0
    from app.services.auth_service import request_password_reset
    processed = 0
    for _ in range(min(batch_size, 25)):
        with SessionLocal() as db:
            job = db.scalar(select(ResetRequestOutbox).where(ResetRequestOutbox.completed_at.is_(None))
                .order_by(ResetRequestOutbox.requested_at).with_for_update(skip_locked=True).limit(1))
            if job is None:
                break
            now = datetime.now(timezone.utc)
            expires = job.expires_at.replace(tzinfo=timezone.utc) if job.expires_at.tzinfo is None else job.expires_at
            if expires > now:
                try:
                    email, institution_slug = json.loads(request_cipher().decrypt(job.encrypted_identity.encode()))
                except (ValueError, TypeError, AttributeError, InvalidToken):
                    logger.warning("Unreadable reset request discarded (no identity details)")
                else:
                    # Token, mail job, request completion and erasure commit
                    # together. A consumer crash rolls ALL of them back.
                    request_password_reset(db, email, institution_slug, enqueue_mail=True,
                                           requested_at=job.requested_at, commit=False)
            job.completed_at = now
            job.encrypted_identity = None
            db.commit()
            processed += 1
    return processed


def deliver_reset_mail(batch_size=5):
    if not get_settings().email_enabled:
        return 0
    delivered = 0
    for _ in range(min(batch_size, 25)):
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            job = db.scalar(select(ResetMailOutbox).where(ResetMailOutbox.completed_at.is_(None),
                ResetMailOutbox.retry_at <= now).order_by(ResetMailOutbox.retry_at)
                .with_for_update(skip_locked=True).limit(1))
            if job is None:
                break
            token = db.get(PasswordResetToken, job.token_id)
            user = db.get(User, token.user_id) if token else None
            expires = token.expires_at.replace(tzinfo=timezone.utc) if token and token.expires_at.tzinfo is None else token.expires_at if token else now
            if token is None or token.used_at or expires <= now or user is None or not user.is_active or user.deleted_at:
                job.completed_at = now
                job.encrypted_token = None
            else:
                try:
                    raw_token = token_cipher().decrypt(job.encrypted_token.encode()).decode()
                    # Stable Message-ID provides delivery identity across an
                    # SMTP accepted/commit-lost retry; SMTP remains at-least-once.
                    send_password_reset_email(user.email, raw_token, message_id=str(job.id))
                except Exception:
                    job.attempts += 1
                    job.retry_at = now + timedelta(seconds=min(300, 5 * 2 ** min(job.attempts, 6)))
                    logger.warning("Reset mail delivery deferred (no recipient/credential details)")
                else:
                    job.completed_at = now
                    job.encrypted_token = None
                    delivered += 1
            db.commit()
    return delivered


def cleanup_expired_sessions(batch_size=100):
    # Keep replay/reset evidence for seven days AFTER expiry; no live token
    # or unexpired revoked credential is removed. SKIP LOCKED is PostgreSQL.
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    removed = 0
    with SessionLocal() as db:
        for model in (RefreshSession, RevokedSession, PasswordResetToken):
            ids = list(db.scalars(select(model.id).where(model.expires_at < cutoff)
                .order_by(model.expires_at).with_for_update(skip_locked=True).limit(min(batch_size, 500))))
            if ids:
                removed += db.execute(delete(model).where(model.id.in_(ids))).rowcount
        request_ids = list(db.scalars(select(ResetRequestOutbox.id).where(ResetRequestOutbox.expires_at < cutoff)
            .order_by(ResetRequestOutbox.expires_at).with_for_update(skip_locked=True).limit(min(batch_size, 500))))
        if request_ids:
            removed += db.execute(delete(ResetRequestOutbox).where(ResetRequestOutbox.id.in_(request_ids))).rowcount
        db.commit()
    return removed


async def maintenance_loop():
    ticks = 0
    while True:
        try:
            await asyncio.to_thread(process_reset_requests)
            await asyncio.to_thread(deliver_reset_mail)
            if ticks % 4 == 0:
                await asyncio.to_thread(cleanup_expired_sessions)
                from app.services.lesson_announcements import announce_available_lessons
                await asyncio.to_thread(announce_available_lessons)
        except Exception:
            logger.warning("Session maintenance temporarily unavailable")
        ticks += 1
        await asyncio.sleep(15)
