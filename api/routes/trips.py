from fastapi import APIRouter

from agents.travel_planner_agent import TravelPlannerGraph

router = APIRouter()

travel_planner = TravelPlannerGraph()


@router.post("/trip-plan")
def plan_trip(request: dict):
    return travel_planner.run(request)


@router.post("/trip-plan/langgraph")
def plan_trip_langgraph(request: dict):
    return travel_planner.run(request)