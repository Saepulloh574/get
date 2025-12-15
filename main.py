import asyncio
import json
import os
import requests
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

# =======================
# GLOBAL STATE
# =======================
verified_users = set()
waiting_range = set()
waiting_admin_input = set()
pending_message = {}  # user_id -> message_id Telegram sementara
sent_numbers = set() # NOTE: sent_numbers tidak digunakan di kode ini, tapi dipertahankan dari kode asli.

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
    try:
        r = requests.post(f"{API}/sendMessage", json=data).json()
        if r.get("ok"):
            return r["result"]["message_id"]
        print(f"[ERROR SEND] {r.get('description', 'Unknown Error')}")
        return None
    except Exception as e:
        print(f"[ERROR SEND REQUEST] {e}")
        return None

def tg_edit(chat_id, message_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        requests.post(f"{API}/editMessageText", json=data)
    except Exception as e:
        print(f"[ERROR EDIT REQUEST] {e}")

def tg_get_updates(offset):
    try:
        return requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 30}).json()
    except Exception as e:
        print(f"[ERROR GET UPDATES] {e}")
        return {"ok": False, "result": []}

def is_user_in_group(user_id):
    try:
        r = requests.get(f"{API}/getChatMember", params={"chat_id": GROUP_ID, "user_id": user_id}).json()
        if not r.get("ok"):
            # Jika user belum pernah start bot, bisa jadi error, anggap belum di grup
            return False
        return r["result"]["status"] in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"[ERROR CHECK GROUP] {e}")
        return False

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
            
        # Skip nomor yang sudah ada status sukses/gagal
        # Kriteria: Harus ada elemen .phone-number DAN tidak ada status sukses/gagal
        if await row.query_selector(".status-success") or await row.query_selector(".status-failed"):
            continue
            
        country_el = await row.query_selector(".badge.bg-primary")
        country = (await country_el.inner_text()).strip().upper() if country_el else "-"
        
        # Cek apakah nomor valid sebelum dikembalikan
        if number and len(number) > 5: # Asumsi nomor valid setidaknya 6 digit
            return number, country
            
    return None, None

# =======================
# PROCESS USER INPUT
# =======================
async def process_user_input(page, user_id, prefix, message_id_to_edit=None):
    try:
        # Menentukan Message ID yang akan diedit (Untuk menjaga chat tetap bersih)
        if message_id_to_edit:
            msg_id = message_id_to_edit
            tg_edit(user_id, msg_id, f"⏳ Sedang mengambil Number...\nRange: <code>{prefix}</code>")
        else:
            # Jika tidak ada ID (biasanya dari input teks manual), kirim pesan baru
            msg_id = tg_send(user_id, f"⏳ Sedang mengambil Number...\nRange: <code>{prefix}</code>")
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
            tg_edit(user_id, msg_id, f"⏳ Nomor belum muncul, mencoba lagi dalam 3 detik...\nRange: <code>{prefix}</code>")
            
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

        # simpan nomor baru ke cache (Hanya jika berhasil ditemukan)
        save_cache({"number": number, "country": country})

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
                [{"text": "🔐 OTP Grup", "url": "https://t.me/+E5grTSLZvbpiMTI1"}] # Ganti jika link grup berubah
            ]
        }

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
                
                # Mendapatkan nama untuk mention (HTML Parse Mode)
                first_name = msg["from"].get("first_name", "User")
                mention = f"<a href='tg://user?id={user_id}'>{first_name}</a>"
                text = msg.get("text", "")

                # --- ADMIN COMMAND HANDLER ---
                if user_id == ADMIN_ID:
                    if text.startswith("/add"):
                        waiting_admin_input.add(user_id)
                        # Kirim pesan baru, ID pesan disimpan untuk diedit selanjutnya
                        prompt_msg_text = "Silahkan kirim daftar range dalam format:\n\n<code>range > country</code>\n\nContoh:\n<code>23273XXX > SIERRA LEONE\n97798XXXX > NEPAL</code>"
                        msg_id = tg_send(user_id, prompt_msg_text)
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
                        # Ini menimpa isi inline.json, tidak append
                        save_inline_ranges(new_ranges)
                        if prompt_msg_id:
                            tg_edit(user_id, prompt_msg_id, f"✅ Berhasil menyimpan {len(new_ranges)} range ke inline.json.")
                    else:
                        if prompt_msg_id:
                            tg_edit(user_id, prompt_msg_id, "❌ Format tidak valid atau tidak ada range yang ditemukan. Batalkan penambahan range.")
                    
                    continue
                # --- END ADMIN COMMAND HANDLER ---
                
                # --- START COMMAND HANDLER (Logika Cerdas) ---
                if text == "/start":
                    # Cek status keanggotaan di grup
                    is_member = is_user_in_group(user_id)
                    
                    if is_member:
                        # User Sudah Gabung Grup (Anggap Terverifikasi)
                        verified_users.add(user_id) 
                        
                        kb = {
                            "inline_keyboard": [
                                [{"text": "📲 Get Number", "callback_data": "getnum"}],
                                [{"text": "👨‍💼 Admin", "url": "https://t.me/"}], # Ganti dengan link admin sebenarnya
                            ]
                        }
                        
                        msg_text = (
                            f"✅ Verifikasi Berhasil, {mention}!\n\n"
                            "Gunakan tombol di bawah:"
                        )
                        # Mengirim pesan baru
                        tg_send(user_id, msg_text, kb)
                    else:
                        # User Belum Gabung Grup
                        kb = {
                            "inline_keyboard": [
                                [{"text": "📌 Gabung Grup", "url": "https://t.me/+E5grTSLZvbpiMTI1"}],
                                [{"text": "✅ Verifikasi", "callback_data": "verify"}],
                            ]
                        }
                        msg_text = (
                            f"Halo {mention} 👋\n"
                            "Gabung grup untuk verifikasi."
                        )
                        # Mengirim pesan baru
                        tg_send(user_id, msg_text, kb)
                        
                    continue
                # --- END START COMMAND HANDLER ---

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
                
                # Mendapatkan nama untuk mention (HTML Parse Mode)
                first_name = cq["from"].get("first_name", "User")
                mention = f"<a href='tg://user?id={user_id}'>{first_name}</a>"


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
                        msg_text = (
                            f"✅ Verifikasi Berhasil, {mention}!\n\n"
                            "Gunakan tombol di bawah:"
                        )
                        tg_edit(chat_id, menu_msg_id, msg_text, kb)
                    continue

                if data_cb == "getnum":
                    if user_id not in verified_users:
                        # Edit pesan callback
                        tg_edit(chat_id, menu_msg_id, "⚠️ Harap verifikasi dulu.")
                        continue
                    
                    inline_ranges = load_inline_ranges()
                    
                    if inline_ranges:
                        kb = generate_inline_keyboard(inline_ranges)
                        msg_text = "Silahkan gunakan range di bawah atau Manual range untuk mendapatkan nomor."
                        
                        # Edit pesan callback menjadi menu range
                        tg_edit(chat_id, menu_msg_id, f"<b>Get Number</b>\n\n{msg_text}", kb)
                        
                        # Simpan ID pesan menu ini agar dapat diedit nanti jika user memilih manual range
                        pending_message[user_id] = menu_msg_id
                    else:
                        # Jika inline range kosong, langsung minta input manual
                        waiting_range.add(user_id)
                        tg_edit(chat_id, menu_msg_id, "Kirim range contoh: <code>9377009XXX</code>")
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
                    tg_edit(chat_id, menu_msg_id, "<b>Get Number</b>\n\nKirim range contoh: <code>9377009XXX</code>")
                    
                    # Simpan ID pesan ini agar dapat diedit oleh process_user_input (untuk kasus input teks)
                    pending_message[user_id] = menu_msg_id
                    continue

        await asyncio.sleep(1)

# =======================
# MAIN
# =======================
async def main():
    print("[INFO] Starting bot...")
    
    # Inisialisasi file jika belum ada
    if not os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "w") as f:
            f.write("[]")
    if not os.path.exists(INLINE_RANGE_FILE):
        with open(INLINE_RANGE_FILE, "w") as f:
            f.write("[]")

    try:
        async with async_playwright() as p:
            # Menggunakan connect_over_cdp untuk browser yang sudah berjalan
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            
            # Cek apakah ada konteks yang terbuka
            if not browser.contexts:
                print("[ERROR] No browser context found. Ensure Chrome is launched with --remote-debugging-port=9222.")
                return

            context = browser.contexts[0]
            
            # Cek apakah ada halaman yang terbuka
            if not context.pages:
                print("[ERROR] No page found in the first context. Ensure the target web page is open.")
                return
                
            page = context.pages[0]
            print("[OK] Connected to existing Chrome via CDP on port 9222")
    
            # Kirim notifikasi bot aktif ke grup
            tg_send(GROUP_ID, "✅ Bot Number Active!")
    
            await telegram_loop(page)
            
    except Exception as e:
        print(f"[FATAL ERROR] Playwright/Browser connection failed: {e}")
        print("Pastikan Anda menjalankan Chrome dengan flag '--remote-debugging-port=9222'.")

if __name__ == "__main__":
    asyncio.run(main())
