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

# --- KONFIGURASI LOGIN (LEVEL 2 ENGINE) ---
EMAIL_MNIT = "muhamadreyhan0073@gmail.com"
PASS_MNIT = "fd140206"
LOGIN_URL = "https://x.mnitnetwork.com/mauth/login"
TARGET_URL = "https://x.mnitnetwork.com/mdashboard/getnum"

# --- LOCK & GLOBAL STANDBY ---
playwright_lock = asyncio.Lock()
shared_page = None 

# --- DATA EMOJI NEGARA (SCRIPT 1 STYLE) ---
GLOBAL_COUNTRY_EMOJI = {
  "AFGHANISTAN": "🇦🇫", "ALBANIA": "🇦🇱", "ALGERIA": "🇩🇿", "ANDORRA": "🇦🇩", "ANGOLA": "🇦🇴",
  "ARGENTINA": "🇦🇷", "ARMENIA": "🇦🇲", "AUSTRALIA": "🇦🇺", "AUSTRIA": "🇦🇹", "AZERBAIJAN": "🇦🇿",
  "BANGLADESH": "🇧🇩", "BELARUS": "🇧🇾", "BELGIUM": "🇧🇪", "BRAZIL": "🇧🇷", "CAMBODIA": "🇰🇭",
  "CANADA": "🇨🇦", "CHINA": "🇨🇳", "COLOMBIA": "🇨🇴", "EGYPT": "🇪🇬", "FRANCE": "🇫🇷",
  "GERMANY": "🇩🇪", "INDIA": "🇮🇳", "INDONESIA": "🇮🇩", "IRAQ": "🇮🇶", "ITALY": "🇮🇹",
  "JAPAN": "🇯🇵", "MALAYSIA": "🇲🇾", "MEXICO": "🇲🇽", "NETHERLANDS": "🇳🇱", "PAKISTAN": "🇵🇰",
  "PHILIPPINES": "🇵🇭", "RUSSIA": "🇷🇺", "SAUDI ARABIA": "🇸🇦", "SINGAPORE": "🇸🇬", "SPAIN": "🇪🇸",
  "THAILAND": "🇹🇭", "TURKEY": "🇹🇷", "UKRAINE": "🇺🇦", "UNITED KINGDOM": "🇬🇧", "UNITED STATES": "🇺🇸",
  "VIETNAM": "🇻🇳", "IVORY COAST": "🇨🇮", "UNKNOWN": "🗺️" 
}

# --- VISUAL PROGRESS BAR (SCRIPT 1 STYLE) ---
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

def get_progress_message(current_step, prefix_range, num_count):
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

# --- LOAD ENV ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GROUP_ID_1 = int(os.getenv("GROUP_ID_1"))
GROUP_ID_2 = int(os.getenv("GROUP_ID_2"))
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --- FILE PATHS ---
USER_FILE = "user.json" 
CACHE_FILE = "cache.json"
INLINE_RANGE_FILE = "inline.json"
WAIT_FILE = "wait.json"
AKSES_GET10_FILE = "aksesget10.json"
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1" 
GROUP_LINK_2 = "https://t.me/zura14g" 

# --- STATE MANAGEMENT ---
verified_users = set()
waiting_admin_input = set()
manual_range_input = set() 
get10_range_input = set()
pending_message = {}
waiting_broadcast_input = set()

# ---------------------------------------------------------
# UTILITIES (FILE & TG)
# ---------------------------------------------------------

def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r") as f:
            try: return json.load(f)
            except: return default
    return default

def save_json(file, data):
    with open(file, "w") as f: json.dump(data, f, indent=2)

def normalize_number(number):
    num = str(number).strip().replace(" ", "").replace("-", "")
    return "+" + num if num.isdigit() and not num.startswith('+') else num

def tg_send(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup: data["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{API}/sendMessage", json=data).json()
        return r["result"]["message_id"] if r.get("ok") else None
    except: return None

def tg_edit(chat_id, mid, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": mid, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup: data["reply_markup"] = reply_markup
    requests.post(f"{API}/editMessageText", json=data)

def is_joined(user_id):
    def check(gid):
        try:
            r = requests.get(f"{API}/getChatMember", params={"chat_id": gid, "user_id": user_id}).json()
            return r.get("ok") and r["result"]["status"] in ["member", "administrator", "creator"]
        except: return False
    return check(GROUP_ID_1) and check(GROUP_ID_2)

# ---------------------------------------------------------
# CHROMIUM ENGINE (AUTO-LOGIN & SCRAPER LEVEL 2)
# ---------------------------------------------------------

async def auto_login(browser_context):
    global shared_page
    print("[SYSTEM] Menjalankan Auto-Login Chromium...")
    page = await browser_context.new_page()
    try:
        await page.goto(LOGIN_URL, timeout=60000)
        await page.fill("input[type='email']", EMAIL_MNIT)
        await page.fill("input[type='password']", PASS_MNIT)
        await page.click("button[type='submit']")
        await page.wait_for_url("**/mdashboard/getnum", timeout=30000)
        await asyncio.sleep(2)
        shared_page = page
        print("[SYSTEM] ✅ Login Berhasil & Standby.")
        return True
    except Exception as e:
        print(f"[SYSTEM] ❌ Login Gagal: {e}")
        return False

async def get_data_parallel(page, num_to_fetch):
    results = []
    rows = await page.locator("tbody tr").all()
    cache = load_json(CACHE_FILE, [])
    cached_nums = [c['number'] for c in cache]

    for row in rows[:num_to_fetch + 5]:
        try:
            num_el = row.locator("td:nth-child(1) span.font-mono")
            status_el = row.locator("td:nth-child(1) div:nth-child(2) span")
            country_el = row.locator("td:nth-child(2) span.text-slate-200")
            
            raw_num = await num_el.inner_text()
            number = normalize_number(raw_num)
            status = (await status_el.inner_text()).lower()
            country = (await country_el.inner_text()).upper()

            if number not in cached_nums and "success" not in status and "failed" not in status:
                results.append({"number": number, "country": country})
        except: continue
    return results

async def process_request(browser, uid, prefix, count, un, fn, mid=None):
    global shared_page
    if not mid: mid = tg_send(uid, get_progress_message(0, prefix, count))
    
    async with playwright_lock:
        try:
            if not shared_page or shared_page.is_closed(): await auto_login(browser)
            
            await shared_page.fill("input[name='numberrange']", prefix)
            tg_edit(uid, mid, get_progress_message(3, prefix, count))
            await shared_page.click("button:has-text('Get Number')", force=True)
            
            found = []
            for step in [5, 8, 12]: # Visual Step dari Script 1
                await asyncio.sleep(1.5)
                found = await get_data_parallel(shared_page, count)
                tg_edit(uid, mid, get_progress_message(step, prefix, count))
                if len(found) >= count: break

            if not found:
                tg_edit(uid, mid, "❌ <b>Nomor tidak ditemukan.</b> Ganti range!")
                return

            # Simpan Data (Struktur Script 1)
            cache = load_json(CACHE_FILE, [])
            wait_list = load_json(WAIT_FILE, [])
            identity = f"@{un}" if un and un != "None" else f'<a href="tg://user?id={uid}">{fn}</a>'

            for n in found[:count]:
                cache.append({"number": n['number'], "user_id": uid, "time": time.time()})
                wait_list.append({"number": n['number'], "user_id": uid, "username": identity, "timestamp": time.time()})
            
            save_json(CACHE_FILE, cache[-1000:])
            save_json(WAIT_FILE, wait_list)

            # Output UI (Script 1 Style)
            emoji = GLOBAL_COUNTRY_EMOJI.get(found[0]['country'], "🗺️")
            if count == 10:
                res_text = f"✅<b>The number is already.</b>\n\n<code>"
                for n in found[:10]: res_text += f"{n['number']}\n"
                res_text += "</code>"
            else:
                res_text = f"✅ <b>The number is ready</b>\n\n"
                for i, n in enumerate(found[:count]):
                    res_text += f"📞 Number {i+1 if count > 1 else ''}: <code>{n['number']}</code>\n"
                res_text += f"{emoji} COUNTRY : {found[0]['country']}\n🏷️ Range   : <code>{prefix}</code>\n\n"
                res_text += "<b>🤖 Number available please use, Waiting for OTP</b>"

            kb = {"inline_keyboard": [
                [{"text": "🔄 Change 1 Number", "callback_data": f"change:1:{prefix}"}],
                [{"text": "🔐 OTP Grup", "url": GROUP_LINK_1}, {"text": "🌐 Change Range", "callback_data": "menu"}]
            ]}
            tg_edit(uid, mid, res_text, kb)
        except Exception as e:
            tg_edit(uid, mid, f"❌ Error Mesin: {str(e)[:50]}")

# ---------------------------------------------------------
# MAIN BOT LOGIC (CASING SCRIPT 1)
# ---------------------------------------------------------

async def telegram_loop(browser):
    offset = 0
    while True:
        try:
            r = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 10}).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                
                if "message" in upd:
                    m = upd["message"]; uid = m["from"]["id"]; text = m.get("text", ""); 
                    un = m["from"].get("username"); fn = m["from"].get("first_name", "User")

                    if uid == ADMIN_ID:
                        if text.startswith("/broadcast"):
                            msg = text.replace("/broadcast", "").strip()
                            for u in load_json(USER_FILE, []): tg_send(u, f"📢 <b>PENGUMUMAN</b>\n\n{msg}")
                            continue
                        elif text == "/add":
                            waiting_admin_input.add(uid)
                            tg_send(uid, "Kirim range format: <code>range > country</code>")
                            continue

                    if text == "/start":
                        if is_joined(uid):
                            users = load_json(USER_FILE, [])
                            if uid not in users: users.append(uid); save_json(USER_FILE, users)
                            tg_send(uid, f"✅ Verifikasi Berhasil, {fn}!", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "menu"}]]})
                        else:
                            tg_send(uid, "❌ Gabung grup dulu!", {"inline_keyboard": [[{"text": "Grup 1", "url": GROUP_LINK_1}],[{"text": "Grup 2", "url": GROUP_LINK_2}],[{"text": "🔄 Verifikasi", "callback_data": "verif"}]]})

                    if uid in waiting_admin_input:
                        waiting_admin_input.remove(uid)
                        new = []
                        for line in text.split('\n'):
                            if ' > ' in line:
                                p = line.split(' > '); c = p[1].strip().upper()
                                new.append({"range": p[0].strip(), "country": c, "emoji": GLOBAL_COUNTRY_EMOJI.get(c, "🗺️")})
                        if new: save_json(INLINE_RANGE_FILE, new); tg_send(uid, "✅ Range Disimpan.")
                        continue

                    # Manual Range Detection
                    if re.match(r"^\d{5,15}[Xx*#]+$", text.strip()):
                        if is_joined(uid): await process_request(browser, uid, text.strip(), 1, un, fn)

                elif "callback_query" in upd:
                    cq = upd["callback_query"]; uid = cq["from"]["id"]; data = cq["data"]; mid = cq["message"]["message_id"]
                    un = cq["from"].get("username"); fn = cq["from"].get("first_name", "User")

                    if data == "menu":
                        ranges = load_json(INLINE_RANGE_FILE, [])
                        kb = [[{"text": f"{r['country']} {r['emoji']}", "callback_data": f"get:{r['range']}"}] for r in ranges]
                        kb.append([{"text": "✍️ Input Manual", "callback_data": "manual"}])
                        tg_edit(uid, mid, "<b>Pilih Range:</b>", {"inline_keyboard": kb})
                    elif data.startswith("get:"):
                        await process_request(browser, uid, data.split(":")[1], 1, un, fn, mid)
                    elif data.startswith("change:"):
                        p = data.split(":"); requests.post(f"{API}/deleteMessage", json={"chat_id": uid, "message_id": mid})
                        await process_request(browser, uid, p[2], int(p[1]), un, fn)
                    elif data == "verif":
                        if is_joined(uid): tg_edit(uid, mid, "✅ Berhasil!", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "menu"}]]})
                        else: requests.post(f"{API}/answerCallbackQuery", json={"callback_query_id": cq["id"], "text": "❌ Masum grup dulu!", "show_alert": True})

        except: await asyncio.sleep(1)

async def main():
    for f in [USER_FILE, CACHE_FILE, INLINE_RANGE_FILE, WAIT_FILE, AKSES_GET10_FILE]:
        if not os.path.exists(f): save_json(f, [] if "user" not in f else [])
    
    subprocess.Popen([sys.executable, "sms.py"]) # Jalankan pendeteksi OTP
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) # Pakai headless=False jika ingin lihat browsernya
        context = await browser.new_context()
        await auto_login(context) # Login diawal
        
        print("[INFO] Bot DNA Hybrid Aktif!")
        await telegram_loop(browser)

if __name__ == "__main__":
    asyncio.run(main())
