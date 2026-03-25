"""
Scrape nöbetçi eczane data from eczaneler.gen.tr for Başakşehir.
Updates pharmacies.json with today's duty pharmacies.

Usage:
    python scrape_nobetci.py          # scrape and update
    python scrape_nobetci.py --dry    # scrape and print only (no file update)
"""
import sys
import json
import re
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import requests
from bs4 import BeautifulSoup

URL = "https://www.eczaneler.gen.tr/nobetci-istanbul-basaksehir"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
DATA_PATH = Path(__file__).parent / "data" / "pharmacies.json"

# Known Bahçeşehir neighborhoods — filter pharmacies to these
BAHCESEHIR_KEYWORDS = [
    "bahçeşehir", "bahcesehir", "boğazköy", "bogazkoy",
    "altınşehir", "altinsehir", "kayaşehir", "kayasehir",
    "ispartakule", "başakşehir mah", "güvercintepe",
]


def is_bahcesehir_area(address: str) -> bool:
    """Check if address is in the greater Bahçeşehir area."""
    addr_lower = address.lower()
    return any(kw in addr_lower for kw in BAHCESEHIR_KEYWORDS)


def parse_phone(raw: str) -> str:
    """Normalize phone to 0212 XXX XX XX format."""
    digits = re.sub(r"[^\d]", "", raw)
    if len(digits) == 11 and digits.startswith("0"):
        return f"0{digits[1:4]} {digits[4:7]} {digits[7:9]} {digits[9:11]}"
    return raw.strip()


def scrape_nobetci() -> dict:
    """Scrape and return structured nöbetçi data."""
    r = requests.get(URL, headers=HEADERS, timeout=15)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table", class_="table")

    result = {
        "scraped_at": datetime.now().isoformat(),
        "source": URL,
        "periods": []
    }

    for table in tables:
        # Get the time period description
        period_div = table.find("div", class_="alert")
        period_text = period_div.get_text(strip=True) if period_div else "Unknown period"

        pharmacies = []
        rows = table.find_all("tr")

        for row in rows:
            # Skip header row
            if row.find("thead") or row.find(class_="thead-dark"):
                continue

            name_tag = row.find("span", class_="isim")
            if not name_tag:
                continue

            name = name_tag.get_text(strip=True)

            # Get address from col-lg-6
            addr_div = row.find("div", class_="col-lg-6")
            if addr_div:
                # Get main address (exclude the landmark note)
                landmark_div = addr_div.find("div", class_="py-2")
                landmark = ""
                if landmark_div:
                    landmark_span = landmark_div.find("span", class_="font-italic")
                    if landmark_span:
                        landmark = landmark_span.get_text(strip=True)
                    landmark_div.decompose()

                # Also check for badge (semt label)
                semt_span = addr_div.find("span", class_=re.compile(r"bg-s|badge"))
                semt = ""
                if semt_span:
                    semt = semt_span.get_text(strip=True)
                    semt_span.decompose()

                address = addr_div.get_text(strip=True)
            else:
                address = ""
                landmark = ""
                semt = ""

            # Get phone from col-lg-3 (not the first one which is the name)
            phone_divs = row.find_all("div", class_="col-lg-3")
            phone = ""
            for pd in phone_divs:
                text = pd.get_text(strip=True)
                if re.search(r"\d{3}.*\d{2}.*\d{2}", text):
                    phone = parse_phone(text)
                    break

            pharmacy = {
                "name": name,
                "address": address,
                "phone": phone,
                "landmark": landmark,
                "semt": semt,
                "is_bahcesehir": is_bahcesehir_area(address),
            }
            pharmacies.append(pharmacy)

        result["periods"].append({
            "description": period_text,
            "pharmacies": pharmacies
        })

    return result


def update_pharmacies_json(scraped: dict) -> None:
    """Replace pharmacies.json with ONLY today's nöbetçi pharmacies."""
    
    # Find today's period (the one with the most pharmacies)
    today_period = None
    for period in scraped["periods"]:
        if today_period is None or len(period["pharmacies"]) > len(today_period["pharmacies"]):
            today_period = period

    if not today_period:
        print("ERROR: No nöbetçi data found!")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Build fresh data with ONLY today's pharmacies
    fresh_data = {
        "mahalle": "Bahçeşehir",
        "ilce": "Başakşehir",
        "il": "İstanbul",
        "last_updated": today_str,
        "verified_by": "auto_scrape",
        "scrape_source": URL,
        "scrape_period": today_period["description"],
        "note": f"Bugünün nöbetçi eczaneleri: {today_period['description']}",
        "pharmacies": []
    }

    for idx, scraped_p in enumerate(today_period["pharmacies"], 1):
        fresh_data["pharmacies"].append({
            "id": f"bah_{idx:03d}",
            "name": scraped_p["name"],
            "address": scraped_p["address"],
            "phone": scraped_p["phone"],
            "lat": None,
            "lng": None,
            "is_duty_today": True,
            "duty_type": "nobetci",
            "duty_hours": {"start": "08:30", "end": "08:30"},
            "notes": scraped_p["landmark"],
            "semt": scraped_p["semt"],
            "verified_at": datetime.now().isoformat(),
        })

    # Write fresh data (REPLACES old file completely)
    DATA_PATH.write_text(
        json.dumps(fresh_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    duty_names = [p["name"] for p in fresh_data["pharmacies"]]
    print(f"Replaced pharmacies.json with {len(fresh_data['pharmacies'])} today's nöbetçi pharmacies")
    print(f"Period: {today_period['description']}")
    print(f"Today's nöbetçi: {', '.join(duty_names)}")


if __name__ == "__main__":
    dry_run = "--dry" in sys.argv

    print(f"Scraping {URL}...")
    data = scrape_nobetci()

    for period in data["periods"]:
        print(f"\n--- {period['description']} ---")
        for p in period["pharmacies"]:
            bah = " [BAHCESEHIR]" if p["is_bahcesehir"] else ""
            print(f"  {p['name']} | {p['phone']} | {p['address'][:60]}...{bah}")

    if dry_run:
        print("\n[DRY RUN — no file changes]")
    else:
        print("\nUpdating pharmacies.json...")
        update_pharmacies_json(data)
