"""Google Hotels search via SerpAPI.

SerpAPI's google_hotels engine returns the same results Google Hotels
shows, including per-room nightly prices from Booking.com, Expedia,
Agoda, Hotels.com, and sometimes direct-hotel offers — pulled through
Google's own API surface, which is the ToS-safe way to get this data
without a per-site affiliate account.

Free tier is 100 searches/month. We only need a handful per check
(one per room bucket, bundled by query string), so a single free key
covers hourly checks for weeks.

Docs: https://serpapi.com/google-hotels-api
"""

from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from . import config, fx

SHIBUYA_LATLONG = "35.6595,139.7004"  # Shibuya Scramble Crossing


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def _get(params: dict) -> dict:
    r = httpx.get("https://serpapi.com/search.json", params=params, timeout=30.0)
    r.raise_for_status()
    return r.json()


def search_room_bucket(
    checkin: str,
    checkout: str,
    adults: int,
    children_ages: list[int],
    query: str = "Shibuya hotels",
) -> list[dict]:
    """Return a flat list of hotel offers for one room bucket.

    Each offer: {hotel_name, total_jpy, total_cad, deeplink, source}
    """
    key = config.serpapi_key()
    if not key:
        return []

    params = {
        "engine": "google_hotels",
        "q": query,
        "check_in_date": checkin,
        "check_out_date": checkout,
        "adults": adults,
        "currency": "JPY",
        "gl": "jp",
        "hl": "en",
        "api_key": key,
    }
    if children_ages:
        params["children"] = len(children_ages)
        params["children_ages"] = ",".join(str(a) for a in children_ages)

    data = _get(params)
    offers: list[dict] = []
    for prop in data.get("properties", []):
        rate = prop.get("rate_per_night") or {}
        total = prop.get("total_rate") or {}
        # Prefer total (incl. taxes) when available, else rate*nights (one night here)
        jpy = total.get("extracted_lowest") or rate.get("extracted_lowest")
        if jpy is None:
            continue
        offers.append(
            {
                "hotel_id": str(prop.get("property_token", "")),
                "hotel_name": prop.get("name", ""),
                "total_jpy": float(jpy),
                "total_cad": round(fx.jpy_to_cad(float(jpy)), 2),
                "deeplink": prop.get("link")
                or (prop.get("serpapi_property_details_link") or ""),
                "source": "google_hotels",
            }
        )
    return offers
