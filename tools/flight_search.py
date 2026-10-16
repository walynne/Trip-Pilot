import requests

from tools.duffel_client import (
    DuffelClient
)
from utils.travel_dates import (
    ensure_future_departure_date,
    ensure_valid_return_date
)


class FlightSearchTool:

    def __init__(self):

        self.client = DuffelClient()

    def search_flights(
        self,
        origin,
        destination,
        departure_date,
        return_date=None
    ):

        departure_date = ensure_future_departure_date(
            departure_date
        )

        return_date = ensure_valid_return_date(
            departure_date,
            return_date
        )

        slices = [

            {
                "origin":
                    origin,

                "destination":
                    destination,

                "departure_date":
                    departure_date
            }

        ]

        if return_date:
            slices.append({
                "origin":
                    destination,

                "destination":
                    origin,

                "departure_date":
                    return_date
            })

        payload = {

            "data": {

                "slices": slices,

                "passengers": [
                    {
                        "type": "adult"
                    }
                ],

                "cabin_class":
                    "economy"
            }
        }

        print(payload)

        response = requests.post(
            f"{self.client.base_url}/air/offer_requests",
            headers=self.client.headers,
            json=payload
        )

        print(response.text)

        response.raise_for_status()

        offer_request = response.json()

        offer_request_id = (
            offer_request["data"]["id"]
        )

        offers = requests.get(
            f"{self.client.base_url}/air/offers",
            headers=self.client.headers,
            params={
                "offer_request_id":
                    offer_request_id
            }
        )

        offers.raise_for_status()

        return offers.json()