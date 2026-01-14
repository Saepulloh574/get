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

# --- KONFIGURASI PROGRESS BAR ---
MAX_BAR_LENGTH = 12 
FILLED_CHAR = "█"
EMPTY_CHAR = "░"

STATUS_MAP = {
    0: "Menunggu di antrian sistem aktif..",
    1: "Mengakses alamat target web aktif.",
    2: "Menunggu pemuatan halaman web on..",
    3: "Mengirim permintaan nomor baru go.",
    4: "Memulai pencarian di tabel data..",
    5: "Mencari nomor pada siklus satu run",
    8: "Mencoba ulang pada siklus dua wait",
    12: "Nomor ditemukan memproses data fin",
    15: "Finalisasi..."
}

def get_progress_message(current_step, total_steps, prefix_range, num_count):
    progress_ratio = min(current_step / 15, 1.0)
    filled_count = math.ceil(progress_ratio * MAX_BAR_LENGTH)
    empty_count = MAX_BAR_LENGTH - filled_count
    progress_bar = FILLED_CHAR * filled_count + EMPTY_CHAR * empty_count
    current_status = STATUS_MAP.get(current_step, STATUS_MAP[1])

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

USER_FILE = "user.json" 
CACHE_FILE = "cache.json"
INLINE_RANGE_FILE = "inline.json"
WAIT_FILE = "wait.json"
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1" 
GROUP_LINK_2 = "https://t.me/zura14g" 

# --- FUNGSI UTILITAS FILE ---
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
    return any(normalize_number(e["number"]) == norm for e in cache)

def load_inline_ranges():
    if os.path.exists(INLINE_RANGE_FILE):
        with open(INLINE_RANGE_FILE, "r") as f:
            try: return json.load(f)
            except: return []
    return []

def save_inline_ranges(ranges):
    with open(INLINE_RANGE_FILE, "w") as f: json.dump(ranges, f, indent=2)

def normalize_number(number):
    n = str(number).strip().replace(" ", "").replace("-", "")
    if not n.startswith('+') and n.isdigit(): n = '+' + n
    return n

# --- TELEGRAM API WRAPPERS ---
def tg_send(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: data["reply_markup"] = reply_markup
    r = requests.post(f"{API}/sendMessage", json=data).json()
    return r["result"]["message_id"] if r.get("ok") else None

def tg_edit(chat_id, message_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: data["reply_markup"] = reply_markup
    requests.post(f"{API}/editMessageText", json=data)

def tg_delete(chat_id, message_id):
    requests.post(f"{API}/deleteMessage", json={"chat_id": chat_id, "message_id": message_id})

async def auto_delete_msg(chat_id, message_id, delay=30):
    await asyncio.sleep(delay)
    tg_delete(chat_id, message_id)

def is_user_in_both_groups(user_id):
    def check(gid):
        r = requests.get(f"{API}/getChatMember", params={"chat_id": gid, "user_id": user_id}).json()
        return r.get("ok") and r["result"]["status"] in ["member", "administrator", "creator"]
    return check(GROUP_ID_1) and check(GROUP_ID_2)

# --- CORE LOGIC ---
async def process_user_input(browser, user_id, prefix, click_count, message_id_to_edit=None):
    msg_id = message_id_to_edit
    page = None
    
    async with playwright_lock:
        try:
            if not msg_id:
                msg_id = tg_send(user_id, get_progress_message(0, 0, prefix, click_count))
            
            context = browser.contexts[0]
            page = await context.new_page()
            await page.goto(f"{BASE_WEB_URL}?range={prefix}", wait_until='domcontentloaded', timeout=20000)
            
            tg_edit(user_id, msg_id, get_progress_message(3, 0, prefix, click_count))
            btn = "button:has-text('Get Number')"
            await page.wait_for_selector(btn, state='visible', timeout=10000)
            for _ in range(click_count): await page.click(btn, force=True)
            
            # Polling Logic (Simplified for brevity)
            await asyncio.sleep(4)
            found_numbers = []
            rows = await page.locator("tbody tr").all()
            for row in rows[:click_count+2]:
                txt = await row.locator("td:nth-child(1) span.font-mono").all_inner_texts()
                if txt:
                    num = normalize_number(txt[0])
                    if not is_in_cache(num):
                        cty = (await row.locator("td:nth-child(2) span.text-slate-200").all_inner_texts())[0].upper()
                        found_numbers.append({'number': num, 'country': cty})
                if len(found_numbers) >= click_count: break

            if not found_numbers:
                tg_edit(user_id, msg_id, "❌ NOMOR TIDAK DITEMUKAN. Coba range lain.")
                return

            # Save & Finalize
            for n in found_numbers: save_cache({"number": n['number'], "country": n['country'], "user_id": user_id, "time": time.time()})
            
            emoji = GLOBAL_COUNTRY_EMOJI.get(found_numbers[0]['country'], "🗺️")
            res_text = f"✅ The number is ready\n\n"
            for i, n in enumerate(found_numbers):
                res_text += f"📞 Number {i+1 if click_count > 1 else ''}: <code>{n['number']}</code>\n"
            
            res_text += f"{emoji} COUNTRY: {found_numbers[0]['country']}\n🏷️ Range: <code>{prefix}</code>\n\n<b>Waiting for OTP....</b>"

            # KEYBOARD BARU (OTP & CHANGE RANGE SEJAJAR)
            inline_kb = {
                "inline_keyboard": [
                    [{"text": "🔄 Change 1 Number", "callback_data": f"change_num:1:{prefix}"}],
                    [{"text": "🔄 Change 3 Number", "callback_data": f"change_num:3:{prefix}"}],
                    [
                        {"text": "🔐 OTP Grup", "url": GROUP_LINK_1},
                        {"text": "🌐 Change Range", "callback_data": "getnum"}
                    ]
                ]
            }
            tg_edit(user_id, msg_id, res_text, reply_markup=inline_kb)

        except Exception as e:
            if msg_id: tg_edit(user_id, msg_id, f"❌ Terjadi kesalahan: {str(e)}")
        finally:
            if page: await page.close()

# --- TELEGRAM LOOP ---
async def telegram_loop(browser):
    verified_users = load_users()
    offset = 0
    while True:
        try:
            updates = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 5}).json()
            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1
                
                if "message" in upd:
                    msg = upd["message"]; uid = msg["from"]["id"]; text = msg.get("text", "")
                    
                    # 1. DETEKSI OTOMATIS RANGE (232XXX)
                    if uid in verified_users and re.match(r"^\+?\d+[Xx*#]+$", text):
                        asyncio.create_task(process_user_input(browser, uid, text.strip(), 1))
                        continue

                    if text == "/start":
                        if is_user_in_both_groups(uid):
                            verified_users.add(uid); save_users(uid)
                            kb = {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}]]}
                            tg_send(uid, "✅ Verifikasi Berhasil!", kb)
                        else:
                            kb = {"inline_keyboard": [[{"text": "📌 Grup 1", "url": GROUP_LINK_1}], [{"text": "📌 Grup 2", "url": GROUP_LINK_2}], [{"text": "✅ Verif", "callback_data": "verify"}]]}
                            tg_send(uid, "Harap join grup dulu:", kb)

                if "callback_query" in upd:
                    cq = upd["callback_query"]; uid = cq["from"]["id"]; data = cq["data"]; mid = cq["message"]["message_id"]
                    
                    if data == "getnum":
                        ranges = load_inline_ranges()
                        btns = [[{"text": f"{r['country']} {r['emoji']}", "callback_data": f"sel:{r['range']}"}] for r in ranges]
                        btns.append([{"text": "Input Manual Range..🖊️", "callback_data": "manual"}])
                        tg_edit(uid, mid, "Pilih Range:", {"inline_keyboard": btns})
                    
                    elif data.startswith("sel:"):
                        prefix = data.split(":")[1]
                        asyncio.create_task(process_user_input(browser, uid, prefix, 1, mid))

                    elif data.startswith("change_num:"):
                        p = data.split(":"); num = int(p[1]); pre = p[2]
                        tg_delete(uid, mid)
                        asyncio.create_task(process_user_input(browser, uid, pre, num))

            await asyncio.sleep(0.5)
        except: continue

# --- LOGIKA KADALUARSA (Integrasi sms.py) ---
# Tambahkan fungsi ini di script pengecek OTP (sms.py) Anda
async def handle_expiry(chat_id, bot_api):
    # Kirim peringatan Kadaluarsa (20 Menit)
    warn_text = "⚠️ <b>Nomor telah kadaluarsa (20 Menit).</b>\nSilahkan ambil nomor baru."
    res = requests.post(f"{bot_api}/sendMessage", json={"chat_id": chat_id, "text": warn_text, "parse_mode": "HTML"}).json()
    if res.get("ok"):
        # Hapus otomatis setelah 30 detik
        asyncio.create_task(auto_delete_msg(chat_id, res["result"]["message_id"], 30))

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        await telegram_loop(browser)

if __name__ == "__main__":
    asyncio.run(main())
