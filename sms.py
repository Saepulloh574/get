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
# Default 30 menit
WAIT_TIMEOUT_SECONDS = int(os.getenv("WAIT_TIMEOUT_SECONDS", 1800)) 

# Nama file
SMC_FILE = "smc.json"
WAIT_FILE = "wait.json"
# ======================================================

def tg_send(chat_id, text, reply_markup=None):
    """Fungsi sederhana untuk mengirim pesan ke Telegram."""
    if not BOT_TOKEN:
        print("[ERROR] BOT_TOKEN tidak ditemukan. Gagal mengirim pesan.")
        return
        
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{API}/sendMessage", json=data).json()
        if not r.get("ok"):
            print(f"[ERROR SMS.PY SEND] {r.get('description', 'Unknown Error')}") 
    except requests.exceptions.RequestException as e:
        print(f"[ERROR SMS.PY REQUEST] Request failed: {e}")
    except Exception as e:
        print(f"[ERROR SMS.PY] Unknown error in tg_send: {e}")

# ================= Fungsi Baca/Tulis File =================

def load_wait_list():
    """Memuat daftar tunggu dari wait.json."""
    if os.path.exists(WAIT_FILE):
        with open(WAIT_FILE, "r") as f:
            try: return json.load(f)
            except json.JSONDecodeError: 
                print(f"[WARNING] {WAIT_FILE} is corrupted. Resetting.")
                return []
    return []

def save_wait_list(data):
    """Menyimpan daftar tunggu ke wait.json."""
    try:
        with open(WAIT_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save {WAIT_FILE}: {e}")

def load_smc():
    """Memuat data SMS/OTP dari smc.json."""
    if os.path.exists(SMC_FILE):
        with open(SMC_FILE, "r") as f:
            try: return json.load(f)
            except json.JSONDecodeError: 
                print(f"[WARNING] {SMC_FILE} is corrupted. Resetting.")
                return []
    return []

def save_smc(data):
    """Menyimpan data SMS/OTP kembali ke smc.json."""
    try:
        with open(SMC_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save {SMC_FILE}: {e}")
        
# ================= Fungsi Utama Monitoring & Forwarding =================

def check_and_forward():
    """
    Memeriksa daftar tunggu dan mencocokkan dengan OTP yang masuk di smc.json.
    Jika cocok atau kedaluwarsa, notifikasi dikirimkan dan item dihapus.
    """
    wait_list = load_wait_list()
    if not wait_list:
        return
        
    sms_data = load_smc()
    
    new_wait_list = [] 
    current_time = time.time()
    
    # 1. Loop melalui daftar tunggu
    for wait_item in wait_list:
        wait_number = wait_item.get('number', 'N/A')
        wait_user_id = wait_item.get('user_id')
        timestamp = wait_item.get('timestamp', 0)
        
        if wait_number == 'N/A' or not wait_user_id:
            continue # Abaikan entri yang tidak valid

        # A. Cek Timeout/Kedaluwarsa
        if current_time - timestamp > WAIT_TIMEOUT_SECONDS:
            timeout_msg = (
                "expired number,removed from the waiting list\n\n"
                f"📞 Number: <code>{wait_number}</code>\n"
                f"Waktu tunggu ({WAIT_TIMEOUT_SECONDS // 60} menit) telah habis. Nomor dihapus dari daftar tunggu."
            )
            tg_send(wait_user_id, timeout_msg)
            print(f"[SMS.PY] Nomor {wait_number} dihapus karena kedaluwarsa.")
            continue # Lanjut ke item tunggu berikutnya
            
        # B. Cek Kecocokan di data OTP (smc.json)
        found_sms = None
        new_sms_data = []
        removed_from_sms = False
        
        # Loop melalui data SMS/OTP
        for sms_entry in sms_data:
            if sms_entry.get("Number") == wait_number and not removed_from_sms:
                found_sms = sms_entry
                removed_from_sms = True 
            else:
                new_sms_data.append(sms_entry) 
        
        # C. Jika OTP Ditemukan
        if found_sms:
            otp = found_sms.get("OTP", "N/A")
            full_message = found_sms.get("FullMessage", "Tidak ada pesan lengkap.")
            
            # --- PENTING: Lakukan Escaping HTML pada pesan mentah ---
            # Mengganti < menjadi &lt; dan > menjadi &gt; untuk menghindari error parsing Telegram
            full_message_escaped = full_message.replace('<', '&lt;').replace('>', '&gt;')
            # --------------------------------------------------------
            
            response_text = (
                "🎉 OTP DITEMUKAN OTOMATIS! 🎉\n\n"
                f"📞 Number: <code>{wait_number}</code>\n"
                f"🔢 OTP: <code>{otp}</code>\n"
                "\n"
                "💬 Full Message:\n"
                f"<blockquote>{full_message_escaped}</blockquote>" # Gunakan yang sudah di-escape
            )
            
            tg_send(wait_user_id, response_text) 
            print(f"[SMS.PY] OTP untuk {wait_number} berhasil dikirim ke User ID {wait_user_id}")
            
            # Perbarui sms_data dengan data yang sudah dihapus
            sms_data = new_sms_data 
            
            # Karena sudah ditemukan dan dikirim, jangan tambahkan ke new_wait_list
            
        else:
            # Jika belum ditemukan dan belum timeout, simpan kembali ke daftar tunggu
            new_wait_list.append(wait_item)

    # 2. Simpan kembali data yang sudah diperbarui
    save_smc(sms_data)
    save_wait_list(new_wait_list)

# ================= Loop Utama =================

def sms_loop():
    """Menjalankan proses check_and_forward secara terus-menerus."""
    if not BOT_TOKEN:
        print("FATAL ERROR: BOT_TOKEN tidak diatur. Tidak dapat menjalankan bot.")
        return

    print("[SMS.PY] SMS Auto-Forward Monitor Started.")
    while True:
        try:
            check_and_forward()
            time.sleep(1) 
        except KeyboardInterrupt:
            print("\n[SMS.PY] Monitor stopped by user.")
            break
        except Exception as e:
            print(f"[FATAL ERROR] An unexpected error occurred in the loop: {e}")
            time.sleep(5) 

if __name__ == "__main__":
    sms_loop()
