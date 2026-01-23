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
USER_FILE = "user.json"
WAIT_FILE = "wait.json"
GROUP_LINK_1 = "https://t.me/+E5grTSLZvbpiMTI1"
GROUP_LINK_2 = "https://t.me/zura14g" 

# --- UTILS TG ---
def tg_send(chat_id, text, kb=None):
    res = requests.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "reply_markup": kb}).json()
    return res["result"]["message_id"] if res.get("ok") else None

def tg_send_photo(chat_id, photo_path, caption):
    with open(photo_path, 'rb') as photo:
        requests.post(f"{API}/sendPhoto", params={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}, files={"photo": photo})

def tg_edit(chat_id, mid, text, kb=None):
    requests.post(f"{API}/editMessageText", json={"chat_id": chat_id, "message_id": mid, "text": text, "parse_mode": "HTML", "reply_markup": kb})

# --- FILE MANAGER ---
def init_files():
    for f, c in {USER_FILE: "[]", WAIT_FILE: "[]"}.items():
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
        print("[TERMINAL] Membuka Browser (GUI Mode) untuk Login...")
        async with async_playwright() as p:
            # headless=False supaya kamu bisa lihat prosesnya di RDP
            browser = await p.chromium.launch(headless=False) 
            context = await browser.new_context(viewport={'width': 1280, 'height': 720})
            page = await context.new_page()
            ss_path = "login_status.png"
            
            try:
                await page.goto("https://x.mnitnetwork.com/mauth/login", timeout=60000)
                
                # Tunggu & Klik Email
                print("[TERMINAL] Mengisi Email...")
                email_input = await page.wait_for_selector("input[type='email']", timeout=20000)
                await email_input.click(force=True)
                await page.keyboard.type(EMAIL_MNIT, delay=100)
                
                # Tunggu & Klik Password
                print("[TERMINAL] Mengisi Password...")
                pass_input = await page.wait_for_selector("input[type='password']", timeout=15000)
                await pass_input.click(force=True)
                await page.keyboard.type(PASS_MNIT, delay=100)
                
                # Klik Sign In
                print("[TERMINAL] Menekan Tombol Sign In...")
                await page.click("button[type='submit']", force=True)
                
                # Tunggu sampai URL berubah ke Dashboard
                try:
                    await page.wait_for_url("**/mdashboard/getnum", timeout=30000)
                    print("[TERMINAL] ✅ URL Terdeteksi: Dashboard")
                except:
                    print("[TERMINAL] ⚠️ URL tidak berubah, mengecek elemen dashboard...")

                await asyncio.sleep(3) # Kasih nafas buat loading dashboard
                await page.screenshot(path=ss_path)
                
                current_url = page.url
                if "mdashboard/getnum" in current_url:
                    self.is_logged_in = True
                    # Transfer Cookies agar httpx bisa jalan di background tanpa browser lagi
                    cookies = await context.cookies()
                    for c in cookies:
                        self.client.cookies.set(c['name'], c['value'], domain=c['domain'])
                    
                    tg_send_photo(ADMIN_ID, ss_path, "✅ <b>LOGIN BERHASIL</b>\nBrowser sudah ditutup, session dipindah ke bot.")
                    print("[TERMINAL] ✅ Login Sukses, session disimpan.")
                    return True
                else:
                    tg_send_photo(ADMIN_ID, ss_path, f"❌ <b>LOGIN GAGAL</b>\nPosisi terakhir di: {current_url}")
                    return False

            except Exception as e:
                await page.screenshot(path=ss_path)
                print(f"[TERMINAL] ❌ ERROR: {e}")
                tg_send_photo(ADMIN_ID, ss_path, f"❌ <b>ERROR SISTEM</b>\nDetail: <code>{str(e)[:150]}</code>")
                return False
            finally:
                await browser.close()

    async def process_get(self, uid, prefix, count, un, fn, mid):
        if not self.is_logged_in: 
            if not await self.auto_login():
                tg_edit(uid, mid, "❌ Gagal login otomatis ke MNIT.")
                return
        
        tg_edit(uid, mid, f"<code>Mengirim permintaan {prefix}..</code>")
        try:
            # Hit API GetNum
            await self.client.get(f"{TARGET_URL}?range={prefix}", headers={"X-Requested-With": "XMLHttpRequest"})
            await asyncio.sleep(2)
            
            # Cek Tabel Nomor Terakhir
            r = await self.client.get("https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info?page=1", headers={"X-Requested-With": "XMLHttpRequest"})
            if r.status_code == 200:
                data = r.json().get("data", [])
                if not data:
                    tg_edit(uid, mid, "❌ Nomor belum muncul. Silakan coba lagi.")
                    return

                num = data[0]['number']
                wait_list = load_json(WAIT_FILE)
                identity = f"@{un}" if un else fn
                
                wait_list.append({"number": num, "user_id": uid, "username": identity, "timestamp": time.time()})
                save_json(WAIT_FILE, wait_list)
                
                res_msg = f"✅ <b>Nomor Berhasil Diambil</b>\n\n📞 <code>{num}</code>\n🏷️ Range: <code>{prefix}</code>\n\n<b>🤖 Menunggu OTP...</b>"
                kb = {"inline_keyboard": [[{"text": "🔄 Ganti Nomor", "callback_data": f"change_num:1:{prefix}"}]]}
                tg_edit(uid, mid, res_msg, kb)
            else:
                tg_edit(uid, mid, "❌ API Error.")
        except Exception as e:
            tg_edit(uid, mid, f"❌ Error: {str(e)[:50]}")

bot_engine = MNIT_Engine()

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
                        verified_users.add(uid); save_json(USER_FILE, list(verified_users))
                        tg_send(uid, "Siap! Kirim range manual (contoh: 225XX) untuk ambil nomor.")
                    
                    elif re.match(r"^\d+[Xx*]+$", txt.strip()):
                        mid = tg_send(uid, "<code>Sabar, lagi proses...</code>")
                        await bot_engine.process_get(uid, txt.strip(), 1, un, fn, mid)
        except: await asyncio.sleep(1)

async def main():
    init_files()
    # Pertama kali jalan, langsung login (kamu bisa lihat di RDP)
    await bot_engine.auto_login()
    print("[TERMINAL] Bot Telegram Aktif!")
    await telegram_loop()

if __name__ == "__main__":
    asyncio.run(main())
