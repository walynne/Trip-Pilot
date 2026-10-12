from datetime import date, datetime


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