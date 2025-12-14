import asyncio
import time
import requests
from collections import deque
from playwright.async_api import async_playwright

# =======================
# CONFIG
# =======================
BOT_TOKEN = "8047851913:AAFGXlRL_e7JcLEMtOqUuuNd_46ZmIoGJN8"
GROUP_ID = -1003492226491  # ?? HARUS NEGATIF
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
GET_NUMBER_DELAY = 3  # detik per user

# =======================
# GLOBAL STATE
# =======================
verified_users = set()
waiting_range = set()
user_last_range = {}
user_queues = {}
user_last_time = {}
sent_numbers = set()
pending_message = {}  # user_id -> message_id Telegram sementara

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

def can_process(user_id):
    last = user_last_time.get(user_id, 0)
    return time.time() - last >= GET_NUMBER_DELAY

# =======================
# HELPER: MAPPING NEGARA KE EMOJI
# =======================
def get_country_emoji(country_name):
    # Mapping negara berdasarkan permintaan, bisa dikembangkan lebih lanjut
    # Nama negara yang diekstrak dari web mungkin berbeda dari nama di sini
    country_map = {
        "Nepal": "🇳🇵",
        "Ivory Coast": "🇨🇮",
        "Guinea": "🇬🇳",
        "Central Africa": "🇨🇫", # Menggunakan "Central Africa" untuk "Central Afrika"
        "Togo": "🇹🇬",
        "Tajikistan": "🇹🇯",
        "Benin": "🇧🇯",
        "Sierra Leone": "🇸🇱",
        "Madagascar": "🇲🇬",
        "Afganistan": "🇦🇫",
        # Tambahkan negara lain sesuai kebutuhan
    }
    # Coba cari persis, atau pakai default
    # Coba cari dengan mengabaikan kasus
    for k, v in country_map.items():
        if k.lower() in country_name.lower():
            return v
    
    return "🗺️" # Emoji default

# =======================
# PARSE NOMOR
# =======================
async def get_number_and_country(page):
    # Tunggu nomor muncul. Kita tidak lagi menunggu 2.5 detik,
    # tapi kita harus menunggu sampai baris/tabel diperbarui.
    # Kita akan menunggu *selector* yang mengindikasikan nomor baru siap
    # atau status nomor telah diperbarui.
    try:
        # Menunggu sampai tabel nomor diperbarui, misalnya menunggu baris baru muncul
        # atau tombol 'Get Number' kembali aktif setelah klik.
        # Karena kita tidak tahu persis DOM mana yang berubah, kita akan
        # mencoba menunggu perubahan di dalam tabel
        await page.wait_for_selector('tbody tr:not(.new-row-indicator-that-is-not-there)', timeout=10000)
    except:
        # Jika timeout, tetap lanjut dengan apa yang ada (mungkin nomor sudah ada)
        pass

    rows = await page.query_selector_all("tbody tr")
    for row in rows:
        phone_el = await row.query_selector(".phone-number")
        if not phone_el:
            continue
        number = (await phone_el.inner_text()).strip()
        if number in sent_numbers:
            continue
        # Periksa apakah nomor sudah berhasil/gagal (jika ada indikator status)
        if await row.query_selector(".status-success") or await row.query_selector(".status-failed"):
            continue
        
        country_el = await row.query_selector(".badge.bg-primary")
        country = (await country_el.inner_text()).strip() if country_el else "-"
        
        # Asumsi nomor pertama yang belum terkirim dan belum ada status adalah nomor baru
        # Kita akan mengambil nomor pertama yang ditemukan
        return number, country
    
    return None, None

# =======================
# PROCESS USER REQUEST
# =======================
async def process_user_queue(page, user_id):
    if user_id not in user_queues or not user_queues[user_id]:
        return
    if not can_process(user_id):
        return

    req = user_queues[user_id].popleft()
    prefix = req["prefix"]

    try:
        # 1. Input Range
        await page.wait_for_selector('input[name="numberrange"]', timeout=5000)
        await page.click('input[name="numberrange"]')
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await page.type('input[name="numberrange"]', prefix, delay=50)

        # 2. Klik Get Number
        await page.wait_for_selector("#getNumberBtn", timeout=5000)
        await page.evaluate("document.querySelector('#getNumberBtn').click()")

        # --- PERUBAHAN UTAMA: TIDAK ADA wait_for_timeout(2500) ---
        # Kita langsung panggil get_number_and_country yang sekarang menangani
        # menunggu pembaruan di halaman web.

        number, country = await get_number_and_country(page)
        
        if not number:
            # hapus pending message jika ada
            if user_id in pending_message:
                tg_edit(user_id, pending_message[user_id], "❌ Nomor tidak ditemukan, coba lagi nanti.")
                del pending_message[user_id]
            return

        sent_numbers.add(number)
        user_last_time[user_id] = time.time()
        
        # Ambil emoji bendera
        emoji = get_country_emoji(country)

        # --- PERUBAHAN: FORMAT PESAN BARU ---
        msg = (
            "✅ **The number is ready**\n\n"
            f"📞 **Number** : <code>{number}</code>\n"
            f"{emoji} **Country** : {country}\n"
            f"🏷️ **Range** : <code>{prefix}</code>"
        )
        
        # --- PERUBAHAN: REPLY MARKUP BARU ---
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "📲 Get Num", "callback_data": "getnum"},
                    {"text": "🔐 OTP Grup", "url": "https://t.me/+E5grTSLZvbpiMTI1"}
                ]
            ]
        }


        # kirim atau edit pesan pending
        if user_id in pending_message:
            tg_edit(user_id, pending_message[user_id], msg, reply_markup=reply_markup)
            del pending_message[user_id]
        else:
            tg_send(user_id, msg, reply_markup=reply_markup)

    except Exception as e:
        print(f"[ERROR] {e}")
        # Hapus/edit pesan pending jika terjadi error
        if user_id in pending_message:
             tg_edit(user_id, pending_message[user_id], f"❌ Terjadi kesalahan saat mengambil nomor: {e}")
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

                if text == "/start":
                    kb = {
                        "inline_keyboard": [
                            [{"text": "📌 Gabung Grup", "url": "https://t.me/+E5grTSLZvbpiMTI1"}],
                            [{"text": "✅ Verifikasi", "callback_data": "verify"}],
                        ]
                    }
                    tg_send(user_id, f"Halo @{username} 👋\nGabung grup untuk verifikasi.", kb)
                    continue

                if user_id in waiting_range:
                    prefix = text.strip()
                    if not prefix: # Pastikan ada input
                        tg_send(user_id, "⚠️ Range tidak boleh kosong. Silakan kirim range contoh: <code>628272XXXX</code>")
                        continue
                        
                    waiting_range.remove(user_id)
                    user_last_range[user_id] = prefix
                    user_queues.setdefault(user_id, deque()).append({"prefix": prefix, "time": time.time()})
                    
                    # kirim pesan pending sementara
                    msg_id = tg_send(user_id, f"⏳ Sedang mengambil Number...\nRange: <code>{prefix}</code>\nUserID: {user_id}")
                    pending_message[user_id] = msg_id

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
                                [{"text": "📲 Get Num", "callback_data": "getnum"}],
                                [{"text": "👨‍💼 Admin", "url": "https://t.me/"}],
                            ]
                        }
                        tg_send(user_id, f"✅ Verifikasi Berhasil!\n\nUser : @{username}\nId : {user_id}\nGunakan tombol di bawah:", kb)

                if data_cb == "getnum":
                    if user_id not in verified_users:
                        tg_send(user_id, "⚠️ Harap verifikasi dulu.")
                        continue
                    waiting_range.add(user_id)
                    tg_send(user_id, "Kirim range contoh: <code>628272XXXX</code>")

        await asyncio.sleep(1)

# =======================
# WORKER LOOP
# =======================
async def worker_loop(page):
    while True:
        # Iterasi melalui salinan kunci untuk menghindari masalah ukuran kamus saat popleft()
        for user_id in list(user_queues.keys()):
            await process_user_queue(page, user_id)
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

        await asyncio.gather(
            telegram_loop(page),
            worker_loop(page)
        )

if __name__ == "__main__":
    asyncio.run(main())
