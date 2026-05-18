#!/usr/bin/env python3
"""Cloudflare'a takılmadan scimagojr.com'dan quartile verisi çeker.

Kullanım:
    python3 scrape_uc.py journals.txt output.json
    xvfb-run --auto-servernum python3 scrape_uc.py journals.txt output.json
"""
import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlparse, parse_qs

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE = "https://www.scimagojr.com"
logger = logging.getLogger("scraper")


def setup_logging(level: int = logging.INFO):
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%Y-%m-%d %H:%M:%S")


def detect_chrome_major_version() -> int | None:
    """Sistemdeki Google Chrome/Chromium ana versiyonunu tespit eder."""
    for binary in ["google-chrome", "chromium", "chromium-browser", "chrome"]:
        if not shutil.which(binary):
            continue
        try:
            out = subprocess.check_output([binary, "--version"], text=True, stderr=subprocess.DEVNULL)
            m = re.search(r"(\d+)\.\d+", out)
            if m:
                return int(m.group(1))
        except Exception:
            continue
    return None


def read_journals(path: str):
    raw = Path(path).read_text(encoding="utf-8")
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def parse_journal_line(line: str):
    parts = [p.strip() for p in line.split("|")]
    if len(parts) >= 2 and re.fullmatch(r"\d+", parts[1]):
        return {"name": parts[0], "sid": parts[1]}
    return {"name": line, "sid": None}


def is_blocked(driver):
    title = driver.title.lower()
    url = driver.current_url.lower()
    return (
        "just a moment" in title
        or "security verification" in title
        or "__cf_chl" in url
    )


def wait_while_cloudflare(driver, timeout_sec=60, poll_sec=1.5):
    started = time.time()
    while time.time() - started < timeout_sec:
        if not is_blocked(driver):
            return True
        time.sleep(poll_sec)
    return False


def extract_quartiles(driver):
    """Quartiles panelinden tablo verisini çeker. Dinamik yüklenmeyi bekler."""
    panel = None
    for xpath in [
        "//div[contains(@class,'quartiles-graph')]",
        "//div[contains(@class,'dashboard') and contains(@class,'journal_column')][.//h2[normalize-space()='Quartiles']]",
    ]:
        try:
            panel = driver.find_element(By.XPATH, xpath)
            break
        except Exception:
            continue

    if not panel:
        return {"ok": False, "reason": "Quartiles panel not found"}

    # Tablonun dinamik yüklenmesini bekle (en fazla 15 sn)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'quartiles-graph')]//table//tbody/tr | //div[contains(@class,'dashboard') and contains(@class,'journal_column')]//table//tbody/tr"))
        )
    except Exception:
        pass

    try:
        rows = panel.find_elements(By.CSS_SELECTOR, "table tbody tr")
    except Exception:
        return {"ok": False, "reason": "Quartiles table rows not found"}

    data = []
    for tr in rows:
        tds = tr.find_elements(By.TAG_NAME, "td")
        if len(tds) < 3:
            continue
        data.append({
            "category": tds[0].text.strip(),
            "year": tds[1].text.strip(),
            "quartile": tds[2].text.strip(),
        })

    if not data:
        return {"ok": False, "reason": "Quartiles table rows not found"}

    return {"ok": True, "rows": data}


def search_and_scrape(driver, journal_name, sid):
    q = sid if sid else journal_name
    encoded_q = quote(str(q))
    if sid:
        search_url = f"{BASE}/journalsearch.php?q={encoded_q}&tip=sid&clean=0"
    else:
        search_url = f"{BASE}/journalsearch.php?q={encoded_q}"

    logger.info("Searching: %s", search_url)
    driver.get(search_url)

    if not wait_while_cloudflare(driver):
        return {"journal_url": None, "ok": False, "reason": "Cloudflare challenge timeout"}

    current_url = driver.current_url
    if "journalrank.php" in current_url:
        logger.info("Redirected to rank page: %s", current_url)
        quartiles = extract_quartiles(driver)
        return {"journal_url": current_url, **quartiles}

    # Doğrudan profil sayfasında mıyız?
    try:
        driver.find_element(By.XPATH, "//h2[normalize-space()='Quartiles']")
        quartiles = extract_quartiles(driver)
        return {"journal_url": current_url, **quartiles}
    except Exception:
        pass

    # Arama sonuçlarından ilk linki al
    try:
        links = driver.find_elements(
            By.CSS_SELECTOR,
            ".search_results a[href*='journalsearch.php'], .search_results a[href*='journalrank.php']"
        )
        if not links:
            return {"journal_url": None, "ok": False, "reason": "Search result link not found"}
        best_href = links[0].get_attribute("href")
        if not best_href:
            return {"journal_url": None, "ok": False, "reason": "Search result href is empty"}
    except Exception as e:
        return {"journal_url": None, "ok": False, "reason": str(e)}

    next_url = best_href if best_href.startswith("http") else f"{BASE}/{best_href.lstrip('/')}"
    logger.info("Opening profile: %s", next_url)
    driver.get(next_url)
    if not wait_while_cloudflare(driver):
        return {"journal_url": None, "ok": False, "reason": "Cloudflare challenge timeout on profile"}

    quartiles = extract_quartiles(driver)
    return {"journal_url": driver.current_url, **quartiles}


def create_driver(chrome_version: int | None = None):
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")

    kwargs = {"options": options}
    if chrome_version:
        kwargs["version_main"] = chrome_version
    return uc.Chrome(**kwargs)


def main():
    parser = argparse.ArgumentParser(description="SCImago Journal Quartiles Scraper")
    parser.add_argument("input", nargs="?", default="journals.txt", help="Input journal list file")
    parser.add_argument("output", nargs="?", default="quartiles_output.json", help="Output JSON file")
    parser.add_argument("--chrome-version", type=int, default=None, help="Chrome major version override")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between journals (seconds)")
    parser.add_argument("--retries", type=int, default=3, help="Max retries per journal")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--state", type=str, default=None, help="Previous result JSON to resume from (skips already-ok entries)")
    args = parser.parse_args()

    setup_logging(logging.DEBUG if args.verbose else logging.INFO)

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    journals_raw = read_journals(str(input_path))
    journals = [parse_journal_line(line) for line in journals_raw]
    if not journals:
        logger.error("Input list is empty.")
        sys.exit(1)

    # State (önceki sonuç) oku
    existing = {}
    if args.state:
        state_path = Path(args.state)
        if state_path.exists():
            try:
                state_data = json.loads(state_path.read_text(encoding="utf-8"))
                for item in state_data:
                    if item.get("ok"):
                        existing[item["query"]] = item
                logger.info("Loaded state from %s: %d already scraped", state_path, len(existing))
            except Exception as e:
                logger.warning("Failed to load state file: %s", e)

    # Yeni çekilecek olanları filtrele
    to_scrape = [j for j in journals if j["name"] not in existing]
    skipped = [j for j in journals if j["name"] in existing]

    if skipped:
        logger.info("Skipping %d already-scraped journal(s)", len(skipped))
    if not to_scrape:
        logger.info("Nothing new to scrape. Writing merged output...")
        results = [existing[j["name"]] for j in journals]
        output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Done. Output: %s", output_path)
        return

    logger.info("Scraping %d new journal(s) out of %d total", len(to_scrape), len(journals))

    chrome_version = args.chrome_version
    if not chrome_version:
        detected = detect_chrome_major_version()
        if detected:
            chrome_version = detected
            logger.info("Detected Chrome version: %d", chrome_version)
        else:
            logger.warning("Could not detect Chrome version; letting undetected-chromedriver auto-detect")

    logger.info("Launching undetected Chrome...")
    driver = create_driver(chrome_version)

    scrape_time = datetime.now().isoformat()
    try:
        new_results = {}
        for journal in to_scrape:
            name = journal["name"]
            sid = journal.get("sid")
            entry = {
                "query": name,
                "sid": sid,
                "ok": False,
                "journal_url": None,
                "rows": [],
                "error": None,
                "timestamp": scrape_time,
            }
            try:
                for attempt in range(1, args.retries + 1):
                    try:
                        data = search_and_scrape(driver, name, sid)
                        if data.get("ok"):
                            entry["ok"] = True
                            entry["rows"] = data["rows"]
                            entry["journal_url"] = data.get("journal_url")
                            url = data.get("journal_url", "")
                            if url:
                                parsed = urlparse(url)
                                qs = parse_qs(parsed.query)
                                if qs.get("tip", [""])[0] == "sid" and qs.get("q"):
                                    entry["sid"] = qs["q"][0]
                            break
                        else:
                            raise Exception(data.get("reason", "Unknown error"))
                    except Exception as e:
                        if attempt == args.retries:
                            raise
                        logger.warning("Retry %d/%d for '%s': %s", attempt, args.retries, name, e)
                        time.sleep(2 * attempt)
            except Exception as e:
                entry["error"] = str(e)
                logger.error("Failed to scrape '%s': %s", name, e)

            new_results[name] = entry
            status = "OK" if entry["ok"] else "ERR"
            logger.info("[%s] %s", status, name)
            time.sleep(args.delay)
          
        # Birleştir: state + yeni sonuçlar (journals.txt sırasına göre)
        merged = []
        for j in journals:
            name = j["name"]
            if name in new_results:
                merged.append(new_results[name])
            elif name in existing:
                merged.append(existing[name])
            else:
                # Fallback (olmaması gerekir ama güvenlik için)
                merged.append({
                    "query": name,
                    "sid": j.get("sid"),
                    "ok": False,
                    "journal_url": None,
                    "rows": [],
                    "error": "Not processed",
                    "timestamp": scrape_time,
                })

        output_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Done. Output: %s", output_path)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
