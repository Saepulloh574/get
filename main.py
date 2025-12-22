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
from copy import deepcopy # Digunakan untuk memecahkan masalah copy list/dict

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
BOT_USERNAME_LINK = "https://t.me/myzuraisgoodbot" 
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1" 
GROUP_LINK_2 = "https://t.me/zura14g" 

verified_users = set()
waiting_range = set()
# waiting_admin_input diubah menjadi dictionary untuk menyimpan mode dan data edit
waiting_admin_input = {} # {user_id: {"mode": "add"|"edit", "prefix_lama": None}} 
pending_message = {}
sent_numbers = set()

GLOBAL_COUNTRY_EMOJI = {}


def load_country_emojis():
    """Memuat data emoji negara dari country.json dengan encoding UTF-8."""
    if os.path.exists(COUNTRY_EMOJI_FILE):
        try:
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

# Fungsi pembantu untuk membuat inline keyboard menu admin
def generate_admin_range_keyboard(ranges, mode):
    keyboard = []
    current_row = []
    
    # Menentukan callback prefix dan tombol kembali
    if mode == "edit":
        prefix_cb = "edit_select:"
        back_cb = "manage_range"
    elif mode == "delete":
        prefix_cb = "delete_select:"
        back_cb = "manage_range"
    else:
        return {"inline_keyboard": []}

    for item in ranges:
        text = f"{item['country']} - {item['range']}"
        callback_data = f"{prefix_cb}{item['range']}"
        current_row.append({"text": text, "callback_data": callback_data})

        if len(current_row) == 1: # Satu range per baris agar mudah diklik
            keyboard.append(current_row)
            current_row = []

    if current_row:
        keyboard.append(current_row)

    keyboard.append([{"text": "« Kembali ke Menu Utama", "callback_data": back_cb}])
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
        
        if await row.query_selector(".status-success") or await row.query_selector(".status-failed"):
            continue

        country_el = await row.query_selector(".badge.bg-primary")
        country = (await country_el.inner_text()).strip().upper() if country_el else "-"

        if number and len(number) > 5:
            return number, country

    return None, None

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

            tg_edit(user_id, msg_id, f"✅ Antrian diterima. Sedang mengambil Number...\nRange: <code>{prefix}</code>")

            # --- Interaksi Playwright ---
            await page.wait_for_selector('input[name="numberrange"]', timeout=10000)
            await page.fill('input[name="numberrange"]', prefix)
            await asyncio.sleep(0.5)

            await page.click("#getNumberBtn", force=True)

            try:
                await page.wait_for_selector("tbody tr", timeout=15000)
            except Exception:
                print(f"[INFO] Timeout menunggu hasil AJAX setelah klik getNumberBtn untuk range {prefix}. Melanjutkan...")
                pass
            
            await asyncio.sleep(2) 

            number, country = await get_number_and_country(page)

            if not number:
                # --- LOADING DINAMIS ---
                delay_duration = 5.0
                update_interval = 0.5
                
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

                number, country = await get_number_and_country(page)
                # --- END LOADING DINAMIS ---

            if not number:
                tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DI TEMUKAN SILAHKAN KLIK /start - GET NUMBER ULANG")
                return

            save_cache({"number": number, "country": country})
            add_to_wait_list(number, user_id)

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
                    # ... (logika welcome message tidak berubah)
                    # (Dihilangkan untuk brevity)
                    continue

                # --- ADMIN /add COMMAND (Menu Utama) ---
                if user_id == ADMIN_ID:
                    if text == "/add":
                        kb = {
                            "inline_keyboard": [
                                [{"text": "✍️ Edit Range", "callback_data": "edit_menu"},
                                 {"text": "🗑️ Hapus Range", "callback_data": "delete_menu"}],
                                [{"text": "➕ Tambah Range Baru", "callback_data": "add_range"}],
                            ]
                        }
                        tg_send(user_id, "⚙️ **Manajemen Range Inline**\n\nSilakan pilih opsi:", kb)
                        continue

                # --- ADMIN INPUT PROCESSING (Tambah/Edit) ---
                if user_id in waiting_admin_input:
                    admin_state = waiting_admin_input.pop(user_id)
                    mode = admin_state["mode"]
                    prompt_msg_id = pending_message.pop(user_id, None)
                    current_ranges = load_inline_ranges()
                    global GLOBAL_COUNTRY_EMOJI
                    GLOBAL_COUNTRY_EMOJI = load_country_emojis()
                    
                    if mode == "add":
                        new_ranges = []
                        for line in text.strip().split('\n'):
                            if ' > ' in line:
                                parts = line.split(' > ', 1)
                                range_prefix = parts[0].strip()
                                country_name = parts[1].strip().upper()
                                
                                # Cek duplikasi sebelum menambah
                                if any(r['range'] == range_prefix for r in current_ranges):
                                    if prompt_msg_id:
                                        tg_edit(user_id, prompt_msg_id, f"❌ Range <code>{range_prefix}</code> sudah ada. Batalkan penambahan range.")
                                    continue
                                
                                emoji = GLOBAL_COUNTRY_EMOJI.get(country_name, "🗺️")
                                new_ranges.append({
                                    "range": range_prefix, "country": country_name, "emoji": emoji
                                })
                        
                        if new_ranges:
                            updated_ranges = current_ranges + new_ranges
                            save_inline_ranges(updated_ranges)
                            if prompt_msg_id:
                                tg_edit(user_id, prompt_msg_id, f"✅ Berhasil menambahkan {len(new_ranges)} range baru. Total range: {len(updated_ranges)}.")
                        else:
                            if prompt_msg_id:
                                tg_edit(user_id, prompt_msg_id, "❌ Format tidak valid atau tidak ada range yang ditemukan. Batalkan penambahan range.")
                                
                    elif mode == "edit":
                        old_prefix = admin_state["prefix_lama"]
                        new_prefix = text.strip()

                        # Cek apakah format input baru sesuai (tidak boleh mengandung ' > ')
                        if ' > ' in new_prefix or not new_prefix:
                            tg_edit(user_id, prompt_msg_id, "❌ Input range baru tidak valid. Range harus berupa prefix tunggal, cth: <code>97798XXXX</code>")
                            continue
                        
                        found = False
                        for r in current_ranges:
                            if r['range'] == old_prefix:
                                r['range'] = new_prefix
                                found = True
                                break
                        
                        if found:
                            save_inline_ranges(current_ranges)
                            tg_edit(user_id, prompt_msg_id, f"✅ Range <code>{old_prefix}</code> berhasil diperbarui menjadi <code>{new_prefix}</code>.")
                        else:
                            tg_edit(user_id, prompt_msg_id, f"❌ Range lama <code>{old_prefix}</code> tidak ditemukan saat mencoba pembaruan.")

                    continue

                # --- /start COMMAND ---
                if text == "/start":
                    # ... (logika /start tidak berubah)
                    # (Dihilangkan untuk brevity)
                    continue

                # --- RANGE INPUT (Manual User) ---
                if user_id in waiting_range:
                    # ... (logika input range user tidak berubah)
                    # (Dihilangkan untuk brevity)
                    await process_user_input(page, user_id, prefix, msg_id_to_edit)
                    continue

            if "callback_query" in upd:
                cq = upd["callback_query"]
                user_id = cq["from"]["id"]
                data_cb = cq["data"]
                chat_id = cq["message"]["chat"]["id"]
                menu_msg_id = cq["message"]["message_id"]

                # Cek izin admin
                if user_id == ADMIN_ID:
                    
                    # 1. Menu Utama Manajemen Range
                    if data_cb == "manage_range":
                        kb = {
                            "inline_keyboard": [
                                [{"text": "✍️ Edit Range", "callback_data": "edit_menu"},
                                 {"text": "🗑️ Hapus Range", "callback_data": "delete_menu"}],
                                [{"text": "➕ Tambah Range Baru", "callback_data": "add_range"}],
                            ]
                        }
                        tg_edit(chat_id, menu_msg_id, "⚙️ **Manajemen Range Inline**\n\nSilakan pilih opsi:", kb)
                        return

                    # 2. Mode Tambah Range
                    if data_cb == "add_range":
                        waiting_admin_input[user_id] = {"mode": "add", "prefix_lama": None}
                        prompt_msg_text = "Silahkan kirim daftar range baru (satu atau banyak) dalam format:\n\n<code>range > country</code>\n\nContoh:\n<code>23273XXX > SIERRA LEONE\n97798XXXX > NEPAL</code>"
                        tg_edit(chat_id, menu_msg_id, prompt_msg_text)
                        pending_message[user_id] = menu_msg_id # Simpan ID pesan untuk diedit
                        return

                    # 3. Menu Edit Range (Pilih Range)
                    if data_cb == "edit_menu":
                        ranges = load_inline_ranges()
                        if not ranges:
                            tg_edit(chat_id, menu_msg_id, "⚠️ Tidak ada range yang tersedia untuk diedit.", reply_markup={"inline_keyboard": [[{"text": "« Kembali", "callback_data": "manage_range"}]]})
                            return
                        
                        kb = generate_admin_range_keyboard(ranges, "edit")
                        tg_edit(chat_id, menu_msg_id, "✍️ **Edit Range**\n\nSilahkan klik salah satu range untuk di edit:", kb)
                        return

                    # 4. Memilih Range untuk Diedit (edit_select:prefix)
                    if data_cb.startswith("edit_select:"):
                        old_prefix = data_cb.split(":")[1]
                        
                        # Temukan detail negara dari prefix lama
                        ranges = load_inline_ranges()
                        selected_range = next((r for r in ranges if r['range'] == old_prefix), None)
                        
                        if selected_range:
                            waiting_admin_input[user_id] = {"mode": "edit", "prefix_lama": old_prefix}
                            
                            prompt_text = (
                                f"📝 **Edit Range**\n\n"
                                f"Anda memilih **{selected_range['country']}** dengan range lama: <code>{old_prefix}</code>.\n\n"
                                f"Silahkan kirim range terbaru untuk negara ini (Contoh: <code>1234577XXX</code>):"
                            )
                            tg_edit(chat_id, menu_msg_id, prompt_text)
                            pending_message[user_id] = menu_msg_id
                        else:
                            tg_edit(chat_id, menu_msg_id, "❌ Range tidak ditemukan. Silakan coba lagi.", reply_markup={"inline_keyboard": [[{"text": "« Kembali", "callback_data": "edit_menu"}]]})
                        return

                    # 5. Menu Hapus Range (Pilih Range)
                    if data_cb == "delete_menu":
                        ranges = load_inline_ranges()
                        if not ranges:
                            tg_edit(chat_id, menu_msg_id, "⚠️ Tidak ada range yang tersedia untuk dihapus.", reply_markup={"inline_keyboard": [[{"text": "« Kembali", "callback_data": "manage_range"}]]})
                            return
                        
                        kb = generate_admin_range_keyboard(ranges, "delete")
                        tg_edit(chat_id, menu_msg_id, "🗑️ **Hapus Range**\n\nSilahkan klik salah satu range untuk di hapus:", kb)
                        return

                    # 6. Memilih Range untuk Dihapus (delete_select:prefix)
                    if data_cb.startswith("delete_select:"):
                        prefix_to_delete = data_cb.split(":")[1]
                        
                        # Tombol konfirmasi
                        kb = {
                            "inline_keyboard": [
                                [{"text": f"✅ Konfirmasi Hapus <code>{prefix_to_delete}</code>", "callback_data": f"confirm_delete:{prefix_to_delete}"}],
                                [{"text": "« Batalkan", "callback_data": "delete_menu"}]
                            ]
                        }
                        
                        ranges = load_inline_ranges()
                        selected_range = next((r for r in ranges if r['range'] == prefix_to_delete), {"country": "N/A"})
                        
                        tg_edit(chat_id, menu_msg_id, f"⚠️ **Konfirmasi Penghapusan**\n\nApakah Anda yakin ingin menghapus range:\n**{selected_range['country']}** (<code>{prefix_to_delete}</code>)?", kb)
                        return

                    # 7. Konfirmasi Penghapusan (confirm_delete:prefix)
                    if data_cb.startswith("confirm_delete:"):
                        prefix_to_delete = data_cb.split(":")[1]
                        ranges = load_inline_ranges()
                        
                        # Buat daftar baru tanpa range yang dihapus
                        updated_ranges = [r for r in ranges if r['range'] != prefix_to_delete]
                        
                        if len(updated_ranges) < len(ranges):
                            save_inline_ranges(updated_ranges)
                            tg_edit(chat_id, menu_msg_id, f"✅ Range <code>{prefix_to_delete}</code> berhasil dihapus. Sisa {len(updated_ranges)} range.", reply_markup={"inline_keyboard": [[{"text": "« Kembali ke Menu Utama", "callback_data": "manage_range"}]]})
                        else:
                            tg_edit(chat_id, menu_msg_id, "❌ Gagal menghapus. Range tidak ditemukan.", reply_markup={"inline_keyboard": [[{"text": "« Kembali ke Menu Utama", "callback_data": "manage_range"}]]})
                        return

                # --- Callback Query NON-ADMIN ---
                if data_cb == "verify":
                    # ... (logika verify tidak berubah)
                    # (Dihilangkan untuk brevity)
                    continue

                if data_cb == "getnum":
                    # ... (logika getnum tidak berubah)
                    # (Dihilangkan untuk brevity)
                    continue

                if data_cb.startswith("select_range:"):
                    # ... (logika select_range tidak berubah)
                    # (Dihilangkan untuk brevity)
                    prefix = data_cb.split(":")[1]
                    tg_edit(chat_id, menu_msg_id, f"<b>Get Number</b>\n\nRange dipilih: <code>{prefix}</code>\n⏳ Sedang memproses...")
                    await process_user_input(page, user_id, prefix, menu_msg_id)
                    continue

                if data_cb == "manual_range":
                    # ... (logika manual_range tidak berubah)
                    # (Dihilangkan untuk brevity)
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
            "NEPAL": "🇳🇵", "IVORY COAST": "🇨🇮", "GUINEA": "🇬🇳", 
            "CENTRAL AFRIKA": "🇨🇫", "TOGO": "🇹🇬", "TAJIKISTAN": "🇹🇯", 
            "BENIN": "🇧🇯", "SIERRA LEONE": "🇸🇱", "MADAGASCAR": "🇲🇬", 
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
            # ... (logika koneksi playwright)
            try:
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
            # ... (end logika koneksi playwright)

            await telegram_loop(page)

    except Exception as e:
        print(f"[FATAL ERROR] An unexpected error occurred: {e}")

    finally:
        if sms_process and sms_process.poll() is None:
            sms_process.terminate()
            print("[INFO] Terminated sms.py process.")

if __name__ == "__main__":
    asyncio.run(main())
