"""C2 corporate hotel research: synthetic deterministic offers, not real inventory.

Matches C1/C3's synchronous, JSON-safe Python tool interface. The module is
independent of an LLM and does not evaluate corporate policy or place bookings.
"""
from datetime import date, datetime, timezone
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
import re


class HotelError(Exception):
    """Provider failure with a machine-readable, safe code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


# All properties, names, rates and coordinates below are deliberately fictional.
# Currency/tax data are simulation parameters, not jurisdictional tax assertions.
MOCK_CITIES = {
    "singapore": ("Singapore", "SG", "SGD", 1.3521, 103.8198),
    "hong kong": ("Hong Kong", "HK", "HKD", 22.3193, 114.1694),
    "london": ("London", "GB", "GBP", 51.5074, -0.1278),
    "new york": ("New York", "US", "USD", 40.7128, -74.0060),
}
MOCK_COUNTRY_NAMES = {
    "SG": ("sg", "singapore"),
    "HK": ("hk", "hong kong"),
    "GB": ("gb", "great britain", "united kingdom", "uk"),
    "US": ("us", "united states", "usa"),
}
# per room per night, as synthetic sample pricing in local currency
MOCK_HOTELS = (
    ("001", "TripPilot Sample Central", "business", True, ("wifi", "workspace"), "flexible", "145.00", ".005", ".008"),
    ("002", "TripPilot Sample Executive", "business", False, ("wifi", "workspace", "breakfast"), "non_refundable", "115.00", ".011", "-.006"),
    ("003", "TripPilot Sample Premier", "premium", True, ("wifi", "workspace", "breakfast", "gym"), "flexible", "205.00", "-.009", ".012"),
)
# Fixed rates are deliberately fictional and NOT legally accurate taxes.
MOCK_TAX_RATE = Decimal("0.10")
MOCK_FEE_PER_ROOM_PER_STAY = Decimal("12.00")
TWOPLACES = Decimal("0.01")


def _money(value):
    return str(value.quantize(TWOPLACES, rounding=ROUND_HALF_UP))


def _parse_date(raw, name):
    if not isinstance(raw, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw) is None:
        raise ValueError(f"{name} must be a YYYY-MM-DD string")
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid calendar date") from exc
    if parsed.isoformat() != raw:
        raise ValueError(f"{name} must be YYYY-MM-DD")
    return parsed


def _positive_int(value, label, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{label} must be an integer between 1 and {maximum}")
    return value


def _resolve_mock_location(location):
    if not isinstance(location, str) or not 2 <= len(location.strip()) <= 200:
        raise ValueError("location must be a city name of 2 to 200 characters")
    tokens = location.strip().split(",")
    if len(tokens) > 2 or any(not token.strip() for token in tokens):
        raise ValueError("location must be a city optionally followed by a country qualifier")
    city = tokens[0].strip().casefold()
    resolved = MOCK_CITIES.get(city)
    if resolved is None:
        raise HotelError("location_not_found", "Destination is not in the mock hotel catalogue.")
    name, country, currency, latitude, longitude = resolved
    if len(tokens) == 2:
        qualifier = tokens[1].strip().casefold()
        if qualifier not in MOCK_COUNTRY_NAMES[country]:
            raise HotelError("location_not_found", "Destination does not match the specified country.")
    return name, country, currency, latitude, longitude


class HotelSearchTool:
    """Search a repeatable synthetic hotel catalogue for course-project demos.

    Public contract: ``search_hotels(location, check_in, check_out, guests=1, rooms=1)``.
    Date interval [check_in, check_out) and all monetary fields are explicit.
    """

    def __init__(self, provider="mock", *, mock_scenario="standard"):
        if provider != "mock":
            raise ValueError("Only the mock hotel provider is implemented; live provider is not available")
        if not isinstance(mock_scenario, str) or mock_scenario not in {"standard", "fully_booked", "price_spike", "provider_error"}:
            raise ValueError("Unsupported mock hotel scenario")
        self.provider = provider
        self.mock_scenario = mock_scenario

    def search_hotels(self, location, check_in, check_out, guests=1, rooms=1):
        """Return JSON-safe synthetic offers, or raise ValueError/HotelError.

        Price is per room; multiple rooms multiply the nightly rate.
        Only real provider integrations may claim verified bookability.
        """
        name, country, currency, latitude, longitude = _resolve_mock_location(location)
        arrival = _parse_date(check_in, "check_in")
        departure = _parse_date(check_out, "check_out")
        nights = (departure - arrival).days
        if not 1 <= nights <= 30:
            raise ValueError("Hotel stays must include 1 to 30 nights; checkout is exclusive")
        guests = _positive_int(guests, "guests", 32)
        rooms = _positive_int(rooms, "rooms", 8)
        if guests > 4 * rooms:
            raise ValueError("Mock capacity is at most 4 guests per room")
        if self.mock_scenario == "provider_error":
            raise HotelError("provider_error", "Simulated hotel provider failure (mock).")

        hotels = []
        if self.mock_scenario != "fully_booked":
            # Pricing must not inherit another tool's precision, rounding or traps.
            with localcontext(Context(prec=28, rounding=ROUND_HALF_UP)):
                for suffix, title, tier, preferred, amenities, cancellation, price, lat_offset, lon_offset in MOCK_HOTELS:
                    rate = Decimal(price)
                    if self.mock_scenario == "price_spike":
                        rate *= Decimal("1.50")
                    rate = rate.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
                    subtotal = rate * rooms * nights
                    taxes = (subtotal * MOCK_TAX_RATE).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
                    fees = MOCK_FEE_PER_ROOM_PER_STAY * rooms
                    total = subtotal + taxes + fees
                    hotels.append({
                        "hotel_id": f"TP-MOCK-{country}-{suffix}",
                        "name": title,
                        "city": name,
                        "country_code": country,
                        "location": {"latitude": round(latitude + float(lat_offset), 6),
                                     "longitude": round(longitude + float(lon_offset), 6),
                                     "coordinates_are_synthetic": True},
                        "hotel_tier": tier,
                        "preferred_supplier": preferred,
                        "amenities": list(amenities),
                        "cancellation_policy": cancellation,
                        "availability_status": "simulated_available",
                        "booking_url": None,
                        "pricing": {
                            "currency": currency,
                            "room_nightly_rate": _money(rate),
                            "room_count": rooms,
                            "night_count": nights,
                            "subtotal": _money(subtotal),
                            "taxes": _money(taxes),
                            "fees": _money(fees),
                            "total": _money(total),
                            "taxes_are_simulated": True,
                        },
                    })
                hotels.sort(key=lambda row: (Decimal(row["pricing"]["total"]), row["hotel_id"]))

        return {
            "location": name,
            "country_code": country,
            "check_in": check_in,
            "check_out": check_out,
            "nights": nights,
            "guests": guests,
            "rooms": rooms,
            "currency": currency,
            "provider": "mock",
            "data_mode": "mock",
            "mock_scenario": self.mock_scenario,
            "status": "success" if hotels else "no_results",
            "hotels": hotels,
            "result_count": len(hotels),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "attribution": "Fictional TripPilot demo hotel catalogue; not real availability or legal tax data",
        }
