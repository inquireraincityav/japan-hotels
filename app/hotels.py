"""Orchestrates a check across all configured room layouts and sources.

For each layout (e.g. "1 room (4 adults + 1 infant)" and "2 rooms …"),
queries each room-bucket, builds the cheapest combined booking per
layout, then merges all layouts' top options into a single ranked list.
"""

from __future__ import annotations

import itertools
from urllib.parse import quote_plus

from . import booking_scraper, config, serpapi_hotels

WALK_SHORTLIST_QUERY = "hotels near Shibuya Scramble Crossing"


def _search_fn():
    return (
        serpapi_hotels.search_room_bucket
        if config.serpapi_key()
        else booking_scraper.search_room_bucket
    )


def booking_deeplink(checkin, checkout, adults, children_ages):
    base = (
        "https://www.booking.com/searchresults.html?"
        f"ss=Shibuya%2C+Tokyo&checkin={checkin}&checkout={checkout}"
        f"&group_adults={adults}&no_rooms=1"
    )
    if children_ages:
        base += f"&group_children={len(children_ages)}"
        for age in children_ages:
            base += f"&age={age}"
    return base


def google_hotels_deeplink(checkin, checkout, adults, children_ages):
    kids = ""
    if children_ages:
        kids = "&children=" + ",".join(str(a) for a in children_ages)
    return (
        f"https://www.google.com/travel/hotels/{quote_plus('Shibuya, Tokyo')}"
        f"?checkin={checkin}&checkout={checkout}&adults={adults}{kids}"
    )


def airbnb_deeplink(checkin, checkout, adults, infants):
    return (
        "https://www.airbnb.com/s/Shibuya--Tokyo/homes?"
        f"checkin={checkin}&checkout={checkout}"
        f"&adults={adults}&infants={infants}"
    )


def _config_combos(cfg_name: str, rooms: list[dict], checkin: str, checkout: str) -> tuple[list[dict], list[dict]]:
    """Return (flat_offers_recorded_in_db, ranked_combos_for_this_layout)."""
    search = _search_fn()
    per_room: list[list[dict]] = []
    flat: list[dict] = []
    for i, bucket in enumerate(rooms):
        adults = int(bucket["adults"])
        kids = list(bucket.get("children_ages") or [])
        offers = search(
            checkin=checkin,
            checkout=checkout,
            adults=adults,
            children_ages=kids,
            query=WALK_SHORTLIST_QUERY,
        )
        tag = f"[{cfg_name}] room{i+1}:{adults}a"
        if kids:
            tag += f"+{len(kids)}c"
        for o in offers:
            o["room_bucket"] = tag
        flat.extend(offers)
        per_room.append(offers)

    combos: list[dict] = []
    if all(per_room):
        tops = [sorted(r, key=lambda x: x["total_cad"])[:8] for r in per_room]
        for pair in itertools.product(*tops):
            total = sum(o["total_cad"] for o in pair)
            combos.append(
                {
                    "layout": cfg_name,
                    "total_cad": round(total, 2),
                    "rooms": list(pair),
                    "same_hotel": len({o["hotel_name"] for o in pair}) == 1
                    if len(pair) > 1
                    else False,
                }
            )
        combos.sort(key=lambda c: c["total_cad"])
    return flat, combos


def check() -> dict:
    cfg = config.load()
    checkin = cfg["dates"]["checkin"]
    checkout = cfg["dates"]["checkout"]
    budget = float(cfg["budget_cad"])

    all_rows: list[dict] = []
    all_combos: list[dict] = []
    deeplinks: dict[str, str] = {}

    layouts = cfg.get("configurations") or [{"name": "default", "rooms": cfg.get("rooms", [])}]

    for layout in layouts:
        name = layout["name"]
        rooms = layout["rooms"]
        rows, combos = _config_combos(name, rooms, checkin, checkout)
        all_rows.extend(rows)
        all_combos.extend(combos)
        # Build deeplinks for this layout (user can click to verify any run)
        for i, r in enumerate(rooms):
            adults = int(r["adults"])
            kids = list(r.get("children_ages") or [])
            key = f"{name} / room{i+1}"
            deeplinks[f"Booking.com — {key}"] = booking_deeplink(checkin, checkout, adults, kids)
            deeplinks[f"Google Hotels — {key}"] = google_hotels_deeplink(checkin, checkout, adults, kids)
            if kids:
                deeplinks[f"Airbnb — {key}"] = airbnb_deeplink(checkin, checkout, adults, len(kids))

    all_combos.sort(key=lambda c: c["total_cad"])
    under = [c for c in all_combos if c["total_cad"] <= budget]
    min_total = all_combos[0]["total_cad"] if all_combos else None

    return {
        "rows": all_rows,
        "combos": all_combos[:10],
        "min_total_cad": min_total,
        "under_budget": under[:5],
        "deeplinks": deeplinks,
        "budget_cad": budget,
    }
