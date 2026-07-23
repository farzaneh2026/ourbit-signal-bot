from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
import requests
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
    if context.args:
        coin = context.args[0].upper()
    else:
        coin = "BTC"

    url = f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT"
    data = requests.get(url).json()await update.message.reply_text(str(data))
    price = float(data["price"])

    tp1 = round(price * 1.015, 2)
    tp2 = round(price * 1.03, 2)
    sl = round(price * 0.985, 2)

    await update.message.reply_text(
        f"📊 سیگنال {coin}/USDT\n\n"
        f"💰 قیمت فعلی: {price}\n\n"
        "🟢 Buy\n"
        f"Entry: {price}\n"
        f"TP1: {tp1}\n"
        f"TP2: {tp2}\n"
        f"SL: {sl}"
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
