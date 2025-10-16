import os
import re
import pdfplumber
from flask import Flask, request
from telegram import Update, Bot, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters

# Flask app
app = Flask(__name__)

# Bot token
TOKEN = "7846567022:AAFedvu82SEUypEfCZdp73D9Ej7Rvn1qlHY"
bot = Bot(token=TOKEN)

# Global o‘zgaruvchilar
ASK_SEMESTER = 1
pdf_data = {}

# --- /start ---
@bot.message_handler(commands=['start'])
async def start(update: Update, context):
    await update.message.reply_text(
        "Salom! 📚 Men faqat kredit va ballga asoslanib o‘rta reytingni hisoblayman.\n"
        "Iltimos, reyting daftar (PDF) faylini yuboring."
    )

# --- PDF faylni qabul qilish ---
async def handle_pdf(update: Update, context):
    file = await update.message.document.get_file()
    file_path = "rating.pdf"
    await file.download_to_drive(file_path)

    # PDF dan matn o‘qish
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
        # Semestr boshlangan joy
        if re.match(r"^\d+\s*-\s*semestr", line, re.IGNORECASE):
            current_sem = int(re.search(r"(\d+)", line).group(1))
            semestr_data[current_sem] = []
            continue

        # Agar satrda ball / kredit mavjud bo‘lsa
        if current_sem:
            nums = re.findall(r"\d+(?:\.\d+)?", line)
            if len(nums) >= 3:
                # kreditni aniqlash
                credit = None
                for n in nums:
                    if '.' in n:
                        credit = float(n)
                        break
                if credit is None:
                    try:
                        credit = float(nums[1])
                    except:
                        continue

                # ballni aniqlash
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

# --- Semestr tanlash ---
async def handle_semester(update: Update, context):
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


# --- Flask route Telegram yangilanishlari uchun ---
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    app.telegram_app.update_queue.put(update)
    return "OK", 200


# --- Flask run ---
if __name__ == "__main__":
    WEBHOOK_URL = f"https://gpa-bot-yr0k.onrender.com/{TOKEN}"

    application = Application.builder().token(TOKEN).build()
    app.telegram_app = application

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.PDF, handle_pdf)],
        states={ASK_SEMESTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_semester)]},
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    # Webhookni o‘rnatish
    bot.delete_webhook()
    bot.set_webhook(WEBHOOK_URL)
    print("🌐 Webhook o‘rnatildi:", WEBHOOK_URL)

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

