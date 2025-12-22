import asyncio
import json
import os
import requests
import re
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import subprocess
import sys
import time

# ================= LOCK =================
playwright_lock = asyncio.Lock()

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID_1 = int(os.getenv("GROUP_ID_1"))
GROUP_ID_2 = int(os.getenv("GROUP_ID_2"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

CACHE_FILE = "cache.json"
INLINE_RANGE_FILE = "inline.json"
SMC_FILE = "smc.json"
WAIT_FILE = "wait.json"

BOT_USERNAME_LINK = "https://t.me/myzuraisgoodbot"
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1"
GROUP_LINK_2 = "https://t.me/zura14g"

verified_users = set()
waiting_range = set()
waiting_admin_input = set()
pending_message = {}

COUNTRY_EMOJI = {
    "NEPAL": "🇳🇵",
    "IVORY COAST": "🇨🇮",
    "GUINEA": "🇬🇳",
    "CENTRAL AFRIKA": "🇨🇫",
    "TOGO": "🇹🇬",
    "TAJIKISTAN": "🇹🇯",
    "BENIN": "🇧🇯",
    "SIERRA LEONE": "🇸🇱",
    "MADAGASCAR": "🇲🇬",
    "AFGANISTAN": "🇦🇫",
}

# ================= FILE UTILS =================
def load_json(file, default):
    if os.path.exists(file):
        try:
            with open(file, "r") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

# ================= TELEGRAM =================
def tg_send(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    r = requests.post(f"{API}/sendMessage", json=payload).json()
    return r.get("result", {}).get("message_id")

def tg_edit(chat_id, msg_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": msg_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{API}/editMessageText", json=payload)

def tg_get_updates(offset):
    return requests.get(
        f"{API}/getUpdates",
        params={"offset": offset, "timeout": 1}
    ).json()

# ================= VALIDATION =================
def is_valid_range(text):
    return bool(re.fullmatch(r"\d{5,12}X+", text))

# ================= PLAYWRIGHT CORE =================
async def get_number_and_country(page):
    rows = await page.query_selector_all("tbody tr")
    for row in rows:
        phone = await row.query_selector(".phone-number")
        if not phone:
            continue

        number = (await phone.inner_text()).strip()
        if not number:
            continue

        country_el = await row.query_selector(".badge.bg-primary")
        country = (await country_el.inner_text()).strip().upper() if country_el else "-"

        return number, country
    return None, None

async def process_user_input(page, user_id, prefix, msg_id):
    async with playwright_lock:
        tg_edit(
            user_id,
            msg_id,
            f"⏳ Processing...\nRange: <code>{prefix}</code>"
        )

        # ====== FIX UTAMA DI SINI ======
        await page.wait_for_selector('input[name="numberrange"]', timeout=15000)
        await page.fill('input[name="numberrange"]', prefix)

        await page.click("#getNumberBtn", force=True)

        # TUNGGU HASIL BUKAN RELOAD
        try:
            await page.wait_for_selector("tbody tr", timeout=15000)
        except:
            tg_edit(user_id, msg_id, "❌ Data tidak muncul.")
            return

        number, country = await get_number_and_country(page)
        if not number:
            tg_edit(user_id, msg_id, "❌ Nomor tidak ditemukan.")
            return

        emoji = COUNTRY_EMOJI.get(country, "🗺️")
        result = (
            "✅ NUMBER READY\n\n"
            f"📞 <code>{number}</code>\n"
            f"{emoji} {country}\n"
            f"🏷️ <code>{prefix}</code>"
        )

        kb = {
            "inline_keyboard": [
                [{"text": "📲 Get Number", "callback_data": "getnum"}],
                [{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}]
            ]
        }

        tg_edit(user_id, msg_id, result, kb)

# ================= TELEGRAM LOOP =================
async def telegram_loop(page):
    offset = 0
    while True:
        updates = tg_get_updates(offset)
        for upd in updates.get("result", []):
            offset = upd["update_id"] + 1

            if "message" in upd:
                msg = upd["message"]
                user_id = msg["from"]["id"]
                text = msg.get("text", "")

                if text == "/start":
                    mid = tg_send(
                        user_id,
                        "Klik tombol untuk ambil nomor",
                        {
                            "inline_keyboard": [
                                [{"text": "📲 Get Number", "callback_data": "getnum"}]
                            ]
                        }
                    )
                    pending_message[user_id] = mid

                elif user_id in waiting_range:
                    waiting_range.remove(user_id)
                    if not is_valid_range(text):
                        tg_send(user_id, "❌ Format range salah")
                        continue
                    await process_user_input(
                        page,
                        user_id,
                        text,
                        pending_message[user_id]
                    )

            if "callback_query" in upd:
                cq = upd["callback_query"]
                user_id = cq["from"]["id"]
                data = cq["data"]
                msg_id = cq["message"]["message_id"]

                if data == "getnum":
                    waiting_range.add(user_id)
                    pending_message[user_id] = msg_id
                    tg_edit(
                        user_id,
                        msg_id,
                        "Kirim range contoh:\n<code>9377009XXX</code>"
                    )

        await asyncio.sleep(1)

# ================= MAIN =================
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0]
        await telegram_loop(page)

if __name__ == "__main__":
    asyncio.run(main())
