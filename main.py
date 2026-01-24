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
# Tambahan Variable Global untuk Tab Standby
shared_page = None 
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

# Step 1, 2, dan 15 dihapus dari visualisasi
STATUS_MAP = {
    0:  "Menunggu di antrian sistem aktif..",
    3:  "Mengirim permintaan nomor baru go.",
    4:  "Memulai pencarian di tabel data..",
    5:  "Mencari nomor pada siklus satu run",
    8:  "Mencoba ulang pada siklus dua wait",
    12: "Nomor ditemukan memproses data fin"
}

def get_progress_message(current_step, total_steps, prefix_range, num_count):
    """Menghasilkan pesan progress bar baru."""
    # Menyesuaikan pembagi ratio ke 12 karena step tertinggi sekarang 12
    progress_ratio = min(current_step / 12, 1.0)
    filled_count = math.ceil(progress_ratio * MAX_BAR_LENGTH)
    empty_count = MAX_BAR_LENGTH - filled_count
    
    progress_bar = FILLED_CHAR * filled_count + EMPTY_CHAR * empty_count
    
    current_status = STATUS_MAP.get(current_step)
    if not current_status:
        if current_step < 3:
            current_status = STATUS_MAP[0]
        elif current_step < 5:
            current_status = STATUS_MAP[4]
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
AKSES_GET10_FILE = "aksesget10.json"
BOT_USERNAME_LINK = "https://t.me/myzuraisgoodbot" 
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1" 
GROUP_LINK_2 = "https://t.me/zura14g" 

# --- VARIABEL GLOBAL ---
waiting_broadcast_input = set() 
broadcast_message = {} 

verified_users = set()
waiting_admin_input = set()
manual_range_input = set() 
get10_range_input = set()
pending_message = {}
sent_numbers = set()
last_used_range = {}


# --- FUNGSI UTILITAS MANAJEMEN FILE ---
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

def load_akses_get10():
    if os.path.exists(AKSES_GET10_FILE):
        with open(AKSES_GET10_FILE, "r") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()

def save_akses_get10(user_id_to_add):
    akses = load_akses_get10()
    akses.add(int(user_id_to_add))
    with open(AKSES_GET10_FILE, "w") as f:
        json.dump(list(akses), f, indent=2)

def has_get10_access(user_id):
    if user_id == ADMIN_ID:
        return True
    akses_list = load_akses_get10()
    return user_id in akses_list

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

def add_to_wait_list(number, user_id, username, first_name):
    """Menambahkan nomor ke wait.json. Pakai @username jika ada, jika tidak pakai Mention Name."""
    wait_list = load_wait_list()
    normalized_number = normalize_number(number)
    
    # Logika Penentuan Identitas
    if username and username != "None":
        # Format @username jika tersedia
        final_identity = f"@{username.replace('@', '')}"
    else:
        # Format HTML Mention Name jika username tidak ada
        final_identity = f'<a href="tg://user?id={user_id}">{first_name}</a>'
    
    # Hapus entri lama dengan nomor yang sama agar bersih
    wait_list = [item for item in wait_list if item['number'] != normalized_number]
    
    wait_list.append({
        "number": normalized_number, 
        "user_id": user_id, 
        "username": final_identity, 
        "timestamp": time.time()
    })
    save_wait_list(wait_list)

def normalize_number(number):
    """Memastikan nomor selalu diawali dengan '+'."""
    normalized_number = str(number).strip().replace(" ", "").replace("-", "")
    if not normalized_number.startswith('+') and normalized_number.isdigit():
        normalized_number = '+' + normalized_number
    return normalized_number
# ----------------------------------------------------


# --- FUNGSI UTILITAS TELEGRAM API ---
def tg_send(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{API}/sendMessage", json=data).json()
        if r.get("ok"):
            return r["result"]["message_id"]
        return None
    except Exception as e:
        return None

def tg_edit(chat_id, message_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{API}/editMessageText", json=data).json()
        if not r.get("ok"):
            if "message is not modified" not in r.get("description", ""):
                 pass 
    except Exception as e:
        pass 

def tg_delete(chat_id, message_id):
    data = {"chat_id": chat_id, "message_id": message_id}
    try:
        requests.post(f"{API}/deleteMessage", json=data).json()
    except Exception as e:
        pass 

def tg_send_action(chat_id, action="typing"):
    data = {"chat_id": chat_id, "action": action}
    try:
        requests.post(f"{API}/sendChatAction", data=data)
    except Exception as e:
        pass 

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

# --- FUNGSI PLAYWRIGHT ASYNC (OPTIMIZED) ---
async def get_number_and_country_from_row(row_selector, page):
    """
    Mengambil data (nomor dan negara) dari satu baris tabel 
    berdasarkan selektor CSS baris. Menggunakan locator Playwright yang lebih cepat.
    """
    try:
        row = page.locator(row_selector) 
        if not await row.is_visible(): return None, None, None 

        phone_el = row.locator("td:nth-child(1) span.font-mono")
        number_raw_list = await phone_el.all_inner_texts()
        number_raw = number_raw_list[0].strip() if number_raw_list else None
        
        number = normalize_number(number_raw) if number_raw else None
        
        if not number or is_in_cache(number): return None, None, None 
        
        # Ekstraksi Status
        status_el = row.locator("td:nth-child(1) div:nth-child(2) span")
        status_text_list = await status_el.all_inner_texts()
        status_text = status_text_list[0].strip().lower() if status_text_list else "unknown"

        if "success" in status_text or "failed" in status_text: return None, None, None
        
        # Ekstraksi Negara
        country_el = row.locator("td:nth-child(2) span.text-slate-200")
        country_list = await country_el.all_inner_texts()
        country = country_list[0].strip().upper() if country_list else "UNKNOWN"

        if number and len(number) > 5: return number, country, status_text
        return None, None, None
        
    except Exception as e:
        return None, None, None

async def get_all_numbers_parallel(page, num_to_fetch):
    """
    Mengambil data dari beberapa baris secara paralel menggunakan 
    asyncio.gather untuk memanggil fungsi ekstraksi Playwright secara bersamaan.
    """
    tasks = []
    # Loop disesuaikan agar bisa mengambil lebih banyak nomor (hingga 10+)
    for i in range(1, num_to_fetch + 5): 
        row_selector = f"tbody tr:nth-child({i})"
        tasks.append(get_number_and_country_from_row(row_selector, page))
    
    results = await asyncio.gather(*tasks)
    
    current_numbers = []
    for number, country, status in results:
        if number and number not in [n['number'] for n in current_numbers]:
            current_numbers.append({'number': number, 'country': country})

    return current_numbers


async def process_user_input(browser, user_id, prefix, click_count, username_tg, first_name_tg, message_id_to_edit=None):
    """Memproses permintaan Get Number dengan jumlah klik yang ditentukan."""
    global GLOBAL_COUNTRY_EMOJI 
    global last_used_range 
    global shared_page

    msg_id = message_id_to_edit if message_id_to_edit else pending_message.pop(user_id, None)
    action_loop_task = None 
    num_to_fetch = click_count 

    if playwright_lock.locked():
        if not msg_id:
            msg_id = tg_send(user_id, get_progress_message(0, 0, prefix, num_to_fetch))
            if not msg_id: return
        else:
            tg_edit(user_id, msg_id, get_progress_message(0, 0, prefix, num_to_fetch))

    async with playwright_lock:
        try:
            action_loop_task = asyncio.create_task(action_task(user_id))
            current_step = 0 
            start_operation_time = time.time()
            
            if not msg_id:
                msg_id = tg_send(user_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
                if not msg_id: return
            
            # --- LOGIKA TAB STANDBY ---
            if not shared_page:
                context = browser.contexts[0]
                shared_page = await context.new_page()
                await shared_page.goto(BASE_WEB_URL, wait_until='domcontentloaded')

            # --- INPUT RANGE ASLI ---
            INPUT_SELECTOR = "input[name='numberrange']"
            await shared_page.wait_for_selector(INPUT_SELECTOR, state='visible', timeout=10000)
            await shared_page.fill(INPUT_SELECTOR, "")
            await shared_page.fill(INPUT_SELECTOR, prefix)

            # Step 1 & 2 di proses tapi visual di skip lewat status map di atas
            current_step = 1 
            # tg_edit visual di skip
            
            await asyncio.sleep(0.5) 
            current_step = 2 
            # tg_edit visual di skip

            BUTTON_SELECTOR = "button:has-text('Get Number')" 
            await shared_page.wait_for_selector(BUTTON_SELECTOR, state='visible', timeout=10000) 
            
            for i in range(click_count):
                await shared_page.click(BUTTON_SELECTOR, force=True)
            
            current_step = 3 
            tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
            
            await asyncio.sleep(0.5) 
            current_step = 4 
            tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
            
            await asyncio.sleep(1) 
            
            delay_duration_round_1 = 5.0 # Ditambah sedikit agar stabil untuk 10 nomor
            delay_duration_round_2 = 5.0
            check_number_interval = 0.25 
            found_numbers = [] 
            
            for round_num, duration in enumerate([delay_duration_round_1, delay_duration_round_2]):
                if round_num == 0:
                    current_step = 5 
                elif round_num == 1:
                    if len(found_numbers) < num_to_fetch: 
                        await shared_page.click(BUTTON_SELECTOR, force=True) 
                        await asyncio.sleep(1.5) 
                        current_step = 8 
                
                start_time = time.time()
                last_number_check_time = 0.0 
                
                while (time.time() - start_time) < duration:
                    current_time = time.time()
                    if current_time - last_number_check_time >= check_number_interval:
                        current_numbers = await get_all_numbers_parallel(shared_page, num_to_fetch)
                        found_numbers = current_numbers
                        last_number_check_time = current_time 
                        if len(found_numbers) >= num_to_fetch:
                            current_step = 12
                            break
                    
                    # Target step maksimal 12 agar bar pas
                    target_step = int(12 * (time.time() - start_operation_time) / (delay_duration_round_1 + delay_duration_round_2 + 4))
                    if target_step > current_step and target_step <= 12:
                         current_step = target_step
                         tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
                    await asyncio.sleep(0.05) 
                    
                if len(found_numbers) >= num_to_fetch: break
            
            if not found_numbers:
                tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DI TEMUKAN. Coba lagi atau ganti range.")
                return 

            main_country = found_numbers[0]['country'] if found_numbers else "UNKNOWN"

            # Step 15 Finalisasi visual di skip
            if found_numbers:
                current_step = 12
                tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))

            # MODIFIKASI: Simpan ke wait.json dengan username/mention
            for entry in found_numbers:
                save_cache({"number": entry['number'], "country": entry['country'], "user_id": user_id, "time": time.time()})
                add_to_wait_list(entry['number'], user_id, username_tg, first_name_tg)
            
            last_used_range[user_id] = prefix 
            emoji = GLOBAL_COUNTRY_EMOJI.get(main_country, "🗺️") 
            
            # --- MODIFIKASI FORMAT OUTPUT KHUSUS /get10 ---
            if num_to_fetch == 10:
                msg = "✅The number is already.\n\n<code>"
                for entry in found_numbers[:10]:
                    msg += f"{entry['number']}\n"
                msg += "</code>"
                # Tanpa label Negara/Range di bawah list nomor sesuai permintaan user
            else:
                msg = "✅ The number is ready\n\n"
                if num_to_fetch == 1:
                    num_data = found_numbers[0]
                    msg += f"📞 Number  : <code>{num_data['number']}</code>\n"
                else:
                    for idx, num_data in enumerate(found_numbers[:num_to_fetch]):
                        msg += f"📞 Number {idx+1} : <code>{num_data['number']}</code>\n"
                
                msg += (
                    f"{emoji} COUNTRY : {main_country}\n"
                    f"🏷️ Range   : <code>{prefix}</code>\n\n"
                    "<b>🤖 Number available please use, Waiting for OTP</b>\n"
                )

            inline_kb = {
                "inline_keyboard": [
                    [{"text": "🔄 Change 1 Number", "callback_data": f"change_num:1:{prefix}"}],
                    [{"text": "🔄 Change 3 Number", "callback_data": f"change_num:3:{prefix}"}],
                    [{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}, {"text": "🌐 Change Range", "callback_data": "getnum"}]
                ]
            }

            tg_edit(user_id, msg_id, msg, reply_markup=inline_kb)

        except PlaywrightTimeoutError:
            if msg_id: tg_edit(user_id, msg_id, "❌ Timeout web. Web lambat atau tombol tidak ditemukan. Mohon coba lagi.")
        except Exception as e:
            if msg_id: tg_edit(user_id, msg_id, f"❌ Terjadi kesalahan fatal ({type(e).__name__}). Mohon coba lagi.")
        finally:
            if action_loop_task: action_loop_task.cancel()


# --- LOOP UTAMA TELEGRAM ---
async def telegram_loop(browser):
    global verified_users 
    global waiting_broadcast_input
    global broadcast_message
    
    verified_users = load_users()
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
                username_tg = msg["from"].get("username") # Simpan username
                mention = f"<a href='tg://user?id={user_id}'>{first_name}</a>"
                text = msg.get("text", "")

                if user_id == ADMIN_ID:
                    if text.startswith("/add"):
                        waiting_admin_input.add(user_id)
                        prompt_msg_text = "Silahkan kirim daftar range dalam format:\n\n<code>range > country</code>\n\nContoh:\n<code>23273XXX > SIERRA LEONE</code>"
                        msg_id = tg_send(user_id, prompt_msg_text)
                        if msg_id: pending_message[user_id] = msg_id
                        continue
                    elif text == "/info":
                        waiting_broadcast_input.add(user_id)
                        prompt_msg_text = "<b>Pesan Siaran</b>\n\nKirim pesan yang ingin disiarkan. Ketik <code>.batal</code> untuk batal."
                        msg_id = tg_send(user_id, prompt_msg_text)
                        if msg_id: broadcast_message[user_id] = msg_id 
                        continue
                    # --- FITUR BERI AKSES get10 ---
                    elif text.startswith("/get10akses "):
                        try:
                            target_id = text.split(" ")[1]
                            save_akses_get10(target_id)
                            tg_send(user_id, f"✅ User <code>{target_id}</code> berhasil diberi akses /get10.")
                        except:
                            tg_send(user_id, "❌ Gagal. Gunakan format: <code>/get10akses ID_USER</code>")
                        continue

                # --- FITUR /get10 (ADMIN & USER TERAKSES) ---
                if text == "/get10":
                    if has_get10_access(user_id):
                        get10_range_input.add(user_id)
                        msg_id = tg_send(user_id, "kirim range contoh 225071606XXX")
                        if msg_id: pending_message[user_id] = msg_id
                    else:
                        tg_send(user_id, "❌ Anda tidak memiliki akses untuk perintah ini.")
                    continue

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
                        tg_edit(user_id, prompt_msg_id, f"✅ Berhasil menyimpan {len(new_ranges)} range.")
                    else:
                        tg_edit(user_id, prompt_msg_id, "❌ Format tidak valid.")
                    continue

                if user_id in waiting_broadcast_input:
                    waiting_broadcast_input.remove(user_id)
                    prompt_msg_id = broadcast_message.pop(user_id, None) 
                    if text.strip().lower() == ".batal":
                        tg_edit(chat_id, prompt_msg_id, "❌ Siaran dibatalkan.")
                        continue
                    tg_edit(chat_id, prompt_msg_id, "✅ Memulai siaran...")
                    await tg_broadcast(text, user_id)
                    continue

                # --- PROSES INPUT UNTUK /get10 ---
                if user_id in get10_range_input:
                    get10_range_input.remove(user_id)
                    prefix = text.strip()
                    menu_msg_id = pending_message.pop(user_id, None)
                    is_manual_format = re.match(r"^\+?\d{3,15}[Xx*#]+$", prefix, re.IGNORECASE)
                    if is_manual_format:
                        if not menu_msg_id: menu_msg_id = tg_send(chat_id, get_progress_message(0, 0, prefix, 10))
                        else: tg_edit(chat_id, menu_msg_id, get_progress_message(0, 0, prefix, 10))
                        await process_user_input(browser, user_id, prefix, 10, username_tg, first_name, menu_msg_id)
                    else:
                        tg_send(chat_id, "❌ Format Range tidak valid.")
                    continue
                
                is_manual_format = re.match(r"^\+?\d{3,15}[Xx*#]+$", text.strip(), re.IGNORECASE)
                if user_id in manual_range_input or (user_id in verified_users and is_manual_format):
                    if user_id in manual_range_input: manual_range_input.remove(user_id) 
                    prefix = text.strip()
                    menu_msg_id = pending_message.pop(user_id, None)
                    if is_manual_format:
                        if not menu_msg_id: menu_msg_id = tg_send(chat_id, get_progress_message(0, 0, prefix, 1))
                        else: tg_edit(chat_id, menu_msg_id, get_progress_message(0, 0, prefix, 1))
                        await process_user_input(browser, user_id, prefix, 1, username_tg, first_name, menu_msg_id)
                    else:
                        tg_send(chat_id, "❌ Format Range tidak valid.")
                    continue

                if text == "/start":
                    if is_user_in_both_groups(user_id):
                        verified_users.add(user_id)
                        save_users(user_id) 
                        kb = {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}],[{"text": "👨‍💼 Admin", "url": "https://t.me/"}],]}
                        tg_send(user_id, f"✅ Verifikasi Berhasil, {mention}!", kb)
                    else:
                        kb = {"inline_keyboard": [[{"text": "📌 Gabung Grup 1", "url": GROUP_LINK_1}], [{"text": "📌 Gabung Grup 2", "url": GROUP_LINK_2}], [{"text": "✅ Verifikasi Ulang", "callback_data": "verify"}],]}
                        tg_send(user_id, f"Halo {mention} 👋\nHarap gabung kedua grup di bawah untuk verifikasi:", kb)
                    continue

            if "callback_query" in upd:
                cq = upd["callback_query"]
                user_id = cq["from"]["id"]
                data_cb = cq["data"]
                chat_id = cq["message"]["chat"]["id"]
                menu_msg_id = cq["message"]["message_id"]
                first_name_tg = cq["from"].get("first_name", "User")
                username_tg = cq["from"].get("username")

                if data_cb == "verify":
                    if not is_user_in_both_groups(user_id):
                        kb = {"inline_keyboard": [[{"text": "📌 Gabung Grup 1", "url": GROUP_LINK_1}], [{"text": "📌 Gabung Grup 2", "url": GROUP_LINK_2}], [{"text": "✅ Verifikasi Ulang", "callback_data": "verify"}],]}
                        tg_edit(chat_id, menu_msg_id, "❌ Belum gabung kedua grup.", kb)
                    else:
                        verified_users.add(user_id)
                        save_users(user_id) 
                        kb = {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}],[{"text": "👨‍💼 Admin", "url": "https://t.me/"}],]}
                        tg_edit(chat_id, menu_msg_id, "✅ Verifikasi Berhasil!", kb)
                    continue
                
                if data_cb == "getnum":
                    if user_id not in verified_users:
                        tg_edit(chat_id, menu_msg_id, "⚠️ Harap verifikasi dulu.")
                        continue
                    inline_ranges = load_inline_ranges()
                    kb = generate_inline_keyboard(inline_ranges) if inline_ranges else {"inline_keyboard": [[{"text": "✍️ Input Manual Range", "callback_data": "manual_range"}]]}
                    tg_edit(chat_id, menu_msg_id, "<b>Get Number</b>\n\nSilahkan pilih range atau input manual.", kb)
                    continue

                if data_cb == "manual_range":
                    if user_id not in verified_users: continue
                    manual_range_input.add(user_id)
                    tg_edit(chat_id, menu_msg_id, "<b>Input Manual Range</b>\n\nKirim Range anda, contoh: <code>2327600XXX</code>") 
                    pending_message[user_id] = menu_msg_id 
                    continue
                
                if data_cb.startswith("select_range:"):
                    if user_id not in verified_users: continue
                    prefix = data_cb.split(":")[1]
                    tg_edit(chat_id, menu_msg_id, get_progress_message(0, 0, prefix, 1)) 
                    await process_user_input(browser, user_id, prefix, 1, username_tg, first_name_tg, menu_msg_id) 
                    continue

                if data_cb.startswith("change_num:"):
                    if user_id not in verified_users: return
                    parts = data_cb.split(":")
                    num_to_fetch = int(parts[1]) 
                    prefix = parts[2]
                    tg_delete(chat_id, menu_msg_id)
                    await process_user_input(browser, user_id, prefix, num_to_fetch, username_tg, first_name_tg) 
                    continue
                
        await asyncio.sleep(0.05) 

# --- TASK MONITORING KADALUARSA ---
async def expiry_monitor_task():
    while True:
        try:
            wait_list = load_wait_list()
            current_time = time.time()
            updated_list = []
            for item in wait_list:
                if current_time - item['timestamp'] > 1200: # 20 Menit
                    msg_id = tg_send(item['user_id'], f"⚠️ Nomor <code>{item['number']}</code> telah kadaluarsa.")
                    if msg_id: asyncio.create_task(delayed_delete(item['user_id'], msg_id, 30))
                else:
                    updated_list.append(item)
            save_wait_list(updated_list)
        except: pass
        await asyncio.sleep(10)

async def delayed_delete(chat_id, message_id, delay):
    await asyncio.sleep(delay)
    tg_delete(chat_id, message_id)

def initialize_files():
    files = {CACHE_FILE: "[]", INLINE_RANGE_FILE: "[]", SMC_FILE: "[]", USER_FILE: "[]", WAIT_FILE: "[]", AKSES_GET10_FILE: "[]"}
    for file, default_content in files.items():
        if not os.path.exists(file):
            with open(file, "w") as f: f.write(default_content)

async def main():
    global shared_page
    print("[INFO] Starting main bot...")
    initialize_files()
    clear_pending_updates()
    sms_process = None
    try:
        sms_process = subprocess.Popen([sys.executable, "sms.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
    except: pass

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            
            # --- PERSYARATAN: BUAT TAB STANDBY DI AWAL ---
            context = browser.contexts[0]
            shared_page = await context.new_page()
            await shared_page.goto(BASE_WEB_URL, wait_until='domcontentloaded')
            
            await asyncio.gather(telegram_loop(browser), expiry_monitor_task())
    except Exception as e:
        print(f"[FATAL ERROR] {e}")
    finally:
        if sms_process: sms_process.terminate()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Bot dimatikan.")
