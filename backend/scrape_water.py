"""
Scrape water outage data from guncelkesintiler.com for Başakşehir.
Updates water.json with current and upcoming outages.

Usage:
    python scrape_water.py          # scrape and update
    python scrape_water.py --dry    # scrape and print only (no file update)
"""
import sys
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

sys.stdout.reconfigure(encoding='utf-8')

import requests
from bs4 import BeautifulSoup

INDEX_URL = "https://guncelkesintiler.com/istanbul/basaksehir/su-kesintisi/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

DATA_PATH = Path(__file__).parent / "data" / "water.json"

DATE_FORMATS = [
    "%d-%m-%Y",
    "%d/%m %Y",
    "%d/%m/%Y",
    "%d.%m.%Y",
    "%d-%m-%y",
    "%d/%m/%y",
]

PLANNED_KEYWORDS = ["bakım", "planlı", "depo", "çalışma", "terfi", "hat yenileme", "yenileme"]
UNPLANNED_KEYWORDS = ["arıza", "boru", "patlak", "kırık", "acil", "kaçak"]


def classify_outage(description: str) -> str:
    """Classify outage as planned or unplanned based on keywords."""
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in PLANNED_KEYWORDS):
        return "planned"
    if any(kw in desc_lower for kw in UNPLANNED_KEYWORDS):
        return "unplanned"
    return "unknown"


def parse_date(date_str: str) -> str:
    """Parse various date formats to ISO format (YYYY-MM-DD)."""
    date_str = date_str.strip()
    
    # Remove Turkish day names
    turkish_days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    for day in turkish_days:
        date_str = date_str.replace(day, "").replace(day.lower(), "").strip()
    
    # Clean up common variations
    date_str = date_str.replace("Saati :", "").replace("Saat :", "").replace("Saat:", "").strip()
    date_str = re.sub(r'\s+', ' ', date_str).strip()
    
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Assume years 26-99 are 2026-2099
            if dt.year < 100:
                dt = dt.replace(year=2000 + dt.year)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return None


def parse_time(time_str: str) -> str:
    """Extract HH:MM from various time formats."""
    time_str = time_str.strip()
    
    # Remove seconds if present
    time_str = re.sub(r':\d{2}$', '', time_str)
    
    # Try to find HH:MM pattern
    match = re.search(r'(\d{1,2}):(\d{2})', time_str)
    if match:
        hour = int(match.group(1))
        minute = match.group(2)
        if 0 <= hour <= 23:
            return f"{hour:02d}:{minute}"
    
    return None


def parse_detail_page(url: str) -> dict:
    """Parse a single outage detail page."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Get all text content
        text = soup.get_text(separator='\n', strip=True)
        
        result = {
            "start_date": None,
            "end_date": None,
            "start_time": None,
            "end_time": None,
            "neighborhoods": [],
            "reason": "",
            "district": "Başakşehir",
        }
        
        # Parse start time
        start_match = re.search(r'Kesintinin\s+Başlama\s+Zaman[ıi]\s*[:;]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if start_match:
            start_text = start_match.group(1)
            result["start_date"] = parse_date(start_text)
            result["start_time"] = parse_time(start_text)
        
        # Parse end time
        end_match = re.search(r'Kesintinin\s+Bitiş\s+Vakti\s*[:;]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if end_match:
            end_text = end_match.group(1)
            result["end_date"] = parse_date(end_text)
            result["end_time"] = parse_time(end_text)
        
        # Parse neighborhoods
        neighborhood_match = re.search(r'Su\s+Kesintisi\s+Yaşanacak\s+Bölgeler\s*[:;]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if neighborhood_match:
            neighborhoods_text = neighborhood_match.group(1)
            # Split by common separators
            neighborhoods = re.split(r'[,;]|\s+ve\s+', neighborhoods_text)
            result["neighborhoods"] = [n.strip() for n in neighborhoods if n.strip()]
        
        # Parse reason/description
        desc_match = re.search(r'Meydana\s+Gelen\s+Kesintinin\s+Açıklamas[ıi]\s*[:;]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if desc_match:
            result["reason"] = desc_match.group(1).strip()
        
        # Parse district
        district_match = re.search(r'[İi]l[çc]e\s*[:;]\s*(.+?)(?:\n|$)', text)
        if district_match:
            result["district"] = district_match.group(1).strip()
        
        return result
        
    except Exception as e:
        print(f"  Error parsing detail page {url}: {e}")
        return None


def scrape_water_outages() -> dict:
    """Scrape water outages from guncelkesintiler.com."""
    print(f"Fetching index page: {INDEX_URL}")
    
    r = requests.get(INDEX_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # Find all detail links
    detail_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        # Look for Başakşehir water detail pages
        if '/istanbul/basaksehir/su/' in href and '/su-kesintisi/' not in href:
            # Skip promo/social links
            if any(x in href.lower() for x in ['whatsapp', 'sosyal-medya', 'facebook', 'twitter']):
                continue
            full_url = urljoin(INDEX_URL, href)
            detail_links.append(full_url)
    
    # Remove duplicates while preserving order
    seen = set()
    detail_links = [x for x in detail_links if not (x in seen or seen.add(x))]
    
    # Limit to last 10
    detail_links = detail_links[:10]
    print(f"Found {len(detail_links)} detail pages to scrape")
    
    outages = []
    now = datetime.now()
    cutoff_date = now - timedelta(days=2)  # Skip outages older than 2 days
    
    for i, url in enumerate(detail_links, 1):
        print(f"  [{i}/{len(detail_links)}] Scraping {url}")
        detail = parse_detail_page(url)
        
        if detail:
            # Check if end date is in the past (stale)
            if detail.get("end_date"):
                try:
                    end_dt = datetime.strptime(detail["end_date"], "%Y-%m-%d")
                    if end_dt < cutoff_date:
                        print(f"    Skipping stale outage (ended {detail['end_date']})")
                        continue
                except ValueError:
                    pass
            
            outage = {
                "id": f"su_{i:03d}",
                "type": classify_outage(detail.get("reason", "")),
                "district": detail.get("district", "Başakşehir"),
                "neighborhoods": detail.get("neighborhoods", []),
                "date": detail.get("start_date") or now.strftime("%Y-%m-%d"),
                "start_time": detail.get("start_time") or "00:00",
                "end_time": detail.get("end_time") or "23:59",
                "reason": detail.get("reason", "Bakım çalışması"),
                "source_url": url,
            }
            outages.append(outage)
        
        time.sleep(1)  # Be polite
    
    result = {
        "last_updated": now.strftime("%Y-%m-%d"),
        "source": "guncelkesintiler.com",
        "outages": outages,
    }
    
    return result


if __name__ == "__main__":
    dry_run = "--dry" in sys.argv
    
    try:
        data = scrape_water_outages()
    except requests.exceptions.RequestException as e:
        print(f"HATA: Siteye erişilemedi: {e}")
        data = {
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "source": "guncelkesintiler.com",
            "outages": [],
            "error": str(e),
        }
    
    print(f"\nFound {len(data['outages'])} water outages")
    
    for outage in data["outages"]:
        print(f"\n  [{outage['type'].upper()}] {outage['date']} {outage['start_time']}-{outage['end_time']}")
        print(f"    Bölgeler: {', '.join(outage['neighborhoods'])}")
        print(f"    Sebep: {outage['reason'][:60]}...")
    
    if dry_run:
        print("\n[DRY RUN — dosya güncellenmedi]")
    else:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\n✓ {DATA_PATH} güncellendi.")
