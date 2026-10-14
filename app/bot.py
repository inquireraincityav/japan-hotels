from __future__ import annotations

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from . import config, db, fx, hotels, notify


HELP = (
    "Shibuya Hotel Monitor commands:\n"
    "/start — register this chat for alerts\n"
    "/status — show current config\n"
    "/check — run a check now\n"
    "/latest — show lowest 10 prices from last check\n"
    "/budget <cad> — set budget (CAD, combined for both rooms)\n"
    "/dates <YYYY-MM-DD> <YYYY-MM-DD> — set checkin / checkout\n"
    "/radius <min> — set max walk minutes from Shibuya Crossing\n"
    "/interval <min> — minutes between scheduled checks\n"
    "/pause  /resume — stop/restart scheduled checks\n"
    "/fx — show current JPY→CAD rate\n"
    "/help — this message"
)


async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    db.add_chat(update.effective_chat.id)
    await update.effective_chat.send_message(
        "✅ You'll receive alerts here.\n\n" + HELP
    )


async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_chat.send_message(HELP)


async def cmd_status(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    c = config.load()
    rooms = "; ".join(
        f"R{i+1}={r['adults']}a"
        + (f"+{len(r.get('children_ages') or [])}c" if r.get("children_ages") else "")
        for i, r in enumerate(c["rooms"])
    )
    await update.effective_chat.send_message(
        f"Dates: {c['dates']['checkin']} → {c['dates']['checkout']}\n"
        f"Rooms: {rooms}\n"
        f"Budget: CAD {c['budget_cad']} total\n"
        f"Max walk: {c['max_walk_minutes']} min\n"
        f"Interval: every {c['check_interval_minutes']} min\n"
        f"Paused: {c['paused']}\n"
        f"FX JPY→CAD: {fx.current_rate():.5f}"
    )


async def cmd_check(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_chat.send_message("🔎 Checking…")
    result = hotels.check()
    db.record_check(result["rows"])
    await notify.send_result(result, prefix="<b>On-demand check</b>\n")


async def cmd_latest(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    rows = db.latest(10)
    if not rows:
        await update.effective_chat.send_message("No checks recorded yet. /check to run one.")
        return
    lines = [
        f"{r['hotel_name']} ({r['room_bucket']}): CAD {r['total_cad']:.2f}"
        for r in rows
    ]
    await update.effective_chat.send_message("\n".join(lines))


async def cmd_budget(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.effective_chat.send_message("Usage: /budget 400")
        return
    try:
        cad = float(ctx.args[0])
    except ValueError:
        await update.effective_chat.send_message("Not a number.")
        return
    c = config.load()
    c["budget_cad"] = cad
    config.save(c)
    await update.effective_chat.send_message(f"Budget → CAD {cad:.0f}")


async def cmd_dates(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if len(ctx.args) != 2:
        await update.effective_chat.send_message("Usage: /dates 2026-12-11 2026-12-12")
        return
    c = config.load()
    c["dates"]["checkin"], c["dates"]["checkout"] = ctx.args[0], ctx.args[1]
    config.save(c)
    await update.effective_chat.send_message(
        f"Dates → {c['dates']['checkin']} → {c['dates']['checkout']}"
    )


async def cmd_radius(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.effective_chat.send_message("Usage: /radius 15")
        return
    c = config.load()
    c["max_walk_minutes"] = int(ctx.args[0])
    config.save(c)
    await update.effective_chat.send_message(f"Walk radius → {c['max_walk_minutes']} min")


async def cmd_interval(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.effective_chat.send_message("Usage: /interval 60")
        return
    c = config.load()
    c["check_interval_minutes"] = int(ctx.args[0])
    config.save(c)
    await update.effective_chat.send_message(
        f"Interval → every {c['check_interval_minutes']} min (restart bot to re-apply)"
    )


async def cmd_pause(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    c = config.load()
    c["paused"] = True
    config.save(c)
    await update.effective_chat.send_message("⏸ Paused.")


async def cmd_resume(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    c = config.load()
    c["paused"] = False
    config.save(c)
    await update.effective_chat.send_message("▶ Resumed.")


async def cmd_fx(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_chat.send_message(f"JPY→CAD: {fx.current_rate():.5f}")


def build(app: Application) -> None:
    handlers = [
        CommandHandler("start", cmd_start),
        CommandHandler("help", cmd_help),
        CommandHandler("status", cmd_status),
        CommandHandler("check", cmd_check),
        CommandHandler("latest", cmd_latest),
        CommandHandler("budget", cmd_budget),
        CommandHandler("dates", cmd_dates),
        CommandHandler("radius", cmd_radius),
        CommandHandler("interval", cmd_interval),
        CommandHandler("pause", cmd_pause),
        CommandHandler("resume", cmd_resume),
        CommandHandler("fx", cmd_fx),
    ]
    for h in handlers:
        app.add_handler(h)
