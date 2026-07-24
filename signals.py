# signals.py

def get_signal():
    """
    تولید سیگنال ساده (نسخه اولیه)
    بعداً به اندیکاتورها و تحلیل هوش مصنوعی وصل می‌کنیم
    """

    signal = {
        "symbol": "BTC/USDT",
        "action": "BUY",
        "entry": "قیمت فعلی",
        "tp1": "+2%",
        "tp2": "+4%",
        "sl": "-2%"
    }

    return signal


def format_signal(signal):
    return f"""
🤖 سیگنال هوش مصنوعی

ارز: {signal['symbol']}
📈 وضعیت: {signal['action']}

🎯 ورود: {signal['entry']}
✅ TP1: {signal['tp1']}
✅ TP2: {signal['tp2']}
🛑 SL: {signal['sl']}

⚠️ معامله را خودت باز کن.
"""
