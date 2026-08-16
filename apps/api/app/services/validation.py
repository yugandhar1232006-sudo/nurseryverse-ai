"""
Shared, real (not placeholder) validation helpers -- timezone validation
against Python's actual IANA tzdata (`zoneinfo`), not a hand-maintained
allowlist; ISO 4217-shaped currency code checking; and operating-hours
JSON-shape validation (Module 4), plus Module 5's growth-curve-baseline
and disease-susceptibility JSON-shape validation. Shared across modules
because `BranchService`/`OrganizationService`/`SpeciesService` each need
some of this (a Branch's own timezone, an Org's default via `OrgSettings`,
a Species' structured JSON fields), and duplicating the same
regex/zoneinfo/JSON-shape logic per service module would be exactly the
"duplicated business logic" the project's quality bar rules out.
"""
from __future__ import annotations

import re
import zoneinfo

from app.core.exceptions import ValidationError

_VALID_TIMEZONES = zoneinfo.available_timezones()
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_OPERATING_HOURS_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def validate_timezone(value: str) -> str:
    if value not in _VALID_TIMEZONES:
        raise ValidationError(f"'{value}' is not a recognized IANA timezone name.")
    return value


def validate_currency_code(value: str) -> str:
    normalized = value.strip().upper()
    if not _CURRENCY_RE.match(normalized):
        raise ValidationError(f"'{value}' is not a valid 3-letter ISO 4217 currency code.")
    return normalized


def validate_country_code(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) != 2 or not normalized.isalpha():
        raise ValidationError(f"'{value}' is not a valid 2-letter ISO 3166-1 country code.")
    return normalized


def validate_hex_color(value: str) -> str:
    if not _HEX_COLOR_RE.match(value):
        raise ValidationError(f"'{value}' is not a valid hex color (expected format '#RRGGBB').")
    return value


def validate_operating_hours(hours: dict | None) -> dict | None:
    """
    `hours` is `{"mon": {"open": "09:00", "close": "17:00"}, ..., "sun":
    None}` -- an absent or null day means closed that day. Every present
    key must be a recognized weekday abbreviation, every non-null value
    must have exactly `open`/`close` in 24-hour `HH:MM` format with
    `open < close`.
    """
    if hours is None:
        return None
    if not isinstance(hours, dict):
        raise ValidationError("operating_hours must be an object keyed by weekday (mon..sun).")

    unknown_days = set(hours) - set(_OPERATING_HOURS_DAYS)
    if unknown_days:
        raise ValidationError(f"Unknown day key(s) in operating_hours: {sorted(unknown_days)}.")

    for day, window in hours.items():
        if window is None:
            continue
        if not isinstance(window, dict) or set(window) != {"open", "close"}:
            raise ValidationError(
                f"operating_hours['{day}'] must be an object with exactly 'open' and 'close', or null."
            )
        open_time, close_time = window["open"], window["close"]
        if not (isinstance(open_time, str) and _TIME_RE.match(open_time)):
            raise ValidationError(f"operating_hours['{day}']['open'] must be 24-hour 'HH:MM'.")
        if not (isinstance(close_time, str) and _TIME_RE.match(close_time)):
            raise ValidationError(f"operating_hours['{day}']['close'] must be 24-hour 'HH:MM'.")
        if open_time >= close_time:
            raise ValidationError(f"operating_hours['{day}']: 'open' must be before 'close'.")

    return hours


def validate_growth_curve_baseline(value: list | None) -> list | None:
    """
    `value` is `[{"days_since_planting": int, "expected_height_cm": number}, ...]`
    (Species.growth_curve_baseline, docs/architecture/06-ai-architecture.md
    §4's growth-prediction fallback baseline). Each point must be
    non-negative on both axes -- a negative day offset or height is never
    meaningful data, only a caller bug.
    """
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValidationError("growth_curve_baseline must be a list of {days_since_planting, expected_height_cm} points.")

    for i, point in enumerate(value):
        if not isinstance(point, dict) or set(point) != {"days_since_planting", "expected_height_cm"}:
            raise ValidationError(
                f"growth_curve_baseline[{i}] must be an object with exactly 'days_since_planting' and 'expected_height_cm'."
            )
        days, height = point["days_since_planting"], point["expected_height_cm"]
        if not isinstance(days, int) or isinstance(days, bool) or days < 0:
            raise ValidationError(f"growth_curve_baseline[{i}]['days_since_planting'] must be a non-negative integer.")
        if not isinstance(height, (int, float)) or isinstance(height, bool) or height < 0:
            raise ValidationError(f"growth_curve_baseline[{i}]['expected_height_cm'] must be a non-negative number.")

    return value


def validate_disease_susceptibility(value: list | None) -> list | None:
    """`value` is a flat list of disease-code strings, e.g. ["root_rot", "powdery_mildew"] -- feeds Disease Detection's confidence-threshold adjustment."""
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise ValidationError("disease_susceptibility must be a list of non-empty strings.")
    return [v.strip() for v in value]
