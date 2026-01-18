import json
import os
import time
import requests
from dotenv import load_dotenv

# Muat variabel lingkungan
load_dotenv()

# ================= Konfigurasi Global =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
WAIT_TIMEOUT_SECONDS = int(os.getenv("WAIT_TIMEOUT_SECONDS", 1800)) 
EXTENDED_WAIT_SECONDS = 300 

SMC_FILE = "smc.json"
WAIT_FILE = "wait.json"
DONATE_LINK = "https://zurastore.my.id/donate"
# ======================================================

def create_otp_keyboard(otp):
    """Membuat keyboard inline: Tombol Copy OTP sejajar dengan Tombol Donate."""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": f"📋 {otp}", "copy_text": {"text": otp}},
                {"text": "💸 Donate", "url": DONATE_LINK}
            ]
        ]
    }
    return json.dumps(keyboard)

def tg_send(chat_id, text, reply_markup=None):
    """Fungsi mengirim pesan dengan dukungan HTML dan Keyboard."""
    if not BOT_TOKEN: return
    
    data = {
        "chat_id": chat_id, 
        "text": text, 
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        data["reply_markup"] = reply_markup
        
    try:
        requests.post(f"{API}/sendMessage", json=data, timeout=15)
    except Exception as e:
        print(f"[ERROR REQUEST] {e}")

# ================= Fungsi Baca/Tulis File =================

def load_wait_list():
    if os.path.exists(WAIT_FILE):
        with open(WAIT_FILE, "r") as f:
            try: return json.load(f)
            except: return []
    return []

def save_wait_list(data):
    with open(WAIT_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_smc():
    if os.path.exists(SMC_FILE):
        with open(SMC_FILE, "r") as f:
            try: return json.load(f)
            except: return []
    return []

def save_smc(data):
    with open(SMC_FILE, "w") as f:
        json.dump(data, f, indent=2)
        
# ================= Fungsi Utama Monitoring =================

def check_and_forward():
    wait_list = load_wait_list()
    if not wait_list: return
        
    sms_data = load_smc()
    new_wait_list = [] 
    current_time = time.time()
    sms_was_changed = False
    
    for wait_item in wait_list:
        wait_number = wait_item.get('number', 'N/A')
        wait_user_id = wait_item.get('user_id')
        start_timestamp = wait_item.get('timestamp', 0)
        user_identity = wait_item.get('username', 'Unknown User')
        otp_received_time = wait_item.get('otp_received_time')

        # 1. Logic Hapus setelah 5 menit dpt OTP
        if otp_received_time:
            if current_time - otp_received_time > EXTENDED_WAIT_SECONDS:
                continue 
        
        # 2. Logic Expired sebelum dpt OTP
        elif current_time - start_timestamp > WAIT_TIMEOUT_SECONDS:
            timeout_msg = (
                "⚠️ <b>Waktu Habis</b>\n"
                f"Nomor: <code>{wait_number}</code> telah dihapus."
            )
            tg_send(wait_user_id, timeout_msg)
            continue

        # 3. Cek SMS Masuk
        found_any_sms = False
        remaining_sms = []
        
        for sms_entry in sms_data:
            if sms_entry.get("Number") == wait_number:
                otp = sms_entry.get("OTP", "N/A")
                
                # Struktur Pesan Baru Sesuai Permintaan
                response_text = (
                    "🗯️ <b>New Message Detected</b>\n\n"
                    f"👤 <b>User:</b> {user_identity}\n"
                    f"☎️ <b>Nomor:</b> <code>{wait_number}</code>\n"
                    f"🔑 <b>OTP:</b> <code>{otp}</code>\n\n"
                    "⚡ <b>Tap the Button To Copy OTP</b> ⚡"
                )
                
                # Kirim dengan Tombol Copy & Donate Sejajar
                keyboard = create_otp_keyboard(otp)
                tg_send(wait_user_id, response_text, reply_markup=keyboard)

                print(f"[SUCCESS] OTP dikirim ke {user_identity}")
                
                wait_item['otp_received_time'] = time.time()
                found_any_sms = True
                sms_was_changed = True
            else:
                remaining_sms.append(sms_entry)
        
        if found_any_sms:
            sms_data = remaining_sms 

        new_wait_list.append(wait_item)

    if sms_was_changed:
        save_smc(sms_data)
    save_wait_list(new_wait_list)

def sms_loop():
    print(f"[STARTED] Monitor OTP berjalan. (Extended Wait: {EXTENDED_WAIT_SECONDS/60}m)")
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
    sms_loop()
