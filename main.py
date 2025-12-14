import asyncio
import json
import os
import requests
import time # Import modul time
from playwright.async_api import async_playwright

# =======================
# CONFIG
# =======================
BOT_TOKEN = "8047851913:AAFGXlRL_e7JcLEMtOqUuuNd_46ZmIoGJN8"
GROUP_ID = -1003492226491  # HARUS NEGATIF
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
CACHE_FILE = "cache.json"

# --- NEW CONFIG ---
ADMIN_ID = 7184123643  # GANTI DENGAN ID TELEGRAM ADMIN SEBENARNYA
INLINE_RANGE_FILE = "inline.json"
OTP_STATUS_FILE = "otp_status.json" # FILE BARU UNTUK STATUS WAITING

# =======================
# GLOBAL STATE
# =======================
verified_users = set()
waiting_range = set()
waiting_admin_input = set() 
pending_message = {}  # user_id -> message_id Telegram sementara (untuk menu/manual range prompt)
sent_numbers = set()

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
# CACHE UTILS
# =======================
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
    cache = load_cache()
    return any(entry["number"] == number for entry in cache)

# =======================
# OTP STATUS UTILS (BARU)
# =======================
# Format data:
# [
#   {"id": 123456789, "number": "+23276284740", "range": "23276XXX", "status": "waiting", "message_id": 999, "user_id": 1234, "timestamp": 1700000000.0}
# ]
def load_otp_status():
    if os.path.exists(OTP_STATUS_FILE):
        with open(OTP_STATUS_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_otp_status(status_list):
    with open(OTP_STATUS_FILE, "w") as f:
        json.dump(status_list, f, indent=2)

def add_otp_status(user_id, number, range_prefix, message_id):
    status_list = load_otp_status()
    # Gunakan Unix timestamp (dengan 10 digit) sebagai ID unik sementara
    otp_id = int(time.time() * 1000) 
    
    new_entry = {
        "id": otp_id,
        "number": number,
        "range": range_prefix,
        "status": "waiting",
        "message_id": message_id,
        "user_id": user_id,
        "timestamp": time.time() # Waktu saat ditambahkan
    }
    status_list.append(new_entry)
    save_otp_status(status_list)
    return otp_id

def remove_otp_status(otp_id):
    status_list = load_otp_status()
    new_status_list = [entry for entry in status_list if entry["id"] != otp_id]
    save_otp_status(new_status_list)
    
def get_waiting_otp_numbers():
    status_list = load_otp_status()
    return [entry for entry in status_list if entry["status"] == "waiting"]

# =======================
# INLINE RANGE UTILS
# =======================
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

def generate_inline_keyboard(ranges):
    keyboard = []
    current_row = []
    
    for item in ranges:
        text = f"{item['country']} {item['emoji']}"
        callback_data = f"select_range:{item['range']}"
        current_row.append({"text": text, "callback_data": callback_data})
        
        if len(current_row) == 2:
            keyboard.append(current_row)
            current_row = []
    
    if current_row:
        keyboard.append(current_row)
        
    keyboard.append([{"text": "Manual Range", "callback_data": "manual_range"}])
    
    return {"inline_keyboard": keyboard}


# =======================
# TELEGRAM UTILS
# =======================
# ... (Fungsi tg_send, tg_edit, tg_get_updates, is_user_in_group tidak berubah)
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
# PARSE NOMOR & OTP (MODIFIKASI)
# =======================
async def get_number_and_country(page):
    """Mencari nomor baru yang belum ada di cache dan belum memiliki status."""
    rows = await page.query_selector_all("tbody tr")
    for row in rows:
        phone_el = await row.query_selector(".phone-number")
        if not phone_el:
            continue
        number = (await phone_el.inner_text()).strip()
        
        # Skip nomor yang sudah ada di cache
        if is_in_cache(number):
            continue
            
        # Skip nomor yang sudah ada status sukses/gagal
        if await row.query_selector(".status-success") or await row.query_selector(".status-failed"):
            continue
            
        country_el = await row.query_selector(".badge.bg-primary")
        country = (await country_el.inner_text()).strip().upper() if country_el else "-"
        
        return number, country, row
    return None, None, None

async def scrape_otp(row):
    """Mencoba mendapatkan OTP dan pesan lengkap dari elemen baris."""
    if not row:
        return None, None
        
    status_el = await row.query_selector(".status-badge.status-success")
    if not status_el:
        return None, None # Belum sukses
        
    otp_el = await row.query_selector(".otp-badge")
    if not otp_el:
        return None, None # Sukses tapi OTP badge belum ada
        
    otp_text = (await otp_el.inner_text()).strip()
    otp_code = otp_text.split()[0] if otp_text.split() else "-"
    
    # Ambil full message dari data-sms attribute
    copy_icon_el = await row.query_selector(".copy-icon")
    full_message = await copy_icon_el.get_attribute("data-sms") if copy_icon_el else "Tidak ada pesan penuh."

    return otp_code, full_message.replace("&lt;#&gt;", "<#>") # Mengganti entity HTML

async def check_for_otp(page, number_to_check):
    """Cek OTP untuk nomor spesifik di halaman saat ini."""
    rows = await page.query_selector_all("tbody tr")
    for row in rows:
        phone_el = await row.query_selector(".phone-number")
        if phone_el and (await phone_el.inner_text()).strip() == number_to_check:
            otp_code, full_message = await scrape_otp(row)
            return otp_code, full_message
    return None, None


# =======================
# PROCESS USER INPUT (MODIFIKASI)
# =======================
async def process_user_input(page, user_id, prefix, message_id_to_edit=None):
    try:
        # Menentukan Message ID yang akan diedit/dikirim (Untuk prompt/status awal)
        if message_id_to_edit:
            msg_id = message_id_to_edit
            tg_edit(user_id, msg_id, f"⏳ Sedang mengambil Number...\nRange: {prefix}")
        else:
            msg_id = tg_send(user_id, f"⏳ Sedang mengambil Number...\nRange: {prefix}")
            if not msg_id: return
            
        # 1. Isi input
        await page.wait_for_selector('input[name="numberrange"]', timeout=10000)
        await page.fill('input[name="numberrange"]', prefix)
        
        # 2. Jeda 0.1 detik
        await asyncio.sleep(0.1) 

        # 3. Klik Get Number
        await page.click("#getNumberBtn")

        # 4. Jeda 1 detik
        await asyncio.sleep(1) 

        # 5. Refresh halaman dan tunggu load penuh (State 'load')
        await page.reload()
        await page.wait_for_load_state("load") 

        # 6. Jeda 1.5 detik sebelum scraping
        await asyncio.sleep(1.5) 

        # 7. Scrape nomor & negara terbaru (Percobaan Pertama)
        number, country, _ = await get_number_and_country(page)
        
        # Logika Tambahan: Jeda 3 detik dan coba scrape lagi jika percobaan pertama gagal
        if not number:
            tg_edit(user_id, msg_id, f"⏳ Nomor belum muncul, mencoba lagi dalam 3 detik...\nRange: {prefix}")
            await asyncio.sleep(3) 
            number, country, _ = await get_number_and_country(page)
        
        # Final Check: Jika masih tidak menemukan nomor
        if not number:
            tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DI TEMUKAN SILAHKAN GET ULANG")
            if user_id in pending_message and pending_message[user_id] == msg_id:
                del pending_message[user_id]
            return

        # simpan nomor baru ke cache
        save_cache({"number": number, "country": country})

        # --- KIRIM PESAN WAITING OTP (PERMANEN) ---
        emoji = COUNTRY_EMOJI.get(country, "🗺️")
        
        # Pesan awal yang akan diedit oleh otp_checker
        msg_waiting = (
            "⏳ WAITING FOR OTP\n\n"
            f"📞 Number  : <code>{number}</code>\n"
            f"{emoji} COUNTRY : {country}\n"
            f"🏷️ Range   : <code>{prefix}</code>\n"
            f"ID (Sementara) : <code>{int(time.time() * 1000)}</code>"
        )
        
        inline_kb_waiting = {
            "inline_keyboard": [
                [{"text": "⏳ Waiting for OTP", "callback_data": "noop"}], # No-op button
                [{"text": "🔐 OTP Grup", "url": "https://t.me/+E5grTSLZvbpiMTI1"}]
            ]
        }
        
        # Kirim ulang pesan WAITING (tidak mengedit msg_id lama)
        # Atau edit jika memang berasal dari menu/manual prompt
        if message_id_to_edit:
             tg_edit(user_id, message_id_to_edit, msg_waiting, reply_markup=inline_kb_waiting)
             final_msg_id = message_id_to_edit # Tetap gunakan ID pesan yang sudah ada
        else:
            # Jika msg_id didapatkan dari tg_send baru, anggap itu ID pesan final
            final_msg_id = msg_id

        # Simpan status ke otp_status.json
        add_otp_status(user_id, number, prefix, final_msg_id)
        
        # Hapus ID dari pending_message
        if user_id in pending_message:
            del pending_message[user_id]

    except Exception as e:
        print(f"[ERROR] Terjadi kesalahan pada Playwright/Web: {e}")
        error_msg_id = message_id_to_edit if message_id_to_edit else pending_message.get(user_id)
        if error_msg_id:
            tg_edit(user_id, error_msg_id, f"❌ Terjadi kesalahan saat proses web. Cek log bot: {type(e).__name__}")
            if user_id in pending_message:
                del pending_message[user_id]

# =======================
# OTP CHECKER LOOP (BARU)
# =======================
async def otp_checker(page):
    while True:
        try:
            # 1. Refresh halaman Playwright
            await page.reload(wait_until="load")
            await asyncio.sleep(1.5) 
            
            waiting_numbers = get_waiting_otp_numbers()
            
            for entry in waiting_numbers:
                otp_id = entry["id"]
                user_id = entry["user_id"]
                number = entry["number"]
                range_prefix = entry["range"]
                msg_id = entry["message_id"]
                timestamp = entry["timestamp"]
                
                # Check Timeout (10 minutes)
                if time.time() - timestamp > 600: # 600 detik = 10 menit
                    # Edit pesan menjadi timeout
                    timeout_msg = (
                        "❌ TIMEOUT (10 Menit)\n\n"
                        f"📞 Number  : <code>{number}</code>\n"
                        f"🏷️ Range   : <code>{range_prefix}</code>"
                    )
                    
                    inline_kb_timeout = {
                        "inline_keyboard": [
                            [{"text": "📲 Get Number", "callback_data": "getnum"}],
                            [{"text": "🔐 OTP Grup", "url": "https://t.me/+E5grTSLZvbpiMTI1"}]
                        ]
                    }
                    tg_edit(user_id, msg_id, timeout_msg, reply_markup=inline_kb_timeout)
                    
                    # Hapus dari status
                    remove_otp_status(otp_id)
                    print(f"[INFO] Nomor {number} dihapus karena timeout.")
                    continue

                # 2. Cek apakah OTP sudah muncul
                otp_code, full_message = await check_for_otp(page, number)
                
                if otp_code:
                    # OTP DITEMUKAN!
                    # Scrape kembali info negara (tidak ada di entry)
                    rows = await page.query_selector_all("tbody tr")
                    country = "UNKNOWN"
                    for row in rows:
                        phone_el = await row.query_selector(".phone-number")
                        if phone_el and (await phone_el.inner_text()).strip() == number:
                            country_el = await row.query_selector(".badge.bg-primary")
                            country = (await country_el.inner_text()).strip().upper() if country_el else "-"
                            break
                            
                    emoji = COUNTRY_EMOJI.get(country, "🗺️")

                    # KIRIM PESAN SUKSES
                    msg_success = (
                        "SUKSES MESSAGE IS READY🥳\n\n"
                        f"📞 Number  : <code>{number}</code>\n"
                        f"{emoji} COUNTRY : {country}\n"
                        f"🏷️ Range   : <code>{range_prefix}</code>\n"
                        "\n"
                        f"🔢 OTP : <code>{otp_code}</code>\n"
                        "\n"
                        "Full Messages :\n"
                        f"<blockquote>{full_message}</blockquote>"
                    )
                    
                    inline_kb_success = {
                        "inline_keyboard": [
                            [{"text": "📲 Get Number", "callback_data": "getnum"}],
                            [{"text": "🔐 OTP Grup", "url": "https://t.me/+E5grTSLZvbpiMTI1"}]
                        ]
                    }

                    tg_edit(user_id, msg_id, msg_success, reply_markup=inline_kb_success)
                    
                    # Hapus dari status
                    remove_otp_status(otp_id)
                    print(f"[INFO] OTP ditemukan untuk {number}, pesan diedit.")
                    
        except Exception as e:
            print(f"[ERROR] Terjadi kesalahan pada OTP Checker: {e}")
            
        await asyncio.sleep(10) # Cek setiap 10 detik

# =======================
# TELEGRAM LOOP
# =======================
async def telegram_loop(page):
    offset = 0
    while True:
        try:
            data = tg_get_updates(offset)
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1

                if "message" in upd:
                    msg = upd["message"]
                    user_id = msg["chat"]["id"]
                    username = msg["from"].get("username", "-")
                    text = msg.get("text", "")

                    # --- ADMIN COMMAND HANDLER ---
                    if user_id == ADMIN_ID:
                        if text.startswith("/add"):
                            waiting_admin_input.add(user_id)
                            msg_id = tg_send(user_id, "Silahkan kirim daftar range dalam format:\n\n<code>range > country</code>\n\nContoh:\n<code>23273XXX > SIERRA LEONE\n97798XXXX > NEPAL</code>")
                            if msg_id:
                                pending_message[user_id] = msg_id
                            continue
                    
                    if user_id in waiting_admin_input:
                        waiting_admin_input.remove(user_id)
                        new_ranges = []
                        for line in text.strip().split('\n'):
                            if ' > ' in line:
                                parts = line.split(' > ', 1)
                                range_prefix = parts[0].strip()
                                country_name = parts[1].strip().upper()
                                emoji = COUNTRY_EMOJI.get(country_name, "🗺️")

                                new_ranges.append({
                                    "range": range_prefix, 
                                    "country": country_name, 
                                    "emoji": emoji
                                })

                        prompt_msg_id = pending_message.pop(user_id, None)
                        
                        if new_ranges:
                            save_inline_ranges(new_ranges)
                            if prompt_msg_id:
                                tg_edit(user_id, prompt_msg_id, f"✅ Berhasil menyimpan {len(new_ranges)} range ke inline.json.")
                        else:
                            if prompt_msg_id:
                                tg_edit(user_id, prompt_msg_id, "❌ Format tidak valid atau tidak ada range yang ditemukan. Batalkan penambahan range.")
                        
                        continue
                    # --- END ADMIN COMMAND HANDLER ---


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
                        waiting_range.remove(user_id)
                        prefix = text.strip()
                        
                        # Message ID yang akan diedit adalah pesan "Kirim range contoh..."
                        msg_id_to_edit = pending_message.pop(user_id, None) 
                        
                        # Memanggil process_user_input dengan ID pesan untuk diedit
                        await process_user_input(page, user_id, prefix, msg_id_to_edit)
                        
                        continue

                if "callback_query" in upd:
                    cq = upd["callback_query"]
                    user_id = cq["from"]["id"]
                    data_cb = cq["data"]
                    
                    chat_id = cq["message"]["chat"]["id"]
                    menu_msg_id = cq["message"]["message_id"]

                    if data_cb == "verify":
                        if not is_user_in_group(user_id):
                            tg_edit(chat_id, menu_msg_id, "❌ Belum gabung grup, silakan join dulu.")
                        else:
                            verified_users.add(user_id)
                            kb = {
                                "inline_keyboard": [
                                    [{"text": "📲 Get Number", "callback_data": "getnum"}],
                                    [{"text": "👨‍💼 Admin", "url": "https://t.me/"}],
                                ]
                            }
                            tg_edit(chat_id, menu_msg_id, f"✅ Verifikasi Berhasil!\n\nGunakan tombol di bawah:", kb)
                        continue

                    if data_cb == "getnum":
                        if user_id not in verified_users:
                            tg_edit(chat_id, menu_msg_id, "⚠️ Harap verifikasi dulu.")
                            continue
                        
                        inline_ranges = load_inline_ranges()
                        
                        if inline_ranges:
                            kb = generate_inline_keyboard(inline_ranges)
                            msg_text = "Range tersedia saat ini, silahkan gunakan range di bawah atau Manual Range."
                            tg_edit(chat_id, menu_msg_id, f"<b>Get Number</b>\n\n{msg_text}", kb)
                            pending_message[user_id] = menu_msg_id
                        else:
                            waiting_range.add(user_id)
                            tg_edit(chat_id, menu_msg_id, "Kirim range contoh: <code>628272XXXX</code>")
                            pending_message[user_id] = menu_msg_id
                        continue
                        
                    if data_cb == "noop":
                         # Callback untuk tombol "Waiting for OTP", tidak melakukan apa-apa
                         pass

                    if data_cb.startswith("select_range:"):
                        if user_id not in verified_users:
                            tg_edit(chat_id, menu_msg_id, "⚠️ Harap verifikasi dulu.")
                            continue
                            
                        prefix = data_cb.split(":")[1]
                        
                        tg_edit(chat_id, menu_msg_id, f"<b>Get Number</b>\n\nRange dipilih: <code>{prefix}</code>\n⏳ Sedang memproses...")
                        
                        await process_user_input(page, user_id, prefix, menu_msg_id)
                        continue

                    if data_cb == "manual_range":
                        waiting_range.add(user_id)
                        
                        tg_edit(chat_id, menu_msg_id, "<b>Get Number</b>\n\nKirim range contoh: <code>628272XXXX</code>")
                        
                        pending_message[user_id] = menu_msg_id
                        continue

            await asyncio.sleep(1)
        except Exception as e:
            print(f"[ERROR] Terjadi kesalahan pada Telegram Loop: {e}")
            await asyncio.sleep(5)


# =======================
# MAIN
# =======================
async def main():
    async with async_playwright() as p:
        # PENTING: Pastikan Chrome sudah berjalan di port 9222 dengan remote debugging
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            # Ambil halaman pertama yang sudah ada (halaman utama scraping)
            if not context.pages:
                page = await context.new_page()
            else:
                page = context.pages[0]
            print("[OK] Connected to existing Chrome")
        except Exception as e:
            print(f"[FATAL] Gagal terhubung ke Chrome: {e}")
            return

        tg_send(GROUP_ID, "✅ Bot Number Active!")

        # Jalankan Telegram Loop dan OTP Checker secara paralel
        await asyncio.gather(
            telegram_loop(page),
            otp_checker(page)
        )

if __name__ == "__main__":
    asyncio.run(main())
