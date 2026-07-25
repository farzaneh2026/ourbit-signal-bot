from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os

from signals import get_signal, format_signal

TOKEN = os.getenv("BOT_TOKEN")

# آیدی تلگرام خودت را بعداً اینجا می‌گذاری
CHAT_ID = os.getenv("CHAT_ID")


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
    data = get_signal()
    text = format_signal(data)

    await update.message.reply_text(text)


# ارسال خودکار سیگنال
async def auto_signal(context: ContextTypes.DEFAULT_TYPE):

    if CHAT_ID:

        data = get_signal()
        text = format_signal(data)

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=text
        )


def main():

    app = Application.builder().token(TOKEN).build()


    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("signal", signal))


    # هر ۱۵ دقیقه یک سیگنال خودکار
    app.job_queue.run_repeating(
        auto_signal,
        interval=900,
        first=10
    )


    print("Bot Started...")

    app.run_polling()


if __name__ == "__main__":
    main()
