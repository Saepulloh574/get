import json
import os
import time
import requests
import html
from dotenv import load_dotenv
from datetime import datetime

# Muat variabel lingkungan
load_dotenv()

# ================= Konfigurasi Global =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
# Waktu tunggu standar sebelum dapet OTP (default 30 menit)
WAIT_TIMEOUT_SECONDS = int(os.getenv("WAIT_TIMEOUT_SECONDS", 1800)) 
# Waktu tunggu tambahan SETELAH dapet OTP (5 menit)
EXTENDED_WAIT_SECONDS = 300 

# Harga Reward per OTP
OTP_REWARD_PRICE = 0.003500

SMC_FILE = "smc.json"
WAIT_FILE = "wait.json"
PROFILE_FILE = "profile.json" # Akses ke file profil
DONATE_LINK = "https://zurastore.my.id/donate"
# ======================================================

def create_otp_keyboard(otp):
    """Membuat keyboard inline: Tombol Copy OTP sejajar dengan Tombol Donate."""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": f" {otp}", "copy_text": {"text": otp}},
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
        res_json = response.json()
        if not res_json.get("ok"):
            print(f"[TG ERROR] {res_json.get('description')}")
        return res_json
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
                if filename == PROFILE_FILE: return {} # Profile dict
                return [] # Default list
    if filename == PROFILE_FILE: return {}
    return []

def save_json_file(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

# ================= Manajemen Profil (Update Saldo) =================

def update_profile_otp(user_id):
    """
    Mengupdate saldo dan counter OTP user di profile.json
    Mengembalikan: (old_balance, new_balance)
    """
    profiles = load_json_file(PROFILE_FILE)
    str_id = str(user_id)
    
    # Init jika belum ada (Safe guard)
    if str_id not in profiles:
        profiles[str_id] = {
            "name": "User", "dana": "Belum Diset", "dana_an": "Belum Diset",
            "balance": 0.000000, "otp_semua": 0, "otp_hari_ini": 0,
            "last_active": datetime.now().strftime("%Y-%m-%d")
        }

    p = profiles[str_id]
    
    # Cek reset harian
    today = datetime.now().strftime("%Y-%m-%d")
    if p.get("last_active") != today:
        p["otp_hari_ini"] = 0
        p["last_active"] = today
        
    old_balance = p.get("balance", 0.0)
    
    # Update Stats
    p["otp_semua"] = p.get("otp_semua", 0) + 1
    p["otp_hari_ini"] = p.get("otp_hari_ini", 0) + 1
    
    # Update Balance
    p["balance"] = old_balance + OTP_REWARD_PRICE
    
    new_balance = p["balance"]
    
    save_json_file(PROFILE_FILE, profiles)
    
    return old_balance, new_balance

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
            else:
                new_wait_list.append(wait_item)
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
            # Menggunakan mapping field dari script bot pertama
            entry_num = str(sms_entry.get("number") or sms_entry.get("Number"))
            
            if not found_for_this_user and entry_num == str(wait_number):
                otp = sms_entry.get("otp") or sms_entry.get("OTP", "N/A")
                service = sms_entry.get("service", "Unknown")
                raw_msg = sms_entry.get("full_message") or sms_entry.get("FullMessage", "No message content")
                
                # Escape HTML agar karakter <#> tidak dianggap tag yang merusak oleh Telegram
                safe_msg = html.escape(raw_msg)
                
                # Cek apakah service adalah WhatsApp
                is_whatsapp = "whatsapp" in service.lower()
                
                if is_whatsapp:
                    # Tidak ada penambahan saldo untuk WhatsApp
                    balance_text = "<i>WhatsApp OTP no balance</i>"
                else:
                    # Update Saldo untuk service lain
                    old_bal, new_bal = update_profile_otp(wait_user_id)
                    balance_text = f"${old_bal:.6f} > ${new_bal:.6f}"
                
                response_text = (
                    "🔔 <b>New Message Detected</b>\n\n"
                    f"☎️ <b>Nomor:</b> <code>{wait_number}</code>\n"
                    f"⚙️ <b>Service:</b> <b>{service}</b>\n\n"
                    f"💰 <b>added:</b> {balance_text}\n\n"
                    f"🗯️ <b>Full Message:</b>\n"
                    f"<blockquote>{safe_msg}</blockquote>\n\n"
                    "⚡ <b>Tap the Button To Copy OTP</b> ⚡"
                )
                
                keyboard = create_otp_keyboard(otp)
                tg_send(wait_user_id, response_text, reply_markup=keyboard)

                print(f"[SUCCESS] OTP {service} terkirim ke {user_identity}.")
                
                wait_item['otp_received_time'] = time.time()
                sms_was_changed = True
                found_for_this_user = True
            else:
                remaining_sms.append(sms_entry)
        
        sms_data = remaining_sms
        new_wait_list.append(wait_item)

    if sms_was_changed:
        save_json_file(SMC_FILE, sms_data)
    
    save_json_file(WAIT_FILE, new_wait_list)

def sms_loop():
    print("========================================")
    print(f"[STARTED] Monitor OTP Aktif")
    print(f"[CONFIG] Startup: smc.json dibersihkan")
    print(f"[CONFIG] Timeout: {WAIT_TIMEOUT_SECONDS/60}m")
    print(f"[CONFIG] Extended: {EXTENDED_WAIT_SECONDS/60}m")
    print(f"[CONFIG] Reward: ${OTP_REWARD_PRICE} / OTP")
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
        print(f"[STARTUP] Mengosongkan {SMC_FILE} untuk sesi baru...")
        save_json_file(SMC_FILE, []) 
    # --------------------------------------------------
    
    sms_loop()
