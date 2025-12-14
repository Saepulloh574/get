import asyncio
import json
import os
import requests
import time
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
OTP_STATE_FILE = "otp_state.json" # FILE BARU UNTUK STATUS OTP

# =======================
# GLOBAL STATE
# =======================
verified_users = set()
waiting_range = set()
waiting_admin_input = set() # NEW
pending_message = {}  # user_id -> message_id Telegram sementara
sent_numbers = set()
# otp_state: {number: {"user_id": int, "range": str, "message": str, "timestamp": float}}
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
# OTP STATE UTILS (NEW)
# =======================
def load_otp_state():
    global otp_state
    if os.path.exists(OTP_STATE_FILE):
        with open(OTP_STATE_FILE, "r") as f:
            try:
                otp_state = json.load(f)
            except json.JSONDecodeError:
                otp_state = {}
    
    # Konversi keys (nomor) yang tersimpan sebagai string kembali ke set jika perlu, 
    # namun untuk otp_state kita simpan sebagai dict {number: info}
    
def save_otp_state():
    with open(OTP_STATE_FILE, "w") as f:
        json.dump(otp_state, f, indent=2)

def add_to_otp_state(number, user_id, prefix):
    # Menyimpan state awal WAITING dengan timestamp saat ini
    otp_state[number] = {
        "user_id": user_id,
        "range": prefix,
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
    # Generates buttons in 2-column format
    keyboard = []
    current_row = []
    
    for item in ranges:
        text = f"{item['country']} {item['emoji']}"
        # Callback format: "select_range:23273XXX"
        callback_data = f"select_range:{item['range']}"
        current_row.append({"text": text, "callback_data": callback_data})
        
        if len(current_row) == 2:
            keyboard.append(current_row)
            current_row = []
    
    if current_row:
        keyboard.append(current_row)
        
    # Add Manual Range button at the bottom
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
# PARSE NOMOR
# =======================
async def get_number_and_country(page):
    rows = await page.query_selector_all("tbody tr")
    for row in rows:
        phone_el = await row.query_selector(".phone-number")
        if not phone_el:
            continue
        number = (await phone_el.inner_text()).strip()
        
        # Skip nomor yang sudah ada di cache
        if is_in_cache(number):
            continue
            
        # Skip nomor yang sudah ada status sukses/gagal (untuk proses get_number_and_country)
        # Nomor waiting tetap diambil
        if await row.query_selector(".status-success") or await row.query_selector(".status-failed"):
            continue
            
        country_el = await row.query_selector(".badge.bg-primary")
        country = (await country_el.inner_text()).strip().upper() if country_el else "-"
        return number, country
    return None, None

async def get_otp_message(page, number_to_check):
    rows = await page.query_selector_all("tbody tr")
    for row in rows:
        phone_el = await row.query_selector(".phone-number")
        if not phone_el:
            continue
        number = (await phone_el.inner_text()).strip()
        
        if number == number_to_check:
            # Cek status
            is_success = await row.query_selector(".status-success")
            is_failed = await row.query_selector(".status-failed")
            
            if is_success:
                # Scrape OTP dan Full Message
                otp_el = await row.query_selector(".otp-badge")
                full_sms_el = await row.query_selector(".copy-icon")
                country_el = await row.query_selector(".badge.bg-primary")
                
                otp = (await otp_el.inner_text()).split()[0].strip() if otp_el else "-"
                
                # Mengambil data-sms attribute
                full_sms_data = await full_sms_el.get_attribute("data-sms") if full_sms_el else "Tidak ada pesan"
                
                country = (await country_el.inner_text()).strip().upper() if country_el else "-"

                return "success", otp, full_sms_data, country
            
            if is_failed:
                return "failed", "-", "-", "-"
                
            return "waiting", "-", "-", "-"

    return None, None, None, None # Nomor tidak ditemukan di halaman

# =======================
# PROCESS USER INPUT
# =======================
async def process_user_input(page, user_id, prefix, message_id_to_edit=None):
    try:
        # Menentukan Message ID yang akan diedit (Untuk menjaga chat tetap bersih)
        if message_id_to_edit:
            msg_id = message_id_to_edit
            tg_edit(user_id, msg_id, f"⏳ Sedang mengambil Number...\nRange: {prefix}")
        else:
            # Jika tidak ada ID (biasanya dari input teks manual), kirim pesan baru
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
        number, country = await get_number_and_country(page)
        
        # Logika Tambahan: Jeda 3 detik dan coba scrape lagi jika percobaan pertama gagal
        if not number:
            # Edit pesan menjadi status retry
            tg_edit(user_id, msg_id, f"⏳ Nomor belum muncul, mencoba lagi dalam 3 detik...\nRange: {prefix}")
            
            # Jeda 3 detik
            await asyncio.sleep(3) 
            
            # Scrape lagi (Percobaan Kedua)
            number, country = await get_number_and_country(page)
        
        # Final Check: Jika masih tidak menemukan nomor
        if not number:
            # Kirim feedback error yang spesifik
            tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DI TEMUKAN SILAHKAN GET ULANG")
            
            # Hapus ID dari pending_message jika ada
            if user_id in pending_message and pending_message[user_id] == msg_id:
                del pending_message[user_id]
            return

        # simpan nomor baru ke cache
        save_cache({"number": number, "country": country})
        
        # Tambahkan ke OTP State (Awalnya waiting)
        add_to_otp_state(number, user_id, prefix)

        emoji = COUNTRY_EMOJI.get(country, "🗺️")
        
        # Format pesan awal, menggunakan format yang sama dengan yang diminta (untuk sementara)
        # Tapi pesan ini akan di-edit/diganti di proses_otp_update jika sukses
        msg = (
            "✅ The number is ready\n\n"
            f"📞 Number  : <code>{number}</code>\n"
            f"{emoji} COUNTRY : {country}\n"
            f"🏷️ Range   : <code>{prefix}</code>\n\n"
            f"Status OTP: **WAITING** (Akan diupdate jika pesan masuk atau timeout 10 menit)"
        )

        inline_kb = {
            "inline_keyboard": [
                [{"text": "📲 Get Number", "callback_data": "getnum"}],
                [{"text": "🔐 OTP Grup", "url": "https://t.me/+E5grTSLZvbpiMTI1"}]
            ]
        }
        
        # Edit pesan menjadi status WAITING
        tg_edit(user_id, msg_id, msg, reply_markup=inline_kb)
        
        # Hapus ID dari pending_message
        if user_id in pending_message and pending_message[user_id] == msg_id:
            del pending_message[user_id]

    except Exception as e:
        print(f"[ERROR] Terjadi kesalahan pada Playwright/Web: {e}")
        # Gunakan msg_id yang sudah didapatkan untuk mengedit pesan error
        error_msg_id = message_id_to_edit if message_id_to_edit else pending_message.get(user_id)
        if error_msg_id:
            tg_edit(user_id, error_msg_id, f"❌ Terjadi kesalahan saat proses web. Cek log bot: {type(e).__name__}")
            if user_id in pending_message:
                del pending_message[user_id]

# =======================
# OTP UPDATE LOOP (NEW)
# =======================
async def process_otp_update(page):
    while True:
        try:
            # Reload halaman untuk mendapatkan data terbaru
            await page.reload()
            await page.wait_for_load_state("load") 
            await asyncio.sleep(1.5) 

            numbers_to_delete = []

            for number, info in list(otp_state.items()):
                user_id = info['user_id']
                range_prefix = info['range']
                current_status = info['message']
                timestamp = info['timestamp']
                
                # Check Timeout (10 minutes = 600 seconds)
                if current_status == "waiting" and (time.time() - timestamp > 600):
                    numbers_to_delete.append(number)
                    
                    # Kirim pesan timeout
                    msg_timeout = (
                        "⚠️ Nomor telah kadaluarsa (Timeout 10 Menit)\n\n"
                        f"📞 Number  : <code>{number}</code>\n"
                        f"🏷️ Range   : <code>{range_prefix}</code>\n\n"
                        "Silahkan Get Number Ulang!"
                    )
                    # Mengirim pesan baru (permanen)
                    tg_send(user_id, msg_timeout) 
                    
                    continue # Lanjut ke nomor berikutnya

                # Hanya proses nomor yang masih "waiting"
                if current_status == "waiting":
                    status, otp, full_sms, country = await get_otp_message(page, number)
                    
                    if status == "success":
                        numbers_to_delete.append(number)
                        
                        # Format pesan sukses (permanen, TIDAK EDIT)
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
                                [{"text": "👨‍💼 Admin", "url": "https://t.me/"}] # Ganti URL admin
                            ]
                        }
                        
                        # Kirim pesan baru (permanen)
                        tg_send(user_id, success_msg, inline_kb)

                    elif status == "failed":
                        numbers_to_delete.append(number)
                        
                        # Kirim pesan failed
                        msg_failed = (
                            "❌ NOMOR GAGAL MENDAPATKAN PESAN\n\n"
                            f"📞 Number  : <code>{number}</code>\n"
                            f"🏷️ Range   : <code>{range_prefix}</code>\n\n"
                            "Silahkan Get Number Ulang!"
                        )
                        # Mengirim pesan baru (permanen)
                        tg_send(user_id, msg_failed)


            # Hapus nomor yang sudah selesai atau timeout
            for number in numbers_to_delete:
                delete_otp_state(number)
                print(f"[OTP] Nomor {number} dihapus dari state. Status: Success/Failed/Timeout")

        except Exception as e:
            print(f"[ERROR] Terjadi kesalahan pada OTP Update Loop: {e}")
            
        # Jeda 10 detik sebelum cek lagi
        await asyncio.sleep(10)

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

                # --- ADMIN COMMAND HANDLER ---
                if user_id == ADMIN_ID:
                    if text.startswith("/add"):
                        waiting_admin_input.add(user_id)
                        # Kirim pesan baru, ID pesan disimpan untuk diedit selanjutnya
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

                    # Ambil message_id dari prompt sebelumnya
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
                    # Mengirim pesan baru
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
                        # Edit pesan callback
                        tg_edit(chat_id, menu_msg_id, "❌ Belum gabung grup, silakan join dulu.")
                    else:
                        verified_users.add(user_id)
                        kb = {
                            "inline_keyboard": [
                                [{"text": "📲 Get Number", "callback_data": "getnum"}],
                                [{"text": "👨‍💼 Admin", "url": "https://t.me/"}],
                            ]
                        }
                        # Edit pesan callback
                        tg_edit(chat_id, menu_msg_id, f"✅ Verifikasi Berhasil!\n\nGunakan tombol di bawah:", kb)
                    continue

                if data_cb == "getnum":
                    if user_id not in verified_users:
                        # Edit pesan callback
                        tg_edit(chat_id, menu_msg_id, "⚠️ Harap verifikasi dulu.")
                        continue
                    
                    inline_ranges = load_inline_ranges()
                    
                    if inline_ranges:
                        kb = generate_inline_keyboard(inline_ranges)
                        msg_text = "Range tersedia saat ini, silahkan gunakan range di bawah atau Manual Range."
                        
                        # Edit pesan callback menjadi menu range
                        tg_edit(chat_id, menu_msg_id, f"<b>Get Number</b>\n\n{msg_text}", kb)
                        
                        # Simpan ID pesan menu ini agar dapat diedit nanti jika user memilih manual range
                        pending_message[user_id] = menu_msg_id
                    else:
                        # Jika inline range kosong, langsung minta input manual
                        waiting_range.add(user_id)
                        tg_edit(chat_id, menu_msg_id, "Kirim range contoh: <code>628272XXXX</code>")
                        # Simpan ID pesan ini agar dapat diedit oleh process_user_input
                        pending_message[user_id] = menu_msg_id
                    continue

                if data_cb.startswith("select_range:"):
                    if user_id not in verified_users:
                        tg_edit(chat_id, menu_msg_id, "⚠️ Harap verifikasi dulu.")
                        continue
                        
                    prefix = data_cb.split(":")[1]
                    
                    # Edit pesan menu menjadi status processing
                    tg_edit(chat_id, menu_msg_id, f"<b>Get Number</b>\n\nRange dipilih: <code>{prefix}</code>\n⏳ Sedang memproses...")
                    
                    # Memanggil process_user_input dengan ID pesan menu untuk diedit
                    await process_user_input(page, user_id, prefix, menu_msg_id)
                    continue

                if data_cb == "manual_range":
                    waiting_range.add(user_id)
                    
                    # Edit pesan menu menjadi permintaan input manual
                    tg_edit(chat_id, menu_msg_id, "<b>Get Number</b>\n\nKirim range contoh: <code>628272XXXX</code>")
                    
                    # Simpan ID pesan ini agar dapat diedit oleh process_user_input (untuk kasus input teks)
                    pending_message[user_id] = menu_msg_id
                    continue

        await asyncio.sleep(1)

# =======================
# MAIN
# =======================
async def main():
    # Load state saat bot start
    load_otp_state()
    
    async with async_playwright() as p:
        # Pengecekan koneksi ke Chrome CDP
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0]
            print("[OK] Connected to existing Chrome")
        except Exception as e:
            print(f"[ERROR] Gagal terhubung ke Chrome CDP. Pastikan Chrome berjalan dengan flag --remote-debugging-port=9222. Error: {e}")
            return # Hentikan eksekusi jika koneksi gagal

        tg_send(GROUP_ID, "✅ Bot Number Active!")

        # Jalankan loop Telegram dan loop update OTP secara paralel
        await asyncio.gather(
            telegram_loop(page),
            process_otp_update(page)
        )

if __name__ == "__main__":
    asyncio.run(main())
