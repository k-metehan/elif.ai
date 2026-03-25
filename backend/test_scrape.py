"""Test scraping eczaneler.gen.tr for nöbetçi data"""
import sys
import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

url = "https://www.eczaneler.gen.tr/nobetci-istanbul-basaksehir"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

try:
    r = requests.get(url, headers=headers, timeout=10)
    print(f"STATUS: {r.status_code}")

    if r.status_code == 200:
        soup = BeautifulSoup(r.text, "html.parser")

        # Dump raw HTML of each table
        tables = soup.find_all("table")
        for i, table in enumerate(tables):
            print(f"\n=== TABLE {i} RAW HTML (first 2000 chars) ===")
            print(str(table)[:2000])

        # Also look for non-table structures with pharmacy data
        print("\n=== SEARCHING FOR PHARMACY PATTERNS ===")
        for tag in soup.find_all(class_=True):
            classes = " ".join(tag.get("class", []))
            if any(x in classes.lower() for x in ["eczane", "pharmacy", "nobetci", "nobet"]):
                print(f"CLASS: {classes}")
                print(f"  TEXT: {tag.get_text(strip=True)[:200]}")

except Exception as e:
    import traceback
    traceback.print_exc()
