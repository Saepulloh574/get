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

# --- KONFIGURASI LEVEL 2 (UBAH DISINI) ---
EMAIL_MNIT = "muhamadreyhan0073@gmail.com"
PASS_MNIT = "fd140206"
# -----------------------------------------

# --- ASYNCIO LOCK UNTUK ANTRIAN ---
playwright_lock = asyncio.Lock()
shared_page = None 

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

# --- PROGRESS BAR GLOBAL ---
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
    filled_count = math.ceil(progress_ratio * 12)
    empty_count = 12 - filled_count
    progress_bar = "█" * filled_count + "░" * empty_count
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
USER_FILE = "user.json"; CACHE_FILE = "cache.json"; INLINE_RANGE_FILE = "inline.json"
WAIT_FILE = "wait.json"; AKSES_GET10_FILE = "aksesget10.json"
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1"; GROUP_LINK_2 = "https://t.me/zura14g" 

# --- VARIABEL GLOBAL BOT ---
verified_users = set(); waiting_admin_input = set(); manual_range_input = set()
get10_range_input = set(); pending_message = {}; waiting_broadcast_input = set(); broadcast_message = {}

# --- FUNGSI UTILITAS FILE ---
def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f: return set(json.load(f))
    return set()

def save_users(user_id):
    users = load_users(); users.add(user_id)
    with open(USER_FILE, "w") as f: json.dump(list(users), f, indent=2)

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f: return json.load(f)
    return []

def save_cache(entry):
    cache = load_cache(); cache.append(entry)
    if len(cache) > 1000: cache.pop(0)
    with open(CACHE_FILE, "w") as f: json.dump(cache, f, indent=2)

def is_in_cache(number):
    num = normalize_number(number)
    return any(normalize_number(e["number"]) == num for e in load_cache())

def load_inline_ranges():
    if os.path.exists(INLINE_RANGE_FILE):
        with open(INLINE_RANGE_FILE, "r") as f: return json.load(f)
    return []

def save_inline_ranges(ranges):
    with open(INLINE_RANGE_FILE, "w") as f: json.dump(ranges, f, indent=2)

def load_wait_list():
    if os.path.exists(WAIT_FILE):
        with open(WAIT_FILE, "r") as f: return json.load(f)
    return []

def save_wait_list(data):
    with open(WAIT_FILE, "w") as f: json.dump(data, f, indent=2)

def add_to_wait_list(number, user_id, username, first_name):
    wait_list = load_wait_list(); num = normalize_number(number)
    identity = f"@{username}" if username and username != "None" else f'<a href="tg://user?id={user_id}">{first_name}</a>'
    wait_list = [i for i in wait_list if i['number'] != num]
    wait_list.append({"number": num, "user_id": user_id, "username": identity, "timestamp": time.time()})
    save_wait_list(wait_list)

def normalize_number(number):
    n = str(number).strip().replace(" ", "").replace("-", "")
    return "+" + n if n.isdigit() and not n.startswith("+") else n

def has_get10_access(user_id):
    if user_id == ADMIN_ID: return True
    if os.path.exists(AKSES_GET10_FILE):
        with open(AKSES_GET10_FILE, "r") as f: return user_id in json.load(f)
    return False

# --- TG UTILS ---
def tg_send(chat_id, text, kb=None):
    res = requests.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "reply_markup": kb}).json()
    return res["result"]["message_id"] if res.get("ok") else None

def tg_edit(chat_id, mid, text, kb=None):
    requests.post(f"{API}/editMessageText", json={"chat_id": chat_id, "message_id": mid, "text": text, "parse_mode": "HTML", "reply_markup": kb})

def tg_delete(chat_id, mid):
    requests.post(f"{API}/deleteMessage", json={"chat_id": chat_id, "message_id": mid})

def is_user_in_both_groups(user_id):
    def check(gid):
        r = requests.get(f"{API}/getChatMember", params={"chat_id": gid, "user_id": user_id}).json()
        return r.get("ok") and r["result"]["status"] in ["member", "administrator", "creator"]
    return check(GROUP_ID_1) and check(GROUP_ID_2)

# --- LEVEL 2 ENGINE (API DIRECT) ---
class MNIT_API:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
        self.is_logged_in = False

    async def login(self):
        print("[TERMINAL] Mencoba Login ke MNIT Network...")
        try:
            resp = await self.client.post("https://x.mnitnetwork.com/mauth/login", data={"email": EMAIL_MNIT, "password": PASS_MNIT})
            if "mdashboard" in str(resp.url) or resp.status_code == 200:
                print(f"[TERMINAL] ✅ LOGIN BERHASIL! Menuju: {resp.url}")
                self.is_logged_in = True
                return True
            print(f"[TERMINAL] ❌ LOGIN GAGAL! Redirect ke: {resp.url}")
            return False
        except Exception as e:
            print(f"[TERMINAL] ❌ ERROR LOGIN: {e}")
            return False

    async def order(self, prefix, count):
        for _ in range(count):
            await self.client.get(f"https://x.mnitnetwork.com/mdashboard/getnum?range={prefix}", headers={"X-Requested-With": "XMLHttpRequest"})

    async def fetch_info(self):
        r = await self.client.get("https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info?page=1", headers={"X-Requested-With": "XMLHttpRequest"})
        return r.json() if r.status_code == 200 else None

mnit_engine = MNIT_API()

# --- CORE PROCESSOR ---
async def process_user_input(user_id, prefix, count, username, fname, mid=None):
    if not mid: mid = tg_send(user_id, get_progress_message(0, 0, prefix, count))
    else: tg_edit(user_id, mid, get_progress_message(0, 0, prefix, count))

    if not mnit_engine.is_logged_in: await mnit_engine.login()

    tg_edit(user_id, mid, get_progress_message(3, 0, prefix, count))
    await mnit_engine.order(prefix, count)
    
    await asyncio.sleep(2)
    tg_edit(user_id, mid, get_progress_message(5, 0, prefix, count))
    
    data = await mnit_engine.fetch_info()
    if not data or not data.get("data"):
        tg_edit(user_id, mid, "❌ Gagal mengambil nomor. Range mungkin salah atau habis.")
        return

    found = []
    for item in data["data"]:
        num = normalize_number(item["number"])
        if not is_in_cache(num):
            found.append({"number": num, "country": item.get("country_name", "UNKNOWN").upper()})
            if len(found) >= count: break

    if not found:
        tg_edit(user_id, mid, "❌ Nomor tidak ditemukan/sudah terpakai.")
        return

    tg_edit(user_id, mid, get_progress_message(12, 0, prefix, count))
    
    for e in found:
        save_cache({"number": e['number'], "country": e['country'], "user_id": user_id, "time": time.time()})
        add_to_wait_list(e['number'], user_id, username, fname)

    country = found[0]['country']; emoji = GLOBAL_COUNTRY_EMOJI.get(country, "🗺️")
    
    if count == 10:
        msg = f"✅The number is already.\n\n<code>" + "\n".join([x['number'] for x in found]) + "</code>"
    else:
        nums_text = "\n".join([f"📞 Number {i+1} : <code>{n['number']}</code>" for i, n in enumerate(found)])
        msg = f"✅ The number is ready\n\n{nums_text}\n{emoji} COUNTRY : {country}\n🏷️ Range : <code>{prefix}</code>\n\n<b>🤖 Number available please use, Waiting for OTP</b>"

    kb = {"inline_keyboard": [[{"text": "🔄 Change 1 Number", "callback_data": f"change_num:1:{prefix}"}],[{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}, {"text": "🌐 Change Range", "callback_data": "getnum"}]]}
    tg_edit(user_id, mid, msg, kb)

# --- TELEGRAM LOOP ---
async def telegram_loop():
    global verified_users; offset = 0
    verified_users = load_users()
    while True:
        try:
            updates = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 10}).json()
            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1
                if "message" in upd:
                    m = upd["message"]; uid = m["from"]["id"]; txt = m.get("text", ""); fn = m["from"].get("first_name", "User"); un = m["from"].get("username")
                    mention = f"<a href='tg://user?id={uid}'>{fn}</a>"

                    if uid == ADMIN_ID:
                        if txt.startswith("/add"):
                            waiting_admin_input.add(uid); pending_message[uid] = tg_send(uid, "Kirim format: <code>range > country</code>")
                            continue
                        elif txt == "/info":
                            waiting_broadcast_input.add(uid); broadcast_message[uid] = tg_send(uid, "Kirim pesan siaran atau <code>.batal</code>")
                            continue

                    if txt == "/get10":
                        if has_get10_access(uid):
                            get10_range_input.add(uid); pending_message[uid] = tg_send(uid, "kirim range contoh 225071606XXX")
                        else: tg_send(uid, "❌ No Access.")
                        continue

                    if uid in get10_range_input:
                        get10_range_input.remove(uid); await process_user_input(uid, txt.strip(), 10, un, fn, pending_message.pop(uid, None))
                        continue

                    if uid in manual_range_input or (uid in verified_users and re.match(r"^\+?\d{3,15}[Xx*#]+$", txt.strip())):
                        manual_range_input.discard(uid); await process_user_input(uid, txt.strip(), 1, un, fn, pending_message.pop(uid, None))
                        continue

                    if txt == "/start":
                        if is_user_in_both_groups(uid):
                            verified_users.add(uid); save_users(uid)
                            tg_send(uid, f"✅ Verifikasi Berhasil, {mention}!", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}]]})
                        else:
                            tg_send(uid, f"Halo {mention} 👋\nHarap gabung grup untuk verifikasi:", {"inline_keyboard": [[{"text": "📌 Grup 1", "url": GROUP_LINK_1}],[{"text": "📌 Grup 2", "url": GROUP_LINK_2}],[{"text": "✅ Verifikasi", "callback_data": "verify"}]]})
                        continue

                if "callback_query" in upd:
                    cq = upd["callback_query"]; uid = cq["from"]["id"]; data = cq["data"]; mid = cq["message"]["message_id"]; fn = cq["from"].get("first_name"); un = cq["from"].get("username")
                    
                    if data == "verify":
                        if is_user_in_both_groups(uid):
                            verified_users.add(uid); save_users(uid)
                            tg_edit(uid, mid, "✅ Berhasil!", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}]]})
                        continue
                    if data == "getnum":
                        ranges = load_inline_ranges(); kb_list = []
                        for r in ranges: kb_list.append([{"text": f"{r['country']} {r['emoji']}", "callback_data": f"select_range:{r['range']}"}])
                        kb_list.append([{"text": "Input Manual Range..🖊️", "callback_data": "manual_range"}])
                        tg_edit(uid, mid, "<b>Pilih salah satu range di bawah atau input manual range, cek range terbaru @ceknewrange</b>", {"inline_keyboard": kb_list})
                        continue
                    if data == "manual_range":
                        manual_range_input.add(uid); pending_message[uid] = mid; tg_edit(uid, mid, "Kirim Range manual:")
                        continue
                    if data.startswith("select_range:"):
                        await process_user_input(uid, data.split(":")[1], 1, un, fn, mid)
                    if data.startswith("change_num:"):
                        p = data.split(":"); tg_delete(uid, mid); await process_user_input(uid, p[2], int(p[1]), un, fn)
        except: await asyncio.sleep(1)

# --- MAIN ---
def init_files():
    for f, c in {USER_FILE:"[]", CACHE_FILE:"[]", INLINE_RANGE_FILE:"[]", WAIT_FILE:"[]", AKSES_GET10_FILE:"[]"}.items():
        if not os.path.exists(f): 
            with open(f, "w") as file: file.write(c)

async def main():
    init_files()
    sms_p = subprocess.Popen([sys.executable, "sms.py"])
    print("[TERMINAL] Bot Standby. Menunggu perintah...")
    try:
        await telegram_loop()
    finally: sms_p.terminate()

if __name__ == "__main__":
    asyncio.run(main())
