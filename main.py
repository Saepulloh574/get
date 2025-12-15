import asyncio
import json
import os
import requests
import re
from playwright.async_api import async_playwright

# =======================
# CONFIG
# =======================
BOT_TOKEN = "8047851913:AAFGXlRL_e7JcLEMtOqUuuNd_46ZmIoGJN8"
GROUP_ID_1 = -1003492226491  # GRUP UTAMA (Contoh: https://t.me/+E5grTSLZvbpiMTI1)
GROUP_ID_2 = -1002383814362  # <--- GANTI ID INI DENGAN ID GRUP KEDUA (zura14g)
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
CACHE_FILE = "cache.json"

# --- NEW CONFIG ---
ADMIN_ID = 7184123643  
INLINE_RANGE_FILE = "inline.json"
SMC_FILE = "smc.json" # FILE BARU UNTUK DATA SMS
BOT_USERNAME_LINK = "https://t.me/myzuraisgoodbot" 
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1" # Link Grup 1
GROUP_LINK_2 = "https://t.me/zura14g"           # Link Grup 2 (Tambahan)

# =======================
# GLOBAL STATE
# =======================
verified_users = set()
waiting_range = set()
waiting_admin_input = set()
pending_message = {} 
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
# SMC UTILS (BARU)
# =======================

def load_smc():
    """Memuat data SMS dari SMC_FILE."""
    if os.path.exists(SMC_FILE):
        with open(SMC_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_smc(data):
    """Menyimpan data SMS ke SMC_FILE."""
    with open(SMC_FILE, "w") as f:
        json.dump(data, f, indent=2)

def find_and_remove_sms(number_to_find):
    """Mencari SMS berdasarkan nomor dan menghapusnya dari file."""
    data = load_smc()
    
    # Normalisasi format: pastikan ada '+'
    normalized_number = number_to_find.strip().replace(" ", "")
    if not normalized_number.startswith('+'):
        normalized_number = '+' + normalized_number
        
    found_sms = None
    new_data = []
    removed = False
    
    for entry in data:
        # Bandingkan dengan nomor yang sudah dinormalisasi
        if entry.get("Number") == normalized_number and not removed:
            found_sms = entry
            removed = True # Hanya hapus entri pertama yang cocok
        else:
            new_data.append(entry)
            
    if found_sms:
        # Simpan kembali data tanpa SMS yang ditemukan
        save_smc(new_data)
        
    return found_sms

def is_valid_phone_number(text):
    """Memeriksa apakah teks terlihat seperti nomor telepon internasional."""
    # Regex yang sederhana untuk nomor yang dimulai dengan '+' dan diikuti 5-15 digit
    # Atau nomor tanpa '+' diikuti setidaknya 6 digit
    return re.fullmatch(r"^\+?\d{6,15}$", text.replace(" ", "").replace("-", ""))


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

def is_user_in_group(user_id, group_id):
    """Mengecek keanggotaan pengguna di grup tertentu."""
    try:
        r = requests.get(f"{API}/getChatMember", params={"chat_id": group_id, "user_id": user_id}).json()
        if not r.get("ok"):
            return False
        return r["result"]["status"] in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"[ERROR CHECK GROUP {group_id}] {e}")
        return False

def is_user_in_both_groups(user_id):
    """Mengecek keanggotaan pengguna di GRUP 1 DAN GRUP 2."""
    is_member_1 = is_user_in_group(user_id, GROUP_ID_1)
    is_member_2 = is_user_in_group(user_id, GROUP_ID_2)
    return is_member_1 and is_member_2

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
        await asyncio.sleep(1.5) 

        # 5. Refresh halaman dan tunggu load penuh (State 'load')
        await page.reload()
        await page.wait_for_load_state("load") 

        # 6. Jeda 1.5 detik sebelum scraping
        await asyncio.sleep(1.8) 

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
                [{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}] # Menggunakan link grup 1 untuk OTP Grup
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
                chat_id = msg["chat"]["id"]
                user_id = msg["from"]["id"]
                
                # Mendapatkan nama untuk mention (HTML Parse Mode)
                first_name = msg["from"].get("first_name", "User")
                mention = f"<a href='tg://user?id={user_id}'>{first_name}</a>"
                text = msg.get("text", "")

                # --- NEW MEMBER WELCOME HANDLER ---
                # Hanya kirim pesan jika anggota baru bergabung di salah satu grup yang dimonitor
                if "new_chat_members" in msg and (chat_id == GROUP_ID_1 or chat_id == GROUP_ID_2):
                    for member in msg["new_chat_members"]:
                        if member["is_bot"]:
                            continue
                            
                        member_first_name = member.get("first_name", "New User")
                        member_mention = f"<a href='tg://user?id={member['id']}'>{member_first_name}</a>"

                        welcome_message = (
                            f"HEYY {member_mention} WELLCOME!!,\n"
                            f"Ready to receive SMS? Get number at here {BOT_USERNAME_LINK}"
                        )
                        # Kirim pesan sambutan ke grup yang baru dimasuki
                        tg_send(chat_id, welcome_message)
                    continue 

                # --- ADMIN COMMAND HANDLER ---
                if user_id == ADMIN_ID:
                    if text.startswith("/add"):
                        waiting_admin_input.add(user_id)
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
                
                # --- START COMMAND HANDLER (Logika Cerdas) ---
                if text == "/start":
                    # Cek status keanggotaan di DUA grup
                    is_member = is_user_in_both_groups(user_id)
                    
                    if is_member:
                        # User Sudah Gabung Kedua Grup
                        verified_users.add(user_id) 
                        
                        kb = {
                            "inline_keyboard": [
                                [{"text": "📲 Get Number", "callback_data": "getnum"}],
                                [{"text": "👨‍💼 Admin", "url": "https://t.me/"}], 
                            ]
                        }
                        
                        msg_text = (
                            f"✅ Verifikasi Berhasil, {mention}!\n\n"
                            "Gunakan tombol di bawah:"
                        )
                        tg_send(user_id, msg_text, kb)
                    else:
                        # User Belum Gabung Kedua Grup
                        kb = {
                            "inline_keyboard": [
                                [{"text": "📌 Gabung Grup 1", "url": GROUP_LINK_1}],
                                [{"text": "📌 Gabung Grup 2", "url": GROUP_LINK_2}],
                                [{"text": "✅ Verifikasi Ulang", "callback_data": "verify"}],
                            ]
                        }
                        msg_text = (
                            f"Halo {mention} 👋\n"
                            "Harap gabung kedua grup di bawah untuk verifikasi:"
                        )
                        tg_send(user_id, msg_text, kb)
                        
                    continue
                # --- END START COMMAND HANDLER ---

                if user_id in waiting_range:
                    waiting_range.remove(user_id)
                    prefix = text.strip()
                    
                    msg_id_to_edit = pending_message.pop(user_id, None) 
                    
                    await process_user_input(page, user_id, prefix, msg_id_to_edit)
                    
                    continue
                    
                # --- NEW SMS SEARCH HANDLER ---
                # Hanya jika bukan perintah, bukan balasan admin, di chat pribadi, dan user sudah terverifikasi
                if chat_id > 0 and text and not text.startswith('/') and user_id in verified_users:
                    if is_valid_phone_number(text):
                        # Jika teks terlihat seperti nomor telepon
                        
                        # Kirim pesan 'Mencari...'
                        search_msg_id = tg_send(user_id, f"🔍 Mencari SMS untuk nomor <code>{text}</code>...")
                        
                        # Cari SMS dan hapus
                        sms_data = find_and_remove_sms(text)
                        
                        if sms_data:
                            # SMS ditemukan
                            number = sms_data["Number"]
                            otp = sms_data.get("OTP", "N/A")
                            full_message = sms_data.get("FullMessage", "Tidak ada pesan lengkap.")
                            
                            response_text = (
                                "✅ SMS Ditemukan dan Dihapus\n\n"
                                f"📞 Number: <code>{number}</code>\n"
                                f"🗝️ OTP: <code>{otp}</code>\n"
                                "\n"
                                "💬 Full Message:\n"
                                f"<blockquote>{full_message}</blockquote>"
                            )
                            
                            inline_kb = {
                                "inline_keyboard": [
                                    [{"text": "🔄 Cari Ulang Nomor Lain", "callback_data": "getnum"}]
                                ]
                            }
                            
                            tg_edit(user_id, search_msg_id, response_text, reply_markup=inline_kb)
                            
                        else:
                            # SMS tidak ditemukan
                            response_text = (
                                f"❌ SMS Tidak Ditemukan\n\n"
                                f"Tidak ada pesan untuk nomor <code>{text}</code>."
                            )
                            inline_kb = {
                                "inline_keyboard": [
                                    [{"text": "🔄 Coba Lagi / Cari Nomor Lain", "callback_data": "getnum"}]
                                ]
                            }
                            tg_edit(user_id, search_msg_id, response_text, reply_markup=inline_kb)
                            
                        continue # Lanjut ke update berikutnya
                # --- END SMS SEARCH HANDLER ---


            if "callback_query" in upd:
                cq = upd["callback_query"]
                user_id = cq["from"]["id"]
                data_cb = cq["data"]
                
                chat_id = cq["message"]["chat"]["id"]
                menu_msg_id = cq["message"]["message_id"]
                
                first_name = cq["from"].get("first_name", "User")
                mention = f"<a href='tg://user?id={user_id}'>{first_name}</a>"


                if data_cb == "verify":
                    if not is_user_in_both_groups(user_id):
                        # Jika verifikasi GAGAL
                        kb = {
                            "inline_keyboard": [
                                [{"text": "📌 Gabung Grup 1", "url": GROUP_LINK_1}],
                                [{"text": "📌 Gabung Grup 2", "url": GROUP_LINK_2}],
                                [{"text": "✅ Verifikasi Ulang", "callback_data": "verify"}],
                            ]
                        }
                        tg_edit(chat_id, menu_msg_id, "❌ Belum gabung kedua grup. Silakan join dulu.", kb)
                    else:
                        # Jika verifikasi BERHASIL
                        verified_users.add(user_id)
                        kb = {
                            "inline_keyboard": [
                                [{"text": "📲 Get Number", "callback_data": "getnum"}],
                                [{"text": "👨‍💼 Admin", "url": "https://t.me/"}],
                            ]
                        }
                        msg_text = (
                            f"✅ Verifikasi Berhasil, {mention}!\n\n"
                            "Gunakan tombol di bawah:"
                        )
                        tg_edit(chat_id, menu_msg_id, msg_text, kb)
                    continue

                if data_cb == "getnum":
                    if user_id not in verified_users:
                        # Jika pesan sudah ada di chat, edit pesan tersebut.
                        tg_edit(chat_id, menu_msg_id, "⚠️ Harap verifikasi dulu.")
                        continue
                    
                    inline_ranges = load_inline_ranges()
                    
                    if inline_ranges:
                        kb = generate_inline_keyboard(inline_ranges)
                        msg_text = "Silahkan gunakan range di bawah atau Manual range untuk mendapatkan nomor."
                        
                        tg_edit(chat_id, menu_msg_id, f"<b>Get Number</b>\n\n{msg_text}", kb)
                        
                        pending_message[user_id] = menu_msg_id
                    else:
                        waiting_range.add(user_id)
                        tg_edit(chat_id, menu_msg_id, "Kirim range contoh: <code>9377009XXX</code>")
                        pending_message[user_id] = menu_msg_id
                    continue

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
                    
                    tg_edit(chat_id, menu_msg_id, "<b>Get Number</b>\n\nKirim range contoh: <code>9377009XXX</code>")
                    
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
    if not os.path.exists(SMC_FILE): # INISIALISASI FILE SMC_FILE BARU
        with open(SMC_FILE, "w") as f:
            f.write("[]")
            
    # Perhatian penting untuk mengganti ID
    if GROUP_ID_2 == -1001234567890:
        print("\n=======================================================")
        print("!!! PERINGATAN PENTING !!!")
        print("Silakan GANTI nilai GROUP_ID_2 (-1001234567890) ")
        print("dengan ID numerik yang BENAR dari grup https://t.me/zura14g.")
        print("Bot TIDAK AKAN berfungsi dengan benar untuk verifikasi dua grup tanpa ID yang valid.")
        print("=======================================================\n")


    try:
        async with async_playwright() as p:
            # Gunakan try-except untuk penanganan koneksi browser yang lebih baik
            try:
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            except Exception as e:
                print(f"[ERROR] Gagal koneksi ke Chrome CDP: {e}")
                print("Pastikan Chrome berjalan dengan flag '--remote-debugging-port=9222' dan web target terbuka.")
                return

            
            if not browser.contexts:
                print("[ERROR] No browser context found. Ensure Chrome is launched with --remote-debugging-port=9222.")
                return

            context = browser.contexts[0]
            
            if not context.pages:
                print("[ERROR] No page found in the first context. Ensure the target web page is open.")
                return
                
            page = context.pages[0]
            print("[OK] Connected to existing Chrome via CDP on port 9222")
    
            # Kirim notifikasi bot aktif ke grup utama
            tg_send(GROUP_ID_1, "✅ Bot Number Active!")
            # Kirim notifikasi ke grup kedua juga
            tg_send(GROUP_ID_2, "✅ Bot Number Active!")
    
            await telegram_loop(page)
            
    except Exception as e:
        print(f"[FATAL ERROR] An unexpected error occurred: {e}")
        # Tambahkan logika untuk mengirimkan notifikasi error ke ADMIN_ID jika perlu
        # tg_send(ADMIN_ID, f"⚠️ FATAL ERROR pada bot: {e}")


if __name__ == "__main__":
    asyncio.run(main())
