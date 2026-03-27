"""
Scrape electricity outage data for Başakşehir.
Tries BEDAŞ official site first, falls back to third-party aggregator.

Usage:
    python scrape_electricity.py          # scrape and update
    python scrape_electricity.py --dry    # scrape and print only (no file update)
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

# Primary source (BEDAŞ official)
BEDAS_URL = "https://www.bedas.com.tr/tr/tumKesintiler/istanbul-elektrik-kesintisi/"

# Fallback source (third-party aggregator)
FALLBACK_URL = "https://guncelkesintiler.com/istanbul/basaksehir/elektrik-kesintisi/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

DATA_PATH = Path(__file__).parent / "data" / "electricity.json"

PLANNED_KEYWORDS = ["bakım", "planlı", "çalışma", "yenileme", "devre", "tesis"]
UNPLANNED_KEYWORDS = ["arıza", "kesinti", "enerji yok", "elektrik yok"]


def is_cloudflare_blocked(html: str) -> bool:
    """Check if response is a Cloudflare challenge page."""
    cf_indicators = [
        "cf-browser-verification",
        "Just a moment",
        "Checking your browser",
        "DDoS protection by Cloudflare",
        "Enable JavaScript and cookies to continue",
    ]
    return any(indicator in html for indicator in cf_indicators)


def classify_outage(description: str) -> str:
    """Classify outage as planned or unplanned."""
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in PLANNED_KEYWORDS):
        return "planned"
    if any(kw in desc_lower for kw in UNPLANNED_KEYWORDS):
        return "unplanned"
    return "unknown"


def parse_date(date_str: str) -> str:
    """Parse various date formats to ISO format."""
    date_str = date_str.strip()
    
    formats = [
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%y",
        "%d/%m/%y",
        "%Y-%m-%d",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.year < 100:
                dt = dt.replace(year=2000 + dt.year)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return None


def parse_time_range(time_str: str) -> tuple:
    """Extract start and end times from a range string."""
    time_str = time_str.strip().lower()
    
    # Match patterns like "09:00 - 17:00" or "09:00/17:00"
    matches = re.findall(r'(\d{1,2}):(\d{2})', time_str)
    
    if len(matches) >= 2:
        start = f"{int(matches[0][0]):02d}:{matches[0][1]}"
        end = f"{int(matches[1][0]):02d}:{matches[1][1]}"
        return start, end
    elif len(matches) == 1:
        start = f"{int(matches[0][0]):02d}:{matches[0][1]}"
        return start, "23:59"
    
    return None, None


def scrape_bedas_direct() -> list:
    """Try to scrape from BEDAŞ official site."""
    print(f"Trying BEDAŞ official site: {BEDAS_URL}")
    
    r = requests.get(BEDAS_URL, headers=HEADERS, timeout=20)
    
    if is_cloudflare_blocked(r.text):
        print("  Blocked by Cloudflare protection")
        return None
    
    soup = BeautifulSoup(r.text, 'html.parser')
    outages = []
    
    # Look for outage table or list
    # BEDAŞ typically uses tables with class names like 'table', 'kesinti-table', etc.
    tables = soup.find_all('table')
    
    for table in tables:
        rows = table.find_all('tr')
        for row in rows[1:]:  # Skip header
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 4:
                try:
                    district = cells[0].get_text(strip=True)
                    
                    # Filter for Başakşehir only
                    if 'başakşehir' not in district.lower():
                        continue
                    
                    area = cells[1].get_text(strip=True)
                    date_text = cells[2].get_text(strip=True)
                    time_text = cells[3].get_text(strip=True)
                    reason = cells[4].get_text(strip=True) if len(cells) > 4 else "Bakım çalışması"
                    
                    date = parse_date(date_text)
                    start_time, end_time = parse_time_range(time_text)
                    
                    outages.append({
                        "district": district,
                        "affected_area": area,
                        "date": date or datetime.now().strftime("%Y-%m-%d"),
                        "start_time": start_time or "09:00",
                        "end_time": end_time or "17:00",
                        "reason": reason,
                        "type": classify_outage(reason),
                    })
                except Exception as e:
                    print(f"  Error parsing row: {e}")
                    continue
    
    return outages if outages else None


def parse_fallback_detail(url: str) -> dict:
    """Parse detail page from fallback aggregator."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        text = soup.get_text(separator='\n', strip=True)
        
        result = {
            "district": "Başakşehir",
            "affected_area": "",
            "date": None,
            "start_time": None,
            "end_time": None,
            "reason": "",
        }
        
        # Parse start/end times
        start_match = re.search(r'Başlangı[çc]\s*[:;]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if start_match:
            date_str = start_match.group(1)
            result["date"] = parse_date(date_str)
            result["start_time"], _ = parse_time_range(date_str)
        
        end_match = re.search(r'Biti[şs]\s*[:;]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if end_match:
            _, result["end_time"] = parse_time_range(end_match.group(1))
        
        # Parse affected area
        area_match = re.search(r'Bölge\s*[:;]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if area_match:
            result["affected_area"] = area_match.group(1).strip()
        
        # Parse reason
        reason_match = re.search(r'(?:Neden|Sebep|Açıklama)\s*[:;]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if reason_match:
            result["reason"] = reason_match.group(1).strip()
        
        return result
        
    except Exception as e:
        print(f"  Error parsing detail: {e}")
        return None


def scrape_fallback() -> list:
    """Scrape from third-party aggregator as fallback."""
    print(f"Trying fallback source: {FALLBACK_URL}")
    
    r = requests.get(FALLBACK_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    
    detail_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/istanbul/basaksehir/elektrik/' in href and 'kesinti' not in href.lower():
            if any(x in href.lower() for x in ['whatsapp', 'sosyal', 'facebook']):
                continue
            full_url = urljoin(FALLBACK_URL, href)
            detail_links.append(full_url)
    
    # Deduplicate and limit
    seen = set()
    detail_links = [x for x in detail_links if not (x in seen or seen.add(x))][:10]
    
    print(f"Found {len(detail_links)} detail pages")
    
    outages = []
    for i, url in enumerate(detail_links, 1):
        print(f"  [{i}/{len(detail_links)}] Scraping {url}")
        detail = parse_fallback_detail(url)
        
        if detail:
            outages.append({
                "district": detail.get("district", "Başakşehir"),
                "affected_area": detail.get("affected_area", "Belirtilmemiş"),
                "date": detail.get("date") or datetime.now().strftime("%Y-%m-%d"),
                "start_time": detail.get("start_time") or "09:00",
                "end_time": detail.get("end_time") or "17:00",
                "reason": detail.get("reason", "Bakım çalışması") or "Bakım çalışması",
                "type": classify_outage(detail.get("reason", "")),
                "source_url": url,
            })
        
        time.sleep(1)
    
    return outages


def scrape_electricity() -> dict:
    """Scrape electricity outages, trying multiple sources."""
    outages = None
    source = "bedas.com.tr"
    
    # Try BEDAŞ first
    try:
        outages = scrape_bedas_direct()
    except requests.exceptions.RequestException as e:
        print(f"  BEDAŞ request failed: {e}")
    
    # Fall back to aggregator if needed
    if not outages:
        try:
            outages = scrape_fallback()
            source = "guncelkesintiler.com"
        except requests.exceptions.RequestException as e:
            print(f"  Fallback request failed: {e}")
    
    now = datetime.now()
    
    if not outages:
        # Both failed — return empty with note
        return {
            "last_updated": now.strftime("%Y-%m-%d"),
            "source": source,
            "outages": [],
            "emergency_phone": "186",
            "note": "Elektrik kesintisi verisi şu an otomatik olarak alınamıyor. Güncel bilgi için BEDAŞ 186'yı arayın.",
        }
    
    # Filter out stale outages (ended more than 1 day ago)
    cutoff = now - timedelta(days=1)
    fresh_outages = []
    
    for outage in outages:
        try:
            end_date = datetime.strptime(outage.get("date", ""), "%Y-%m-%d")
            if end_date >= cutoff:
                fresh_outages.append(outage)
        except (ValueError, TypeError):
            fresh_outages.append(outage)  # Keep if date parsing fails
    
    return {
        "last_updated": now.strftime("%Y-%m-%d"),
        "source": source,
        "outages": fresh_outages,
        "emergency_phone": "186",
    }


if __name__ == "__main__":
    dry_run = "--dry" in sys.argv
    
    try:
        data = scrape_electricity()
    except Exception as e:
        print(f"HATA: Beklenmeyen hata: {e}")
        data = {
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "source": "bedas.com.tr",
            "outages": [],
            "emergency_phone": "186",
            "note": "Elektrik kesintisi verisi şu an alınamıyor. BEDAŞ 186'yı arayın.",
            "error": str(e),
        }
    
    print(f"\nFound {len(data['outages'])} electricity outages")
    if data.get('note'):
        print(f"Note: {data['note']}")
    
    for outage in data["outages"][:5]:  # Show first 5
        print(f"\n  [{outage['type'].upper()}] {outage['date']} {outage['start_time']}-{outage['end_time']}")
        print(f"    Bölge: {outage['affected_area']}")
        print(f"    Sebep: {outage['reason'][:50]}...")
    
    if dry_run:
        print("\n[DRY RUN — dosya güncellenmedi]")
    else:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\n✓ {DATA_PATH} güncellendi.")
