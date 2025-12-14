import asyncio
import requests
from playwright.async_api import async_playwright

# =======================
# CONFIG
# =======================
BOT_TOKEN = "8047851913:AAFGXlRL_e7JcLEMtOqUuuNd_46ZmIoGJN8"
GROUP_ID = -1003492226491  # HARUS NEGATIF
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# =======================
# GLOBAL STATE
# =======================
verified_users = set()
waiting_range = set()
sent_numbers = set()
pending_message = {}  # user_id -> message_id Telegram sementara

# =======================
# COUNTRY EMOJI
# =======================
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

# =======================
# TELEGRAM UTILS
# =======================
def tg_send(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    r = requests.post(f"{API}/sendMessage", json=data).json()
    if r.get("ok"):
        return r["result"]["message_id"]
    return None

def tg_edit(chat_id, message_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    requests.post(f"{API}/editMessageText", json=data)

def tg_get_updates(offset):
    return requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 30}).json()

def is_user_in_group(user_id):
    r = requests.get(f"{API}/getChatMember", params={"chat_id": GROUP_ID, "user_id": user_id}).json()
    if not r.get("ok"):
        return False
    return r["result"]["status"] in ["member", "administrator", "creator"]

# =======================
# PARSE NOMOR
# =======================
async def get_number_and_country(page):
    rows = await page.query_selector_all("tbody tr")
    for row in rows:
        phone_el = await row.query_selector(".phone-number")
        if not phone_el:
            continue
        number = (await phone_el.inner_text()).strip()
        if number in sent_numbers:
            continue
        if await row.query_selector(".status-success") or await row.query_selector(".status-failed"):
            continue
        country_el = await row.query_selector(".badge.bg-primary")
        country = (await country_el.inner_text()).strip().upper() if country_el else "-"
        return number, country
    return None, None

# =======================
# PROCESS USER REQUEST
# =======================
async def process_user_input(page, user_id, prefix):
    try:
        # kirim pesan pending
        msg_id = tg_send(user_id, f"⏳ Sedang mengambil Number...\nRange: {prefix}")
        pending_message[user_id] = msg_id

        # refresh halaman dan tunggu load
        await page.reload()
        await page.wait_for_load_state("networkidle")

        # input prefix & klik tombol
        await page.wait_for_selector('input[name="numberrange"]', timeout=10000)
        await page.fill('input[name="numberrange"]', prefix)
        await page.click("#getNumberBtn")

        # tunggu table muncul
        await page.wait_for_selector("tbody tr", timeout=10000)

        number, country = await get_number_and_country(page)
        if not number:
            tg_edit(user_id, pending_message[user_id], "❌ Nomor tidak ditemukan, coba lagi nanti.")
            del pending_message[user_id]
            return

        sent_numbers.add(number)

        emoji = COUNTRY_EMOJI.get(country, "🗺️")
        msg = (
            "✅ The number is ready\n\n"
            f"📞 Number  : <code>{number}</code>\n"
            f"{emoji} COUNTRY : {country}\n"
            f"🏷️ Range   : <code>{prefix}</code>"
        )

        inline_kb = {
            "inline_keyboard": [
                [{"text": "📲 Get Number", "callback_data": "getnum"}],
                [{"text": "🔐 OTP Grup", "url": "https://t.me/+E5grTSLZvbpiMTI1"}]
            ]
        }

        tg_edit(user_id, pending_message[user_id], msg, reply_markup=inline_kb)
        del pending_message[user_id]

    except Exception as e:
        print(f"[ERROR] {e}")
        if user_id in pending_message:
            tg_edit(user_id, pending_message[user_id], f"❌ Terjadi kesalahan: {e}")
            del pending_message[user_id]

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
                username = msg["from"].get("username", "-")
                text = msg.get("text", "")

                # start command
                if text == "/start":
                    kb = {
                        "inline_keyboard": [
                            [{"text": "📌 Gabung Grup", "url": "https://t.me/+E5grTSLZvbpiMTI1"}],
                            [{"text": "✅ Verifikasi", "callback_data": "verify"}],
                        ]
                    }
                    tg_send(user_id, f"Halo @{username} 👋\nGabung grup untuk verifikasi.", kb)
                    continue

                # user kirim range
                if user_id in waiting_range:
                    waiting_range.remove(user_id)
                    prefix = text.strip()
                    # langsung proses input tanpa queue
                    await process_user_input(page, user_id, prefix)

            # callback query
            if "callback_query" in upd:
                cq = upd["callback_query"]
                user_id = cq["from"]["id"]
                data_cb = cq["data"]
                username = cq["from"].get("username", "-")

                if data_cb == "verify":
                    if not is_user_in_group(user_id):
                        tg_send(user_id, "❌ Belum gabung grup, silakan join dulu.")
                    else:
                        verified_users.add(user_id)
                        kb = {
                            "inline_keyboard": [
                                [{"text": "📲 Get Number", "callback_data": "getnum"}],
                                [{"text": "👨‍💼 Admin", "url": "https://t.me/"}],
                            ]
                        }
                        tg_send(user_id, f"✅ Verifikasi Berhasil!\n\nUser : @{username}\nGunakan tombol di bawah:", kb)

                if data_cb == "getnum":
                    if user_id not in verified_users:
                        tg_send(user_id, "⚠️ Harap verifikasi dulu.")
                        continue
                    waiting_range.add(user_id)
                    tg_send(user_id, "Kirim range contoh: <code>628272XXXX</code>")

        await asyncio.sleep(1)

# =======================
# MAIN
# =======================
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0]
        print("[OK] Connected to existing Chrome")

        # kirim pesan ke grup saat bot aktif
        tg_send(GROUP_ID, "✅ Bot Number Active!")

        await telegram_loop(page)

if __name__ == "__main__":
    asyncio.run(main())
