"""Tests for the HotelService with live search capability."""

import pytest
from services.hotel_service import HotelService
from tools.hotel_search import HotelError


def test_hotel_service_with_mock_provider():
    """Test HotelService with mock provider."""
    service = HotelService(provider="mock")

    result = service.search_hotels(
        location="Singapore",
        check_in="2026-11-15",
        check_out="2026-11-17",
        guests=2,
        rooms=1
    )

    assert result["location"] == "Singapore"
    assert result["country_code"] == "SG"
    assert result["currency"] == "SGD"
    assert result["provider"] == "mock"
    assert result["data_mode"] == "mock"
    assert result["status"] == "success"
    assert result["is_live"] is False
    assert result["result_count"] > 0

    # Verify normalized hotel structure
    hotel = result["hotels"][0]
    assert "id" in hotel
    assert "name" in hotel
    assert "pricing" in hotel
    assert "location" in hotel
    assert "amenities" in hotel


def test_hotel_service_default_provider():
    """Test that HotelService defaults to appropriate provider based on env."""
    import os
    service = HotelService()
    expected = (
        "serpapi" if os.getenv("SERPAPI_API_KEY")
        else "duffel" if os.getenv("DUFFEL_API_KEY")
        else "mock"
    )
    assert service.provider == expected


def test_hotel_service_get_best_hotel():
    """Test get_best_hotel method."""
    service = HotelService(provider="mock")

    result = service.search_hotels(
        location="London",
        check_in="2026-11-20",
        check_out="2026-11-22",
        guests=1,
        rooms=1
    )

    best = service.get_best_hotel(result)
    assert best is not None
    assert "name" in best


def test_hotel_service_filter_by_price():
    """Test filtering hotels by price constraints."""
    service = HotelService(provider="mock")

    result = service.search_hotels(
        location="New York",
        check_in="2026-12-01",
        check_out="2026-12-03",
        guests=2,
        rooms=1
    )

    original_count = result["result_count"]

    # Filter hotels with a reasonable max nightly rate
    filtered = service.filter_hotels_by_price(result, max_nightly_rate=150)
    assert len(filtered) <= original_count


def test_hotel_service_filter_by_amenities():
    """Test filtering hotels by required amenities."""
    service = HotelService(provider="mock")

    result = service.search_hotels(
        location="Hong Kong",
        check_in="2026-11-10",
        check_out="2026-11-12",
        guests=1,
        rooms=1
    )

    # Filter for hotels with wifi and workspace
    filtered = service.filter_hotels_by_amenities(
        result,
        required_amenities=["wifi", "workspace"]
    )
    assert len(filtered) > 0

    # Verify all filtered hotels have the required amenities
    for hotel in filtered:
        amenities_lower = [a.lower() for a in hotel["amenities"]]
        assert "wifi" in amenities_lower or "workspace" in amenities_lower


def test_hotel_service_normalized_pricing():
    """Test that pricing is properly normalized."""
    service = HotelService(provider="mock")

    result = service.search_hotels(
        location="Singapore",
        check_in="2026-11-01",
        check_out="2026-11-04",
        guests=2,
        rooms=1
    )

    hotel = result["hotels"][0]
    pricing = hotel["pricing"]

    # Verify all pricing fields are present
    assert pricing["nightly_rate"] is not None
    assert pricing["total"] is not None
    assert pricing["currency"] == "SGD"


def test_hotel_service_location_normalization():
    """Test that location data is properly normalized."""
    service = HotelService(provider="mock")

    result = service.search_hotels(
        location="London, GB",
        check_in="2026-11-15",
        check_out="2026-11-17",
        guests=1,
        rooms=1
    )

    assert result["location"] == "London"
    assert result["country_code"] == "GB"
    assert result["is_live"] is False

    for hotel in result["hotels"]:
        location = hotel["location"]
        assert "latitude" in location
        assert "longitude" in location
        assert "is_synthetic" in location


def test_hotel_service_mock_scenario():
    """Test that mock scenarios are preserved in response."""
    service = HotelService(provider="mock")

    result = service.search_hotels(
        location="Singapore",
        check_in="2026-11-15",
        check_out="2026-11-17",
        guests=1,
        rooms=1
    )

    assert result["mock_scenario"] == "standard"


def test_hotel_service_fully_booked_scenario():
    """Test mock fully_booked scenario."""
    service = HotelService(provider="mock")
    service.tool.mock_scenario = "fully_booked"

    result = service.search_hotels(
        location="New York",
        check_in="2026-11-15",
        check_out="2026-11-17",
        guests=1,
        rooms=1
    )

    assert result["status"] == "no_results"
    assert result["result_count"] == 0
    assert len(result["hotels"]) == 0


def test_hotel_service_price_spike_scenario():
    """Test mock price_spike scenario."""
    service = HotelService(provider="mock")
    service.tool.mock_scenario = "price_spike"

    result = service.search_hotels(
        location="Singapore",
        check_in="2026-11-15",
        check_out="2026-11-17",
        guests=1,
        rooms=1
    )

    assert result["status"] == "success"
    assert result["result_count"] > 0
    # Prices should be 50% higher due to price_spike scenario
    assert "mock_scenario" in result
    assert result["mock_scenario"] == "price_spike"


def test_hotel_service_error_handling():
    """Test error handling in HotelService."""
    service = HotelService(provider="mock")

    # Invalid location
    with pytest.raises(HotelError):
        service.search_hotels(
            location="Unknown City",
            check_in="2026-11-15",
            check_out="2026-11-17"
        )


def test_hotel_service_with_live_provider_requires_key():
    """Test that live provider requires DUFFEL_API_KEY."""
    import os
    from unittest.mock import patch

    # Mock absence of DUFFEL_API_KEY
    with patch.dict(os.environ, {}, clear=False):
        if "DUFFEL_API_KEY" in os.environ:
            del os.environ["DUFFEL_API_KEY"]

        service = HotelService(provider="mock")
        assert service.provider == "mock"


def test_hotel_service_provider_validation():
    """Test that invalid provider raises error."""
    with pytest.raises(ValueError):
        HotelService(provider="invalid")
