"""
Scrape event data from Başakşehir Belediyesi.
Updates events.json with upcoming cultural and social events.

Usage:
    python scrape_events.py          # scrape and update
    python scrape_events.py --dry    # scrape and print only (no file update)
"""
import sys
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

sys.stdout.reconfigure(encoding='utf-8')

import requests
from bs4 import BeautifulSoup

# Primary source
BILET_URL = "https://bilet.basaksehir.bel.tr/etkinlik/etkinlikliste"

# Fallback source
KULTUR_URL = "https://kultursanat.basaksehir.bel.tr/etkinlikler"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

DATA_PATH = Path(__file__).parent / "data" / "events.json"


def parse_date(date_str: str) -> str:
    """Parse various Turkish date formats to ISO format."""
    date_str = date_str.strip().lower()
    
    # Remove Turkish day names
    days = ["pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar"]
    for day in days:
        date_str = date_str.replace(day, "").strip()
    
    # Common formats
    formats = [
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d %B %Y",  # 15 Mart 2026
        "%d %b %Y",  # 15 Mar 2026
    ]
    
    # Turkish month names
    months_tr = {
        "ocak": "01", "şubat": "02", "mart": "03", "nisan": "04",
        "mayıs": "05", "haziran": "06", "temmuz": "07", "ağustos": "08",
        "eylül": "09", "ekim": "10", "kasım": "11", "aralık": "12",
    }
    
    # Try to convert Turkish month names to numbers
    for tr_month, num in months_tr.items():
        if tr_month in date_str:
            date_str = date_str.replace(tr_month, num)
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return None


def parse_time(time_str: str) -> str:
    """Extract HH:MM from time string."""
    match = re.search(r'(\d{1,2}):(\d{2})', time_str)
    if match:
        return f"{int(match.group(1)):02d}:{match.group(2)}"
    return None


def extract_event_id(url: str) -> str:
    """Extract event ID from detail URL."""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if 'id' in params:
            return params['id'][0]
        # Try to extract from path
        match = re.search(r'/etkinlik/([^/]+)', url)
        if match:
            return match.group(1)
    except:
        pass
    return None


def scrape_bilet_site() -> list:
    """Scrape events from bilet.basaksehir.bel.tr."""
    print(f"Fetching events from: {BILET_URL}")
    
    r = requests.get(BILET_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    
    events = []
    
    # Try multiple selectors for event cards
    event_cards = (
        soup.find_all('div', class_=re.compile(r'event|etkinlik|card', re.I)) or
        soup.find_all('article') or
        soup.find_all('div', class_=re.compile(r'col-'))
    )
    
    print(f"Found {len(event_cards)} potential event cards")
    
    for card in event_cards[:20]:  # Limit to 20
        try:
            # Find title
            title_elem = (
                card.find(['h3', 'h2', 'h4', 'h5'], class_=re.compile(r'title|baslik', re.I)) or
                card.find('a', class_=re.compile(r'title', re.I)) or
                card.find(['h3', 'h2', 'h4'])
            )
            if not title_elem:
                continue
            
            title = title_elem.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            
            # Find link
            link_elem = card.find('a', href=True)
            if not link_elem:
                continue
            
            detail_url = urljoin(BILET_URL, link_elem['href'])
            event_id = extract_event_id(detail_url) or f"evt_{len(events)+1:03d}"
            
            # Find date
            date_elem = card.find(class_=re.compile(r'date|tarih', re.I))
            date_str = date_elem.get_text(strip=True) if date_elem else ""
            
            # Find time
            time_elem = card.find(class_=re.compile(r'time|saat', re.I))
            time_str = time_elem.get_text(strip=True) if time_elem else ""
            
            # Find location
            location_elem = card.find(class_=re.compile(r'location|yer|venue', re.I))
            location = location_elem.get_text(strip=True) if location_elem else "Başakşehir"
            
            # Find category
            category_elem = card.find(class_=re.compile(r'category|kategori|tag', re.I))
            category = category_elem.get_text(strip=True) if category_elem else "Etkinlik"
            
            # Check for "free" indicator
            is_free = bool(card.find(text=re.compile(r'ücretsiz|free', re.I)) or
                          card.find(class_=re.compile(r'free|ücretsiz', re.I)))
            
            event = {
                "id": event_id,
                "title": title,
                "date": parse_date(date_str) or (datetime.now() + timedelta(days=len(events))).strftime("%Y-%m-%d"),
                "time": parse_time(time_str) or "20:00",
                "location": location,
                "category": category,
                "description": "",  # Will be filled from detail page if needed
                "source_url": detail_url,
                "is_free": is_free,
            }
            
            events.append(event)
            
        except Exception as e:
            print(f"  Error parsing card: {e}")
            continue
    
    return events


def scrape_kultur_site() -> list:
    """Scrape events from kultursanat.basaksehir.bel.tr as fallback."""
    print(f"Trying fallback source: {KULTUR_URL}")
    
    r = requests.get(KULTUR_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    
    events = []
    
    # Look for event items
    items = soup.find_all(['article', 'div', 'li'], class_=re.compile(r'event|etkinlik|item', re.I))
    
    for i, item in enumerate(items[:15], 1):
        try:
            title_elem = item.find(['h3', 'h2', 'h4', 'a'])
            if not title_elem:
                continue
            
            title = title_elem.get_text(strip=True)
            link = title_elem.get('href', '') if title_elem.name == 'a' else ''
            
            if not link:
                link_elem = item.find('a', href=True)
                if link_elem:
                    link = link_elem['href']
            
            detail_url = urljoin(KULTUR_URL, link) if link else KULTUR_URL
            
            # Extract date from text
            text = item.get_text()
            date_match = re.search(r'(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?', text)
            if date_match:
                day, month, year = date_match.groups()
                year = year or datetime.now().year
                if len(str(year)) == 2:
                    year = 2000 + int(year)
                date_str = f"{int(year)}-{int(month):02d}-{int(day):02d}"
            else:
                date_str = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
            
            events.append({
                "id": f"evt_{i:03d}",
                "title": title,
                "date": date_str,
                "time": "20:00",
                "location": "Başakşehir Kültür Merkezi",
                "category": "Kültür",
                "description": "",
                "source_url": detail_url,
                "is_free": True,
            })
            
        except Exception as e:
            print(f"  Error parsing item: {e}")
            continue
    
    return events


def scrape_events() -> dict:
    """Scrape events from Başakşehir sources."""
    events = []
    source = "bilet.basaksehir.bel.tr"
    
    # Try primary source
    try:
        events = scrape_bilet_site()
    except requests.exceptions.RequestException as e:
        print(f"Primary source failed: {e}")
    
    # Fallback if needed
    if not events:
        try:
            events = scrape_kultur_site()
            source = "kultursanat.basaksehir.bel.tr"
        except requests.exceptions.RequestException as e:
            print(f"Fallback source failed: {e}")
    
    now = datetime.now()
    
    # Filter to future events only
    future_events = []
    for event in events:
        try:
            event_date = datetime.strptime(event["date"], "%Y-%m-%d")
            if event_date >= now - timedelta(days=1):  # Include today
                future_events.append(event)
        except (ValueError, TypeError):
            future_events.append(event)  # Keep if date parsing fails
    
    # Sort by date
    future_events.sort(key=lambda x: x.get("date", ""))
    
    # Limit to 20 events
    future_events = future_events[:20]
    
    if not future_events:
        # Return sample events if scraping fails
        return generate_sample_events()
    
    return {
        "last_updated": now.strftime("%Y-%m-%d"),
        "source": source,
        "events": future_events,
    }


def generate_sample_events() -> dict:
    """Generate sample events if scraping fails."""
    now = datetime.now()
    
    sample_events = [
        {
            "id": "evt_001",
            "title": "Ramazan Etkinlikleri",
            "description": "Başakşehir Belediyesi Ramazan programı: iftar çadırı, çocuk etkinlikleri, sahne gösterileri",
            "location": "Başakşehir Millet Bahçesi",
            "date": (now + timedelta(days=5)).strftime("%Y-%m-%d"),
            "time": "İftar saatinde",
            "organizer": "Başakşehir Belediyesi",
            "category": "ramazan",
            "is_free": True,
        },
        {
            "id": "evt_002",
            "title": "Bahçeşehir Gölet Parkı Çocuk Şenliği",
            "description": "Palyaço gösterisi, yüz boyama, balon sanatı. 3-12 yaş arası çocuklar için.",
            "location": "Bahçeşehir Gölet Parkı",
            "date": (now + timedelta(days=10)).strftime("%Y-%m-%d"),
            "time": "10:00 - 17:00",
            "organizer": "Başakşehir Belediyesi Kültür Müdürlüğü",
            "category": "cocuk",
            "is_free": True,
        },
        {
            "id": "evt_003",
            "title": "Ücretsiz Sağlık Taraması",
            "description": "Tansiyon, şeker, kolesterol ölçümü. Randevusuz.",
            "location": "Bahçeşehir 1. Kısım Aile Sağlığı Merkezi",
            "date": (now + timedelta(days=15)).strftime("%Y-%m-%d"),
            "time": "09:00 - 16:00",
            "organizer": "Başakşehir Belediyesi Sağlık İşleri",
            "category": "saglik",
            "is_free": True,
        },
    ]
    
    return {
        "last_updated": now.strftime("%Y-%m-%d"),
        "source": "mock_demo",
        "events": sample_events,
        "note": "Canlı etkinlik verisi şu an alınamıyor.",
    }


if __name__ == "__main__":
    dry_run = "--dry" in sys.argv
    
    try:
        data = scrape_events()
    except Exception as e:
        print(f"HATA: {e}")
        data = generate_sample_events()
        data["error"] = str(e)
    
    print(f"\nFound {len(data['events'])} events")
    if data.get('note'):
        print(f"Note: {data['note']}")
    
    for evt in data["events"][:5]:
        print(f"\n  [{evt['date']}] {evt['title']}")
        print(f"    {evt['location']} | {evt['time']}")
        if evt.get('is_free'):
            print(f"    Ücretsiz")
    
    if dry_run:
        print("\n[DRY RUN — dosya güncellenmedi]")
    else:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\n✓ {DATA_PATH} güncellendi.")
