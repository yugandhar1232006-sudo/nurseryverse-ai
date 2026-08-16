"""
Versioned, multi-channel/format template rendering (this module's own
"Implement versioned templates... HTML Email, Plain Text Email, SMS,
Push, In-App" / "must support localization in the future" requirements).

Resolution order, most-specific first (`TemplateService.render` below):
  1. The org's own active override row (`notification_templates.nursery_id
     = <org>`), highest `version`.
  2. The platform's global default row (`nursery_id IS NULL`), highest
     `version`.
  3. This module's in-code `DEFAULT_TEMPLATES` registry.

Step 3 exists so the system is fully functional the moment this module
ships, with zero required admin seeding step -- the exact same reasoning
`app/ai/survival_prediction/inference.py`'s `_SEVERITY_RISK` table (a
versioned-with-the-code constant, not a DB row) already established for
this codebase: a *baseline* is application code, not editable business
data; only an org's deliberate customization belongs in the database.
Steps 1-2 are real, fully-functional DB-backed rows an Org Admin can
create today via `POST /notifications/templates` -- this is genuine
three-tier resolution, not a fallback masking an unfinished feature.

Rendering is real Jinja2 (`jinja2==3.0.3`, already a transitive
dependency of this project, now declared explicitly in
requirements/base.txt), `autoescape=True` for HTML/text email bodies so a
template variable containing user-authored text (a plant's `common_label`,
a customer's `full_name`, ...) can never break out of the rendered markup
-- the same XSS-prevention default any production email system requires.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import jinja2

from app.db.enums import NotificationCategory, NotificationChannel
from app.repositories.interfaces import NotificationTemplateRepository

_ENV = jinja2.Environment(autoescape=True, undefined=jinja2.StrictUndefined)


@dataclass(frozen=True)
class RenderedTemplate:
    subject: str | None
    body: str


@dataclass(frozen=True)
class _TemplateSource:
    subject_template: str | None
    body_template: str


# Platform baseline defaults. Keyed by (category, channel, format).
# "text" is the only format for every non-email channel (see
# NotificationTemplate's own docstring on why the column still exists
# uniformly); email additionally has "html". Every category this module's
# EVENTS section requires has at least an in_app/text entry -- the
# minimum every category needs, since in-app is this module's "always
# created first, regardless of channel preferences" channel (Notification
# model's own docstring).
DEFAULT_TEMPLATES: dict[tuple[NotificationCategory, NotificationChannel, str], _TemplateSource] = {}


def _register(
    category: NotificationCategory,
    channel: NotificationChannel,
    fmt: str,
    *,
    subject: str | None,
    body: str,
) -> None:
    DEFAULT_TEMPLATES[(category, channel, fmt)] = _TemplateSource(subject_template=subject, body_template=body)


# --- In-app (text) — every category gets one; this is the channel every Notification row always has. ---
_register(NotificationCategory.EMPLOYEE_INVITE, NotificationChannel.IN_APP, "text", subject=None, body="{{ email }} was invited to join as {{ role_code }}.")
_register(NotificationCategory.PASSWORD_RESET, NotificationChannel.IN_APP, "text", subject=None, body="A password reset was requested for your account.")
_register(NotificationCategory.EMAIL_VERIFICATION, NotificationChannel.IN_APP, "text", subject=None, body="A verification email was sent to your address.")
_register(NotificationCategory.PLANT_REGISTERED, NotificationChannel.IN_APP, "text", subject=None, body="New plant {{ common_label }} registered at {{ branch_name }}.")
_register(NotificationCategory.PLANT_READY_FOR_SALE, NotificationChannel.IN_APP, "text", subject=None, body="{{ common_label }} is now ready for sale.")
_register(NotificationCategory.DISEASE_CONFIRMED, NotificationChannel.IN_APP, "text", subject=None, body="Disease detected on {{ common_label }}: {{ condition_name }} ({{ severity }}).")
_register(NotificationCategory.PLANT_UNDER_TREATMENT, NotificationChannel.IN_APP, "text", subject=None, body="{{ common_label }} has started treatment.")
_register(NotificationCategory.PLANT_SOLD, NotificationChannel.IN_APP, "text", subject=None, body="{{ common_label }} was sold for {{ unit_price }}.")
_register(NotificationCategory.RESERVATION_CREATED, NotificationChannel.IN_APP, "text", subject=None, body="A stock reservation was created for order item {{ order_item_id }}.")
_register(NotificationCategory.RESERVATION_EXPIRING, NotificationChannel.IN_APP, "text", subject=None, body="A reservation is expiring in {{ minutes_remaining }} minutes.")
_register(NotificationCategory.INVOICE_GENERATED, NotificationChannel.IN_APP, "text", subject=None, body="Invoice generated for {{ total_amount }}.")
_register(NotificationCategory.PAYMENT_RECEIVED, NotificationChannel.IN_APP, "text", subject=None, body="Payment of {{ amount }} received via {{ method }}.")
_register(NotificationCategory.LOW_STOCK, NotificationChannel.IN_APP, "text", subject=None, body="{{ product_name }} is low on stock ({{ quantity_available }} remaining, threshold {{ threshold }}).")
_register(NotificationCategory.INVENTORY_TRANSFER, NotificationChannel.IN_APP, "text", subject=None, body="{{ quantity }} units transferred between locations.")
_register(NotificationCategory.SYSTEM_ALERT, NotificationChannel.IN_APP, "text", subject=None, body="{{ title }}: {{ message }}")
_register(NotificationCategory.AI_RECOMMENDATION_READY, NotificationChannel.IN_APP, "text", subject=None, body="A new {{ priority }}-priority AI recommendation is ready for review.")
_register(NotificationCategory.AI_PREDICTION_READY, NotificationChannel.IN_APP, "text", subject=None, body="A new {{ prediction_type }} prediction is ready ({{ confidence }} confidence).")
_register(NotificationCategory.PLANT_TRANSFERRED, NotificationChannel.IN_APP, "text", subject=None, body="{{ common_label }} was moved to a new branch.")
_register(NotificationCategory.PURCHASE_ORDER_RECEIVED, NotificationChannel.IN_APP, "text", subject=None, body="Purchase order stock received ({{ quantity }} units).")
_register(NotificationCategory.WATERING_OVERDUE, NotificationChannel.IN_APP, "text", subject=None, body="{{ common_label }} is overdue for watering.")
_register(NotificationCategory.INVOICE_OVERDUE, NotificationChannel.IN_APP, "text", subject=None, body="Invoice for {{ total_amount }} is now overdue.")
# --- Added by Phase 6 Module 12 (Reports & Analytics) ---
_register(
    NotificationCategory.REPORT_READY, NotificationChannel.IN_APP, "text", subject=None,
    body="{% if file_url %}Your {{ report_type }} report is ready to download.{% else %}Your {{ report_type }} report failed to generate: {{ error_message }}{% endif %}",
)

# --- Email (html + text) — the categories this module's own default channel table (docs/ux/14) marks as email-eligible. ---
for _cat, _subject, _html, _text in (
    (
        NotificationCategory.PLANT_SOLD,
        "A plant sold at your nursery",
        "<p>{{ common_label }} was sold for <strong>{{ unit_price }}</strong>.</p>",
        "{{ common_label }} was sold for {{ unit_price }}.",
    ),
    (
        NotificationCategory.INVOICE_GENERATED,
        "New invoice generated",
        "<p>Invoice generated for <strong>{{ total_amount }}</strong>.</p>",
        "Invoice generated for {{ total_amount }}.",
    ),
    (
        NotificationCategory.PAYMENT_RECEIVED,
        "Payment received",
        "<p>Payment of <strong>{{ amount }}</strong> received via {{ method }}.</p>",
        "Payment of {{ amount }} received via {{ method }}.",
    ),
    (
        NotificationCategory.DISEASE_CONFIRMED,
        "Disease detected on your plant",
        "<p>Disease detected on {{ common_label }}: <strong>{{ condition_name }}</strong> ({{ severity }}).</p>",
        "Disease detected on {{ common_label }}: {{ condition_name }} ({{ severity }}).",
    ),
    (
        NotificationCategory.LOW_STOCK,
        "Low stock alert",
        "<p>{{ product_name }} is low on stock — {{ quantity_available }} remaining (threshold {{ threshold }}).</p>",
        "{{ product_name }} is low on stock ({{ quantity_available }} remaining, threshold {{ threshold }}).",
    ),
    (
        NotificationCategory.SYSTEM_ALERT,
        "{{ title }}",
        "<p>{{ message }}</p>",
        "{{ message }}",
    ),
    (
        NotificationCategory.AI_RECOMMENDATION_READY,
        "New AI recommendation ready",
        "<p>A new <strong>{{ priority }}</strong>-priority AI recommendation is ready for review.</p>",
        "A new {{ priority }}-priority AI recommendation is ready for review.",
    ),
):
    _register(_cat, NotificationChannel.EMAIL, "html", subject=_subject, body=_html)
    _register(_cat, NotificationChannel.EMAIL, "text", subject=_subject, body=_text)

# --- SMS (text) — high-severity/time-sensitive categories only, per docs/ux/14's "SMS gated by org+user opt-in" rule. ---
_register(NotificationCategory.DISEASE_CONFIRMED, NotificationChannel.SMS, "text", subject=None, body="Alert: disease detected on {{ common_label }} ({{ severity }}).")
_register(NotificationCategory.LOW_STOCK, NotificationChannel.SMS, "text", subject=None, body="Low stock: {{ product_name }} ({{ quantity_available }} left).")
_register(NotificationCategory.SYSTEM_ALERT, NotificationChannel.SMS, "text", subject=None, body="{{ title }}: {{ message }}")
_register(NotificationCategory.RESERVATION_EXPIRING, NotificationChannel.SMS, "text", subject=None, body="Reservation expiring in {{ minutes_remaining }} min.")

# --- Push (text) — mirrors the SMS set, the module's other "opt-in, urgent-only" channel. ---
_register(NotificationCategory.DISEASE_CONFIRMED, NotificationChannel.PUSH, "text", subject="Disease detected", body="{{ common_label }}: {{ condition_name }} ({{ severity }}).")
_register(NotificationCategory.LOW_STOCK, NotificationChannel.PUSH, "text", subject="Low stock", body="{{ product_name }} — {{ quantity_available }} remaining.")
_register(NotificationCategory.SYSTEM_ALERT, NotificationChannel.PUSH, "text", subject="{{ title }}", body="{{ message }}")
_register(NotificationCategory.AI_RECOMMENDATION_READY, NotificationChannel.PUSH, "text", subject="New recommendation", body="A new {{ priority }}-priority recommendation is ready.")


class TemplateNotFoundError(Exception):
    """No org override, no global default row, and no in-code baseline exists for this (category, channel, format, locale)."""


class TemplateService:
    def __init__(self, template_repo: NotificationTemplateRepository) -> None:
        self._templates = template_repo

    async def render(
        self,
        *,
        nursery_id: uuid.UUID,
        category: NotificationCategory,
        channel: NotificationChannel,
        format: str = "text",
        locale: str = "en",
        context: dict,
    ) -> RenderedTemplate:
        source = await self._resolve(
            nursery_id=nursery_id, category=category, channel=channel, format=format, locale=locale
        )
        body = _ENV.from_string(source.body_template).render(**context)
        subject = _ENV.from_string(source.subject_template).render(**context) if source.subject_template else None
        return RenderedTemplate(subject=subject, body=body)

    async def _resolve(
        self,
        *,
        nursery_id: uuid.UUID,
        category: NotificationCategory,
        channel: NotificationChannel,
        format: str,
        locale: str,
    ) -> _TemplateSource:
        org_row = await self._templates.get_active(
            nursery_id=nursery_id, category=category, channel=channel, format=format, locale=locale
        )
        if org_row is not None:
            return _TemplateSource(subject_template=org_row.subject_template, body_template=org_row.body_template)

        global_row = await self._templates.get_active(
            nursery_id=None, category=category, channel=channel, format=format, locale=locale
        )
        if global_row is not None:
            return _TemplateSource(subject_template=global_row.subject_template, body_template=global_row.body_template)

        default = DEFAULT_TEMPLATES.get((category, channel, format))
        if default is not None:
            return default

        # Locale/format fall back to the canonical "en"/"text" baseline
        # before giving up entirely -- a locale this module hasn't been
        # translated into yet (its own "must support localization in the
        # future" requirement -- no non-English templates ship today)
        # must still render *something* rather than fail the whole
        # notification.
        if locale != "en":
            return await self._resolve(
                nursery_id=nursery_id, category=category, channel=channel, format=format, locale="en"
            )
        if format != "text":
            return await self._resolve(
                nursery_id=nursery_id, category=category, channel=channel, format="text", locale=locale
            )
        raise TemplateNotFoundError(f"No template for {category}/{channel}/{format}/{locale}")
