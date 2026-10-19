"""Orchestrates a check across all configured sources and room buckets.

Produces a ranked list of (room1_offer, room2_offer) combinations whose
combined CAD total is minimized. Any combination at or below the budget
triggers an alert via notify.send().
"""

from __future__ import annotations

import itertools
from urllib.parse import quote_plus

from . import booking_scraper, config, serpapi_hotels

WALK_SHORTLIST_QUERY = "hotels near Shibuya Scramble Crossing"


def _query_for_bucket(bucket: dict) -> str:
    return WALK_SHORTLIST_QUERY


def booking_deeplink(checkin: str, checkout: str, adults: int, children_ages: list[int]) -> str:
    base = (
        "https://www.booking.com/searchresults.html?"
        f"ss=Shibuya%2C+Tokyo&checkin={checkin}&checkout={checkout}"
        f"&group_adults={adults}&no_rooms=1"
    )
    if children_ages:
        base += f"&group_children={len(children_ages)}"
        for i, age in enumerate(children_ages):
            base += f"&age={age}"
    return base


def google_hotels_deeplink(checkin: str, checkout: str, adults: int, children_ages: list[int]) -> str:
    kids = ""
    if children_ages:
        kids = "&children=" + ",".join(str(a) for a in children_ages)
    return (
        f"https://www.google.com/travel/hotels/{quote_plus('Shibuya, Tokyo')}"
        f"?checkin={checkin}&checkout={checkout}&adults={adults}{kids}"
    )


def airbnb_deeplink(checkin: str, checkout: str, adults: int, infants: int) -> str:
    return (
        "https://www.airbnb.com/s/Shibuya--Tokyo/homes?"
        f"checkin={checkin}&checkout={checkout}"
        f"&adults={adults}&infants={infants}"
    )


def check() -> dict:
    """Run one full check. Returns a dict with:
    - rows: flattened offers (persisted)
    - combos: top combined pairings per room config
    - min_total_cad: cheapest combined total
    - under_budget: list of combos whose total_cad <= budget
    - deeplinks: {site: url} for manual verification
    """
    cfg = config.load()
    checkin = cfg["dates"]["checkin"]
    checkout = cfg["dates"]["checkout"]
    budget = float(cfg["budget_cad"])

    rows: list[dict] = []
    per_room_offers: list[list[dict]] = []

    # Pick the data source: SerpAPI when the user set up a key, otherwise
    # the fully-local Playwright Booking.com scraper (no account needed).
    search_fn = (
        serpapi_hotels.search_room_bucket
        if config.serpapi_key()
        else booking_scraper.search_room_bucket
    )

    for i, bucket in enumerate(cfg["rooms"]):
        adults = int(bucket["adults"])
        kids = list(bucket.get("children_ages") or [])
        offers = search_fn(
            checkin=checkin,
            checkout=checkout,
            adults=adults,
            children_ages=kids,
            query=_query_for_bucket(bucket),
        )
        tag = f"room{i+1}:{adults}a"
        if kids:
            tag += f"+{len(kids)}c"
        for o in offers:
            o["room_bucket"] = tag
        rows.extend(offers)
        per_room_offers.append(offers)

    combos: list[dict] = []
    if all(per_room_offers):
        # Rank each room's offers, then combine cheapest N x N
        tops = [sorted(r, key=lambda x: x["total_cad"])[:8] for r in per_room_offers]
        for pair in itertools.product(*tops):
            # Disallow using the same property for both rooms if the hotel
            # likely cannot provide two rooms at that rate — a soft guess:
            # we DO allow it but mark it; the user can decide.
            total = sum(o["total_cad"] for o in pair)
            combos.append(
                {
                    "total_cad": round(total, 2),
                    "rooms": pair,
                    "same_hotel": len({o["hotel_name"] for o in pair}) == 1,
                }
            )
        combos.sort(key=lambda c: c["total_cad"])

    under = [c for c in combos if c["total_cad"] <= budget]
    min_total = combos[0]["total_cad"] if combos else None

    # Build deeplinks for manual verification regardless of API success
    # (room 1 may have an infant; room 2 adults-only).
    r1 = cfg["rooms"][0]
    r2 = cfg["rooms"][1] if len(cfg["rooms"]) > 1 else None
    deeplinks = {
        "booking_room1": booking_deeplink(checkin, checkout, r1["adults"], r1.get("children_ages") or []),
        "google_room1": google_hotels_deeplink(checkin, checkout, r1["adults"], r1.get("children_ages") or []),
        "airbnb_room1": airbnb_deeplink(checkin, checkout, r1["adults"], len(r1.get("children_ages") or [])),
    }
    if r2:
        deeplinks.update(
            {
                "booking_room2": booking_deeplink(checkin, checkout, r2["adults"], r2.get("children_ages") or []),
                "google_room2": google_hotels_deeplink(checkin, checkout, r2["adults"], r2.get("children_ages") or []),
            }
        )

    return {
        "rows": rows,
        "combos": combos[:10],
        "min_total_cad": min_total,
        "under_budget": under[:5],
        "deeplinks": deeplinks,
        "budget_cad": budget,
    }
