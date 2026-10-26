from services.activity_service import build_activity_schedule


def test_tokyo_advice_without_forecast():
    schedule = build_activity_schedule("Tokyo", "2030-11-15", "2030-11-18", [])
    assert len(schedule) == 4
    assert "Senso-ji" in schedule[0]["suggested_activity"]
    assert "Shibuya" in schedule[1]["suggested_activity"]
    assert "Weather forecast is unavailable" in schedule[0]["suggested_activity"]
    assert schedule[0]["source_url"].startswith("https://www.gotokyo.org/")
    assert "airport transfer" in schedule[-1]["suggested_activity"]


def test_high_risk_overrides_outdoor_plan_and_preserves_weather():
    schedule = build_activity_schedule("Tokyo", "2030-11-15", "2030-11-15", [
        {"date": "2030-11-15", "risk_level": "high", "temperature_max_c": 20},
    ])
    assert "postpone outdoor" in schedule[0]["suggested_activity"]
    assert "Sumida River walk" not in schedule[0]["suggested_activity"]
    assert schedule[0]["temperature_max_c"] == 20


def test_other_destinations_get_varied_general_advice_not_tokyo_sources():
    schedule = build_activity_schedule("Paris", "2030-11-15", "2030-11-18", [])
    assert "Paris" in schedule[0]["suggested_activity"]
    assert schedule[0]["source_url"] is None
    assert "culture day" in schedule[1]["suggested_activity"]
    assert "market or shopping" in schedule[2]["suggested_activity"]
    assert "park or scenic walk" in schedule[3]["suggested_activity"]


def test_singapore_has_destination_routes_and_official_sources():
    for destination in ("Singapore", "SIN", " singapore "):
        schedule = build_activity_schedule(destination, "2030-11-15", "2030-11-18", [])
        assert "Gardens by the Bay" in schedule[0]["suggested_activity"]
        assert "Chinatown" in schedule[1]["suggested_activity"]
        assert "Little India" in schedule[2]["suggested_activity"]
        assert "National Gallery" in schedule[3]["suggested_activity"]
        assert all(day["source_url"] == "https://www.visitsingapore.com/" for day in schedule)


def test_singapore_high_risk_does_not_recommend_waterfront_walk():
    schedule = build_activity_schedule("SIN", "2030-11-15", "2030-11-15", [
        {"date": "2030-11-15", "risk_level": "high"},
    ])
    assert "waterfront walk" not in schedule[0]["suggested_activity"]
    assert "postpone outdoor" in schedule[0]["suggested_activity"]


def test_moderate_risk_includes_indoor_alternative():
    schedule = build_activity_schedule("NRT", "2030-11-15", "2030-11-15", [
        {"date": "2030-11-15", "risk_level": "moderate"},
    ])
    assert "indoor alternative" in schedule[0]["suggested_activity"]