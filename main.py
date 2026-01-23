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

# --- KONFIGURASI LOGIN MNIT (SESUAIKAN) ---
EMAIL_MNIT = "muhamadreyhan0073@gmail.com"
PASS_MNIT = "fd140206"
TARGET_URL = "https://x.mnitnetwork.com/mdashboard/getnum"

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
    current_status = STATUS_MAP.get(current_step, "Sedang memproses..")
    return (
    f"<code>{current_status}</code>\n"
    f"<blockquote>Range: <code>{prefix_range}</code> | Jumlah: <code>{num_count}</code></blockquote>\n"
    f"<code>Load:</code> [{progress_bar}]"
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID_1 = int(os.getenv("GROUP_ID_1"))
GROUP_ID_2 = int(os.getenv("GROUP_ID_2"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))
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

verified_users = set()
waiting_admin_input = set()
manual_range_input = set() 
get10_range_input = set()
pending_message = {}
last_used_range = {}
waiting_broadcast_input = set() 
broadcast_message = {} 

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
    norm = normalize_number(number) 
    return any(normalize_number(entry["number"]) == norm for entry in cache)

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
            except: return []
    return []

def save_wait_list(data):
    with open(WAIT_FILE, "w") as f: json.dump(data, f, indent=2)

def add_to_wait_list(number, user_id, username, first_name):
    wait_list = load_wait_list()
    norm = normalize_number(number)
    final_identity = f"@{username.replace('@', '')}" if username and username != "None" else f'<a href="tg://user?id={user_id}">{first_name}</a>'
    wait_list = [item for item in wait_list if item['number'] != norm]
    wait_list.append({"number": norm, "user_id": user_id, "username": final_identity, "timestamp": time.time()})
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
    r = requests.post(f"{API}/sendMessage", json=data).json()
    return r["result"]["message_id"] if r.get("ok") else None

def tg_send_photo(chat_id, photo_path, caption):
    with open(photo_path, 'rb') as f:
        requests.post(f"{API}/sendPhoto", params={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}, files={"photo": f})

def tg_edit(chat_id, message_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: data["reply_markup"] = reply_markup
    requests.post(f"{API}/editMessageText", json=data)

def tg_delete(chat_id, message_id):
    requests.post(f"{API}/deleteMessage", json={"chat_id": chat_id, "message_id": message_id})

def is_user_in_both_groups(user_id):
    def check(gid):
        r = requests.get(f"{API}/getChatMember", params={"chat_id": gid, "user_id": user_id}).json()
        return r.get("ok") and r["result"]["status"] in ["member", "administrator", "creator"]
    return check(GROUP_ID_1) and check(GROUP_ID_2)

# --- LOGIN AUTO ENGINE ---
async def auto_login_mnit(browser_context):
    global shared_page
    print("[TERMINAL] Menjalankan Auto-Login...")
    page = await browser_context.new_page()
    ss_path = "login_status.png"
    try:
        await page.goto("https://x.mnitnetwork.com/mauth/login", timeout=60000)
        await page.wait_for_selector("input[type='email']", timeout=20000)
        await page.type("input[type='email']", EMAIL_MNIT, delay=100)
        await page.type("input[type='password']", PASS_MNIT, delay=100)
        await page.click("button[type='submit']")
        
        # Tunggu redirect ke dashboard
        try:
            await page.wait_for_url("**/mdashboard/getnum", timeout=30000)
        except:
            pass 
            
        await asyncio.sleep(3)
        await page.screenshot(path=ss_path)
        
        if "mdashboard/getnum" in page.url:
            print("[TERMINAL] ✅ LOGIN BERHASIL")
            tg_send_photo(ADMIN_ID, ss_path, "✅ <b>LOGIN BERHASIL</b>\nBot sudah masuk ke Dashboard.")
            shared_page = page 
            return True
        else:
            print(f"[TERMINAL] ❌ LOGIN GAGAL: {page.url}")
            tg_send_photo(ADMIN_ID, ss_path, f"❌ <b>LOGIN GAGAL</b>\nURL: {page.url}")
            await page.close()
            return False
    except Exception as e:
        await page.screenshot(path=ss_path)
        tg_send_photo(ADMIN_ID, ss_path, f"❌ <b>ERROR LOGIN</b>\n{str(e)[:100]}")
        await page.close()
        return False

# --- PLAYWRIGHT HELPERS ---
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
        return (number, country, status_text) if number and len(number) > 5 else (None, None, None)
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
    num_to_fetch = click_count 

    async with playwright_lock:
        try:
            current_step = 0 
            if not shared_page or shared_page.is_closed():
                await auto_login_mnit(browser_context)
            
            if not msg_id:
                msg_id = tg_send(user_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
            
            await shared_page.fill("input[name='numberrange']", prefix)
            await shared_page.click("button:has-text('Get Number')", force=True)
            
            # Start logic progress
            current_step = 3
            tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
            
            found_numbers = []
            start_op = time.time()
            for round_num in range(2):
                if round_num == 1 and len(found_numbers) < num_to_fetch:
                    await shared_page.click("button:has-text('Get Number')", force=True)
                    current_step = 8
                
                start_time = time.time()
                while (time.time() - start_time) < 5.0:
                    found_numbers = await get_all_numbers_parallel(shared_page, num_to_fetch)
                    if len(found_numbers) >= num_to_fetch:
                        current_step = 12
                        break
                    # Visual Progress
                    target = int(12 * (time.time() - start_op) / 12)
                    if target > current_step and target <= 11:
                        current_step = target
                        tg_edit(user_id, msg_id, get_progress_message(current_step, 0, prefix, num_to_fetch))
                    await asyncio.sleep(0.5)
                if len(found_numbers) >= num_to_fetch: break

            if not found_numbers:
                tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DI TEMUKAN.")
                return 

            for entry in found_numbers[:num_to_fetch]:
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
                msg = f"✅ The number is ready\n\n"
                for idx, num_data in enumerate(found_numbers[:num_to_fetch]):
                    msg += f"📞 Number {idx+1 if num_to_fetch > 1 else ''} : <code>{num_data['number']}</code>\n"
                msg += f"{emoji} COUNTRY : {main_country}\n🏷️ Range   : <code>{prefix}</code>\n\n<b>🤖 Waiting for OTP</b>"

            kb = {"inline_keyboard": [
                [{"text": "🔄 Change 1 Number", "callback_data": f"change_num:1:{prefix}"}],
                [{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}, {"text": "🌐 Change Range", "callback_data": "getnum"}]
            ]}
            tg_edit(user_id, msg_id, msg, kb)
        except Exception as e:
            tg_edit(user_id, msg_id, f"❌ Error: {str(e)[:50]}")

# --- BROADCAST ---
async def tg_broadcast(message_text, admin_id):
    users = list(load_users())
    tg_send(admin_id, f"🔄 Memulai siaran ke {len(users)} user...")
    for u in users:
        tg_send(u, message_text)
        await asyncio.sleep(0.05)
    tg_send(admin_id, "✅ Selesai.")

# --- TELEGRAM LOOP ---
async def telegram_loop(browser_context):
    global verified_users, waiting_admin_input, manual_range_input, get10_range_input, waiting_broadcast_input
    verified_users = load_users()
    offset = 0
    while True:
        try:
            r = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 5}).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                if "message" in upd:
                    msg = upd["message"]; chat_id = msg["chat"]["id"]; user_id = msg["from"]["id"]
                    text = msg.get("text", ""); fn = msg["from"].get("first_name", "User"); un = msg["from"].get("username")

                    if user_id == ADMIN_ID:
                        if text == "/add":
                            waiting_admin_input.add(user_id)
                            tg_send(user_id, "Kirim range: <code>range > country</code>")
                            continue
                        elif text == "/info":
                            waiting_broadcast_input.add(user_id)
                            tg_send(user_id, "Kirim pesan siaran atau <code>.batal</code>")
                            continue
                        elif text.startswith("/get10akses "):
                            tid = text.split(" ")[1]
                            save_akses_get10(tid)
                            tg_send(user_id, f"✅ Akses /get10 diberikan ke {tid}")
                            continue

                    if text == "/get10" and has_get10_access(user_id):
                        get10_range_input.add(user_id)
                        pending_message[user_id] = tg_send(user_id, "Kirim range untuk 10 nomor:")
                        continue

                    if user_id in waiting_broadcast_input:
                        waiting_broadcast_input.remove(user_id)
                        if text.lower() != ".batal": await tg_broadcast(text, user_id)
                        continue

                    if user_id in waiting_admin_input:
                        waiting_admin_input.remove(user_id)
                        new_ranges = []
                        for line in text.strip().split('\n'):
                            if ' > ' in line:
                                p = line.split(' > '); r_px = p[0].strip(); c_nm = p[1].strip().upper()
                                new_ranges.append({"range": r_px, "country": c_nm, "emoji": GLOBAL_COUNTRY_EMOJI.get(c_nm, "🗺️")})
                        if new_ranges: save_inline_ranges(new_ranges); tg_send(user_id, "✅ Saved.")
                        continue

                    is_man = re.match(r"^\+?\d{3,15}[Xx*#]+$", text.strip(), re.IGNORECASE)
                    if user_id in get10_range_input:
                        get10_range_input.remove(user_id)
                        if is_man: await process_user_input(browser_context, user_id, text.strip(), 10, un, fn, pending_message.pop(user_id))
                        continue

                    if is_man and user_id in verified_users:
                        await process_user_input(browser_context, user_id, text.strip(), 1, un, fn)
                        continue

                    if text == "/start":
                        if is_user_in_both_groups(user_id):
                            verified_users.add(user_id); save_users(user_id)
                            tg_send(user_id, f"✅ Verifikasi Berhasil!", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}]]})
                        else:
                            kb = {"inline_keyboard": [[{"text": "📌 Grup 1", "url": GROUP_LINK_1}],[{"text": "📌 Grup 2", "url": GROUP_LINK_2}],[{"text": "✅ Verifikasi", "callback_data": "verify"}]]}
                            tg_send(user_id, "Silakan gabung grup:", kb)

                elif "callback_query" in upd:
                    cq = upd["callback_query"]; user_id = cq["from"]["id"]; data_cb = cq["data"]
                    chat_id = cq["message"]["chat"]["id"]; mid = cq["message"]["message_id"]
                    un = cq["from"].get("username"); fn = cq["from"].get("first_name", "User")

                    if data_cb == "getnum" and user_id in verified_users:
                        ranges = load_inline_ranges()
                        kb = generate_inline_keyboard(ranges)
                        tg_edit(chat_id, mid, "<b>Get Number</b>", kb)
                    elif data_cb == "manual_range":
                        manual_range_input.add(user_id); pending_message[user_id] = mid
                        tg_edit(chat_id, mid, "Kirim Range manual:")
                    elif data_cb.startswith("select_range:"):
                        await process_user_input(browser_context, user_id, data_cb.split(":")[1], 1, un, fn, mid)
                    elif data_cb.startswith("change_num:"):
                        p = data_cb.split(":"); tg_delete(chat_id, mid)
                        await process_user_input(browser_context, user_id, p[2], int(p[1]), un, fn)
                    elif data_cb == "verify":
                        if is_user_in_both_groups(user_id):
                            verified_users.add(user_id); save_users(user_id)
                            tg_edit(chat_id, mid, "✅ Berhasil!", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}]]})
        except: await asyncio.sleep(1)

async def main():
    for f, c in {USER_FILE:"[]", CACHE_FILE:"[]", INLINE_RANGE_FILE:"[]", WAIT_FILE:"[]", AKSES_GET10_FILE:"[]"}.items():
        if not os.path.exists(f): 
            with open(f, "w") as x: x.write(c)
    
    # Start sms.py background
    subprocess.Popen([sys.executable, "sms.py"])
    
    async with async_playwright() as p:
        # headless=False untuk RDP agar bisa lihat loginnya pertama kali
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        # Jalankan login di awal
        await auto_login_mnit(context)
        
        print("[INFO] Bot is Running...")
        await telegram_loop(context)

if __name__ == "__main__":
    asyncio.run(main())
