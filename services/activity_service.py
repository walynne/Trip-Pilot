"""Destination advice based on published tourism guides, not live availability."""

from datetime import date, timedelta


# Curated suggestions, deliberately separate from date-specific weather data.
DESTINATION_GUIDES = {
    "tokyo": {
        "aliases": {"tokyo", "nrt", "hnd"},
        "source": "https://www.gotokyo.org/en/",
        "routes": [
            "Asakusa: visit Senso-ji and Nakamise shopping street, then explore Kappabashi. Add a Sumida River walk if conditions allow.",
            "Shibuya: explore PARCO, see the Scramble Crossing, and enjoy dinner near Miyashita Park. Consider SHIBUYA SKY if tickets and weather permit.",
        ],
    },
    "singapore": {
        "aliases": {"singapore", "sin"},
        "source": "https://www.visitsingapore.com/",
        "routes": [
            "Singapore Marina Bay: explore Gardens by the Bay, then consider a waterfront walk and dinner nearby. Check tickets for indoor conservatories separately.",
            "Singapore Chinatown: explore the neighborhood and try hawker food at Maxwell Food Centre. Allow time for a cafe or a nearby cultural visit.",
            "Singapore Little India and Kampong Glam: explore local shops and food, taking breaks from the heat. Use public transport between neighborhoods.",
            "Singapore museum day: consider the National Gallery or Asian Civilisations Museum, then a relaxed meal nearby. Check exhibitions and opening hours.",
        ],
    },
}


def _destination_advice(destination, index):
    normalized = str(destination).strip().casefold()
    guide = next((item for item in DESTINATION_GUIDES.values() if normalized in item["aliases"]), None)
    if guide and index < len(guide["routes"]):
        return guide["routes"][index], guide["source"]
    # No invented attractions or opening hours for destinations without a guide.
    ideas = [
        f"Settle into {destination} and explore the neighborhood near your accommodation. Try local food and identify nearby transport stops.",
        f"Plan a culture day in {destination}: choose a museum or historic district using the local tourism office's recommendations, with lunch nearby.",
        f"Explore a market or shopping neighborhood in {destination}, leaving time for a cafe and local food. Group stops within one area.",
        f"Consider a park or scenic walk in {destination} if conditions permit, with a nearby indoor alternative and time to rest.",
        f"Keep a flexible day in {destination} for personal interests, souvenirs, or places missed earlier. Avoid filling every hour.",
    ]
    return ideas[min(index, len(ideas) - 1)], guide["source"] if guide else None


def build_activity_schedule(destination, start_date, end_date, forecast, search_result=None):
    weather_by_date = {day.get("date"): day for day in forecast}
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    schedule = []
    for index in range(max(1, (end - start).days + 1)):
        day_date = (start + timedelta(days=index)).isoformat()
        weather = weather_by_date.get(day_date, {})
        risk = weather.get("risk_level") or "unknown"
        activity, source = _destination_advice(destination, index)
        places = (search_result or {}).get("places", [])
        live_place = places[index] if index < len(places) else None
        if live_place:
            activity = f"Consider visiting {live_place['name']} in {destination}. Plan a relaxed meal nearby and check travel time from your accommodation."
            source = live_place["source_url"]
        if risk == "high":
            activity = "Prioritize safety and follow local alerts; postpone outdoor sightseeing. Consider a nearby indoor activity only if travel is safe."
        elif risk == "moderate":
            activity += " Keep an indoor alternative and allow extra travel time."
        elif not weather:
            activity += " Weather forecast is unavailable for this date; check nearer departure."
        if index == 0:
            activity += " Arrival day: shorten this plan around your actual flight arrival and check-in."
        if day_date == end_date:
            activity += " Keep departure time free and allow an airport transfer buffer."
        schedule.append({
            **weather, "date": day_date,
            "condition": weather.get("condition") or "Flexible sightseeing plan",
            "risk_level": risk, "suggested_activity": activity,
            "source_url": source,
            "activity_source": "live_search" if live_place and risk != "high" else "offline_advice",
            "search_status": (search_result or {}).get("status", "not_requested"),
            "search_message": (search_result or {}).get("message"),
            "searched_at": (search_result or {}).get("searched_at"),
            "planning_note": "Suggested itinerary, not a reservation or live availability check. Confirm opening hours and tickets. Group nearby sights and leave rest time; on business trips, fit sightseeing around meetings.",
        })
    return schedule