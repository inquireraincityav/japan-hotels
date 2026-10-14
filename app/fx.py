from __future__ import annotations

import time

import httpx

_cache: dict[str, float | int] = {"rate": 0.0, "ts": 0}


def jpy_to_cad(amount_jpy: float) -> float:
    now = time.time()
    if now - _cache["ts"] > 3600 or _cache["rate"] == 0.0:
        try:
            r = httpx.get("https://open.er-api.com/v6/latest/JPY", timeout=10.0)
            r.raise_for_status()
            _cache["rate"] = float(r.json()["rates"]["CAD"])
        except Exception:
            # Fallback: approximate rate (JPY -> CAD ~ 0.0091 in late 2026)
            _cache["rate"] = 0.0091
        _cache["ts"] = int(now)
    return amount_jpy * float(_cache["rate"])


def current_rate() -> float:
    jpy_to_cad(1.0)
    return float(_cache["rate"])
