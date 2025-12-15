import asyncio
import json
import os
import requests
import time
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

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
OTP_STATE_FILE = "otp_state.json" 
# URL halaman scraping (GANTI DENGAN URL ASLI ANDA!)
SCRAPE_URL = "https://v2.mnitnetwork.com/dashboard/getnum" 

# =======================
# GLOBAL STATE
# =======================
verified_users = set()
waiting_range = set()
waiting_admin_input = set() 
pending_message = {}  # user_id -> message_id Telegram sementara
sent_numbers = set()
# otp_state: {number: {"user_id": int, "range": str, "message": str, "timestamp": float, "country": str}}
otp_state = {} 

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
            return json.load(f)
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
# OTP STATE UTILS
# =======================
def load_otp_state():
    global otp_state
    if os.path.exists(OTP_STATE_FILE):
        with open(OTP_STATE_FILE, "r") as f:
            try:
                data = json.load(f)
                otp_state = {k: {**v, 'timestamp': float(v['timestamp'])} for k, v in data.items()}
            except json.JSONDecodeError:
                otp_state = {}
    
def save_otp_state():
    with open(OTP_STATE_FILE, "w") as f:
        json.dump(otp_state, f, indent=2)

def add_to_otp_state(number, user_id, prefix, country):
    otp_state[number] = {
        "user_id": user_id,
        "range": prefix,
        "country": country,
        "message": "waiting",
        "timestamp": time.time()
    }
    save_otp_state()

def delete_otp_state(number):
    if number in otp_state:
        del otp_state[number]
        save_otp_state()

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
# PARSE NOMOR & OTP
# =======================
async def get_number_and_country(page):
    rows = await page.query_selector_all("tbody tr")
    for row in rows:
        phone_el = await row.query_selector(".phone-number")
        if not phone_el: continue
        number = (await phone_el.inner_text()).strip()
        
        if is_in_cache(number): continue
        if await row.query_selector(".status-success") or await row.query_selector(".status-failed"): continue
            
        country_el = await row.query_selector(".badge.bg-primary")
        country = (await country_el.inner_text()).strip().upper() if country_el else "-"
        return number, country
    return None, None

async def get_otp_message(page, number_to_check):
    rows = await page.query_selector_all("tbody tr")
    for row in rows:
        phone_el = await row.query_selector(".phone-number")
        if not phone_el: continue
        number = (await phone_el.inner_text()).strip()
        
        if number == number_to_check:
            country_el = await row.query_selector(".badge.bg-primary")
            country = (await country_el.inner_text()).strip().upper() if country_el else "-"
            
            is_success = await row.query_selector(".status-success")
            is_failed = await row.query_selector(".status-failed")
            
            if is_success:
                otp_el = await row.query_selector(".otp-badge")
                full_sms_el = await row.query_selector(".copy-icon")
                
                otp_text = await otp_el.inner_text() if otp_el else "-"
                otp = otp_text.split()[0].strip() if ' ' in otp_text else otp_text.strip()
                
                full_sms_data = await full_sms_el.get_attribute("data-sms") if full_sms_el else "Tidak ada pesan"

                return "success", otp, full_sms_data, country
            
            if is_failed:
                return "failed", "-", "-", country
                
            return "waiting", "-", "-", country

    return None, None, None, None 

# =======================
# PROCESS USER INPUT
# =======================
async def process_user_input(browser_context, user_id, prefix, message_id_to_edit=None):
    page = None
    try:
        # 1. Buka Page/Tab baru
        page = await browser_context.new_page()
        # Menggunakan wait_until="domcontentloaded" untuk load yang lebih cepat
        await page.goto(SCRAPE_URL, wait_until="domcontentloaded", timeout=20000) 

        # 2. Menentukan Message ID yang akan diedit
        if message_id_to_edit:
            msg_id = message_id_to_edit
            tg_edit(user_id, msg_id, f"⏳ Sedang mengambil Number...\nRange: {prefix}")
        else:
            msg_id = tg_send(user_id, f"⏳ Sedang mengambil Number...\nRange: {prefix}")
            if not msg_id: return
            
        # 3. Isi input dan Klik Get Number
        await page.wait_for_selector('input[name="numberrange"]', timeout=10000)
        await page.fill('input[name="numberrange"]', prefix)
        await asyncio.sleep(0.2) 

        # Klik Get Number dan tunggu potensi navigasi/reload
        try:
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=5000):
                await page.click("#getNumberBtn")
        except PlaywrightTimeoutError:
            print("[DEBUG] Klik tidak memicu navigasi. Melanjutkan...")
            pass 

        await asyncio.sleep(2) 

        # 4. Scrape nomor & negara terbaru (Percobaan Pertama)
        number, country = await get_number_and_country(page)
        
        # Logika Tambahan: Retry jika percobaan pertama gagal
        if not number:
            tg_edit(user_id, msg_id, f"⏳ Nomor belum muncul, mencoba lagi dalam 3 detik...\nRange: {prefix}")
            await asyncio.sleep(3) 
            number, country = await get_number_and_country(page)
        
        # Final Check: Jika masih tidak menemukan nomor
        if not number:
            tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DI TEMUKAN SILAHKAN GET ULANG")
            if user_id in pending_message and pending_message[user_id] == msg_id: del pending_message[user_id]
            return

        # simpan nomor baru ke cache dan OTP State
        save_cache({"number": number, "country": country})
        add_to_otp_state(number, user_id, prefix, country)

        emoji = COUNTRY_EMOJI.get(country, "🗺️")
        
        # PERUBAHAN TEKS STATUS WAITING
        msg = (
            "✅ The number is ready\n\n"
            f"📞 Number  : <code>{number}</code>\n"
            f"{emoji} COUNTRY : {country}\n"
            f"🏷️ Range   : <code>{prefix}</code>\n\n"
            f"message will come here or check otp group." # TEKS BARU
        )

        inline_kb = {
            "inline_keyboard": [
                [{"text": "📲 Get Number", "callback_data": "getnum"}],
                [{"text": "🔐 OTP Grup", "url": "https://t.me/+E5grTSLZvbpiMTI1"}]
            ]
        }
        
        tg_edit(user_id, msg_id, msg, reply_markup=inline_kb)
        
        if user_id in pending_message and pending_message[user_id] == msg_id: del pending_message[user_id]

    except Exception as e:
        print(f"[ERROR] Terjadi kesalahan pada Playwright/Web (process_user_input): {type(e).__name__} - {e}")
        error_msg_id = message_id_to_edit if message_id_to_edit else pending_message.get(user_id)
        if error_msg_id:
            tg_edit(user_id, error_msg_id, f"❌ Terjadi kesalahan saat proses web. Silakan coba lagi.")
            if user_id in pending_message: del pending_message[user_id]
            
    finally:
        # 5. Tutup Page/Tab
        if page:
            await page.close()


# =======================
# OTP UPDATE LOOP (Dioptimalkan)
# =======================
async def process_otp_update(browser_context):
    MIN_INTERVAL = 5 # Target interval minimum (termasuk waktu scraping)
    
    while True:
        page = None
        start_time = time.time() 

        try:
            # 1. Buka Page/Tab baru
            page = await browser_context.new_page()
            
            # Navigasi cepat
            await page.goto(SCRAPE_URL, wait_until="domcontentloaded", timeout=10000) 
            
            # Jeda diperpendek
            await asyncio.sleep(0.5) 

            numbers_to_delete = []

            for number, info in list(otp_state.items()):
                user_id = info['user_id']
                range_prefix = info['range']
                current_status = info['message']
                timestamp = info['timestamp']
                country = info['country']
                
                # Check Timeout (10 minutes = 600 seconds)
                if current_status == "waiting" and (time.time() - timestamp > 600):
                    numbers_to_delete.append(number)
                    
                    msg_timeout = (
                        "⚠️ Nomor telah kadaluarsa.\n\n"
                        f"📞 Number  : <code>{number}</code>\n"
                        f"🏷️ Range   : <code>{range_prefix}</code>\n\n"
                        "Silahkan Get Number Ulang!"
                    )
                    tg_send(user_id, msg_timeout) 
                    continue 

                # Hanya proses nomor yang masih "waiting"
                if current_status == "waiting":
                    status, otp, full_sms, _ = await get_otp_message(page, number)
                    
                    if status == "success":
                        numbers_to_delete.append(number)
                        
                        emoji = COUNTRY_EMOJI.get(country, "🗺️")
                        success_msg = (
                            "SUKSES MESSAGE IS READY🥳\n\n"
                            f"📞 Number  : <code>{number}</code>\n"
                            f"{emoji} COUNTRY : {country}\n"
                            f"🏷️ Range   : <code>{range_prefix}</code>\n\n"
                            f"🔢 OTP : <code>{otp}</code>\n\n"
                            f"Full Messages :\n"
                            f"<blockquote>{full_sms}</blockquote>"
                        )
                        
                        inline_kb = {
                            "inline_keyboard": [
                                [{"text": "📲 Get Number", "callback_data": "getnum"}],
                                [{"text": "👨‍💼 Admin", "url": "https://t.me/"}]
                            ]
                        }
                        
                        tg_send(user_id, success_msg, inline_kb)

                    elif status == "failed":
                        numbers_to_delete.append(number)
                        
                        msg_failed = (
                            "❌ Invalid Number.\n\n"
                            f"📞 Number  : <code>{number}</code>\n"
                            f"🏷️ Range   : <code>{range_prefix}</code>\n\n"
                            "Silahkan Get Number Ulang!"
                        )
                        tg_send(user_id, msg_failed)

            for number in numbers_to_delete:
                delete_otp_state(number)
                print(f"[OTP] Nomor {number} dihapus dari state.")

        except Exception as e:
            print(f"[ERROR] Terjadi kesalahan pada OTP Update Loop (Umum): {type(e).__name__} - {e}")
            await asyncio.sleep(5) 
            
        finally:
            # 2. Tutup Page/Tab
            if page:
                await page.close()

        # Hitung durasi proses
        end_time = time.time()
        duration = end_time - start_time
        
        # Jeda dinamis agar total waktu iterasi mendekati MIN_INTERVAL
        # Dipastikan jeda minimal 1 detik
        wait_time = max(1, MIN_INTERVAL - duration) 
        
        # Jeda dinamis sebelum cek lagi
        print(f"[DEBUG] Iterasi OTP selesai dalam {duration:.2f}s. Menunggu {wait_time:.2f}s.")
        await asyncio.sleep(wait_time)


# =======================
# TELEGRAM LOOP
# =======================
async def telegram_loop(browser_context):
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
                            new_ranges.append({"range": range_prefix, "country": country_name, "emoji": emoji})

                    prompt_msg_id = pending_message.pop(user_id, None)
                    if new_ranges:
                        save_inline_ranges(new_ranges)
                        if prompt_msg_id: tg_edit(user_id, prompt_msg_id, f"✅ Berhasil menyimpan {len(new_ranges)} range ke inline.json.")
                    else:
                        if prompt_msg_id: tg_edit(user_id, prompt_msg_id, "❌ Format tidak valid atau tidak ada range yang ditemukan. Batalkan penambahan range.")
                    
                    continue

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
                    msg_id_to_edit = pending_message.pop(user_id, None) 
                    await process_user_input(browser_context, user_id, prefix, msg_id_to_edit)
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

                if data_cb.startswith("select_range:"):
                    if user_id not in verified_users:
                        tg_edit(chat_id, menu_msg_id, "⚠️ Harap verifikasi dulu.")
                        continue
                        
                    prefix = data_cb.split(":")[1]
                    tg_edit(chat_id, menu_msg_id, f"<b>Get Number</b>\n\nRange dipilih: <code>{prefix}</code>\n⏳ Sedang memproses...")
                    await process_user_input(browser_context, user_id, prefix, menu_msg_id)
                    continue

                if data_cb == "manual_range":
                    waiting_range.add(user_id)
                    tg_edit(chat_id, menu_msg_id, "<b>Get Number</b>\n\nKirim range contoh: <code>628272XXXX</code>")
                    pending_message[user_id] = menu_msg_id
                    continue

        await asyncio.sleep(1)

# =======================
# MAIN
# =======================
async def main():
    load_otp_state()
    
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            browser_context = browser.contexts[0] 
            
            # --- MODIFIKASI DILAKUKAN DI SINI ---
            # Menghapus loop cleanup yang menutup semua tab yang sudah ada.
            # Bot akan membuat page/tab baru secara otomatis saat dibutuhkan.

            print("[OK] Connected to existing Chrome. Old pages kept open.")
        except Exception as e:
            print(f"[ERROR] Gagal terhubung ke Chrome CDP. Pastikan Chrome berjalan dengan flag --remote-debugging-port=9222. Error: {e}")
            return 

        tg_send(GROUP_ID, "✅ Bot Number Active!")

        # Jalankan loop Telegram dan loop update OTP secara paralel, passing browser_context
        await asyncio.gather(
            telegram_loop(browser_context),
            process_otp_update(browser_context)
        )

if __name__ == "__main__":
    asyncio.run(main())
