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
                self.token = data.get("token") or data.get("data", {}).get("token")
                if self.token:
                    self.headers["mauthtoken"] = self.token
                    print(f"✅ API Login Sukses. Token: {self.token[:10]}...")
                    return True
            print(f"❌ API Login Gagal ({response.status_code}): {response.text}")
            return False
        except Exception as e:
            print(f"❌ API Login Error: {e}")
            return False

    async def get_numbers(self, prefix_range, count=1):
        if not self.token:
            if not await self.login(): return None

        results = []
        try:
            # 1. Order Number
            order_url = f"{BASE_API_URL}/mdashboard/getnum/number"
            payload = {"range": prefix_range, "is_national": False, "remove_plus": False}
            
            for _ in range(count):
                resp = await self.client.post(order_url, json=payload, headers=self.headers)
                if resp.status_code == 401:
                    await self.login()
                    resp = await self.client.post(order_url, json=payload, headers=self.headers)
                await asyncio.sleep(0.3)

            # 2. Ambil Info (Polling)
            today = datetime.now().strftime("%Y-%m-%d")
            info_url = f"{BASE_API_URL}/mdashboard/getnum/info"
            
            for attempt in range(6):
                await asyncio.sleep(2) # Beri waktu sistem MNIT memproses
                info_res = await self.client.get(info_url, params={"date": today, "page": 1}, headers=self.headers)
                
                if info_res.status_code == 200:
                    try:
                        resp_json = info_res.json()
                        # Validasi apakah resp_json adalah dictionary
                        if not isinstance(resp_json, dict):
                            print(f"⚠️ Warning: Response bukan JSON object, melainkan {type(resp_json)}")
                            continue
                            
                        rows = resp_json.get("data", [])
                        if not isinstance(rows, list): rows = []

                        for row in rows:
                            raw_num = row.get("phone_number")
                            if not raw_num: continue
                            
                            num = normalize_number(raw_num)
                            if not is_in_cache(num):
                                results.append({
                                    "number": num,
                                    "country": str(row.get("country_name", "UNKNOWN")).upper()
                                })
                                if len(results) >= count: break
                        
                        if len(results) >= count: break
                    except Exception as json_err:
                        print(f"⚠️ JSON Parse Error: {json_err}")
                else:
                    print(f"⚠️ Info API Error {info_res.status_code}")
            
            return results if results else None
        except Exception as e:
            print(f"❌ API get_numbers Error: {e}")
            return None

mnit_api = MnitAPI()

# --- UTILS ---
# Pastikan list emoji ini lengkap agar tidak muncul Map Emoji terus
GLOBAL_COUNTRY_EMOJI = {
    "INDONESIA": "🇮🇩", "MALAYSIA": "🇲🇾", "USA": "🇺🇸", "UKRAINE": "🇺🇦", 
    "VIETNAM": "🇻🇳", "THAILAND": "🇹🇭", "PHILIPPINES": "🇵🇭"
}

def normalize_number(number):
    if not number: return ""
    num = str(number).strip().replace(" ", "").replace("-", "")
    if num.isdigit() and not num.startswith('+'):
        return '+' + num
    return num

def load_users():
    if not os.path.exists(USER_FILE): return set()
    try:
        with open(USER_FILE, "r") as f: return set(json.load(f))
    except: return set()

def save_users(user_id):
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        with open(USER_FILE, "w") as f: json.dump(list(users), f)

def is_in_cache(number):
    if not os.path.exists(CACHE_FILE): return False
    try:
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
            return any(item.get('number') == number for item in cache)
    except: return False

def save_cache(entry):
    data = []
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f: data = json.load(f)
        except: data = []
    
    data.append(entry)
    if len(data) > 1000: data.pop(0)
    with open(CACHE_FILE, "w") as f: json.dump(data, f, indent=2)

def load_inline_ranges():
    if not os.path.exists(INLINE_RANGE_FILE): return []
    try:
        with open(INLINE_RANGE_FILE, "r") as f: return json.load(f)
    except: return []

# --- TELEGRAM ACTIONS ---
def tg_send(chat_id, text, reply_markup=None):
    url = f"{API_TG}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "reply_markup": reply_markup}
    try:
        r = requests.post(url, json=payload).json()
        return r.get("result", {}).get("message_id")
    except: return None

def tg_edit(chat_id, message_id, text, reply_markup=None):
    url = f"{API_TG}/editMessageText"
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML", "reply_markup": reply_markup}
    try: requests.post(url, json=payload)
    except: pass

def is_user_in_both_groups(user_id):
    if user_id == ADMIN_ID: return True
    def check(gid):
        try:
            r = requests.get(f"{API_TG}/getChatMember", params={"chat_id": gid, "user_id": user_id}).json()
            return r.get("result", {}).get("status") in ["member", "administrator", "creator"]
        except: return False
    return check(GROUP_ID_1) and check(GROUP_ID_2)

# --- CORE LOGIC ---
async def process_user_input(user_id, prefix, count, username, first_name, edit_mid=None):
    mid = edit_mid or tg_send(user_id, "<code>⏳ Menghubungkan ke API MNIT...</code>")
    tg_edit(user_id, mid, f"<code>🚀 Membeli {count} nomor (Range: {prefix})...</code>")
    
    found_data = await mnit_api.get_numbers(prefix, count)
    
    if not found_data:
        tg_edit(user_id, mid, "❌ <b>Gagal!</b>\nNomor tidak ditemukan dalam 10 detik atau saldo/limit bermasalah.")
        return

    # Success Logic
    for item in found_data:
        save_cache({"number": item['number'], "country": item['country'], "user_id": user_id, "time": time.time()})

    main_country = found_data[0]['country']
    emoji = GLOBAL_COUNTRY_EMOJI.get(main_country, "🗺️")
    
    msg = f"✅ <b>Nomor Berhasil!</b>\n\n"
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
    print("[RUN] Loop Telegram Aktif.")
    while True:
        try:
            resp = requests.get(f"{API_TG}/getUpdates", params={"offset": offset, "timeout": 20}).json()
            if not resp.get("ok"): 
                await asyncio.sleep(2)
                continue

            for upd in resp.get("result", []):
                offset = upd["update_id"] + 1
                
                if "message" in upd:
                    msg = upd["message"]
                    uid = msg["from"]["id"]
                    text = msg.get("text", "")
                    
                    if text == "/start":
                        if is_user_in_both_groups(uid):
                            save_users(uid)
                            tg_send(uid, "✅ Selamat datang! Verifikasi berhasil.", {"inline_keyboard": [[{"text": "📲 Ambil Nomor", "callback_data": "getnum"}]]})
                        else:
                            tg_send(uid, "❌ Anda harus bergabung di grup kami untuk menggunakan bot ini.", {"inline_keyboard": [[{"text": "Grup 1", "url": GROUP_LINK_1}],[{"text": "Grup 2", "url": GROUP_LINK_2}]]})
                    
                    elif text == "/getnum" or text == "📲 Ambil Nomor":
                        if not is_user_in_both_groups(uid): continue
                        ranges = load_inline_ranges()
                        if not ranges:
                            tg_send(uid, "⚠️ Belum ada range yang dikonfigurasi admin.")
                            continue
                        kb = [[{"text": f"{r['country']} {r['emoji']}", "callback_data": f"select_range:{r['range']}"}] for r in ranges]
                        tg_send(uid, "<b>Silahkan pilih range:</b>", {"inline_keyboard": kb})

                    elif re.match(r"^\+?\d{5,15}[Xx*#]+$", text):
                        if is_user_in_both_groups(uid):
                            await process_user_input(uid, text.strip(), 1, msg["from"].get("username"), msg["from"].get("first_name"))

                if "callback_query" in upd:
                    cq = upd["callback_query"]
                    uid = cq["from"]["id"]
                    data = cq["data"]
                    mid = cq["message"]["message_id"]

                    if data == "getnum":
                        ranges = load_inline_ranges()
                        kb = [[{"text": f"{r['country']} {r['emoji']}", "callback_data": f"select_range:{r['range']}"}] for r in ranges]
                        tg_edit(uid, mid, "<b>Silahkan pilih range:</b>", {"inline_keyboard": kb})
                    
                    elif data.startswith("select_range:"):
                        pref = data.split(":")[1]
                        await process_user_input(uid, uid, 1, cq["from"].get("username"), cq["from"].get("first_name"), edit_mid=mid)

        except Exception as e:
            print(f"Loop Error: {e}")
            await asyncio.sleep(5)
        await asyncio.sleep(0.2)

async def main():
    print("[INFO] Bot API Mode Started...")
    # Initialize files
    for f in [USER_FILE, CACHE_FILE, INLINE_RANGE_FILE]:
        if not os.path.exists(f):
            with open(f, "w") as file: file.write("[]")
            
    success = await mnit_api.login()
    if success:
        await telegram_loop()
    else:
        print("[FATAL] Tidak bisa lanjut tanpa login API.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[OFF] Bot dihentikan.")
