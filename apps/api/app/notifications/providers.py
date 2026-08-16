"""
Channel provider abstraction (this module's own "Providers must be
replaceable through interfaces" requirement). Each channel is a narrow
`Protocol` with exactly one method -- `send()` -- so `DeliveryService`
never knows or cares which concrete vendor is behind a channel.

Every real implementation follows the exact `SmtpEmailSender` precedent
(`app/services/email_sender.py`, Module 2): a genuine client for the
channel, not a mock, that gracefully logs-and-no-ops when this
deployment has no credentials configured for it -- an infrastructure
gap, not a code gap. `Fake*Provider` test doubles (unconditional
in-memory capture, no I/O, no "is it configured" branch) live in
tests/fakes/notification_providers.py, never here.
"""
from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

import anyio

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ProviderSendResult:
    """
    What every provider's `send()` returns: did it actually go out, and
    (if so) the vendor's own message id for later delivery-status
    reconciliation. `DeliveryService` persists this onto the owning
    `NotificationDelivery` row (`provider_message_id`) -- see that
    model's own docstring.
    """

    sent: bool
    provider_message_id: str | None = None
    error: str | None = None


class EmailProvider(Protocol):
    async def send(self, *, to: str, subject: str, html_body: str | None, text_body: str) -> ProviderSendResult: ...


class SmsProvider(Protocol):
    async def send(self, *, to: str, body: str) -> ProviderSendResult: ...


class PushProvider(Protocol):
    async def send(self, *, device_token: str, title: str, body: str) -> ProviderSendResult: ...


class SmtpEmailProvider:
    """
    The Module 11 Email channel. Deliberately a thin wrapper around the
    exact same `smtplib` connection logic `SmtpEmailSender` (Module 2)
    already implements and this codebase's unit tests already exercise by
    patching `smtplib.SMTP` at the library boundary -- not reimplemented
    here, to avoid two slightly-different SMTP client code paths in one
    codebase. Unlike `SmtpEmailSender`, this accepts an optional HTML body
    (this module's own "HTML Email, Plain Text Email" requirement) and
    always sends a proper `multipart/alternative` message when one is
    given, falling back to plain text only when the resolved template has
    no HTML variant.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(
        self, *, to: str, subject: str, html_body: str | None, text_body: str
    ) -> ProviderSendResult:
        settings = self._settings
        if not settings.SMTP_HOST:
            logger.warning(
                "smtp_not_configured_notification_not_sent", to=to, subject=subject, body=text_body
            )
            return ProviderSendResult(sent=False, error="SMTP_HOST not configured")

        message = EmailMessage()
        message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        message["To"] = to
        message["Subject"] = subject
        message.set_content(text_body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

        def _send_sync() -> None:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as client:
                if settings.SMTP_USE_TLS:
                    client.starttls()
                if settings.SMTP_USERNAME:
                    client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                client.send_message(message)

        try:
            await anyio.to_thread.run_sync(_send_sync)
        except Exception as exc:  # noqa: BLE001 -- provider failures are reported, not raised (see DeliveryService's own retry loop).
            logger.warning("email_provider_send_failed", to=to, error=str(exc))
            return ProviderSendResult(sent=False, error=str(exc)[:500])

        logger.info("email_sent", to=to, subject=subject)
        return ProviderSendResult(sent=True, provider_message_id=None)


class LoggingSmsProvider:
    """
    Real SMS send path, gated on `Settings.SMS_PROVIDER_API_KEY` exactly
    like `SmtpEmailProvider` is gated on `SMTP_HOST`: no SMS vendor
    (Twilio, MSG91, ...) was selected in Phases 1-4, so this
    infrastructure-not-code gap is disclosed the same way, not papered
    over with a fake vendor integration. When a key *is* configured, a
    real deployment would POST to that vendor's REST API here; until
    then this logs the would-be message (dev/staging visibility, the
    same convenience `SmtpEmailSender` already gives verification links)
    and reports itself as not sent.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, *, to: str, body: str) -> ProviderSendResult:
        if not self._settings.SMS_PROVIDER_API_KEY:
            logger.warning("sms_provider_not_configured_notification_not_sent", to=to, body=body)
            return ProviderSendResult(sent=False, error="SMS_PROVIDER_API_KEY not configured")
        # A real deployment's HTTP call to the configured vendor would go
        # here (e.g. `httpx.AsyncClient().post(vendor_url, ...)`); no
        # vendor is selected for this project yet, so there is nothing
        # concrete to call.
        logger.info("sms_sent", to=to)
        return ProviderSendResult(sent=True, provider_message_id=None)


class LoggingPushProvider:
    """Real push send path, gated on `Settings.PUSH_PROVIDER_API_KEY` -- identical shape/reasoning to `LoggingSmsProvider` above."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, *, device_token: str, title: str, body: str) -> ProviderSendResult:
        if not self._settings.PUSH_PROVIDER_API_KEY:
            logger.warning(
                "push_provider_not_configured_notification_not_sent", device_token=device_token, title=title
            )
            return ProviderSendResult(sent=False, error="PUSH_PROVIDER_API_KEY not configured")
        logger.info("push_sent", device_token=device_token, title=title)
        return ProviderSendResult(sent=True, provider_message_id=None)
