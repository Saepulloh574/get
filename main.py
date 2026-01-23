import asyncio
import json
import os
import requests
import re
import httpx
from datetime import datetime
from dotenv import load_dotenv
import subprocess
import sys
import time
import math

# --- CONFIGURATION & PATHS ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
EMAIL_MNIT = "muhamadreyhan0073@gmail.com"
PASS_MNIT = "fd140206"
BASE_API_URL = "https://x.mnitnetwork.com/mapi/v1"

try:
    GROUP_ID_1 = int(os.getenv("GROUP_ID_1"))
    GROUP_ID_2 = int(os.getenv("GROUP_ID_2"))
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError) as e:
    print(f"[FATAL] Environment variables missing: {e}")
    sys.exit(1)

API_TG = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --- FILE CONSTANTS ---
USER_FILE = "user.json"
CACHE_FILE = "cache.json"
INLINE_RANGE_FILE = "inline.json"
WAIT_FILE = "wait.json"
AKSES_GET10_FILE = "aksesget10.json"
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1"
GROUP_LINK_2 = "https://t.me/zura14g"

# --- GLOBAL VARS ---
verified_users = set()
waiting_broadcast_input = set()
broadcast_message = {}
waiting_admin_input = set()
manual_range_input = set()
get10_range_input = set()
pending_message = {}
last_used_range = {}

# --- API CLASS MNIT ---
class MnitAPI:
    def __init__(self):
        self.token = None
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self.headers = {"accept": "application/json, text/plain, */*"}

    async def login(self):
        url = f"{BASE_API_URL}/mauth/login"
        payload = {"email": EMAIL_MNIT, "password": PASS_MNIT}
        try:
            response = await self.client.post(url, json=payload, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                # Mengambil token dari response
                self.token = data.get("token") or data.get("data", {}).get("token")
                if self.token:
                    self.headers["mauthtoken"] = self.token
                    print(f"✅ API Login Sukses. Token: {self.token[:10]}...")
                    return True
            print(f"❌ API Login Gagal: {response.text}")
            return False
        except Exception as e:
            print(f"❌ API Login Error: {e}")
            return False

    async def get_numbers(self, prefix_range, count=1):
        """Membeli nomor dan mengambil hasilnya"""
        if not self.token:
            if not await self.login(): return None

        results = []
        try:
            # 1. Order Number
            order_url = f"{BASE_API_URL}/mdashboard/getnum/number"
            payload = {"range": prefix_range, "is_national": False, "remove_plus": False}
            
            # Melakukan klik/order sebanyak count
            for _ in range(count):
                resp = await self.client.post(order_url, json=payload, headers=self.headers)
                if resp.status_code == 401: # Expired
                    await self.login()
                    resp = await self.client.post(order_url, json=payload, headers=self.headers)
                await asyncio.sleep(0.2) # Jeda antar request

            # 2. Ambil Info (Polling)
            today = datetime.now().strftime("%Y-%m-%d")
            info_url = f"{BASE_API_URL}/mdashboard/getnum/info"
            
            # Coba polling maksimal 5 kali
            for _ in range(5):
                info_res = await self.client.get(info_url, params={"date": today, "page": 1}, headers=self.headers)
                if info_res.status_code == 200:
                    rows = info_res.json().get("data", [])
                    # Filter nomor yang belum ada di cache dan limit sesuai count
                    for row in rows:
                        num = normalize_number(row.get("phone_number"))
                        if not is_in_cache(num):
                            results.append({
                                "number": num,
                                "country": row.get("country_name", "UNKNOWN").upper()
                            })
                            if len(results) >= count: break
                    if len(results) >= count: break
                await asyncio.sleep(1.5)
            
            return results
        except Exception as e:
            print(f"❌ API Error: {e}")
            return None

mnit_api = MnitAPI()

# --- UTILS (Emoji, Progress, File) ---
GLOBAL_COUNTRY_EMOJI = {"INDONESIA": "🇮🇩", "MALAYSIA": "🇲🇾", "USA": "🇺🇸", "UKRAINE": "🇺🇦"} # Tambahkan list lengkap Anda di sini

def normalize_number(number):
    if not number: return ""
    num = str(number).strip().replace(" ", "").replace("-", "")
    return '+' + num if num.isdigit() and not num.startswith('+') else num

def load_users():
    try:
        with open(USER_FILE, "r") as f: return set(json.load(f))
    except: return set()

def save_users(user_id):
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        with open(USER_FILE, "w") as f: json.dump(list(users), f)

def is_in_cache(number):
    try:
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
            return any(item['number'] == number for item in cache)
    except: return False

def save_cache(entry):
    try:
        with open(CACHE_FILE, "r+") as f:
            data = json.load(f)
            data.append(entry)
            if len(data) > 1000: data.pop(0)
            f.seek(0); json.dump(data, f); f.truncate()
    except:
        with open(CACHE_FILE, "w") as f: json.dump([entry], f)

def load_inline_ranges():
    try:
        with open(INLINE_RANGE_FILE, "r") as f: return json.load(f)
    except: return []

def save_inline_ranges(data):
    with open(INLINE_RANGE_FILE, "w") as f: json.dump(data, f)

# --- TELEGRAM ACTIONS ---
def tg_send(chat_id, text, reply_markup=None):
    url = f"{API_TG}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "reply_markup": reply_markup}
    try: return requests.post(url, json=payload).json().get("result", {}).get("message_id")
    except: return None

def tg_edit(chat_id, message_id, text, reply_markup=None):
    url = f"{API_TG}/editMessageText"
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML", "reply_markup": reply_markup}
    requests.post(url, json=payload)

def is_user_in_both_groups(user_id):
    def check(gid):
        try:
            r = requests.get(f"{API_TG}/getChatMember", params={"chat_id": gid, "user_id": user_id}).json()
            return r.get("result", {}).get("status") in ["member", "administrator", "creator"]
        except: return False
    return check(GROUP_ID_1) and check(GROUP_ID_2)

# --- CORE LOGIC ---
async def process_user_input(user_id, prefix, count, username, first_name, edit_mid=None):
    mid = edit_mid or tg_send(user_id, "<code>⏳ Menghubungkan ke API MNIT...</code>")
    
    # Progress Simulation (Fast via API)
    tg_edit(user_id, mid, "<code>🚀 Mengirim permintaan beli nomor...</code>")
    
    found_data = await mnit_api.get_numbers(prefix, count)
    
    if not found_data:
        tg_edit(user_id, mid, "❌ <b>Gagal mendapatkan nomor.</b>\nAPI tidak merespon atau range salah.")
        return

    # Success Logic
    for item in found_data:
        save_cache({"number": item['number'], "country": item['country'], "user_id": user_id, "time": time.time()})

    main_country = found_data[0]['country']
    emoji = GLOBAL_COUNTRY_EMOJI.get(main_country, "🗺️")
    
    msg = f"✅ <b>Nomor Berhasil Didapatkan!</b>\n\n"
    for idx, item in enumerate(found_data):
        msg += f"📞 No {idx+1}: <code>{item['number']}</code>\n"
    
    msg += f"\n{emoji} Negara: {main_country}\n🏷️ Range: <code>{prefix}</code>"
    
    kb = {"inline_keyboard": [
        [{"text": "🔄 Ganti Nomor", "callback_data": f"select_range:{prefix}"}],
        [{"text": "🌐 Menu Utama", "callback_data": "getnum"}]
    ]}
    
    tg_edit(user_id, mid, msg, reply_markup=kb)

# --- TELEGRAM LOOP ---
async def telegram_loop():
    offset = 0
    while True:
        try:
            resp = requests.get(f"{API_TG}/getUpdates", params={"offset": offset, "timeout": 10}).json()
            for upd in resp.get("result", []):
                offset = upd["update_id"] + 1
                
                # Handle Messages
                if "message" in upd:
                    msg = upd["message"]
                    uid = msg["from"]["id"]
                    text = msg.get("text", "")
                    
                    if text == "/start":
                        if is_user_in_both_groups(uid):
                            save_users(uid)
                            tg_send(uid, "✅ Verifikasi Sukses!", {"inline_keyboard": [[{"text": "📲 Ambil Nomor", "callback_data": "getnum"}]]})
                        else:
                            tg_send(uid, "❌ Gabung grup dulu!", {"inline_keyboard": [[{"text": "Grup 1", "url": GROUP_LINK_1}],[{"text": "Grup 2", "url": GROUP_LINK_2}]]})
                    
                    elif text == "/getnum" or text == "📲 Ambil Nomor":
                        ranges = load_inline_ranges()
                        kb = []
                        for r in ranges: kb.append([{"text": f"{r['country']} {r['emoji']}", "callback_data": f"select_range:{r['range']}"}])
                        tg_send(uid, "<b>Pilih Range:</b>", {"inline_keyboard": kb})

                    # Auto detect manual range pattern (e.g. 62812XXX)
                    elif re.match(r"^\+?\d{5,15}[Xx*#]+$", text):
                        await process_user_input(uid, text.strip(), 1, msg["from"].get("username"), msg["from"].get("first_name"))

                # Handle Callbacks
                if "callback_query" in upd:
                    cq = upd["callback_query"]
                    uid = cq["from"]["id"]
                    data = cq["data"]
                    mid = cq["message"]["message_id"]

                    if data == "getnum":
                        ranges = load_inline_ranges()
                        kb = [[{"text": f"{r['country']} {r['emoji']}", "callback_data": f"select_range:{r['range']}"}] for r in ranges]
                        tg_edit(uid, mid, "<b>Pilih Range:</b>", {"inline_keyboard": kb})
                    
                    elif data.startswith("select_range:"):
                        pref = data.split(":")[1]
                        await process_user_input(uid, pref, 1, cq["from"].get("username"), cq["from"].get("first_name"), edit_mid=mid)

        except Exception as e:
            print(f"Loop Error: {e}")
            await asyncio.sleep(2)
        await asyncio.sleep(0.1)

async def main():
    # Inisialisasi file jika belum ada
    for f in [USER_FILE, CACHE_FILE, INLINE_RANGE_FILE]:
        if not os.path.exists(f):
            with open(f, "w") as file: file.write("[]")
    
    print("[INFO] Bot API Mode Started...")
    await mnit_api.login()
    await telegram_loop()

if __name__ == "__main__":
    asyncio.run(main())
