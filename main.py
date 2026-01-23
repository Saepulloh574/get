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

# --- CONFIGURATION & PATHS ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    GROUP_ID_1 = int(os.getenv("GROUP_ID_1"))
    GROUP_ID_2 = int(os.getenv("GROUP_ID_2"))
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError) as e:
    print(f"[FATAL] Environment variables missing: {e}")
    sys.exit(1)

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
BASE_WEB_URL = "https://x.mnitnetwork.com/mdashboard/getnum" 
SESSION_DIR = "playwright_session" # Folder to store login cookies/session

# --- FILE CONSTANTS ---
USER_FILE = "user.json" 
CACHE_FILE = "cache.json"
INLINE_RANGE_FILE = "inline.json"
SMC_FILE = "smc.json"
WAIT_FILE = "wait.json"
AKSES_GET10_FILE = "aksesget10.json"
BOT_USERNAME_LINK = "https://t.me/myzuraisgoodbot" 
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1" 
GROUP_LINK_2 = "https://t.me/zura14g" 

# --- ASYNCIO LOCK & GLOBAL VARS ---
playwright_lock = asyncio.Lock()
shared_page = None 
waiting_broadcast_input = set() 
broadcast_message = {} 
verified_users = set()
waiting_admin_input = set()
manual_range_input = set() 
get10_range_input = set()
pending_message = {}
sent_numbers = set()
last_used_range = {}

# --- COUNTRY EMOJI DATA ---
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

# --- PROGRESS BAR CONFIG ---
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

# --- FILE UTILITIES ---
def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            try: return set(json.load(f))
            except json.JSONDecodeError: return set()
    return set()

def save_users(user_id):
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        with open(USER_FILE, "w") as f: json.dump(list(users), f, indent=2)

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            try: return json.load(f)
            except json.JSONDecodeError: return []
    return []

def save_cache(number_entry):
    cache = load_cache()
    if len(cache) >= 1000: cache.pop(0) 
    cache.append(number_entry)
    with open(CACHE_FILE, "w") as f: json.dump(cache, f, indent=2)

def is_in_cache(number):
    cache = load_cache()
    normalized_number = normalize_number(number) 
    return any(normalize_number(entry["number"]) == normalized_number for entry in cache)

def load_inline_ranges():
    if os.path.exists(INLINE_RANGE_FILE):
        with open(INLINE_RANGE_FILE, "r") as f:
            try: return json.load(f)
            except json.JSONDecodeError: return []
    return []

def save_inline_ranges(ranges):
    with open(INLINE_RANGE_FILE, "w") as f: json.dump(ranges, f, indent=2)

def load_akses_get10():
    if os.path.exists(AKSES_GET10_FILE):
        with open(AKSES_GET10_FILE, "r") as f:
            try: return set(json.load(f))
            except json.JSONDecodeError: return set()
    return set()

def save_akses_get10(user_id_to_add):
    akses = load_akses_get10()
    akses.add(int(user_id_to_add))
    with open(AKSES_GET10_FILE, "w") as f: json.dump(list(akses), f, indent=2)

def has_get10_access(user_id):
    if user_id == ADMIN_ID: return True
    akses_list = load_akses_get10()
    return user_id in akses_list

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
    if current_row: keyboard.append(current_row)
    keyboard.append([{"text": "Input Manual Range..🖊️", "callback_data": "manual_range"}])
    return {"inline_keyboard": keyboard}

def load_wait_list():
    if os.path.exists(WAIT_FILE):
        with open(WAIT_FILE, "r") as f:
            try: return json.load(f)
            except json.JSONDecodeError: return []
    return []

def save_wait_list(data):
    with open(WAIT_FILE, "w") as f: json.dump(data, f, indent=2)

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

# --- TELEGRAM API UTILS ---
def tg_send(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: data["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{API}/sendMessage", json=data).json()
        return r["result"]["message_id"] if r.get("ok") else None
    except: return None

def tg_edit(chat_id, message_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: data["reply_markup"] = reply_markup
    try: requests.post(f"{API}/editMessageText", json=data)
    except: pass 

def tg_delete(chat_id, message_id):
    try: requests.post(f"{API}/deleteMessage", json={"chat_id": chat_id, "message_id": message_id})
    except: pass 

def tg_send_action(chat_id, action="typing"):
    try: requests.post(f"{API}/sendChatAction", data={"chat_id": chat_id, "action": action})
    except: pass 

def tg_get_updates(offset):
    try: return requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 5}).json()
    except: return {"ok": False, "result": []}

def is_user_in_group(user_id, group_id):
    try:
        r = requests.get(f"{API}/getChatMember", params={"chat_id": group_id, "user_id": user_id}).json()
        return r["result"]["status"] in ["member", "administrator", "creator"] if r.get("ok") else False
    except: return False

def is_user_in_both_groups(user_id):
    return is_user_in_group(user_id, GROUP_ID_1) and is_user_in_group(user_id, GROUP_ID_2)

def clear_pending_updates():
    try:
        r = requests.get(f"{API}/getUpdates", params={"offset": -1, "timeout": 1}).json()
        if r.get("ok") and r.get("result"):
            last_id = r["result"][-1]["update_id"]
            requests.get(f"{API}/getUpdates", params={"offset": last_id + 1, "timeout": 1})
    except: pass

async def tg_broadcast(message_text, admin_id):
    user_ids = list(load_users())
    s, f = 0, 0
    admin_msg_id = tg_send(admin_id, f"🔄 Memulai siaran ke **{len(user_ids)}** pengguna...")
    for i, user_id in enumerate(user_ids):
        if i % 10 == 0 and admin_msg_id:
            tg_edit(admin_id, admin_msg_id, f"🔄 Siaran: **{i}/{len(user_ids)}** (S:{s}, G:{f})")
        if tg_send(user_id, message_text): s += 1
        else: f += 1
        await asyncio.sleep(0.05) 
    tg_edit(admin_id, admin_msg_id, f"✅ Selesai!\n👥 Total: {len(user_ids)}\n🟢 Sukses: {s}\n🔴 Gagal: {f}")

async def action_task(chat_id):
    while True:
        tg_send_action(chat_id)
        await asyncio.sleep(4.5)

# --- SCRAPING LOGIC ---
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
        return (number, country, status_text) if (number and len(number) > 5) else (None, None, None)
    except: return None, None, None

async def get_all_numbers_parallel(page, num_to_fetch):
    tasks = [get_number_and_country_from_row(f"tbody tr:nth-child({i})", page) for i in range(1, num_to_fetch + 5)]
    results = await asyncio.gather(*tasks)
    current_numbers = []
    for number, country, status in results:
        if number and number not in [n['number'] for n in current_numbers]:
            current_numbers.append({'number': number, 'country': country})
    return current_numbers

async def process_user_input(browser_context, user_id, prefix, click_count, username_tg, first_name_tg, message_id_to_edit=None):
    global shared_page, last_used_range
    msg_id = message_id_to_edit if message_id_to_edit else pending_message.pop(user_id, None)
    action_loop_task = None 
    num_to_fetch = click_count 

    if playwright_lock.locked():
        if not msg_id: msg_id = tg_send(user_id, get_progress_message(0, 0, prefix, num_to_fetch))
        else: tg_edit(user_id, msg_id, get_progress_message(0, 0, prefix, num_to_fetch))

    async with playwright_lock:
        try:
            action_loop_task = asyncio.create_task(action_task(user_id))
            start_operation_time = time.time()
            if not msg_id: msg_id = tg_send(user_id, get_progress_message(0, 0, prefix, num_to_fetch))
            
            if not shared_page:
                shared_page = await browser_context.new_page()
                await shared_page.goto(BASE_WEB_URL, wait_until='domcontentloaded')

            INPUT_SELECTOR, BUTTON_SELECTOR = "input[name='numberrange']", "button:has-text('Get Number')" 
            await shared_page.wait_for_selector(INPUT_SELECTOR, state='visible', timeout=10000)
            await shared_page.fill(INPUT_SELECTOR, prefix)
            
            tg_edit(user_id, msg_id, get_progress_message(3, 0, prefix, num_to_fetch))
            for _ in range(click_count): await shared_page.click(BUTTON_SELECTOR, force=True)
            
            await asyncio.sleep(0.5)
            tg_edit(user_id, msg_id, get_progress_message(4, 0, prefix, num_to_fetch))
            
            found_numbers = []
            for round_num in range(2):
                if round_num == 1 and len(found_numbers) < num_to_fetch:
                    await shared_page.click(BUTTON_SELECTOR, force=True)
                    tg_edit(user_id, msg_id, get_progress_message(8, 0, prefix, num_to_fetch))
                
                start_time = time.time()
                while (time.time() - start_time) < 5.0:
                    found_numbers = await get_all_numbers_parallel(shared_page, num_to_fetch)
                    if len(found_numbers) >= num_to_fetch: break
                    await asyncio.sleep(0.25)
                if len(found_numbers) >= num_to_fetch: break
            
            if not found_numbers:
                tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DI TEMUKAN. Coba lagi atau ganti range.")
                return 

            tg_edit(user_id, msg_id, get_progress_message(12, 0, prefix, num_to_fetch))
            for entry in found_numbers:
                save_cache({"number": entry['number'], "country": entry['country'], "user_id": user_id, "time": time.time()})
                add_to_wait_list(entry['number'], user_id, username_tg, first_name_tg)
            
            last_used_range[user_id] = prefix 
            main_country = found_numbers[0]['country']
            emoji = GLOBAL_COUNTRY_EMOJI.get(main_country, "🗺️") 
            
            if num_to_fetch == 10:
                msg = "✅The number is already.\n\n<code>" + "\n".join([e['number'] for e in found_numbers[:10]]) + "</code>"
            else:
                msg = "✅ The number is ready\n\n"
                for idx, num_data in enumerate(found_numbers[:num_to_fetch]):
                    msg += f"📞 Number {' ' if num_to_fetch==1 else idx+1} : <code>{num_data['number']}</code>\n"
                msg += f"{emoji} COUNTRY : {main_country}\n🏷️ Range   : <code>{prefix}</code>\n\n<b>🤖 Number available please use, Waiting for OTP</b>\n"

            inline_kb = {"inline_keyboard": [
                [{"text": "🔄 Change 1 Number", "callback_data": f"change_num:1:{prefix}"}],
                [{"text": "🔄 Change 3 Number", "callback_data": f"change_num:3:{prefix}"}],
                [{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}, {"text": "🌐 Change Range", "callback_data": "getnum"}]
            ]}
            tg_edit(user_id, msg_id, msg, reply_markup=inline_kb)
        except Exception as e:
            if msg_id: tg_edit(user_id, msg_id, f"❌ Error: {type(e).__name__}")
        finally:
            if action_loop_task: action_loop_task.cancel()

# --- MAIN LOOPS ---
async def telegram_loop(browser_context):
    global verified_users, waiting_broadcast_input, broadcast_message
    verified_users = load_users()
    offset = 0
    while True:
        data = tg_get_updates(offset)
        for upd in data.get("result", []):
            offset = upd["update_id"] + 1
            if "message" in upd:
                msg = upd["message"]
                user_id, text = msg["from"]["id"], msg.get("text", "")
                f_name, u_tg = msg["from"].get("first_name", "User"), msg["from"].get("username")
                mention = f"<a href='tg://user?id={user_id}'>{f_name}</a>"

                if user_id == ADMIN_ID:
                    if text.startswith("/add"):
                        waiting_admin_input.add(user_id)
                        pending_message[user_id] = tg_send(user_id, "Kirim format: <code>range > country</code>")
                        continue
                    elif text == "/info":
                        waiting_broadcast_input.add(user_id)
                        broadcast_message[user_id] = tg_send(user_id, "Kirim pesan siaran atau <code>.batal</code>")
                        continue
                    elif text.startswith("/get10akses "):
                        try:
                            t_id = text.split(" ")[1]
                            save_akses_get10(t_id)
                            tg_send(user_id, f"✅ Akses /get10 diberikan ke {t_id}")
                        except: pass
                        continue

                if text == "/get10" and has_get10_access(user_id):
                    get10_range_input.add(user_id)
                    pending_message[user_id] = tg_send(user_id, "Kirim range (contoh: 225071606XXX)")
                    continue

                if user_id in waiting_admin_input:
                    waiting_admin_input.remove(user_id)
                    new_r = []
                    for line in text.strip().split('\n'):
                        if ' > ' in line:
                            p = line.split(' > ')
                            new_r.append({"range": p[0].strip(), "country": p[1].strip().upper(), "emoji": GLOBAL_COUNTRY_EMOJI.get(p[1].strip().upper(), "🗺️")})
                    save_inline_ranges(new_r)
                    tg_edit(user_id, pending_message.pop(user_id), f"✅ Tersimpan {len(new_r)} range.")
                    continue

                if user_id in waiting_broadcast_input:
                    waiting_broadcast_input.remove(user_id)
                    p_id = broadcast_message.pop(user_id)
                    if text.lower() == ".batal": tg_edit(user_id, p_id, "❌ Batal.")
                    else: await tg_broadcast(text, user_id)
                    continue

                if user_id in get10_range_input:
                    get10_range_input.remove(user_id)
                    await process_user_input(browser_context, user_id, text.strip(), 10, u_tg, f_name, pending_message.pop(user_id))
                    continue
                
                is_man = re.match(r"^\+?\d{3,15}[Xx*#]+$", text.strip(), re.IGNORECASE)
                if (user_id in manual_range_input or (user_id in verified_users and is_man)):
                    if user_id in manual_range_input: manual_range_input.remove(user_id)
                    await process_user_input(browser_context, user_id, text.strip(), 1, u_tg, f_name, pending_message.pop(user_id, None))
                    continue

                if text == "/start":
                    if is_user_in_both_groups(user_id):
                        verified_users.add(user_id); save_users(user_id)
                        tg_send(user_id, f"✅ Berhasil {mention}!", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}]]})
                    else:
                        tg_send(user_id, f"Halo {mention} 👋\nGabung dulu:", {"inline_keyboard": [[{"text": "Grup 1", "url": GROUP_LINK_1}],[{"text": "Grup 2", "url": GROUP_LINK_2}],[{"text": "✅ Verifikasi", "callback_data": "verify"}]]})

            if "callback_query" in upd:
                cq = upd["callback_query"]
                u_id, d_cb, c_id, m_id = cq["from"]["id"], cq["data"], cq["message"]["chat"]["id"], cq["message"]["message_id"]
                u_tg, f_tg = cq["from"].get("username"), cq["from"].get("first_name", "User")

                if d_cb == "verify":
                    if is_user_in_both_groups(u_id):
                        verified_users.add(u_id); save_users(u_id)
                        tg_edit(c_id, m_id, "✅ Berhasil!", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}]]})
                    else: tg_edit(c_id, m_id, "❌ Belum gabung.", {"inline_keyboard": [[{"text": "Grup 1", "url": GROUP_LINK_1}],[{"text": "Grup 2", "url": GROUP_LINK_2}],[{"text": "✅ Verifikasi", "callback_data": "verify"}]]})
                elif d_cb == "getnum" and u_id in verified_users:
                    rgs = load_inline_ranges()
                    tg_edit(c_id, m_id, "<b>Pilih Range:</b>", generate_inline_keyboard(rgs))
                elif d_cb == "manual_range" and u_id in verified_users:
                    manual_range_input.add(u_id); pending_message[u_id] = m_id
                    tg_edit(c_id, m_id, "Kirim range (contoh: 2327600XXX)")
                elif d_cb.startswith("select_range:") and u_id in verified_users:
                    await process_user_input(browser_context, u_id, d_cb.split(":")[1], 1, u_tg, f_tg, m_id)
                elif d_cb.startswith("change_num:") and u_id in verified_users:
                    tg_delete(c_id, m_id)
                    await process_user_input(browser_context, u_id, d_cb.split(":")[2], int(d_cb.split(":")[1]), u_tg, f_tg)
        await asyncio.sleep(0.05)

async def expiry_monitor_task():
    while True:
        try:
            wait_list = load_wait_list(); now = time.time(); upd = []
            for it in wait_list:
                if now - it['timestamp'] > 1200:
                    mid = tg_send(it['user_id'], f"⚠️ Nomor <code>{it['number']}</code> kadaluarsa.")
                    if mid: asyncio.create_task(delayed_delete(it['user_id'], mid, 30))
                else: upd.append(it)
            save_wait_list(upd)
        except: pass
        await asyncio.sleep(10)

async def delayed_delete(c_id, m_id, delay):
    await asyncio.sleep(delay); tg_delete(c_id, m_id)

def initialize_files():
    for f, d in {CACHE_FILE: "[]", INLINE_RANGE_FILE: "[]", SMC_FILE: "[]", USER_FILE: "[]", WAIT_FILE: "[]", AKSES_GET10_FILE: "[]"}.items():
        if not os.path.exists(f): 
            with open(f, "w") as file: file.write(d)

async def main():
    global shared_page
    initialize_files(); clear_pending_updates()
    
    # SMS Process startup
    sms_p = None
    try: sms_p = subprocess.Popen([sys.executable, "sms.py"])
    except: pass

    async with async_playwright() as p:
        # --- LOGIN LOGIC ---
        is_first_run = not os.path.exists(SESSION_DIR)
        
        if is_first_run:
            print("\n" + "="*50)
            print("PERTAMA KALI JALAN: PERLU LOGIN MANUAL")
            print("="*50)
            choice = input("Ketik 'Y' untuk membuka browser login: ").strip().upper()
            if choice == 'Y':
                browser = await p.chromium.launch_persistent_context(SESSION_DIR, headless=False)
                page = await browser.new_page()
                await page.goto(BASE_WEB_URL)
                print("\n[!] SILAHKAN LOGIN DI JENDELA BROWSER.")
                print("[!] SETELAH BERHASIL MASUK DASHBOARD, TUTUP BROWSER TERSEBUT.")
                
                # Wait for manual close
                while len(browser.pages) > 0:
                    await asyncio.sleep(1)
                await browser.close()
                print("\n[OK] Session tersimpan. Memulai bot dalam mode background (Headless)...")
            else:
                print("[ABORT] Login dibatalkan.")
                return

        # --- BACKGROUND BOT (PERMANENT) ---
        print("[INFO] Menjalankan Bot di Latar Belakang...")
        browser = await p.chromium.launch_persistent_context(
            SESSION_DIR, 
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        
        shared_page = await browser.new_page()
        await shared_page.goto(BASE_WEB_URL, wait_until='domcontentloaded')
        
        try:
            await asyncio.gather(telegram_loop(browser), expiry_monitor_task())
        finally:
            if sms_p: sms_p.terminate()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("\n[INFO] Off.")
