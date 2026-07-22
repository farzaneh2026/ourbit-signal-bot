from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 ربات سیگنال Ourbit فعال شد.\n\n"
        "دستورات:\n"
        "/signal - دریافت سیگنال\n"
        "/help - راهنما"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "این ربات سیگنال خرید و فروش را نمایش می‌دهد."
    )

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 نمونه سیگنال\n\n"
        "🟢 Buy\n"
        "Entry: 100.00\n"
        "TP1: 101.50\n"
        "TP2: 103.00\n"
        "SL: 98.50"
    )

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("signal", signal))

    print("Bot Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
