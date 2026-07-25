import ccxt
import pandas as pd
import ta

exchange = ccxt.kucoin()


def get_signal():
    symbols = [
        "BTC/USDT",
        "ETH/USDT",
        "BNB/USDT",
        "SOL/USDT",
        "XRP/USDT",
        "DOGE/USDT",
        "ADA/USDT",
        "TRX/USDT",
        "LINK/USDT",
        "AVAX/USDT"
    ]

    best = None

    try:
        for symbol in symbols:

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

            df["rsi"] = ta.momentum.RSIIndicator(
                df["close"],
                window=14
            ).rsi()

            macd = ta.trend.MACD(df["close"])

            df["macd"] = macd.macd()
            df["macd_signal"] = macd.macd_signal()

            price = float(df["close"].iloc[-1])
            ema50 = float(df["ema50"].iloc[-1])
            rsi = float(df["rsi"].iloc[-1])
            macd_value = float(df["macd"].iloc[-1])
            macd_signal = float(df["macd_signal"].iloc[-1])


            if price > ema50 and rsi < 70 and macd_value > macd_signal:

                action = "BUY"

                tp1 = round(price * 1.02, 2)
                tp2 = round(price * 1.04, 2)
                tp3 = round(price * 1.06, 2)
                sl = round(price * 0.98, 2)

                strength = 90


            elif price < ema50 and rsi > 30 and macd_value < macd_signal:

                action = "SELL"

                tp1 = round(price * 0.98, 2)
                tp2 = round(price * 0.96, 2)
                tp3 = round(price * 0.94, 2)
                sl = round(price * 1.02, 2)

                strength = 90

            else:
                continue


            if best is None or strength > best["strength"]:
                best = {
                    "strength": strength,
                    "symbol": symbol,
                    "action": action,
                    "order_type": "LIMIT",
                    "entry": round(price, 2),
                    "tp1": tp1,
                    "tp2": tp2,
                    "tp3": tp3,
                    "sl": sl,
                    "rsi": round(rsi, 2),
                    "strength_percent": strength
                }


        if best:
            del best["strength"]
            return best


        return {
            "symbol": "NONE",
            "action": "WAIT",
            "order_type": "-",
            "entry": "-",
            "tp1": "-",
            "tp2": "-",
            "tp3": "-",
            "sl": "-",
            "rsi": "-",
            "strength_percent": "-"
        }


    except Exception as e:
        return {
            "symbol": "ERROR",
            "action": "ERROR",
            "order_type": "-",
            "entry": str(e),
            "tp1": "-",
            "tp2": "-",
            "tp3": "-",
            "sl": "-",
            "rsi": "-",
            "strength_percent": "-"
        }


def format_signal(signal):
    return f"""🤖 Ourbit AI Signal

💰 ارز: {signal['symbol']}
📊 وضعیت: {signal['action']}
📌 سفارش: {signal['order_type']}

⭐ قدرت سیگنال: {signal['strength_percent']}%

🎯 ورود: {signal['entry']}

✅ TP1: {signal['tp1']}
✅ TP2: {signal['tp2']}
✅ TP3: {signal['tp3']}

🛑 SL: {signal['sl']}

📈 RSI: {signal['rsi']}
📊 MACD: ✅

⚠️ معامله را دستی انجام بده.
"""
