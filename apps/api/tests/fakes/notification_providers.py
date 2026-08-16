"""
Fake channel providers for Module 11 (Notifications) tests -- unconditional
in-memory capture, no I/O, no "is this deployment configured" branch (that
branch belongs to the real `SmtpEmailProvider`/`LoggingSmsProvider`/
`LoggingPushProvider` in app/notifications/providers.py; a fake never
needs it since there's no real vendor behind it to be unconfigured).

`should_fail` lets a test force a delivery failure on demand (retry/DLQ
tests need a provider that fails N times then succeeds, or fails forever)
without monkeypatching or mocking library internals.
"""
from __future__ import annotations

from app.notifications.providers import ProviderSendResult


class FakeEmailProvider:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.sent: list[dict] = []

    async def send(self, *, to: str, subject: str, html_body: str | None, text_body: str) -> ProviderSendResult:
        if self.should_fail:
            return ProviderSendResult(sent=False, error="Simulated email provider failure")
        self.sent.append({"to": to, "subject": subject, "html_body": html_body, "text_body": text_body})
        return ProviderSendResult(sent=True, provider_message_id=f"fake-email-{len(self.sent)}")


class FakeSmsProvider:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.sent: list[dict] = []

    async def send(self, *, to: str, body: str) -> ProviderSendResult:
        if self.should_fail:
            return ProviderSendResult(sent=False, error="Simulated SMS provider failure")
        self.sent.append({"to": to, "body": body})
        return ProviderSendResult(sent=True, provider_message_id=f"fake-sms-{len(self.sent)}")


class FakePushProvider:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.sent: list[dict] = []

    async def send(self, *, device_token: str, title: str, body: str) -> ProviderSendResult:
        if self.should_fail:
            return ProviderSendResult(sent=False, error="Simulated push provider failure")
        self.sent.append({"device_token": device_token, "title": title, "body": body})
        return ProviderSendResult(sent=True, provider_message_id=f"fake-push-{len(self.sent)}")
