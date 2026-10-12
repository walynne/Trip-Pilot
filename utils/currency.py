import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


DEFAULT_TARGET_CURRENCY = os.getenv(
    "DISPLAY_CURRENCY",
    "HKD"
).upper()


EXCHANGE_RATES_TO_HKD = {
    "HKD": Decimal("1"),
    "AUD": Decimal("5.10"),
    "USD": Decimal("7.80"),
    "EUR": Decimal("8.60"),
    "GBP": Decimal("10.10"),
    "JPY": Decimal("0.052")
}


def convert_amount(
    amount,
    from_currency,
    to_currency=DEFAULT_TARGET_CURRENCY
):

    if amount is None:
        return None, from_currency

    from_currency = (from_currency or "").upper()
    to_currency = (to_currency or DEFAULT_TARGET_CURRENCY).upper()

    try:
        parsed_amount = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        return amount, from_currency

    if from_currency == to_currency:
        converted = parsed_amount
    elif to_currency == "HKD" and from_currency in EXCHANGE_RATES_TO_HKD:
        converted = parsed_amount * EXCHANGE_RATES_TO_HKD[from_currency]
    else:
        return str(
            parsed_amount.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )
        ), from_currency

    return str(
        converted.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )
    ), to_currency