from __future__ import annotations

from telegram import Bot
from telegram.constants import ParseMode

from . import config, db


def _bot() -> Bot:
    return Bot(token=config.telegram_token())


def _fmt_combo(c: dict) -> str:
    header = f"• <b>CAD {c['total_cad']:.2f}</b>  —  {c['layout']}"
    if c.get("same_hotel") and len(c["rooms"]) > 1:
        header += "  (same hotel — confirm 2 rooms available!)"
    lines = [header]
    for i, r in enumerate(c["rooms"], 1):
        suffix = f" · R{i}" if len(c["rooms"]) > 1 else ""
        lines.append(
            f'  {r["hotel_name"]}{suffix} — CAD {r["total_cad"]:.2f}  '
            f'<a href="{r["deeplink"]}">open</a>'
        )
    return "\n".join(lines)


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
    footer = "\n\n<b>Manual verification links:</b>\n" + "\n".join(
        f'• <a href="{url}">{label}</a>' for label, url in links.items()
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
