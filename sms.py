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
PROFILE_FILE = "profil.json"
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
        response = requests.post(f"{API}/sendMessage", json=data, timeout=15)
        return response.json()
    except Exception as e:
        print(f"[ERROR REQUEST] {e}")
        return None

# ================= Fungsi Baca/Tulis File =================

def load_json_file(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            try:
                return json.load(f)
            except:
                return [] if "profil" not in filename else {}
    return [] if "profil" not in filename else {}

def save_json_file(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

def add_economy_bonus(user_id):
    """Menambah saldo dan counter OTP user."""
    profiles = load_json_file(PROFILE_FILE)
    uid = str(user_id)
    if uid in profiles:
        old_balance = profiles[uid].get("balance", 0.0)
        new_balance = old_balance + 0.003500
        profiles[uid]["balance"] = new_balance
        profiles[uid]["otp_semua"] = profiles[uid].get("otp_semua", 0) + 1
        profiles[uid]["otp_hari_ini"] = profiles[uid].get("otp_hari_ini", 0) + 1
        save_json_file(PROFILE_FILE, profiles)
        return old_balance, new_balance
    return 0.0, 0.0

# ================= Fungsi Utama Monitoring =================

def check_and_forward():
    wait_list = load_json_file(WAIT_FILE)
    if not wait_list:
        return
        
    sms_data = load_json_file(SMC_FILE)
    if not sms_data:
        return

    new_wait_list = [] 
    current_time = time.time()
    sms_was_changed = False
    
    for wait_item in wait_list:
        wait_number = wait_item.get('number', 'N/A')
        wait_user_id = wait_item.get('user_id')
        start_timestamp = wait_item.get('timestamp', 0)
        user_identity = wait_item.get('username', 'Unknown User')
        otp_received_time = wait_item.get('otp_received_time')

        # 1. Logic Sesi Selesai (Cleanup)
        if otp_received_time:
            if current_time - otp_received_time > EXTENDED_WAIT_SECONDS:
                print(f"[CLEANUP] Sesi selesai untuk {wait_number}")
                continue 
        
        # 2. Logic Expired
        elif current_time - start_timestamp > WAIT_TIMEOUT_SECONDS:
            timeout_msg = (
                "⚠️ <b>Waktu Habis</b>\n"
                f"Nomor: <code>{wait_number}</code> telah dihapus karena tidak ada SMS masuk."
            )
            tg_send(wait_user_id, timeout_msg)
            print(f"[TIMEOUT] {wait_number} dihapus.")
            continue

        # 3. Cek & Filter SMS
        remaining_sms = []
        found_for_this_user = False
        
        for sms_entry in sms_data:
            if str(sms_entry.get("Number")) == str(wait_number):
                otp = sms_entry.get("OTP", "N/A")
                
                # Proses Ekonomi
                old_bal, new_bal = add_economy_bonus(wait_user_id)
                
                response_text = (
                    "🗯️ <b>New Message Detected</b>\n\n"
                    f"👤 <b>User:</b> {user_identity}\n"
                    f"☎️ <b>Nomor:</b> <code>{wait_number}</code>\n"
                    f"🔑 <b>OTP:</b> <code>{otp}</code>\n\n"
                    f"💰added: ${old_bal:.6f} > ${new_bal:.6f}\n\n"
                    "⚡ <b>Tap the Button To Copy OTP</b> ⚡"
                )
                
                keyboard = create_otp_keyboard(otp)
                tg_send(wait_user_id, response_text, reply_markup=keyboard)

                print(f"[SUCCESS] OTP {otp} terkirim. Menghapus data dari smc.json.")
                
                wait_item['otp_received_time'] = time.time()
                sms_was_changed = True
                found_for_this_user = True
            else:
                remaining_sms.append(sms_entry)
        
        # Update sms_data untuk iterasi user berikutnya
        sms_data = remaining_sms
        new_wait_list.append(wait_item)

    # Simpan perubahan permanen jika ada SMS yang diproses
    if sms_was_changed:
        save_json_file(SMC_FILE, sms_data)
    
    save_json_file(WAIT_FILE, new_wait_list)

def sms_loop():
    print("========================================")
    print(f"[STARTED] Monitor OTP Aktif")
    print(f"[CONFIG] Startup: smc.json dibersihkan")
    print(f"[CONFIG] Timeout: {WAIT_TIMEOUT_SECONDS/60}m")
    print(f"[CONFIG] Extended: {EXTENDED_WAIT_SECONDS/60}m")
    print("========================================")
    
    while True:
        try:
            check_and_forward()
            time.sleep(2) 
        except KeyboardInterrupt:
            print("\n[STOPPED] Bot dimatikan.")
            break
        except Exception as e:
            print(f"[LOOP ERROR] {e}")
            time.sleep(5) 

if __name__ == "__main__":
    # --- PROSES PEMBERSIHAN SAAT PERTAMA KALI JALAN ---
    if os.path.exists(SMC_FILE):
        print(f"[STARTUP] Mengosongkan {SMC_FILE} secara permanen...")
        save_json_file(SMC_FILE, []) 
    # --------------------------------------------------
    
    sms_loop()
