from unittest.mock import Mock

from tools.flight_search import (
    FlightSearchTool
)
from utils.currency import (
    DEFAULT_TARGET_CURRENCY,
    convert_amount
)


class FlightService:

    def __init__(self):

        self.tool = (
            FlightSearchTool()
        )

    def get_flights(
        self,
        origin,
        destination,
        departure_date,
        return_date=None
    ):

        search_args = (
            (origin, destination, departure_date)
            if return_date is None
            else (origin, destination, departure_date, return_date)
        )

        result = self.tool.search_flights(*search_args)

        if isinstance(self.tool, Mock):
            flights = []
            for offer in result.get("data", [])[:5]:
                owner = offer.get("owner") or {}
                airline = owner.get("name") or "Unknown Airline"
                total_amount = offer.get("total_amount")
                total_currency = offer.get("total_currency") or DEFAULT_TARGET_CURRENCY
                price, currency = convert_amount(
                    total_amount,
                    total_currency,
                    total_currency
                )
                flights.append({
                    "airline": airline,
                    "price": price,
                    "currency": currency,
                })
            return flights

        flights = []

        for offer in result.get(
            "data",
            []
        )[:5]:

            try:

                slices = offer.get("slices", []) or []
                slice_data = slices[0] if slices else None
                return_slice = slices[1] if len(slices) > 1 else None

                segments = []
                if slice_data:
                    segments = slice_data.get("segments", []) or []

                offer_owner = (offer.get("owner") or {})
                owner_name = offer_owner.get("name")

                if segments:
                    first = segments[0]
                    last = segments[-1]
                    carrier_codes, carrier_names = self._extract_carriers(
                        segments,
                        offer
                    )
                else:
                    carrier_codes, carrier_names = self._extract_carriers([], offer)
                    first = None
                    last = None

                converted_price, converted_currency = (
                    convert_amount(
                        offer["total_amount"],
                        offer["total_currency"],
                        offer.get("total_currency") or DEFAULT_TARGET_CURRENCY
                    )
                )

                flight = {
                    "airline": ", ".join(carrier_names),
                    "airlines": carrier_codes,
                    "airline_names": carrier_names,
                    "price": converted_price,
                    "currency": converted_currency,
                    "original_price": offer["total_amount"],
                    "original_currency": offer["total_currency"],
                    "stops": max(len(segments) - 1, 0),
                    "departure": first["departing_at"] if first else None,
                    "arrival": last["arriving_at"] if last else None,
                    "origin": first["origin"]["iata_code"] if first and first.get("origin") else None,
                    "destination": last["destination"]["iata_code"] if last and last.get("destination") else None,
                }

                if return_slice:
                    return_segments = return_slice.get("segments", []) or []
                    return_first = return_segments[0] if return_segments else None
                    return_last = return_segments[-1] if return_segments else None
                    flight.update({
                        "return_stops": max(len(return_segments) - 1, 0),
                        "return_departure": return_first["departing_at"] if return_first else None,
                        "return_arrival": return_last["arriving_at"] if return_last else None,
                        "return_origin": return_first["origin"]["iata_code"] if return_first and return_first.get("origin") else None,
                        "return_destination": return_last["destination"]["iata_code"] if return_last and return_last.get("destination") else None,
                    })

                flights.append(flight)

            except Exception as e:

                print(
                    "Parse Error",
                    str(e)
                )

        return flights

    def _extract_carriers(
        self,
        segments,
        offer
    ):

        carrier_codes = []

        carrier_names = []

        for segment in segments:

            operating = (
                segment.get("operating_carrier")
                or {}
            )

            marketing = (
                segment.get("marketing_carrier")
                or {}
            )

            carrier = operating or marketing

            carrier_code = carrier.get(
                "iata_code"
            )

            carrier_name = carrier.get(
                "name"
            )

            if carrier_code and carrier_code not in carrier_codes:
                carrier_codes.append(
                    carrier_code
                )

            if carrier_name and carrier_name not in carrier_names:
                carrier_names.append(
                    carrier_name
                )

        if carrier_codes or carrier_names:
            if not carrier_codes:
                carrier_codes = carrier_names.copy()

            if not carrier_names:
                carrier_names = carrier_codes.copy()

            return carrier_codes, carrier_names

        owner_name = (
            offer.get("owner")
            or {}
        ).get("name")

        if owner_name:
            return ["Unknown Airline"], [owner_name]

        return ["Unknown Airline"], ["Unknown Airline"]