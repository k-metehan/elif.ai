"""
Scrape weather data from Open-Meteo API for Başakşehir.
Updates weather.json with current conditions and 3-day forecast.

Usage:
    python scrape_weather.py          # fetch and update
    python scrape_weather.py --dry    # fetch and print only (no file update)
"""
import sys
import json
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import requests

# Başakşehir coordinates
LAT = 41.07
LON = 28.67

API_URL = (
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    f"&current=temperature_2m,apparent_temperature,precipitation,weather_code,windspeed_10m"
    f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
    f"&timezone=Europe%2FIstanbul"
    f"&forecast_days=3"
)

DATA_PATH = Path(__file__).parent / "data" / "weather.json"

# WMO weather code → Turkish description
WEATHER_DESCRIPTIONS = {
    0: "Açık",
    1: "Az bulutlu",
    2: "Parçalı bulutlu",
    3: "Bulutlu",
    45: "Sisli",
    48: "Kırağılı sis",
    51: "Hafif çisenti",
    53: "Orta çisenti",
    55: "Yoğun çisenti",
    56: "Dondurucu hafif çisenti",
    57: "Dondurucu yoğun çisenti",
    61: "Hafif yağmur",
    63: "Orta yağmur",
    65: "Şiddetli yağmur",
    66: "Dondurucu hafif yağmur",
    67: "Dondurucu şiddetli yağmur",
    71: "Hafif kar",
    73: "Orta kar",
    75: "Yoğun kar",
    77: "Kar taneleri",
    80: "Hafif sağanak",
    81: "Orta sağanak",
    82: "Şiddetli sağanak",
    85: "Hafif kar sağanağı",
    86: "Yoğun kar sağanağı",
    95: "Gök gürültülü fırtına",
    96: "Dolu ile fırtına",
    99: "Şiddetli dolu fırtınası",
}


def get_weather_description(code: int) -> str:
    """Map WMO weather code to Turkish description."""
    return WEATHER_DESCRIPTIONS.get(code, f"Bilinmeyen hava kodu ({code})")


def fetch_weather() -> dict:
    """Fetch weather from Open-Meteo and return structured data."""
    r = requests.get(API_URL, timeout=15)
    r.raise_for_status()
    data = r.json()

    current = data.get("current", {})
    daily = data.get("daily", {})

    # Build current weather
    current_code = current.get("weather_code", 0)
    result = {
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "source": "open-meteo.com",
        "current": {
            "temperature": current.get("temperature_2m"),
            "feels_like": current.get("apparent_temperature"),
            "precipitation_mm": current.get("precipitation", 0),
            "weather_description": get_weather_description(current_code),
            "weather_code": current_code,
            "wind_speed_kmh": current.get("windspeed_10m", 0),
        },
        "forecast": [],
    }

    # Build forecast (skip today — index 0 — since it's in "current")
    times = daily.get("time", [])
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    rain_probs = daily.get("precipitation_probability_max", [])
    codes = daily.get("weather_code", [])

    for i in range(len(times)):
        if i == 0:
            continue  # skip today
        result["forecast"].append({
            "date": times[i],
            "high": highs[i] if i < len(highs) else None,
            "low": lows[i] if i < len(lows) else None,
            "rain_probability": rain_probs[i] if i < len(rain_probs) else None,
            "weather_description": get_weather_description(codes[i] if i < len(codes) else 0),
            "weather_code": codes[i] if i < len(codes) else 0,
        })

    return result


if __name__ == "__main__":
    dry_run = "--dry" in sys.argv

    print(f"Fetching weather for Başakşehir ({LAT}, {LON})...")
    weather = fetch_weather()

    cur = weather["current"]
    print(f"\nŞu an: {cur['temperature']}°C (hissedilen {cur['feels_like']}°C)")
    print(f"Durum: {cur['weather_description']}")
    print(f"Rüzgâr: {cur['wind_speed_kmh']} km/h")
    print(f"Yağış: {cur['precipitation_mm']} mm")

    for fc in weather["forecast"]:
        print(f"\n{fc['date']}: {fc['low']}°C — {fc['high']}°C, {fc['weather_description']}")
        print(f"  Yağmur olasılığı: %{fc['rain_probability']}")

    if dry_run:
        print("\n[DRY RUN — dosya güncellenmedi]")
    else:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(
            json.dumps(weather, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\n✓ {DATA_PATH} güncellendi.")
