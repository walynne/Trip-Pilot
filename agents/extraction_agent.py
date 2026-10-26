import json
import re
from datetime import date

from utils.airport_mapper import (
    normalize_airport
)
from utils.travel_dates import (
    extract_weekday_range,
    normalize_departure_date,
    normalize_return_date
)


class ExtractionAgent:

    def __init__(self, llm):

        self.llm = llm

    def extract(
        self,
        user_message
    ):

        today = date.today().isoformat()

        prompt = f"""
You are TripPilot's travel extraction agent.

Extract travel information from the user's request.

Today is {today}.

RULES:

1. Return ONLY valid JSON.
2. No markdown.
3. No explanations.
4. Use airport IATA codes.
5. Never return city names.
6. Convert natural language dates into YYYY-MM-DD format.
7. If date cannot be determined, return null.
8. Budget must be numeric.
9. Preferences must be an array.
10. Never return a past departure date.
11. If the user does not specify a year, choose the next future occurrence.
12. If the user mentions a return trip, populate return_date.
13. Never return a return_date earlier than departure_date.
14. If the user specifies a hotel stay duration, return hotel_nights as an integer.

Date Examples:

"15 Nov 2026"
→ "2026-11-15"

"November 15, 2026"
→ "2026-11-15"

"next Monday"
→ convert to actual date

"tomorrow"
→ convert to actual date

"in 2 weeks"
→ convert to actual date

Airport Examples:

Hong Kong → HKG
Tokyo → NRT
Haneda → HND
Narita → NRT
London → LHR
Singapore → SIN
New York → JFK
Paris → CDG

Output Schema:

{{
  "intent": "flight_search",
  "origin": "HKG",
  "destination": "NRT",
  "departure_date": "2026-11-15",
  "return_date": null,
    "hotel_nights": null,
  "budget": 2500,
  "preferences": []
}}

Examples

User:
Fly from Hong Kong to Tokyo tomorrow

Output:
{{
  "intent": "flight_search",
  "origin": "HKG",
  "destination": "NRT",
  "departure_date": "2026-10-13",
  "return_date": null,
  "budget": null,
  "preferences": []
}}

User:
Need a flight from Hong Kong to London on 15 Nov 2026

Output:
{{
  "intent": "flight_search",
  "origin": "HKG",
  "destination": "LHR",
  "departure_date": "2026-11-15",
  "return_date": null,
  "budget": null,
  "preferences": []
}}

User:
I need to go to Tokyo next Monday

Output:
{{
  "intent": "flight_search",
  "origin": "HKG",
  "destination": "NRT",
  "departure_date": "ACTUAL_DATE",
  "return_date": null,
  "budget": null,
  "preferences": []
}}

User:
I want to go to Tokyo next Monday and come back Friday

Output:
{{
  "intent": "flight_search",
  "origin": "HKG",
  "destination": "NRT",
  "departure_date": "ACTUAL_NEXT_MONDAY_DATE",
  "return_date": "ACTUAL_NEXT_FRIDAY_DATE",
  "budget": null,
  "preferences": []
}}

User Request:

{user_message}

Return JSON only.
"""

        response = self.llm.chat(
            "Travel extraction specialist",
            prompt
        )

        print("\nRAW EXTRACTION")
        print(response)

        try:

            trip = json.loads(
                response
            )

        except Exception:

            match = re.search(
                r"\{.*\}",
                response,
                re.DOTALL
            )

            if not match:
                raise Exception(
                    "Cannot parse extraction response"
                )

            trip = json.loads(
                match.group()
            )

        trip["origin"] = normalize_airport(
            trip.get("origin")
        )

        trip["destination"] = normalize_airport(
            trip.get("destination")
        )

        trip["departure_date"] = normalize_departure_date(
            trip.get("departure_date")
        )

        trip["return_date"] = normalize_return_date(
            trip.get("return_date")
        )

        reference_day = date.today()
        weekday_range = extract_weekday_range(user_message, today=reference_day)
        if weekday_range:
            trip["departure_date"], trip["return_date"] = weekday_range

        trip["hotel_nights"] = None
        hotel_nights = re.search(r"\b(\d{1,2})\s+nights?\b", user_message, re.IGNORECASE)
        if hotel_nights:
            trip["hotel_nights"] = int(hotel_nights.group(1))

        if weekday_range:
            departure, return_date = weekday_range
            date_diff = (date.fromisoformat(return_date) - date.fromisoformat(departure)).days
            if date_diff > 0 and trip.get("hotel_nights") is None:
                trip["hotel_nights"] = date_diff

        return trip