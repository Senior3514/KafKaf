"""Current weather via Open-Meteo — free, no API key required."""

from kafkaf.core.skills.base import Skill
from kafkaf.core.skills.net_utils import TTLCache, get_with_retry

_cache = TTLCache(ttl_seconds=600)  # weather doesn't change meaningfully faster than this

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

        cache_key = city.lower()
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        geo = await get_with_retry(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
        )
        geo.raise_for_status()
        results = geo.json().get("results")
        if not results:
            return f"error: could not find a location named {city!r}"

        place = results[0]
        forecast = await get_with_retry(
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
        result = (
            f"{place.get('name', city)}: {current.get('temperature')}°C, "
            f"{description}, wind {current.get('windspeed')} km/h"
        )
        _cache.set(cache_key, result)
        return result
