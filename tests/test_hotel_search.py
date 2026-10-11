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
