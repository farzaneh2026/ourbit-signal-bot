import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Signal:
    direction: str
    symbol: str
    leverage: Optional[int] = None
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    source_message_id: Optional[int] = None
    raw_text: str = ''
    confirmed: bool = False


def _num(value: str) -> float:
    return float(value.replace(',', '').strip())


def _number_after(patterns, text):
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return _num(m.group(1))
    return None


def parse_toobit_signal(text: str, message_id: int | None = None) -> Signal | None:
    if not text:
        return None

    t = text.replace('٬', ',').replace('٫', '.')
    trans = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
    t = t.translate(trans)
    up = t.upper()

    # Only copy a real Toobit execution confirmation by default. This avoids
    # copying a pending signal that the user later rejects on Toobit.
    confirmed = bool(
        re.search(r'معامله\s+باز\s+شد', t, re.I)
        or re.search(r'TP\s*\+\s*SL\s*(?:تأیید|تایید)', t, re.I)
        or re.search(r'TP\s*\+\s*SL\s+CONFIRMED', up, re.I)
    )

    if not confirmed:
        return None

    if re.search(r'\b(?:BUY|LONG)\b|🟢', up):
        direction = 'LONG'
    elif re.search(r'\b(?:SELL|SHORT)\b|🔴', up):
        direction = 'SHORT'
    else:
        return None

    m = re.search(r'\b([A-Z0-9]{2,20})\s*(?:[-_/])\s*USDT\b', up)
    if not m:
        return None
    symbol = m.group(1) + '_USDT'

    leverage = _number_after([
        r'(?:LEVERAGE|اهرم)\s*[:：]?\s*(\d+)\s*[xX×]?'
    ], up)
    leverage = int(leverage) if leverage is not None else None

    entry = _number_after([
        r'(?:^|\n)\s*ENTRY\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)',
        r'(?:^|\n)\s*ورود\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)',
    ], t)

    tp = _number_after([
        r'(?:TP\s*\(\s*FULL[^\n]*\)|TP\s*\(\s*FULL\s*/\s*2R\s*\)|TP)\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)',
        r'(?:تیک?\s*پی|هدف)\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)',
    ], t)

    sl = _number_after([
        r'(?:^|\n)\s*SL\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)',
        r'(?:^|\n)\s*حد\s*ضرر\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)',
    ], t)

    # Some Toobit messages label the plan as "TP (Full / 2R)".
    if tp is None:
        m = re.search(r'TP[^\n]*?([0-9]+(?:\.[0-9]+)?)', t, re.I)
        if m:
            tp = _num(m.group(1))

    if entry is None or sl is None or tp is None:
        return None

    # Reject malformed geometry before anything reaches Ourbit.
    if direction == 'LONG' and not (sl < entry < tp):
        return None
    if direction == 'SHORT' and not (tp < entry < sl):
        return None

    return Signal(
        direction=direction,
        symbol=symbol,
        leverage=leverage,
        entry=entry,
        stop_loss=sl,
        take_profit=tp,
        source_message_id=message_id,
        raw_text=text,
        confirmed=True,
    )
