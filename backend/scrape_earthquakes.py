"""
Scrape earthquake data from AFAD API for Istanbul region.
Updates earthquakes.json with last 24 hours of seismic activity.

Usage:
    python scrape_earthquakes.py          # fetch and update
    python scrape_earthquakes.py --dry    # fetch and print only (no file update)
"""
import sys
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import requests

# Başakşehir center coordinates
BASAKSEHIR_LAT = 41.07
BASAKSEHIR_LON = 28.67

# AFAD API base
API_BASE = "https://deprem.afad.gov.tr/apiv2/event/filter"

DATA_PATH = Path(__file__).parent / "data" / "earthquakes.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers using haversine formula."""
    R = 6371  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def magnitude_label(mag: float) -> str:
    """Return Turkish severity label for magnitude."""
    if mag < 3.0:
        return "hissedilmeyecek büyüklükte"
    elif mag < 4.0:
        return "hafif"
    elif mag < 5.0:
        return "orta şiddette"
    else:
        return "şiddetli"


def generate_summary(earthquakes: list) -> str:
    """Generate a Turkish summary of recent seismic activity."""
    if not earthquakes:
        return "Son 24 saatte İstanbul yakınında kayda değer deprem olmadı."

    count = len(earthquakes)
    max_mag = max(eq["magnitude"] for eq in earthquakes)
    max_eq = next(eq for eq in earthquakes if eq["magnitude"] == max_mag)

    if count == 1:
        return (
            f"Son 24 saatte İstanbul yakınında 1 deprem oldu: "
            f"{max_mag} büyüklüğünde, {max_eq['location']} "
            f"({magnitude_label(max_mag)})."
        )

    return (
        f"Son 24 saatte İstanbul yakınında {count} deprem oldu. "
        f"En büyüğü {max_mag} büyüklüğünde, {max_eq['location']} "
        f"({magnitude_label(max_mag)})."
    )


def fetch_earthquakes() -> dict:
    """Fetch last 24h earthquakes from AFAD API."""
    now = datetime.now()
    start = now - timedelta(hours=24)

    params = {
        "start": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "end": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "lat": 41.0,
        "lon": 28.7,
        "maxrad": 150000,  # 150km in meters
        "magmin": 2.0,
        "limit": 20,
        "orderby": "timedesc",
    }

    r = requests.get(API_BASE, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()

    raw = r.json()

    # AFAD returns a list directly
    if isinstance(raw, dict):
        # Sometimes wrapped in an object
        raw = raw.get("result", raw.get("data", []))

    earthquakes = []
    for eq in raw:
        try:
            lat = float(eq.get("latitude", 0))
            lon = float(eq.get("longitude", 0))
            mag = float(eq.get("magnitude", 0))
            depth = float(eq.get("depth", 0))
            location = eq.get("location", "Bilinmeyen konum")
            date_str = eq.get("date", "")
            eq_id = str(eq.get("id", ""))

            distance = round(haversine_km(BASAKSEHIR_LAT, BASAKSEHIR_LON, lat, lon), 1)

            earthquakes.append({
                "id": eq_id,
                "magnitude": mag,
                "depth_km": depth,
                "location": location,
                "distance_to_basaksehir_km": distance,
                "date_time": date_str,
                "lat": lat,
                "lon": lon,
            })
        except (ValueError, TypeError) as e:
            print(f"  Skipping malformed earthquake entry: {e}")
            continue

    # Sort by magnitude descending
    earthquakes.sort(key=lambda x: x["magnitude"], reverse=True)

    result = {
        "last_updated": now.strftime("%Y-%m-%d"),
        "source": "deprem.afad.gov.tr",
        "earthquakes": earthquakes,
        "summary": generate_summary(earthquakes),
    }

    return result


if __name__ == "__main__":
    dry_run = "--dry" in sys.argv

    print("AFAD Deprem API'den veri çekiliyor (son 24 saat, 150km yarıçap)...")

    try:
        data = fetch_earthquakes()
    except requests.exceptions.RequestException as e:
        print(f"HATA: AFAD API'ye erişilemedi: {e}")
        data = {
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "source": "deprem.afad.gov.tr",
            "earthquakes": [],
            "summary": "Deprem verisi şu an alınamıyor.",
            "error": str(e),
        }

    print(f"\n{data['summary']}")

    for eq in data["earthquakes"]:
        print(
            f"  M{eq['magnitude']} | {eq['depth_km']}km derinlik | "
            f"{eq['location']} | {eq['distance_to_basaksehir_km']}km uzaklık | "
            f"{eq['date_time']}"
        )

    if dry_run:
        print("\n[DRY RUN — dosya güncellenmedi]")
    else:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\n✓ {DATA_PATH} güncellendi.")
