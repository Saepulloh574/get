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

# --- KONFIGURASI LOGIN MNIT ---
EMAIL_MNIT = "muhamadreyhan0073@gmail.com"
PASS_MNIT = "fd140206"
BASE_URL = "https://x.mnitnetwork.com"
LOGIN_URL = f"{BASE_URL}/mauth/login"
TARGET_URL = f"{BASE_URL}/mdashboard/getnum"
STATE_FILE = "state.json"

# --- ASYNCIO LOCK UNTUK ANTRIAN PLAYWRIGHT ---
playwright_lock = asyncio.Lock()
shared_page = None 

# --- DATA GLOBAL EMOJI NEGARA ---
GLOBAL_COUNTRY_EMOJI = {
  "AFGHANISTAN": "🇦🇫", "ALBANIA": "🇦🇱", "ALGERIA": "🇩🇿", "ANDORRA": "🇦🇩", "ANGOLA": "🇦🇴",
  "ARGENTINA": "🇦🇷", "AUSTRALIA": "🇦🇺", "AUSTRIA": "🇦🇹", "BRAZIL": "🇧🇷", "CANADA": "🇨🇦",
  "CHINA": "🇨🇳", "FRANCE": "🇫🇷", "GERMANY": "🇩🇪", "INDIA": "🇮🇳", "INDONESIA": "🇮🇩",
  "JAPAN": "🇯🇵", "MALAYSIA": "🇲🇾", "RUSSIA": "🇷🇺", "USA": "🇺🇸", "VIETNAM": "🇻🇳", "UNKNOWN": "🗺️" 
}

# --- PROGRESS BAR CONFIG ---
MAX_BAR_LENGTH = 12 
FILLED_CHAR = "█"
EMPTY_CHAR = "░"
STATUS_MAP = {
    0: "Menunggu di antrian sistem aktif..",
    3: "Mengirim permintaan nomor baru go.",
    4: "Memulai pencarian di tabel data..",
    8: "Mencoba ulang pada siklus dua wait",
    12: "Nomor ditemukan memproses data fin"
}

def get_progress_message(current_step, prefix_range, num_count):
    progress_ratio = min(current_step / 12, 1.0)
    filled_count = math.ceil(progress_ratio * MAX_BAR_LENGTH)
    progress_bar = FILLED_CHAR * filled_count + EMPTY_CHAR * (MAX_BAR_LENGTH - filled_count)
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

# --- FILE MANAGEMENT ---
def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            try: return json.load(f) if isinstance(default, list) else set(json.load(f))
            except: return default
    return default

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(list(data) if isinstance(data, set) else data, f, indent=2)

# Global Sets
verified_users = load_json("user.json", set())
waiting_admin_input = set()
manual_range_input = set() 
get10_range_input = set()
pending_message = {}
last_used_range = {}
waiting_broadcast_input = set() 

# --- TG API UTILS ---
def tg_send(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: data["reply_markup"] = reply_markup
    r = requests.post(f"{API}/sendMessage", json=data).json()
    return r["result"]["message_id"] if r.get("ok") else None

def tg_edit(chat_id, message_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: data["reply_markup"] = reply_markup
    requests.post(f"{API}/editMessageText", json=data)

def is_user_in_both_groups(user_id):
    def check(gid):
        r = requests.get(f"{API}/getChatMember", params={"chat_id": gid, "user_id": user_id}).json()
        return r.get("ok") and r["result"]["status"] in ["member", "administrator", "creator"]
    return check(GROUP_ID_1) and check(GROUP_ID_2)

# --- ENGINE LOGIN & AUTO-REDIRECT ---
async def ensure_logged_in(page):
    """Mengecek apakah sesi masih aktif, jika tidak maka login ulang."""
    if "mauth/login" in page.url or await page.locator("input[type='email']").is_visible():
        print("[TERMINAL] Sesi berakhir/Logout terdeteksi. Melakukan Login Ulang...")
        await page.goto(LOGIN_URL)
        await page.fill("input[type='email']", EMAIL_MNIT)
        await page.fill("input[type='password']", PASS_MNIT)
        await page.click("button[type='submit']")
        await page.wait_for_url("**/mdashboard/getnum", timeout=30000)
        await page.context.storage_state(path=STATE_FILE)
        print("[TERMINAL] Login Ulang Berhasil.")
    elif "mdashboard/getnum" not in page.url:
        await page.goto(TARGET_URL)

async def auto_login_mnit(browser_context):
    global shared_page
    print("[TERMINAL] Mencoba Login Otomatis...")
    page = await browser_context.new_page()
    try:
        await page.goto(TARGET_URL, timeout=60000)
        # Jika diarahkan ke login
        if "mauth/login" in page.url:
            await page.fill("input[type='email']", EMAIL_MNIT)
            await page.fill("input[type='password']", PASS_MNIT)
            await page.click("button[type='submit']")
            await page.wait_for_url("**/mdashboard/getnum", timeout=30000)
        
        await asyncio.sleep(2)
        if "mdashboard/getnum" in page.url:
            print("[TERMINAL] ✅ LOGIN BERHASIL")
            await page.context.storage_state(path=STATE_FILE)
            shared_page = page 
            return True
        return False
    except Exception as e:
        print(f"[ERROR] Login: {e}")
        return False

# --- PLAYWRIGHT HELPERS ---
def normalize_number(number):
    if not number: return None
    n = str(number).strip().replace(" ", "").replace("-", "")
    return "+" + n if not n.startswith('+') and n.isdigit() else n

async def get_all_numbers_parallel(page, num_to_fetch):
    current_numbers = []
    rows = await page.locator("tbody tr").all()
    for row in rows[:num_to_fetch + 5]:
        phone_el = row.locator("td:nth-child(1) span.font-mono")
        status_el = row.locator("td:nth-child(1) div:nth-child(2) span")
        country_el = row.locator("td:nth-child(2) span.text-slate-200")
        
        num_raw = await phone_el.inner_text() if await phone_el.count() > 0 else None
        status = await status_el.inner_text() if await status_el.count() > 0 else ""
        country = await country_el.inner_text() if await country_el.count() > 0 else "UNKNOWN"
        
        num = normalize_number(num_raw)
        if num and "success" not in status.lower() and "failed" not in status.lower():
            current_numbers.append({'number': num, 'country': country.strip().upper()})
    return current_numbers

async def process_user_input(browser_context, user_id, prefix, click_count, un, fn, msg_id=None):
    global shared_page
    async with playwright_lock:
        try:
            await ensure_logged_in(shared_page)
            if not msg_id: msg_id = tg_send(user_id, get_progress_message(0, prefix, click_count))
            
            await shared_page.fill("input[name='numberrange']", prefix)
            await shared_page.click("button:has-text('Get Number')", force=True)
            
            tg_edit(user_id, msg_id, get_progress_message(3, prefix, click_count))
            await asyncio.sleep(2) # Tunggu tabel refresh

            found = await get_all_numbers_parallel(shared_page, click_count)
            if not found:
                tg_edit(user_id, msg_id, "❌ Nomor tidak ditemukan dalam range ini.")
                return

            # Result Formatting
            main_country = found[0]['country']
            emoji = GLOBAL_COUNTRY_EMOJI.get(main_country, "🗺️")
            msg = f"✅ The number is ready\n\n"
            for i, item in enumerate(found[:click_count]):
                msg += f"📞 Number {i+1}: <code>{item['number']}</code>\n"
            msg += f"\n{emoji} COUNTRY : {main_country}\n🏷️ Range : <code>{prefix}</code>\n\n<b>🤖 Waiting for OTP</b>"
            
            kb = {"inline_keyboard": [[{"text": "🔄 Change Number", "callback_data": f"change_num:1:{prefix}"}],[{"text": "🔐 OTP Grup", "url": GROUP_ID_1}]]}
            tg_edit(user_id, msg_id, msg, kb)
        except Exception as e:
            tg_edit(user_id, msg_id, f"❌ Error System: {str(e)[:50]}")

# --- TELEGRAM UPDATES ---
async def telegram_loop(context):
    offset = 0
    while True:
        try:
            r = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 10}).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                if "message" in upd:
                    msg = upd["message"]; user_id = msg["from"]["id"]; text = msg.get("text", "")
                    un = msg["from"].get("username"); fn = msg["from"].get("first_name", "User")
                    
                    if text == "/start":
                        if is_user_in_both_groups(user_id):
                            verified_users.add(user_id); save_json("user.json", verified_users)
                            tg_send(user_id, "✅ Akses Aktif. Gunakan /getnum atau ketik range langsung.")
                        else:
                            tg_send(user_id, "Silakan gabung grup untuk verifikasi.")
                    
                    elif re.match(r"^\+?\d{3,15}[Xx*#]+$", text.strip()):
                        await process_user_input(context, user_id, text.strip(), 1, un, fn)

                elif "callback_query" in upd:
                    cq = upd["callback_query"]; data = cq["data"]; user_id = cq["from"]["id"]
                    if data.startswith("change_num:"):
                        p = data.split(":")
                        await process_user_input(context, user_id, p[2], int(p[1]), "un", "fn", cq["message"]["message_id"])
        except: await asyncio.sleep(2)

# --- MAIN RUNNER ---
async def main():
    # Setup Files
    for f in ["user.json", "cache.json", "inline.json", "wait.json"]:
        if not os.path.exists(f): save_json(f, [])

    async with async_playwright() as p:
        # STEP 1: LOGIN DENGAN GUI
        print("[SISTEM] Membuka Browser GUI untuk Login...")
        browser = await p.chromium.launch(headless=False)
        
        # Cek jika ada session lama
        storage = STATE_FILE if os.path.exists(STATE_FILE) else None
        context = await browser.new_context(storage_state=storage)
        
        login_success = await auto_login_mnit(context)
        
        if login_success:
            print("\n" + "="*40)
            pilihan = input("Login Berhasil! Tutup GUI & jalan di latar belakang? (Y/T): ").strip().lower()
            print("="*40 + "\n")
            
            if pilihan == 'y':
                print("[SISTEM] Beralih ke Mode Latar Belakang (Headless)...")
                await context.storage_state(path=STATE_FILE)
                await browser.close()
                
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(storage_state=STATE_FILE)
                # Re-init shared page
                global shared_page
                shared_page = await context.new_page()
                await shared_page.goto(TARGET_URL)
            else:
                print("[SISTEM] Melanjutkan dengan mode GUI.")
        
        print("[INFO] Bot Telegram Aktif...")
        await telegram_loop(context)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Bot dimatikan.")
