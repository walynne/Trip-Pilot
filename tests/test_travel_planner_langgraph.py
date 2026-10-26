from agents.travel_planner_agent import TravelPlannerGraph


def test_hotel_search_preserves_display_data(monkeypatch):
    graph = TravelPlannerGraph()
    hotel = {
        "status": "success",
        "options": [{"name": "Singapore hotel", "pricing": {"total": "450.00", "currency": "SGD"}}],
        "budget_total": 450,
        "currency": "SGD",
        "check_in": "2026-11-15",
        "check_out": "2026-11-18",
    }
    hotel["recommended"] = hotel["options"][0]
    plan = {
        "hotel": hotel,
        "summary": {"destination": "Singapore"},
        "schedule": [{"date": "2026-11-15"}],
    }
    monkeypatch.setattr(graph.planner_agent, "plan_trip", lambda request: plan)

    result = graph._hotel_search_node({"trip_details": {"destination": "SIN"}})

    assert result["hotel_options"] == hotel["options"]
    assert result["hotel"] == hotel
    assert result["summary"] == plan["summary"]
    assert result["schedule"] == plan["schedule"]


def test_travel_planner_graph_has_expected_sequence():
    graph = TravelPlannerGraph()
    node_names = [name for name in graph.graph.nodes.keys() if name != "__start__"]

    assert node_names[:9] == [
        "travel_planner_agent",
        "flight_search_node",
        "hotel_search_node",
        "weather_node",
        "policy_validation_node",
        "budget_optimization_node",
        "approval_node",
        "booking_node",
        "final_itinerary",
    ]


def test_travel_planner_graph_runs_end_to_end_with_sample_request():
    graph = TravelPlannerGraph()
    result = graph.run({
        "origin": "JFK",
        "destination": "LHR",
        "departure_date": "2026-11-01",
        "return_date": "2026-11-05",
        "guests": 1,
    })

    assert result["final_itinerary"]["origin"] == "JFK"
    assert result["final_itinerary"]["destination"] == "LHR"
    assert "status" in result["final_itinerary"]
    assert "weather" in result["final_itinerary"]


def test_travel_planner_graph_includes_weather_node():
    graph = TravelPlannerGraph()
    node_names = [name for name in graph.graph.nodes.keys() if name != "__start__"]
    assert "weather_node" in node_names
