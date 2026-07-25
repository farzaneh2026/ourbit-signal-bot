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
                columns=[
                    "time",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume"
                ]
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

            volume_now = float(df["volume"].iloc[-1])
            volume_avg = float(df["volume"].tail(20).mean())

            score = 0

            if price > ema50:
                score += 30
                trend = "BUY"
            elif price < ema50:
                score += 30
                trend = "SELL"
            else:
                continue

            if trend == "BUY" and rsi < 70:
                score += 30

            elif trend == "SELL" and rsi > 30:
                score += 30

            else:
                continue

            if trend == "BUY" and macd_value > macd_signal:
                score += 30

            elif trend == "SELL" and macd_value < macd_signal:
                score += 30

            else:
                continue

            if volume_now > volume_avg:
                score += 10

            if score < 60:
                continue

            if trend == "BUY":
                tp1 = round(price * 1.02, 2)
                tp2 = round(price * 1.04, 2)
                tp3 = round(price * 1.06, 2)
                sl = round(price * 0.98, 2)

            else:
                tp1 = round(price * 0.98, 2)
                tp2 = round(price * 0.96, 2)
                tp3 = round(price * 0.94, 2)
                sl = round(price * 1.02, 2)


            if best is None or score > best["score"]:
                best = {
                    "score": score,
                    "symbol": symbol,
                    "action": trend,
                    "order_type": "LIMIT",
                    "entry": round(price, 2),
                    "tp1": tp1,
                    "tp2": tp2,
                    "tp3": tp3,
                    "sl": sl,
                    "rsi": round(rsi, 2),
                }


        if best:
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
            "score": "-"
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
            "score": "-"
        }



def format_signal(signal):
    return f"""🤖 Ourbit AI Signal

💰 ارز: {signal['symbol']}
📊 وضعیت: {signal['action']}
📌 سفارش: {signal['order_type']}

⭐ قدرت سیگنال: {signal['score']}/100

🎯 ورود: {signal['entry']}

✅ TP1: {signal['tp1']}
✅ TP2: {signal['tp2']}
✅ TP3: {signal['tp3']}

🛑 SL: {signal['sl']}

📈 RSI: {signal['rsi']}
📊 MACD: ✅
📊 Volume: ✅

⚠️ معامله را دستی انجام بده.
"""
