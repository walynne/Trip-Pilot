from datetime import date, datetime, timedelta
import re


WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def extract_weekday_range(message, today=None):
    if not isinstance(message, str):
        return None

    weekday = r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    patterns = (
        rf"\b(?:from\s+)?next\s+({weekday})\s+(?:to|through|until|[-\u2013])\s+(?:(?:next|this)\s+)?({weekday})\b",
        rf"\bnext\s+({weekday})\b.*?\b(?:return|come back|back)\s+(?:(?:on|next|this)\s+)?({weekday})\b",
    )
    match = next(
        (found for pattern in patterns if (found := re.search(pattern, message, re.IGNORECASE))),
        None,
    )
    if match is None:
        return None

    reference = today or date.today()
    start_weekday = WEEKDAYS[match.group(1).casefold()]
    end_weekday = WEEKDAYS[match.group(2).casefold()]
    days_until_start = (start_weekday - reference.weekday()) % 7
    if days_until_start == 0:
        days_until_start = 7
    start = reference + timedelta(days=days_until_start)
    days_to_end = (end_weekday - start_weekday) % 7
    if days_to_end == 0:
        days_to_end = 7
    end = start + timedelta(days=days_to_end)
    return start.isoformat(), end.isoformat()


def _safe_replace_year(value, target_year):

    try:
        return value.replace(year=target_year)
    except ValueError:
        if value.month == 2 and value.day == 29:
            return value.replace(year=target_year, day=28)
        raise


def normalize_departure_date(value):

    if not value:
        return value

    try:
        parsed = datetime.strptime(
            value,
            "%Y-%m-%d"
        ).date()
    except ValueError:
        return None

    today = date.today()

    if parsed > today:
        return parsed.isoformat()

    candidate = _safe_replace_year(
        parsed,
        today.year
    )

    if candidate <= today:
        candidate = _safe_replace_year(
            parsed,
            today.year + 1
        )

    return candidate.isoformat()


def normalize_return_date(value):

    return normalize_departure_date(
        value
    )


def ensure_future_departure_date(value):

    normalized = normalize_departure_date(value)

    if not normalized:
        raise ValueError(
            "departure_date must be a valid YYYY-MM-DD date"
        )

    parsed = datetime.strptime(
        normalized,
        "%Y-%m-%d"
    ).date()

    if parsed <= date.today():
        raise ValueError(
            "departure_date must be in the future"
        )

    return normalized


def ensure_valid_return_date(
    departure_date,
    return_date
):

    if not return_date:
        return None

    normalized_departure = ensure_future_departure_date(
        departure_date
    )

    normalized_return = ensure_future_departure_date(
        return_date
    )

    departure_parsed = datetime.strptime(
        normalized_departure,
        "%Y-%m-%d"
    ).date()

    return_parsed = datetime.strptime(
        normalized_return,
        "%Y-%m-%d"
    ).date()

    if return_parsed < departure_parsed:
        raise ValueError(
            "return_date must be on or after departure_date"
        )

    return normalized_return