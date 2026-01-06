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
import math 

# --- ASYNCIO LOCK UNTUK ANTRIAN PLAYWRIGHT ---
playwright_lock = asyncio.Lock()
# ----------------------------------------------

# --- DATA GLOBAL EMOJI NEGARA ---
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
  "GREECE": "🇬🇷", "GRENADA": "🇬🇹", "GUATEMALA": "🇬🇹", "GUINEA": "🇬🇳", "GUINEA-BISSAU": "🇬🇼",
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

# --- KONFIGURASI PROGRESS BAR GLOBAL ---
MAX_BAR_LENGTH = 12 
FILLED_CHAR = "█"
EMPTY_CHAR = "░"

STATUS_MAP = {
    0:  "Menunggu di antrian sistem aktif..",
    1:  "Mengakses alamat target web aktif.",
    2:  "Menunggu pemuatan halaman web on..",
    3:  "Mengirim permintaan nomor baru go.",
    4:  "Memulai pencarian di tabel data..",
    5:  "Mencari nomor pada siklus satu run",
    8:  "Mencoba ulang pada siklus dua wait",
    12: "Nomor ditemukan memproses data fin",
    15: "Finalisasi..."
}

def get_progress_message(current_step, total_steps, prefix_range, num_count):
    """Menghasilkan pesan progress bar baru."""
    progress_ratio = min(current_step / 15, 1.0)
    filled_count = math.ceil(progress_ratio * MAX_BAR_LENGTH)
    empty_count = MAX_BAR_LENGTH - filled_count
    
    progress_bar = FILLED_CHAR * filled_count + EMPTY_CHAR * empty_count
    
    current_status = STATUS_MAP.get(current_step)
    if not current_status:
        if current_step < 5:
            current_status = STATUS_MAP[1]
        elif current_step < 8:
            current_status = STATUS_MAP[5]
        elif current_step < 12:
            current_status = STATUS_MAP[8]
        else:
            current_status = STATUS_MAP[12]

    return (
    f"<code>{current_status}</code>\n"
    f"<blockquote>Range: <code>{prefix_range}</code> | Jumlah: <code>{num_count}</code></blockquote>\n"
    f"<code>Load:</code> [{progress_bar}]"
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
BASE_WEB_URL = "https://x.mnitnetwork.com/mdashboard/getnum" 

# --- KONSTANTA FILE ---
USER_FILE = "user.json" 
CACHE_FILE = "cache.json"
INLINE_RANGE_FILE = "inline.json"
SMC_FILE = "smc.json"
WAIT_FILE = "wait.json"
COUNTRY_EMOJI_FILE = "country.json" 
BOT_USERNAME_LINK = "https://t.me/myzuraisgoodbot" 
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1" 
GROUP_LINK_2 = "https://t.me/zura14g" 

# --- VARIABEL GLOBAL ---
waiting_broadcast_input = set() 
broadcast_message = {} 

verified_users = set()
waiting_admin_input = set()
manual_range_input = set() 
pending_message = {}
sent_numbers = set()
last_used_range = {}


# --- FUNGSI UTILITAS MANAJEMEN FILE ---
# ... (load_users, save_users, load_cache, save_cache, is_in_cache, load_inline_ranges, save_inline_ranges, generate_inline_keyboard, load_wait_list, save_wait_list, add_to_wait_list tetap sama)
def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()

def save_users(user_id):
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        with open(USER_FILE, "w") as f:
            json.dump(list(users), f, indent=2)

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
    # Pastikan nomor di cache juga dinormalisasi untuk perbandingan
    normalized_number = normalize_number(number) 
    return any(normalize_number(entry["number"]) == normalized_number for entry in cache)

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
    
    keyboard.append([{"text": "Input Manual Range..🖊️", "callback_data": "manual_range"}])
    
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
    """Memastikan nomor selalu diawali dengan '+'."""
    normalized_number = str(number).strip().replace(" ", "").replace("-", "")
    if not normalized_number.startswith('+'):
        normalized_number = '+' + normalized_number
    return normalized_number
# ----------------------------------------------------


# --- FUNGSI UTILITAS TELEGRAM API ---
# ... (tg_send, tg_edit, tg_delete, tg_send_action, tg_get_updates, is_user_in_group, is_user_in_both_groups, clear_pending_updates, tg_broadcast, action_task tetap sama)
def tg_send(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{API}/sendMessage", json=data).json()
        if r.get("ok"):
            return r["result"]["message_id"]
        # print(f"[ERROR SEND] {r.get('description', 'Unknown Error')} for chat_id {chat_id}")
        return None
    except Exception as e:
        # print(f"[ERROR SEND REQUEST] {e}")
        return None

def tg_edit(chat_id, message_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{API}/editMessageText", json=data).json()
        if not r.get("ok"):
            if "message is not modified" not in r.get("description", ""):
                 pass # print(f"[ERROR EDIT] {r.get('description', 'Unknown Error')} for chat_id {chat_id}")
    except Exception as e:
        pass # print(f"[ERROR EDIT REQUEST] {e}")

def tg_delete(chat_id, message_id):
    data = {"chat_id": chat_id, "message_id": message_id}
    try:
        r = requests.post(f"{API}/deleteMessage", json=data).json()
        if not r.get("ok"):
             if "message to delete not found" not in r.get("description", ""):
                 pass # print(f"[ERROR DELETE] {r.get('description', 'Unknown Error')} for chat_id {chat_id}")
    except Exception as e:
        pass # print(f"[ERROR DELETE REQUEST] {e}")

def tg_send_action(chat_id, action="typing"):
    data = {"chat_id": chat_id, "action": action}
    try:
        requests.post(f"{API}/sendChatAction", data=data)
    except Exception as e:
        pass # print(f"[ERROR SEND ACTION] {e}")

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

async def tg_broadcast(message_text, admin_id):
    user_ids = list(load_users())
    success_count = 0
    fail_count = 0
    
    admin_msg_id = tg_send(admin_id, f"🔄 Memulai siaran ke **{len(user_ids)}** pengguna. Harap tunggu...")

    for i, user_id in enumerate(user_ids):
        if i % 10 == 0 and admin_msg_id:
             try:
                 tg_edit(admin_id, admin_msg_id, f"🔄 Siaran: **{i}/{len(user_ids)}** (Sukses: {success_count}, Gagal: {fail_count})")
             except:
                 pass 
        
        res = tg_send(user_id, message_text)
        if res:
            success_count += 1
        else:
            fail_count += 1
        await asyncio.sleep(0.05) 

    final_msg = (
        f"✅ Siaran Selesai!\n\n"
        f"👥 Total Pengguna: **{len(user_ids)}**\n"
        f"🟢 Berhasil Terkirim: **{success_count}**\n"
        f"🔴 Gagal Terkirim: **{fail_count}**"
    )
    if admin_msg_id:
        tg_edit(admin_id, admin_msg_id, final_msg)
    else:
        tg_send(admin_id, final_msg)

async def action_task(chat_id, action_interval=4.5):
    while True:
        tg_send_action(chat_id, action="typing") 
        await asyncio.sleep(action_interval) 

# --- FUNGSI PLAYWRIGHT ASYNC ---
async def get_number_and_country_from_row(row_selector, page):
    """
    Mengambil data (nomor dan negara) dari satu baris tabel 
    berdasarkan selektor CSS baris (misalnya 'tbody tr:first-child').
    """
    try:
        row = await page.query_selector(row_selector) 
        if not row: return None, None, None # Return 3 nilai (nomor, negara, status)

        # 1. MENGAMBIL NOMOR: span dengan kelas 'font-mono' di kolom pertama
        phone_el = await row.query_selector("td:nth-child(1) span.font-mono")
        number_raw = (await phone_el.inner_text()).strip() if phone_el else None
        
        number = normalize_number(number_raw) if number_raw else None
        
        if not number or is_in_cache(number): return None, None, None 
        
        # 2. MENGAMBIL STATUS: span di td pertama/div kedua
        status_el = await row.query_selector("td:nth-child(1) div:nth-child(2) span")
        status_text = (await status_el.inner_text()).strip().lower() if status_el else "unknown"
        
        # Abaikan jika status sudah final (success/failed)
        if "success" in status_text or "failed" in status_text: return None, None, None
        
        # 3. MENGAMBIL NEGARA: span dengan kelas 'text-slate-200' di td kedua
        country_el = await row.query_selector("td:nth-child(2) span.text-slate-200")
        country = (await country_el.inner_text()).strip().upper() if country_el else "UNKNOWN"

        if len(number) > 5: return number, country, status_text
        return None, None, None
        
    except Exception as e:
        # print(f"[ERROR PARSING ROW {row_selector}] Gagal memparsing data tabel: {e}")
        return None, None, None

async def process_user_input(browser, user_id, prefix, click_count, message_id_to_edit=None):
    """Memproses permintaan Get Number dengan jumlah klik (1 atau 3) yang ditentukan."""
    global GLOBAL_COUNTRY_EMOJI 
    global last_used_range 

    msg_id = message_id_to_edit if message_id_to_edit else pending_message.pop(user_id, None)
    page = None
    action_loop_task = None 
    
    num_to_fetch = click_count # Jumlah nomor yang dicari

    # --- Feedback Antrian ---
    if playwright_lock.locked():
        if not msg_id:
            msg_id = tg_send(user_id, get_progress_message(0, 0, prefix, num_to_fetch))
            if not msg_id: return
        else:
            tg_edit(user_id, msg_id, get_progress_message(0, 0, prefix, num_to_fetch))

    # --- Lock Utama Playwright ---
    async with playwright_lock:
        
        try:
            action_loop_task = asyncio.create_task(action_task(user_id))
            current_step = 0 
            
            if not msg_id:
                msg_id = tg_send(user_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
                if not msg_id: return
            
            context = browser.contexts[0]
            page = await context.new_page() 
            print(f"[DEBUG] Tab baru dibuka untuk user {user_id} (Count: {num_to_fetch})")
            
            # 1. NAVIGASI KE URL BARU
            NEW_URL = f"{BASE_WEB_URL}?range={prefix}"
            await page.goto(NEW_URL, wait_until='domcontentloaded', timeout=30000)
            current_step = 1 
            tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
            
            await asyncio.sleep(3) 
            current_step = 2 
            tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))

            # 2. TUNGGU TOMBOL SIAP DAN KLIK SEJUMLAH 'click_count'
            BUTTON_SELECTOR = "button:has-text('Get Number')" 
            await page.wait_for_selector(BUTTON_SELECTOR, state='visible', timeout=15000)
            
            for i in range(click_count):
                await page.click(BUTTON_SELECTOR, force=True)
                # Jeda sebentar antar klik
                await asyncio.sleep(0.5) 
            
            current_step = 3 
            tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
            
            # 3. TUNGGU PEMUATAN DAN PENCARIAN
            await asyncio.sleep(1) 
            current_step = 4 
            tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
            
            await asyncio.sleep(2) 
            
            # 4. MULAI MENCARI NOMOR (Siklus 1 & 2)
            delay_duration_round_1 = 6.0 
            delay_duration_round_2 = 6.0
            
            progress_update_interval = 0.2 
            check_number_interval = 0.5 
            
            found_numbers = [] # List untuk menyimpan 1 atau 3 nomor yang ditemukan
            
            for round_num, duration in enumerate([delay_duration_round_1, delay_duration_round_2]):
                
                if round_num == 0:
                    current_step = 5 
                elif round_num == 1:
                    if len(found_numbers) < num_to_fetch: 
                        # Klik ulang 1 kali jika belum dapat nomor sesuai target
                        await page.click(BUTTON_SELECTOR, force=True) 
                        await asyncio.sleep(3) # Tunggu lebih lama untuk retry
                        current_step = 8 
                
                start_time = time.time()
                last_number_check_time = 0.0 
                
                while (time.time() - start_time) < duration:
                    
                    current_time = time.time()
                    
                    if current_time - last_number_check_time >= check_number_interval:
                        
                        # Cek dari baris 1 hingga baris ke-N (sesuai num_to_fetch)
                        current_numbers = []
                        all_countries = set() # Untuk menyimpan negara yang ditemukan
                        
                        for i in range(1, num_to_fetch + 1):
                            row_selector = f"tbody tr:nth-child({i})"
                            number, country, status = await get_number_and_country_from_row(row_selector, page)
                            
                            if number and number not in [n['number'] for n in current_numbers]:
                                current_numbers.append({'number': number, 'country': country})
                                all_countries.add(country)

                        found_numbers = current_numbers
                        last_number_check_time = current_time 
                        
                        if len(found_numbers) >= num_to_fetch:
                            current_step = 12
                            break
                    
                    # Update progress
                    current_step += 1
                    tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
                    
                    await asyncio.sleep(progress_update_interval) 
                    
                if len(found_numbers) >= num_to_fetch: break

            # 5. PENYIMPANAN & RESPON
            
            if not found_numbers:
                tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DI TEMUKAN. Coba lagi atau ganti range.")
                return 

            # Ambil negara dari nomor pertama yang ditemukan (asumsi semua nomor dalam satu range berasal dari negara yang sama)
            main_country = found_numbers[0]['country'] if found_numbers else "UNKNOWN"

            if found_numbers:
                while current_step < 15:
                    current_step += 1
                    tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
                    await asyncio.sleep(0.1) 

            # Simpan semua nomor yang ditemukan ke cache dan wait list
            for entry in found_numbers:
                save_cache({"number": entry['number'], "country": entry['country'], "user_id": user_id, "time": time.time()})
                add_to_wait_list(entry['number'], user_id)
            
            last_used_range[user_id] = prefix 

            emoji = GLOBAL_COUNTRY_EMOJI.get(main_country, "🗺️") 
            
            # --- Pembentukan Pesan Output ---
            msg = "✅ The number is ready\n\n"
            
            if num_to_fetch == 1:
                num_data = found_numbers[0]
                msg += f"📞 Number  : <code>{num_data['number']}</code>\n"
            elif num_to_fetch == 3:
                for idx, num_data in enumerate(found_numbers[:3]):
                    msg += f"📞 Number {idx+1} : <code>{num_data['number']}</code>\n"
            
            msg += (
                f"{emoji} COUNTRY : {main_country}\n"
                f"🏷️ Range   : <code>{prefix}</code>\n\n"
                "<b>🤖 Number available please use.</b>\n"
                "<b>Waiting for OTP....</b>"
            )
            # --- Akhir Pembentukan Pesan Output ---


            # --- Keyboard Inline Baru ---
            inline_kb = {
                "inline_keyboard": [
                    [
                        {"text": "🔄 Change 1 Number", "callback_data": f"change_num:1:{prefix}"},
                        {"text": "🔄 Change 3 Number", "callback_data": f"change_num:3:{prefix}"}
                    ],
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
        
        # --- BLOK FINALLY: PASTIKAN TAB DITUTUP DAN ACTION DIBATALKAN ---
        finally:
            if page:
                await page.close()
                print(f"[DEBUG] Tab untuk user {user_id} ditutup")
            if action_loop_task:
                action_loop_task.cancel()
                print(f"[DEBUG] Chat action untuk user {user_id} dibatalkan")


# --- LOOP UTAMA TELEGRAM ---
async def telegram_loop(browser):
    global verified_users 
    global waiting_broadcast_input
    global broadcast_message
    
    verified_users = load_users()
    print(f"[INFO] Memuat {len(verified_users)} ID pengguna yang tersimpan.")

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

                
                # --- ADMIN COMMANDS ---
                if user_id == ADMIN_ID:
                    if text.startswith("/add"):
                        waiting_admin_input.add(user_id)
                        prompt_msg_text = "Silahkan kirim daftar range dalam format:\n\n<code>range > country</code>\n\nContoh:\n<code>23273XXX > SIERRA LEONE\n97798XXXX > NEPAL</code>"
                        msg_id = tg_send(user_id, prompt_msg_text)
                        if msg_id: pending_message[user_id] = msg_id
                        continue

                    elif text == "/info":
                        waiting_broadcast_input.add(user_id)
                        prompt_msg_text = "<b>Pesan Siaran</b>\n\nSilahkan kirim pesan apapun (teks, markdown, html) yang akan di sampaikan ke seluruh pengguna bot.\n\nKetik <code>.batal</code> untuk membatalkan."
                        msg_id = tg_send(user_id, prompt_msg_text)
                        if msg_id: broadcast_message[user_id] = msg_id 
                        continue

                # --- ADMIN INPUT PROCESSING (ADD RANGE) ---
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

                # --- ADMIN INPUT PROCESSING (BROADCAST) ---
                if user_id in waiting_broadcast_input:
                    waiting_broadcast_input.remove(user_id)
                    prompt_msg_id = broadcast_message.pop(user_id, None) 
                    
                    if text.strip().lower() == ".batal":
                        if prompt_msg_id: tg_edit(chat_id, prompt_msg_id, "❌ Siaran dibatalkan.")
                        else: tg_send(chat_id, "❌ Siaran dibatalkan.")
                        continue

                    if prompt_msg_id: tg_edit(chat_id, prompt_msg_id, "✅ Pesan diterima. Memulai siaran...")
                    else: tg_send(chat_id, "✅ Pesan diterima. Memulai siaran...")

                    await tg_broadcast(text, user_id)
                    continue
                
                # --- PEMROSESAN INPUT RANGE MANUAL DARI USER ---
                if user_id in manual_range_input:
                    manual_range_input.remove(user_id) 
                    prefix = text.strip()
                    menu_msg_id = pending_message.pop(user_id, None)
                    num_to_fetch = 1 # Default saat input manual, kita ambil 1 nomor

                    if re.match(r"^\+?\d{3,15}[Xx*#]+$", prefix, re.IGNORECASE):
                        if menu_msg_id:
                            tg_edit(chat_id, menu_msg_id, get_progress_message(0, 0, prefix, num_to_fetch)) 
                        else:
                            menu_msg_id = tg_send(chat_id, get_progress_message(0, 0, prefix, num_to_fetch))

                        await process_user_input(browser, user_id, prefix, num_to_fetch, menu_msg_id)
                    else:
                        error_msg = "❌ Format Range tidak valid. Contoh format: <code>2327600XXX</code>. Silakan coba lagi."
                        if menu_msg_id:
                            tg_edit(chat_id, menu_msg_id, error_msg)
                        else:
                            tg_send(chat_id, error_msg)
                    continue

                # --- /start COMMAND ---
                if text == "/start":
                    is_member = is_user_in_both_groups(user_id)
                    if is_member:
                        verified_users.add(user_id)
                        save_users(user_id) 
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

                # --- CALLBACK VERIFY ---
                if data_cb == "verify":
                    if not is_user_in_both_groups(user_id):
                        kb = {"inline_keyboard": [[{"text": "📌 Gabung Grup 1", "url": GROUP_LINK_1}], [{"text": "📌 Gabung Grup 2", "url": GROUP_LINK_2}], [{"text": "✅ Verifikasi Ulang", "callback_data": "verify"}],]}
                        tg_edit(chat_id, menu_msg_id, "❌ Belum gabung kedua grup. Silakan join dulu.", kb)
                    else:
                        verified_users.add(user_id)
                        save_users(user_id) 
                        kb = {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}],[{"text": "👨‍💼 Admin", "url": "https://t.me/"}],]}
                        tg_edit(chat_id, menu_msg_id, "✅ Verifikasi Berhasil!\n\nGunakan tombol di bawah:", kb)
                    continue
                
                # --- CALLBACK GETNUM ---
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

                # --- CALLBACK MANUAL RANGE ---
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
                
                # --- CALLBACK SELECT RANGE ---
                if data_cb.startswith("select_range:"):
                    if user_id not in verified_users:
                        tg_edit(chat_id, menu_msg_id, "⚠️ Harap verifikasi dulu.")
                        continue
                    prefix = data_cb.split(":")[1]
                    num_to_fetch = 1 # Default saat memilih range

                    current_step = 0
                    message = get_progress_message(current_step, 0, prefix, num_to_fetch)
                    tg_edit(chat_id, menu_msg_id, message) 

                    await process_user_input(browser, user_id, prefix, num_to_fetch, menu_msg_id) 
                    continue

                # --- CALLBACK CHANGE NUMBER (1 atau 3) ---
                if data_cb.startswith("change_num:"):
                    if user_id not in verified_users:
                        tg_edit(chat_id, menu_msg_id, "⚠️ Harap verifikasi dulu.")
                        return
                    
                    parts = data_cb.split(":")
                    if len(parts) != 3:
                        tg_edit(chat_id, menu_msg_id, "❌ Format tombol Change Number tidak valid.")
                        return

                    num_to_fetch = int(parts[1]) # 1 atau 3
                    prefix = parts[2]
                    
                    if not prefix:
                        tg_edit(chat_id, menu_msg_id, "❌ Tidak ada range terakhir yang tersimpan. Silakan pilih range baru melalui /start.")
                        return
                    
                    # Hapus pesan lama dan mulai proses baru
                    tg_delete(chat_id, menu_msg_id)
                    
                    await process_user_input(browser, user_id, prefix, num_to_fetch) 
                    continue
                
        await asyncio.sleep(0.5)

def initialize_files():
    files = {CACHE_FILE: "[]", INLINE_RANGE_FILE: "[]", SMC_FILE: "[]", USER_FILE: "[]"}
    for file, default_content in files.items():
        if not os.path.exists(file):
            with open(file, "w") as f:
                f.write(default_content)
            print(f"[INFO] File {file} dibuat.")

    if os.path.exists(WAIT_FILE):
        os.remove(WAIT_FILE)
        print(f"[INFO] File {WAIT_FILE} dibersihkan/dihapus saat startup.")
    with open(WAIT_FILE, "w") as f:
        f.write("[]")
    
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

            if not browser.contexts[0].pages:
                 page = await browser.contexts[0].new_page()
                 await page.goto(BASE_WEB_URL, wait_until='domcontentloaded')
                 print("[WARN] Membuka halaman Playwright awal di tab 1.")
            
            print("[OK] Connected to existing Chrome via CDP on port 9222")
            
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
