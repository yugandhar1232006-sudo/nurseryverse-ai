"""
Unit tests for Module 12's Pydantic DTOs (app/schemas/reports.py):
`ReportFilters`'s date-range validation and `to_json_dict()` storage-shape
serialization, `DateRangeParams`/`get_date_range_params`'s inverted-range
rejection, and `ScheduledReportCreateRequest`/`ScheduledReportUpdateRequest`'s
past-`next_run_at` rejection. No fakes/harness needed -- pure schema-level
validation, exercised directly.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import ValidationError
from app.db.enums import ReportFormat, ReportScheduleFrequency, ReportType
from app.schemas.reports import (
    DateRangeParams,
    ReportFilters,
    ScheduledReportCreateRequest,
    ScheduledReportUpdateRequest,
    get_date_range_params,
)

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------
# ReportFilters
# --------------------------------------------------------------------------


def test_report_filters_defaults_to_all_none():
    filters = ReportFilters()
    assert filters.species_id is None
    assert filters.date_from is None
    assert filters.date_to is None
    assert filters.low_stock_only is False


def test_report_filters_accepts_equal_date_from_and_date_to():
    now = datetime.now(timezone.utc)
    filters = ReportFilters(date_from=now, date_to=now)
    assert filters.date_from == now


def test_report_filters_rejects_date_from_after_date_to():
    now = datetime.now(timezone.utc)
    with pytest.raises(PydanticValidationError, match="date_from must not be after date_to"):
        ReportFilters(date_from=now, date_to=now - timedelta(days=1))


def test_report_filters_to_json_dict_omits_unset_fields():
    filters = ReportFilters(species_id=uuid.uuid4())
    data = filters.to_json_dict()
    assert set(data.keys()) == {"species_id", "low_stock_only"}


def test_report_filters_to_json_dict_serializes_uuid_and_datetime_as_strings():
    species_id = uuid.uuid4()
    date_from = datetime(2026, 1, 1, tzinfo=timezone.utc)
    filters = ReportFilters(species_id=species_id, date_from=date_from)
    data = filters.to_json_dict()
    assert data["species_id"] == str(species_id)
    assert isinstance(data["species_id"], str)
    assert data["date_from"] == date_from.isoformat()
    assert isinstance(data["date_from"], str)


def test_report_filters_to_json_dict_roundtrips_through_report_generation_parsers():
    """`ReportGenerationService._parse_uuid`/`_parse_datetime` are the readers on the other end -- confirm the shape they expect is exactly what this produces."""
    from app.services.report_generation_service import _parse_datetime, _parse_uuid

    species_id = uuid.uuid4()
    date_from = datetime(2026, 3, 15, 12, 30, tzinfo=timezone.utc)
    data = ReportFilters(species_id=species_id, date_from=date_from).to_json_dict()
    assert _parse_uuid(data["species_id"]) == species_id
    assert _parse_datetime(data["date_from"]) == date_from


def test_report_filters_low_stock_only_survives_serialization_even_when_false_is_the_default():
    """`low_stock_only` is a `bool = False`, not `| None`, so `exclude_none` never drops it -- unlike every other field here, filters consumers can rely on it always being present."""
    data = ReportFilters().to_json_dict()
    assert data["low_stock_only"] is False


# --------------------------------------------------------------------------
# DateRangeParams / get_date_range_params
# --------------------------------------------------------------------------


def test_date_range_params_accepts_none_bounds():
    params = DateRangeParams()
    assert params.date_from is None
    assert params.date_to is None


def test_date_range_params_rejects_inverted_range():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        DateRangeParams(date_from=now, date_to=now - timedelta(days=1))


def test_get_date_range_params_factory_matches_class_behavior():
    now = datetime.now(timezone.utc)
    params = get_date_range_params(date_from=now - timedelta(days=1), date_to=now)
    assert params.date_from == now - timedelta(days=1)
    assert params.date_to == now
    with pytest.raises(ValidationError):
        get_date_range_params(date_from=now, date_to=now - timedelta(days=1))


# --------------------------------------------------------------------------
# ScheduledReportCreateRequest
# --------------------------------------------------------------------------


def _create_request(**overrides) -> dict:
    base = dict(
        name="Weekly Sales",
        report_type=ReportType.SALES,
        format=ReportFormat.CSV,
        frequency=ReportScheduleFrequency.WEEKLY,
        next_run_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    base.update(overrides)
    return base


def test_scheduled_report_create_request_accepts_future_next_run_at():
    request = ScheduledReportCreateRequest(**_create_request())
    assert request.frequency == ReportScheduleFrequency.WEEKLY


def test_scheduled_report_create_request_rejects_past_next_run_at():
    with pytest.raises(PydanticValidationError, match="next_run_at must not be in the past"):
        ScheduledReportCreateRequest(**_create_request(next_run_at=datetime.now(timezone.utc) - timedelta(days=1)))


def test_scheduled_report_create_request_rejects_blank_name():
    with pytest.raises(PydanticValidationError):
        ScheduledReportCreateRequest(**_create_request(name=""))


def test_scheduled_report_create_request_treats_naive_next_run_at_as_utc():
    """A naive `next_run_at` one hour in the future (interpreted as UTC) must pass; the validator's own `.replace(tzinfo=timezone.utc)` fallback is what's under test here, not timezone-aware inputs."""
    naive_future = datetime.utcnow() + timedelta(hours=1)
    request = ScheduledReportCreateRequest(**_create_request(next_run_at=naive_future))
    assert request.next_run_at == naive_future


def test_scheduled_report_create_request_default_filters_is_empty_report_filters():
    request = ScheduledReportCreateRequest(**_create_request())
    assert request.filters == ReportFilters()
    assert request.branch_id is None


# --------------------------------------------------------------------------
# ScheduledReportUpdateRequest
# --------------------------------------------------------------------------


def test_scheduled_report_update_request_all_fields_optional():
    request = ScheduledReportUpdateRequest()
    assert request.name is None
    assert request.filters is None
    assert request.frequency is None
    assert request.next_run_at is None


def test_scheduled_report_update_request_skips_validation_when_next_run_at_unset():
    # Must not raise even though nothing else is supplied.
    request = ScheduledReportUpdateRequest(name="Renamed")
    assert request.name == "Renamed"


def test_scheduled_report_update_request_rejects_past_next_run_at():
    with pytest.raises(PydanticValidationError, match="next_run_at must not be in the past"):
        ScheduledReportUpdateRequest(next_run_at=datetime.now(timezone.utc) - timedelta(days=1))


def test_scheduled_report_update_request_accepts_future_next_run_at():
    future = datetime.now(timezone.utc) + timedelta(days=2)
    request = ScheduledReportUpdateRequest(next_run_at=future)
    assert request.next_run_at == future


def test_scheduled_report_update_request_rejects_blank_name_when_supplied():
    with pytest.raises(PydanticValidationError):
        ScheduledReportUpdateRequest(name="")
