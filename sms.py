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
# Default 30 menit untuk pencarian awal
WAIT_TIMEOUT_SECONDS = int(os.getenv("WAIT_TIMEOUT_SECONDS", 1800)) 
# Masa tunggu tambahan setelah OTP pertama masuk (5 menit)
EXTENDED_WAIT_SECONDS = 300 

# Nama file
SMC_FILE = "smc.json"
WAIT_FILE = "wait.json"
# ======================================================

def tg_send(chat_id, text, reply_markup=None):
    """Fungsi sederhana untuk mengirim pesan ke Telegram."""
    if not BOT_TOKEN:
        print("[ERROR] BOT_TOKEN tidak ditemukan.")
        return
        
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{API}/sendMessage", json=data).json()
        if not r.get("ok"):
            print(f"[ERROR SEND] {r.get('description', 'Unknown Error')}") 
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
    try:
        with open(WAIT_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[ERROR SAVE WAIT] {e}")

def load_smc():
    if os.path.exists(SMC_FILE):
        with open(SMC_FILE, "r") as f:
            try: return json.load(f)
            except: return []
    return []

def save_smc(data):
    try:
        with open(SMC_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[ERROR SAVE SMC] {e}")
        
# ================= Fungsi Utama Monitoring & Forwarding =================

def check_and_forward():
    wait_list = load_wait_list()
    if not wait_list:
        return
        
    sms_data = load_smc()
    new_wait_list = [] 
    current_time = time.time()
    sms_was_changed = False
    
    for wait_item in wait_list:
        wait_number = wait_item.get('number', 'N/A')
        wait_user_id = wait_item.get('user_id')
        start_timestamp = wait_item.get('timestamp', 0)
        
        # Cek apakah nomor ini sudah pernah menerima OTP sebelumnya
        otp_received_time = wait_item.get('otp_received_time')

        # --- LOGIKA 1: PENGHAPUSAN DIAM-DIAM SETELAH 5 MENIT ---
        if otp_received_time:
            if current_time - otp_received_time > EXTENDED_WAIT_SECONDS:
                print(f"[INFO] {wait_number} dihapus diam-diam (5 menit berlalu).")
                continue # Langsung skip, tidak masuk ke new_wait_list
        
        # --- LOGIKA 2: EXPIRED SEBELUM DAPAT OTP (DENGAN NOTIF) ---
        elif current_time - start_timestamp > WAIT_TIMEOUT_SECONDS:
            timeout_msg = (
                "⚠️ <b>Waktu Habis</b>\n"
                f"Nomor: <code>{wait_number}</code>\n"
                f"Telah dihapus dari daftar karena tidak ada SMS masuk."
            )
            tg_send(wait_user_id, timeout_msg)
            print(f"[INFO] {wait_number} expired (timeout).")
            continue

        # --- LOGIKA 3: CEK SMS MASUK ---
        found_any_sms = False
        remaining_sms = []
        
        for sms_entry in sms_data:
            if sms_entry.get("Number") == wait_number:
                # OTP Ditemukan!
                otp = sms_entry.get("OTP", "N/A")
                full_msg = sms_entry.get("FullMessage", "-")
                msg_escaped = full_msg.replace('<', '&lt;').replace('>', '&gt;')
                
                response_text = (
                    "📩 <b>SMS BARU DITERIMA!</b>\n\n"
                    f"📞 Nomor: <code>{wait_number}</code>\n"
                    f"🔢 OTP: <code>{otp}</code>\n\n"
                    f"💬 Pesan:\n<blockquote>{msg_escaped}</blockquote>"
                )
                
                tg_send(wait_user_id, response_text)
                print(f"[SUCCESS] OTP dikirim untuk {wait_number}")
                
                # Tandai waktu OTP masuk untuk memulai/reset timer 5 menit
                wait_item['otp_received_time'] = time.time()
                found_any_sms = True
                sms_was_changed = True
            else:
                remaining_sms.append(sms_entry)
        
        if found_any_sms:
            sms_data = remaining_sms # Perbarui data SMS (buang yang sudah dikirim)

        # Simpan kembali ke daftar tunggu (kecuali yang sudah di-'continue')
        new_wait_list.append(wait_item)

    # Simpan perubahan file
    if sms_was_changed:
        save_smc(sms_data)
    save_wait_list(new_wait_list)

# ================= Loop Utama =================

def sms_loop():
    if not BOT_TOKEN:
        print("FATAL ERROR: BOT_TOKEN tidak diatur.")
        return

    print(f"[STARTED] Monitor berjalan. (Extended Wait: {EXTENDED_WAIT_SECONDS/60}m)")
    while True:
        try:
            check_and_forward()
            time.sleep(2) # Delay antar pengecekan
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[LOOP ERROR] {e}")
            time.sleep(5) 

if __name__ == "__main__":
    sms_loop()
