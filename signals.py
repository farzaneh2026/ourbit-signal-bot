def get_signal():
    return {
        "symbol": "BTC/USDT",
        "action": "WAIT",
        "entry": "در حال بررسی",
        "tp1": "-",
        "tp2": "-",
        "sl": "-"
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
"""
