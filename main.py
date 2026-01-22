import asyncio
import json
import os
import requests
import httpx
import re
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from dotenv import load_dotenv
import subprocess
import sys
import time
import math 

# --- KONFIGURASI LEVEL 2 ---
EMAIL_MNIT = "muhamadreyhan0073@gmail.com"
PASS_MNIT = "fd140206"
# ---------------------------

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

# --- KONFIGURASI PROGRESS BAR GLOBAL ---
MAX_BAR_LENGTH = 12 
FILLED_CHAR = "█"
EMPTY_CHAR = "░"

STATUS_MAP = {
    0:  "Menunggu di antrian sistem aktif..",
    3:  "Mengirim permintaan nomor baru go.",
    12: "Nomor ditemukan memproses data fin"
}

def get_progress_message(current_step, total_steps, prefix_range, num_count):
    progress_ratio = min(current_step / 12, 1.0)
    filled_count = math.ceil(progress_ratio * MAX_BAR_LENGTH)
    empty_count = MAX_BAR_LENGTH - filled_count
    progress_bar = FILLED_CHAR * filled_count + EMPTY_CHAR * empty_count
    current_status = STATUS_MAP.get(current_step, "Sedang memproses..")
    return (
    f"<code>{current_status}</code>\n"
    f"<blockquote>Range: <code>{prefix_range}</code> | Jumlah: <code>{num_count}</code></blockquote>\n"
    f"<code>Load:</code> [{progress_bar}]"
)

# --- LOAD DOTENV ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    GROUP_ID_1 = int(os.getenv("GROUP_ID_1"))
    GROUP_ID_2 = int(os.getenv("GROUP_ID_2"))
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError) as e:
    print(f"[FATAL] Variabel lingkungan GROUP_ID_1, GROUP_ID_2, atau ADMIN_ID tidak diatur: {e}")
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
last_used_range = {}

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
        with open(USER_FILE, "w") as f: json.dump(list(users), f, indent=2)

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
    with open(CACHE_FILE, "w") as f: json.dump(cache, f, indent=2)

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
    with open(INLINE_RANGE_FILE, "w") as f: json.dump(ranges, f, indent=2)

def load_akses_get10():
    if os.path.exists(AKSES_GET10_FILE):
        with open(AKSES_GET10_FILE, "r") as f:
            try: return set(json.load(f))
            except: return set()
    return set()

def save_akses_get10(user_id_to_add):
    akses = load_akses_get10()
    akses.add(int(user_id_to_add))
    with open(AKSES_GET10_FILE, "w") as f: json.dump(list(akses), f, indent=2)

def has_get10_access(user_id):
    if user_id == ADMIN_ID: return True
    return user_id in load_akses_get10()

def generate_inline_keyboard(ranges):
    keyboard = []
    current_row = []
    for item in ranges:
        text = f"{item['country']} {item['emoji']}"
        current_row.append({"text": text, "callback_data": f"select_range:{item['range']}"})
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
            except: return []
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
    wait_list.append({"number": normalized_number, "user_id": user_id, "username": final_identity, "timestamp": time.time()})
    save_wait_list(wait_list)

def normalize_number(number):
    normalized_number = str(number).strip().replace(" ", "").replace("-", "")
    if not normalized_number.startswith('+') and normalized_number.isdigit():
        normalized_number = '+' + normalized_number
    return normalized_number

# --- TG API UTILS ---
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

def tg_get_updates(offset):
    try: return requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 5}).json()
    except: return {"ok": False, "result": []}

def is_user_in_both_groups(user_id):
    def check(gid):
        try:
            r = requests.get(f"{API}/getChatMember", params={"chat_id": gid, "user_id": user_id}).json()
            return r.get("ok") and r["result"]["status"] in ["member", "administrator", "creator"]
        except: return False
    return check(GROUP_ID_1) and check(GROUP_ID_2)

# --- LEVEL 2 API CLASS ---
class MNITDirect:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
        self.base_url = "https://x.mnitnetwork.com"
        self.is_logged_in = False

    async def login(self):
        try:
            login_data = {"email": EMAIL_MNIT, "password": PASS_MNIT}
            resp = await self.client.post(f"{self.base_url}/mauth/login", data=login_data)
            if resp.status_code == 200 or "mdashboard" in str(resp.url):
                self.is_logged_in = True
                return True
            return False
        except: return False

    async def order_number(self, prefix, count):
        tasks = []
        for _ in range(count):
            tasks.append(self.client.get(f"{self.base_url}/mdashboard/getnum", params={"range": prefix}, headers={"X-Requested-With": "XMLHttpRequest"}))
        await asyncio.gather(*tasks)

    async def get_info(self):
        resp = await self.client.get(f"{self.base_url}/mapi/v1/mdashboard/getnum/info?page=1", headers={"X-Requested-With": "XMLHttpRequest"})
        return resp.json() if resp.status_code == 200 else None

mnit_api = MNITDirect()

# --- MODIFIED PROCESS INPUT (LEVEL 2) ---
async def process_user_input(browser, user_id, prefix, click_count, username_tg, first_name_tg, message_id_to_edit=None):
    msg_id = message_id_to_edit if message_id_to_edit else pending_message.pop(user_id, None)
    if not msg_id: msg_id = tg_send(user_id, get_progress_message(0, 0, prefix, click_count))
    else: tg_edit(user_id, msg_id, get_progress_message(0, 0, prefix, click_count))

    try:
        if not mnit_api.is_logged_in: await mnit_api.login()
        
        tg_edit(user_id, msg_id, get_progress_message(3, 0, prefix, click_count))
        await mnit_api.order_number(prefix, click_count)
        
        await asyncio.sleep(2.0) # Tunggu sinkronisasi API
        data = await mnit_api.get_info()
        
        if not data or not data.get("data"):
            tg_edit(user_id, msg_id, "❌ Gagal mengambil data. Range mungkin salah atau habis.")
            return

        found_numbers = []
        for item in data["data"]:
            num = normalize_number(item["number"])
            if not is_in_cache(num):
                country = item.get("country_name", "UNKNOWN").upper()
                found_numbers.append({"number": num, "country": country})
                if len(found_numbers) >= click_count: break

        if not found_numbers:
            tg_edit(user_id, msg_id, "❌ Nomor tidak ditemukan. Coba lagi.")
            return

        tg_edit(user_id, msg_id, get_progress_message(12, 0, prefix, click_count))
        
        for entry in found_numbers:
            save_cache({"number": entry['number'], "country": entry['country'], "user_id": user_id, "time": time.time()})
            add_to_wait_list(entry['number'], user_id, username_tg, first_name_tg)

        main_country = found_numbers[0]['country']
        emoji = GLOBAL_COUNTRY_EMOJI.get(main_country, "🗺️")
        
        if click_count == 10:
            msg = "✅The number is already.\n\n<code>"
            for entry in found_numbers: msg += f"{entry['number']}\n"
            msg += "</code>"
        else:
            msg = f"✅ The number is ready\n\n"
            for idx, num_data in enumerate(found_numbers):
                msg += f"📞 Number {idx+1} : <code>{num_data['number']}</code>\n"
            msg += f"{emoji} COUNTRY : {main_country}\n🏷️ Range : <code>{prefix}</code>\n\n<b>🤖 Number available please use, Waiting for OTP</b>"

        kb = {"inline_keyboard": [[{"text": "🔄 Change 1 Number", "callback_data": f"change_num:1:{prefix}"}],[{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}, {"text": "🌐 Change Range", "callback_data": "getnum"}]]}
        tg_edit(user_id, msg_id, msg, reply_markup=kb)

    except Exception as e:
        tg_edit(user_id, msg_id, f"❌ Error: {str(e)}")

# --- TELEGRAM LOOP ---
async def telegram_loop(browser):
    global verified_users, waiting_broadcast_input, broadcast_message
    verified_users = load_users()
    offset = 0
    while True:
        data = tg_get_updates(offset)
        for upd in data.get("result", []):
            offset = upd["update_id"] + 1
            if "message" in upd:
                msg = upd["message"]; chat_id = msg["chat"]["id"]; user_id = msg["from"]["id"]
                first_name = msg["from"].get("first_name", "User"); username_tg = msg["from"].get("username")
                text = msg.get("text", "")

                if user_id == ADMIN_ID:
                    if text.startswith("/add"):
                        waiting_admin_input.add(user_id)
                        pending_message[user_id] = tg_send(user_id, "Kirim: <code>range > country</code>")
                        continue
                    elif text == "/info":
                        waiting_broadcast_input.add(user_id)
                        broadcast_message[user_id] = tg_send(user_id, "Kirim pesan siaran atau <code>.batal</code>")
                        continue
                    elif text.startswith("/get10akses "):
                        try:
                            tid = text.split(" ")[1]; save_akses_get10(tid)
                            tg_send(user_id, f"✅ Akses diberikan ke {tid}")
                        except: pass
                        continue

                if text == "/get10":
                    if has_get10_access(user_id):
                        get10_range_input.add(user_id)
                        pending_message[user_id] = tg_send(user_id, "Kirim range (contoh 22507XXX)")
                    else: tg_send(user_id, "❌ No access.")
                    continue

                if user_id in waiting_admin_input:
                    waiting_admin_input.remove(user_id); new_ranges = []
                    for line in text.split('\n'):
                        if ' > ' in line:
                            p = line.split(' > '); r_pre = p[0].strip(); c_name = p[1].strip().upper()
                            new_ranges.append({"range": r_pre, "country": c_name, "emoji": GLOBAL_COUNTRY_EMOJI.get(c_name, "🗺️")})
                    save_inline_ranges(new_ranges); tg_edit(user_id, pending_message.pop(user_id), "✅ Saved.")
                    continue

                # Handle Manual/Get10 Range
                is_manual = re.match(r"^\+?\d{3,15}[Xx*#]+$", text.strip(), re.IGNORECASE)
                if user_id in get10_range_input:
                    get10_range_input.remove(user_id)
                    if is_manual: await process_user_input(browser, user_id, text.strip(), 10, username_tg, first_name)
                    continue
                
                if user_id in manual_range_input or (user_id in verified_users and is_manual):
                    if user_id in manual_range_input: manual_range_input.remove(user_id)
                    if is_manual: await process_user_input(browser, user_id, text.strip(), 1, username_tg, first_name)
                    continue

                if text == "/start":
                    if is_user_in_both_groups(user_id):
                        verified_users.add(user_id); save_users(user_id)
                        tg_send(user_id, f"✅ Berhasil!", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}]]})
                    else:
                        kb = {"inline_keyboard": [[{"text": "📌 Grup 1", "url": GROUP_LINK_1}], [{"text": "📌 Grup 2", "url": GROUP_LINK_2}], [{"text": "✅ Verif", "callback_data": "verify"}]]}
                        tg_send(user_id, "Gabung grup dulu:", kb)
                    continue

            if "callback_query" in upd:
                cq = upd["callback_query"]; user_id = cq["from"]["id"]; data_cb = cq["data"]
                chat_id = cq["message"]["chat"]["id"]; mid = cq["message"]["message_id"]
                fname = cq["from"].get("first_name"); uname = cq["from"].get("username")

                if data_cb == "verify":
                    if is_user_in_both_groups(user_id):
                        verified_users.add(user_id); save_users(user_id)
                        tg_edit(chat_id, mid, "✅ Berhasil!", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}]]})
                    continue
                if data_cb == "getnum":
                    ranges = load_inline_ranges()
                    tg_edit(chat_id, mid, "Pilih Range:", generate_inline_keyboard(ranges))
                    continue
                if data_cb == "manual_range":
                    manual_range_input.add(user_id); pending_message[user_id] = mid
                    tg_edit(chat_id, mid, "Kirim range manual:")
                    continue
                if data_cb.startswith("select_range:"):
                    await process_user_input(browser, user_id, data_cb.split(":")[1], 1, uname, fname, mid)
                    continue
                if data_cb.startswith("change_num:"):
                    p = data_cb.split(":"); tg_delete(chat_id, mid)
                    await process_user_input(browser, user_id, p[2], int(p[1]), uname, fname)
                    continue
        await asyncio.sleep(0.1)

# --- TASKS & MAIN ---
async def expiry_monitor_task():
    while True:
        try:
            wl = load_wait_list(); ct = time.time(); updated = []
            for item in wl:
                if ct - item['timestamp'] > 1200:
                    tg_send(item['user_id'], f"⚠️ <code>{item['number']}</code> expired.")
                else: updated.append(item)
            save_wait_list(updated)
        except: pass
        await asyncio.sleep(20)

def initialize_files():
    for f, c in {CACHE_FILE:"[]", INLINE_RANGE_FILE:"[]", USER_FILE:"[]", WAIT_FILE:"[]", AKSES_GET10_FILE:"[]"}.items():
        if not os.path.exists(f): 
            with open(f, "w") as file: file.write(c)

async def main():
    initialize_files()
    sms_p = subprocess.Popen([sys.executable, "sms.py"])
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            await asyncio.gather(telegram_loop(browser), expiry_monitor_task())
    finally: sms_p.terminate()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
