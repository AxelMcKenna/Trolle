"""
Simple scraper to inspect Countdown store locator page structure.
"""
import asyncio
import json
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


async def inspect_page():
    """Load the page and dump what we find."""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        logger.info("Loading page...")
        await page.goto('https://www.woolworths.co.nz/store-finder', timeout=30000)

        await asyncio.sleep(5)

        logger.info("PAGE TITLE: %s", await page.title())
        logger.info("PAGE URL: %s", page.url)

        # Get page HTML to inspect
        html = await page.content()
        logger.info("Page HTML length: %d chars", len(html))

        # Look for store-related data
        logger.info("Searching for store data...")

        # Check window object
        window_data = await page.evaluate('''() => {
            const keys = Object.keys(window).filter(k =>
                k.toLowerCase().includes('store') ||
                k.toLowerCase().includes('location') ||
                k.toLowerCase().includes('__')
            );
            return keys;
        }''')
        logger.info("Window keys with 'store/location/__': %s", window_data)

        # Check for Next.js data
        next_data = await page.evaluate('''() => {
            const el = document.getElementById('__NEXT_DATA__');
            if (el) return JSON.parse(el.textContent);
            return null;
        }''')

        if next_data:
            logger.info("Found __NEXT_DATA__!")
            logger.info("Keys: %s", list(next_data.keys()) if isinstance(next_data, dict) else type(next_data))
            logger.debug("Data: %s", json.dumps(next_data, indent=2)[:1000])

        # Look for React/API data in scripts
        script_data = await page.evaluate('''() => {
            const scripts = Array.from(document.querySelectorAll('script'));
            const results = [];
            for (const script of scripts) {
                const text = script.textContent || '';
                if (text.includes('"stores"') || text.includes('"locations"') ||
                    text.includes('storeLocator') || text.includes('"address"')) {
                    results.push({
                        src: script.src || 'inline',
                        preview: text.substring(0, 200)
                    });
                }
            }
            return results;
        }''')

        if script_data:
            logger.info("Found %d scripts with store-related content:", len(script_data))
            for i, script in enumerate(script_data[:3]):
                logger.info("  Script %d: Src=%s Preview=%s", i+1, script['src'], script['preview'][:150])

        # Check page structure
        logger.info("Checking page structure for store UI elements...")
        structure = await page.evaluate('''() => {
            return {
                hasInput: !!document.querySelector('input[type="text"], input[placeholder*="ubur"], input[placeholder*="ocation"]'),
                hasMap: !!document.querySelector('[class*="map"], #map, canvas'),
                hasStoreList: !!document.querySelector('[class*="store"], [class*="location"]'),
                bodyClasses: document.body.className,
                mainContent: document.body.textContent.substring(0, 500)
            };
        }''')

        logger.info("Structure: %s", json.dumps(structure, indent=2))

        # Keep browser open for manual inspection
        logger.info("Browser will stay open for 60 seconds. Manually inspect the page to see how stores are loaded.")

        await asyncio.sleep(60)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(inspect_page())
