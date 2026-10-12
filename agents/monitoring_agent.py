import json


class MonitoringAgent:

    def __init__(self, llm):

        self.llm = llm

    def detect(
        self,
        trip,
        flights
    ):

        if not flights:

            return {

                "type":
                    "NO_FLIGHTS",

                "severity":
                    "HIGH",

                "message":
                    "No flights available"
            }

        return {

            "type":
                "NORMAL",

            "severity":
                "LOW",

            "message":
                "Trip monitoring active"
        }

    def analyse(
        self,
        trip,
        issue
    ):

        prompt = f"""
You are TripPilot Monitoring Agent.

Trip:

{json.dumps(trip, indent=2)}

Issue:

{json.dumps(issue, indent=2)}

Provide:

1. Risk assessment
2. Business impact
3. Recommended action
4. Should trip be replanned?
"""

        return self.llm.chat(
            "Travel monitoring specialist",
            prompt
        )