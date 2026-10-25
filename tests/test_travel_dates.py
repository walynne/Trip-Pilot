import json
from datetime import date

from agents.extraction_agent import ExtractionAgent
from utils.travel_dates import extract_weekday_range


def test_next_monday_to_friday_resolves_to_same_week():
    dates = extract_weekday_range(
        "Plan a trip to Japan from next Monday to Friday",
        today=date(2026, 10, 24),
    )

    assert dates == ("2026-10-26", "2026-10-30")


def test_next_monday_return_friday_resolves_to_same_week():
    dates = extract_weekday_range(
        "I will travel from Hong Kong next Monday and return Friday",
        today=date(2026, 10, 25),
    )

    assert dates == ("2026-10-26", "2026-10-30")


def test_extraction_overrides_incorrect_llm_weekday_dates(monkeypatch):
    import agents.extraction_agent as extraction_module

    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 24)

    class FakeLLM:
        def chat(self, *_args):
            return json.dumps({
                "origin": "HKG",
                "destination": "NRT",
                "departure_date": "2026-10-30",
                "return_date": "2026-11-03",
            })

    monkeypatch.setattr(extraction_module, "date", FixedDate)
    extracted = ExtractionAgent(FakeLLM()).extract(
        "Plan a trip to Japan from next Monday to Friday"
    )

    assert extracted["departure_date"] == "2026-10-26"
    assert extracted["return_date"] == "2026-10-30"


def test_extraction_reads_explicit_hotel_nights(monkeypatch):
    import agents.extraction_agent as extraction_module

    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 25)

    class FakeLLM:
        def chat(self, *_args):
            return json.dumps({
                "origin": "HKG",
                "destination": "NRT",
                "departure_date": "2026-10-26",
                "return_date": "2026-10-30",
            })

    monkeypatch.setattr(extraction_module, "date", FixedDate)
    extracted = ExtractionAgent(FakeLLM()).extract(
        "I will travel from Hong Kong next Monday and return Friday. I need 1 night hotel."
    )

    assert extracted["departure_date"] == "2026-10-26"
    assert extracted["return_date"] == "2026-10-30"
    assert extracted["hotel_nights"] == 1