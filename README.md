# Shibuya Hotel Monitor

A local Python bot that watches hotel prices in Shibuya for a specific stay
and alerts you via Telegram when a result fits your budget. You can also
chat with the bot to change parameters, pause/resume, trigger an immediate
check, and list the latest prices.

## What it monitors

- **Dates:** 2026-12-11 → 2026-12-12 (1 night) — editable via Telegram
- **Occupancy:** checks BOTH layouts every run and ranks them together —
  (a) one room for 4 adults + 1 infant, and (b) two rooms = (2 adults +
  1 infant) + (2 adults). Editable in `app/config.yaml`.
- **Area:** ≤ ~15-minute walk from Shibuya Scramble Crossing
- **Budget:** CAD $375 total (both rooms combined, taxes & fees included) — editable
- **Default source: fully local Booking.com search via Playwright.**
  The bot drives a headless Chromium on your own machine, loads the
  public Booking.com search page with your dates and occupancy, and
  reads prices directly from the rendered results. No account, no API
  key, no third-party service.
- **Optional: Google Hotels via SerpAPI.** If you *do* set a
  `SERPAPI_KEY` in `.env`, the bot uses that instead — faster and more
  reliable, but SerpAPI's free tier requires phone verification.

> **Why not Airbnb / Expedia / Agoda directly?** Airbnb has no public API
> and actively blocks scrapers. Expedia and Agoda use the same inventory
> pool as Booking.com for most Shibuya properties, so Booking.com is a
> good proxy. If you want Expedia/Agoda specifically later, we can add
> their partner APIs (require account approval) or an aggregator like
> RapidAPI's `hotels4` endpoint.

## Shortlist (edit `app/config.yaml`)

All within ~15-min walk of Shibuya Crossing:

| # | Hotel | Approx walk |
|---|---|---|
| 1 | Shibuya Excel Hotel Tokyu | 1 min |
| 2 | Shibuya Tokyu REI Hotel | 3 min |
| 3 | Shibuya Stream Excel Hotel Tokyu | 4 min |
| 4 | Tokyu Stay Shibuya | 8 min |
| 5 | Shibuya Granbell Hotel | 6 min |
| 6 | Shibuya Tobu Hotel | 7 min |
| 7 | All Day Place Shibuya | 7 min |
| 8 | Mustard Hotel Shibuya | 9 min |
| 9 | Trunk Hotel Cat Street | 12 min |
| 10 | Hotel Mets Shibuya | 10 min |
| 11 | Dormy Inn Premium Shibuya Jingumae | 13 min |
| 12 | Shibuya Hotel En | 10 min |

The bot searches Booking.com (or Google Hotels via SerpAPI, if you
opted in) for `"Shibuya, Tokyo"`, so any property in the area with
available inventory for your dates surfaces automatically — this list
is a reference, not a filter. You don't need to pre-seed IDs.

## Telegram commands

Once the bot is running and you've started a chat with it, these commands work:

| Command | What it does |
|---|---|
| `/start` | Register your chat as the alert destination |
| `/status` | Current config: dates, guests, budget, pause state, last check |
| `/check` | Run a check right now |
| `/latest` | Show the lowest N prices from the most recent check |
| `/budget 400` | Set budget to CAD 400 total |
| `/dates 2026-12-11 2026-12-12` | Set check-in / check-out |
| `/radius 20` | Expand walk-radius (minutes) — adds nearby hotels |
| `/addhotel <booking_hotel_id> <name>` | Add a hotel to the watchlist |
| `/removehotel <booking_hotel_id>` | Remove one |
| `/pause` / `/resume` | Stop / restart scheduled checks |
| `/interval 30` | Minutes between checks (default: 60) |
| `/fx` | Show the FX rate in use (JPY → CAD) |
| `/help` | List commands |

The bot pings you on **any** result ≤ budget. It also sends a daily
summary at 09:00 local showing the 5 cheapest combinations even if none
hit the budget, so you can see the trend.

## Setup

```bash
# 1. Clone and enter
git clone <this-repo>
cd japan-hotels

# 2. Make a virtualenv (Python 3.10–3.13 recommended; 3.14 works too)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2b. Install the headless Chromium that the local scraper drives
#     (one-time, ~150MB download):
playwright install chromium

# 3. Create a Telegram bot
#    - Open Telegram, message @BotFather
#    - Send /newbot, pick a name, pick a username ending in "bot"
#    - BotFather replies with a token like 1234567890:ABC...xyz
#    - Copy that token.

# 4. (Optional) Get a SerpAPI key at https://serpapi.com (100 free searches/month)

# 5. Create .env
cp .env.example .env
# then edit .env and paste in:
#   TELEGRAM_BOT_TOKEN=...
#   SERPAPI_KEY=...        (optional)
#   TZ=America/Vancouver   (your local timezone)

# 6. Run the bot
python -m app.main
```

Keep it running under `tmux`, `screen`, `systemd`, or a Dockerfile (one is
included). Open your bot in Telegram and send `/start` — you're set.

## Budget reality check

CAD 375 total for 2 rooms (1 adult-pair + 1 adult-pair-with-infant) on
a Thursday–Friday in Shibuya in December is tight but not impossible —
business hotels like Shibuya Tokyu REI, Hotel Mets Shibuya, and Shibuya
Tobu Hotel do dip into the ¥12,000–¥16,000 per room range on quieter
weeks. The bot will tell you when that happens. If the dates are firm and
you don't see hits by late October 2026, we can widen the radius or relax
to 2 twin rooms at properties like Hotel Unizo Shibuya (14 min walk) or
look at serviced apartments in Jingumae.

## File layout

```
app/
  main.py          # Scheduler + Telegram bot entrypoint
  bot.py           # Telegram command handlers
  config.py        # Load / save YAML + .env
  config.yaml      # Dates, budget, hotel list, interval
  db.py            # SQLite for check history + chat state
  fx.py            # JPY <-> CAD rate (open.er-api.com, no key)
  hotels.py        # Booking.com availability JSON client
  serpapi_hotels.py# Optional Google Hotels via SerpAPI
  booking_scraper.py # Default: fully-local Booking.com Playwright scraper
  notify.py        # Compose + send Telegram alerts
.env.example
requirements.txt
Dockerfile
```
