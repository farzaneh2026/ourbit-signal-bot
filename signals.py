import ccxt
import pandas as pd
import ta

exchange = ccxt.kucoin()


def get_signal():
    symbols = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "DOT/USDT",
    "LTC/USDT",
    "AVAX/USDT",
    "LINK/USDT"
    ]

    for symbol in symbols:
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

            df["ema50"] = ta.trend.EMAIndicator(
                df["close"], window=50
            ).ema_indicator()

            df["ema200"] = ta.trend.EMAIndicator(
                df["close"], window=200
            ).ema_indicator()

            price = df["close"].iloc[-1]
            ema50 = df["ema50"].iloc[-1]
            ema200 = df["ema200"].iloc[-1]

                        if price > ema50:
                return {
                    "symbol": symbol,
                    "action": "BUY",
                    "entry": price,
                    "tp1": price * 1.02,
                    "tp2": price * 1.04,
                    "sl": price * 0.98
                }

            elif price < ema50:
                return {
                    "symbol": symbol,
                    "action": "SELL",
                    "entry": price,
                    "tp1": price * 0.98,
                    "tp2": price * 0.96,
                    "sl": price * 1.02
                }

        except Exception:
            continue

    return {
        "symbol": "NONE",
        "action": "WAIT",
        "entry": "-",
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

⚠️ معامله را دستی انجام بده.
"""
