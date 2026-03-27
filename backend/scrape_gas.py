"""
Scrape natural gas outage data for Başakşehir.
İGDAŞ is heavily protected, so this tries third-party sources first.

Usage:
    python scrape_gas.py          # scrape and update
    python scrape_gas.py --dry    # scrape and print only (no file update)
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

# İGDAŞ official (likely to be blocked)
IGDAS_URL = "https://igdas.istanbul/gaz-kesme-durumu"

# Third-party fallback
FALLBACK_URL = "https://guncelkesintiler.com/istanbul/basaksehir/dogalgaz-kesintisi/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

DATA_PATH = Path(__file__).parent / "data" / "gas.json"

PLANNED_KEYWORDS = ["bakım", "planlı", "çalışma", "hat", "yenileme"]
UNPLANNED_KEYWORDS = ["arıza", "kaçak", "acil", "kaza"]


def is_blocked_response(html: str) -> bool:
    """Check if response indicates blocking/WAF."""
    indicators = [
        "access denied",
        "waf",
        "cloudflare",
        "captcha",
        "güvenlik",
        "engellendi",
    ]
    return any(ind in html.lower() for ind in indicators)


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
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return None


def parse_time_range(time_str: str) -> tuple:
    """Extract start and end times."""
    matches = re.findall(r'(\d{1,2}):(\d{2})', time_str)
    
    if len(matches) >= 2:
        start = f"{int(matches[0][0]):02d}:{matches[0][1]}"
        end = f"{int(matches[1][0]):02d}:{matches[1][1]}"
        return start, end
    elif len(matches) == 1:
        start = f"{int(matches[0][0]):02d}:{matches[0][1]}"
        return start, None
    
    return None, None


def parse_fallback_detail(url: str) -> dict:
    """Parse gas outage detail from third-party site."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        text = soup.get_text(separator='\n', strip=True)
        
        result = {
            "district": "Başakşehir",
            "neighborhoods": [],
            "date": None,
            "start_time": None,
            "end_time": None,
            "reason": "",
        }
        
        # Parse neighborhoods
        area_match = re.search(r'(?:Bölge|Mahalle|Yer)\s*[:;]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if area_match:
            areas_text = area_match.group(1)
            neighborhoods = re.split(r'[,;]|\s+ve\s+', areas_text)
            result["neighborhoods"] = [n.strip() for n in neighborhoods if n.strip()]
        
        # Parse date/time
        date_match = re.search(r'(?:Tarih|Zaman|Başlangı[çc])\s*[:;]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if date_match:
            date_str = date_match.group(1)
            result["date"] = parse_date(date_str)
            result["start_time"], result["end_time"] = parse_time_range(date_str)
        
        # Parse reason
        reason_match = re.search(r'(?:Neden|Sebep|Açıklama)\s*[:;]\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if reason_match:
            result["reason"] = reason_match.group(1).strip()
        
        return result
        
    except Exception as e:
        print(f"  Error parsing detail: {e}")
        return None


def scrape_fallback() -> list:
    """Try scraping from third-party aggregator."""
    print(f"Trying third-party source: {FALLBACK_URL}")
    
    try:
        r = requests.get(FALLBACK_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        
        if is_blocked_response(r.text):
            print("  Blocked by WAF/protection")
            return None
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        detail_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/istanbul/basaksehir/dogalgaz/' in href:
                if any(x in href.lower() for x in ['whatsapp', 'sosyal', 'facebook']):
                    continue
                full_url = urljoin(FALLBACK_URL, href)
                detail_links.append(full_url)
        
        # Deduplicate and limit
        seen = set()
        detail_links = [x for x in detail_links if not (x in seen or seen.add(x))][:8]
        
        print(f"Found {len(detail_links)} gas outage detail pages")
        
        outages = []
        for i, url in enumerate(detail_links, 1):
            print(f"  [{i}/{len(detail_links)}] Scraping {url}")
            detail = parse_fallback_detail(url)
            
            if detail:
                outages.append({
                    "id": f"gaz_{i:03d}",
                    "type": classify_outage(detail.get("reason", "")),
                    "district": detail.get("district", "Başakşehir"),
                    "neighborhoods": detail.get("neighborhoods", []),
                    "date": detail.get("date") or datetime.now().strftime("%Y-%m-%d"),
                    "start_time": detail.get("start_time") or "09:00",
                    "end_time": detail.get("end_time") or "17:00",
                    "reason": detail.get("reason", "Bakım çalışması") or "Bakım çalışması",
                    "source_url": url,
                })
            
            time.sleep(1)
        
        return outages
        
    except requests.exceptions.RequestException as e:
        print(f"  Fallback request failed: {e}")
        return None


def scrape_igdas() -> list:
    """Try scraping from İGDAŞ official site (likely to fail)."""
    print(f"Trying İGDAŞ official site: {IGDAS_URL}")
    
    try:
        r = requests.get(IGDAS_URL, headers=HEADERS, timeout=15)
        
        if is_blocked_response(r.text):
            print("  Blocked by WAF/protection")
            return None
        
        # If we got here, try to parse (unlikely)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Look for outage information
        # This is speculative as we couldn't research the actual HTML
        outages = []
        
        print("  İGDAŞ site accessible but parsing not implemented (WAF usually blocks)")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"  İGDAŞ request failed: {e}")
        return None


def scrape_gas() -> dict:
    """Scrape gas outages with fallback strategy."""
    outages = None
    
    # Try İGDAŞ first (unlikely to work)
    outages = scrape_igdas()
    source = "igdas.istanbul"
    
    # Fall back to third-party
    if not outages:
        outages = scrape_fallback()
        source = "guncelkesintiler.com"
    
    now = datetime.now()
    
    if not outages:
        # Both failed — return minimal data with emergency number
        return {
            "last_updated": now.strftime("%Y-%m-%d"),
            "source": "igdas.istanbul",
            "outages": [],
            "emergency_phone": "187",
            "note": "Doğalgaz kesintisi verisi şu an otomatik olarak alınamıyor. Güncel bilgi için İGDAŞ 187'yi arayın.",
        }
    
    # Filter stale outages
    cutoff = now - timedelta(days=1)
    fresh_outages = []
    
    for outage in outages:
        try:
            end_date = datetime.strptime(outage.get("date", ""), "%Y-%m-%d")
            if end_date >= cutoff:
                fresh_outages.append(outage)
        except (ValueError, TypeError):
            fresh_outages.append(outage)
    
    return {
        "last_updated": now.strftime("%Y-%m-%d"),
        "source": source,
        "outages": fresh_outages,
        "emergency_phone": "187",
    }


if __name__ == "__main__":
    dry_run = "--dry" in sys.argv
    
    try:
        data = scrape_gas()
    except Exception as e:
        print(f"HATA: {e}")
        data = {
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "source": "igdas.istanbul",
            "outages": [],
            "emergency_phone": "187",
            "note": "Doğalgaz kesintisi verisi şu an alınamıyor. İGDAŞ 187'yi arayın.",
            "error": str(e),
        }
    
    print(f"\nFound {len(data['outages'])} gas outages")
    if data.get('note'):
        print(f"Note: {data['note']}")
    
    for outage in data["outages"]:
        print(f"\n  [{outage['type'].upper()}] {outage['date']} {outage['start_time']}-{outage['end_time']}")
        print(f"    Bölgeler: {', '.join(outage['neighborhoods'])}")
    
    print(f"\nAcil durum: İGDAŞ {data['emergency_phone']}")
    
    if dry_run:
        print("\n[DRY RUN — dosya güncellenmedi]")
    else:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\n✓ {DATA_PATH} güncellendi.")
