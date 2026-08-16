"""
Template Tests (Module 11's own required category) -- `TemplateService`'s
three-tier resolution (org override > global default > in-code baseline),
Jinja2 rendering, autoescape, and locale/format fallback.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.enums import NotificationCategory, NotificationChannel
from app.models.notifications import NotificationTemplate
from app.notifications.templates import TemplateNotFoundError, TemplateService

pytestmark = pytest.mark.unit


async def test_renders_in_code_baseline_when_no_db_row_exists(harness):
    org_id = uuid.uuid4()
    rendered = await harness.template_service.render(
        nursery_id=org_id, category=NotificationCategory.PLANT_SOLD, channel=NotificationChannel.IN_APP,
        context={"common_label": "Fiddle Leaf Fig", "unit_price": "45.00"},
    )
    assert rendered.body == "Fiddle Leaf Fig was sold for 45.00."
    assert rendered.subject is None


async def test_org_override_takes_precedence_over_global_default(harness):
    org_id = uuid.uuid4()
    global_template = NotificationTemplate(
        nursery_id=None, category=NotificationCategory.PLANT_REGISTERED, channel=NotificationChannel.IN_APP,
        format="text", locale="en", version=1, subject_template=None,
        body_template="GLOBAL: {{ common_label }}", is_active=True,
    )
    await harness.notification_templates.add(global_template)
    org_template = NotificationTemplate(
        nursery_id=org_id, category=NotificationCategory.PLANT_REGISTERED, channel=NotificationChannel.IN_APP,
        format="text", locale="en", version=1, subject_template=None,
        body_template="ORG OVERRIDE: {{ common_label }}", is_active=True,
    )
    await harness.notification_templates.add(org_template)

    rendered = await harness.template_service.render(
        nursery_id=org_id, category=NotificationCategory.PLANT_REGISTERED, channel=NotificationChannel.IN_APP,
        context={"common_label": "Monstera"},
    )
    assert rendered.body == "ORG OVERRIDE: Monstera"

    # A different org with no override of its own still sees the global default.
    other_org = uuid.uuid4()
    rendered_other = await harness.template_service.render(
        nursery_id=other_org, category=NotificationCategory.PLANT_REGISTERED, channel=NotificationChannel.IN_APP,
        context={"common_label": "Monstera"},
    )
    assert rendered_other.body == "GLOBAL: Monstera"


async def test_highest_version_wins(harness):
    org_id = uuid.uuid4()
    await harness.notification_templates.add(
        NotificationTemplate(
            nursery_id=org_id, category=NotificationCategory.SYSTEM_ALERT, channel=NotificationChannel.IN_APP,
            format="text", locale="en", version=1, subject_template=None, body_template="v1: {{ message }}", is_active=True,
        )
    )
    await harness.notification_templates.add(
        NotificationTemplate(
            nursery_id=org_id, category=NotificationCategory.SYSTEM_ALERT, channel=NotificationChannel.IN_APP,
            format="text", locale="en", version=2, subject_template=None, body_template="v2: {{ message }}", is_active=True,
        )
    )
    rendered = await harness.template_service.render(
        nursery_id=org_id, category=NotificationCategory.SYSTEM_ALERT, channel=NotificationChannel.IN_APP,
        context={"message": "Irrigation offline"},
    )
    assert rendered.body == "v2: Irrigation offline"


async def test_inactive_template_is_not_selected(harness):
    org_id = uuid.uuid4()
    await harness.notification_templates.add(
        NotificationTemplate(
            nursery_id=org_id, category=NotificationCategory.SYSTEM_ALERT, channel=NotificationChannel.IN_APP,
            format="text", locale="en", version=2, subject_template=None, body_template="INACTIVE v2", is_active=False,
        )
    )
    rendered = await harness.template_service.render(
        nursery_id=org_id, category=NotificationCategory.SYSTEM_ALERT, channel=NotificationChannel.IN_APP,
        context={"title": "Alert", "message": "Test"},
    )
    # Falls through to the in-code baseline since the only DB row is inactive.
    assert rendered.body == "Alert: Test"


async def test_html_format_falls_back_to_text_when_only_a_text_row_exists(harness):
    org_id = uuid.uuid4()
    # RESERVATION_CREATED has no in-code EMAIL baseline of either format --
    # only a global text override exists, seeded directly here.
    await harness.notification_templates.add(
        NotificationTemplate(
            nursery_id=None, category=NotificationCategory.RESERVATION_CREATED, channel=NotificationChannel.EMAIL,
            format="text", locale="en", version=1, subject_template="Reservation created",
            body_template="Reservation for {{ quantity }} units created.", is_active=True,
        )
    )
    rendered = await harness.template_service.render(
        nursery_id=org_id, category=NotificationCategory.RESERVATION_CREATED, channel=NotificationChannel.EMAIL,
        format="html", context={"quantity": 5},
    )
    assert rendered.body == "Reservation for 5 units created."
    assert rendered.subject == "Reservation created"


async def test_unknown_locale_falls_back_to_english(harness):
    org_id = uuid.uuid4()
    rendered = await harness.template_service.render(
        nursery_id=org_id, category=NotificationCategory.PLANT_SOLD, channel=NotificationChannel.IN_APP,
        locale="fr", context={"common_label": "Rose", "unit_price": "10.00"},
    )
    assert rendered.body == "Rose was sold for 10.00."


async def test_autoescape_prevents_html_injection_in_html_email(harness):
    org_id = uuid.uuid4()
    rendered = await harness.template_service.render(
        nursery_id=org_id, category=NotificationCategory.DISEASE_CONFIRMED, channel=NotificationChannel.EMAIL,
        format="html",
        context={"common_label": "<script>alert(1)</script>", "condition_name": "Root Rot", "severity": "high"},
    )
    assert "<script>" not in rendered.body
    assert "&lt;script&gt;" in rendered.body


async def test_raises_when_absolutely_no_template_exists(harness):
    org_id = uuid.uuid4()
    service = TemplateService(harness.notification_templates)
    with pytest.raises(TemplateNotFoundError):
        await service.render(
            nursery_id=org_id, category=NotificationCategory.WATERING_OVERDUE, channel=NotificationChannel.PUSH,
            format="text", context={},
        )
