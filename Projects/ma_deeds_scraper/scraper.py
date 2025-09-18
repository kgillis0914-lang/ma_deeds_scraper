import os
import json
import time
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# ----------------- Config -----------------
load_dotenv()

DATE_FROM = os.getenv("DATE_FROM", "2025-09-10")
DATE_TO = os.getenv("DATE_TO", "2025-09-10")
COUNTIES_FILE = os.getenv("COUNTIES_FILE", "counties.json")
OUT_CSV = os.getenv("OUT_CSV", "ma_deeds_data/records.csv")
ONLY_COUNTY = os.getenv("ONLY_COUNTY", "").strip()

DEFAULT_NAV_TIMEOUT = 90_000
DEFAULT_TIMEOUT = 30_000

# ----------------- Utils -----------------
def ensure_dirs():
    Path("ma_deeds_data").mkdir(parents=True, exist_ok=True)
    Path("downloads").mkdir(parents=True, exist_ok=True)

def load_counties():
    path = Path(COUNTIES_FILE)
    if not path.exists():
        raise FileNotFoundError(f"Counties config not found: {COUNTIES_FILE}")
    return json.loads(path.read_text())

def uniq(seq):
    out, seen = [], set()
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out

def abs_urls(base_url, hrefs):
    return [urljoin(base_url, h) for h in hrefs if h]

def launch_browser(p):
    browser = p.chromium.launch(
        headless=True,
        args=["--disable-dev-shm-usage", "--no-sandbox"],
    )
    page = browser.new_page()
    page.set_default_timeout(DEFAULT_TIMEOUT)
    page.set_default_navigation_timeout(DEFAULT_NAV_TIMEOUT)
    return browser, page

def settle(page, ms=1200):
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(ms)

def vendor_result_rows_to_detail_links(page, base_url):
    sels = [
        "a:has-text('View')",
        "a:has-text('Document')",
        "a[href*='DocView']",
        "a[href*='Document']",
        "a[href*='Details']",
        "a[href*='Viewer']",
    ]
    detail_links = []
    for sel in sels:
        for a in page.query_selector_all(sel):
            href = a.get_attribute("href")
            if href:
                detail_links.append(urljoin(base_url, href))
    return uniq(detail_links)

def find_pdf_on_detail(page):
    for sel in ["a[href$='.pdf']", "a[href*='.PDF']"]:
        el = page.query_selector(sel)
        if el:
            href = el.get_attribute("href")
            if href:
                return urljoin(page.url, href)
    for sel in [
        "a:has-text('PDF')",
        "a:has-text('Download')",
        "a:has-text('View')",
        "button:has-text('PDF')",
        "button:has-text('Download')",
        "button:has-text('View')",
    ]:
        el = page.query_selector(sel)
        if el:
            href = el.get_attribute("href")
            if href:
                return urljoin(page.url, href)
    return None

# ----------------- Vendor scrapers -----------------
def scrape_masslandrecords(page, url, county):
    print(f"[{county}] Opening {url}", flush=True)
    page.goto(url, timeout=DEFAULT_NAV_TIMEOUT)
    settle(page)

    for f in ["#RecordedDateFrom", "input[name='RecordedDateFrom']", "#FromDate"]:
        try:
            page.fill(f, DATE_FROM, timeout=3000)
            print(f"[{county}] Filled From via {f}", flush=True)
            break
        except:
            pass

    for t in ["#RecordedDateTo", "input[name='RecordedDateTo']", "#ToDate"]:
        try:
            page.fill(t, DATE_TO, timeout=3000)
            print(f"[{county}] Filled To via {t}", flush=True)
            break
        except:
            pass

    for btn in ["button#SearchBtn", "input[value='Search']", "button:has-text('Search')", "text=Search"]:
        try:
            page.click(btn, timeout=5000)
            print(f"[{county}] Clicked Search via {btn}", flush=True)
            break
        except:
            pass

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2500)

    detail_links = vendor_result_rows_to_detail_links(page, url)
    print(f"[{county}] Found {len(detail_links)} detail links", flush=True)

    rows = []
    for i, link in enumerate(detail_links, 1):
        try:
            page.goto(link, timeout=DEFAULT_NAV_TIMEOUT)
            settle(page)
            pdf_link = find_pdf_on_detail(page)
            rows.append({"county": county, "detail_url": link, "pdf_url": pdf_link or ""})
            print(f"[{county}] {i}/{len(detail_links)} PDF: {'yes' if pdf_link else 'no'}", flush=True)
        except Exception as e:
            print(f"[{county}] Detail {i} failed: {e}", flush=True)

    return rows

def scrape_browntech_barnstable(page, url, county):
    print(f"[{county}] Opening {url}", flush=True)
    page.goto(url, timeout=DEFAULT_NAV_TIMEOUT)
    settle(page)
    for f in ["input[name='FromDate']", "#FromDate"]:
        try:
            page.fill(f, DATE_FROM, timeout=2000); break
        except: pass
    for t in ["input[name='ToDate']", "#ToDate"]:
        try:
            page.fill(t, DATE_TO, timeout=2000); break
        except: pass
    for btn in ["button:has-text('Search')", "input[type='submit']"]:
        try:
            page.click(btn, timeout=4000); break
        except: pass

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2500)

    detail_links = vendor_result_rows_to_detail_links(page, url)
    rows = []
    for link in detail_links:
        try:
            page.goto(link, timeout=DEFAULT_NAV_TIMEOUT)
            settle(page)
            pdf_link = find_pdf_on_detail(page)
            rows.append({"county": county, "detail_url": link, "pdf_url": pdf_link or ""})
        except Exception as e:
            print(f"[{county}] detail fail: {e}", flush=True)
    return rows

def scrape_browntech_alis(page, url, county):
    return scrape_browntech_barnstable(page, url, county)

def scrape_kofile_titleview(page, url, county):
    print(f"[{county}] Opening {url}", flush=True)
    page.goto(url, timeout=DEFAULT_NAV_TIMEOUT)
    settle(page)
    for f in ["input#fromDate", "input[name='fromDate']"]:
        try:
            page.fill(f, DATE_FROM, timeout=2000); break
        except: pass
    for t in ["input#toDate", "input[name='toDate']"]:
        try:
            page.fill(t, DATE_TO, timeout=2000); break
        except: pass
    for btn in ["button:has-text('Search')", "input[type='submit']"]:
        try:
            page.click(btn, timeout=4000); break
        except: pass

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2500)

    detail_links = vendor_result_rows_to_detail_links(page, url)
    rows = []
    for link in detail_links:
        try:
            page.goto(link, timeout=DEFAULT_NAV_TIMEOUT)
            settle(page)
            pdf_link = find_pdf_on_detail(page)
            rows.append({"county": county, "detail_url": link, "pdf_url": pdf_link or ""})
        except Exception as e:
            print(f"[{county}] detail fail: {e}", flush=True)
    return rows

def scrape_kofile_taunton(page, url, county):
    return scrape_kofile_titleview(page, url, county)

def scrape_custom_link(page, url, county):
    print(f"[{county}] Opening {url}", flush=True)
    page.goto(url, timeout=DEFAULT_NAV_TIMEOUT)
    settle(page)
    pdfs = [a.get_attribute("href") for a in page.query_selector_all("a[href$='.pdf'], a[href*='.PDF']")]
    pdfs = abs_urls(url, uniq(pdfs))
    return [{"county": county, "detail_url": url, "pdf_url": p} for p in pdfs]

VENDOR_FUNCS = {
    "masslandrecords": scrape_masslandrecords,
    "browntech_barnstable": scrape_browntech_barnstable,
    "browntech_alis": scrape_browntech_alis,
    "kofile_titleview": scrape_kofile_titleview,
    "kofile_taunton": scrape_kofile_taunton,
    "custom_link": scrape_custom_link,
}

def run_one(county):
    vendor = county.get("vendor")
    url = county.get("search_url")
    name = county.get("name", "Unknown")
    func = VENDOR_FUNCS.get(vendor, scrape_custom_link)

    with sync_playwright() as p:
        browser, page = launch_browser(p)
        try:
            rows = func(page, url, name) or []
        except Exception as e:
            print(f"[{name}] ERROR: {e}", flush=True)
            rows = []
        finally:
            browser.close()
    return rows

def main():
    ensure_dirs()
    counties = load_counties()
    if ONLY_COUNTY:
        counties = [c for c in counties if c.get("name") == ONLY_COUNTY]
        print(f"ONLY_COUNTY set → running {len(counties)} county: {ONLY_COUNTY}", flush=True)
    else:
        print(f"Loaded {len(counties)} counties", flush=True)

    all_rows = []
    for c in counties:
        cname = c.get("name", "Unknown")
        print(f"Scraping {cname}…", flush=True)
        for attempt in range(1, 3):
            rows = run_one(c)
            if rows:
                print(f"  ✓ {cname}: {len(rows)} row(s)", flush=True)
                all_rows.extend(rows)
                break
            else:
                print(f"  ⚠ {cname}: attempt {attempt} returned 0 rows", flush=True)
                if attempt == 1:
                    time.sleep(1.5)

    df = pd.DataFrame(all_rows, columns=["county", "detail_url", "pdf_url"])
    out = Path(OUT_CSV)
    if out.exists():
        old = pd.read_csv(out)
        df = pd.concat([old, df], ignore_index=True)
        df = df.drop_duplicates(subset=["county", "detail_url", "pdf_url"])

    df.to_csv(out, index=False)
    print(f"Saved {len(df)} rows to {out}", flush=True)

if __name__ == "__main__":
    print("Starting scraper…", flush=True)
    main()
