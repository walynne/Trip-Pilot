"""Service wrapper around the weather search tool."""

from tools.weather_search import WeatherSearchTool


class WeatherService:
    """Thin application-service layer for weather lookups."""

    def __init__(self, provider="open_meteo", *, mock_scenario="normal", thresholds=None):
        self.tool = WeatherSearchTool(
            provider,
            mock_scenario=mock_scenario,
            thresholds=thresholds,
        )

    def get_weather(self, location, start_date, end_date):
        return self.tool.search_weather(location, start_date, end_date)

    def search_weather(self, location, start_date, end_date):
        return self.get_weather(location, start_date, end_date)

    def get_forecast(self, location, start_date, end_date):
        return self.get_weather(location, start_date, end_date)


__all__ = ["WeatherService"]
