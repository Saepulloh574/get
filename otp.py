import os
import json
import time
import requests
from datetime import datetime

# ================= CONFIG =================
BOT_TOKEN = "7386979557:AAEXKl33CCcaQgKes3acF9HBSZGnwRWissk"
OTP_FILE = "otp.json"           # dari get.py
SMC_FILE = "C:/Users/Administrator/ivams/smc.json"  # sesuaikan path
CHECK_INTERVAL = 5               # detik

# ================= HELPERS =================
def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def send_telegram(user_id, text):
    url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload={"chat_id": user_id, "text": text, "parse_mode":"HTML"}
    try:
        r=requests.post(url,data=payload,timeout=10)
        return r.ok
    except:
        return False

def format_sms_message(entry):
    return f"""SMS received 🥳

Range: {entry.get('range','N/A')}
Number: <code>{entry.get('number','N/A')}</code>
OTP: <code>{entry.get('otp','N/A')}</code>

Silahkan gunakan!"""

# ================= MAIN LOOP (DENGAN LOGIKA PENGHAPUSAN OTP.JSON) =================
def main():
    print("OTP watcher running...")
    while True:
        try:
            otp_users = load_json(OTP_FILE)
            if not otp_users:
                time.sleep(CHECK_INTERVAL)
                continue

            smc_data = load_json(SMC_FILE)
            if not smc_data:
                time.sleep(CHECK_INTERVAL)
                continue

            new_smc = []
            # Duplikasi daftar pengguna yang menunggu, untuk dimodifikasi
            new_otp_users = list(otp_users) 

            for entry in smc_data:
                # Cari semua pengguna yang menunggu OTP untuk nomor ini
                matched_users = [u for u in otp_users if u["number"] == entry.get("number")]
                
                if matched_users:
                    # Kirim OTP ke semua pengguna yang cocok
                    for u in matched_users:
                        msg = format_sms_message(entry)
                        sent = send_telegram(u["id"], msg)
                        
                        if sent:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] OTP sent to {u['id']} - {entry['number']}")
                            
                            # Jika pengiriman berhasil, hapus entri ini dari daftar tunggu
                            # Ini mencegah OTP terkirim lagi di masa depan.
                            try:
                                # Hapus objek pengguna dari daftar baru (new_otp_users)
                                # Gunakan list comprehension untuk memastikan objek yang dihapus sesuai
                                new_otp_users = [
                                    item for item in new_otp_users 
                                    if not (item["id"] == u["id"] and item["number"] == u["number"])
                                ]
                            except ValueError:
                                # Tangani kasus jika elemen sudah terhapus (misal ada duplikat dalam otp.json)
                                pass
                        else:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Failed send OTP to {u['id']}")
                    
                    # SMS ini dianggap sudah diproses, jadi jangan masukkan ke new_smc (otomatis terhapus)
                else:
                    # Jika tidak ada pengguna yang cocok, SMS disimpan kembali ke smc.json
                    new_smc.append(entry)
            
            # 1. Simpan perubahan pada OTP_FILE (menghapus user yang sudah menerima)
            if len(new_otp_users) != len(otp_users):
                save_json(OTP_FILE, new_otp_users)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Updated OTP_FILE: {len(otp_users) - len(new_otp_users)} user(s) removed.")
            
            # 2. Simpan perubahan pada SMC_FILE (menghapus SMS yang sudah terkirim)
            if len(new_smc) != len(smc_data):
                save_json(SMC_FILE, new_smc)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Updated SMC_FILE: {len(smc_data) - len(new_smc)} SMS removed.")
            
            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__=="__main__":
    main()
    
