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

# ================= MAIN LOOP =================
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

            new_smc=[]
            for entry in smc_data:
                matched_users=[u for u in otp_users if u["number"]==entry.get("number")]
                if matched_users:
                    for u in matched_users:
                        msg=format_sms_message(entry)
                        sent=send_telegram(u["id"], msg)
                        if sent:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] OTP sent to {u['id']} - {entry['number']}")
                        else:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Failed send OTP to {u['id']}")
                    # jangan masukkan ke new_smc → otomatis dihapus
                else:
                    new_smc.append(entry)
            if len(new_smc)!=len(smc_data):
                save_json(SMC_FILE,new_smc)
            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__=="__main__":
    main()
