import ccxt
import pandas as pd
import ta
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

# اتصال به صرافی
exchange = ccxt.kucoin({
    "enableRateLimit": True,
})

# -----------------------------
# تنظیمات
# -----------------------------
SYMBOL = "SOL/USDT"
TIMEFRAME = "15m"
LIMIT = 200

ENTRY_TOLERANCE = 0.005   # 0.5 درصد


def get_signal():

    try:

        ohlcv = exchange.fetch_ohlcv(
            SYMBOL,
            timeframe=TIMEFRAME,
            limit=LIMIT
        )

        df = pd.DataFrame(
            ohlcv,
            columns=[
                "time",
                "open",
                "high",
                "low",
                "close",
                "volume"
            ]
        )

        # -----------------------------
        # اندیکاتورها
        # -----------------------------

        df["ema50"] = EMAIndicator(
            close=df["close"],
            window=50
        ).ema_indicator()

        df["rsi"] = RSIIndicator(
            close=df["close"],
            window=14
        ).rsi()

        macd = MACD(df["close"])

        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()

        atr = AverageTrueRange(
            df["high"],
            df["low"],
            df["close"]
        )

        df["atr"] = atr.average_true_range()

        last = df.iloc[-1]

        price = float(last["close"])
        ema = float(last["ema50"])
        rsi = float(last["rsi"])
        macd_value = float(last["macd"])
        macd_signal = float(last["macd_signal"])
        atr = float(last["atr"])
        volume = float(last["volume"])

        # -----------------------------
        # امتیازدهی
        # -----------------------------

        score = 0
        reason = []

        if price > ema:
            score += 25
            reason.append("EMA")

        if rsi > 55:
            score += 20
            reason.append("RSI")

        if macd_value > macd_signal:
            score += 30
            reason.append("MACD")

        avg_volume = df["volume"].tail(20).mean()

        if volume > avg_volume:
            score += 15
            reason.append("Volume")

        if atr > df["atr"].tail(20).mean():
            score += 10
            reason.append("ATR")

        strength = min(score, 100)
        # -----------------------------
        # تعیین جهت معامله
        # -----------------------------

        if strength >= 60:
            signal = "BUY"
        else:
            signal = "SELL"

        entry = price

        # -----------------------------
        # محاسبه TP و SL
        # -----------------------------

        if signal == "BUY":

            tp1 = round(entry * 1.02, 4)
            tp2 = round(entry * 1.04, 4)
            tp3 = round(entry * 1.06, 4)

            sl = round(entry * 0.98, 4)

        else:

            tp1 = round(entry * 0.98, 4)
            tp2 = round(entry * 0.96, 4)
            tp3 = round(entry * 0.94, 4)

            sl = round(entry * 1.02, 4)

        # -----------------------------
        # بررسی فاصله قیمت از ورود
        # -----------------------------

        current_price = float(
            exchange.fetch_ticker(SYMBOL)["last"]
        )

        diff = abs(current_price - entry) / entry

        if diff <= ENTRY_TOLERANCE:
            status = "🟢 READY TO ENTER"

        elif diff <= ENTRY_TOLERANCE * 2:
            status = "🟡 WAIT"

        else:
            status = "🔴 INVALID"

        # -----------------------------
        # آماده‌سازی خروجی
        # -----------------------------

        return {

            "symbol": SYMBOL,

            "signal": signal,

            "entry": round(entry, 4),

            "current_price": round(current_price, 4),

            "tp1": tp1,

            "tp2": tp2,

            "tp3": tp3,

            "sl": sl,

            "strength": strength,

            "status": status,

            "rsi": round(rsi, 2),

            "ema": round(ema, 4),

            "macd": round(macd_value, 4),

            "atr": round(atr, 4),

            "reason": " + ".join(reason)

        }
        
def format_signal(signal):
    if signal["symbol"] == "NONE":
        return (
            "❌ در حال حاضر سیگنال مناسبی پیدا نشد\n"
            "چند دقیقه دیگر دوباره امتحان کنید."
        )

    return f"""
🤖 Ourbit AI Signal v1.3

📊 Symbol: {signal['symbol']}
📈 Signal: {signal['signal']}

💰 Entry: {signal['entry']}
🎯 TP1: {signal['tp1']}
🎯 TP2: {signal['tp2']}
🎯 TP3: {signal['tp3']}
🛑 Stop Loss: {signal['sl']}

📡 Order: {signal['order_type']}
🔥 Strength: {signal['strength']}%

📉 RSI: {signal['rsi']}
📊 EMA: {signal['ema']}
📈 MACD: {signal['macd']}
📏 ATR: {signal['atr']}

📝 Reason:
{signal['reason']}
"""
⚠️ این فقط یک سیگنال تحلیلی است و مسئولیت معامله با کاربر است.
"""


# در صورت بروز خطا
def get_empty_signal():

    return {
        "symbol": "NONE"
    }


# اگر در get_signal خطایی رخ داد:
#
# except Exception as e:
#     print(e)
#     return get_empty_signal()
