from __future__ import annotations

from telegram import Bot
from telegram.constants import ParseMode

from . import config, db


def _bot() -> Bot:
    return Bot(token=config.telegram_token())


def _fmt_combo(c: dict) -> str:
    r1, r2 = c["rooms"][0], c["rooms"][1]
    note = "  (same hotel — confirm 2 rooms available!)" if c["same_hotel"] else ""
    return (
        f"• Total CAD {c['total_cad']:.2f}{note}\n"
        f"  R1: {r1['hotel_name']} — CAD {r1['total_cad']:.2f}\n"
        f"       <a href=\"{r1['deeplink']}\">open</a>\n"
        f"  R2: {r2['hotel_name']} — CAD {r2['total_cad']:.2f}\n"
        f"       <a href=\"{r2['deeplink']}\">open</a>"
    )


async def send_result(result: dict, prefix: str = "") -> None:
    bot = _bot()
    chats = db.chat_ids()
    if not chats:
        return

    budget = result["budget_cad"]
    header = prefix
    if result["under_budget"]:
        header += f"✅ <b>{len(result['under_budget'])} combo(s) under CAD {budget:.0f}</b>\n\n"
        body = "\n\n".join(_fmt_combo(c) for c in result["under_budget"])
    elif result["combos"]:
        header += (
            f"ℹ️ Nothing under CAD {budget:.0f} yet. "
            f"Cheapest combo: CAD {result['min_total_cad']:.2f}\n\n"
        )
        body = "\n\n".join(_fmt_combo(c) for c in result["combos"][:3])
    else:
        header += "⚠️ No data this run (SerpAPI key missing or quota exhausted?).\n"
        body = ""

    links = result["deeplinks"]
    footer = (
        "\n\n<b>Manual verification links:</b>\n"
        f"• <a href=\"{links.get('booking_room1','')}\">Booking.com — Room 1</a>\n"
        f"• <a href=\"{links.get('booking_room2','')}\">Booking.com — Room 2</a>\n"
        f"• <a href=\"{links.get('google_room1','')}\">Google Hotels — Room 1</a>\n"
        f"• <a href=\"{links.get('airbnb_room1','')}\">Airbnb — Room 1</a>"
    )

    msg = header + body + footer
    for cid in chats:
        try:
            await bot.send_message(
                chat_id=cid,
                text=msg,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception as e:
            print(f"telegram send failed for {cid}: {e}")


async def send_text(text: str) -> None:
    bot = _bot()
    for cid in db.chat_ids():
        try:
            await bot.send_message(chat_id=cid, text=text)
        except Exception as e:
            print(f"telegram send failed for {cid}: {e}")
