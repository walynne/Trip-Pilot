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

    def __init__(self, provider="mock", *, mock_scenario="standard", client=None, geocoder=None):
        if provider not in {"mock", "duffel", "serpapi"}:
            raise ValueError("provider must be mock, duffel, or serpapi")
        if not isinstance(mock_scenario, str) or mock_scenario not in {"standard", "fully_booked", "price_spike", "provider_error"}:
            raise ValueError("Unsupported mock hotel scenario")
        self.provider = provider
        self.mock_scenario = mock_scenario
        self.client = client
        self.geocoder = geocoder
        if provider == "duffel" and self.client is None:
            from tools.duffel_stays_client import DuffelStaysClient

            self.client = DuffelStaysClient()
        elif provider == "serpapi" and self.client is None:
            from tools.google_hotels_tool import GoogleHotelsSearchTool

            self.client = GoogleHotelsSearchTool()

    def search_hotels(self, location, check_in, check_out, guests=1, rooms=1):
        """Return JSON-safe synthetic offers, or raise ValueError/HotelError.

        Price is per room; multiple rooms multiply the nightly rate.
        Only real provider integrations may claim verified bookability.
        """
        arrival = _parse_date(check_in, "check_in")
        departure = _parse_date(check_out, "check_out")
        nights = (departure - arrival).days
        if not 1 <= nights <= 30:
            raise ValueError("Hotel stays must include 1 to 30 nights; checkout is exclusive")
        guests = _positive_int(guests, "guests", 32)
        rooms = _positive_int(rooms, "rooms", 8)

        if self.provider == "duffel":
            return self._search_duffel(location, check_in, check_out, nights, guests, rooms)
        if self.provider == "serpapi":
            return self._search_serpapi(location, check_in, check_out, nights, guests, rooms)

        name, country, currency, latitude, longitude = _resolve_mock_location(location)
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

    def _search_duffel(self, location, check_in, check_out, nights, guests, rooms):
        try:
            response = self.client.search(location, check_in, check_out, guests, rooms)
        except ValueError as exc:
            raise HotelError("provider_error", str(exc)) from exc

        hotels = []
        for item in response["results"]:
            accommodation = item.get("accommodation") or item
            available_rates = []
            for room in accommodation.get("rooms", []) or []:
                available_rates.extend(room.get("rates", []) or [])
            if not available_rates:
                continue
            rate = min(
                available_rates,
                key=lambda candidate: Decimal(candidate.get("total_amount", "Infinity")),
            )
            amount = Decimal(rate["total_amount"])
            currency = rate.get("total_currency") or rate.get("currency")
            location_data = accommodation.get("location") or {}
            address = location_data.get("address") or {}
            coordinates = location_data.get("geographic_coordinates") or {}
            hotels.append({
                "hotel_id": accommodation.get("id") or accommodation.get("accommodation_id"),
                "name": accommodation.get("name") or accommodation.get("accommodation_name") or "Hotel",
                "city": address.get("city_name") or response["location"],
                "country_code": address.get("country_code") or response.get("country_code"),
                "location": {
                    "latitude": coordinates.get("latitude", response["latitude"]),
                    "longitude": coordinates.get("longitude", response["longitude"]),
                    "coordinates_are_synthetic": False,
                },
                "hotel_tier": None,
                "preferred_supplier": None,
                "amenities": [amenity.get("description") for amenity in accommodation.get("amenities", []) or []
                              if isinstance(amenity, dict) and amenity.get("description")],
                "cancellation_policy": None,
                "availability_status": "available",
                "booking_url": None,
                "pricing": {
                    "currency": currency,
                    "room_nightly_rate": format(amount / nights, ".2f"),
                    "room_count": rooms,
                    "night_count": nights,
                    "subtotal": rate.get("base_amount"),
                    "taxes": rate.get("tax_amount"),
                    "fees": None,
                    "total": rate["total_amount"],
                    "taxes_are_simulated": False,
                    "payment_type": rate.get("payment_type"),
                },
            })

        hotels.sort(key=lambda hotel: (hotel["pricing"]["currency"], Decimal(hotel["pricing"]["total"])))
        return {
            "location": response["location"],
            "country_code": response.get("country_code"),
            "check_in": check_in,
            "check_out": check_out,
            "nights": nights,
            "guests": guests,
            "rooms": rooms,
            "currency": hotels[0]["pricing"]["currency"] if hotels else None,
            "provider": "duffel",
            "data_mode": "live",
            "mock_scenario": None,
            "status": "success" if hotels else "no_results",
            "hotels": hotels,
            "result_count": len(hotels),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "attribution": "Duffel Stays; live rates and availability can change",
        }

    def _search_serpapi(self, location, check_in, check_out, nights, guests, rooms):
        try:
            response = self.client.search_google_hotels(
                f"Hotels in {location}",
                check_in,
                check_out,
                adults=guests,
            )
        except Exception as exc:
            raise HotelError("provider_error", "Google Hotels search could not be completed.") from exc

        if not isinstance(response, dict) or response.get("status") == "error":
            raise HotelError("provider_error", "Google Hotels search returned an error.")

        hotels = []
        for item in response.get("properties", []):
            nightly = item.get("price_per_night")
            total = item.get("total_price")
            try:
                if total is None and nightly is not None:
                    total = Decimal(str(nightly)) * nights
                if nightly is None and total is not None:
                    nightly = Decimal(str(total)) / nights
                if total is None or nightly is None:
                    continue
                total_amount = Decimal(str(total))
                nightly_amount = Decimal(str(nightly))
            except Exception:
                continue

            coordinates = item.get("gps_coordinates") or {}
            hotels.append({
                "hotel_id": item.get("property_token"),
                "name": item.get("name") or "Hotel",
                "city": location.split(",", 1)[0].strip(),
                "country_code": None,
                "location": {
                    "latitude": coordinates.get("latitude"),
                    "longitude": coordinates.get("longitude"),
                    "coordinates_are_synthetic": False,
                },
                "hotel_tier": None,
                "preferred_supplier": None,
                "amenities": item.get("amenities", []),
                "rating": item.get("rating"),
                "review_count": item.get("reviews"),
                "address": item.get("address"),
                "free_cancellation": item.get("free_cancellation"),
                "cancellation_policy": None,
                "availability_status": "price_listed",
                "booking_url": item.get("link"),
                "pricing": {
                    "currency": item.get("currency") or "USD",
                    "room_nightly_rate": format(nightly_amount, ".2f"),
                    "room_count": rooms,
                    "night_count": nights,
                    "subtotal": None,
                    "taxes": None,
                    "fees": None,
                    "total": format(total_amount, ".2f"),
                    "taxes_are_simulated": False,
                },
            })

        hotels.sort(key=lambda hotel: Decimal(hotel["pricing"]["total"]))
        return {
            "location": location,
            "country_code": None,
            "check_in": check_in,
            "check_out": check_out,
            "nights": nights,
            "guests": guests,
            "rooms": rooms,
            "currency": hotels[0]["pricing"]["currency"] if hotels else "USD",
            "provider": "google_hotels",
            "data_mode": "live",
            "mock_scenario": None,
            "status": "success" if hotels else "no_results",
            "hotels": hotels,
            "result_count": len(hotels),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "attribution": "Google Hotels results via SerpApi; prices and availability can change",
        }
