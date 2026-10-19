"""Fully-local Booking.com search scraper via Playwright.

No external services, no API keys, no account signups. Launches a
headless Chromium on your machine, navigates to Booking.com's public
search URL with your dates and occupancy, and extracts property names
and prices from the rendered page.

Trade-offs vs. a paid API:
- Breaks when Booking.com changes their DOM (expect occasional fixes).
- Slower (~15-30s per room-bucket query).
- Running from a residential IP once or twice a day is well below any
  rate-limit threshold; running every 5 minutes would get you blocked.

The selectors used (`data-testid="property-card"`, `data-testid="title"`,
`data-testid="price-and-discounted-price"`) have been Booking.com's
public attributes for several years and are reasonably stable.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urlencode

from . import fx

SEARCH_URL = "https://www.booking.com/searchresults.html"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)


def _url(checkin: str, checkout: str, adults: int, children_ages: list[int]) -> str:
    params = {
        "ss": "Shibuya, Tokyo",
        "checkin": checkin,
        "checkout": checkout,
        "group_adults": adults,
        "no_rooms": 1,
        "group_children": len(children_ages),
        "selected_currency": "JPY",
        "nflt": "ht_id%3D204",  # hotels filter (optional)
    }
    url = SEARCH_URL + "?" + urlencode(params)
    for age in children_ages:
        url += f"&age={age}"
    return url


_PRICE_RE = re.compile(r"[\d,]+")


def _parse_jpy(text: str) -> float | None:
    if not text:
        return None
    m = _PRICE_RE.search(text.replace("\xa0", " "))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


async def _search_async(
    checkin: str, checkout: str, adults: int, children_ages: list[int]
) -> list[dict]:
    from playwright.async_api import async_playwright

    url = _url(checkin, checkout, adults, children_ages)
    results: list[dict] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(
                user_agent=USER_AGENT,
                locale="en-US",
                viewport={"width": 1366, "height": 900},
            )
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            # Dismiss any cookie / signin modals that would hide cards.
            for sel in [
                "button#onetrust-accept-btn-handler",
                'button[aria-label="Dismiss sign-in info."]',
            ]:
                try:
                    await page.locator(sel).first.click(timeout=1500)
                except Exception:
                    pass
            # Wait for property cards.
            try:
                await page.wait_for_selector(
                    '[data-testid="property-card"]', timeout=20000
                )
            except Exception:
                return results
            # Scroll a bit so lazy-loaded prices render.
            for y in (500, 1200, 2000):
                await page.evaluate(f"window.scrollTo(0, {y})")
                await page.wait_for_timeout(400)
            cards = page.locator('[data-testid="property-card"]')
            n = await cards.count()
            for i in range(min(n, 25)):
                card = cards.nth(i)
                try:
                    name_el = card.locator('[data-testid="title"]').first
                    price_el = card.locator(
                        '[data-testid="price-and-discounted-price"]'
                    ).first
                    link_el = card.locator('a[data-testid="title-link"]').first

                    name = (await name_el.text_content() or "").strip()
                    price_text = (await price_el.text_content() or "").strip()
                    href = await link_el.get_attribute("href") or ""
                    jpy = _parse_jpy(price_text)
                    if not name or jpy is None:
                        continue
                    results.append(
                        {
                            "hotel_id": href.split("?")[0].rsplit("/", 1)[-1],
                            "hotel_name": name,
                            "total_jpy": jpy,
                            "total_cad": round(fx.jpy_to_cad(jpy), 2),
                            "deeplink": href if href.startswith("http") else "https://www.booking.com" + href,
                            "source": "booking_scrape",
                        }
                    )
                except Exception:
                    continue
        finally:
            await browser.close()
    return results


def search_room_bucket(
    checkin: str,
    checkout: str,
    adults: int,
    children_ages: list[int],
    **_: object,
) -> list[dict]:
    """Sync wrapper matching the signature of serpapi_hotels.search_room_bucket."""
    try:
        return asyncio.run(_search_async(checkin, checkout, adults, children_ages))
    except RuntimeError:
        # If called from inside a running loop (shouldn't happen in our
        # scheduler flow but just in case), run on a side thread.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(
                lambda: asyncio.run(
                    _search_async(checkin, checkout, adults, children_ages)
                )
            )
            return fut.result()
