from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from telegram.ext import Application

from . import bot, config, db, hotels, notify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("monitor")


async def scheduled_check() -> None:
    cfg = config.load()
    if cfg.get("paused"):
        log.info("paused — skipping")
        return
    log.info("running scheduled check")
    try:
        result = hotels.check()
        db.record_check(result["rows"])
        # Only ping when we have hits under budget — otherwise stay quiet.
        if result["under_budget"]:
            # Hysteresis: suppress repeat alerts within alert_delta_cad.
            fresh = []
            delta = float(cfg.get("alert_delta_cad", 5))
            for combo in result["under_budget"]:
                key = f"{combo['rooms'][0]['hotel_name']}|{combo['rooms'][1]['hotel_name']}"
                last = db.last_alert_cad(key)
                if last is None or abs(last - combo["total_cad"]) >= delta:
                    db.set_last_alert(key, combo["total_cad"])
                    fresh.append(combo)
            if fresh:
                result2 = dict(result)
                result2["under_budget"] = fresh
                await notify.send_result(result2, prefix="🎯 <b>Match!</b>\n")
    except Exception as e:
        log.exception("check failed: %s", e)


async def daily_summary() -> None:
    cfg = config.load()
    if not cfg.get("daily_summary", True):
        return
    try:
        result = hotels.check()
        db.record_check(result["rows"])
        await notify.send_result(result, prefix="☀️ <b>Daily summary</b>\n")
    except Exception as e:
        log.exception("daily summary failed: %s", e)


async def _post_init(application: Application) -> None:
    cfg = config.load()
    sched = AsyncIOScheduler(timezone=config.tz())
    sched.add_job(
        scheduled_check,
        IntervalTrigger(minutes=int(cfg["check_interval_minutes"])),
        id="hotel_check",
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        daily_summary,
        CronTrigger(hour=9, minute=3, timezone=config.tz()),
        id="daily_summary",
    )
    sched.start()
    application.bot_data["scheduler"] = sched
    log.info(
        "scheduler started: every %s min, daily summary at 09:03 %s",
        cfg["check_interval_minutes"],
        config.tz(),
    )


def main() -> None:
    db.init()
    # Python 3.14 removed the implicit event-loop creation in the main
    # thread that older python-telegram-bot versions assumed. Create one.
    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    application = (
        Application.builder()
        .token(config.telegram_token())
        .post_init(_post_init)
        .build()
    )
    bot.build(application)
    log.info("bot starting; press Ctrl-C to stop")
    application.run_polling()


if __name__ == "__main__":
    main()
