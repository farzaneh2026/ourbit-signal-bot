import random


def get_signal():
    # نسخه اولیه استراتژی
    # بعداً به قیمت واقعی اوربیت وصل می‌کنیم

    coins = [
        "BTC",
        "ETH",
        "SOL",
        "DOGE",
        "ADA",
        "XRP"
    ]

    coin = random.choice(coins)

    # تست تحلیل
    rsi = random.randint(30, 70)

    if rsi < 45:
        action = "BUY"
    elif rsi > 60:
        action = "SELL"
    else:
        action = "WAIT"

    return {
        "symbol": f"{coin}/USDT",
        "action": action,
        "entry": "قیمت لحظه‌ای",
        "tp1": "+2%",
        "tp2": "+4%",
        "sl": "-2%"
    }


def format_signal(signal):
    return f"""
🤖 Ourbit AI Signal

💰 ارز: {signal['symbol']}
📊 وضعیت: {signal['action']}

🎯 ورود: {signal['entry']}
✅ TP1: {signal['tp1']}
✅ TP2: {signal['tp2']}
🛑 SL: {signal['sl']}

⚠️ معامله را خودت باز کن.
"""
