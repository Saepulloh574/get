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

# STATUS MAP: Disederhanakan sesuai permintaan user (tanpa 1, 2, 15)
STATUS_MAP = {
    0:  "Menunggu di antrian sistem aktif..",
    3:  "Mengirim permintaan nomor baru go.",
    4:  "Memulai pencarian di tabel data..",
    5:  "Mencari nomor pada siklus satu run",
    8:  "Mencoba ulang pada siklus dua wait",
    12: "Nomor ditemukan memproses data fin"
}

def get_progress_message(current_step, total_steps, prefix_range, num_count):
    """Menghasilkan pesan progress bar."""
    progress_ratio = min(current_step / 12, 1.0)
    filled_count = math.ceil(progress_ratio * MAX_BAR_LENGTH)
    empty_count = MAX_BAR_LENGTH - filled_count
    progress_bar = FILLED_CHAR * filled_count + EMPTY_CHAR * empty_count
    
    current_status = STATUS_MAP.get(current_step, "Sedang memproses data...")

    return (
    f"<code>{current_status}</code>\n"
    f"<blockquote>Range: <code>{prefix_range}</code> | Jumlah: <code>{num_count}</code></blockquote>\n"
    f"<code>Load:</code> [{progress_bar}]"
)
# ---------------------------------------------------------


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

# --- FUNGSI TELEGRAM API ---
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

def is_user_in_both_groups(user_id):
    def check(gid):
        try:
            r = requests.get(f"{API}/getChatMember", params={"chat_id": gid, "user_id": user_id}).json()
            return r.get("ok") and r["result"]["status"] in ["member", "administrator", "creator"]
        except: return False
    return check(GROUP_ID_1) and check(GROUP_ID_2)

async def tg_broadcast(message_text, admin_id):
    user_ids = list(load_users())
    tg_send(admin_id, f"🔄 Memulai siaran ke {len(user_ids)} pengguna...")
    for uid in user_ids:
        tg_send(uid, message_text)
        await asyncio.sleep(0.05) 
    tg_send(admin_id, "✅ Siaran Selesai!")

async def action_task(chat_id):
    while True:
        tg_send_action(chat_id) 
        await asyncio.sleep(4.5) 

# --- FUNGSI PLAYWRIGHT ASYNC ---
async def get_number_and_country_from_row(row_selector, page):
    try:
        row = page.locator(row_selector) 
        if not await row.is_visible(): return None, None, None 
        phone_el = row.locator("td:nth-child(1) span.font-mono")
        number_raw = (await phone_el.all_inner_texts())[0].strip()
        number = normalize_number(number_raw)
        if is_in_cache(number): return None, None, None 
        status_text = (await row.locator("td:nth-child(1) div:nth-child(2) span").all_inner_texts())[0].strip().lower()
        if "success" in status_text or "failed" in status_text: return None, None, None
        country = (await row.locator("td:nth-child(2) span.text-slate-200").all_inner_texts())[0].strip().upper()
        return number, country, status_text
    except: return None, None, None

async def get_all_numbers_parallel(page, num_to_fetch):
    tasks = [get_number_and_country_from_row(f"tbody tr:nth-child({i})", page) for i in range(1, num_to_fetch + 4)]
    results = await asyncio.gather(*tasks)
    current_numbers = []
    for num, ctry, st in results:
        if num and num not in [n['number'] for n in current_numbers]:
            current_numbers.append({'number': num, 'country': ctry})
    return current_numbers

async def process_user_input(browser, user_id, prefix, click_count, username_tg, first_name_tg, message_id_to_edit=None):
    global shared_page
    msg_id = message_id_to_edit if message_id_to_edit else pending_message.pop(user_id, None)
    action_loop_task = asyncio.create_task(action_task(user_id))

    if not msg_id:
        msg_id = tg_send(user_id, get_progress_message(0, 0, prefix, click_count))
    else:
        tg_edit(user_id, msg_id, get_progress_message(0, 0, prefix, click_count))

    async with playwright_lock:
        try:
            # 1. Gunakan Tab Standby (Tanpa step 1 & 2 / loading ulang)
            if not shared_page:
                shared_page = await browser.contexts[0].new_page()
                await shared_page.goto(BASE_WEB_URL, wait_until='domcontentloaded')

            # 2. Input Selector Asli
            INPUT_SELECTOR = "input[name='numberrange']"
            await shared_page.fill(INPUT_SELECTOR, prefix)

            # 3. Request Number (Step 3)
            tg_edit(user_id, msg_id, get_progress_message(3, 0, prefix, click_count))
            BUTTON_SELECTOR = "button:has-text('Get Number')" 
            for _ in range(click_count):
                await shared_page.click(BUTTON_SELECTOR, force=True)
            
            # 4. Scanning (Step 4 & 5)
            tg_edit(user_id, msg_id, get_progress_message(5, 0, prefix, click_count))
            found_numbers = []
            for round_num in range(2):
                if round_num == 1 and len(found_numbers) < click_count:
                    tg_edit(user_id, msg_id, get_progress_message(8, 0, prefix, click_count))
                    await shared_page.click(BUTTON_SELECTOR, force=True)
                    await asyncio.sleep(1.5)
                
                for _ in range(15):
                    current_list = await get_all_numbers_parallel(shared_page, click_count)
                    if len(current_list) >= click_count:
                        found_numbers = current_list
                        break
                    await asyncio.sleep(0.3)
                if len(found_numbers) >= click_count: break

            if not found_numbers:
                tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DITEMUKAN. Ganti range.")
                return 

            tg_edit(user_id, msg_id, get_progress_message(12, 0, prefix, click_count))

            # 5. Result Output
            for entry in found_numbers:
                save_cache({"number": entry['number'], "country": entry['country'], "user_id": user_id, "time": time.time()})
                add_to_wait_list(entry['number'], user_id, username_tg, first_name_tg)
            
            emoji = GLOBAL_COUNTRY_EMOJI.get(found_numbers[0]['country'], "🗺️") 
            msg = f"✅ The number is ready\n\n"
            for idx, n in enumerate(found_numbers):
                lbl = f"Number {idx+1}" if click_count > 1 else "Number"
                msg += f"📞 {lbl} : <code>{n['number']}</code>\n"
            
            msg += f"{emoji} COUNTRY : {found_numbers[0]['country']}\n🏷️ Range : <code>{prefix}</code>\n\n<b>🤖 Number available, Waiting for OTP</b>"

            inline_kb = {"inline_keyboard": [
                [{"text": "🔄 Change 1 Number", "callback_data": f"change_num:1:{prefix}"}],
                [{"text": "🔄 Change 3 Number", "callback_data": f"change_num:3:{prefix}"}],
                [{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}, {"text": "🌐 Change Range", "callback_data": "getnum"}]
            ]}
            tg_edit(user_id, msg_id, msg, reply_markup=inline_kb)

        except Exception as e:
            tg_edit(user_id, msg_id, f"❌ Terjadi kesalahan.")
        finally:
            action_loop_task.cancel()

# --- LOOP UTAMA TELEGRAM ---
async def telegram_loop(browser):
    global verified_users, waiting_broadcast_input, manual_range_input, waiting_admin_input
    verified_users = load_users()
    offset = 0
    while True:
        data = tg_get_updates(offset)
        for upd in data.get("result", []):
            offset = upd["update_id"] + 1
            if "message" in upd:
                msg = upd["message"]; chat_id = msg["chat"]["id"]; user_id = msg["from"]["id"]
                text = msg.get("text", ""); username = msg["from"].get("username"); first_name = msg["from"].get("first_name", "User")

                if user_id == ADMIN_ID:
                    if text.startswith("/add"):
                        waiting_admin_input.add(user_id)
                        pending_message[user_id] = tg_send(user_id, "Kirim daftar range: <code>range > country</code>")
                        continue
                    if text == "/info":
                        waiting_broadcast_input.add(user_id)
                        broadcast_message[user_id] = tg_send(user_id, "Kirim pesan siaran (atau .batal):")
                        continue

                if user_id in waiting_admin_input:
                    waiting_admin_input.remove(user_id)
                    nr = []
                    for l in text.strip().split('\n'):
                        if ' > ' in l:
                            p = l.split(' > ', 1); c = p[1].strip().upper()
                            nr.append({"range": p[0].strip(), "country": c, "emoji": GLOBAL_COUNTRY_EMOJI.get(c, "🗺️")})
                    save_inline_ranges(nr); tg_edit(chat_id, pending_message.pop(user_id), f"✅ Tersimpan {len(nr)} range.")
                    continue

                if user_id in waiting_broadcast_input:
                    waiting_broadcast_input.remove(user_id)
                    mid = broadcast_message.pop(user_id)
                    if text.lower() == ".batal": tg_edit(chat_id, mid, "Batal.")
                    else: await tg_broadcast(text, user_id)
                    continue

                is_rng = re.match(r"^\+?\d{3,15}[Xx*#]+$", text.strip())
                if user_id in manual_range_input or (user_id in verified_users and is_rng):
                    if user_id in manual_range_input: manual_range_input.remove(user_id)
                    await process_user_input(browser, user_id, text.strip(), 1, username, first_name)
                    continue

                if text == "/start":
                    if is_user_in_both_groups(user_id):
                        verified_users.add(user_id); save_users(user_id)
                        tg_send(user_id, f"✅ Halo {first_name}, Verifikasi Berhasil!", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}]]})
                    else:
                        tg_send(user_id, "Harap gabung grup dulu:", {"inline_keyboard": [[{"text": "Grup 1", "url": GROUP_LINK_1}],[{"text": "Grup 2", "url": GROUP_LINK_2}],[{"text": "Verifikasi", "callback_data": "verify"}]]})

            elif "callback_query" in upd:
                cq = upd["callback_query"]; user_id = cq["from"]["id"]; data_cb = cq["data"]; chat_id = cq["message"]["chat"]["id"]
                msg_id = cq["message"]["message_id"]; un = cq["from"].get("username"); fn = cq["from"].get("first_name", "User")

                if data_cb == "verify":
                    if is_user_in_both_groups(user_id):
                        verified_users.add(user_id); save_users(user_id)
                        tg_edit(chat_id, msg_id, "✅ Berhasil!", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}]]})
                    else: tg_send(user_id, "❌ Belum gabung.")
                elif data_cb == "getnum" and user_id in verified_users:
                    tg_edit(chat_id, msg_id, "Pilih Range:", generate_inline_keyboard(load_inline_ranges()))
                elif data_cb == "manual_range":
                    manual_range_input.add(user_id); pending_message[user_id] = msg_id
                    tg_edit(chat_id, msg_id, "Kirim range manual:")
                elif data_cb.startswith("select_range:"):
                    await process_user_input(browser, user_id, data_cb.split(":")[1], 1, un, fn, msg_id)
                elif data_cb.startswith("change_num:"):
                    p = data_cb.split(":")
                    tg_delete(chat_id, msg_id)
                    await process_user_input(browser, user_id, p[2], int(p[1]), un, fn)
        await asyncio.sleep(0.05) 

async def expiry_monitor_task():
    while True:
        try:
            wl = load_wait_list(); ct = time.time(); ul = []
            for i in wl:
                if ct - i['timestamp'] > 1200: tg_send(i['user_id'], f"⚠️ <code>{i['number']}</code> Kadaluarsa.")
                else: ul.append(i)
            save_wait_list(ul)
        except: pass
        await asyncio.sleep(10)

async def main():
    global shared_page
    if not os.path.exists(WAIT_FILE):
        with open(WAIT_FILE, "w") as f: f.write("[]")
    sms_p = subprocess.Popen([sys.executable, "sms.py"])
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            shared_page = await browser.contexts[0].new_page()
            await shared_page.goto(BASE_WEB_URL, wait_until='domcontentloaded')
            await asyncio.gather(telegram_loop(browser), expiry_monitor_task())
    except Exception as e: print(e)
    finally: sms_p.terminate()

if __name__ == "__main__":
    asyncio.run(main())
