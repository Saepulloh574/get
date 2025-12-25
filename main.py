import asyncio
import json
import os
import requests
import re
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from dotenv import load_dotenv
import subprocess
import sys
import time

# --- ASYNCIO LOCK UNTUK ANTRIAN PLAYWRIGHT ---
playwright_lock = asyncio.Lock()
# ----------------------------------------------

# --- DATA GLOBAL EMOJI NEGARA (DIGABUNGKAN) ---
GLOBAL_COUNTRY_EMOJI = {
  "AFGHANISTAN": "🇦🇫", "ALBANIA": "🇦🇱", "ALGERIA": "🇩🇿", "ANDORRA": "🇦🇩", "ANGOLA": "🇦🇴",
  "ANTIGUA AND BARBUDA": "🇦🇬", "ARGENTINA": "🇦🇷", "ARMENIA": "🇦🇲", "AUSTRALIA": "🇦🇺", "AUSTRIA": "🇦🇹",
  "AZERBAIJAN": "🇦🇿", "BAHAMAS": "🇧🇸", "BAHRAIN": "🇧🇭", "BANGLADESH": "🇧🇩", "BARBADOS": "🇧🇧",
  "BELARUS": "🇧🇾", "BELGIUM": "🇧🇪", "BELIZE": "🇧🇿", "BENIN": "🇧🇯", "BHUTAN": "🇧🇹",
  "BOLIVIA": "🇧🇴", "BOSNIA AND HERZEGOVINA": "🇧🇦", "BOTSWANA": "🇧🇼", "BRAZIL": "🇧🇷", "BRUNEI": "🇧🇳",
  "BULGARIA": "🇧🇬", "BURKINA FASO": "🇧🇫", "BURUNDI": "🇧🇮", "CAMBODIA": "🇰🇭", "CAMEROON": "🇨🇲",
  "CANADA": "🇨🇦", "CAPE VERDE": "🇨🇻", "CENTRAL AFRICAN REPUBLIC": "🇨🇫", "CHAD": "🇹🇩", "CHILE": "🇨🇱",
  "CHINA": "🇨🇳", "COLOMBIA": "🇨🇴", "COMOROS": "🇰🇲", "CONGO": "🇨🇬", "COSTA RICA": "🇨🇷",
  "CROATIA": "🇭🇷", "CUBA": "🇨🇺", "CYPRUS": "🇨🇾", "CZECH REPUBLIC": "🇨🇿", "IVORY COAST": "🇨🇮",
  "DENMARK": "🇩🇰", "DJIBOUTI": "🇩🇯", "DOMINICA": "🇩🇲", "DOMINICAN REPUBLIC": "🇩🇴", "ECUADOR": "🇪🇨",
  "EGYPT": "🇪🇬", "EL SALVADOR": "🇸🇻", "EQUATORIAL GUINEA": "🇬🇶", "ERITREA": "🇪🇷", "ESTONIA": "🇪🇪",
  "ESWATINI": "🇸🇿", "ETHIOPIA": "🇪🇹", "FIJI": "🇫🇯", "FINLAND": "🇫🇮", "FRANCE": "🇫🇷",
  "GABON": "🇬🇦", "GAMBIA": "🇬🇲", "GEORGIA": "🇬🇪", "GERMANY": "🇩🇪", "GHANA": "🇬🇭",
  "GREECE": "🇬🇷", "GRENADA": "🇬🇩", "GUATEMALA": "🇬🇹", "GUINEA": "🇬🇳", "GUINEA-BISSAU": "🇬🇼",
  "GUYANA": "🇬🇾", "HAITI": "🇭🇹", "HONDURAS": "🇭🇳", "HUNGARY": "🇭🇺", "ICELAND": "🇮🇸",
  "INDIA": "🇮🇳", "INDONESIA": "🇮🇩", "IRAN": "🇮🇷", "IRAQ": "🇮🇶", "IRELAND": "🇮🇪",
  "ISRAEL": "🇮🇱", "ITALY": "🇮🇹", "JAMAICA": "🇯🇲", "JAPAN": "🇯🇵", "JORDAN": "🇯🇴",
  "KAZAKHSTAN": "🇰🇿", "KENYA": "🇰🇪", "KIRIBATI": "🇰🇮", "KUWAIT": "🇰🇼", "KYRGYZSTAN": "🇰🇬",
  "LAOS": "🇱🇦", "LATVIA": "🇱🇻", "LEBANON": "🇱🇧", "LESOTHO": "🇱🇸", "LIBERIA": "🇱🇷",
  "LIBYA": "🇱🇾", "LIECHTENSTEIN": "🇱🇮", "LITHUANIA": "🇱🇹", "LUXEMBOURG": "🇱🇺", "MADAGASCAR": "🇲🇬",
  "MALAWI": "🇲🇼", "MALAYSIA": "🇲🇾", "MALDIVES": "🇲🇻", "MALI": "🇲🇱", "MALTA": "🇲🇹",
  "MARSHALL ISLANDS": "🇲🇭", "MAURITANIA": "🇲🇷", "MAURITIUS": "🇲🇺", "MEXICO": "🇲🇽", "MICRONESIA": "🇫🇲",
  "MOLDOVA": "🇲🇩", "MONACO": "🇲🇨", "MONGOLIA": "🇲🇳", "MONTENEGRO": "🇲🇪", "MOROCCO": "🇲🇦",
  "MOZAMBIQUE": "🇲🇿", "MYANMAR": "🇲🇲", "NAMIBIA": "🇳🇦", "NAURU": "🇳🇷", "NEPAL": "🇳🇵",
  "NETHERLANDS": "🇳🇱", "NEW ZEALAND": "🇳🇿", "NICARAGUA": "🇳🇮", "NIGER": "🇳🇪", "NIGERIA": "🇳🇬",
  "NORTH KOREA": "🇰🇵", "NORTH MACEDONIA": "🇲🇰", "NORWAY": "🇳🇴", "OMAN": "🇴🇲", "PAKISTAN": "🇵🇰",
  "PALAU": "🇵🇼", "PALESTINE": "🇵🇸", "PANAMA": "🇵🇦", "PAPUA NEW GUINEA": "🇵🇬", "PARAGUAY": "🇵🇾",
  "PERU": "🇵🇪", "PHILIPPINES": "🇵🇭", "POLAND": "🇵🇱", "PORTUGAL": "🇵🇹", "QATAR": "🇶🇦",
  "ROMANIA": "🇷🇴", "RUSSIA": "🇷🇺", "RWANDA": "🇷🇼", "SAINT KITTS AND NEVIS": "🇰🇳", "SAINT LUCIA": "🇱🇨",
  "SAINT VINCENT AND THE GRENADINES": "🇻🇨", "SAMOA": "🇼🇸", "SAN MARINO": "🇸🇲", "SAO TOME AND PRINCIPE": "🇸🇹",
  "SAUDI ARABIA": "🇸🇦", "SENEGAL": "🇸🇳", "SERBIA": "🇷🇸", "SEYCHELLES": "🇸🇨", "SIERRA LEONE": "🇸🇱",
  "SINGAPORE": "🇸🇬", "SLOVAKIA": "🇸🇰", "SLOVENIA": "🇸🇮", "SOLOMON ISLANDS": "🇸🇧", "SOMALIA": "🇸🇴",
  "SOUTH AFRICA": "🇿🇦", "SOUTH KOREA": "🇰🇷", "SOUTH SUDAN": "🇸🇸", "SPAIN": "🇪🇸", "SRI LANKA": "🇱🇰",
  "SUDAN": "🇸🇩", "SURINAME": "🇸🇷", "SWEDEN": "🇸🇪", "SWITZERLAND": "🇨🇭", "SYRIA": "🇸🇾",
  "TAJIKISTAN": "🇹🇯", "TANZANIA": "🇹🇿", "THAILAND": "🇹🇭", "TIMOR-LESTE": "🇹🇱", "TOGO": "🇹🇬",
  "TONGA": "🇹🇴", "TRINIDAD AND TOBAGO": "🇹🇹", "TUNISIA": "🇹🇳", "TURKEY": "🇹🇷", "TURKMENISTAN": "🇹🇲",
  "TUVALU": "🇹🇻", "UGANDA": "🇺🇬", "UKRAINE": "🇺🇦", "UNITED ARAB EMIRATES": "🇦🇪", "UNITED KINGDOM": "🇬🇧",
  "UNITED STATES": "🇺🇸", "URUGUAY": "🇺🇾", "UZBEKISTAN": "🇺🇿", "VANUATU": "🇻🇺", "VATICAN CITY": "🇻🇦",
  "VENEZUELA": "🇻🇪", "VIETNAM": "🇻🇳", "YEMEN": "🇾🇪", "ZAMBIA": "🇿🇲", "ZIMBABWE": "🇿🇼", "UNKNOWN": "🗺️" 
}
# ----------------------------------------------

# --- KONFIGURASI PROGRESS BAR GLOBAL (DIUBAH) ---
MAX_BARS = 12 # MODIFIKASI: Diubah dari 15 menjadi 12
BAR_EMOJI = "◽"

def get_progress_message(current_step, total_steps, prefix_range):
    """Menghasilkan pesan progress bar yang berulang, dapat diakses secara global."""
    bar_count = (current_step % MAX_BARS) + 1
    progress_bar = BAR_EMOJI * bar_count
    
    # MODIFIKASI: Menambahkan tag <code> pada bagian tertentu
    return (
    f"<code>Looking for your number, please be patient, sir.</code>\n"
    f"<blockquote>Range: <code>{prefix_range}</code></blockquote>\n"
    f"<code>Load:</code> {progress_bar}"
)
# ---------------------------------------------------------


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    GROUP_ID_1 = int(os.getenv("GROUP_ID_1"))
    GROUP_ID_2 = int(os.getenv("GROUP_ID_2"))
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError) as e:
    print(f"[FATAL] Variabel lingkungan GROUP_ID_1, GROUP_ID_2, atau ADMIN_ID tidak diatur atau tidak valid: {e}")
    sys.exit(1)

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
BASE_WEB_URL = "https://v2.mnitnetwork.com/dashboard/getnum" 

CACHE_FILE = "cache.json"
INLINE_RANGE_FILE = "inline.json"
SMC_FILE = "smc.json"
WAIT_FILE = "wait.json"
COUNTRY_EMOJI_FILE = "country.json" 
BOT_USERNAME_LINK = "https://t.me/myzuraisgoodbot" 
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1" 
GROUP_LINK_2 = "https://t.me/zura14g" 

verified_users = set()
waiting_admin_input = set()
manual_range_input = set() 
pending_message = {}
sent_numbers = set()
last_used_range = {}


# --- FUNGSI UTILITAS MANAJEMEN FILE (Tidak ada perubahan) ---

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
    if len(cache) >= 1000:
        cache.pop(0) 
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
    """Membuat keyboard inline dari daftar range yang tersedia, ditambah tombol Manual Range."""
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
    
    keyboard.append([{"text": "✍️ Input Manual Range", "callback_data": "manual_range"}])
    
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


# --- FUNGSI UTILITAS TELEGRAM API (Tidak ada perubahan) ---

def tg_send(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{API}/sendMessage", json=data).json()
        if r.get("ok"):
            return r["result"]["message_id"]
        print(f"[ERROR SEND] {r.get('description', 'Unknown Error')} for chat_id {chat_id}")
        return None
    except Exception as e:
        print(f"[ERROR SEND REQUEST] {e}")
        return None

def tg_edit(chat_id, message_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{API}/editMessageText", json=data).json()
        if not r.get("ok"):
            if "message is not modified" not in r.get("description", ""):
                 print(f"[ERROR EDIT] {r.get('description', 'Unknown Error')} for chat_id {chat_id}")
    except Exception as e:
        print(f"[ERROR EDIT REQUEST] {e}")

def tg_get_updates(offset):
    try:
        return requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 5}).json()
    except requests.exceptions.ReadTimeout:
        return {"ok": True, "result": []}
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

def clear_pending_updates():
    """Mengabaikan semua update Telegram yang tertunda."""
    try:
        r = requests.get(f"{API}/getUpdates", params={"offset": -1, "timeout": 1}).json()
        if r.get("ok") and r.get("result"):
            last_update_id = r["result"][-1]["update_id"]
            r = requests.get(f"{API}/getUpdates", params={"offset": last_update_id + 1, "timeout": 1}).json()
            if r.get("ok"):
                 print(f"[INFO] Berhasil membersihkan hingga {len(r['result'])} updates lama.")
                 return
        print("[INFO] Tidak ada updates lama yang perlu dibersihkan.")
    except Exception as e:
        print(f"[ERROR CLEAR UPDATES] Gagal membersihkan pending updates: {e}")


# --- FUNGSI PLAYWRIGHT ASYNC (get_number_and_country tidak diubah) ---

async def get_number_and_country(page):
    """Mengambil nomor terbaru dari tabel, jika belum di cache dan status belum final."""
    try:
        row = await page.query_selector("tbody tr:first-child") 
        if not row: return None, None
            
        phone_el = await row.query_selector(".phone-number")
        if not phone_el: return None, None

        number = (await phone_el.inner_text()).strip()
        
        if is_in_cache(number): return None, None 
        
        status_el = await row.query_selector("td:nth-child(3) .badge")
        if status_el:
             status_text = (await status_el.inner_text()).strip().lower()
             if "success" in status_text or "failed" in status_text: return None, None
        
        country_el = await row.query_selector(".badge.bg-primary")
        country = (await country_el.inner_text()).strip().upper() if country_el else "UNKNOWN"

        if number and len(number) > 5: return number, country 
        return None, None
        
    except Exception as e:
        # Menghilangkan logging error berlebihan yang terjadi selama polling Playwright
        # print(f"[ERROR GET NUMBER] Gagal membaca DOM: {e}")
        return None, None


# MODIFIKASI: Menerima 'browser'
async def process_user_input(browser, user_id, prefix, message_id_to_edit=None):
    """Memproses permintaan Get Number menggunakan Playwright dengan tab baru untuk setiap permintaan."""
    global GLOBAL_COUNTRY_EMOJI 
    global last_used_range 

    msg_id = message_id_to_edit if message_id_to_edit else pending_message.pop(user_id, None)
    page = None

    # --- Feedback Antrian ---
    if playwright_lock.locked():
        if not msg_id:
            msg_id = tg_send(user_id, get_progress_message(0, 0, prefix))
            if not msg_id: return
        else:
            tg_edit(user_id, msg_id, get_progress_message(0, 0, prefix))

    # --- Lock Utama Playwright ---
    async with playwright_lock:
        
        try:
            current_step = 0 
            
            # --- Inisialisasi Pesan Awal ---
            if not msg_id:
                msg_id = tg_send(user_id, get_progress_message(current_step, 0, prefix))
                if not msg_id: return
            
            # Mendapatkan konteks dan membuat tab baru
            context = browser.contexts[0]
            page = await context.new_page() 
            print(f"[DEBUG] Tab baru dibuka untuk user {user_id}")
            
            # 1. NAVIGASI KE URL BARU
            NEW_URL = f"{BASE_WEB_URL}?range={prefix}"
            await page.goto(NEW_URL, wait_until='domcontentloaded', timeout=30000)
            current_step += 1
            tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix))
            
            # --- Jeda 3 Detik di sini ---
            await asyncio.sleep(3) 
            current_step += 1
            tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix))

            # 2. TUNGGU TOMBOL SIAP DAN KLIK (Awal)
            await page.wait_for_selector("#getNumberBtn", state='visible', timeout=15000)
            await page.click("#getNumberBtn", force=True)
            
            # 3. TUNGGU PEMUATAN JARINGAN & PENCARIAN (Awal)
            await asyncio.sleep(1) 
            current_step += 1
            tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix))
            await page.wait_for_load_state('networkidle', timeout=15000) 
            await asyncio.sleep(2) 
            current_step += 1
            tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix))

            # 5. MULAI MENCARI NOMOR (Siklus 1 & 2)
            delay_duration_round_1 = 5.0 # Durasi pencarian Siklus 1
            delay_duration_round_2 = 5.0 # Durasi pencarian Siklus 2
            
            # MODIFIKASI UTAMA: Update Progress Bar setiap 0.5 detik
            progress_update_interval = 0.5 
            check_number_interval = 1.0 # Interval pengecekan nomor Playwright
            
            number = None
            
            for round_num, duration in enumerate([delay_duration_round_1, delay_duration_round_2]):
                
                # Logika Klik Ulang pada Siklus 2
                if round_num == 1 and not number: 
                    await page.click("#getNumberBtn", force=True)
                    await asyncio.sleep(1) 
                    await page.wait_for_load_state('networkidle', timeout=15000)
                    await asyncio.sleep(2) 
                    
                start_time = time.time()
                last_number_check_time = 0.0 # Waktu terakhir kita mengecek get_number_and_country

                while (time.time() - start_time) < duration:
                    
                    current_time = time.time()
                    
                    # Logika Pemeriksaan Nomor (setiap 1.0 detik)
                    # Hanya panggil Playwright jika sudah waktunya
                    if current_time - last_number_check_time >= check_number_interval:
                        number, country = await get_number_and_country(page)
                        last_number_check_time = current_time # Update waktu pengecekan
                        if number: break
                    
                    # Logika Update Progress Bar (setiap 0.5 detik)
                    # Progress bar harus selalu bergerak untuk feedback UI
                    current_step += 1
                    tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix))
                    
                    # Jeda untuk memastikan pembaruan terjadi setiap 0.5 detik
                    await asyncio.sleep(progress_update_interval) 
                    
                if number: break

            if not number:
                tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DI TEMUKAN. Coba lagi atau ganti range.")
                return 

            # 6. PENYIMPANAN & RESPON
            save_cache({"number": number, "country": country, "user_id": user_id, "time": time.time()})
            add_to_wait_list(number, user_id)
            last_used_range[user_id] = prefix 

            emoji = GLOBAL_COUNTRY_EMOJI.get(country, "🗺️") 
            msg = (
                "✅ The number is ready\n\n"
                f"📞 Number  : <code>{number}</code>\n"
                f"{emoji} COUNTRY : {country}\n"
                f"🏷️ Range   : <code>{prefix}</code>\n\n"
                "<b>🤖 Number available please use.</b>\n"
                "<b>Waiting for OTP....</b>"
            )

            inline_kb = {
                "inline_keyboard": [
                    [{"text": "🔄 Change Number", "callback_data": f"change_num:{prefix}"}],
                    [{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}]
                ]
            }

            # --- Pesan Akhir (Berhasil) ---
            tg_edit(user_id, msg_id, msg, reply_markup=inline_kb)

        except PlaywrightTimeoutError as pte:
            error_type = pte.__class__.__name__
            print(f"[ERROR PLAYWRIGHT TIMEOUT] Timeout pada navigasi/klik: {error_type} - {pte}")
            if msg_id: tg_edit(user_id, msg_id, f"❌ Timeout web ({error_type}). Web lambat atau tombol tidak ditemukan. Mohon coba lagi.")
                
        except Exception as e:
            error_type = e.__class__.__name__
            print(f"[ERROR FATAL DIBLOKIR] Proses Playwright Gagal Total: {error_type} - {e}")
            if msg_id: tg_edit(user_id, msg_id, f"❌ Terjadi kesalahan fatal ({error_type}). Mohon coba lagi atau hubungi admin.")
        
        # --- BLOK FINALLY: PASTIKAN TAB DITUTUP ---
        finally:
            if page:
                await page.close()
                print(f"[DEBUG] Tab untuk user {user_id} ditutup")


# --- LOOP UTAMA TELEGRAM ---
async def telegram_loop(browser):
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
                        welcome_message = (f"🥳HI!! {member_mention} WELCOME TO GRUP\nREADY TO RECEIVE SMS⁉️\n📞GET NUMBER IN BOT⤵️⤵️")
                        inline_kb = {"inline_keyboard": [[{"text": "📲 GET NUMBER", "url": BOT_USERNAME_LINK}]]}
                        tg_send(chat_id, welcome_message, reply_markup=inline_kb)
                    continue

                # --- ADMIN /add COMMAND ---
                if user_id == ADMIN_ID:
                    if text.startswith("/add"):
                        waiting_admin_input.add(user_id)
                        prompt_msg_text = "Silahkan kirim daftar range dalam format:\n\n<code>range > country</code>\n\nContoh:\n<code>23273XXX > SIERRA LEONE\n97798XXXX > NEPAL</code>"
                        msg_id = tg_send(user_id, prompt_msg_text)
                        if msg_id: pending_message[user_id] = msg_id
                        continue

                # --- ADMIN INPUT PROCESSING ---
                if user_id in waiting_admin_input:
                    waiting_admin_input.remove(user_id)
                    new_ranges = []
                    for line in text.strip().split('\n'):
                        if ' > ' in line:
                            parts = line.split(' > ', 1)
                            range_prefix = parts[0].strip()
                            country_name = parts[1].strip().upper() 
                            emoji = GLOBAL_COUNTRY_EMOJI.get(country_name, "🗺️") 
                            new_ranges.append({"range": range_prefix, "country": country_name, "emoji": emoji})
                    prompt_msg_id = pending_message.pop(user_id, None)
                    if new_ranges:
                        save_inline_ranges(new_ranges)
                        if prompt_msg_id: tg_edit(user_id, prompt_msg_id, f"✅ Berhasil menyimpan {len(new_ranges)} range ke inline.json.")
                    else:
                        if prompt_msg_id: tg_edit(user_id, prompt_msg_id, "❌ Format tidak valid atau tidak ada range yang ditemukan. Batalkan penambahan range.")
                    continue

                # --- PEMROSESAN INPUT RANGE MANUAL DARI USER ---
                if user_id in manual_range_input:
                    manual_range_input.remove(user_id) 
                    prefix = text.strip()
                    menu_msg_id = pending_message.pop(user_id, None)

                    if re.match(r"^\+?\d{3,15}[Xx*#]+$", prefix, re.IGNORECASE):
                        if menu_msg_id:
                            tg_edit(chat_id, menu_msg_id, get_progress_message(0, 0, prefix)) 
                        else:
                            menu_msg_id = tg_send(chat_id, get_progress_message(0, 0, prefix))

                        await process_user_input(browser, user_id, prefix, menu_msg_id)
                    else:
                        error_msg = "❌ Format Range tidak valid. Contoh format: <code>2327600XXX</code>. Silakan coba lagi."
                        if menu_msg_id:
                            tg_edit(chat_id, menu_msg_id, error_msg)
                        else:
                            tg_send(chat_id, error_msg)
                    continue
                # ----------------------------------------------------

                # --- /start COMMAND ---
                if text == "/start":
                    is_member = is_user_in_both_groups(user_id)
                    if is_member:
                        verified_users.add(user_id)
                        kb = {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}],[{"text": "👨‍💼 Admin", "url": "https://t.me/"}],]}
                        msg_text = (f"✅ Verifikasi Berhasil, {mention}!\n\nGunakan tombol di bawah:")
                        tg_send(user_id, msg_text, kb)
                    else:
                        kb = {"inline_keyboard": [[{"text": "📌 Gabung Grup 1", "url": GROUP_LINK_1}], [{"text": "📌 Gabung Grup 2", "url": GROUP_LINK_2}], [{"text": "✅ Verifikasi Ulang", "callback_data": "verify"}],]}
                        msg_text = (f"Halo {mention} 👋\nHarap gabung kedua grup di bawah untuk verifikasi:")
                        tg_send(user_id, msg_text, kb)
                    continue

            if "callback_query" in upd:
                cq = upd["callback_query"]
                user_id = cq["from"]["id"]
                data_cb = cq["data"]
                chat_id = cq["message"]["chat"]["id"]
                menu_msg_id = cq["message"]["message_id"]

                if data_cb == "verify":
                    if not is_user_in_both_groups(user_id):
                        kb = {"inline_keyboard": [[{"text": "📌 Gabung Grup 1", "url": GROUP_LINK_1}], [{"text": "📌 Gabung Grup 2", "url": GROUP_LINK_2}], [{"text": "✅ Verifikasi Ulang", "callback_data": "verify"}],]}
                        tg_edit(chat_id, menu_msg_id, "❌ Belum gabung kedua grup. Silakan join dulu.", kb)
                    else:
                        verified_users.add(user_id)
                        kb = {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}],[{"text": "👨‍💼 Admin", "url": "https://t.me/"}],]}
                        tg_edit(chat_id, menu_msg_id, "✅ Verifikasi Berhasil!\n\nGunakan tombol di bawah:", kb)
                    continue

                if data_cb == "getnum":
                    if user_id not in verified_users:
                        tg_edit(chat_id, menu_msg_id, "⚠️ Harap verifikasi dulu.")
                        continue
                    inline_ranges = load_inline_ranges()
                    if inline_ranges:
                        kb = generate_inline_keyboard(inline_ranges)
                        tg_edit(chat_id, menu_msg_id, f"<b>Get Number</b>\n\nSilahkan gunakan range di bawah untuk mendapatkan nomor.", kb)
                    else:
                        kb = {"inline_keyboard": [[{"text": "✍️ Input Manual Range", "callback_data": "manual_range"}]]}
                        tg_edit(chat_id, menu_msg_id, "❌ Belum ada Range yang tersedia otomatis. Silahkan gunakan Input Manual Range.", kb)
                    continue

                # --- PENANGANAN CALLBACK MANUAL RANGE ---
                if data_cb == "manual_range":
                    if user_id not in verified_users:
                        tg_edit(chat_id, menu_msg_id, "⚠️ Harap verifikasi dulu.")
                        continue
                    
                    manual_range_input.add(user_id)
                    prompt_msg_text = (
                        "<b>Input Manual Range</b>\n\n"
                        "Silahkan kirim Range anda, contohnya:\n"
                        "<code>2327600XXX</code>\n\n"
                        "<i>(Pastikan format range sudah benar)</i>"
                    )
                    tg_edit(chat_id, menu_msg_id, prompt_msg_text) 
                    pending_message[user_id] = menu_msg_id 
                    continue
                # --------------------------------------------------
                
                if data_cb.startswith("select_range:"):
                    if user_id not in verified_users:
                        tg_edit(chat_id, menu_msg_id, "⚠️ Harap verifikasi dulu.")
                        continue
                    prefix = data_cb.split(":")[1]
                    
                    current_step = 0
                    message = get_progress_message(current_step, 0, prefix)
                    tg_edit(chat_id, menu_msg_id, message) 

                    await process_user_input(browser, user_id, prefix, menu_msg_id) 
                    continue

                if data_cb.startswith("change_num:"):
                    if user_id not in verified_users:
                        tg_edit(chat_id, menu_msg_id, "⚠️ Harap verifikasi dulu.")
                        return
                    prefix = data_cb.split(":")[1]
                    if not prefix:
                        tg_edit(chat_id, menu_msg_id, "❌ Tidak ada range terakhir yang tersimpan. Silakan pilih range baru melalui /start.")
                        return
                    
                    current_step = 0
                    message = get_progress_message(current_step, 0, prefix)
                    tg_edit(chat_id, menu_msg_id, message)
                    
                    await process_user_input(browser, user_id, prefix, menu_msg_id) 
                    continue
                
        await asyncio.sleep(0.5)

def initialize_files():
    files = {CACHE_FILE: "[]", INLINE_RANGE_FILE: "[]", SMC_FILE: "[]"}
    for file, default_content in files.items():
        if not os.path.exists(file):
            with open(file, "w") as f:
                f.write(default_content)
    
    # BERSIHKAN WAIT LIST SAAT START
    if os.path.exists(WAIT_FILE):
        os.remove(WAIT_FILE)
        print(f"[INFO] File {WAIT_FILE} dibersihkan/dihapus saat startup.")
    with open(WAIT_FILE, "w") as f:
        f.write("[]")
    
    # HAPUS BAGIAN PEMBUATAN/PEMUATAN country.json
    if os.path.exists(COUNTRY_EMOJI_FILE):
        print(f"[INFO] Menghapus file {COUNTRY_EMOJI_FILE} yang sudah tidak terpakai.")
        os.remove(COUNTRY_EMOJI_FILE)


async def main():
    print("[INFO] Starting main bot (Telegram/Playwright)...")
    initialize_files()
    
    print("[INFO] Membersihkan pending updates dari Telegram API...")
    clear_pending_updates()
    
    print(f"[INFO] Memuat {len(GLOBAL_COUNTRY_EMOJI)} emoji negara dari hardcode.")

    sms_process = None
    try:
        sms_process = subprocess.Popen([sys.executable, "sms.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
        print(f"[INFO] Started sms.py process with PID: {sms_process.pid}")
    except Exception as e:
        print(f"[FATAL ERROR] Failed to start sms.py: {e}")

    browser = None
    try:
        async with async_playwright() as p:
            try:
                # Menghubungkan ke instance Chrome yang ada
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            except Exception as e:
                print(f"[ERROR] Gagal koneksi ke Chrome CDP: {e}")
                print("Pastikan Chrome berjalan dengan flag '--remote-debugging-port=9222' dan web target terbuka.")
                if sms_process and sms_process.poll() is None: sms_process.terminate()
                return

            # Cek dan buka minimal satu halaman untuk memastikan konteks pertama ada
            if not browser.contexts[0].pages:
                 page = await browser.contexts[0].new_page()
                 await page.goto(BASE_WEB_URL, wait_until='domcontentloaded')
                 print("[WARN] Membuka halaman Playwright awal di tab 1.")
            
            print("[OK] Connected to existing Chrome via CDP on port 9222")
            
            # Meneruskan objek 'browser'
            await asyncio.gather(
                telegram_loop(browser), 
            )

    except Exception as e:
        print(f"[FATAL ERROR] An unexpected error occurred: {e}")

    finally:
        if browser:
            pass 
        
        if sms_process and sms_process.poll() is None:
            sms_process.terminate()
            print("[INFO] Terminated sms.py process.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Bot dimatikan oleh pengguna (KeyboardInterrupt).")
    except Exception as e:
        print(f"[FATAL] Kesalahan utama: {e}")
