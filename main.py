import asyncio
import time
import aiohttp
import requests
from collections import deque
from playwright.async_api import async_playwright

# =======================
# CONFIG
# =======================
BOT_TOKEN = "8047851913:AAFGXlRL_e7JcLEMtOqUuuNd_46ZmIoGJN8"
GROUP_ID = -1003492226491  # ?? HARUS NEGATIF
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
GET_NUMBER_DELAY = 3

# =======================
# GLOBAL STATE
# =======================
verified_users = set()
waiting_range = set()
user_last_range = {}
user_queues = {}
user_last_time = {}
sent_numbers = set()
pending_message = {}  # user_id -> message_id

# =======================
# TELEGRAM ASYNC UTILS
# =======================
async def tg_send(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    async with aiohttp.ClientSession() as s:
        async with s.post(f"{API}/sendMessage", json=payload) as r:
            data = await r.json()
            return data["result"]["message_id"]

async def tg_edit(chat_id, msg_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": msg_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    async with aiohttp.ClientSession() as s:
        async with s.post(f"{API}/editMessageText", json=payload):
            pass

def tg_get_updates(offset):
    return requests.get(
        f"{API}/getUpdates",
        params={"offset": offset, "timeout": 30}
    ).json()

def is_user_in_group(user_id):
    r = requests.get(
        f"{API}/getChatMember",
        params={"chat_id": GROUP_ID, "user_id": user_id}
    ).json()
    if not r.get("ok"):
        return False
    return r["result"]["status"] in ["member", "administrator", "creator"]

def can_process(user_id):
    return time.time() - user_last_time.get(user_id, 0) >= GET_NUMBER_DELAY

# =======================
# GET NUMBER (FAST)
# =======================
async def get_number_and_country(page):
    row = await page.query_selector("tbody tr")
    if not row:
        return None, None

    phone = await row.query_selector(".phone-number")
    if not phone:
        return None, None

    number = (await phone.inner_text()).strip()
    if number in sent_numbers:
        return None, None

    country_el = await row.query_selector(".badge.bg-primary")
    country = (await country_el.inner_text()).strip() if country_el else "-"

    return number, country

# =======================
# PROCESS QUEUE
# =======================
async def process_user_queue(page, user_id):
    if user_id not in user_queues or not user_queues[user_id]:
        return
    if not can_process(user_id):
        return

    req = user_queues[user_id].popleft()
    prefix = req["prefix"]

    try:
        await page.wait_for_selector('input[name="numberrange"]', timeout=5000)
        await page.fill('input[name="numberrange"]', prefix)
        await page.click("#getNumberBtn")

        await page.wait_for_selector("tbody tr .phone-number", timeout=5000)
        number, country = await get_number_and_country(page)

        if not number:
            return

        sent_numbers.add(number)
        user_last_time[user_id] = time.time()

        msg = (
            "✅ <b>The number is ready</b>\n\n"
            f"📞 Number  : <code>{number}</code>\n"
            f"🌍 Country : {country}\n"
            f"📌 Range   : <code>{prefix}</code>"
        )

        await tg_edit(
            user_id,
            pending_message[user_id],
            msg,
            reply_markup={
                "inline_keyboard": [
                    [
                        {"text": "🔁 Change", "callback_data": "change"},
                        {"text": "🔐 OTP Grup", "url": "https://t.me/+E5grTSLZvbpiMTI1"}
                    ]
                ]
            }
        )

    except Exception as e:
        print("[ERROR]", e)

# =======================
# TELEGRAM LOOP
# =======================
async def telegram_loop(page):
    offset = 0
    while True:
        data = tg_get_updates(offset)
        for upd in data.get("result", []):
            offset = upd["update_id"] + 1

            if "message" in upd:
                msg = upd["message"]
                user_id = msg["chat"]["id"]
                text = msg.get("text", "")
                username = msg["from"].get("username", "-")

                if text == "/start":
                    await tg_send(
                        user_id,
                        f"Halo @{username} 👋\nGabung grup lalu verifikasi.",
                        {
                            "inline_keyboard": [
                                [{"text": "📌 Gabung Grup", "url": "https://t.me/+E5grTSLZvbpiMTI1"}],
                                [{"text": "✅ Verifikasi", "callback_data": "verify"}],
                            ]
                        }
                    )

                elif user_id in waiting_range:
                    waiting_range.remove(user_id)
                    user_last_range[user_id] = text
                    user_queues.setdefault(user_id, deque()).append({"prefix": text})
                    msg_id = await tg_send(
                        user_id,
                        "⏳ <b>Processing...</b>\nPlease wait"
                    )
                    pending_message[user_id] = msg_id

            if "callback_query" in upd:
                cq = upd["callback_query"]
                user_id = cq["from"]["id"]
                data_cb = cq["data"]

                if data_cb == "verify":
                    if not is_user_in_group(user_id):
                        await tg_send(user_id, "❌ Join grup dulu.")
                    else:
                        verified_users.add(user_id)
                        await tg_send(
                            user_id,
                            "✅ Verifikasi berhasil",
                            {
                                "inline_keyboard": [
                                    [{"text": "📲 Get Num", "callback_data": "getnum"}]
                                ]
                            }
                        )

                elif data_cb == "getnum":
                    if user_id not in verified_users:
                        await tg_send(user_id, "⚠️ Verifikasi dulu.")
                        continue
                    waiting_range.add(user_id)
                    await tg_send(user_id, "Kirim range contoh:\n<code>62827XXXX</code>")

                elif data_cb == "change":
                    prefix = user_last_range.get(user_id)
                    if prefix:
                        user_queues.setdefault(user_id, deque()).append({"prefix": prefix})
                        msg_id = await tg_send(user_id, "⏳ <b>Changing number...</b>")
                        pending_message[user_id] = msg_id

        await asyncio.sleep(1)

# =======================
# WORKER LOOP
# =======================
async def worker_loop(page):
    while True:
        for uid in list(user_queues.keys()):
            await process_user_queue(page, uid)
        await asyncio.sleep(0.5)

# =======================
# MAIN
# =======================
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0]
        print("[OK] Connected to Chrome Debug")

        await tg_send(GROUP_ID, "✅ Bot Number Active")

        await asyncio.gather(
            telegram_loop(page),
            worker_loop(page)
        )

if __name__ == "__main__":
    asyncio.run(main())
