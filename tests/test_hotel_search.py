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

