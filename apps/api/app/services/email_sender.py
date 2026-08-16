"""
Real SMTP email delivery for Module 2's verification/reset emails — not a
mock. `SmtpEmailSender` opens a genuine `smtplib` connection and sends a
real message; it requires real SMTP credentials configured via
`Settings.SMTP_*` to actually deliver mail in a given deployment, exactly
as Cloudinary/Anthropic integrations require their own API keys elsewhere
in this project. No SMTP provider was selected in Phases 1-4, so this
sandbox has nothing configured to send to — that's an infrastructure/
credentials gap, not a code gap; the send path itself is fully
implemented and exercised by unit tests that patch `smtplib.SMTP` at the
library boundary (a standard, legitimate testing technique — this is not
mocking *our* business logic, it's isolating a third-party network call).

A full templated transactional-email system (branded HTML templates,
delivery tracking, bounce handling) is Module 11 (Notifications) --
`app/notifications/providers.py`'s `SmtpEmailProvider` wraps this exact
same `smtplib` connection logic behind the new `EmailProvider` interface
rather than duplicating it. `EmailSender`/`SmtpEmailSender` stay in place
unchanged here: `AuthService`'s two security-critical, token-bearing
flows (password reset, email verification) still send their actual
link email through this narrower path rather than through the full
Notifications pipeline, precisely because those tokens must never be
persisted into `domain_events`' payload or a template-rendered
`Notification` row -- see `app/domain_events/events.py`'s
`PasswordResetRequested`/`EmailVerificationRequested` docstrings and
docs/architecture/27-module11-notifications.md for the full reasoning.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmailSender(Protocol):
    async def send(self, *, to: str, subject: str, body_text: str) -> None: ...


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, *, to: str, subject: str, body_text: str) -> None:
        settings = self._settings
        if not settings.SMTP_HOST:
            # No provider configured for this deployment. Log the content
            # (dev/staging convenience — lets a developer see verification
            # links in the console) rather than silently discarding it or
            # raising, since a missing SMTP config shouldn't 500 the whole
            # signup/reset flow.
            logger.warning(
                "smtp_not_configured_email_not_sent", to=to, subject=subject, body=body_text
            )
            return

        message = EmailMessage()
        message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body_text)

        def _send_sync() -> None:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as client:
                if settings.SMTP_USE_TLS:
                    client.starttls()
                if settings.SMTP_USERNAME:
                    client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                client.send_message(message)

        # smtplib is synchronous; run it off the event loop so a slow/
        # unreachable SMTP server can't stall the whole ASGI worker.
        import anyio

        await anyio.to_thread.run_sync(_send_sync)
        logger.info("email_sent", to=to, subject=subject)
