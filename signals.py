import ccxt
import pandas as pd
import ta

exchange = ccxt.kucoin()


def get_signal():
    try:
        symbol = "BTC/USDT"

        candles = exchange.fetch_ohlcv(
            symbol,
            timeframe="15m",
            limit=100
        )

        df = pd.DataFrame(
            candles,
            columns=["time", "open", "high", "low", "close", "volume"]
        )

        df["ema50"] = ta.trend.EMAIndicator(
            df["close"],
            window=50
        ).ema_indicator()

        price = float(df["close"].iloc[-1])
        ema50 = float(df["ema50"].iloc[-1])

        if price > ema50:
            action = "BUY"
            tp1 = round(price * 1.02, 2)
            tp2 = round(price * 1.04, 2)
            sl = round(price * 0.98, 2)
        else:
            action = "SELL"
            tp1 = round(price * 0.98, 2)
            tp2 = round(price * 0.96, 2)
            sl = round(price * 1.02, 2)

        return {
            "symbol": symbol,
            "action": action,
            "entry": round(price, 2),
            "tp1": tp1,
            "tp2": tp2,
            "sl": sl
        }

    except Exception as e:
        return {
            "symbol": "ERROR",
            "action": "ERROR",
            "entry": str(e),
            "tp1": "-",
            "tp2": "-",
            "sl": "-"
        }


def format_signal(signal):
    return f"""🤖 Ourbit AI Signal

💰 ارز: {signal['symbol']}
📊 وضعیت: {signal['action']}

🎯 ورود: {signal['entry']}
✅ TP1: {signal['tp1']}
✅ TP2: {signal['tp2']}
🛑 SL: {signal['sl']}

⚠️ معامله را دستی انجام بده.
"""
