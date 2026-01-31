import json
import os
import time
import requests
import html
import threading
from dotenv import load_dotenv
from datetime import datetime

# Muat variabel lingkungan
load_dotenv()

# ================= Konfigurasi Global =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Masukkan ID Telegram Admin Anda di sini atau di .env
ADMIN_ID = os.getenv("ADMIN_ID", "12345678") 
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

WAIT_TIMEOUT_SECONDS = int(os.getenv("WAIT_TIMEOUT_SECONDS", 1800)) 
EXTENDED_WAIT_SECONDS = 300 
OTP_REWARD_PRICE = 0.003500

SMC_FILE = "smc.json"
WAIT_FILE = "wait.json"
PROFILE_FILE = "profile.json"
SETTINGS_FILE = "settings.json"
DONATE_LINK = "https://zurastore.my.id/donate"

# State internal agar tidak sering baca file
GLOBAL_SETTINGS = {"balance_enabled": True}
# ======================================================

def load_json_file(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            try:
                return json.load(f)
            except:
                if filename == PROFILE_FILE: return {}
                if filename == SETTINGS_FILE: return {"balance_enabled": True}
                return []
    if filename == PROFILE_FILE: return {}
    if filename == SETTINGS_FILE: return {"balance_enabled": True}
    return []

def save_json_file(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

def tg_api(method, data):
    """Helper untuk memanggil Telegram Bot API."""
    try:
        res = requests.post(f"{API}/{method}", json=data, timeout=10)
        return res.json()
    except:
        return None

def update_profile_otp(user_id):
    profiles = load_json_file(PROFILE_FILE)
    str_id = str(user_id)
    if str_id not in profiles:
        profiles[str_id] = {
            "name": "User", "balance": 0.0, "otp_semua": 0, "otp_hari_ini": 0,
            "last_active": datetime.now().strftime("%Y-%m-%d")
        }
    p = profiles[str_id]
    today = datetime.now().strftime("%Y-%m-%d")
    if p.get("last_active") != today:
        p["otp_hari_ini"] = 0
        p["last_active"] = today
    old_bal = p.get("balance", 0.0)
    p["otp_semua"] = p.get("otp_semua", 0) + 1
    p["otp_hari_ini"] = p.get("otp_hari_ini", 0) + 1
    p["balance"] = old_bal + OTP_REWARD_PRICE
    save_json_file(PROFILE_FILE, profiles)
    return old_bal, p["balance"]

# --- FUNGSI ADMIN COMMANDS ---
def check_admin_updates():
    """Fungsi untuk mengecek pesan masuk (Polling) khusus untuk Command Admin."""
    last_update_id = 0
    print("[SYSTEM] Admin Command Listener Aktif.")
    
    while True:
        try:
            updates = tg_api("getUpdates", {"offset": last_update_id + 1, "timeout": 20})
            if updates and updates.get("ok"):
                for up in updates["result"]:
                    last_update_id = up["update_id"]
                    msg = up.get("message")
                    if not msg or "text" not in msg: continue
                    
                    user_id = str(msg["from"]["id"])
                    text = msg["text"]

                    if user_id == str(ADMIN_ID):
                        if text == "/stopbalance":
                            GLOBAL_SETTINGS["balance_enabled"] = False
                            save_json_file(SETTINGS_FILE, GLOBAL_SETTINGS)
                            tg_api("sendMessage", {"chat_id": user_id, "text": "🛑 <b>Balance Dinonaktifkan Global.</b>", "parse_mode": "HTML"})
                            print("[ADMIN] Balance DISABLED")
                            
                        elif text == "/startbalance":
                            GLOBAL_SETTINGS["balance_enabled"] = True
                            save_json_file(SETTINGS_FILE, GLOBAL_SETTINGS)
                            tg_api("sendMessage", {"chat_id": user_id, "text": "✅ <b>Balance Diaktifkan Kembali.</b>", "parse_mode": "HTML"})
                            print("[ADMIN] Balance ENABLED")
        except:
            pass
        time.sleep(1)

# --- FUNGSI UTAMA MONITORING ---
def check_and_forward():
    wait_list = load_json_file(WAIT_FILE)
    if not wait_list: return
    sms_data = load_json_file(SMC_FILE)
    if not sms_data: return

    new_wait_list = []
    current_time = time.time()
    sms_changed = False
    
    # Ambil status terbaru dari memori
    balance_active = GLOBAL_SETTINGS["balance_enabled"]

    for wait_item in wait_list:
        wait_num = wait_item.get('number')
        user_id = wait_item.get('user_id')
        start_ts = wait_item.get('timestamp', 0)
        otp_rec_time = wait_item.get('otp_received_time')

        if otp_rec_time:
            if current_time - otp_rec_time > EXTENDED_WAIT_SECONDS: continue
            new_wait_list.append(wait_item); continue
        
        if current_time - start_ts > WAIT_TIMEOUT_SECONDS:
            tg_api("sendMessage", {"chat_id": user_id, "text": f"⚠️ <b>Waktu Habis</b>\nNomor <code>{wait_num}</code> dihapus." , "parse_mode": "HTML"})
            continue

        rem_sms = []
        found = False
        for sms in sms_data:
            sms_num = str(sms.get("number") or sms.get("Number"))
            if not found and sms_num == str(wait_num):
                otp = sms.get("otp") or sms.get("OTP", "N/A")
                svc = sms.get("service", "Unknown")
                raw = html.escape(sms.get("full_message") or sms.get("FullMessage", ""))
                
                # LOGIK REWARD TEXT
                if not balance_active:
                    bal_txt = "<b>Not available at this time</b>"
                elif "whatsapp" in svc.lower():
                    bal_txt = "<i>WhatsApp OTP no balance</i>"
                else:
                    old, new = update_profile_otp(user_id)
                    bal_txt = f"${old:.6f} > ${new:.6f}"
                
                msg_body = (
                    "🔔 <b>New Message Detected</b>\n\n"
                    f"☎️ <b>Nomor:</b> <code>{wait_num}</code>\n"
                    f"⚙️ <b>Service:</b> <b>{svc}</b>\n\n"
                    f"💰 <b>Added:</b> {bal_txt}\n\n"
                    f"🗯️ <b>Full Message:</b>\n"
                    f"<blockquote>{raw}</blockquote>\n\n"
                    "⚡ <b>Tap the Button To Copy OTP</b> ⚡"
                )
                
                kb = {"inline_keyboard": [[{"text": f" {otp}", "copy_text": {"text": otp}}, {"text": "💸 Donate", "url": DONATE_LINK}]]}
                tg_api("sendMessage", {"chat_id": user_id, "text": msg_body, "reply_markup": kb, "parse_mode": "HTML"})
                
                wait_item['otp_received_time'] = time.time()
                sms_changed = True
                found = True
            else:
                rem_sms.append(sms)
        
        sms_data = rem_sms
        new_wait_list.append(wait_item)

    if sms_changed: save_json_file(SMC_FILE, sms_data)
    save_json_file(WAIT_FILE, new_wait_list)

def main_loop():
    # Load settings awal
    global GLOBAL_SETTINGS
    GLOBAL_SETTINGS = load_json_file(SETTINGS_FILE)
    
    # Jalankan Admin Listener di Thread terpisah agar tidak mengganggu loop Monitoring
    admin_thread = threading.Thread(target=check_admin_updates, daemon=True)
    admin_thread.start()

    print("========================================")
    print(f"[STARTED] Monitor OTP & Admin Cmd Aktif")
    print(f"[STATUS] Initial Balance: {GLOBAL_SETTINGS['balance_enabled']}")
    print("========================================")
    
    while True:
        try:
            check_and_forward()
            time.sleep(2)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[LOOP ERROR] {e}")
            time.sleep(5)

if __name__ == "__main__":
    if os.path.exists(SMC_FILE):
        save_json_file(SMC_FILE, [])
    main_loop()
