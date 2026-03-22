"""
SPA URL Scraper
---------------
Automates URL extraction from Next.js / React SPAs where
navigation elements use onClick handlers instead of <a> tags.

Usage:
    1. Add your target language URLs to LANG_URLS
    2. Run: python spa_url_scraper.py
    3. Results saved to sets_<language>.json and all_set_urls.json
"""

import asyncio
import json
import re
from playwright.async_api import async_playwright

# ── Configuration ─────────────────────────────────────────────────────────────

# Target pages — one entry per language/filter variant you want to scrape
LANG_URLS = {
    "language_1": "https://example.com/sets/category/3?language=language_1",
    "language_2": "https://example.com/sets/category/3?language=language_2",
}

# CSS selector that matches each tile/card element on the listing page
TILE_SELECTOR = "li.list-none"

# Regex to extract a clean URL from the navigation target
# Adjust to match your site's URL pattern
URL_PATTERN = re.compile(r'/sets/category/3/([^?&]+)\?groupId=(\d+)')

# Base URL of the site
BASE_URL = "https://example.com"

# ── Core Logic ─────────────────────────────────────────────────────────────────

async def scrape_urls(page, label, start_url):
    """
    Opens start_url, scrolls to load all tiles, then clicks each one
    and records the resulting URL.
    """
    collected = {}
    print(f"\n=== {label.upper()} ===")

    await page.goto(start_url, wait_until="networkidle")

    # Scroll incrementally to trigger lazy-loaded content
    for i in range(40):
        await page.evaluate(f"window.scrollTo(0, {i * 800})")
        await asyncio.sleep(0.4)
    await asyncio.sleep(1)

    # Capture tile names and positions from the fully-rendered DOM
    tiles_info = await page.evaluate(f"""
    () => [...document.querySelectorAll('{TILE_SELECTOR}')].map(t => {{
        const rect = t.getBoundingClientRect();
        const p = t.querySelector('p');
        return {{
            name: p ? p.innerText.split('\\n')[0].trim() : '',
            top: rect.top + window.scrollY,
            x: rect.left + rect.width / 2,
            y: rect.top + rect.height / 2
        }};
    }}).filter(t => t.name)
    """)

    print(f"Found {len(tiles_info)} tiles")

    for i, tile in enumerate(tiles_info):
        try:
            # Return to listing page before each click
            await page.goto(start_url, wait_until="networkidle")

            # Scroll tile into view
            await page.evaluate(f"window.scrollTo(0, {max(0, tile['top'] - 300)})")
            await asyncio.sleep(0.5)

            # Click and wait for React router to update the URL
            await page.mouse.click(tile['x'], tile['y'])
            await asyncio.sleep(1.5)

            # Read the URL after navigation
            after_url = page.url
            if after_url != start_url and "_rsc" not in after_url:
                m = URL_PATTERN.search(after_url)
                if m:
                    clean = f"{BASE_URL}/sets/category/3/{m.group(1)}?groupId={m.group(2)}&cardType=cards"
                    if clean not in collected:
                        collected[clean] = tile['name']
                        print(f"  [{len(collected)}] {tile['name']} → {clean}")

        except Exception as e:
            print(f"  Error on tile {i}: {e}")
            continue

        if (i + 1) % 10 == 0:
            print(f"  Progress: {i+1}/{len(tiles_info)} | captured: {len(collected)}")

    return [{"url": u, "name": n, "language": label} for u, n in collected.items()]


async def main():
    all_results = {}

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=False)
        page = await browser.new_page()

        for label, start_url in LANG_URLS.items():
            results = await scrape_urls(page, label, start_url)
            all_results[label] = results
            print(f"\n{label}: {len(results)} items found")

        await browser.close()

    # Save per-language files
    for label, results in all_results.items():
        fname = f"sets_{label}.json"
        with open(fname, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Saved → {fname} ({len(results)} items)")

    # Save combined file
    with open("all_set_urls.json", "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print("Saved → all_set_urls.json")


if __name__ == "__main__":
    asyncio.run(main())
