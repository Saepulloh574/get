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

# ---------------------------------------------------------

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
COUNTRY_EMOJI_FILE = "country.json" # FILE BARU DITAMBAHKAN
BOT_USERNAME_LINK = "https://t.me/myzuraisgoodbot"
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1"
GROUP_LINK_2 = "https://t.me/zura14g"

verified_users = set()
waiting_range = set()
waiting_admin_input = set()
pending_message = {}
sent_numbers = set()

# HAPUS kamus COUNTRY_EMOJI, diganti dengan variabel global yang dimuat di main
GLOBAL_COUNTRY_EMOJI = {}


def load_country_emojis():
    """Memuat data emoji negara dari country.json."""
    if os.path.exists(COUNTRY_EMOJI_FILE):
        with open(COUNTRY_EMOJI_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print(f"[ERROR] Gagal memuat {COUNTRY_EMOJI_FILE}: Format tidak valid.")
                return {}
    return {}

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
    normalized_number = normalize_number(number)
    if not any(item['number'] == normalized_number for item in wait_list):
        wait_list.append({"number": normalized_number, "user_id": user_id, "timestamp": time.time()})
        save_wait_list(wait_list)

def normalize_number(number):
    normalized_number = number.strip().replace(" ", "").replace("-", "")
    if not normalized_number.startswith('+'):
        normalized_number = '+' + normalized_number
    return normalized_number

def is_valid_phone_number(text):
    # Memeriksa apakah input terlihat seperti nomor telepon lengkap, bukan hanya prefix range
    return re.fullmatch(r"^+?\d{6,15}$", text.replace(" ", "").replace("-", ""))

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
        return requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 1}).json()
    except Exception as e:
        print(f"[ERROR GET UPDATES] {e}")
        return {"ok": False, "result": []}

def is_user_in_group(user_id, group_id):
    try:
        r = requests.get(f"{API}/getChatMember", params={"chat_id": group_id, "user_id": user_id}).json()
        if not r.get("ok"):
            return False
        return r["result"]["status"] in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"[ERROR CHECK GROUP {group_id}] {e}")
        return False

def is_user_in_both_groups(user_id):
    is_member_1 = is_user_in_group(user_id, GROUP_ID_1)
    is_member_2 = is_user_in_group(user_id, GROUP_ID_2)
    return is_member_1 and is_member_2

async def get_number_and_country(page):
    rows = await page.query_selector_all("tbody tr")
    for row in rows:
        phone_el = await row.query_selector(".phone-number")
        if not phone_el:
            continue
        number = (await phone_el.inner_text()).strip()
        
        if is_in_cache(number):
            continue
        
        # Cek apakah nomor memiliki status 'success' atau 'failed' (sudah diambil)
        # Jika ada status-success atau status-failed, lewati
        if await row.query_selector(".status-success") or await row.query_selector(".status-failed"):
            continue

        country_el = await row.query_selector(".badge.bg-primary")
        country = (await country_el.inner_text()).strip().upper() if country_el else "-"

        if number and len(number) > 5:
            return number, country

    return None, None

async def process_user_input(page, user_id, prefix, message_id_to_edit=None):
    global GLOBAL_COUNTRY_EMOJI # Menggunakan variabel global yang dimuat di main

    msg_id = message_id_to_edit if message_id_to_edit else pending_message.pop(user_id, None)

    # --- START LOCK MODIFICATION (Feedback Antrian) ---
    if playwright_lock.locked():
        if msg_id:
            tg_edit(user_id, msg_id, f"⏳ Permintaan Anda masuk antrian. Mohon tunggu.\nRange: <code>{prefix}</code>")
        else:
            msg_id = tg_send(user_id, f"⏳ Permintaan Anda masuk antrian. Mohon tunggu.\nRange: <code>{prefix}</code>")
            if not msg_id: return

    # Menggunakan Lock untuk memastikan hanya satu task yang bisa masuk (Antrian Utama)
    async with playwright_lock:
        try:
            # Pengecekan ulang msg_id setelah mendapatkan Lock
            if not msg_id:
                msg_id = tg_send(user_id, f"⏳ Sedang mengambil Number...\nRange: <code>{prefix}</code>")
                if not msg_id: return

            # Update status ke 'Sedang Diproses' setelah mendapatkan Lock
            tg_edit(user_id, msg_id, f"✅ Antrian diterima. Sedang mengambil Number...\nRange: <code>{prefix}</code>")

            # --- Bagian Interaksi Playwright (DIJAMIN SEQUENTIAL) ---

            await page.wait_for_selector('input[name="numberrange"]', timeout=10000)
            await page.fill('input[name="numberrange"]', prefix)
            await asyncio.sleep(0.5)

            # MODIFIKASI: Menggunakan force=True dan TIDAK reload
            await page.click("#getNumberBtn", force=True)

            # Menunggu hasil AJAX dengan timeout singkat
            try:
                # Menunggu setidaknya satu baris baru muncul atau tabel diperbarui
                await page.wait_for_selector("tbody tr", timeout=15000)
            except Exception:
                # Ini diizinkan jika AJAX lambat atau gagal, kita akan cek lagi di loop
                print(f"[INFO] Timeout menunggu hasil AJAX setelah klik getNumberBtn untuk range {prefix}. Melanjutkan...")
                pass
            
            # Beri jeda sebentar untuk memastikan DOM stabil setelah AJAX
            await asyncio.sleep(2)

            number, country = await get_number_and_country(page)

            if not number:
                # --- START MODIFIKASI LOADING DINAMIS ---
                delay_duration = 5.0 # Perpanjang sedikit untuk toleransi loading
                update_interval = 0.5 # Perpanjang interval update
                
                loading_statuses = [
                    "⏳ Nomor belum muncul mencoba lagi.",
                    "⏳ Nomor belum muncul mencoba lagi..",
                    "⏳ Nomor belum muncul mencoba lagi...",
                    "⏳ Nomor belum muncul mencoba lagi....",
                ]

                start_time = time.time()
                while (time.time() - start_time) < delay_duration:
                    index = int((time.time() - start_time) / update_interval) % len(loading_statuses)
                    current_status = loading_statuses[index]
                    
                    tg_edit(user_id, msg_id, f"{current_status}\nRange: <code>{prefix}</code>")
                    
                    await asyncio.sleep(update_interval)

                # Coba ambil nomor lagi setelah loop loading selesai
                number, country = await get_number_and_country(page)
                # --- END MODIFIKASI LOADING DINAMIS ---

            if not number:
                tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DI TEMUKAN SILAHKAN KLIK /start - GET NUMBER ULANG")
                return

            save_cache({"number": number, "country": country})
            add_to_wait_list(number, user_id)

            # MENGGUNAKAN GLOBAL_COUNTRY_EMOJI
            emoji = GLOBAL_COUNTRY_EMOJI.get(country, "🗺️")
            msg = (
                "✅ The number is ready\n\n"
                f"📞 Number  : <code>{number}</code>\n"
                f"{emoji} COUNTRY : {country}\n"
                f"🏷️ Range   : <code>{prefix}</code>\n\n"
                "<b>🤖 Nomor telah dimasukkan ke daftar tunggu otomatis.</b>\n"
                "<b>OTP akan dikirimkan ke chat ini Atau Check OTP grup.</b>"
            )

            inline_kb = {
                "inline_keyboard": [
                    [{"text": "📲 Get Number", "callback_data": "getnum"}],
                    [{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}]
                ]
            }

            tg_edit(user_id, msg_id, msg, reply_markup=inline_kb)

        except Exception as e:
            print(f"[ERROR] Terjadi kesalahan pada Playwright/Web: {e}")
            if msg_id:
                tg_edit(user_id, msg_id, f"❌ Terjadi kesalahan saat proses web. Cek log bot: {type(e).__name__}")

        # Lock otomatis dilepas saat keluar dari 'async with'
    # --- END LOCK MODIFICATION ---

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

                first_name = msg["from"].get("first_name", "User")
                mention = f"<a href='tg://user?id={user_id}'>{first_name}</a>"
                text = msg.get("text", "")

                # --- START MODIFIKASI WELCOME MESSAGE ---
                if "new_chat_members" in msg and chat_id == GROUP_ID_2: # HANYA GROUP_ID_2
                    for member in msg["new_chat_members"]:
                        if member["is_bot"]: continue

                        member_first_name = member.get("first_name", "New User")
                        member_mention = f"<a href='tg://user?id={member['id']}'>{member_first_name}</a>"

                        # FORMAT PESAN BARU
                        welcome_message = (
                            f"🥳HI!! {member_mention} WELCOME TO GRUP\n"
                            "READY TO RECEIVE SMS⁉️\n"
                            "📞GET NUMBER IN BOT⤵️⤵️"
                        )

                        # INLINE KEYBOARD DENGAN BOT_USERNAME_LINK
                        inline_kb = {
                            "inline_keyboard": [
                                [{"text": "📲 GET NUMBER", "url": BOT_USERNAME_LINK}]
                            ]
                        }

                        tg_send(chat_id, welcome_message, reply_markup=inline_kb)
                    continue

                # --- END MODIFIKASI WELCOME MESSAGE ---

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
                    
                    # MEMUAT ULANG GLOBAL_COUNTRY_EMOJI UNTUK DIGUNAKAN DI SINI
                    global GLOBAL_COUNTRY_EMOJI
                    GLOBAL_COUNTRY_EMOJI = load_country_emojis()
                    
                    for line in text.strip().split('\n'):
                        if ' > ' in line:
                            parts = line.split(' > ', 1)
                            range_prefix = parts[0].strip()
                            country_name = parts[1].strip().upper()
                            # MENGGUNAKAN GLOBAL_COUNTRY_EMOJI
                            emoji = GLOBAL_COUNTRY_EMOJI.get(country_name, "🗺️") 
                            new_ranges.append({
                                "range": range_prefix, "country": country_name, "emoji": emoji
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

                if text == "/start":
                    is_member = is_user_in_both_groups(user_id)

                    if is_member:
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

                if user_id in waiting_range:
                    waiting_range.remove(user_id)
                    prefix = text.strip()
                    msg_id_to_edit = pending_message.get(user_id)

                    if is_valid_phone_number(prefix):
                        # Nomor telepon lengkap diinput, bukan range (prefix)
                        tg_send(user_id, "⚠️ Input tidak valid sebagai range. Silakan kirim prefix range, contoh: <code>9377009XXX</code>.")
                        if user_id in pending_message:
                            del pending_message[user_id]
                        
                        # Berikan lagi kesempatan untuk input range
                        waiting_range.add(user_id)
                        
                        continue

                    await process_user_input(page, user_id, prefix, msg_id_to_edit)
                    continue

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
                        kb = {
                            "inline_keyboard": [
                                [{"text": "📌 Gabung Grup 1", "url": GROUP_LINK_1}],
                                [{"text": "📌 Gabung Grup 2", "url": GROUP_LINK_2}],
                                [{"text": "✅ Verifikasi Ulang", "callback_data": "verify"}],
                            ]
                        }
                        tg_edit(chat_id, menu_msg_id, "❌ Belum gabung kedua grup. Silakan join dulu.", kb)
                    else:
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
                        tg_edit(chat_id, menu_msg_id, "⚠️ Harap verifikasi dulu.")
                        continue

                    inline_ranges = load_inline_ranges()

                    if inline_ranges:
                        kb = generate_inline_keyboard(inline_ranges)
                        msg_text = "Silahkan gunakan range di bawah atau Manual range untuk mendapatkan nomor."

                        tg_edit(chat_id, menu_msg_id, f"<b>Get Number</b>\n\n{msg_text}", kb)

                        # Menyimpan ID pesan untuk diedit nanti
                        pending_message[user_id] = menu_msg_id
                    else:
                        # Jika tidak ada inline range, langsung minta input range
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

def initialize_files():
    files = [CACHE_FILE, INLINE_RANGE_FILE, SMC_FILE, WAIT_FILE]
    for file in files:
        if not os.path.exists(file):
            with open(file, "w") as f:
                f.write("[]")
    
    # Inisialisasi file country.json jika belum ada
    if not os.path.exists(COUNTRY_EMOJI_FILE):
        default_emojis = {
            "NEPAL": "🇳🇵",
            "IVORY COAST": "🇨🇮",
            "GUINEA": "🇬🇳",
            "CENTRAL AFRIKA": "🇨🇫",
            "TOGO": "🇹🇬",
            "TAJIKISTAN": "🇹🇯",
            "BENIN": "🇧🇯",
            "SIERRA LEONE": "🇸🇱",
            "MADAGASCAR": "🇲🇬",
            "AFGHANISTAN": "🇦🇫",
        }
        with open(COUNTRY_EMOJI_FILE, "w") as f:
            json.dump(default_emojis, f, indent=2)

async def main():
    print("[INFO] Starting main bot (Telegram/Playwright)...")
    initialize_files()

    # MEMUAT EMOTICON NEGARA SEKALI SAJA SAAT START
    global GLOBAL_COUNTRY_EMOJI
    GLOBAL_COUNTRY_EMOJI = load_country_emojis()
    print(f"[INFO] Memuat {len(GLOBAL_COUNTRY_EMOJI)} emoji negara dari {COUNTRY_EMOJI_FILE}.")

    sms_process = None
    try:
        sms_process = subprocess.Popen([sys.executable, "sms.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
        print(f"[INFO] Started sms.py process with PID: {sms_process.pid}")
    except Exception as e:
        print(f"[FATAL ERROR] Failed to start sms.py: {e}")
        return

    try:
        async with async_playwright() as p:
            try:
                # Menghubungkan ke Chrome yang sudah berjalan (dengan flag --remote-debugging-port=9222)
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            except Exception as e:
                print(f"[ERROR] Gagal koneksi ke Chrome CDP: {e}")
                print("Pastikan Chrome berjalan dengan flag '--remote-debugging-port=9222' dan web target terbuka.")
                return

            context = browser.contexts[0]
            if not context.pages:
                print("[ERROR] No page found in the first context. Ensure the target web page is open.")
                return

            page = context.pages[0]
            print("[OK] Connected to existing Chrome via CDP on port 9222")

            await telegram_loop(page)

    except Exception as e:
        print(f"[FATAL ERROR] An unexpected error occurred: {e}")

    finally:
        if sms_process and sms_process.poll() is None:
            sms_process.terminate()
            print("[INFO] Terminated sms.py process.")

if __name__ == "__main__":
    asyncio.run(main())
