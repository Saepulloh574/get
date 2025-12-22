import json
import os
import time
import requests

BOT_TOKEN = "7386979557:AAEXKl33CCcaQgKes3acF9HBSZGnwRWissk"
OTP_FILE = "otp.json"
SMC_FILE = "../ivams/smc.json"

def send(user_id, text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": user_id,
            "text": text,
            "parse_mode": "HTML"
        },
        timeout=10
    )

print("OTP WATCHER RUNNING")

while True:
    try:
        if not os.path.exists(OTP_FILE) or not os.path.exists(SMC_FILE):
            time.sleep(2)
            continue

        otp_wait = json.load(open(OTP_FILE))
        smc = json.load(open(SMC_FILE))

        new_otp = []
        new_smc = []

        for s in smc:
            sent = False
            for o in otp_wait:
                if s["number"] == o["number"]:
                    msg = f"""🥳 <b>SMS received!</b>

🌍 Range: <b>{s['range']}</b>
📱 Number: <code>{s['number']}</code>
🔢 OTP: <code>{s['otp']}</code>

Silahkan gunakan
"""
                    send(o["user_id"], msg)
                    sent = True
                    break

            if not sent:
                new_smc.append(s)

        for o in otp_wait:
            if not any(o["number"] == s["number"] for s in smc):
                new_otp.append(o)

        json.dump(new_otp, open(OTP_FILE,"w"), indent=2)
        json.dump(new_smc, open(SMC_FILE,"w"), indent=2)

    except Exception as e:
        print("OTP ERROR:", e)

    time.sleep(2)
