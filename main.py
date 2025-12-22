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

# --- MODIFIKASI: ASYNCIO LOCK UNTUK ANTRIAN PLAYWRIGHT ---
playwright_lock = asyncio.Lock()
# ------------------------------------------------------

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

# ================= FILE HANDLER =================

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_cache(number_entry):
    cache = load_cache()
    cache.append(number_entry)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

def is_in_cache(number):
    return any(entry["number"] == number for entry in load_cache())

def load_inline_ranges():
    if os.path.exists(INLINE_RANGE_FILE):
        with open(INLINE_RANGE_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_inline_ranges(ranges):
    with open(INLINE_RANGE_FILE, "w") as f:
        json.dump(ranges, f, indent=2)

def load_wait_list():
    if os.path.exists(WAIT_FILE):
        with open(WAIT_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_wait_list(data):
    with open(WAIT_FILE, "w") as f:
        json.dump(data, f, indent=2)

def add_to_wait_list(number, user_id):
    wait_list = load_wait_list()
    normalized = normalize_number(number)
    if not any(i["number"] == normalized for i in wait_list):
        wait_list.append({
            "number": normalized,
            "user_id": user_id,
            "timestamp": time.time()
        })
        save_wait_list(wait_list)

def normalize_number(number):
    n = number.strip().replace(" ", "").replace("-", "")
    if not n.startswith("+"):
        n = "+" + n
    return n

def is_valid_phone_number(text):
    return re.fullmatch(r"^\+?\d{6,15}$", text.replace(" ", "").replace("-", ""))

# ================= TELEGRAM =================

def tg_send(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{API}/sendMessage", json=data).json()
        if r.get("ok"):
            return r["result"]["message_id"]
    except:
        pass
    return None

def tg_edit(chat_id, msg_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "message_id": msg_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        requests.post(f"{API}/editMessageText", json=data)
    except:
        pass

def tg_get_updates(offset):
    try:
        return requests.get(
            f"{API}/getUpdates",
            params={"offset": offset, "timeout": 1}
        ).json()
    except:
        return {"ok": False, "result": []}

# ================= PLAYWRIGHT =================

async def get_number_and_country(page):
    rows = await page.query_selector_all("tbody tr")
    for row in rows:
        phone_el = await row.query_selector(".phone-number")
        if not phone_el:
            continue

        number = (await phone_el.inner_text()).strip()
        if is_in_cache(number):
            continue

        if await row.query_selector(".status-success") or await row.query_selector(".status-failed"):
            continue

        country_el = await row.query_selector(".badge.bg-primary")
        country = (await country_el.inner_text()).strip().upper() if country_el else "-"

        if number and len(number) > 5:
            return number, country

    return None, None

# ================= CORE PROCESS =================

async def process_user_input(page, user_id, prefix, message_id_to_edit=None):
    msg_id = message_id_to_edit or pending_message.pop(user_id, None)

    if playwright_lock.locked():
        msg_id = msg_id or tg_send(user_id, f"⏳ Permintaan masuk antrian\nRange: <code>{prefix}</code>")

    async with playwright_lock:
        try:
            tg_edit(user_id, msg_id, f"✅ Sedang mengambil number...\nRange: <code>{prefix}</code>")

            await page.wait_for_selector('input[name="numberrange"]', timeout=10000)
            await page.fill('input[name="numberrange"]', prefix)
            await asyncio.sleep(0.5)

            # ===== INI YANG DIMODIFIKASI SESUAI PERMINTAAN =====
            await page.click("#getNumberBtn", force=True)

            try:
                await page.wait_for_selector("tbody tr", timeout=15000)
            except:
                pass
            # ==================================================

            number, country = await get_number_and_country(page)

            if not number:
                tg_edit(user_id, msg_id, "❌ Nomor tidak ditemukan, silakan coba ulang.")
                return

            save_cache({"number": number, "country": country})
            add_to_wait_list(number, user_id)

            emoji = COUNTRY_EMOJI.get(country, "🗺️")
            tg_edit(
                user_id,
                msg_id,
                f"✅ The number is ready\n\n"
                f"📞 <code>{number}</code>\n"
                f"{emoji} COUNTRY : {country}\n"
                f"🏷️ Range : <code>{prefix}</code>"
            )

        except Exception as e:
            tg_edit(user_id, msg_id, f"❌ ERROR: {type(e).__name__}")

# ================= TELEGRAM LOOP =================

async def telegram_loop(page):
    offset = 0
    while True:
        data = tg_get_updates(offset)
        for upd in data.get("result", []):
            offset = upd["update_id"] + 1

            if "callback_query" in upd:
                cq = upd["callback_query"]
                uid = cq["from"]["id"]
                mid = cq["message"]["message_id"]
                cid = cq["message"]["chat"]["id"]

                if cq["data"] == "getnum":
                    waiting_range.add(uid)
                    pending_message[uid] = mid
                    tg_edit(cid, mid, "Kirim range contoh: <code>9377009XXX</code>")

            if "message" in upd:
                msg = upd["message"]
                uid = msg["from"]["id"]
                text = msg.get("text", "")

                if uid in waiting_range:
                    waiting_range.remove(uid)
                    await process_user_input(page, uid, text)

        await asyncio.sleep(1)

# ================= MAIN =================

def initialize_files():
    for f in [CACHE_FILE, INLINE_RANGE_FILE, WAIT_FILE]:
        if not os.path.exists(f):
            with open(f, "w") as x:
                x.write("[]")

async def main():
    print("[INFO] Starting bot...")
    initialize_files()

    sms_process = subprocess.Popen([sys.executable, "sms.py"])

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0]
        await telegram_loop(page)

if __name__ == "__main__":
    asyncio.run(main())
