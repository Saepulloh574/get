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

# --- KONFIGURASI LOGIN ---
EMAIL_MNIT = "muhamadreyhan0073@gmail.com"
PASS_MNIT = "fd140206"
TARGET_URL = "https://x.mnitnetwork.com/mdashboard/getnum"

# --- DATA GLOBAL EMOJI ---
GLOBAL_COUNTRY_EMOJI = {
  "AFGHANISTAN": "🇦🇫", "ALBANIA": "🇦🇱", "ALGERIA": "🇩🇿", "ANDORRA": "🇦🇩", "ANGOLA": "🇦🇴",
  "ARGENTINA": "🇦🇷", "AUSTRALIA": "🇦🇺", "AUSTRIA": "🇦🇹", "BRAZIL": "🇧🇷", "CHINA": "🇨🇳",
  "INDIA": "🇮🇳", "INDONESIA": "🇮🇩", "MALAYSIA": "🇲🇾", "RUSSIA": "🇷🇺", "USA": "🇺🇸", "UNKNOWN": "🗺️"
}

# --- PROGRESS BAR ---
STATUS_MAP = {
    0:  "Menunggu di antrian sistem aktif..",
    3:  "Mengirim permintaan nomor baru go.",
    5:  "Mencari nomor pada siklus satu run",
    12: "Nomor ditemukan memproses data fin"
}

def get_progress_message(current_step, total_steps, prefix_range, num_count):
    progress_ratio = min(current_step / 12, 1.0)
    filled_count = math.ceil(progress_ratio * 12)
    progress_bar = "█" * filled_count + "░" * (12 - filled_count)
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

# --- KONSTANTA FILE ---
USER_FILE = "user.json"; CACHE_FILE = "cache.json"; INLINE_RANGE_FILE = "inline.json"
WAIT_FILE = "wait.json"; AKSES_GET10_FILE = "aksesget10.json"
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1"; GROUP_LINK_2 = "https://t.me/zura14g" 

# --- GLOBAL VAR ---
verified_users = set(); manual_range_input = set(); get10_range_input = set(); pending_message = {}

# --- FUNGSI MANAJEMEN FILE ---
def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f: return set(json.load(f))
    return set()

def save_users(user_id):
    users = load_users(); users.add(user_id)
    with open(USER_FILE, "w") as f: json.dump(list(users), f, indent=2)

def normalize_number(number):
    n = str(number).strip().replace(" ", "").replace("-", "")
    return "+" + n if n.isdigit() and not n.startswith("+") else n

def add_to_wait_list(number, user_id, username, first_name):
    wait_list = []
    if os.path.exists(WAIT_FILE):
        with open(WAIT_FILE, "r") as f: wait_list = json.load(f)
    num = normalize_number(number)
    identity = f"@{username}" if username and username != "None" else f'<a href="tg://user?id={user_id}">{first_name}</a>'
    wait_list = [i for i in wait_list if i['number'] != num]
    wait_list.append({"number": num, "user_id": user_id, "username": identity, "timestamp": time.time()})
    with open(WAIT_FILE, "w") as f: json.dump(wait_list, f, indent=2)

# --- TG UTILS ---
def tg_send(chat_id, text, kb=None):
    res = requests.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "reply_markup": kb}).json()
    return res["result"]["message_id"] if res.get("ok") else None

def tg_send_photo(chat_id, photo_path, caption):
    with open(photo_path, 'rb') as photo:
        requests.post(f"{API}/sendPhoto", params={"chat_id": chat_id, "caption": caption}, files={"photo": photo})

def tg_edit(chat_id, mid, text, kb=None):
    requests.post(f"{API}/editMessageText", json={"chat_id": chat_id, "message_id": mid, "text": text, "parse_mode": "HTML", "reply_markup": kb})

def tg_delete(chat_id, mid):
    requests.post(f"{API}/deleteMessage", json={"chat_id": chat_id, "message_id": mid})

def is_user_in_both_groups(user_id):
    def check(gid):
        r = requests.get(f"{API}/getChatMember", params={"chat_id": gid, "user_id": user_id}).json()
        return r.get("ok") and r["result"]["status"] in ["member", "administrator", "creator"]
    return check(GROUP_ID_1) and check(GROUP_ID_2)

# --- ENGINE LEVEL 2 ---
class MNIT_Engine:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=20.0, follow_redirects=True)
        self.is_logged_in = False

    async def auto_login_with_screenshot(self):
        print("[TERMINAL] Menjalankan Playwright untuk Login...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto("https://x.mnitnetwork.com/mauth/login")
                await page.fill("input[name='email']", EMAIL_MNIT)
                await page.fill("input[name='password']", PASS_MNIT)
                await page.click("button[type='submit']")
                await page.wait_for_load_state("networkidle")
                
                # Cek URL Setelah Login
                current_url = page.url
                screenshot_path = "login_status.png"
                await page.screenshot(path=screenshot_path)

                if TARGET_URL in current_url:
                    print(f"[TERMINAL] ✅ LOGIN BERHASIL: {current_url}")
                    self.is_logged_in = True
                    # Ambil cookies dari playwright untuk dipindah ke httpx
                    cookies = await page.context.cookies()
                    for cookie in cookies:
                        self.client.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
                    tg_send_photo(ADMIN_ID, screenshot_path, "✅ <b>LOGIN BERHASIL</b>\nBot sudah masuk ke Dashboard GetNum.")
                    return True
                else:
                    print(f"[TERMINAL] ❌ LOGIN GAGAL: Redirect ke {current_url}")
                    tg_send_photo(ADMIN_ID, screenshot_path, f"❌ <b>LOGIN GAGAL</b>\nURL nyasar ke: {current_url}")
                    return False
            except Exception as e:
                print(f"[TERMINAL] ❌ ERROR: {e}")
                return False
            finally:
                await browser.close()

    async def process(self, uid, prefix, count, un, fn, mid):
        if not self.is_logged_in: await self.auto_login_with_screenshot()
        
        tg_edit(uid, mid, get_progress_message(3, 0, prefix, count))
        for _ in range(count):
            await self.client.get(f"{TARGET_URL}?range={prefix}", headers={"X-Requested-With": "XMLHttpRequest"})
        
        await asyncio.sleep(2)
        r = await self.client.get("https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info?page=1", headers={"X-Requested-With": "XMLHttpRequest"})
        data = r.json() if r.status_code == 200 else None
        
        if not data or not data.get("data"):
            tg_edit(uid, mid, "❌ Gagal ambil nomor.")
            return

        found = []
        for item in data["data"][:count]:
            found.append({"number": normalize_number(item["number"]), "country": item.get("country_name", "UNKNOWN").upper()})

        tg_edit(uid, mid, get_progress_message(12, 0, prefix, count))
        for e in found: add_to_wait_list(e['number'], uid, un, fn)

        nums_text = "\n".join([f"📞 Number {i+1} : <code>{n['number']}</code>" for i, n in enumerate(found)])
        kb = {"inline_keyboard": [[{"text": "🔄 Change 1 Number", "callback_data": f"change_num:1:{prefix}"}],[{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}, {"text": "🌐 Change Range", "callback_data": "getnum"}]]}
        tg_edit(uid, mid, f"✅ The number is ready\n\n{nums_text}\n🏷️ Range : <code>{prefix}</code>\n\n<b>🤖 Waiting for OTP</b>", kb)

bot_engine = MNIT_Engine()

# --- LOOP TELEGRAM ---
async def telegram_loop():
    global verified_users; offset = 0
    verified_users = load_users()
    while True:
        try:
            updates = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 10}).json()
            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1
                if "message" in upd:
                    m = upd["message"]; uid = m["from"]["id"]; txt = m.get("text", ""); fn = m["from"].get("first_name"); un = m["from"].get("username")
                    
                    if txt == "/start":
                        if is_user_in_both_groups(uid):
                            verified_users.add(uid); save_users(uid)
                            tg_send(uid, f"✅ Verifikasi Berhasil, <a href='tg://user?id={uid}'>{fn}</a>!", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}]]})
                        else:
                            tg_send(uid, "Gabung grup dulu:", {"inline_keyboard": [[{"text": "📌 Grup 1", "url": GROUP_LINK_1}],[{"text": "📌 Grup 2", "url": GROUP_LINK_2}],[{"text": "✅ Verifikasi", "callback_data": "verify"}]]})
                    
                    elif re.match(r"^\+?\d{3,15}[Xx*#]+$", txt.strip()) and uid in verified_users:
                        mid = tg_send(uid, get_progress_message(0, 0, txt, 1))
                        await bot_engine.process(uid, txt.strip(), 1, un, fn, mid)

                elif "callback_query" in upd:
                    cq = upd["callback_query"]; uid = cq["from"]["id"]; data = cq["data"]; mid = cq["message"]["message_id"]
                    if data == "getnum":
                        kb = [[{"text": "Input Manual Range..🖊️", "callback_data": "manual_range"}]]
                        tg_edit(uid, mid, "<b>Pilih salah satu range di bawah atau input manual range, cek range terbaru @ceknewrange</b>", {"inline_keyboard": kb})
                    elif data == "manual_range":
                        tg_edit(uid, mid, "Kirim Range manual:")
                    elif data.startswith("change_num:"):
                        p = data.split(":"); tg_delete(uid, mid)
                        new_mid = tg_send(uid, get_progress_message(0, 0, p[2], int(p[1])))
                        await bot_engine.process(uid, p[2], int(p[1]), cq["from"].get("username"), cq["from"].get("first_name"), new_mid)
        except: await asyncio.sleep(1)

async def main():
    # RUN PERTAMA KALI: AUTO LOGIN
    success = await bot_engine.auto_login_with_screenshot()
    if not success:
        print("[TERMINAL] Bot tetap berjalan, akan mencoba login ulang saat ada request.")
    
    sms_p = subprocess.Popen([sys.executable, "sms.py"])
    try:
        await telegram_loop()
    finally: sms_p.terminate()

if __name__ == "__main__":
    asyncio.run(main())
