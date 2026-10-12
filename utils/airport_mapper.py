CITY_TO_IATA = {

    "hong kong": "HKG",

    "tokyo": "NRT",

    "haneda": "HND",

    "narita": "NRT",

    "london": "LHR",

    "singapore": "SIN",

    "paris": "CDG",

    "new york": "JFK"
}


def is_iata_code(value):

    if not isinstance(value, str):
        return False

    value = value.strip()

    return len(value) == 3 and value.isalpha()



def normalize_airport(value):

    if not value:
        return value

    value = value.strip()

    if len(value) == 3:
        return value.upper()

    return CITY_TO_IATA.get(
        value.lower(),
        value
    )