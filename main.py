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

STATUS_MAP = {
    0:  "Menunggu di antrian sistem aktif..",
    3:  "Mengirim permintaan nomor baru go.",
    4:  "Memulai pencarian di tabel data..",
    5:  "Mencari nomor pada siklus satu run",
    8:  "Mencoba ulang pada siklus dua wait",
    12: "Nomor ditemukan memproses data fin"
}

def get_progress_message(current_step, total_steps, prefix_range, num_count):
    progress_ratio = min(current_step / 12, 1.0)
    filled_count = math.ceil(progress_ratio * MAX_BAR_LENGTH)
    empty_count = MAX_BAR_LENGTH - filled_count
    progress_bar = FILLED_CHAR * filled_count + EMPTY_CHAR * empty_count
    current_status = STATUS_MAP.get(current_step)
    if not current_status:
        if current_step < 3: current_status = STATUS_MAP[0]
        elif current_step < 5: current_status = STATUS_MAP[4]
        elif current_step < 8: current_status = STATUS_MAP[5]
        elif current_step < 12: current_status = STATUS_MAP[8]
        else: current_status = STATUS_MAP[12]
    return (
    f"<code>{current_status}</code>\n"
    f"<blockquote>Range: <code>{prefix_range}</code> | Jumlah: <code>{num_count}</code></blockquote>\n"
    f"<code>Load:</code> [{progress_bar}]"
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    GROUP_ID_1 = int(os.getenv("GROUP_ID_1"))
    GROUP_ID_2 = int(os.getenv("GROUP_ID_2"))
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError) as e:
    print(f"[FATAL] Config Error: {e}")
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
PROFIL_FILE = "profil.json"
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
waiting_dana_input = set()

# --- FUNGSI PROFIL & SALDO ---
def load_profil():
    if os.path.exists(PROFIL_FILE):
        with open(PROFIL_FILE, "r") as f:
            try: return json.load(f)
            except: return {}
    return {}

def save_profil(data):
    with open(PROFIL_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user_profil(user_id, name, username):
    profils = load_profil()
    u_id = str(user_id)
    if u_id not in profils:
        profils[u_id] = {
            "id": user_id,
            "nama": name,
            "username": f"@{username}" if username else "None",
            "dana": "Belum diatur",
            "a_n": "-",
            "balance": 0.0,
            "otp_total": 0,
            "otp_hari_ini": 0,
            "last_otp_date": time.strftime("%Y-%m-%d")
        }
        save_profil(profils)
    
    # Reset daily OTP if date changed
    today = time.strftime("%Y-%m-%d")
    if profils[u_id].get("last_otp_date") != today:
        profils[u_id]["otp_hari_ini"] = 0
        profils[u_id]["last_otp_date"] = today
        save_profil(profils)
        
    return profils[u_id]

def update_user_balance(user_id, amount_to_add):
    profils = load_profil()
    u_id = str(user_id)
    if u_id in profils:
        old_bal = profils[u_id]["balance"]
        profils[u_id]["balance"] += amount_to_add
        profils[u_id]["otp_total"] += 1
        profils[u_id]["otp_hari_ini"] += 1
        save_profil(profils)
        return old_bal, profils[u_id]["balance"]
    return 0.0, 0.0

# --- FUNGSI UTILITAS MANAJEMEN FILE ---
def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            try: return set(json.load(f))
            except: return set()
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
            try: return json.load(f)
            except: return []
    return []

def save_cache(number_entry):
    cache = load_cache()
    if len(cache) >= 1000: cache.pop(0) 
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
            try: return json.load(f)
            except: return []
    return []

def save_inline_ranges(ranges):
    with open(INLINE_RANGE_FILE, "w") as f:
        json.dump(ranges, f, indent=2)

def load_akses_get10():
    if os.path.exists(AKSES_GET10_FILE):
        with open(AKSES_GET10_FILE, "r") as f:
            try: return set(json.load(f))
            except: return set()
    return set()

def save_akses_get10(user_id_to_add):
    akses = load_akses_get10()
    akses.add(int(user_id_to_add))
    with open(AKSES_GET10_FILE, "w") as f:
        json.dump(list(akses), f, indent=2)

def has_get10_access(user_id):
    if user_id == ADMIN_ID: return True
    akses_list = load_akses_get10()
    return user_id in akses_list

def generate_inline_keyboard(ranges):
    # Modified to Vertical layout 1x10
    keyboard = []
    for item in ranges:
        service = item.get('service', 'WA')
        text = f"{item['emoji']} {item['country']} {service}"
        callback_data = f"select_range:{item['range']}"
        keyboard.append([{"text": text, "callback_data": callback_data}])
    
    keyboard.append([{"text": "Input Manual Range..🖊️", "callback_data": "manual_range"}])
    return {"inline_keyboard": keyboard}

def load_wait_list():
    if os.path.exists(WAIT_FILE):
        with open(WAIT_FILE, "r") as f:
            try: return json.load(f)
            except: return []
    return []

def save_wait_list(data):
    with open(WAIT_FILE, "w") as f:
        json.dump(data, f, indent=2)

def add_to_wait_list(number, user_id, username, first_name):
    wait_list = load_wait_list()
    normalized_number = normalize_number(number)
    if username and username != "None":
        final_identity = f"@{username.replace('@', '')}"
    else:
        final_identity = f'<a href="tg://user?id={user_id}">{first_name}</a>'
    wait_list = [item for item in wait_list if item['number'] != normalized_number]
    wait_list.append({
        "number": normalized_number, 
        "user_id": user_id, 
        "username": final_identity, 
        "timestamp": time.time()
    })
    save_wait_list(wait_list)

def normalize_number(number):
    normalized_number = str(number).strip().replace(" ", "").replace("-", "")
    if not normalized_number.startswith('+') and normalized_number.isdigit():
        normalized_number = '+' + normalized_number
    return normalized_number

# --- FUNGSI UTILITAS TELEGRAM API ---
def tg_send(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup: data["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{API}/sendMessage", json=data).json()
        if r.get("ok"): return r["result"]["message_id"]
    except: pass
    return None

def tg_edit(chat_id, message_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup: data["reply_markup"] = reply_markup
    try: requests.post(f"{API}/editMessageText", json=data)
    except: pass 

def tg_delete(chat_id, message_id):
    try: requests.post(f"{API}/deleteMessage", json={"chat_id": chat_id, "message_id": message_id})
    except: pass 

def tg_get_updates(offset):
    try: return requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 5}).json()
    except: return {"ok": True, "result": []}

def is_user_in_group(user_id, group_id):
    try:
        r = requests.get(f"{API}/getChatMember", params={"chat_id": group_id, "user_id": user_id}).json()
        return r.get("ok") and r["result"]["status"] in ["member", "administrator", "creator"]
    except: return False

def is_user_in_both_groups(user_id):
    return is_user_in_group(user_id, GROUP_ID_1) and is_user_in_group(user_id, GROUP_ID_2)

def clear_pending_updates():
    try:
        r = requests.get(f"{API}/getUpdates", params={"offset": -1, "timeout": 1}).json()
        if r.get("ok") and r.get("result"):
            last_update_id = r["result"][-1]["update_id"]
            requests.get(f"{API}/getUpdates", params={"offset": last_update_id + 1, "timeout": 1})
    except: pass

async def tg_broadcast(message_text, admin_id):
    user_ids = list(load_users())
    success_count = 0
    fail_count = 0
    admin_msg_id = tg_send(admin_id, f"🔄 Memulai siaran ke **{len(user_ids)}** pengguna...")
    for i, user_id in enumerate(user_ids):
        res = tg_send(user_id, message_text)
        if res: success_count += 1
        else: fail_count += 1
        await asyncio.sleep(0.05) 
    tg_edit(admin_id, admin_msg_id, f"✅ Siaran Selesai!\n🟢 Sukses: {success_count}\n🔴 Gagal: {fail_count}")

async def action_task(chat_id):
    while True:
        requests.post(f"{API}/sendChatAction", data={"chat_id": chat_id, "action": "typing"})
        await asyncio.sleep(4.5) 

# --- PLAYWRIGHT LOGIC ---
async def get_number_and_country_from_row(row_selector, page):
    try:
        row = page.locator(row_selector) 
        if not await row.is_visible(): return None, None, None 
        phone_el = row.locator("td:nth-child(1) span.font-mono")
        number_raw_list = await phone_el.all_inner_texts()
        number_raw = number_raw_list[0].strip() if number_raw_list else None
        number = normalize_number(number_raw) if number_raw else None
        if not number or is_in_cache(number): return None, None, None 
        status_el = row.locator("td:nth-child(1) div:nth-child(2) span")
        status_text_list = await status_el.all_inner_texts()
        status_text = status_text_list[0].strip().lower() if status_text_list else "unknown"
        if "success" in status_text or "failed" in status_text: return None, None, None
        country_el = row.locator("td:nth-child(2) span.text-slate-200")
        country_list = await country_el.all_inner_texts()
        country = country_list[0].strip().upper() if country_list else "UNKNOWN"
        if number and len(number) > 5: return number, country, status_text
        return None, None, None
    except: return None, None, None

async def get_all_numbers_parallel(page, num_to_fetch):
    tasks = []
    for i in range(1, num_to_fetch + 5): 
        tasks.append(get_number_and_country_from_row(f"tbody tr:nth-child({i})", page))
    results = await asyncio.gather(*tasks)
    current_numbers = []
    for number, country, status in results:
        if number and number not in [n['number'] for n in current_numbers]:
            current_numbers.append({'number': number, 'country': country})
    return current_numbers

async def process_user_input(browser, user_id, prefix, click_count, username_tg, first_name_tg, message_id_to_edit=None):
    global shared_page
    msg_id = message_id_to_edit if message_id_to_edit else pending_message.pop(user_id, None)
    action_loop_task = None 
    num_to_fetch = click_count 
    if playwright_lock.locked():
        if not msg_id: msg_id = tg_send(user_id, get_progress_message(0, 0, prefix, num_to_fetch))
        else: tg_edit(user_id, msg_id, get_progress_message(0, 0, prefix, num_to_fetch))
    async with playwright_lock:
        try:
            action_loop_task = asyncio.create_task(action_task(user_id))
            current_step = 0 
            start_operation_time = time.time()
            if not msg_id:
                msg_id = tg_send(user_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
            if not shared_page:
                shared_page = await browser.contexts[0].new_page()
                await shared_page.goto(BASE_WEB_URL, wait_until='domcontentloaded')
            await shared_page.fill("input[name='numberrange']", prefix)
            current_step = 3
            tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
            for _ in range(click_count):
                await shared_page.click("button:has-text('Get Number')", force=True)
            current_step = 5
            tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
            found_numbers = []
            for round_num in range(2):
                if round_num == 1 and len(found_numbers) < num_to_fetch:
                    await shared_page.click("button:has-text('Get Number')", force=True)
                    current_step = 8
                    tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
                start_t = time.time()
                while (time.time() - start_t) < 5.0:
                    found_numbers = await get_all_numbers_parallel(shared_page, num_to_fetch)
                    if len(found_numbers) >= num_to_fetch: break
                    await asyncio.sleep(0.5)
                if len(found_numbers) >= num_to_fetch: break
            
            if not found_numbers:
                tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DI TEMUKAN. Coba lagi atau ganti range.")
                return 

            current_step = 12
            tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))

            for entry in found_numbers:
                save_cache({"number": entry['number'], "country": entry['country'], "user_id": user_id, "time": time.time()})
                add_to_wait_list(entry['number'], user_id, username_tg, first_name_tg)
            
            last_used_range[user_id] = prefix 
            main_country = found_numbers[0]['country']
            emoji = GLOBAL_COUNTRY_EMOJI.get(main_country, "🗺️") 
            
            if num_to_fetch == 10:
                msg = "✅The number is already.\n\n<code>"
                for entry in found_numbers[:10]: msg += f"{entry['number']}\n"
                msg += "</code>"
            else:
                msg = "✅ The number is ready\n\n"
                if num_to_fetch == 1:
                    msg += f"📞 Number  : <code>{found_numbers[0]['number']}</code>\n"
                else:
                    for idx, n in enumerate(found_numbers[:num_to_fetch]):
                        msg += f"📞 Number {idx+1} : <code>{n['number']}</code>\n"
                msg += f"{emoji} COUNTRY : {main_country}\n🏷️ Range   : <code>{prefix}</code>\n\n<b>🤖 Number available please use, Waiting for OTP</b>\n"

            inline_kb = {"inline_keyboard": [
                [{"text": "🔄 Change 1 Number", "callback_data": f"change_num:1:{prefix}"}],
                [{"text": "🔄 Change 3 Number", "callback_data": f"change_num:3:{prefix}"}],
                [{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}, {"text": "🌐 Change Range", "callback_data": "getnum"}]
            ]}
            tg_edit(user_id, msg_id, msg, reply_markup=inline_kb)
        except Exception as e:
            if msg_id: tg_edit(user_id, msg_id, f"❌ Error: {e}")
        finally:
            if action_loop_task: action_loop_task.cancel()

# --- MAIN LOOP ---
async def telegram_loop(browser):
    global verified_users, waiting_broadcast_input, broadcast_message, waiting_dana_input
    verified_users = load_users()
    offset = 0
    while True:
        data = tg_get_updates(offset)
        for upd in data.get("result", []):
            offset = upd["update_id"] + 1
            if "message" in upd:
                msg = upd["message"]; chat_id = msg["chat"]["id"]; user_id = msg["from"]["id"]
                first_name = msg["from"].get("first_name", "User"); username_tg = msg["from"].get("username")
                mention = f"<a href='tg://user?id={user_id}'>{first_name}</a>"; text = msg.get("text", "")

                if user_id == ADMIN_ID:
                    if text.startswith("/add"):
                        waiting_admin_input.add(user_id)
                        pending_message[user_id] = tg_send(user_id, "Kirim daftar: <code>range > country > service</code>")
                        continue
                    elif text == "/info":
                        waiting_broadcast_input.add(user_id)
                        broadcast_message[user_id] = tg_send(user_id, "Kirim pesan siaran atau <code>.batal</code>")
                        continue
                    elif text.startswith("/get10akses "):
                        try:
                            t_id = text.split(" ")[1]; save_akses_get10(t_id)
                            tg_send(user_id, f"✅ User <code>{t_id}</code> diberi akses /get10.")
                        except: tg_send(user_id, "Gunakan: /get10akses ID")
                        continue
                    elif text == "/list":
                        all_p = load_profil(); list_msg = "<b>Daftar Semua User:</b>\n\n"
                        for uid, p in all_p.items():
                            list_msg += f"Name: {p['nama']}\nDana: {p['dana']}\nBalance: ${p['balance']:.6f}\nOTP: {p['otp_total']}\n\n"
                        tg_send(user_id, list_msg)
                        continue

                # User Logic
                if text == "/start":
                    if is_user_in_both_groups(user_id):
                        verified_users.add(user_id); save_users(user_id)
                        p = get_user_profil(user_id, first_name, username_tg)
                        username_disp = f"/{p['username']}" if p['username'] != "None" else ""
                        msg_text = (
                            f"✅ Verifikasi Berhasil, {mention}{username_disp}\n\n"
                            f"Profil anda :\n"
                            f"🔖Nama: {mention}\n"
                            f"🧾Dana: {p['dana']}\n"
                            f"📊Total of all OTPs: {p['otp_total']}\n"
                            f"📊daily OTP count: {p['otp_hari_ini']}\n"
                            f"💰Balance: ${p['balance']:.6f}\n"
                        )
                        kb = {"inline_keyboard": [
                            [{"text": "📲 Get Number", "callback_data": "getnum"}, {"text": "👨‍💼 Admin", "url": "https://t.me/admin"}],
                            [{"text": "💸 Withdraw Money", "callback_data": "withdraw_menu"}]
                        ]}
                        tg_send(user_id, msg_text, kb)
                    else:
                        kb = {"inline_keyboard": [[{"text": "📌 Gabung Grup 1", "url": GROUP_LINK_1}], [{"text": "📌 Gabung Grup 2", "url": GROUP_LINK_2}], [{"text": "✅ Verifikasi", "callback_data": "verify"}]]}
                        tg_send(user_id, f"Halo {mention}, gabung grup untuk verifikasi:", kb)
                    continue

                if user_id in waiting_dana_input:
                    waiting_dana_input.remove(user_id)
                    if "dana:" in text.lower() and "a/n:" in text.lower():
                        profils = load_profil(); u_id = str(user_id)
                        lines = text.split("\n")
                        profils[u_id]["dana"] = lines[0].split(":")[1].strip()
                        profils[u_id]["a_n"] = lines[1].split(":")[1].strip()
                        save_profil(profils)
                        tg_send(user_id, "✅ Dana Berhasil Diupdate!")
                    else:
                        waiting_dana_input.add(user_id)
                        tg_send(user_id, "❌ Pastikan format benar coba lagi\ndana: \nA/N:")
                    continue

                if text == "/get10" and has_get10_access(user_id):
                    get10_range_input.add(user_id)
                    pending_message[user_id] = tg_send(user_id, "kirim range contoh 225071606XXX")
                    continue

                if user_id in waiting_admin_input:
                    waiting_admin_input.remove(user_id)
                    new_r = []
                    for line in text.strip().split('\n'):
                        if ' > ' in line:
                            ps = line.split(' > ')
                            r_px = ps[0].strip(); c_nm = ps[1].strip().upper(); srv = ps[2].strip() if len(ps) > 2 else "WA"
                            new_r.append({"range": r_px, "country": c_nm, "emoji": GLOBAL_COUNTRY_EMOJI.get(c_nm, "🗺️"), "service": srv})
                    save_inline_ranges(new_r); tg_send(user_id, "✅ Tersimpan.")
                    continue

                is_manual = re.match(r"^\+?\d{3,15}[Xx*#]+$", text.strip(), re.IGNORECASE)
                if user_id in manual_range_input or (user_id in verified_users and is_manual):
                    if user_id in manual_range_input: manual_range_input.remove(user_id)
                    await process_user_input(browser, user_id, text.strip(), 1, username_tg, first_name)
                    continue

            if "callback_query" in upd:
                cq = upd["callback_query"]; u_id = cq["from"]["id"]; cb = cq["data"]; c_id = cq["message"]["chat"]["id"]; m_id = cq["message"]["message_id"]
                p = get_user_profil(u_id, cq["from"].get("first_name"), cq["from"].get("username"))

                if cb == "withdraw_menu":
                    kb = {"inline_keyboard": [
                        [{"text": "$1.000000", "callback_data": "wd:1.0"}, {"text": "$2.000000", "callback_data": "wd:2.0"}],
                        [{"text": "$3.000000", "callback_data": "wd:3.0"}, {"text": "$5.000000", "callback_data": "wd:5.0"}],
                        [{"text": "⚙️ Setting Dana", "callback_data": "set_dana"}]
                    ]}
                    tg_edit(c_id, m_id, f"Silahkan Pilih Jumlah Windraw anda\nDana: {p['dana']}\nA/N : {p['a_n']}", kb)
                
                elif cb == "set_dana":
                    waiting_dana_input.add(u_id)
                    tg_edit(c_id, m_id, "silahkan kirim dana dalam format \n\ndana: \nA/N: ")

                elif cb.startswith("wd:"):
                    amount = float(cb.split(":")[1])
                    if p["balance"] < amount:
                        tg_send(u_id, "❌ Saldo tidak mencukupi.")
                    elif amount < 1.0:
                        tg_send(u_id, "❌ Minimal withdraw $1.000000")
                    else:
                        profils = load_profil(); profils[str(u_id)]["balance"] -= amount; save_profil(profils)
                        admin_kb = {"inline_keyboard": [[{"text": "✅ Approved", "callback_data": f"adm_wd_ok:{u_id}:{amount}"}, {"text": "❌ Cancel", "callback_data": f"adm_wd_no:{u_id}:{amount}"}]]}
                        tg_send(ADMIN_ID, f"User meminta Windraw\nuser: {p['username']}\nSaldo: ${amount:.6f}", admin_kb)
                        tg_send(u_id, "✅ Permintaan WD dikirim ke admin.")

                elif cb.startswith("adm_wd_ok:"):
                    target_id, amt = cb.split(":")[1], float(cb.split(":")[2])
                    tg_send(int(target_id), f"Selamat Windraw anda sukses cek dana anda sekarang:\nPenarikan : ${amt:.6f}\nsaldo saat ini: ${load_profil()[target_id]['balance']:.6f}")
                    tg_delete(c_id, m_id)

                elif cb.startswith("adm_wd_no:"):
                    target_id, amt = cb.split(":")[1], float(cb.split(":")[2])
                    profils = load_profil(); profils[target_id]["balance"] += amt; save_profil(profils)
                    tg_send(int(target_id), "Admin membatalkan Windraw\nsilahkan chat Admin atau melakukan ulang Windraw.")
                    tg_delete(c_id, m_id)

                elif cb == "getnum":
                    inline_ranges = load_inline_ranges()
                    kb = generate_inline_keyboard(inline_ranges)
                    tg_edit(c_id, m_id, "<b>Get Number</b>\n\nSilahkan pilih range atau input manual.", kb)
                
                elif cb.startswith("select_range:"):
                    await process_user_input(browser, u_id, cb.split(":")[1], 1, cq["from"].get("username"), cq["from"].get("first_name"), m_id)
        await asyncio.sleep(0.05) 

async def main():
    global shared_page
    initialize_files()
    clear_pending_updates()
    try: subprocess.Popen([sys.executable, "sms.py"])
    except: pass
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        shared_page = await browser.contexts[0].new_page()
        await shared_page.goto(BASE_WEB_URL, wait_until='domcontentloaded')
        await asyncio.gather(telegram_loop(browser))

def initialize_files():
    for f, d in {CACHE_FILE: "[]", INLINE_RANGE_FILE: "[]", USER_FILE: "[]", WAIT_FILE: "[]", PROFIL_FILE: "{}", AKSES_GET10_FILE: "[]"}.items():
        if not os.path.exists(f): 
            with open(f, "w") as x: x.write(d)

if __name__ == "__main__":
    asyncio.run(main())
