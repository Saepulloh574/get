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
sent_numbers = set()

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
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    r = requests.post(f"{API}/sendMessage", json=payload).json()
    return r.get("result", {}).get("message_id")

def tg_edit(chat_id, msg_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{API}/editMessageText", json=payload)

def tg_get_updates(offset):
    return requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 1}).json()

# ================= PLAYWRIGHT =================
async def get_number_and_country(page):
    rows = await page.query_selector_all("tbody tr")
    for row in rows:
        phone_el = await row.query_selector(".phone-number")
        if not phone_el:
            continue
        number = (await phone_el.inner_text()).strip()
        if not number:
            continue
        country_el = await row.query_selector(".badge.bg-primary")
        country = (await country_el.inner_text()).strip().upper() if country_el else "-"
        return number, country
    return None, None

async def process_user_input(page, user_id, prefix, message_id_to_edit=None):
    msg_id = message_id_to_edit if message_id_to_edit else pending_message.get(user_id)

    if playwright_lock.locked():
        tg_edit(user_id, msg_id, f"⏳ Masuk antrian...\nRange: <code>{prefix}</code>")

    async with playwright_lock:
        try:
            tg_edit(user_id, msg_id, f"⏳ Mengambil number...\nRange: <code>{prefix}</code>")

            await page.wait_for_selector('input[name="numberrange"]', timeout=15000)
            await page.fill('input[name="numberrange"]', prefix)
            await asyncio.sleep(0.5)

            # ================= FIX SATU-SATUNYA =================
            await page.click("#getNumberBtn", force=True)
            await page.wait_for_selector("tbody tr", timeout=15000)
            # ❌ TIDAK ADA page.reload()
            # ====================================================

            number, country = await get_number_and_country(page)
            if not number:
                tg_edit(user_id, msg_id, "❌ Nomor tidak ditemukan.")
                return

            emoji = COUNTRY_EMOJI.get(country, "🗺️")
            msg = (
                "✅ The number is ready\n\n"
                f"📞 Number  : <code>{number}</code>\n"
                f"{emoji} COUNTRY : {country}\n"
                f"🏷️ Range   : <code>{prefix}</code>\n\n"
                "<b>OTP akan dikirim otomatis.</b>"
            )

            kb = {
                "inline_keyboard": [
                    [{"text": "📲 Get Number", "callback_data": "getnum"}],
                    [{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}]
                ]
            }

            tg_edit(user_id, msg_id, msg, kb)

        except Exception as e:
            print("[ERROR]", e)
            tg_edit(user_id, msg_id, "❌ Error saat mengambil number.")

# ================= TELEGRAM LOOP =================
async def telegram_loop(page):
    offset = 0
    while True:
        data = tg_get_updates(offset)
        for upd in data.get("result", []):
            offset = upd["update_id"] + 1

            if "message" in upd:
                msg = upd["message"]
                user_id = msg["from"]["id"]
                text = msg.get("text", "")

                if text == "/start":
                    mid = tg_send(
                        user_id,
                        "Klik tombol untuk ambil number",
                        {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}]]}
                    )
                    pending_message[user_id] = mid

                elif user_id in waiting_range:
                    waiting_range.remove(user_id)
                    await process_user_input(page, user_id, text, pending_message[user_id])

            if "callback_query" in upd:
                cq = upd["callback_query"]
                user_id = cq["from"]["id"]
                data_cb = cq["data"]
                msg_id = cq["message"]["message_id"]

                if data_cb == "getnum":
                    waiting_range.add(user_id)
                    pending_message[user_id] = msg_id
                    tg_edit(user_id, msg_id, "Kirim range contoh:\n<code>9377009XXX</code>")

        await asyncio.sleep(1)

# ================= MAIN =================
async def main():
    print("[INFO] Starting bot...")
    subprocess.Popen([sys.executable, "sms.py"])

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0]
        await telegram_loop(page)

if __name__ == "__main__":
    asyncio.run(main())
