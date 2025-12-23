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
# Pastikan ini diatur di .env
try:
    GROUP_ID_1 = int(os.getenv("GROUP_ID_1"))
    GROUP_ID_2 = int(os.getenv("GROUP_ID_2"))
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError) as e:
    print(f"[FATAL] Variabel lingkungan GROUP_ID_1, GROUP_ID_2, atau ADMIN_ID tidak diatur atau tidak valid: {e}")
    sys.exit(1)

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

CACHE_FILE = "cache.json"
INLINE_RANGE_FILE = "inline.json"
SMC_FILE = "smc.json"
WAIT_FILE = "wait.json"
COUNTRY_EMOJI_FILE = "country.json"
BOT_USERNAME_LINK = "https://t.me/myzuraisgoodbot" # Ganti ini dengan username bot Anda
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1" # Ganti ini
GROUP_LINK_2 = "https://t.me/zura14g" # Ganti ini

verified_users = set()
waiting_range = set()
waiting_admin_input = set()
pending_message = {}
sent_numbers = set()

# Variabel global untuk menyimpan emoji yang dimuat dari file
GLOBAL_COUNTRY_EMOJI = {}


def load_country_emojis():
    """Memuat data emoji negara dari country.json dengan encoding UTF-8."""
    if os.path.exists(COUNTRY_EMOJI_FILE):
        try:
            # PENTING: Menggunakan encoding='utf-8' eksplisit untuk mencegah mojibake
            with open(COUNTRY_EMOJI_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"[ERROR] Gagal memuat {COUNTRY_EMOJI_FILE}: Format JSON tidak valid.")
            return {}
        except Exception as e:
            print(f"[ERROR] Gagal membaca {COUNTRY_EMOJI_FILE}: {e}")
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
    # Regex untuk mengecek apakah input hanya berisi angka, spasi, dash, dan opsional tanda '+' di depan.
    # Digunakan di /start untuk mencegah input range berupa nomor lengkap
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

# --- MODIFIKASI FUNGSI PENGAMBILAN NOMOR UNTUK MENGECEK "Just now" ---
async def get_number_and_country(page):
    """
    Mengambil nomor pertama dari tabel yang memiliki status Last Activity "Just now",
    belum ada di cache, dan status web bukan 'success' atau 'failed'.
    """
    rows = await page.query_selector_all("tbody tr")
    
    for row in rows: 
        # Coba ambil teks 'Last Activity'
        time_el = await row.query_selector("td small.text-muted")
        
        if time_el:
            last_activity_text = (await time_el.inner_text()).strip().lower()
            
            # Kriteria 1: Harus "Just now"
            if last_activity_text != "just now":
                continue # Lewati jika bukan nomor terbaru
                
            # Kriteria 2: Ambil Nomor
            phone_el = await row.query_selector(".phone-number")
            if not phone_el:
                continue

            number = (await phone_el.inner_text()).strip()
            
            # Kriteria 3: Belum di cache
            if is_in_cache(number):
                continue
            
            # Kriteria 4: Status web bukan success/failed
            if await row.query_selector(".status-success") or await row.query_selector(".status-failed"):
                continue

            # Jika semua kriteria lolos
            country_el = await row.query_selector(".badge.bg-primary")
            country = (await country_el.inner_text()).strip().upper() if country_el else "-"

            if number and len(number) > 5:
                return number, country # Nomor pertama yang 'Just now' akan dikembalikan

    return None, None
# --- AKHIR MODIFIKASI FUNGSI PENGAMBILAN NOMOR ---

async def process_user_input(page, user_id, prefix, message_id_to_edit=None):
    global GLOBAL_COUNTRY_EMOJI 

    msg_id = message_id_to_edit if message_id_to_edit else pending_message.pop(user_id, None)

    # --- Feedback Antrian ---
    if playwright_lock.locked():
        if msg_id:
            tg_edit(user_id, msg_id, f"⏳ Permintaan Anda masuk antrian. Mohon tunggu.\nRange: <code>{prefix}</code>")
        else:
            msg_id = tg_send(user_id, f"⏳ Permintaan Anda masuk antrian. Mohon tunggu.\nRange: <code>{prefix}</code>")
            if not msg_id: return

    # --- Lock Utama Playwright ---
    async with playwright_lock:
        try:
            if not msg_id:
                msg_id = tg_send(user_id, f"⏳ Sedang mengambil Number...\nRange: <code>{prefix}</code>")
                if not msg_id: return

            tg_edit(user_id, msg_id, f"✅ Antrian diterima. Sedang mengirim range ke web...\nRange: <code>{prefix}</code>")

            # --- Interaksi Playwright ---
            await page.wait_for_selector('input[name="numberrange"]', timeout=10000)
            await page.fill('input[name="numberrange"]', prefix)
            await asyncio.sleep(0.5)

            # Klik tombol tanpa reload
            await page.click("#getNumberBtn", force=True)

            # Menunggu hasil AJAX (tabel diperbarui)
            try:
                # Menunggu setidaknya satu baris baru muncul di dalam tbody
                await page.wait_for_selector("tbody tr", timeout=15000)
            except Exception:
                print(f"[INFO] Timeout menunggu hasil AJAX setelah klik getNumberBtn untuk range {prefix}. Melanjutkan...")
                pass
            
            await asyncio.sleep(1) # Beri jeda stabilitas DOM

            number, country = await get_number_and_country(page)

            if not number:
                # --- LOADING DINAMIS (Menunggu status 'Just now' muncul) ---
                # Durasi diperpanjang karena kita menunggu status 'Just now' yang butuh waktu.
                delay_duration = 10.0 
                update_interval = 0.5
                
                loading_statuses = [
                    "⏳ mencoba lagi s.",
                    "⏳ mencoba lagi sa..",
                    "⏳ mencoba lagi sab...",
                    "⏳ mencoba lagi saba....",
                    "⏳ mencoba lagi sabar.....",
                ]

                start_time = time.time()
                while (time.time() - start_time) < delay_duration:
                    index = int((time.time() - start_time) / update_interval) % len(loading_statuses)
                    current_status = loading_statuses[index]
                    
                    tg_edit(user_id, msg_id, f"{current_status}\nRange: <code>{prefix}</code>")
                    
                    await asyncio.sleep(update_interval)

                number, country = await get_number_and_country(page)
                # --- END LOADING DINAMIS ---

            if not number:
                tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DI TEMUKAN ATAU STATUS BUKAN 'Just now'. SILAHKAN KLIK /start - GET NUMBER ULANG")
                return

            save_cache({"number": number, "country": country})
            add_to_wait_list(number, user_id)

            # Menggunakan GLOBAL_COUNTRY_EMOJI
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
            print(f"[ERROR] Terjadi kesalahan pada Playwright/Web: {type(e).__name__} - {e}")
            if msg_id:
                tg_edit(user_id, msg_id, f"❌ Terjadi kesalahan saat proses web. Cek log bot: {type(e).__name__}")
    # --- END Lock Utama Playwright ---

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

                # --- WELCOME MESSAGE ---
                if "new_chat_members" in msg and chat_id == GROUP_ID_2:
                    for member in msg["new_chat_members"]:
                        if member["is_bot"]: continue

                        member_first_name = member.get("first_name", "New User")
                        member_mention = f"<a href='tg://user?id={member['id']}'>{member_first_name}</a>"

                        welcome_message = (
                            f"🥳HI!! {member_mention} WELCOME TO GRUP\n"
                            "READY TO RECEIVE SMS⁉️\n"
                            "📞GET NUMBER IN BOT⤵️⤵️"
                        )

                        inline_kb = {
                            "inline_keyboard": [
                                [{"text": "📲 GET NUMBER", "url": BOT_USERNAME_LINK}]
                            ]
                        }
                        tg_send(chat_id, welcome_message, reply_markup=inline_kb)
                    continue

                # --- ADMIN /add COMMAND ---
                if user_id == ADMIN_ID:
                    if text.startswith("/add"):
                        waiting_admin_input.add(user_id)
                        prompt_msg_text = "Silahkan kirim daftar range dalam format:\n\n<code>range > country</code>\n\nContoh:\n<code>23273XXX > SIERRA LEONE\n97798XXXX > NEPAL</code>"
                        msg_id = tg_send(user_id, prompt_msg_text)
                        if msg_id:
                            pending_message[user_id] = msg_id
                        continue

                # --- ADMIN INPUT PROCESSING ---
                if user_id in waiting_admin_input:
                    waiting_admin_input.remove(user_id)
                    new_ranges = []
                    
                    global GLOBAL_COUNTRY_EMOJI
                    GLOBAL_COUNTRY_EMOJI = load_country_emojis() # Reload emoji

                    for line in text.strip().split('\n'):
                        if ' > ' in line:
                            parts = line.split(' > ', 1)
                            range_prefix = parts[0].strip()
                            country_name = parts[1].strip().upper()
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

                # --- /start COMMAND ---
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

                # --- RANGE INPUT (Manual) ---
                if user_id in waiting_range:
                    waiting_range.remove(user_id)
                    prefix = text.strip()
                    msg_id_to_edit = pending_message.get(user_id)

                    if is_valid_phone_number(prefix):
                        tg_send(user_id, "⚠️ Input tidak valid sebagai range. Silakan kirim prefix range, contoh: <code>9377009XXX</code>.")
                        if user_id in pending_message:
                            del pending_message[user_id]
                        
                        waiting_range.add(user_id) # Minta input ulang
                        
                        continue

                    await process_user_input(page, user_id, prefix, msg_id_to_edit)
                    continue

            if "callback_query" in upd:
                cq = upd["callback_query"]
                user_id = cq["from"]["id"]
                data_cb = cq["data"]

                chat_id = cq["message"]["chat"]["id"]
                menu_msg_id = cq["message"]["message_id"]

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
                        tg_edit(chat_id, menu_msg_id, "✅ Verifikasi Berhasil!\n\nGunakan tombol di bawah:", kb)
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

def initialize_files():
    files = {CACHE_FILE: "[]", INLINE_RANGE_FILE: "[]", SMC_FILE: "[]", WAIT_FILE: "[]"}
    for file, default_content in files.items():
        if not os.path.exists(file):
            with open(file, "w") as f:
                f.write(default_content)
    
    # Inisialisasi country.json jika belum ada
    if not os.path.exists(COUNTRY_EMOJI_FILE):
        default_emojis = {
            "NEPAL": "🇳🇵",
            "IVORY COAST": "🇨🇮",
            "GUINEA": "🇬🇳",
            "CENTRAL AFRIKA": "🇨🇫", # Menggunakan nama lama sebagai default, harus disesuaikan jika ingin pakai nama penuh
            "TOGO": "🇹🇬",
            "TAJIKISTAN": "🇹🇯",
            "BENIN": "🇧🇯",
            "SIERRA LEONE": "🇸🇱",
            "MADAGASCAR": "🇲🇬",
            "AFGANISTAN": "🇦🇫",
        }
        try:
            with open(COUNTRY_EMOJI_FILE, "w", encoding='utf-8') as f:
                json.dump(default_emojis, f, indent=2)
            print(f"[INFO] File {COUNTRY_EMOJI_FILE} dibuat dengan emoji default.")
        except Exception as e:
            print(f"[ERROR] Gagal menulis {COUNTRY_EMOJI_FILE}: {e}")


async def main():
    print("[INFO] Starting main bot (Telegram/Playwright)...")
    initialize_files()

    # --- MEMUAT GLOBAL COUNTRY EMOTICON ---
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
