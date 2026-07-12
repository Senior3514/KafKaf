"""Current weather via Open-Meteo — free, no API key required."""

import httpx

from kafkaf.core.skills.base import Skill

_WEATHER_CODES = {
    0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    71: "slight snow", 73: "moderate snow", 75: "heavy snow",
    80: "rain showers", 81: "moderate rain showers", 82: "violent rain showers",
    95: "thunderstorm",
}  # fmt: skip


class WeatherSkill(Skill):
    name = "weather"
    description = "Get current weather for a city name, e.g. 'Tel Aviv'."

    async def run(self, arg: str) -> str:
        city = arg.strip()
        if not city:
            return "error: provide a city name"

        async with httpx.AsyncClient(timeout=15.0) as client:
            geo = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1},
            )
            geo.raise_for_status()
            results = geo.json().get("results")
            if not results:
                return f"error: could not find a location named {city!r}"

            place = results[0]
            forecast = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "current_weather": "true",
                },
            )
            forecast.raise_for_status()
            current = forecast.json().get("current_weather", {})

        if not current:
            return "error: no current weather data available"

        code = current.get("weathercode")
        description = _WEATHER_CODES.get(code, f"code {code}")
        return (
            f"{place.get('name', city)}: {current.get('temperature')}°C, "
            f"{description}, wind {current.get('windspeed')} km/h"
        )
