import os
import json
import sys
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ================= CONFIG =================
TOKEN = "ISI_TOKEN_BOT_LO"
ADMIN_ID = 7184123643
OTP_FILE = "otp.json"

# ================= AUTO START otp.py =================
def start_otp_watcher():
    otp_path = os.path.join(os.path.dirname(__file__), "otp.py")
    python = sys.executable

    subprocess.Popen(
        [python, otp_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )

start_otp_watcher()

# ================= DIR =================
for d in ["number", "step", "temp"]:
    os.makedirs(d, exist_ok=True)

# ================= HELPERS =================
async def send(update, context, text, kb=None):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode="HTML",
        reply_markup=kb
    )

def save_waiting_otp(user_id, number):
    data = []
    if os.path.exists(OTP_FILE):
        try:
            with open(OTP_FILE, "r") as f:
                data = json.load(f)
        except:
            pass

    data.append({
        "user_id": user_id,
        "number": number
    })

    with open(OTP_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    files = [f.replace(".json","") for f in os.listdir("number") if f.endswith(".json")]
    if not files:
        await send(update, context, "❌ Tidak ada country")
        return

    buttons, row = [], []
    for i,c in enumerate(files,1):
        row.append(InlineKeyboardButton(c, callback_data=f"ct_{c}"))
        if i % 2 == 0:
            buttons.append(row); row=[]
    if row:
        buttons.append(row)

    await send(update, context, "🌍 <b>Pilih Country</b>", InlineKeyboardMarkup(buttons))

# ================= CALLBACK =================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = q.message.chat.id

    # pilih country
    if data.startswith("ct_"):
        c = data[3:]
        kb = [[InlineKeyboardButton("📲 Get Number", callback_data=f"get_{c}")]]
        await q.edit_message_text(
            f"🌍 <b>{c}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    # ambil nomor
    elif data.startswith("get_"):
        c = data[4:]
        path = f"number/{c}.json"

        if not os.path.exists(path):
            await q.edit_message_text("❌ File tidak ditemukan")
            return

        nums = json.load(open(path))
        if not nums:
            await q.edit_message_text("❌ Number habis")
            return

        num = nums.pop(0)
        json.dump(nums, open(path,"w"), indent=2)

        save_waiting_otp(uid, f"+{num}")

        kb = [
            [InlineKeyboardButton("🔄 Change Num", callback_data=f"get_{c}")],
            [InlineKeyboardButton("🔗 OTP Grup", url="https://t.me/xxxxx")]
        ]

        await q.edit_message_text(
            f"""🎉 <b>Your Number</b>

📱 <code>+{num}</code>
🌍 <b>{c}</b>

⏳ <i>Menunggu OTP...</i>""",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )

# ================= MAIN =================
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(callback))

print("GET BOT RUNNING (OTP watcher auto started)")
app.run_polling()
