"""
Capture network requests when loading Countdown stores.
"""
import asyncio
import json
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


async def capture_store_requests():
    """Intercept network requests to find store API."""

    api_requests = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Capture all network requests
        async def handle_response(response):
            url = response.url
            # Look for API calls that might have store data
            if any(keyword in url.lower() for keyword in ['store', 'location', 'shop', 'api', 'fulfilment']):
                try:
                    if response.status == 200:
                        api_requests.append({
                            'url': url,
                            'status': response.status,
                            'method': response.request.method,
                            'type': response.request.resource_type
                        })
                        logger.info("Captured: %s %s", response.request.method, url[:100])

                        # Try to get response body if it's JSON
                        content_type = response.headers.get('content-type', '')
                        if 'json' in content_type:
                            try:
                                body = await response.json()
                                logger.debug("Response type: %s", type(body))
                                if isinstance(body, list):
                                    logger.debug("Array with %d items", len(body))
                                    if body:
                                        logger.debug("First item keys: %s", list(body[0].keys())[:10])
                                elif isinstance(body, dict):
                                    logger.debug("Object keys: %s", list(body.keys())[:10])

                                # Save full response for inspection
                                api_requests[-1]['response'] = body
                            except:
                                pass
                except Exception as e:
                    logger.error("Error handling response: %s", e)

        page.on('response', handle_response)

        logger.info("Loading store finder page...")
        await page.goto('https://www.woolworths.co.nz/store-finder', wait_until='domcontentloaded')
        await asyncio.sleep(3)

        logger.info("Page loaded. Now triggering store search...")

        # Try to trigger the "Find stores near me" or search
        try:
            # Option 1: Click "Find stores near me" button
            near_me_button = page.locator('text=Find stores near me')
            if await near_me_button.count() > 0:
                logger.info("Clicking 'Find stores near me'...")
                await near_me_button.click()
                await asyncio.sleep(5)
        except Exception as e:
            logger.warning("Near me button error: %s", e)

        try:
            # Option 2: Search for a city
            search_input = page.locator('input[type="text"]').first
            if await search_input.count() > 0:
                logger.info("Searching for 'Auckland'...")
                await search_input.fill("Auckland")
                await asyncio.sleep(2)

                # Press Enter or click search button
                await search_input.press('Enter')
                await asyncio.sleep(5)
        except Exception as e:
            logger.warning("Search error: %s", e)

        logger.info("Captured %d API requests", len(api_requests))

        # Save captured requests
        if api_requests:
            output_file = '/Users/axelmckenna/dev/Grocify/api/data/countdown_api_requests.json'
            with open(output_file, 'w') as f:
                json.dump(api_requests, f, indent=2)
            logger.info("Saved API requests to: %s", output_file)

            # Log summary
            logger.info("API Endpoints found:")
            for i, req in enumerate(api_requests[:5], 1):
                logger.info("%d. %s %s", i, req['method'], req['url'][:80])
                if 'response' in req:
                    resp = req['response']
                    if isinstance(resp, list) and resp:
                        logger.info("   Array with %d items, sample keys: %s", len(resp), list(resp[0].keys())[:8])

        logger.info("Browser staying open for 30 seconds for inspection...")
        await asyncio.sleep(30)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(capture_store_requests())
