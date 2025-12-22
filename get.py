import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

TOKEN = "7386979557:AAEXKl33CCcaQgKes3acF9HBSZGnwRWissk"
ADMIN_ID = 7184123643  # ADMIN ONLY

# ====== DIRECTORIES ======
for d in ["number", "step", "temp"]:
    if not os.path.exists(d):
        os.makedirs(d)

# ====== HELPERS ======
def send_message(update_or_chat, text, reply_markup=None):
    if isinstance(update_or_chat, Update):
        chat_id = update_or_chat.effective_chat.id
    else:
        chat_id = update_or_chat
    return bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=reply_markup)

def edit_message(update: Update, text, reply_markup=None):
    query = update.callback_query
    query.edit_message_text(text=text, parse_mode="HTML", reply_markup=reply_markup)

# ====== COMMANDS ======
def start(update: Update, context: CallbackContext):
    dirs = [f for f in os.listdir("number") if f.endswith(".json")]
    if not dirs:
        send_message(update, "❌ Tidak ada country di folder number/")
        return

    buttons = []
    row = []
    for i, f in enumerate(dirs, start=1):
        ct = f.replace(".json", "")
        row.append(InlineKeyboardButton(ct, callback_data=f"ct_{ct}"))
        if i % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    send_message(update, "🌍 <b>Pilih Country</b>", InlineKeyboardMarkup(buttons))

def addnum(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_ID:
        send_message(update, "❌ Anda bukan admin!")
        return
    with open(f"step/{update.effective_chat.id}.txt", "w") as f:
        f.write("wait_numbers")
    send_message(update, "Silahkan kirim seluruh nomor (pisah baris).")

def hapus(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_ID:
        send_message(update, "❌ Anda bukan admin!")
        return
    dirs = [f for f in os.listdir("number") if f.endswith(".json")]
    if not dirs:
        send_message(update, "❌ Tidak ada file number di folder number/")
        return

    buttons = []
    row = []
    for i, f in enumerate(dirs, start=1):
        name = f.replace(".json", "")
        row.append(InlineKeyboardButton(name, callback_data=f"del_{name}"))
        if i % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    send_message(update, "🗑️ <b>Pilih file number yang ingin dihapus</b>", InlineKeyboardMarkup(buttons))

# ====== CALLBACK HANDLER ======
def callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    chat_id_cb = query.message.chat.id

    # ===== User pilih country ======
    if data.startswith("ct_"):
        country = data[3:]
        buttons = [[InlineKeyboardButton("📲 Get Num", callback_data=f"get_{country}")]]
        edit_message(update, f"🌍 Country: <b>{country}</b>\n\nKlik tombol di bawah untuk mengambil nomor.", InlineKeyboardMarkup(buttons))

    # ===== User klik Get Num ======
    elif data.startswith("get_"):
        country = data[4:]
        file_path = f"number/{country}.json"
        if not os.path.exists(file_path):
            edit_message(update, "❌ File number tidak ditemukan.")
            return
        with open(file_path, "r") as f:
            numbers = json.load(f)
        if not numbers:
            edit_message(update, "❌ Number habis.")
            return
        num = numbers.pop(0)
        with open(file_path, "w") as f:
            json.dump(numbers, f, indent=4)
        buttons = [
            [InlineKeyboardButton("🔄 Change Num", callback_data=f"chg_{country}")],
            [InlineKeyboardButton("🔗 OTP Grup", url="https://t.me/+E5grTSLZvbpiMTI1")]
        ]
        edit_message(update, f"🎉 <b>Your Number !!!</b>\n\n📱 Number: <code>+{num}</code>\n🌍 Country: <b>{country}</b>\n\n✨ Silahkan Gunakan", InlineKeyboardMarkup(buttons))

    # ===== User klik Change Num ======
    elif data.startswith("chg_"):
        country = data[4:]
        file_path = f"number/{country}.json"
        if not os.path.exists(file_path):
            edit_message(update, "❌ File number tidak ditemukan.")
            return
        with open(file_path, "r") as f:
            numbers = json.load(f)
        if not numbers:
            edit_message(update, "❌ Number habis.")
            return
        num = numbers.pop(0)
        with open(file_path, "w") as f:
            json.dump(numbers, f, indent=4)
        buttons = [
            [InlineKeyboardButton("🔄 Change Num", callback_data=f"chg_{country}")],
            [InlineKeyboardButton("🔗 OTP Grup", url="https://t.me/+E5grTSLZvbpiMTI1")]
        ]
        edit_message(update, f"🔄 <b>Changed Number !!!</b>\n\n📱 Number: <code>+{num}</code>\n🌍 Country: <b>{country}</b>\n\n✨ Gunakan nomor baru kamu", InlineKeyboardMarkup(buttons))

    # ===== ADMIN: Hapus file ======
    elif data.startswith("del_"):
        if chat_id_cb != ADMIN_ID:
            edit_message(update, "❌ Hanya admin yang bisa menghapus file.")
            return
        file_to_del = data[4:]
        file_path = f"number/{file_to_del}.json"
        if os.path.exists(file_path):
            os.remove(file_path)
            edit_message(update, f"✅ File <b>{file_to_del}</b> berhasil dihapus.")
        else:
            edit_message(update, f"❌ File <b>{file_to_del}</b> tidak ditemukan.")

# ====== ADMIN STEPS ======
def handle_message(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    step_file = f"step/{chat_id}.txt"
    if not os.path.exists(step_file):
        return

    if chat_id != ADMIN_ID:
        send_message(chat_id, "❌ Anda bukan admin!")
        os.remove(step_file)
        return

    with open(step_file, "r") as f:
        step = f.read()

    text = update.message.text

    # STEP 1: terima nomor
    if step == "wait_numbers":
        nums_raw = text.split("\n")
        nums = list({''.join(filter(str.isdigit, n)) for n in nums_raw if n.strip()})
        count = len(nums)
        with open(f"temp/{chat_id}.json", "w") as f:
            json.dump(nums, f)
        with open(step_file, "w") as f:
            f.write("wait_title")
        send_message(chat_id, f"Nomor diterima: <b>{count}</b> nomor (tanpa duplikat)\n\nSekarang beri judul/country, contoh:\n<b>Peru🇵🇪</b>")

    # STEP 2: terima nama country
    elif step == "wait_title":
        title = text.strip()
        with open(f"temp/{chat_id}.json", "r") as f:
            nums = json.load(f)
        with open(f"number/{title}.json", "w") as f:
            json.dump(nums, f, indent=4)
        os.remove(step_file)
        os.remove(f"temp/{chat_id}.json")
        send_message(chat_id, f"✅ <b>Sukses menyimpan:</b>\n<b>{title}</b>\n{len(nums)} number.")

# ====== MAIN ======
updater = Updater(TOKEN)
bot = updater.bot
dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("addnum", addnum))
dispatcher.add_handler(CommandHandler("hapus", hapus))
dispatcher.add_handler(CallbackQueryHandler(callback_handler))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

updater.start_polling()
updater.idle()
