"""C2 deterministic offline contract tests, matching pytest convention of C3."""
import json
from decimal import Decimal
from unittest.mock import Mock

import pytest
import requests

from tools.hotel_search import HotelError, HotelSearchTool


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Hotel mock provider attempted external network access")
    monkeypatch.setattr(requests, "get", forbidden)
    monkeypatch.setattr(requests, "post", forbidden)


def hotels(**kwargs):
    return HotelSearchTool(**kwargs).search_hotels("Singapore, SG", "2030-11-15", "2030-11-18")


def _flight_offer(amount, currency="HKD", airline="Sample Airline"):
    return {
        "owner": {"name": airline},
        "total_amount": str(amount),
        "total_currency": currency,
        "slices": [{
            "segments": [{
                "marketing_carrier": {"iata_code": "CX", "name": airline},
                "operating_carrier": {"iata_code": "CX", "name": airline},
                "origin": {"iata_code": "HKG"},
                "destination": {"iata_code": "SIN"},
                "departing_at": "2030-11-15T10:00:00+00:00",
                "arriving_at": "2030-11-15T13:00:00+00:00",
            }]
        }]
    }


def test_basic_mock_results():
    result = hotels()
    assert result["data_mode"] == "mock"
    assert result["provider"] == "mock"
    assert result["status"] == "success"
    assert result["result_count"] == 3
    assert result["nights"] == 3
    assert result["currency"] == "SGD"
    assert result["attribution"]
    assert all(row["location"]["coordinates_are_synthetic"] for row in result["hotels"])


def test_total_uses_decimal():
    result = HotelSearchTool().search_hotels("Singapore", "2030-11-15", "2030-11-17", rooms=2, guests=3)
    for hotel in result["hotels"]:
        pricing = hotel["pricing"]
        base = Decimal(pricing["room_nightly_rate"]) * 2 * 2
        assert Decimal(pricing["subtotal"]) == base
        assert Decimal(pricing["taxes"]) == (base * Decimal(".10")).quantize(Decimal(".01"))
        assert Decimal(pricing["fees"]) == Decimal("24.00")
        assert Decimal(pricing["total"]) == sum(map(Decimal, (pricing["subtotal"], pricing["taxes"], pricing["fees"])))


def test_sorted_ascending_total():
    rows = hotels()["hotels"]
    assert [Decimal(x["pricing"]["total"]) for x in rows] == sorted(Decimal(x["pricing"]["total"]) for x in rows)


def test_mock_determinism():
    first, second = hotels(), hotels()
    first.pop("retrieved_at")
    second.pop("retrieved_at")
    assert first == second


@pytest.mark.parametrize("city,currency", [
    ("Singapore, SG", "SGD"), ("Hong Kong, HK", "HKD"),
    ("London, GB", "GBP"), ("New York, US", "USD"),
    ("London, United Kingdom", "GBP"),
])
def test_qualified_cities(city, currency):
    result = HotelSearchTool().search_hotels(city, "2030-11-15", "2030-11-16")
    assert result["currency"] == currency


@pytest.mark.parametrize("city", ["Unknown City", "Singapore, GB", "Tokyo", "London, US"])
def test_unknown_city_or_qualifier(city):
    with pytest.raises(HotelError) as error:
        HotelSearchTool().search_hotels(city, "2030-11-15", "2030-11-16")
    assert error.value.code == "location_not_found"


@pytest.mark.parametrize("location", [None, 12, "", "A", "S," ,",SG", "London, GB, London"])
def test_invalid_location(location):
    with pytest.raises(ValueError):
        HotelSearchTool().search_hotels(location, "2030-11-15", "2030-11-16")


@pytest.mark.parametrize("check_in,check_out", [
    ("bad", "2030-11-18"), ("2030-02-30", "2030-11-18"),
    ("20301115", "2030-11-18"), ("2030-11-15", "2030-11-15"),
    ("2030-11-18", "2030-11-15"), ("2030-11-15", "2030-12-16"),
])
def test_invalid_dates(check_in, check_out):
    with pytest.raises(ValueError):
        HotelSearchTool().search_hotels("Singapore", check_in, check_out)


@pytest.mark.parametrize("guests,rooms", [(0,1), (1,0), (True,1), (1,True), (33,8), (5,1), (1,9), (1.5,1)])
def test_occupancy_rejects_invalid_values(guests, rooms):
    with pytest.raises(ValueError):
        HotelSearchTool().search_hotels("Singapore", "2030-11-15", "2030-11-17", guests=guests, rooms=rooms)


def test_mock_fully_booked():
    result = hotels(mock_scenario="fully_booked")
    assert result["status"] == "no_results"
    assert result["hotels"] == []
    assert result["result_count"] == 0


def test_mock_price_spike():
    standard = hotels()
    spiked = hotels(mock_scenario="price_spike")
    assert spiked["data_mode"] == "mock"
    assert Decimal(spiked["hotels"][0]["pricing"]["room_nightly_rate"]) > Decimal(standard["hotels"][0]["pricing"]["room_nightly_rate"])


def test_mock_provider_error():
    with pytest.raises(HotelError) as error:
        hotels(mock_scenario="provider_error")
    assert error.value.code == "provider_error"


def test_unsupported_provider_and_scenario():
    with pytest.raises(ValueError):
        HotelSearchTool(provider="live")
    with pytest.raises(ValueError):
        HotelSearchTool(mock_scenario="weather")


def test_duffel_provider_normalizes_live_rates_without_inventing_tax_or_booking():
    class Client:
        def search(self, location, check_in, check_out, guests, rooms):
            assert (location, check_in, check_out, guests, rooms) == (
                "Tokyo", "2030-11-15", "2030-11-18", 2, 1,
            )
            return {
                "location": "Tokyo",
                "country_code": "JP",
                "latitude": 35.6762,
                "longitude": 139.6503,
                "results": [{
                    "accommodation": {
                        "id": "acc_live_1",
                        "name": "Live Sample Hotel",
                        "location": {
                            "address": {"city_name": "Tokyo", "country_code": "JP"},
                            "geographic_coordinates": {"latitude": 35.67, "longitude": 139.65},
                        },
                        "rooms": [{"rates": [{
                            "total_amount": "30000.00",
                            "total_currency": "JPY",
                            "base_amount": "27000.00",
                            "tax_amount": "3000.00",
                            "payment_type": "pay_now",
                        }]}],
                    }
                }],
            }

    result = HotelSearchTool(provider="duffel", client=Client()).search_hotels(
        "Tokyo", "2030-11-15", "2030-11-18", guests=2, rooms=1,
    )

    assert result["provider"] == "duffel"
    assert result["data_mode"] == "live"
    assert result["status"] == "success"
    assert result["hotels"][0]["hotel_id"] == "acc_live_1"
    assert result["hotels"][0]["pricing"] == {
        "currency": "JPY",
        "room_nightly_rate": "10000.00",
        "room_count": 1,
        "night_count": 3,
        "subtotal": "27000.00",
        "taxes": "3000.00",
        "fees": None,
        "total": "30000.00",
        "taxes_are_simulated": False,
        "payment_type": "pay_now",
    }
    assert result["hotels"][0]["availability_status"] == "available"
    assert result["hotels"][0]["booking_url"] is None
def test_duffel_client_sends_stay_search_and_fetch_all_rates_requests(monkeypatch):
    from tools.duffel_stays_client import DuffelStaysClient

    monkeypatch.setenv("DUFFEL_API_KEY", "test-token")
    monkeypatch.setenv("DUFFEL_BASE_URL", "https://api.example.test")

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class Session:
        def __init__(self):
            self.calls = []

        def request(self, method, url, **kwargs):
            self.calls.append((method, url, kwargs))
            if url.endswith("/stays/search"):
                return Response({"data": {"results": [{"id": "srr_123"}]}})
            return Response({"data": {"id": "srr_123", "accommodation": {"id": "acc_123"}}})

    session = Session()
    client = DuffelStaysClient(session=session)
    client.geocoder.lookup_location = lambda _location: {
        "results": [{"name": "Tokyo", "country_code": "JP", "latitude": 35.67, "longitude": 139.65}]
    }
    result = client.search("Tokyo", "2030-11-15", "2030-11-18", guests=3, rooms=2)

    assert result["results"] == [{"id": "srr_123", "accommodation": {"id": "acc_123"}}]
    assert session.calls[0][0:2] == ("POST", "https://api.example.test/stays/search")
    assert session.calls[0][2]["json"]["data"]["rooms"] == 2
    assert session.calls[0][2]["json"]["data"]["guests"] == [
        {"type": "adult"}, {"type": "adult"}, {"type": "adult"},
    ]
    assert session.calls[1][0:2] == (
        "POST",
        "https://api.example.test/stays/search_results/srr_123/actions/fetch_all_rates",
    )


def test_duffel_access_denied_explains_stays_access_requirement(monkeypatch):
    from tools.duffel_stays_client import DuffelStaysClient

    monkeypatch.setenv("DUFFEL_API_KEY", "test-token")

    class Response:
        status_code = 403

        def raise_for_status(self):
            raise requests.exceptions.HTTPError(response=self)

    class Session:
        def request(self, *_args, **_kwargs):
            return Response()

    client = DuffelStaysClient(session=Session())
    with pytest.raises(ValueError, match="request Stays access"):
        client._request("POST", "/stays/search", json={"data": {}})


def test_planner_selects_duffel_when_credentials_exist_and_allows_mock_override(monkeypatch):
    from agents.planner_agent import PlannerAgent

    monkeypatch.setenv("DUFFEL_API_KEY", "test-token")
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.setenv("TRIPPILOT_HOTEL_PROVIDER", "duffel")
    planner = PlannerAgent()
    assert planner.hotel_service.provider == "duffel"

    monkeypatch.setenv("TRIPPILOT_HOTEL_PROVIDER", "mock")
    offline_planner = PlannerAgent()
    assert offline_planner.hotel_service.provider == "mock"


def test_google_hotels_search_normalizes_live_rates():
    class Client:
        def __init__(self):
            self.request = None

        def search_google_hotels(self, query, check_in, check_out, adults=2):
            self.request = (query, check_in, check_out, adults)
            return {
                "status": "success",
                "properties": [{
                    "property_token": "prop123",
                    "name": "Live Singapore Hotel",
                    "rating": 4.7,
                    "reviews": 820,
                    "price_per_night": 240,
                    "total_price": 480,
                    "currency": "SGD",
                    "amenities": ["Free Wi-Fi", "Business center"],
                    "gps_coordinates": {"latitude": 1.3, "longitude": 103.8},
                }],
            }

    client = Client()
    result = HotelSearchTool(provider="serpapi", client=client).search_hotels(
        "Singapore", "2030-11-15", "2030-11-17", guests=3, rooms=2,
    )

    assert client.request == ("Hotels in Singapore", "2030-11-15", "2030-11-17", 3)
    assert result["provider"] == "google_hotels"
    assert result["data_mode"] == "live"
    assert result["hotels"][0]["name"] == "Live Singapore Hotel"
    assert result["hotels"][0]["pricing"]["total"] == "480.00"
    assert result["hotels"][0]["pricing"]["room_nightly_rate"] == "240.00"
    assert result["hotels"][0]["rating"] == 4.7
    assert result["hotels"][0]["amenities"] == ["Free Wi-Fi", "Business center"]


def test_google_hotels_tool_uses_google_search_results_parameters():
    from tools.google_hotels_tool import GoogleHotelsSearchTool

    captured = {}

    class FakeSearch:
        def __init__(self, params):
            captured["params"] = params

        def get_dict(self):
            return {
                "search_parameters": {"currency": "USD"},
                "properties": [{
                    "name": "Tokyo Business Hotel",
                    "overall_rating": 4.6,
                    "reviews": 510,
                    "rate_per_night": {"extracted_lowest": 180, "lowest": "$180"},
                    "total_rate": {"extracted_lowest": 360, "lowest": "$360"},
                    "amenities": ["Free Wi-Fi", "Breakfast"],
                }],
            }

    result = GoogleHotelsSearchTool("test-key", search_class=FakeSearch).search_google_hotels(
        "Hotels in Tokyo near Tokyo Station",
        "2026-11-15",
        "2026-11-17",
        adults=2,
    )

    assert captured["params"] == {
        "engine": "google_hotels",
        "q": "Hotels in Tokyo near Tokyo Station",
        "check_in_date": "2026-11-15",
        "check_out_date": "2026-11-17",
        "adults": 2,
        "currency": "USD",
        "api_key": "test-key",
    }
    assert result["status"] == "success"
    assert result["result_count"] == 1
    assert result["properties"][0]["rating"] == 4.6
    assert result["properties"][0]["price_per_night"] == 180
def test_json_serializable():
    json.dumps(hotels())


def test_no_real_bookability_claim():
    result = hotels()
    for row in result["hotels"]:
        assert row["availability_status"] == "simulated_available"
        assert row["booking_url"] is None
        assert row["pricing"]["taxes_are_simulated"] is True


def test_no_policy_decisions_embedded():
    for row in hotels()["hotels"]:
        assert "policy_compliant" not in row
        assert "approval_required" not in row


@pytest.mark.parametrize("scenario", [None, [], {}, 1, True])
def test_invalid_scenario_types_raise_value_error(scenario):
    with pytest.raises(ValueError, match="Unsupported mock hotel scenario"):
        HotelSearchTool(mock_scenario=scenario)


@pytest.mark.parametrize("scenario", ["standard", "price_spike"])
def test_pricing_independent_of_caller_decimal_context(scenario):
    from decimal import Inexact, ROUND_DOWN, Rounded, localcontext
    tool = HotelSearchTool(mock_scenario=scenario)
    expected = tool.search_hotels("Singapore", "2030-11-15", "2030-12-15", guests=32, rooms=8)
    with localcontext() as context:
        context.prec = 4
        context.rounding = ROUND_DOWN
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        before = context.copy()
        actual = tool.search_hotels("Singapore", "2030-11-15", "2030-12-15", guests=32, rooms=8)
        assert context.prec == before.prec
        assert context.rounding == before.rounding
        assert context.traps == before.traps
        assert context.flags == before.flags
    expected.pop("retrieved_at")
    actual.pop("retrieved_at")
    assert actual == expected
    expected_totals = {
        "standard": {"001": "38376.00", "002": "30456.00", "003": "54216.00"},
        "price_spike": {"001": "57516.00", "002": "45636.00", "003": "81276.00"},
    }
    for hotel in actual["hotels"]:
        assert hotel["pricing"]["total"] == expected_totals[scenario][hotel["hotel_id"][-3:]]


@pytest.mark.parametrize("city,currency", [
    ("Singapore, SG", "SGD"), ("Hong Kong, HK", "HKD"),
    ("London, GB", "GBP"), ("New York, US", "USD"),
])
def test_price_spike_amounts_currency_and_provenance(city, currency):
    first = HotelSearchTool(mock_scenario="price_spike").search_hotels(city, "2030-11-15", "2030-11-16")
    second = HotelSearchTool(mock_scenario="price_spike").search_hotels(city, "2030-11-15", "2030-11-16")
    first.pop("retrieved_at")
    second.pop("retrieved_at")
    assert first == second
    expected = {
        "001": {"room_nightly_rate": "217.50", "subtotal": "217.50", "taxes": "21.75", "fees": "12.00", "total": "251.25"},
        "002": {"room_nightly_rate": "172.50", "subtotal": "172.50", "taxes": "17.25", "fees": "12.00", "total": "201.75"},
        "003": {"room_nightly_rate": "307.50", "subtotal": "307.50", "taxes": "30.75", "fees": "12.00", "total": "350.25"},
    }
    assert first["data_mode"] == first["provider"] == "mock"
    for hotel in first["hotels"]:
        pricing = hotel["pricing"]
        assert pricing["currency"] == first["currency"] == currency
        assert pricing["taxes_are_simulated"] is True
        for key, value in expected[hotel["hotel_id"][-3:]].items():
            assert pricing[key] == value
    json.dumps(first, allow_nan=False)


@pytest.mark.parametrize("check_in,check_out,nights", [
    ("2032-02-28", "2032-03-01", 2),
    ("2030-12-31", "2031-01-01", 1),
    ("2030-11-15", "2030-12-15", 30),
])
def test_exclusive_checkout_calendar_boundaries(check_in, check_out, nights):
    result = HotelSearchTool().search_hotels("London", check_in, check_out)
    assert result["nights"] == nights
    assert all(hotel["pricing"]["night_count"] == nights for hotel in result["hotels"])


def test_money_half_up_rounding():
    from tools.hotel_search import _money
    assert _money(Decimal("1.005")) == "1.01"
    assert _money(Decimal("1.004")) == "1.00"


def test_c1_flight_service_contract_preserved(monkeypatch):
    from services.flight_service import FlightService
    post = Mock()
    post.return_value.json.return_value = {"data": {"id": "request-id"}}
    get = Mock()
    offers = {"data": [_flight_offer(i, airline="Sample Airline") for i in range(5)]}
    get.return_value.json.return_value = offers
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    result = FlightService().get_flights("HKG", "SIN", "2030-11-15")
    assert len(result) == 5
    assert result[0] == {"airline": "Sample Airline", "airlines": ["CX"], "airline_names": ["Sample Airline"], "price": "0.00", "currency": "HKD", "original_price": "0", "original_currency": "HKD", "stops": 0, "departure": "2030-11-15T10:00:00+00:00", "arrival": "2030-11-15T13:00:00+00:00", "origin": "HKG", "destination": "SIN"}
    assert post.call_args.kwargs["json"]["data"]["slices"] == [
        {"origin": "HKG", "destination": "SIN", "departure_date": "2030-11-15"}]
    assert get.call_args.kwargs["params"] == {"offer_request_id": "request-id"}


def test_hotel_failure_does_not_replace_trip_agent_result():
    from agents.trip_agent import TripAgent
    agent = TripAgent.__new__(TripAgent)
    requirements = {"origin": "HKG", "destination": "SIN", "departure_date": "2030-11-15"}
    agent.extractor = Mock()
    agent.extractor.extract.return_value = requirements
    agent.flight_service = Mock()
    agent.flight_service.get_flights.return_value = [{"airline": "Sample Airline"}]
    agent.recommender = Mock()
    agent.recommender.recommend.return_value = "Recommended flight"
    agent.monitor = Mock()
    agent.monitor.detect.return_value = {"type": "none", "severity": "LOW"}
    agent.monitor.analyse.return_value = {"status": "ok"}
    agent.replanner = Mock()
    agent.replanner.replan.return_value = {"status": "not_needed"}
    result = agent.run("Trip request")
    assert set(result) == {"agent_steps", "trip_details", "requirements", "flights", "recommendation", "event", "monitor_result", "replan_result"}
    before = dict(result)
    try:
        result["hotels"] = HotelSearchTool(mock_scenario="provider_error").search_hotels(
            "Singapore", "2030-11-16", "2030-11-18")
    except (HotelError, ValueError) as exc:
        result["hotels"] = {"status": "unavailable", "data_mode": "mock", "provider": "mock",
                            "error_code": exc.code if isinstance(exc, HotelError) else "invalid_input"}
    assert all(result[key] == value for key, value in before.items())
    assert result["hotels"]["error_code"] == "provider_error"

