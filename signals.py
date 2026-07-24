import ccxt
import pandas as pd


exchange = None


def get_signal():
    symbol = "BTC/USDT"

    try:
        candles = exchange.fetch_ohlcv(
            symbol,
            timeframe="15m",
            limit=100
        )

        df = pd.DataFrame(
            candles,
            columns=["time","open","high","low","close","volume"]
        )

        close = df["close"]

        ema50 = close.ewm(span=50).mean().iloc[-1]
        ema200 = close.ewm(span=200).mean().iloc[-1]
        price = close.iloc[-1]

        if price > ema50 and price > ema200:
            action = "BUY"
        elif price < ema50 and price < ema200:
            action = "SELL"
        else:
            action = "WAIT"

        return {
            "symbol": symbol,
            "action": action,
            "entry": price,
            "tp1": f"{price*1.02:.4f}",
            "tp2": f"{price*1.04:.4f}",
            "sl": f"{price*0.98:.4f}"
        }

    except Exception as e:
        return {
            "symbol": symbol,
            "action": "ERROR",
            "entry": str(e),
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
