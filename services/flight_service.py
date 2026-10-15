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

        result = (
            self.tool.search_flights(
                origin,
                destination,
                departure_date,
                return_date
            )
        )

        flights = []

        for offer in result.get(
            "data",
            []
        )[:10]:

            try:

                slice_data = (
                    offer["slices"][0]
                )

                return_slice = None

                if len(
                    offer.get("slices", [])
                ) > 1:
                    return_slice = offer["slices"][1]

                segments = (
                    slice_data["segments"]
                )

                first = segments[0]

                last = segments[-1]

                carrier_codes, carrier_names = self._extract_carriers(
                    segments,
                    offer
                )

                converted_price, converted_currency = (
                    convert_amount(
                        offer["total_amount"],
                        offer["total_currency"],
                        DEFAULT_TARGET_CURRENCY
                    )
                )

                flights.append({

                    "airline":
                        ", ".join(carrier_codes),

                    "airlines":
                        carrier_codes,

                    "airline_names":
                        carrier_names,

                    "price":
                        converted_price,

                    "currency":
                        converted_currency,

                    "original_price":
                        offer["total_amount"],

                    "original_currency":
                        offer["total_currency"],

                    "stops":
                        max(
                            len(segments)-1,
                            0
                        ),

                    "departure":
                        first["departing_at"],

                    "arrival":
                        last["arriving_at"],

                    "origin":
                        first["origin"]["iata_code"],

                    "destination":
                        last["destination"]["iata_code"]
                })

                if return_slice:

                    return_segments = (
                        return_slice["segments"]
                    )

                    return_first = return_segments[0]

                    return_last = return_segments[-1]

                    flights[-1].update({

                        "return_stops":
                            max(
                                len(return_segments) - 1,
                                0
                            ),

                        "return_departure":
                            return_first["departing_at"],

                        "return_arrival":
                            return_last["arriving_at"],

                        "return_origin":
                            return_first["origin"]["iata_code"],

                        "return_destination":
                            return_last["destination"]["iata_code"]
                    })

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
            return [owner_name], [owner_name]

        return ["Unknown Airline"], ["Unknown Airline"]