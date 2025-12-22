import os
import sys
import json
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

# ================= CONFIG =================
TOKEN = "7386979557:AAEXKl33CCcaQgKes3acF9HBSZGnwRWissk"
ADMIN_ID = 7184123643
OTP_FILE = "otp.json"

# ================= DIRECTORIES =================
for d in ["number","step","temp"]:
    os.makedirs(d, exist_ok=True)

# ================= OTP WATCHER =================
def start_otp_watcher():
    otp_path = os.path.join(os.path.dirname(__file__),"otp.py")
    python = sys.executable
    subprocess.Popen([python, otp_path],
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL,
                     creationflags=subprocess.CREATE_NEW_CONSOLE)
start_otp_watcher()

# ================= HELPERS =================
async def send(update, context, text, kb=None):
    await context.bot.send_message(update.effective_chat.id, text=text, parse_mode="HTML", reply_markup=kb)

async def edit(update, context, text, kb=None):
    try:
        await update.callback_query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        if "Message is not modified" in str(e): pass
        else: raise e

def save_waiting_otp(user_id, number):
    data=[]
    if os.path.exists(OTP_FILE):
        try: data=json.load(open(OTP_FILE))
        except: pass
    data.append({"id": user_id, "number": number})
    with open(OTP_FILE,"w") as f:
        json.dump(data,f,indent=2)

# ================= COMMANDS =================
async def start_cmd(update, context):
    dirs=[f.replace(".json","") for f in os.listdir("number") if f.endswith(".json")]
    if not dirs: await send(update, context,"❌ Tidak ada country"); return
    buttons,row=[],[]
    for i,c in enumerate(dirs,1):
        row.append(InlineKeyboardButton(c, callback_data=f"ct_{c}"))
        if i%2==0: buttons.append(row); row=[]
    if row: buttons.append(row)
    await send(update, context,"🌍 <b>Pilih Country</b>", InlineKeyboardMarkup(buttons))

async def addnum(update, context):
    if update.effective_chat.id!=ADMIN_ID: await send(update, context,"❌ Anda bukan admin!"); return
    with open(f"step/{update.effective_chat.id}.txt","w") as f: f.write("wait_numbers")
    await send(update, context,"Silahkan kirim seluruh nomor (pisah baris).")

async def hapus(update, context):
    if update.effective_chat.id!=ADMIN_ID: await send(update, context,"❌ Anda bukan admin!"); return
    dirs=[f for f in os.listdir("number") if f.endswith(".json")]
    if not dirs: await send(update, context,"❌ Tidak ada file number"); return
    buttons,row=[],[]
    for i,f in enumerate(dirs,1):
        row.append(InlineKeyboardButton(f.replace(".json",""), callback_data=f"del_{f.replace('.json','')}"))
        if i%2==0: buttons.append(row); row=[]
    if row: buttons.append(row)
    await send(update, context,"🗑️ <b>Pilih file number yang ingin dihapus</b>", InlineKeyboardMarkup(buttons))

# ================= CALLBACK HANDLER =================
async def callback_handler(update, context):
    q=update.callback_query
    await q.answer()
    data=q.data; uid=q.message.chat.id

    # pilih country
    if data.startswith("ct_"):
        c=data[3:]
        kb=[[InlineKeyboardButton("📲 Get Number", callback_data=f"get_{c}")]]
        await edit(update, context, f"🌍 <b>{c}</b>", InlineKeyboardMarkup(kb))

    # ambil nomor
    elif data.startswith("get_"):
        c=data[4:]
        path=f"number/{c}.json"
        if not os.path.exists(path): await edit(update, context,"❌ File tidak ditemukan"); return
        nums=json.load(open(path))
        if not nums: await edit(update, context,"❌ Number habis"); return
        num=nums.pop(0)
        json.dump(nums, open(path,"w"), indent=4)
        save_waiting_otp(uid,f"+{num}")
        kb=[[InlineKeyboardButton("🔄 Change Num", callback_data=f"get_{c}")],
            [InlineKeyboardButton("🔗 OTP Grup", url="https://t.me/...")]]
        await edit(update, context,f"🎉 <b>Your Number</b>\n\n📱 <code>+{num}</code>\n🌍 <b>{c}</b>\n⏳ <i>Menunggu OTP...</i>", InlineKeyboardMarkup(kb))

    # hapus file (admin)
    elif data.startswith("del_"):
        if uid!=ADMIN_ID: await edit(update, context,"❌ Hanya admin"); return
        fdel=data[4:]; fpath=f"number/{fdel}.json"
        if os.path.exists(fpath): os.remove(fpath); await edit(update, context,f"✅ File <b>{fdel}</b> berhasil dihapus")
        else: await edit(update, context,f"❌ File <b>{fdel}</b> tidak ditemukan")

# ================= ADMIN STEPS =================
async def handle_msg(update, context):
    uid=update.effective_chat.id; step_file=f"step/{uid}.txt"
    if not os.path.exists(step_file): return
    if uid!=ADMIN_ID: await send(update, context,"❌ Anda bukan admin!"); os.remove(step_file); return
    text=update.message.text
    with open(step_file,"r") as f: step=f.read()

    # STEP 1: nomor
    if step=="wait_numbers":
        nums=list({''.join(filter(str.isdigit,n)) for n in text.split("\n") if n.strip()})
        with open(f"temp/{uid}.json","w") as f: json.dump(nums,f)
        with open(step_file,"w") as f: f.write("wait_title")
        await send(update, context,f"Nomor diterima: <b>{len(nums)}</b>\nSekarang beri judul/country")

    # STEP 2: country
    elif step=="wait_title":
        title=text.strip()
        nums=json.load(open(f"temp/{uid}.json"))
        with open(f"number/{title}.json","w") as f: json.dump(nums,f,indent=4)
        os.remove(step_file); os.remove(f"temp/{uid}.json")
        await send(update, context,f"✅ <b>Sukses menyimpan:</b>\n<b>{title}</b>\n{len(nums)} number.")

# ================= MAIN =================
app=ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start_cmd))
app.add_handler(CommandHandler("addnum", addnum))
app.add_handler(CommandHandler("hapus", hapus))
app.add_handler(CallbackQueryHandler(callback_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))

print("GET BOT RUNNING (OTP watcher auto started)")
app.run_polling()
