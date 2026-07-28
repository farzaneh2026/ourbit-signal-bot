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
        "AVAX/USDT",
        "DOT/USDT",
        "LTC/USDT",
        "ATOM/USDT",
        "UNI/USDT",
        "ETC/USDT",
        "FIL/USDT",
        "APT/USDT",
        "ARB/USDT",
        "OP/USDT",
        "NEAR/USDT"
    ]

    best_signal = None

    for symbol in symbols:

        try:

            candles = exchange.fetch_ohlcv(
                symbol,
                timeframe="30m",
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

            macd = ta.trend.MACD(
                df["close"]
            )

            df["macd"] = macd.macd()
            df["macd_signal"] = macd.macd_signal()

            atr = ta.volatility.AverageTrueRange(
                df["high"],
                df["low"],
                df["close"],
                window=14
            )

            df["atr"] = atr.average_true_range()


            price = float(df["close"].iloc[-1])
            ema = float(df["ema50"].iloc[-1])
            rsi = float(df["rsi"].iloc[-1])

            macd_value = float(df["macd"].iloc[-1])
            macd_sig = float(df["macd_signal"].iloc[-1])

            atr_value = float(df["atr"].iloc[-1])

            volume_now = float(df["volume"].iloc[-1])
            volume_avg = float(df["volume"].tail(20).mean())


            score = 0


            if price > ema:
                action = "BUY"
                score += 30

            elif price < ema:
                action = "SELL"
                score += 30

            else:
                continue
                            if action == "BUY" and rsi < 70:
                score += 20

            elif action == "SELL" and rsi > 30:
                score += 20

            else:
                continue


            if action == "BUY" and macd_value > macd_sig:
                score += 25

            elif action == "SELL" and macd_value < macd_sig:
                score += 25

            else:
                continue


            if volume_now > volume_avg:
                score += 15


            if score < 70:
                continue


            if action == "BUY":

                sl = round(price - (atr_value * 2), 4)
                tp1 = round(price + (atr_value * 2), 4)
                tp2 = round(price + (atr_value * 4), 4)
                tp3 = round(price + (atr_value * 6), 4)

            else:

                sl = round(price + (atr_value * 2), 4)
                tp1 = round(price - (atr_value * 2), 4)
                tp2 = round(price - (atr_value * 4), 4)
                tp3 = round(price - (atr_value * 6), 4)


            entry_status = "⏳ صبر کن"

            if action == "BUY":
                entry_status = "✅ بررسی ورود"

            elif action == "SELL":
                entry_status = "✅ بررسی ورود"


            if best_signal is None or score > best_signal["score"]:

                best_signal = {
                    "symbol": symbol,
                    "action": action,
                    "order_type": "LIMIT",
                    "score": score,
                    "entry": round(price, 4),
                    "tp1": tp1,
                    "tp2": tp2,
                    "tp3": tp3,
                    "sl": sl,
                    "rsi": round(rsi, 2),
                    "entry_status": entry_status,
                    "reason": "EMA + RSI + MACD + Volume + ATR"
                }


        except Exception:
            continue
