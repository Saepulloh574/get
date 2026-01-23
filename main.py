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

# --- UTILS TG ---
def tg_send(chat_id, text, kb=None):
    res = requests.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "reply_markup": kb}).json()
    return res["result"]["message_id"] if res.get("ok") else None

def tg_send_photo(chat_id, photo_path, caption):
    with open(photo_path, 'rb') as photo:
        requests.post(f"{API}/sendPhoto", params={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}, files={"photo": photo})

def tg_edit(chat_id, mid, text, kb=None):
    requests.post(f"{API}/editMessageText", json={"chat_id": chat_id, "message_id": mid, "text": text, "parse_mode": "HTML", "reply_markup": kb})

def tg_delete(chat_id, mid):
    requests.post(f"{API}/deleteMessage", json={"chat_id": chat_id, "message_id": mid})

def is_user_in_both_groups(user_id):
    def check(gid):
        r = requests.get(f"{API}/getChatMember", params={"chat_id": gid, "user_id": user_id}).json()
        return r.get("ok") and r["result"]["status"] in ["member", "administrator", "creator"]
    return check(GROUP_ID_1) and check(GROUP_ID_2)

# --- FILE MANAGER ---
def init_files():
    for f, c in {USER_FILE:"[]", CACHE_FILE:"[]", INLINE_RANGE_FILE:"[]", WAIT_FILE:"[]", AKSES_GET10_FILE:"[]"}.items():
        if not os.path.exists(f): 
            with open(f, "w") as file: file.write(c)

def load_json(filename):
    if not os.path.exists(filename): return []
    with open(filename, "r") as f: 
        try: return json.load(f)
        except: return []

def save_json(filename, data):
    with open(filename, "w") as f: json.dump(data, f, indent=2)

# --- ENGINE ---
class MNIT_Engine:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self.is_logged_in = False

    async def auto_login(self):
        print("[TERMINAL] Menjalankan Playwright untuk Login...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            ss_path = "login_check.png"
            try:
                await page.goto("https://x.mnitnetwork.com/mauth/login", timeout=60000)
                
                # Gunakan selector tipe (Hasil Inspect)
                await page.wait_for_selector("input[type='email']", timeout=20000)
                
                # PERBAIKAN: Gunakan fill() tanpa delay atau type() dengan delay
                await page.type("input[type='email']", EMAIL_MNIT, delay=100)
                await page.type("input[type='password']", PASS_MNIT, delay=100)
                
                await page.click("button[type='submit']")
                
                # Tunggu proses login/redirect selesai
                await page.wait_for_load_state("networkidle", timeout=30000)
                await asyncio.sleep(2) 
                
                current_url = page.url
                await page.screenshot(path=ss_path)

                if "mdashboard/getnum" in current_url:
                    print(f"[TERMINAL] ✅ LOGIN BERHASIL")
                    self.is_logged_in = True
                    # Pindahkan cookies ke client API
                    cookies = await page.context.cookies()
                    for c in cookies:
                        self.client.cookies.set(c['name'], c['value'], domain=c['domain'])
                    tg_send_photo(ADMIN_ID, ss_path, "✅ <b>LOGIN BERHASIL</b>\nBot sudah masuk ke Dashboard GetNum.")
                    return True
                else:
                    print(f"[TERMINAL] ❌ LOGIN GAGAL: Redirect ke {current_url}")
                    tg_send_photo(ADMIN_ID, ss_path, f"❌ <b>LOGIN GAGAL</b>\nBot nyasar ke: <code>{current_url}</code>")
                    return False
            except Exception as e:
                await page.screenshot(path=ss_path)
                print(f"[TERMINAL] ❌ ERROR: {e}")
                tg_send_photo(ADMIN_ID, ss_path, f"❌ <b>ERROR LOGIN</b>\nDetail: <code>{str(e)[:150]}</code>")
                return False
            finally:
                await browser.close()

    async def process_get(self, uid, prefix, count, un, fn, mid):
        if not self.is_logged_in: 
            success = await self.auto_login()
            if not success:
                tg_edit(uid, mid, "❌ Sistem sedang bermasalah (Login Gagal).")
                return
        
        tg_edit(uid, mid, f"<code>Mengirim permintaan nomor..</code>")
        try:
            for _ in range(count):
                await self.client.get(f"{TARGET_URL}?range={prefix}", headers={"X-Requested-With": "XMLHttpRequest"})
            
            await asyncio.sleep(3)
            r = await self.client.get("https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info?page=1", headers={"X-Requested-With": "XMLHttpRequest"})
            
            if r.status_code == 200:
                data = r.json().get("data", [])
                found = data[:count]
                if not found:
                    tg_edit(uid, mid, "❌ Nomor belum muncul di tabel, coba lagi.")
                    return

                wait_list = load_json(WAIT_FILE)
                identity = f"@{un}" if un else f'<a href="tg://user?id={uid}">{fn}</a>'
                
                res_msg = "✅ <b>The number is ready</b>\n\n"
                for i, n in enumerate(found):
                    num = n['number']
                    wait_list.append({"number": num, "user_id": uid, "username": identity, "timestamp": time.time()})
                    res_msg += f"📞 Number {i+1} : <code>{num}</code>\n"
                
                save_json(WAIT_FILE, wait_list)
                res_msg += f"\n🏷️ Range : <code>{prefix}</code>\n\n<b>🤖 Waiting for OTP</b>"
                kb = {"inline_keyboard": [[{"text": "🔄 Change Number", "callback_data": f"change_num:1:{prefix}"}],[{"text": "🌐 Change Range", "callback_data": "getnum"}]]}
                tg_edit(uid, mid, res_msg, kb)
            else:
                tg_edit(uid, mid, "❌ Gagal mengambil data dari API MNIT.")
        except Exception as e:
            tg_edit(uid, mid, f"❌ Terjadi kesalahan: {str(e)[:50]}")

bot_engine = MNIT_Engine()

# --- TELEGRAM HANDLER ---
async def telegram_loop():
    global verified_users; offset = 0
    verified_users = set(load_json(USER_FILE))
    while True:
        try:
            updates = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 10}).json()
            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1
                if "message" in upd:
                    m = upd["message"]; uid = m["from"]["id"]; txt = m.get("text", ""); fn = m["from"].get("first_name", "User"); un = m["from"].get("username")
                    
                    if txt == "/start":
                        if is_user_in_both_groups(uid):
                            verified_users.add(uid); save_json(USER_FILE, list(verified_users))
                            tg_send(uid, f"✅ Verifikasi Berhasil, <a href='tg://user?id={uid}'>{fn}</a>!", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}]]})
                        else:
                            tg_send(uid, f"Halo {fn}, Harap gabung grup dulu untuk akses:", {"inline_keyboard": [[{"text": "📌 Grup 1", "url": GROUP_LINK_1}],[{"text": "📌 Grup 2", "url": GROUP_LINK_2}],[{"text": "✅ Verifikasi Ulang", "callback_data": "verify"}]]})
                    
                    elif re.match(r"^\d+[Xx*]+$", txt.strip()) and uid in verified_users:
                        mid = tg_send(uid, "<code>Sedang memproses permintaan...</code>")
                        await bot_engine.process_get(uid, txt.strip(), 1, un, fn, mid)

                elif "callback_query" in upd:
                    cq = upd["callback_query"]; uid = cq["from"]["id"]; data = cq["data"]; mid = cq["message"]["message_id"]
                    if data == "getnum":
                        kb = {"inline_keyboard": [[{"text": "Input Manual Range..🖊️", "callback_data": "manual_range"}]]}
                        tg_edit(uid, mid, "<b>Pilih salah satu range di bawah atau input manual range, cek range terbaru @ceknewrange</b>", kb)
                    elif data == "manual_range":
                        tg_edit(uid, mid, "<b>Input Manual Range</b>\n\nKirim range anda, contoh: <code>2327600XXX</code>")
                    elif data == "verify":
                        if is_user_in_both_groups(uid):
                            verified_users.add(uid); save_json(USER_FILE, list(verified_users))
                            tg_edit(uid, mid, "✅ Verifikasi Berhasil! Silakan klik Get Number.", {"inline_keyboard": [[{"text": "📲 Get Number", "callback_data": "getnum"}]]})
                        else:
                            tg_send(uid, "❌ Kamu belum bergabung di semua grup.")
        except: await asyncio.sleep(1)

async def main():
    init_files()
    # Menjalankan login otomatis saat startup
    await bot_engine.auto_login()
    
    # Menjalankan monitor OTP
    if os.path.exists("sms.py"):
        subprocess.Popen([sys.executable, "sms.py"])
        
    print("[STARTED] Bot is running and monitoring...")
    await telegram_loop()

if __name__ == "__main__":
    asyncio.run(main())
