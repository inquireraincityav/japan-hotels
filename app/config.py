from __future__ import annotations

import os
import threading
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
CFG_PATH = ROOT / "config.yaml"
HOTELS_PATH = ROOT / "hotels.json"

load_dotenv(ROOT.parent / ".env")

_lock = threading.Lock()


def load() -> dict:
    with _lock:
        with open(CFG_PATH) as f:
            return yaml.safe_load(f)


def save(cfg: dict) -> None:
    with _lock:
        with open(CFG_PATH, "w") as f:
            yaml.safe_dump(cfg, f, sort_keys=False)


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def telegram_token() -> str:
    tok = env("TELEGRAM_BOT_TOKEN")
    if not tok or tok.startswith("paste-"):
        raise SystemExit("TELEGRAM_BOT_TOKEN missing — edit .env")
    return tok


def serpapi_key() -> str | None:
    k = env("SERPAPI_KEY")
    return k or None


def tz() -> str:
    return env("TZ", "America/Vancouver") or "America/Vancouver"
