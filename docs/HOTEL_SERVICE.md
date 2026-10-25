# HotelService: Live Hotel Search

`HotelService` provides a unified interface for mock and live hotel searches through Duffel Stays or Google Hotels via SerpApi.

## Quick Start

### Mock Provider (Default)
```python
from services.hotel_service import HotelService

# Create service with mock provider
service = HotelService(provider="mock")

# Search for hotels
result = service.search_hotels(
    location="Singapore",
    check_in="2026-11-15",
    check_out="2026-11-17",
    guests=2,
    rooms=1
)

print(f"Found {result['result_count']} hotels")
print(f"Provider: {result['provider']} (data_mode: {result['data_mode']})")

# Get best (cheapest) hotel
best = service.get_best_hotel(result)
print(f"Best hotel: {best['name']} - {best['pricing']['total']} {best['pricing']['currency']}")
```

## Live Search with Duffel

To enable live hotel searches via Duffel:

1. **Set your Duffel API credentials:**
   ```bash
   export DUFFEL_API_KEY="your-api-key-here"
   export DUFFEL_BASE_URL="https://api.duffel.com"  # optional
   ```

2. **Create service with live provider:**
   ```python
   from services.hotel_service import HotelService

    # Automatically selects SerpApi first, then Duffel if configured
   service = HotelService()

   # Or explicitly request Duffel
   service = HotelService(provider="duffel")

   # Search for hotels (real data from Duffel API)
   result = service.search_hotels(
       location="London",
       check_in="2026-12-15",
       check_out="2026-12-18",
       guests=2,
       rooms=1
   )

   if result['is_live']:
       print("✓ Using live Duffel data")
   else:
       print("Using mock data")
   ```

## Live Search with Google Hotels via SerpApi

Install the `google-search-results` dependency and configure a SerpApi key in
`.env`:

```dotenv
SERPAPI_API_KEY=your-serpapi-key
TRIPPILOT_HOTEL_PROVIDER=serpapi
```

SerpApi is selected automatically when `SERPAPI_API_KEY` is present, unless
`TRIPPILOT_HOTEL_PROVIDER` explicitly selects another provider. Google Hotels
prices and availability are search results and can change; this integration does
not make reservations.

```python
from services.hotel_service import HotelService

service = HotelService(provider="serpapi")
result = service.search_hotels(
    location="Tokyo, Japan",
    check_in="2026-11-15",
    check_out="2026-11-17",
    guests=2,
    rooms=1,
)

print(result["provider"], result["data_mode"], result["result_count"])
for hotel in result["hotels"]:
    print(hotel["name"], hotel["pricing"]["total"], hotel["pricing"]["currency"])
```

The search uses SerpApi's `google_hotels` engine with the destination, dates, and
adult count. Set `SERPAPI_API_KEY` before starting the app to enable live results.

## Key Features

### Automatic Provider Selection
```python
# Defaults to SerpApi when SERPAPI_API_KEY is set, then Duffel, otherwise mock
service = HotelService()

# Explicitly choose provider
service = HotelService(provider="mock")    # Force mock
service = HotelService(provider="duffel")  # Force Duffel (requires API key)
service = HotelService(provider="serpapi") # Force Google Hotels via SerpApi
```

### Filtering and Enrichment
```python
# Filter by price
affordable = service.filter_hotels_by_price(
    result,
    max_nightly_rate=200,
    max_total=1000
)

# Filter by amenities
business_hotels = service.filter_hotels_by_amenities(
    result,
    required_amenities=["wifi", "workspace", "breakfast"]
)

# Get best option
best = service.get_best_hotel(result)
```

### Normalized Response Format
```python
result = service.search_hotels(
    location="Singapore",
    check_in="2026-11-15",
    check_out="2026-11-17"
)

# Common fields (mock and live)
print(result["location"])      # "Singapore"
print(result["country_code"])  # "SG"
print(result["currency"])      # "SGD"
print(result["nights"])        # 2
print(result["provider"])      # "mock" or "duffel"
print(result["data_mode"])     # "mock" or "live"
print(result["is_live"])       # False or True
print(result["result_count"])  # Number of results

# Hotel data normalized across providers
for hotel in result["hotels"]:
    print(f"{hotel['name']}")
    print(f"  Price: {hotel['pricing']['nightly_rate']} {hotel['pricing']['currency']}/night")
    print(f"  Total: {hotel['pricing']['total']}")
    print(f"  Amenities: {', '.join(hotel['amenities'])}")
    print(f"  Location: ({hotel['location']['latitude']}, {hotel['location']['longitude']})")
```

## Mock Scenarios (Testing)

For local development and testing, use mock scenarios:

```python
from services.hotel_service import HotelService

# Standard mock (normal pricing, 3 hotels)
service = HotelService(provider="mock")
service.tool.mock_scenario = "standard"

# Price spike (50% higher prices for testing surge pricing)
service.tool.mock_scenario = "price_spike"

# Fully booked (no results, tests fallback handling)
service.tool.mock_scenario = "fully_booked"

# Provider error (tests error recovery)
service.tool.mock_scenario = "provider_error"

result = service.search_hotels(...)
print(result["mock_scenario"])  # Shows which scenario was used
```

## Integration with PlannerAgent

The `PlannerAgent` now uses `HotelService` instead of directly using `HotelSearchTool`:

```python
from agents.planner_agent import PlannerAgent

# PlannerAgent automatically uses HotelService
planner = PlannerAgent()

# Set environment variable to control provider
# TRIPPILOT_HOTEL_PROVIDER=mock or TRIPPILOT_HOTEL_PROVIDER=duffel
```

## Response Structure

### Mock Provider Response
```python
{
    "location": "Singapore",
    "country_code": "SG",
    "check_in": "2026-11-15",
    "check_out": "2026-11-17",
    "nights": 2,
    "guests": 2,
    "rooms": 1,
    "currency": "SGD",
    "provider": "mock",
    "data_mode": "mock",
    "status": "success",
    "hotels": [
        {
            "id": "TP-MOCK-SG-001",
            "name": "TripPilot Sample Central",
            "city": "Singapore",
            "country_code": "SG",
            "tier": "business",
            "amenities": ["wifi", "workspace"],
            "cancellation_policy": "flexible",
            "location": {
                "latitude": 1.3521,
                "longitude": 103.8198,
                "is_synthetic": True
            },
            "pricing": {
                "currency": "SGD",
                "nightly_rate": "145.00",
                "subtotal": "290.00",
                "taxes": "29.00",
                "fees": "24.00",
                "total": "343.00"
            }
        },
        # ... more hotels
    ],
    "result_count": 3,
    "is_live": False,
    "mock_scenario": "standard"
}
```

### Live Provider Response (Duffel)
```python
{
    "location": "London",
    "country_code": "GB",
    "check_in": "2026-12-15",
    "check_out": "2026-12-18",
    "nights": 3,
    "guests": 2,
    "rooms": 1,
    "currency": "GBP",
    "provider": "duffel",
    "data_mode": "live",
    "status": "success",
    "hotels": [
        {
            "id": "duffel-hotel-id-123",
            "name": "The Savoy",
            "city": "London",
            "country_code": "GB",
            "tier": None,  # Not set by Duffel provider
            "amenities": ["wifi", "gym", "restaurant"],
            "location": {
                "latitude": 51.507,
                "longitude": -0.121,
                "is_synthetic": False
            },
            "pricing": {
                "currency": "GBP",
                "nightly_rate": "450.00",
                "subtotal": "1350.00",
                "taxes": "270.00",
                "fees": None,
                "total": "1620.00",
                "payment_type": "prepaid"
            }
        },
        # ... more hotels
    ],
    "result_count": 25,
    "is_live": True,
    "retrieved_at": "2026-10-25T12:34:56.789Z"
}
```

## Error Handling

```python
from services.hotel_service import HotelService
from tools.hotel_search import HotelError

service = HotelService()

try:
    result = service.search_hotels(
        location="Singapore",
        check_in="2026-11-15",
        check_out="2026-11-17"
    )
except HotelError as e:
    print(f"Hotel search failed: {e.code} - {e}")
except ValueError as e:
    print(f"Invalid parameters: {e}")
```

## Environment Variables

- `DUFFEL_API_KEY`: Required for live searches via Duffel
- `DUFFEL_BASE_URL`: Optional, defaults to https://api.duffel.com
- `TRIPPILOT_HOTEL_PROVIDER`: Force provider selection (mock/duffel)

## Comparison: Mock vs Live

| Feature | Mock | Live (Duffel) |
|---------|------|---------------|
| Real API calls | ❌ | ✓ |
| Current pricing | ❌ | ✓ |
| Real availability | ❌ | ✓ |
| Deterministic results | ✓ | ❌ |
| Good for testing | ✓ | ❌ |
| Good for production | ❌ | ✓ |
| Requires API key | ❌ | ✓ |
| Supports scenarios | ✓ (testing) | ❌ |
