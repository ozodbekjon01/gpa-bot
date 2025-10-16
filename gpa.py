import os
import re
import pdfplumber
from flask import Flask, request
from telegram import Bot, Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

TOKEN = "7846567022:AAFedvu82SEUypEfCZdp73D9Ej7Rvn1qlHY"
ASK_SEMESTER = 1
pdf_data = {}

app = Flask(__name__)
bot = Bot(token=TOKEN)

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! 📚 Men faqat kredit va ballga asoslanib o‘rta reytingni hisoblayman.\n"
        "Iltimos, reyting daftar (PDF) faylini yuboring."
    )

# --- PDF qabul qilish ---
async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    file_path = "rating.pdf"
    await file.download_to_drive(file_path)

    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    semestr_data = {}
    current_sem = None

    for line in text.splitlines():
        line = line.strip()

        if re.match(r"^\d+\s*-\s*semestr", line, re.IGNORECASE):
            current_sem = int(re.search(r"(\d+)", line).group(1))
            semestr_data[current_sem] = []
            continue

        if current_sem:
            nums = re.findall(r"\d+(?:\.\d+)?", line)
            if len(nums) >= 3:
                credit = None
                for n in nums:
                    if "." in n:
                        credit = float(n)
                        break
                if credit is None:
                    try:
                        credit = float(nums[1])
                    except:
                        continue

                m = re.search(r"/\s*(\d+)", line)
                if m:
                    ball = int(m.group(1))
                else:
                    try:
                        ball = int(nums[-2])
                    except:
                        continue

                semestr_data[current_sem].append((credit, ball))

    pdf_data[update.message.from_user.id] = semestr_data

    await update.message.reply_text(
        "📄 PDF o‘qildi!\nEndi nechanchi semestrgacha o‘rta ballni hisoblashni tanlang:",
        reply_markup=ReplyKeyboardMarkup(
            [["1", "2", "3", "4"], ["5", "6", "7", "8"]],
            one_time_keyboard=True,
            resize_keyboard=True,
        ),
    )
    return ASK_SEMESTER

# --- Semestr tanlangandan keyin hisoblash ---
async def handle_semester(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in pdf_data:
        await update.message.reply_text("Avval PDF fayl yuboring.")
        return ConversationHandler.END

    try:
        sem_num = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Iltimos, semestr raqamini kiriting (masalan, 4).")
        return ASK_SEMESTER

    semestrlar = pdf_data[user_id]
    total_points = 0.0
    total_credits = 0.0

    for s in range(1, sem_num + 1):
        if s in semestrlar:
            for credit, ball in semestrlar[s]:
                total_points += credit * ball
                total_credits += credit

    if total_credits == 0:
        await update.message.reply_text("Ma’lumot topilmadi.")
        return ConversationHandler.END

    avg = total_points / total_credits
    await update.message.reply_text(f"🎓 1-{sem_num}-semestrlar oralig‘idagi o‘rta ball: {avg:.2f}")
    return ConversationHandler.END

# --- Bekor qilish ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bekor qilindi.")
    return ConversationHandler.END

# --- Telegram webhook uchun Flask endpoint ---
@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot)
    await application.process_update(update)
    return "OK", 200

# --- Flask test sahifa ---
@app.route("/", methods=["GET"])
def home():
    return "🤖 Telegram GPA bot ishlayapti!"

# --- Telegram application yaratish ---
application = (
    ApplicationBuilder()
    .token(TOKEN)
    .build()
)

conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Document.MimeType("application/pdf"), handle_pdf)],
    states={ASK_SEMESTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_semester)]},
    fallbacks=[CommandHandler("start", start)],
)

application.add_handler(CommandHandler("start", start))
application.add_handler(conv_handler)

# --- Flask serverni ishga tushirish ---
if __name__ == "__main__":
    # WEBHOOK URL — bu siz joylagan domen manzili bo‘lishi kerak:
    WEBHOOK_URL = f"https://your-domain-name.com/{TOKEN}"

    import asyncio
    asyncio.run(bot.set_webhook(url=WEBHOOK_URL))

    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Server ishga tushdi... Port: {port}")
    app.run(host="0.0.0.0", port=port)
